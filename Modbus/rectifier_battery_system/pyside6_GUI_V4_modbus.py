import sys
import serial.tools.list_ports
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QGridLayout, QSpinBox,
    QMessageBox
)
from PySide6.QtCore import Qt, QTimer
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

# ---------------------------
# 패턴 기반 레지스터 생성
# ---------------------------

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
# Modbus GUI
# ---------------------------

class ModbusGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modbus RTU GUI with Alarms")
        self.resize(900, 650)
        self.client = None
        self.monitor_timer = QTimer()
        self.monitor_timer.setInterval(5000)
        self.monitor_timer.timeout.connect(self.read_alarms)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Top: Port & Baud
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

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self.disconnect_modbus)
        self.btn_disconnect.setEnabled(False)
        port_layout.addWidget(self.btn_disconnect)

        port_layout.addStretch()
        port_layout.addWidget(QLabel("Monitor Interval (s):"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 60)
        self.spin_interval.setValue(5)
        self.spin_interval.valueChanged.connect(self.update_monitor_interval)
        port_layout.addWidget(self.spin_interval)

        # Middle: Read buttons
        grid = QGridLayout()
        layout.addLayout(grid)
        self.btn_vdc = QPushButton("Read DC Voltage")
        self.btn_vdc.clicked.connect(lambda: self.read_single(0x1000, self.btn_vdc, "System DC Voltage", scale=0.1))
        grid.addWidget(self.btn_vdc, 0, 0)
        self.btn_iload = QPushButton("Read DC Load Current")
        self.btn_iload.clicked.connect(lambda: self.read_single(0x1001, self.btn_iload, "Total DC Load Current", scale=0.1))
        grid.addWidget(self.btn_iload, 0, 1)
        self.btn_acf = QPushButton("Read AC Frequency")
        self.btn_acf.clicked.connect(lambda: self.read_single(0x100C, self.btn_acf, "AC Frequency"))
        grid.addWidget(self.btn_acf, 1, 0)
        self.btn_ibatt = QPushButton("Read Battery Current")
        self.btn_ibatt.clicked.connect(lambda: self.read_single(0x1401, self.btn_ibatt, "Total Battery Current", signed=True, scale=0.1))
        grid.addWidget(self.btn_ibatt, 1, 1)
        self.btn_soc = QPushButton("Read SOC")
        self.btn_soc.clicked.connect(lambda: self.read_single(0xA739, self.btn_soc, "Battery SOC"))
        grid.addWidget(self.btn_soc, 2, 0)

        # Alarm buttons
        alarm_layout = QHBoxLayout()
        layout.addLayout(alarm_layout)
        self.btn_read_alarms = QPushButton(f"Read Alarms ({len(ALARM_REGISTERS)})")
        self.btn_read_alarms.clicked.connect(self.read_alarms)
        alarm_layout.addWidget(self.btn_read_alarms)

        self.btn_monitor = QPushButton("Start Monitor")
        self.btn_monitor.setCheckable(True)
        self.btn_monitor.clicked.connect(self.toggle_monitor)
        alarm_layout.addWidget(self.btn_monitor)
        alarm_layout.addStretch()

        # Log
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
        self.btn_ibatt.setEnabled(enabled)
        self.btn_soc.setEnabled(enabled)
        self.btn_read_alarms.setEnabled(enabled)
        self.btn_monitor.setEnabled(enabled)

    # ---------------------------
    # Connect / Disconnect
    # ---------------------------

    def connect_modbus(self):
        port = self.combo_port.currentText()
        if not port:
            self.log_message("❌ No COM port selected")
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
                QMessageBox.information(self, "Connection Success", f"✅ {port} 연결 성공 ({baud}bps)")
                self.update_buttons(True)
                self.btn_connect.setEnabled(False)
                self.btn_disconnect.setEnabled(True)
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
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)

    # ---------------------------
    # Modbus Read
    # ---------------------------

    def read_register(self, address, count=1, slave=1, signed=False, scale=1):
        if not self.client:
            self.log_message("❌ Not connected")
            return None
        try:
            rr = self.client.read_holding_registers(address=address, count=count, device_id=slave)
            self.log_message(f"TX: Read 0x{address:04X} Count={count} Slave={slave}")
            if rr is None or (hasattr(rr, "isError") and rr.isError()):
                self.log_message(f"❌ Read error at 0x{address:04X}")
                return None
            val = rr.registers[0] if hasattr(rr, "registers") and rr.registers else None
            if val is None:
                self.log_message(f"❌ Empty value at 0x{address:04X}")
                return None
            self.log_message(f"RX: 0x{val:04X} ({val})")
            if signed and val > 0x7FFF:
                val -= 0x10000
            return val * scale
        except Exception as e:
            self.log_message(f"❌ Modbus Exception while reading 0x{address:04X}: {e}")
            return None

    def read_single(self, address, button, name, signed=False, scale=1):
        button.setStyleSheet("background-color: lightgreen")
        QApplication.processEvents()
        val = self.read_register(address, signed=signed, scale=scale)
        if val is not None:
            self.log_message(f"{name}: {val}")
        button.setStyleSheet("")

    # ---------------------------
    # Alarms
    # ---------------------------

    def read_alarms(self):
        if not self.client:
            self.log_message("❌ Not connected - cannot read alarms")
            return
        self.log_message("=== Reading Alarms ===")
        alarm_found = False
        items = sorted(ALARM_REGISTERS.items(), key=lambda kv: kv[1])
        for name, addr in items:
            val = self.read_register(addr)
            if val is None:
                continue
            if isinstance(val, (int, float)) and int(val) != 0:
                self.log_message(f"ALARM -> {name} @0x{addr:04X} : 0x{int(val):02X}")
                alarm_found = True
            else:
                self.log_message(f"Normal -> {name} @0x{addr:04X}")
        self.btn_read_alarms.setStyleSheet("background-color: salmon" if alarm_found else "lightgreen")
        self.log_message("=== Alarms Read Complete ===")

    # ---------------------------
    # Monitor
    # ---------------------------

    def toggle_monitor(self, checked):
        if checked:
            interval_s = self.spin_interval.value()
            self.monitor_timer.setInterval(interval_s * 1000)
            self.monitor_timer.start()
            self.btn_monitor.setText("Stop Monitor")
            self.log_message(f"🔁 Alarm monitor started (interval {interval_s}s)")
        else:
            self.monitor_timer.stop()
            self.btn_monitor.setText("Start Monitor")
            self.log_message("⏸ Alarm monitor stopped")

    def update_monitor_interval(self, val):
        if self.monitor_timer.isActive():
            self.monitor_timer.setInterval(val * 1000)
            self.log_message(f"Monitor interval updated to {val}s")

# ---------------------------
# 실행부
# ---------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ModbusGUI()
    gui.show()
    sys.exit(app.exec())