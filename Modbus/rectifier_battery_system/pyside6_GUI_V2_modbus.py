import sys
import serial.tools.list_ports
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QGridLayout
)
from PySide6.QtCore import Qt, QTimer
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

# Modbus 레지스터 주소
REG_SYSTEM_DC_VOLTAGE   = 0x1000
REG_TOTAL_DC_LOAD_CURR  = 0x1001
REG_AC_FREQ             = 0x100C
REG_BATT_STATUS         = 0x1400
REG_TOTAL_BATT_CURRENT  = 0x1401
REG_BATT_SOC            = 0xA739

class ModbusGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modbus RTU GUI")
        self.resize(700, 500)
        self.client = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        # COM / Baudrate 선택
        port_layout = QHBoxLayout()
        layout.addLayout(port_layout)
        port_layout.addWidget(QLabel("COM Port:"))
        self.combo_port = QComboBox()
        port_layout.addWidget(self.combo_port)
        port_layout.addWidget(QLabel("Baudrate:"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        port_layout.addWidget(self.combo_baud)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_modbus)
        port_layout.addWidget(self.btn_connect)

        # 개별 읽기 버튼
        grid = QGridLayout()
        layout.addLayout(grid)
        self.btn_vdc = QPushButton("Read DC Voltage")
        self.btn_vdc.clicked.connect(lambda: self.read_single(REG_SYSTEM_DC_VOLTAGE, self.btn_vdc, "System DC Voltage", scale=0.1))
        grid.addWidget(self.btn_vdc, 0, 0)
        self.btn_iload = QPushButton("Read DC Load Current")
        self.btn_iload.clicked.connect(lambda: self.read_single(REG_TOTAL_DC_LOAD_CURR, self.btn_iload, "Total DC Load Current", scale=0.1))
        grid.addWidget(self.btn_iload, 0, 1)
        self.btn_acf = QPushButton("Read AC Frequency")
        self.btn_acf.clicked.connect(lambda: self.read_single(REG_AC_FREQ, self.btn_acf, "AC Frequency"))
        grid.addWidget(self.btn_acf, 1, 0)
        self.btn_batt_status = QPushButton("Read Battery Status")
        self.btn_batt_status.clicked.connect(lambda: self.read_battery_status(self.btn_batt_status))
        grid.addWidget(self.btn_batt_status, 1, 1)
        self.btn_ibatt = QPushButton("Read Battery Current")
        self.btn_ibatt.clicked.connect(lambda: self.read_single(REG_TOTAL_BATT_CURRENT, self.btn_ibatt, "Total Battery Current", signed=True, scale=0.1))
        grid.addWidget(self.btn_ibatt, 2, 0)
        self.btn_soc = QPushButton("Read SOC")
        self.btn_soc.clicked.connect(lambda: self.read_single(REG_BATT_SOC, self.btn_soc, "Battery SOC"))
        grid.addWidget(self.btn_soc, 2, 1)

        # 전체 읽기 버튼
        self.btn_all = QPushButton("Read All Info")
        self.btn_all.clicked.connect(self.read_all)
        layout.addWidget(self.btn_all)

        # TX/RX 로그
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.populate_ports()
        self.update_buttons(False)

    def populate_ports(self):
        ports = serial.tools.list_ports.comports()
        self.combo_port.clear()
        for p in ports:
            self.combo_port.addItem(p.device)

    def log_message(self, msg):
        self.log.append(msg)

    def update_buttons(self, enabled):
        self.btn_vdc.setEnabled(enabled)
        self.btn_iload.setEnabled(enabled)
        self.btn_acf.setEnabled(enabled)
        self.btn_batt_status.setEnabled(enabled)
        self.btn_ibatt.setEnabled(enabled)
        self.btn_soc.setEnabled(enabled)
        self.btn_all.setEnabled(enabled)

    def connect_modbus(self):
        port = self.combo_port.currentText()
        baud = int(self.combo_baud.currentText())
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
            self.btn_connect.setEnabled(False)
        else:
            self.log_message(f"❌ Failed to connect to {port}")

    def read_register(self, address, count=1, slave=1, signed=False, scale=1):
        if not self.client:
            self.log_message("❌ Not connected")
            return None
        try:
            rr = self.client.read_holding_registers(address=address, count=count, device_id=slave)
            self.log_message(f"TX: Read 0x{address:04X} Count={count} Slave={slave}")
            if rr.isError():
                self.log_message(f"❌ Read error at 0x{address:04X}")
                return None
            val = rr.registers[0]
            self.log_message(f"RX: 0x{val:04X}")
            if signed and val > 0x7FFF:
                val -= 0x10000
            return val * scale
        except Exception as e:
            self.log_message(f"❌ Modbus Exception: {e}")
            return None

    # 단일 항목 읽기 (버튼 색상 녹색 처리)
    def read_single(self, address, button, name, signed=False, scale=1):
        original_color = button.palette().color(button.backgroundRole()).name()
        button.setStyleSheet("background-color: lightgreen")
        QApplication.processEvents()  # UI 즉시 업데이트

        val = self.read_register(address, signed=signed, scale=scale)
        if val is not None:
            self.log_message(f"{name}: {val}")

        # 완료 후 원래 색으로 복귀
        button.setStyleSheet("")

    # 배터리 상태 읽기
    def read_battery_status(self, button):
        original_color = button.palette().color(button.backgroundRole()).name()
        button.setStyleSheet("background-color: lightgreen")
        QApplication.processEvents()

        val = self.read_register(REG_BATT_STATUS)
        status_map = {0: "Float Charging", 1: "Equalized Charging", 2: "Discharging", 3: "Hibernation"}
        if val is not None:
            self.log_message(f"Battery Status: {status_map.get(val, 'Unknown')}")

        button.setStyleSheet("")

    # 전체 읽기
    def read_all(self):
        # 전체 버튼들을 순차적으로 눌린 것처럼 처리
        buttons = [
            (self.btn_vdc, REG_SYSTEM_DC_VOLTAGE, "System DC Voltage", False, 0.1),
            (self.btn_iload, REG_TOTAL_DC_LOAD_CURR, "Total DC Load Current", False, 0.1),
            (self.btn_acf, REG_AC_FREQ, "AC Frequency", False, 1),
            (self.btn_batt_status, REG_BATT_STATUS, "Battery Status", False, 1),
            (self.btn_ibatt, REG_TOTAL_BATT_CURRENT, "Total Battery Current", True, 0.1),
            (self.btn_soc, REG_BATT_SOC, "Battery SOC", False, 1)
        ]
        for btn, addr, name, signed, scale in buttons:
            btn.setStyleSheet("background-color: lightgreen")
            QApplication.processEvents()
            if name == "Battery Status":
                self.read_battery_status(btn)
            else:
                self.read_single(addr, btn, name, signed, scale)
            btn.setStyleSheet("")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ModbusGUI()
    gui.show()
    sys.exit(app.exec())