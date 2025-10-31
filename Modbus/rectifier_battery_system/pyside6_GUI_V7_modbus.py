import sys
import os
import serial.tools.list_ports
from functools import partial

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QSpinBox, QMessageBox, QDialog, QHeaderView, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from pymodbus.client import ModbusSerialClient

# ---------------------------
# 알람 레지스터 정의
# ---------------------------
ALARM_STATIC = {
    "DC Overvoltage": 0x500E,
    "DC Undervoltage": 0x500F,
    "Load Fuse Break": 0x5010,
    "Door Alarm": 0x5011,
    "Water Alarm": 0x5012,
    "Smoke Alarm": 0x5013,
    "High Equipment Area Temperature": 0x5014,
    "Equipment Area Temperature Sensor Fault": 0x5015,
    "Ambient Humidity Sensor Fault": 0x5016,
    "LLVD1 Warning": 0x5017,
    "LLVD1 Disconnected": 0x5018,
    "LLVD2 Warning": 0x5019,
    "LLVD2 Disconnected": 0x501A,
    "DC Ultra High Voltage": 0x501B,
    "DC Ultra Low Voltage": 0x501C,
    "Controller Hardware Fault": 0x501D,
    "Battery Test Failure": 0x501E,
    "LVD Disabled": 0x501F,
    "Low Rectifier Remaining Capacity": 0x5020,
    "Battery Discharge": 0x5021,
    "Battery Missing": 0x5022,
    "Urgent Alarm (CELLNEX)": 0x502F,
    "Non-urgent Alarm (CELLNEX)": 0x5030,
    "Fuse Broken Alarm (CELLNEX)": 0x5031,
    "LLVD3 Warning": 0x5032,
    "LLVD3 Disconnected": 0x5033,
    "LLVD4 Warning": 0x5034,
    "LLVD4 Disconnected": 0x5035,
    "Battery High Temperature": 0x5500,
    "Battery Temperature Sensor 1 Fault": 0x5501,
    "BLVD Disconnected": 0x5502,
    "BLVD Warning": 0x5503,
    "Battery Forcibly Connection": 0x5504,
    "Battery Low Temperature": 0x5505,
    "Battery Fuse Blown": 0x5506,
    "Battery Contactor Fault": 0x5507,
    "Battery Reversely Connection": 0x5508,
    "Return Air Temperature Sensor 1 Fault": 0x5700,
    "Outdoor Ambient Temperature Sensor Fault": 0x5701,
    "High Battery Area Temperature": 0x576A,
    "Battery Area Temperature Sensor Fault": 0x576B,
    "Battery 2 High Temperature": 0x576C,
    "Battery Temperature Sensor 2 Fault": 0x576D,
    "Return Air Temperature Sensor 2 Fault": 0x576E,
    "Door Alarm (Battery Area)": 0x576F,
    "Battery Cabinet Communication Failure": 0x5772,
    "SSU Lost": 0x5900,
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
# 모듈 설정
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
# 모듈 상세 팝업
# ---------------------------
class ModuleDetailDialog(QDialog):
    def __init__(self, parent, module_number, cell_voltages, cell_temps):
        super().__init__(parent)
        self.setWindowTitle(f"Module {module_number} Details")
        self.resize(400, 200)
        layout = QVBoxLayout(self)

        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        table = QTableWidget(self)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Cell #", "Voltage (V)", "Temp (℃)"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setRowCount(len(cell_voltages))

        for i in range(len(cell_voltages)):
            table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            table.setItem(i, 1, QTableWidgetItem(f"{cell_voltages[i]:.4f}"))
            table.setItem(i, 2, QTableWidgetItem(f"{cell_temps[i]:.2f}"))
        layout.addWidget(table)

# ---------------------------
# 메인 GUI
# ---------------------------
class ModbusGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modbus RTU GUI with Alarms + Battery")
        self.resize(1400, 900)
        self.client = None

        # 타이머
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
        main_layout.addLayout(left_v, stretch=2)

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

        # 로그창
        center_layout = QVBoxLayout()
        left_v.addLayout(center_layout, stretch=3)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(140)
        center_layout.addWidget(self.log)

        # ---------------------------
        # 배터리 이미지 프레임
        # ---------------------------
        image_path = os.path.join(os.path.dirname(__file__), "배터리시스템.png")
        if not os.path.exists(image_path):
            QMessageBox.warning(None, "이미지 오류", f"이미지를 찾을 수 없습니다:\n{image_path}")
            pixmap = QPixmap(300, 800)
            pixmap.fill(Qt.lightGray)
        else:
            pixmap = QPixmap(image_path)
            pixmap = pixmap.scaled(pixmap.width(), pixmap.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.batt_frame = QFrame(self)
        self.batt_frame.setFixedSize(pixmap.width(), pixmap.height())
        center_layout.addWidget(self.batt_frame, alignment=Qt.AlignLeft)

        self.label_batt = QLabel(self.batt_frame)
        self.label_batt.setPixmap(pixmap)
        self.label_batt.setScaledContents(True)
        self.label_batt.setGeometry(0, 0, pixmap.width(), pixmap.height())
        self.label_batt.show()

        # 오버레이 버튼
        self.overlay_buttons = []
        self.add_battery_overlay_buttons()

        # ---------------------------
        # 모듈 테이블
        # ---------------------------
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout, stretch=1)
        right_layout.addWidget(QLabel("🔍 Modules Overview"))
        self.module_table = QTableWidget()
        self.module_table.setColumnCount(5)
        self.module_table.setHorizontalHeaderLabels(
            ["Module", "Cell Voltages (V)", "Cell Temps (℃)", "Module Voltage (V)", "Module Temp (℃)"])
        self.module_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.module_table.setRowCount(MODULE_COUNT)
        for i in range(MODULE_COUNT):
            self.module_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
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
        self.populate_ports()
        self.update_buttons(False)
        self.update_module_table()

    # ---------------------------
    # 오버레이 버튼
    # ---------------------------
    def add_battery_overlay_buttons(self):
        label_w = self.batt_frame.width()
        label_h = self.batt_frame.height()
        total_sections = MODULE_COUNT + 1
        section_height = max(20, label_h // total_sections)

        font_css = (
            "color: black;"
            "font-weight: bold;"
            "font-size: 14px;"
            "background-color: rgba(255, 255, 255, 150);"
            "border-radius: 5px;"
            "padding-left: 6px;"
        )

        for i in range(total_sections):
            y = label_h - (i + 1) * section_height
            btn = QPushButton(self.batt_frame)
            btn.setGeometry(0, y, label_w, section_height)
            btn.setStyleSheet("background-color: rgba(255, 223, 0, 80); border: 1px solid black;")

            if i < MODULE_COUNT:
                module_num = i + 1
                btn.setToolTip(f"{module_num}번 모듈")
                btn.clicked.connect(partial(self.on_overlay_clicked, module_num))

                label = QLabel(f"{module_num}번 모듈", self.batt_frame)
                label.setGeometry(10, y, 120, section_height)
                label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                label.setStyleSheet(font_css)
                label.show()
            else:
                btn.setToolTip("감시제어장치 (SMU02C)")
                btn.clicked.connect(partial(self.on_overlay_clicked, MODULE_COUNT + 1))

                label = QLabel("감시제어장치", self.batt_frame)
                label.setGeometry(10, y, 140, section_height)
                label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                label.setStyleSheet(font_css)
                label.show()

            btn.raise_()  # 버튼을 레이블 위로
            btn.show()
            self.overlay_buttons.append(btn)

    def on_overlay_clicked(self, module_num):
        """모듈 클릭 시 팝업창 표시"""
        voltage = round(52.0 + (module_num * 0.1), 2)
        current = round(10.0 + (module_num * 0.05), 2)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"{module_num}번 모듈 정보")
        dialog.setFixedSize(250, 180)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl_title = QLabel(f"🔋 {module_num}번 모듈 상태")
        lbl_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #003366;")
        lbl_voltage = QLabel(f"전압: {voltage:.2f} V")
        lbl_voltage.setStyleSheet("font-size: 14px; color: black;")
        lbl_current = QLabel(f"전류: {current:.2f} A")
        lbl_current.setStyleSheet("font-size: 14px; color: black;")

        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet("padding: 5px 15px; font-weight: bold;")
        btn_close.clicked.connect(dialog.close)

        layout.addWidget(lbl_title)
        layout.addSpacing(8)
        layout.addWidget(lbl_voltage)
        layout.addWidget(lbl_current)
        layout.addStretch()
        layout.addWidget(btn_close, alignment=Qt.AlignRight)
        dialog.setLayout(layout)
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
    # Modbus 연결/해제
    # ---------------------------
    def connect_modbus(self):
        port = self.combo_port.currentText()
        if not port:
            QMessageBox.warning(self, "Connection Error", "❌ COM 포트를 선택하세요.")
            return
        baud = int(self.combo_baud.currentText())
        try:
            self.client = ModbusSerialClient(
                port=port,
                baudrate=baud,
                stopbits=1,
                bytesize=8,
                parity='N',
                timeout=1
            )
            if self.client.connect():
                self.log_message(f"✅ Connected to {port} @ {baud}bps")
                self.update_buttons(True)
            else:
                self.log_message(f"❌ Failed to connect to {port}")
                QMessageBox.critical(self, "Connection Failed", f"❌ {port} 연결 실패\n원인: 장치 응답 없음")
        except Exception as e:
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
            self.log_message(f"TX: Read 0x{address:04X} Count={count} Slave={slave}")
            if rr is None or (hasattr(rr, "isError") and rr.isError()):
                self.log_message(f"❌ Read error at 0x{address:04X}")
                return None
            val = rr.registers[0] if hasattr(rr, "registers") and rr.registers else None
            if val is None:
                return None
            if signed and val > 0x7FFF:
                val -= 0x10000
            return val * scale
        except Exception as e:
            self.log_message(f"❌ Exception reading register 0x{address:04X}: {e}")
            return None

    # ---------------------------
    # 모듈 테이블 업데이트
    # ---------------------------
    def update_module_table(self):
        for i in range(MODULE_COUNT):
            voltages = [round(3.7 + j * 0.01, 4) for j in range(CELLS_PER_MODULE)]
            temps = [round(25 + j * 0.2, 2) for j in range(CELLS_PER_MODULE)]
            mod_voltage = sum(voltages)
            mod_temp = max(temps)
            self.module_table.setItem(i, 1, QTableWidgetItem(str(voltages)))
            self.module_table.setItem(i, 2, QTableWidgetItem(str(temps)))
            self.module_table.setItem(i, 3, QTableWidgetItem(f"{mod_voltage:.2f}"))
            self.module_table.setItem(i, 4, QTableWidgetItem(f"{mod_temp:.2f}"))

    # ---------------------------
    # 알람
    # ---------------------------
    def read_alarms(self):
        for name, reg in ALARM_REGISTERS.items():
            val = self.read_register(reg)
            if val:
                self.log_message(f"⚠ {name}: {val}")

    def toggle_alarm_monitor(self, checked):
        if checked:
            self.alarm_timer.start()
            self.btn_monitor.setText("Stop Alarm Monitor")
            self.log_message("🔔 Alarm monitoring started")
        else:
            self.alarm_timer.stop()
            self.btn_monitor.setText("Start Alarm Monitor")
            self.log_message("🔕 Alarm monitoring stopped")

    def change_poll_interval(self, value):
        self.module_poll_timer.setInterval(value * 1000)
        self.log_message(f"⏱ Poll interval changed to {value}s")


# ---------------------------
# 실행
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ModbusGUI()
    gui.show()
    sys.exit(app.exec())
