import sys
import os
import queue
import threading
import time
import logging
from logging.handlers import RotatingFileHandler
import serial.tools.list_ports
from functools import partial
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QSpinBox, QMessageBox, QHeaderView, QDialog
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer, QObject, Signal
from pymodbus.client import ModbusSerialClient
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ---------------------------
# 장치 기본 정보 레지스터
# ---------------------------
DEVICE_INFO_REGS = {
    "Manufacturer code": (0x0000, 1, "UNIT16"),
    "Equipment type": (0x0001, 1, "UNIT16"),
    "Protocol version": (0x0002, 1, "UNIT16"),
    "Software version": (0x0003, 1, "UNIT16"),
    "Hardware version": (0x0004, 1, "UNIT16"),
    "System type": (0x0005, 14, "String"),  # 0x0005~0x0012 = 14 words = 28 bytes
    "Software entire version": (0x0013, 14, "String"),  # 0x0013~0x0020
}

# ---------------------------
# 알람 레지스터 정의 (N=1~10 확장)
# ---------------------------
ALARM_REGISTERS = {}

# 1) 고정 주소 알람
ALARM_REGISTERS.update({
    "Battery Missing": 0x5022,  # MA (0x00: normal; 0x01: alarm)
})

# 2) Lithium Battery 1~10
for n in range(1, 11):
    ALARM_REGISTERS[f"Lithium Battery {n} Abnormal"] = 0x5036 + (n - 1) * 1

# 3) 0x8431+(N-1)*64 패턴 (10개씩 확장)
for n in range(1, 11):
    base = 0x8431 + (n - 1) * 64
    ALARM_REGISTERS.update({
        f"Charge Over Voltage {n}": base,
        f"Charge Over Current {n}": base + 1,
        f"Overdischarge {n}": base + 2,
        f"Heavy Load Warning {n}": base + 3,
        f"Reversely Connection {n}": base + 4,
        f"Charge Over/Discharge Over Temp {n}": base + 5,
        f"Communication Failure {n}": base + 6,
        f"Low Temperature {n}": base + 7,
        f"Discharge/Charge High Temp Protection {n}": base + 8,
        f"Low Temperature Protection {n}": base + 9,
        f"Overcharge Protection {n}": base + 10,
        f"Overdischarge Protection {n}": base + 11,
        f"Charge/Discharge Overcurrent Protection {n}": base + 12,
    })

# ---------------------------
# 설정 (업데이트된 주소 적용)
# ---------------------------
MODULE_COUNT = 10
CELLS_PER_MODULE = 15

# 새 테이블 기준:
MODBUS_MODULE_BASE = 0xA731
MODBUS_MODULE_STRIDE = 0x40  # (64 decimal)

# 새 전압 및 온도 시작 오프셋
MODBUS_CELL_TEMP_BASE_OFFSET = 0xA73A - MODBUS_MODULE_BASE  # 0x09
MODBUS_CELL_VOLT_BASE_OFFSET = 0xA750 - MODBUS_MODULE_BASE  # 0x1F

MODBUS_CELL_TEMP_OFFSET_STEP = 1
MODBUS_CELL_VOLT_OFFSET_STEP = 1

BATTERY_VOLTAGE_OFFSET = 0xA731 - MODBUS_MODULE_BASE  # 0
BATTERY_CURRENT_OFFSET = 0xA733 - MODBUS_MODULE_BASE  # 2
BATTERY_SOC_OFFSET = 0xA739 - MODBUS_MODULE_BASE      # 8

