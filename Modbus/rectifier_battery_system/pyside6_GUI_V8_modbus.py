import sys
import os
import serial.tools.list_ports
from functools import partial

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QSpinBox, QMessageBox, QHeaderView, QDialog, QTableWidgetSelectionRange
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer
from pymodbus.client import ModbusSerialClient

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
# 알람 레지스터 정의
# ---------------------------
ALARM_STATIC = {
    "DC Overvoltage": 0x500E,
    "DC Undervoltage": 0x500F,
    "Load Fuse Break": 0x5010,
    # ... 기존과 동일 ...
}

def generate_di_registers():
    return {f"DI{i}": 0x5023 + (i - 1) for i in range(1, 13)}

def generate_lithium_battery_regs():
    return {f"Lithium Battery {n} Abnormal": 0x5036 + (n - 1) for n in range(1, 33)}

def generate_battery_bank_regs():
    regs = {}
    for n in range(1, 7):
        base = 0x5520 + (n - 1) * 16
        regs[f"Battery Bank {n} Fuse Break"] = base
        regs[f"Battery Bank {n} Middle Voltage Imbalance"] = base + 1
    return regs

def generate_ssu_pv_regs(max_units=60):
    regs = {}
    for n in range(1, max_units + 1):
        block = 0x5900 + (n - 1) * 16
        regs[f"SSU{n} Fault"] = block + 1
        regs[f"SSU{n} Communication Failure"] = block + 2
        regs[f"PV{n} Array Fault"] = block + 3
        regs[f"SSU{n} Protection"] = block + 4
    return regs

ALARM_REGISTERS = {}
ALARM_REGISTERS.update(ALARM_STATIC)
ALARM_REGISTERS.update(generate_di_registers())
ALARM_REGISTERS.update(generate_lithium_battery_regs())
ALARM_REGISTERS.update(generate_battery_bank_regs())
ALARM_REGISTERS.update(generate_ssu_pv_regs(max_units=10))

# ---------------------------
# 설정
# ---------------------------
MODULE_COUNT = 10
CELLS_PER_MODULE = 15

MODBUS_MODULE_BASE = 0x6000
MODBUS_MODULE_STRIDE = 0x20
MODBUS_CELL_VOLTAGE_OFFSET = 0x0
MODBUS_CELL_TEMP_OFFSET = 0x10
MODBUS_MODULE_TOTAL_VOLTAGE_OFFSET = 0x0F
MODBUS_MODULE_TEMP_OFFSET = 0x1F

# ---------------------------
# 세부 팝업창 (셀 1~15)
# ---------------------------
class ModuleDetailDialog(QDialog):
    def __init__(self, parent, module_num, data, mode):
        super().__init__(parent)
        self.setWindowTitle(f"Module {module_num} {'Voltages' if mode == 'v' else 'Temps'} Detail")
        layout = QVBoxLayout(self)

        for i, val in enumerate(data):
            label = QLabel(f"Cell {i+1}: {val:.3f} {'V' if mode == 'v' else '℃'}")
            layout.addWidget(label)
            
