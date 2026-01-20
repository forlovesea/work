import sys
import struct
import serial
import serial.tools.list_ports
from PySide6.QtWidgets import *
from PySide6.QtCore import QTimer
from pymodbus.client.serial import ModbusSerialClient


# ============================
# CRC (C 코드 그대로 포팅)
# ============================
def count_crc(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


# ============================
# Modbus Master
# ============================
class ModbusMaster:
    def __init__(self, port, baudrate=9600, slave_id=33):
        self.slave_id = slave_id
        self.client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            stopbits=1,
            bytesize=8,
            parity='N',
            timeout=1
        )

    def connect(self):
        return self.client.connect()

    def close(self):
        self.client.close()

    # Raw frame 송신
    def send_raw(self, frame: bytes) -> bytes:
        self.client.socket.write(frame)
        return self.client.socket.read(256)


# ============================
# GUI
# ============================
class TimeGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modbus Time Polling")
        self.resize(800, 600)

        self.master = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_time)

        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)

        # ----------- Top -----------
        top = QHBoxLayout()

        self.cmb_port = QComboBox()
        self.refresh_ports()

        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")

        self.btn_connect.clicked.connect(self.connect_port)
        self.btn_disconnect.clicked.connect(self.disconnect_port)

        top.addWidget(QLabel("COM Port"))
        top.addWidget(self.cmb_port)
        top.addWidget(self.btn_connect)
        top.addWidget(self.btn_disconnect)

        # ----------- Frame View -----------
        self.text_frame = QTextEdit()
        self.text_frame.setReadOnly(True)

        # ----------- Time View -----------
        self.lbl_time = QLabel("Time : -")
        self.lbl_time.setStyleSheet("font-size:18px; font-weight:bold;")

        layout.addLayout(top)
        layout.addWidget(QLabel("TX / RX Frame"))
        layout.addWidget(self.text_frame)
        layout.addWidget(QLabel("Read Time"))
        layout.addWidget(self.lbl_time)

    # ============================
    # Serial
    # ============================
    def refresh_ports(self):
        self.cmb_port.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.cmb_port.addItem(p.device)

    def connect_port(self):
        port = self.cmb_port.currentText()
        self.master = ModbusMaster(port)

        if self.master.connect():
            QMessageBox.information(self, "Connect", f"Connected to {port}")
            self.timer.start(1000)  # 1초 polling
        else:
            QMessageBox.critical(self, "Connect", "Connection Failed")

    def disconnect_port(self):
        if self.master:
            self.timer.stop()
            self.master.close()
            self.master = None
            QMessageBox.information(self, "Disconnect", "Disconnected")

    # ============================
    # Polling
    # ============================
    def poll_time(self):
        if not self.master:
            return

        # Build Modbus RTU Frame
        slave = 33
        function = 0x03
        start_addr = 0x2000
        count = 6

        frame = struct.pack(">B B H H", slave, function, start_addr, count)
        crc = count_crc(frame)
        frame += struct.pack("<H", crc)

        # TX 표시
        self.log_frame("TX", frame)

        # RX 수신
        rx = self.master.send_raw(frame)
        if not rx:
            return

        self.log_frame("RX", rx)

        # 응답 파싱
        if len(rx) >= 3 + 6 * 2:
            data = rx[3:-2]
            regs = struct.unpack(">6H", data)

            year, month, day, hour, minute, second = regs
            self.lbl_time.setText(
                f"Time : {year:04d}-{month:02d}-{day:02d} "
                f"{hour:02d}:{minute:02d}:{second:02d}"
            )

    def poll_battery(self, n: int):
        """
        Battery Barcode        : 0xC670 ~ 0xC67E + (N-1)*32, STRING, 30 bytes (15 regs)
        Battery Temperature    : 0xA706, INT16
        Battery Voltage (N)    : 0xA731~0xA732 + (N-1)*64, UINT32, /10
        Battery Current (N)    : 0xA733~0xA734 + (N-1)*64, INT32, /10
        Battery SOC (N)        : 0xA739 + (N-1)*64, UINT16
        """
        self.text_battery.clear()
        self.text_battery.append(f"[Battery Module N = {n}]")

        # ---- Barcode (STRING 30 bytes = 15 regs) ----
        barcode_base = 0xC670 + (n - 1) * 32
        barcode = self.read_string(barcode_base, 15)
        self.text_battery.append(f"Battery Barcode : {barcode}")

        # ---- Temperature (global) ----
        temp = self.read_int16(0xA706)
        self.text_battery.append(f"Battery Temperature : {temp} degC")

        # ---- Voltage (N) UINT32 /10 ----
        v_base = 0xA731 + (n - 1) * 64
        voltage_raw = self.read_uint32(v_base)
        voltage = voltage_raw / 10.0
        self.text_battery.append(f"Battery Voltage : {voltage:.1f} V")

        # ---- Current (N) INT32 /10 ----
        c_base = 0xA733 + (n - 1) * 64
        current_raw = self.read_int32(c_base)
        current = current_raw / 10.0
        self.text_battery.append(f"Battery Current : {current:.1f} A")

        # ---- SOC (N) UINT16 ----
        soc_base = 0xA739 + (n - 1) * 64
        soc = self.read_uint16(soc_base)
        self.text_battery.append(f"Battery SOC : {soc} %")
        
    # ============================
    def log_frame(self, title, data: bytes):
        hexstr = " ".join(f"{b:02X}" for b in data)
        self.text_frame.append(f"[{title}] {hexstr}")


# ============================
# Main
# ============================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TimeGui()
    win.show()
    sys.exit(app.exec())
