import sys
import time
import struct
import serial
from PySide6.QtWidgets import *
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt

# ============================
# CRC (C 코드 그대로 포팅)
# ============================
def count_crc(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


# ============================
# Modbus RTU Frame 생성
# ============================
def build_modbus_frame(slave_id, function, start_addr, count):
    frame = bytearray()
    frame.append(slave_id)
    frame.append(function)
    frame.append((start_addr >> 8) & 0xFF)
    frame.append(start_addr & 0xFF)
    frame.append((count >> 8) & 0xFF)
    frame.append(count & 0xFF)

    crc = count_crc(frame)
    frame.append(crc & 0xFF)        # CRC Low
    frame.append((crc >> 8) & 0xFF) # CRC High
    return frame


# ============================
# Main GUI
# ============================
class BMSMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BMS System Monitor")
        self.resize(800, 600)

        # Serial config
        self.port = "COM33"
        self.baudrate = 9600
        self.slave_id = 0x21

        self.ser = None

        # Pages
        self.stack = QStackedWidget()

        self.page_status = self.create_status_page()
        self.page_alarms = QLabel("Alarms Page")
        self.page_info = QLabel("Running Info Page")
        self.page_settings = QLabel("Settings Page")
        self.page_ctrl = QLabel("Running Control Page")

        self.page_alarms.setAlignment(Qt.AlignCenter)
        self.page_info.setAlignment(Qt.AlignCenter)
        self.page_settings.setAlignment(Qt.AlignCenter)
        self.page_ctrl.setAlignment(Qt.AlignCenter)

        self.stack.addWidget(self.page_status)
        self.stack.addWidget(self.page_alarms)
        self.stack.addWidget(self.page_info)
        self.stack.addWidget(self.page_settings)
        self.stack.addWidget(self.page_ctrl)

        # Bottom buttons
        self.btn_alarms = QPushButton("Alarms")
        self.btn_info = QPushButton("Runn.Info")
        self.btn_settings = QPushButton("Settings")
        self.btn_ctrl = QPushButton("Runn.Ctrl")

        self.btn_alarms.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_info.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.btn_settings.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        self.btn_ctrl.clicked.connect(lambda: self.stack.setCurrentIndex(4))

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_alarms)
        btn_layout.addWidget(self.btn_info)
        btn_layout.addWidget(self.btn_settings)
        btn_layout.addWidget(self.btn_ctrl)

        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(self.stack)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # Timer polling
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_status)

        self.connect_serial()

    # ============================
    # Status Page UI
    # ============================
    def create_status_page(self):
        page = QWidget()
        layout = QFormLayout()

        self.lbl_temp = QLabel("-- °C")
        self.lbl_voltage = QLabel("-- V")
        self.lbl_current = QLabel("-- A")
        self.lbl_soc = QLabel("-- %")

        layout.addRow("Battery Temperature:", self.lbl_temp)
        layout.addRow("Battery Voltage:", self.lbl_voltage)
        layout.addRow("Battery Current:", self.lbl_current)
        layout.addRow("SOC:", self.lbl_soc)

        page.setLayout(layout)
        return page

    # ============================
    # Serial Connect
    # ============================
    def connect_serial(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=1
            )
            time.sleep(1)
            self.timer.start(1000)
        except Exception as e:
            QMessageBox.critical(self, "Serial Error", str(e))

    # ============================
    # Raw Modbus Read
    # ============================
    def read_registers(self, start_addr, count):
        frame = build_modbus_frame(self.slave_id, 0x03, start_addr, count)
        self.ser.write(frame)
        time.sleep(0.1)
        rx = self.ser.read(100)
        return rx

    # ============================
    # Polling
    # ============================
    def poll_status(self):
        try:
            # Battery Temperature (INT16)
            rx = self.read_registers(0xA706, 1)
            if len(rx) >= 7:
                temp = struct.unpack(">h", rx[3:5])[0]
                self.lbl_temp.setText(f"{temp} °C")

            # Battery Voltage (UINT32, precision 1)
            rx = self.read_registers(0xA731, 2)
            if len(rx) >= 9:
                raw = struct.unpack(">I", rx[3:7])[0]
                self.lbl_voltage.setText(f"{raw/10:.1f} V")

            # Battery Current (INT32, precision 1)
            rx = self.read_registers(0xA733, 2)
            if len(rx) >= 9:
                raw = struct.unpack(">i", rx[3:7])[0]
                self.lbl_current.setText(f"{raw/10:.1f} A")

            # SOC (UINT16)
            rx = self.read_registers(0xA739, 1)
            if len(rx) >= 7:
                soc = struct.unpack(">H", rx[3:5])[0]
                self.lbl_soc.setText(f"{soc} %")

        except Exception as e:
            print("Polling error:", e)


# ============================
# Main
# ============================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BMSMonitor()
    window.show()
    sys.exit(app.exec())