# ---------------------------
# 메인 GUI
# ---------------------------
class ModbusGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modbus RTU GUI with Alarms + Battery")
        self.resize(1600, 900)
        self.client = None

        self.alarm_timer = QTimer()
        self.alarm_timer.setInterval(5000)
        self.alarm_timer.timeout.connect(self.read_alarms)

        self.module_poll_timer = QTimer()
        self.module_poll_timer.setInterval(1000)
        self.module_poll_timer.timeout.connect(self.update_module_table)
        self.module_poll_timer.start()

        # 레이아웃
        main_layout = QHBoxLayout(self)
        left_v = QVBoxLayout()
        main_layout.addLayout(left_v, stretch=3)

        # ---------------------------
        # Device Info Table
        # ---------------------------
        left_v.addWidget(QLabel("🔹 Device Info"))
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(3)
        self.device_table.setHorizontalHeaderLabels(["Name", "Address", "Value"])
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.device_table.setRowCount(len(DEVICE_INFO_REGS))
        left_v.addWidget(self.device_table)
        
        # 포트/설정
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

        # 로그창
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

        # 오른쪽: 모듈 테이블
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout, stretch=2)
        right_layout.addWidget(QLabel("🔍 Modules Overview"))
        self.module_table = QTableWidget()
        self.module_table.setColumnCount(5)
        self.module_table.setHorizontalHeaderLabels(["Module", "Cell Voltages (V)", "Cell Temps (℃)", "Module Voltage (V)", "Module Temp (℃)"])
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

        # 초기화
        self.update_device_info_table()
        self.populate_ports()
        self.update_buttons(False)
        self.update_module_table()

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
        cell_vs, cell_ts, mod_v, mod_t = self.read_module_data(module_num)
        dialog = ModuleDetailDialog(self, module_num, cell_vs, cell_ts)
        dialog.exec()

    # ---------------------------
    # 포트 관련
    # ---------------------------
    def populate_ports(self):
        ports = serial.tools.list_ports.comports()
        self.combo_port.clear()
        for p in ports:
            self.combo_port.addItem(p.device)

    def log_message(self, msg):
        self.log.append(msg)

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
    # 레지스터 읽기
    # ---------------------------
    def read_register(self, address, count=1, slave=33, signed=False, scale=1):
        if not self.client:
            return None
        try:
            rr = self.client.read_holding_registers(address=address, count=count, slave=slave)
            if rr is None or (hasattr(rr, "isError") and rr.isError()):
                return None
            val = rr.registers[0] if hasattr(rr, "registers") and rr.registers else None
            if val is None:
                return None
            if signed and val > 0x7FFF:
                val -= 0x10000
            return val * scale
        except Exception:
            return None

    # ---------------------------
    # 모듈 데이터 읽기
    # ---------------------------
    def read_module_data(self, module_number):
        base = MODBUS_MODULE_BASE + (module_number - 1) * MODBUS_MODULE_STRIDE
        cell_vs, cell_ts = [], []
        for i in range(CELLS_PER_MODULE):
            v = self.read_register(base + MODBUS_CELL_VOLTAGE_OFFSET + i, scale=0.001)
            cell_vs.append(v)
        for i in range(CELLS_PER_MODULE):
            t = self.read_register(base + MODBUS_CELL_TEMP_OFFSET + i, signed=True, scale=0.1)
            cell_ts.append(t)
        mod_v = self.read_register(base + MODBUS_MODULE_TOTAL_VOLTAGE_OFFSET, scale=0.001)
        mod_t = self.read_register(base + MODBUS_MODULE_TEMP_OFFSET, signed=True, scale=0.1)

        # 모의 데이터 처리
        if any(v is None for v in cell_vs) or any(t is None for t in cell_ts) or mod_v is None or mod_t is None:
            cell_vs = [3.65 + 0.01 * module_number + 0.001 * i for i in range(CELLS_PER_MODULE)]
            cell_ts = [25.0 + module_number * 0.5 + 0.1 * i for i in range(CELLS_PER_MODULE)]
            mod_v = sum(cell_vs)
            mod_t = sum(cell_ts) / len(cell_ts)

        return cell_vs, cell_ts, mod_v, mod_t

    # ---------------------------
    # 모듈 테이블 업데이트
    # ---------------------------
    def update_module_table(self):
        for i in range(MODULE_COUNT):
            cell_vs, cell_ts, mod_v, mod_t = self.read_module_data(i + 1)
            self.module_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.module_table.setItem(
                i, 1,
                QTableWidgetItem(", ".join(f"{v:.2f}" if v is not None else "N/A" for v in cell_vs))
            )
            self.module_table.setItem(
                i, 2,
                QTableWidgetItem(", ".join(f"{t:.1f}" if t is not None else "N/A" for t in cell_ts))
            )
            self.module_table.setItem(i, 3, QTableWidgetItem(f"{mod_v:.2f}" if mod_v is not None else "N/A"))
            self.module_table.setItem(i, 4, QTableWidgetItem(f"{mod_t:.1f}" if mod_t is not None else "N/A"))

    # ---------------------------
    # 알람 읽기
    # ---------------------------
    def read_alarms(self):
        if not self.client:
            self.log_message("❌ Not connected - cannot read alarms")
            return
        self.log_message("=== Reading Alarms ===")
        alarm_found = False
        for name, addr in sorted(ALARM_REGISTERS.items(), key=lambda kv: kv[1]):
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
# 실행부
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ModbusGUI()
    gui.show()
    sys.exit(app.exec())