# ---------------------------
# 세부 팝업창 (셀 1~15)
# ---------------------------
class ModuleDetailDialog(QDialog):
    def __init__(self, parent, module_num, cell_vs, cell_ts):
        super().__init__(parent)
        self.setWindowTitle(f"Module {module_num} Detail")
        layout = QVBoxLayout(self)
        header = QLabel(f"📊 Module {module_num} — Cell Voltage & Temperature")
        layout.addWidget(header)
        fig = Figure(figsize=(6, 3))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.plot(range(1, 1 + len(cell_vs)), cell_vs, "bo-", label="Voltage (V)")
        ax.set_xlabel("Cell #")
        ax.set_ylabel("Voltage (V)")
        ax.set_ylim(3.4, 4.3)
        ax2 = ax.twinx()
        ax2.plot(range(1, 1 + len(cell_ts)), cell_ts, "r^-", label="Temp (℃)")
        ax2.set_ylabel("Temp (℃)")
        ax2.set_ylim(20, 60)
        fig.tight_layout()
        layout.addWidget(canvas)
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Voltage (V)", "Temperature (°C)"])
        table.setRowCount(len(cell_vs))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i in range(len(cell_vs)):
            v = cell_vs[i] if cell_vs[i] is not None else 0
            t = cell_ts[i] if cell_ts[i] is not None else 0
            table.setItem(i, 0, QTableWidgetItem(f"{v:.3f}"))
            table.setItem(i, 1, QTableWidgetItem(f"{t:.1f}"))
        layout.addWidget(table)
        self.setLayout(layout)
        self.resize(500, 600)

    def closeEvent(self, event):
        if hasattr(self.parent(), "detail_dialog"):
            self.parent().detail_dialog = None
        event.accept()

# ---------------------------
# 비동기 로그 에미터/워커
# ---------------------------
class LogEmitter(QObject):
    new_log = Signal(str)  # 일반 로그 (QTextEdit)
    new_txrx = Signal(str, str, str)  # time, direction, data


class ModbusLogWorker:
    """백그라운드에서 큐를 읽어 시그널을 통해 UI로 전달한다."""
    def __init__(self, emitter: LogEmitter, maxsize=1000):
        self.emitter = emitter
        self._q = queue.Queue(maxsize=maxsize)
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        self.maxsize = maxsize

    def enqueue_log(self, line: str):
        try:
            self._q.put(("log", line), block=False)
        except queue.Full:
            try:
                # drop oldest to make room
                _ = self._q.get_nowait()
                self._q.put(("log", line), block=False)
                logging.warning("Log queue full: dropped oldest log to enqueue new log")
            except Exception:
                logging.exception("Failed to enqueue log when queue was full")

    def enqueue_txrx(self, time_str: str, direction: str, data: str):
        try:
            self._q.put(("txrx", time_str, direction, data), block=False)
        except queue.Full:
            try:
                _ = self._q.get_nowait()
                self._q.put(("txrx", time_str, direction, data), block=False)
                logging.warning("TX/RX queue full: dropped oldest TX/RX to enqueue new item")
            except Exception:
                logging.exception("Failed to enqueue txrx when queue was full")

    def stop(self):
        self._running = False
        self._q.put(("__stop__",))
        self._thread.join(timeout=2)

    def _worker_loop(self):
        while self._running:
            try:
                item = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if not item:
                continue
            if item[0] == "__stop__":
                break
            if item[0] == "log":
                _, line = item
                self.emitter.new_log.emit(line)
            elif item[0] == "txrx":
                _, time_str, direction, data = item
                self.emitter.new_txrx.emit(time_str, direction, data)


