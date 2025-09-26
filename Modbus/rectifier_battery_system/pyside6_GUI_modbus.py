import sys
import serial.tools.list_ports
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit
)
from PySide6.QtCore import QTimer
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
        self.resize(600, 400)

        self.client = None

        # 레이아웃
        layout = QVBoxLayout()
        self.setLayout(layout)

        # COM 포트 / Baudrate 선택
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

        # Read 버튼
        self.btn_read = QPushButton("Read Battery Info")
        self.btn_read.clicked.connect(self.read_battery_info)
        self.btn_read.setEnabled(False)
        layout.addWidget(self.btn_read)

        # TX/RX 로그 창
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.populate_ports()

    def populate_ports(self):
        ports = serial.tools.list_ports.comports()
        self.combo_port.clear()
        for p in ports:
            self.combo_port.addItem(p.device)

    def log_message(self, msg):
        self.log.append(msg)

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
            self.btn_read.setEnabled(True)
            self.btn_connect.setEnabled(False)
        else:
            self.log_message(f"❌ Failed to connect to {port}")

    def read_register(self, address, count=1, slave=1, signed=False):
        if not self.client:
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
            return val
        except ModbusException as e:
            self.log_message(f"❌ Modbus Exception: {e}")
            return None

    def read_battery_info(self):
        if not self.client:
            self.log_message("❌ Not connected")
            return

        vdc = self.read_register(REG_SYSTEM_DC_VOLTAGE)
        iload = self.read_register(REG_TOTAL_DC_LOAD_CURR)
        f_ac = self.read_register(REG_AC_FREQ)
        batt_status = self.read_register(REG_BATT_STATUS)
        ibatt = self.read_register(REG_TOTAL_BATT_CURRENT, signed=True)
        soc = self.read_register(REG_BATT_SOC)

        status_map = {0: "Float Charging", 1: "Equalized Charging", 2: "Discharging", 3: "Hibernation"}

        if vdc is not None:
            self.log_message(f"System DC Voltage : {vdc/10:.1f} V")
        if iload is not None:
            self.log_message(f"Total DC Load Current : {iload/10:.1f} A")
        if f_ac is not None:
            self.log_message(f"AC Frequency : {f_ac} Hz")
        if batt_status is not None:
            self.log_message(f"Battery Status : {status_map.get(batt_status, 'Unknown')}")
        if ibatt is not None:
            self.log_message(f"Total Battery Current : {ibatt/10:.1f} A")
        if soc is not None:
            self.log_message(f"Battery SOC : {soc} %")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ModbusGUI()
    gui.show()
    sys.exit(app.exec())