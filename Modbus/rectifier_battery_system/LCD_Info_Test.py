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
# Modbus Master (Raw frame)
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

    def send_raw(self, frame: bytes) -> bytes:
        # pymodbus 3.x 내부 socket 사용
        self.client.socket.write(frame)
        return self.client.socket.read(256)


# ============================
# GUI
# ============================
class TimeBatteryGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modbus Time & Battery Monitor")
        self.resize(900, 700)

        self.master = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_all)

        self.build_ui()

    # ---------- UI ----------
    def build_ui(self):
        layout = QVBoxLayout(self)

        # Top: COM control
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

        # TX/RX Frame view
        self.text_frame = QTextEdit()
        self.text_frame.setReadOnly(True)

        # Time view
        self.lbl_time = QLabel("Time : -")
        self.lbl_time.setStyleSheet("font-size:18px; font-weight:bold;")

        # Battery selector
        sel = QHBoxLayout()
        self.cmb_n = QComboBox()
        for i in range(1, 33):
            self.cmb_n.addItem(str(i))
        sel.addWidget(QLabel("Battery Module N"))
        sel.addWidget(self.cmb_n)
        sel.addStretch()

        # Battery info area
        self.text_battery = QTextEdit()
        self.text_battery.setReadOnly(True)
        self.text_battery.setMinimumHeight(200)
        
        self.text_cell = QTextEdit()
        self.text_cell.setReadOnly(True)
        self.text_cell.setMinimumHeight(200)

        layout.addLayout(top)
        layout.addWidget(QLabel("TX / RX Frame"))
        layout.addWidget(self.text_frame)
        layout.addWidget(QLabel("Read Time (0x2000, 6 regs)"))
        layout.addWidget(self.lbl_time)
        layout.addLayout(sel)
        
        layout.addWidget(QLabel("Battery Information"))
        layout.addWidget(self.text_battery)
        
        layout.addWidget(QLabel("Cell Information"))
        layout.addWidget(self.text_cell)

    # ---------- Serial ----------
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

    # ---------- Polling ----------
    def poll_all(self):
        if not self.master:
            return

        # 1) Time polling
        self.poll_time()

        # 2) Battery polling (선택된 N)
        try:
            n = int(self.cmb_n.currentText())
        except:
            n = 1
        self.poll_battery(n)

    # ---------- Time ----------
    def poll_time(self):
        slave = 1
        function = 0x03
        start_addr = 0x2000
        count = 6

        frame = struct.pack(">B B H H", slave, function, start_addr, count)
        crc = count_crc(frame)
        frame += struct.pack("<H", crc)

        self.log_frame("TX", frame)
        rx = self.master.send_raw(frame)
        if not rx:
            return
        self.log_frame("RX", rx)

        # 응답 파싱: [slave][func][bytecount][data...][crc]
        if len(rx) >= 3 + 6 * 2 + 2:
            data = rx[3:3 + 12]
            regs = struct.unpack(">6H", data)
            year, month, day, hour, minute, second = regs
            self.lbl_time.setText(
                f"Time : {year:04d}-{month:02d}-{day:02d} "
                f"{hour:02d}:{minute:02d}:{second:02d}"
            )

    # ---------- Battery ----------
    def poll_battery(self, n: int):
        """
        Battery Barcode        : 0xC670 ~ 0xC67E + (N-1)*32, STRING, 30 bytes (15 regs)
        Battery Temperature    : 0xA706, INT16
        Battery Voltage (N)    : 0xA731~0xA732 + (N-1)*64, UINT32, /10
        Battery Current (N)    : 0xA733~0xA734 + (N-1)*64, INT32, /10
        Battery SOC (N)        : 0xA739 + (N-1)*64, UINT16
        """
        self.text_battery.clear()
        self.text_cell.clear()
        
        # ---- Temperature (global) ----
        temp = self.read_int16(0xA706)
        self.text_battery.append(f"Battery Temperature : {temp} degC")
        
        
        self.text_battery.append(f"[Battery Module N = {n}]")

        # ---- Barcode (STRING 30 bytes = 15 regs) ----
        barcode_base = 0xC670 + (n - 1) * 32
        barcode = self.read_string(barcode_base, 15)
        self.text_battery.append(f"Battery Barcode : {barcode}")        

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
        
        for i in range(1, 16):
            addr = 0xA739 + i + (n - 1) * 64
            t = self.read_int16(addr)            
            self.text_cell.append(f"Cell-{i} Temperature : {t} degC")
            
            addr = 0xA74F + i + (n - 1) * 64
            v = self.read_uint16(addr) / 10
            self.text_cell.append(f"Cell-{i} Voltage : {v:.3f} V")
        
            
    # ---------- Raw helpers ----------
    def build_read_frame(self, start_addr, count):
        slave = 33
        function = 0x03
        frame = struct.pack(">B B H H", slave, function, start_addr, count)
        crc = count_crc(frame)
        return frame + struct.pack("<H", crc)

    def send_and_recv(self, frame: bytes):
        self.log_frame("TX", frame)
        rx = self.master.send_raw(frame)
        if rx:
            self.log_frame("RX", rx)
        return rx

    # ---------- Parse helpers ----------
    def read_uint16(self, addr):
        frame = self.build_read_frame(addr, 1)
        rx = self.send_and_recv(frame)
        if not rx or len(rx) < 3 + 2 + 2:
            return 0
        data = rx[3:5]
        return struct.unpack(">H", data)[0]

    def read_int16(self, addr):
        u = self.read_uint16(addr)
        return struct.unpack(">h", struct.pack(">H", u))[0]

    def read_uint32(self, addr):
        frame = self.build_read_frame(addr, 2)
        rx = self.send_and_recv(frame)
        if not rx or len(rx) < 3 + 4 + 2:
            return 0
        data = rx[3:7]
        hi, lo = struct.unpack(">2H", data)
        return (hi << 16) | lo

    def read_int32(self, addr):
        u32 = self.read_uint32(addr)
        return struct.unpack(">i", struct.pack(">I", u32))[0]

    def read_string(self, addr, reg_count):
        frame = self.build_read_frame(addr, reg_count)
        rx = self.send_and_recv(frame)
        if not rx or len(rx) < 3 + reg_count * 2 + 2:
            return ""
        data = rx[3:3 + reg_count * 2]
        # big-endian words -> bytes
        raw = bytearray()
        for i in range(0, len(data), 2):
            raw.append(data[i])
            raw.append(data[i + 1])
        try:
            s = raw.rstrip(b"\x00").decode("ascii", errors="ignore")
        except:
            s = ""
        return s

    # ---------- Frame log ----------
    def log_frame(self, title, data: bytes):
        hexstr = " ".join(f"{b:02X}" for b in data)
        self.text_frame.append(f"[{title}] {hexstr}")


# ============================
# Main
# ============================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TimeBatteryGui()
    win.show()
    sys.exit(app.exec())