# ---------------------------
# 로깅 설정 (파일, 로테이팅)
# ---------------------------
def setup_file_logging(log_path="modbus_gui.log", max_bytes=2_000_000, backup_count=3, level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    # 콘솔 핸들러도 추가 (선택적)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)


# ---------------------------
# 메인 GUI
# ---------------------------
class ModbusGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.detail_dialog = None
        self.setWindowTitle("Modbus RTU GUI with Alarms + Battery + TX/RX Log")
        self.resize(1700, 950)
        self.client = None

        # 설정값 (UI로 변경 가능)
        self.log_file_path = os.path.join(os.path.dirname(__file__), "modbus_gui.log")
        setup_file_logging(log_path=self.log_file_path)
        self.log_level = logging.INFO
        self.modbus_retries = 2
        self.modbus_retry_delay = 0.2  # seconds
        self.log_queue_maxsize = 2000

        # 로그 워커/에미터
        self.log_emitter = LogEmitter()
        self.log_worker = ModbusLogWorker(self.log_emitter, maxsize=self.log_queue_maxsize)
        self.log_emitter.new_log.connect(self._append_log_to_widget)
        self.log_emitter.new_txrx.connect(self._append_txrx_row)

        # 기본: TX/RX 로그를 기본적으로 "중지" 상태로 설정
        self.log_enabled = False

        # 타이머
        self.alarm_timer = QTimer()
        self.alarm_timer.setInterval(5000)
        self.alarm_timer.timeout.connect(self.read_alarms)
        self.module_poll_timer = QTimer()
        self.module_poll_timer.setInterval(5000)
        self.module_poll_timer.timeout.connect(self.update_module_table)
        self.module_poll_timer.start()

        # 전체 레이아웃
        main_layout = QHBoxLayout(self)
        left_v = QVBoxLayout()
        main_layout.addLayout(left_v, stretch=3)

        # ---------------------------
        # Device Info
        # ---------------------------
        left_v.addWidget(QLabel("🔹 Device Info"))
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(3)
        self.device_table.setHorizontalHeaderLabels(["Name", "Address", "Value"])
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.device_table.setRowCount(len(DEVICE_INFO_REGS))
        left_v.addWidget(self.device_table)

        # 포트 설정
        top_port = QHBoxLayout()
        left_v.addLayout(top_port)
        top_port.addWidget(QLabel("COM Port:"))
        self.combo_port = QComboBox()
        top_port.addWidget(self.combo_port)
        top_port.addWidget(QLabel("Baudrate:"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        top_port.addWidget(self.combo_baud)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_modbus)
        top_port.addWidget(self.btn_connect)
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self.disconnect_modbus)
        self.btn_disconnect.setEnabled(False)
        top_port.addWidget(self.btn_disconnect)
        top_port.addStretch()
        top_port.addWidget(QLabel("Module Poll Interval (s):"))
        self.spin_poll_interval = QSpinBox()
        self.spin_poll_interval.setRange(1, 60)
        self.spin_poll_interval.setValue(1)
        self.spin_poll_interval.valueChanged.connect(self.change_poll_interval)
        top_port.addWidget(self.spin_poll_interval)

        # 로그 레벨/큐 설정 UI
        controls_h = QHBoxLayout()
        left_v.addLayout(controls_h)
        controls_h.addWidget(QLabel("Log Level:"))
        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.combo_log_level.setCurrentText("INFO")
        self.combo_log_level.currentTextChanged.connect(self.change_log_level)
        controls_h.addWidget(self.combo_log_level)

        controls_h.addWidget(QLabel("Queue Max:"))
        self.spin_queue_max = QSpinBox()
        self.spin_queue_max.setRange(100, 10000)
        self.spin_queue_max.setValue(self.log_queue_maxsize)
        self.spin_queue_max.valueChanged.connect(self.change_queue_max)
        controls_h.addWidget(self.spin_queue_max)

        controls_h.addWidget(QLabel("Retries:"))
        self.spin_retries = QSpinBox()
        self.spin_retries.setRange(0, 10)
        self.spin_retries.setValue(self.modbus_retries)
        self.spin_retries.valueChanged.connect(self.change_retries)
        controls_h.addWidget(self.spin_retries)

        controls_h.addWidget(QLabel("Retry Delay (ms):"))
        self.spin_retry_delay = QSpinBox()
        self.spin_retry_delay.setRange(50, 2000)
        self.spin_retry_delay.setValue(int(self.modbus_retry_delay * 1000))
        self.spin_retry_delay.valueChanged.connect(self.change_retry_delay)
        controls_h.addWidget(self.spin_retry_delay)

        # 로그
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(140)
        left_v.addWidget(self.log)

        # 배터리 이미지
        self.label_batt = QLabel(self)
        image_path = os.path.join(os.path.dirname(__file__), "배터리시스템.png")
        if not os.path.exists(image_path):
            QMessageBox.warning(None, "이미지 오류", f"이미지를 찾을 수 없습니다:\n{image_path}")
            pixmap = QPixmap(300, 800)
            pixmap.fill(Qt.lightGray)
        else:
            pixmap = QPixmap(image_path)
            pixmap = pixmap.scaled(pixmap.width(), pixmap.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label_batt.setPixmap(pixmap)
        self.label_batt.setScaledContents(True)
        self.label_batt.setFixedSize(pixmap.width(), pixmap.height())
        left_v.addWidget(self.label_batt, alignment=Qt.AlignLeft)

        # 이미지 오버레이 버튼
        self.overlay_buttons = []
        self.add_battery_overlay_buttons()

        # ---------------------------
        # 오른쪽: 모듈 테이블 + TX/RX 로그
        # ---------------------------
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout, stretch=3)
        right_layout.addWidget(QLabel("🔍 Modules Overview"))
        self.module_table = QTableWidget()
        self.module_table.setColumnCount(3)
        self.module_table.setHorizontalHeaderLabels(["Module", "Voltage (V)", "Temp (℃)"])
        self.module_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.module_table.setRowCount(MODULE_COUNT)
        right_layout.addWidget(self.module_table)

        # 알람 버튼
        bottom_buttons = QHBoxLayout()
        right_layout.addLayout(bottom_buttons)
        self.btn_read_alarms = QPushButton(f"Read Alarms ({len(ALARM_REGISTERS)})")
        self.btn_read_alarms.clicked.connect(self.read_alarms)
        bottom_buttons.addWidget(self.btn_read_alarms)
        self.btn_monitor = QPushButton("Start Alarm Monitor")
        self.btn_monitor.setCheckable(True)
        self.btn_monitor.clicked.connect(self.toggle_alarm_monitor)
        bottom_buttons.addWidget(self.btn_monitor)
        bottom_buttons.addStretch()

        # ---------------------------
        # TX/RX 로그 추가 섹션
        # ---------------------------
        right_layout.addWidget(QLabel("📡 Modbus TX/RX Log (Raw Data)"))
        self.txrx_table = QTableWidget()
        self.txrx_table.setColumnCount(3)
        self.txrx_table.setHorizontalHeaderLabels(["Time", "Direction", "Data (Hex)"])
        self.txrx_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        time_col_index = 0
        direction_col_index = 1
        header = self.txrx_table.horizontalHeader()
        header.setSectionResizeMode(time_col_index, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(direction_col_index, QHeaderView.ResizeToContents)
        self.txrx_table.setColumnWidth(time_col_index, 20)
        self.txrx_table.setColumnWidth(direction_col_index, 10)
        right_layout.addWidget(self.txrx_table)

        # TX/RX 상태 박스
        txrx_layout = QHBoxLayout()
        right_layout.addLayout(txrx_layout)
        self.tx_box = QPushButton("TX")
        self.tx_box.setStyleSheet("background-color: gray; color: white; font-weight: bold;")
        self.rx_box = QPushButton("RX")
        self.rx_box.setStyleSheet("background-color: gray; color: white; font-weight: bold;")
        for box in [self.tx_box, self.rx_box]:
            box.setFixedWidth(80)
            box.setEnabled(False)
        txrx_layout.addWidget(self.tx_box)
        txrx_layout.addWidget(self.rx_box)
        
        # 🔹 LOG START/STOP 버튼 추가 (초기: Start Log로 표시)
        self.btn_toggle_log = QPushButton("Start Log")
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.setStyleSheet("background-color: salmon; font-weight: bold;")
        self.btn_toggle_log.clicked.connect(self.toggle_txrx_log)
        txrx_layout.addWidget(self.btn_toggle_log)
        txrx_layout.addStretch()

        # 초기화
        self.update_device_info_table()
        self.populate_ports()
        self.update_buttons(False)
        self.module_table.cellClicked.connect(self.handle_module_table_click)
        self.update_module_table()

    # ---------------------------
    # 앱 종료 시 워커 중지
    # ---------------------------
    def stop_log_worker(self):
        try:
            self.log_worker.stop()
        except Exception:
            pass

    # ---------------------------
    # 로그 위젯에 직접 추가 (메인스레드에서 실행되어야 함)
    # ---------------------------
    def _append_log_to_widget(self, msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log.append(f"{timestamp} {msg}")

    def _append_txrx_row(self, time_str: str, direction: str, data: str):
        row = self.txrx_table.rowCount()
        self.txrx_table.insertRow(row)
        self.txrx_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.txrx_table.setItem(row, 1, QTableWidgetItem(direction))
        self.txrx_table.setItem(row, 2, QTableWidgetItem(data))
        self.txrx_table.scrollToBottom()

    def flash_tx(self):
        self.tx_box.setStyleSheet("background-color: green; color: white; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self.tx_box.setStyleSheet("background-color: gray; color: white;"))

    def flash_rx(self):
        self.rx_box.setStyleSheet("background-color: green; color: white; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self.rx_box.setStyleSheet("background-color: gray; color: white;"))

     # ---------------------------
    # Device Info 읽기
    # ---------------------------
    def update_device_info_table(self):
        if not self.client:
            for row, (name, (addr, count, dtype)) in enumerate(DEVICE_INFO_REGS.items()):
                self.device_table.setItem(row, 0, QTableWidgetItem(name))
                self.device_table.setItem(row, 1, QTableWidgetItem(f"0x{addr:04X}"))
                self.device_table.setItem(row, 2, QTableWidgetItem("N/A"))
            return

        for row, (name, (addr, count, dtype)) in enumerate(DEVICE_INFO_REGS.items()):
            val = None
            if dtype == "UNIT16":
                val = self.read_register(addr)
            elif dtype == "String":
                chars = []
                for i in range(count):
                    word = self.read_register(addr + i)
                    if word is None:
                        continue
                    chars.append(chr((word >> 8) & 0xFF))
                    chars.append(chr(word & 0xFF))
                val = "".join(chars).strip()
            self.device_table.setItem(row, 0, QTableWidgetItem(name))
            self.device_table.setItem(row, 1, QTableWidgetItem(f"0x{addr:04X}"))
            self.device_table.setItem(row, 2, QTableWidgetItem(str(val) if val else "N/A"))
    # ---------------------------
    # 이미지 오버레이 버튼
    # ---------------------------
    def add_battery_overlay_buttons(self):
        label_w = self.label_batt.width()
        label_h = self.label_batt.height()
        total_sections = MODULE_COUNT + 1
        section_height = max(20, label_h // total_sections)
        for i in range(total_sections):
            y = label_h - (i + 1) * section_height
            btn = QPushButton(self.label_batt)
            btn.setGeometry(0, y, label_w, section_height)
            btn.setStyleSheet("background-color: rgba(255, 223, 0, 80); border: none;")
            btn.clicked.connect(partial(self.on_overlay_clicked, i + 1))
            btn.show()
            self.overlay_buttons.append(btn)

    def on_overlay_clicked(self, module_num):
        if module_num == 11:
            self.log_message("⚠️배터리 모듈 영역이 아닙니다.")
            return 
        if self.detail_dialog is not None and self.detail_dialog.isVisible():
            self.detail_dialog.close()
        cell_vs, cell_ts, mod_v, mod_t = self.read_module_data(module_num)
        self.detail_dialog = ModuleDetailDialog(self, module_num, cell_vs, cell_ts)
        self.detail_dialog.show()

    # ---------------------------
    # 포트 관련
    # ---------------------------
    def populate_ports(self):
        ports = serial.tools.list_ports.comports()
        self.combo_port.clear()
        for p in ports:
            self.combo_port.addItem(p.device)

    def log_message(self, msg):
        # 로깅 모듈에도 남김
        logging.info(msg)
        # 큐에 넣으면 워커가 UI 스레드로 안전하게 전달
        self.log_worker.enqueue_log(msg)

    def update_buttons(self, connected):
        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
        self.btn_read_alarms.setEnabled(connected)
        self.btn_monitor.setEnabled(True)

    # ---------------------------
    # Modbus 연결
    # ---------------------------
    def connect_modbus(self):
        port = self.combo_port.currentText()
        if not port:
            QMessageBox.warning(self, "Connection Error", "❌ COM 포트를 선택하세요.")
            return
        baud = int(self.combo_baud.currentText())
        try:
            self.client = ModbusSerialClient(port=port, baudrate=baud, stopbits=1, bytesize=8, parity='N', timeout=1)
            if self.client.connect():
                self.log_message(f"✅ Connected to {port} @ {baud}bps")
                QMessageBox.information(self, "Connected", f"✅ {port} 연결 성공!")
                self.update_buttons(True)
            else:
                self.client = None
                self.log_message(f"❌ Failed to connect to {port}")
                QMessageBox.critical(self, "Connection Failed", f"❌ {port} 연결 실패\n원인: 장치 응답 없음")
        except Exception as e:
            self.client = None
            self.log_message(f"❌ Exception during connection: {e}")
            QMessageBox.critical(self, "Connection Error", f"❌ 연결 중 오류 발생\n원인: {str(e)}")

    def disconnect_modbus(self):
        if self.client:
            try:
                self.client.close()
                self.client = None
                self.log_message("✅ Modbus disconnected")
                QMessageBox.information(self, "Disconnected", "✅ Modbus 연결 해제 완료")
            except Exception as e:
                self.log_message(f"❌ Exception during disconnect: {e}")
                QMessageBox.critical(self, "Disconnect Error", f"❌ 연결 해제 중 오류 발생\n원인: {str(e)}")
        else:
            self.log_message("⚠ Not connected")
            QMessageBox.warning(self, "Disconnect", "⚠ 연결 상태가 아닙니다.")
        self.update_buttons(False)

    # ---------------------------
    # 레지스터 읽기 (재시도 로직 포함)
    # ---------------------------
    def read_register(self, address, count=1, slave=33, signed=False, scale=1):
        if not self.client:
            return None
        last_exc = None
        for attempt in range(self.modbus_retries + 1):
            try:
                self.flash_tx()
                self.add_txrx_log("TX", f"Read @0x{address:04X}, count={count}")
                rr = self.client.read_holding_registers(address=address, count=count, slave=slave)
                self.flash_rx()
                if rr is None or (hasattr(rr, "isError") and rr.isError()):
                    last_exc = Exception("No response / Modbus error")
                    raise last_exc
                val = rr.registers[0] if hasattr(rr, "registers") and rr.registers else None
                if val is not None:
                    self.add_txrx_log("RX", f"0x{val:04X}")
                if signed and val is not None and val > 0x7FFF:
                    val -= 0x10000
                return val * scale if val is not None else None
            except Exception as e:
                last_exc = e
                logging.debug(f"Read register attempt {attempt} failed: {e}")
                # 짧은 대기 후 재시도
                if attempt < self.modbus_retries:
                    time.sleep(self.modbus_retry_delay)
        # 모든 시도 실패
        logging.error(f"Failed to read register 0x{address:04X} after {self.modbus_retries + 1} attempts: {last_exc}")
        self.add_txrx_log("ERR", f"Read @0x{address:04X} failed: {last_exc}")
        return None

    # ---------------------------
    # 모듈 데이터 읽기 (주소 체계 반영)
    # ---------------------------
    def read_module_data(self, module_number):
        base = MODBUS_MODULE_BASE + (module_number - 1) * MODBUS_MODULE_STRIDE
        cell_vs, cell_ts = [], []

        for i in range(CELLS_PER_MODULE):
            addr = base + MODBUS_CELL_VOLT_BASE_OFFSET + i * MODBUS_CELL_VOLT_OFFSET_STEP
            v = self.read_register(addr, scale=0.001)
            cell_vs.append(v)

        for i in range(CELLS_PER_MODULE):
            addr = base + MODBUS_CELL_TEMP_BASE_OFFSET + i * MODBUS_CELL_TEMP_OFFSET_STEP
            t = self.read_register(addr, signed=True, scale=0.1)
            cell_ts.append(t)

        mod_v = self.read_register(base + BATTERY_VOLTAGE_OFFSET, count=2, scale=0.001)
        mod_t = sum(t for t in cell_ts if t is not None) / len(cell_ts)

        if any(v is None for v in cell_vs) or any(t is None for t in cell_ts) or mod_v is None:
            cell_vs = [3.65 + 0.01 * module_number + 0.001 * i for i in range(CELLS_PER_MODULE)]
            cell_ts = [25.0 + module_number * 0.5 + 0.1 * i for i in range(CELLS_PER_MODULE)]
            mod_v = sum(cell_vs)
            mod_t = sum(cell_ts) / len(cell_ts)

        return cell_vs, cell_ts, mod_v, mod_t

    def handle_module_table_click(self, row, col):
        if row + 1 == 11:
            self.log.append("⚠️ Module 11은 배터리 모듈이 아닙니다.")
            return
        if col in [1, 2]:
            cell_vs, cell_ts, mod_v, mod_t = self.read_module_data(row + 1)
            self.detail_dialog = ModuleDetailDialog(self, row + 1, cell_vs, cell_ts)
            self.detail_dialog.show()

    # ---------------------------
    # 모듈 테이블 업데이트
    # ---------------------------
    def update_module_table(self):
        for i in range(MODULE_COUNT):
            cell_vs, cell_ts, mod_v, mod_t = self.read_module_data(i + 1)
            self.module_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.module_table.setItem(i, 1, QTableWidgetItem(f"{mod_v:.2f}" if mod_v is not None else "N/A"))
            self.module_table.setItem(i, 2, QTableWidgetItem(f"{mod_t:.1f}" if mod_t is not None else "N/A"))

    # ---------------------------
    # 알람 읽기
    # ---------------------------
    def read_alarms(self):
        if not self.client:
            self.log_message("❌ Not connected - cannot read alarms")
            return
        self.log_message("=== Reading Alarms ===")
        alarm_found = False
        int_items = [(k, v) for k, v in ALARM_REGISTERS.items() if isinstance(v, int)]
        str_items = [(k, v) for k, v in ALARM_REGISTERS.items() if not isinstance(v, int)]

        for name, addr in sorted(int_items, key=lambda kv: kv[1]) + str_items:
            if isinstance(addr, str):
                self.log_message(f"ℹ️ {name} uses calculated address expression: {addr}")
                continue
            val = self.read_register(addr)
            if val is None:
                continue
            if isinstance(val, (int, float)) and int(val) != 0:
                self.log_message(f"🚨 ALARM -> {name} @0x{addr:04X} : 0x{int(val):02X}")
                alarm_found = True
            else:
                self.log_message(f"✅ Normal -> {name} @0x{addr:04X}")
        self.btn_read_alarms.setStyleSheet("background-color: salmon" if alarm_found else "background-color: lightgreen")
        self.log_message("=== Alarms Read Complete ===")

    # ---------------------------
    # 알람 모니터 토글
    # ---------------------------
    def toggle_alarm_monitor(self, checked):
        if checked:
            self.alarm_timer.start()
            self.btn_monitor.setText("Stop Alarm Monitor")
        else:
            self.alarm_timer.stop()
            self.btn_monitor.setText("Start Alarm Monitor")

    # ---------------------------
    # 폴링 간격 변경
    # ---------------------------
    def change_poll_interval(self, val):
        self.module_poll_timer.setInterval(val * 1000)
        self.log_message(f"Module poll interval set to {val}s")

    # ---------------------------
    # 로그 설정 변경 콜백들
    # ---------------------------
    def change_log_level(self, text):
        level = getattr(logging, text.upper(), logging.INFO)
        logging.getLogger().setLevel(level)
        self.log_message(f"Log level set to {text}")

    def change_queue_max(self, val):
        # 큐 교체: 새로운 worker 생성 후 기존 정지
        try:
            old_worker = self.log_worker
            self.log_worker = ModbusLogWorker(self.log_emitter, maxsize=val)
            old_worker.stop()
            self.log_message(f"Log queue max changed to {val}")
        except Exception as e:
            logging.exception("Failed to change queue max")
            self.log_message(f"Failed to change queue max: {e}")

    def change_retries(self, val):
        self.modbus_retries = val
        self.log_message(f"Modbus retries set to {val}")

    def change_retry_delay(self, ms):
        self.modbus_retry_delay = ms / 1000.0
        self.log_message(f"Modbus retry delay set to {self.modbus_retry_delay}s")

    # ---------------------------
    # TX/RX LOG START/STOP 토글
    # ---------------------------
    def toggle_txrx_log(self, checked):
        # 체크되면 로그를 시작 (True = 로그 ON)
        self.log_enabled = checked
        if self.log_enabled:
            self.btn_toggle_log.setText("Stop Log")
            self.btn_toggle_log.setStyleSheet("background-color: lightgreen; font-weight: bold;")
            self.log_message("🟢 TX/RX 로그 기록이 시작되었습니다.")
        else:
            self.btn_toggle_log.setText("Start Log")
            self.btn_toggle_log.setStyleSheet("background-color: salmon; font-weight: bold;")
            self.log_message("⛔ TX/RX 로그 기록이 중지되었습니다.")

    # ---------------------------
    # TX/RX 로그 기록 함수 (비동기 큐에 넣음)
    # ---------------------------
    def add_txrx_log(self, direction, data):
        # 로그가 비활성화 되어 있으면 UI로는 보내지 않지만 파일에는 남김
        time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        # 항상 파일로 남김
        logging.info(f"{direction}: {data}")
        if not getattr(self, "log_enabled", False):
            return
        self.log_worker.enqueue_txrx(time_str, direction, data)

# ---------------------------
# 실행부
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ModbusGUI()
    app.aboutToQuit.connect(gui.stop_log_worker)
    gui.show()
    sys.exit(app.exec())
