import sys
import time
from pymodbus.client import ModbusSerialClient
from PySide6.QtWidgets import *
from PySide6.QtCore import *

# =========================
# Modbus Thread
# =========================
class ModbusThread(QThread):
    data_signal = Signal(dict)
    status_signal = Signal(bool)

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.running = True

        self.client = ModbusSerialClient(
            port=self.port,
            baudrate=9600,
            parity='N',
            stopbits=1,
            bytesize=8,
            timeout=1
        )

    def run(self):
        if not self.client.connect():
            self.status_signal.emit(False)
            return

        self.status_signal.emit(True)

        while self.running:
            try:
                data = self.read_all()
                self.data_signal.emit(data)
            except Exception as e:
                print("Error:", e)

            time.sleep(1)

        self.client.close()

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

    def read_all(self):
        result = {}

        for n in range(1, 11):  # 10개만 사용
            module = self.read_module(n)
            if module:
                result[n] = module

        return result

    def read_module(self, n):
        base = (n - 1) * 64
        start = int("0xA731", 16) + base

        rr = self.client.read_holding_registers(
            address=start,
            count=80
        )

        if rr.isError():
            return None

        regs = rr.registers

        def u16(i):
            return regs[i]

        def s16(i):
            v = regs[i]
            return v - 65536 if v > 32767 else v

        def u32(i):
            return (regs[i] << 16) | regs[i + 1]

        def s32(i):
            v = (regs[i] << 16) | regs[i + 1]
            return v - 0x100000000 if v > 0x7FFFFFFF else v

        data = {}

        data["volt"] = u32(0) / 10
        data["current"] = s32(2) / 10
        data["soc"] = u16(8)
        data["soh"] = u16(0xA766 - 0xA731)

        # 온도 23개
        temps = []
        for i in range(23):
            offset = (0xA73A + i) - 0xA731
            temps.append(s16(offset))
        data["temps"] = temps

        # 셀 전압 23개
        cells = []
        for i in range(23):
            offset = (0xA750 + i) - 0xA731
            cells.append(u16(offset) / 10)
        data["cells"] = cells

        return data


# =========================
# Main UI
# =========================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Battery Monitoring (Modbus RTU)")
        self.resize(900, 600)

        self.thread = None
        self.module_data = {}

        self.init_ui()

    def init_ui(self):
        main = QWidget()
        layout = QVBoxLayout(main)

        # ===== 연결 패널 =====
        conn_layout = QHBoxLayout()

        conn_layout.addWidget(QLabel("COM Port"))

        self.com_combo = QComboBox()
        self.com_combo.addItems(self.get_ports())
        conn_layout.addWidget(self.com_combo)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_device)
        conn_layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self.disconnect_device)
        conn_layout.addWidget(self.btn_disconnect)

        layout.addLayout(conn_layout)

        # ===== 테이블 =====
        self.table = QTableWidget(10, 5)
        self.table.setHorizontalHeaderLabels(
            ["Module", "Voltage(V)", "Current(A)", "SOC(%)", "SOH(%)"]
        )
        layout.addWidget(self.table)

        self.setCentralWidget(main)

    def get_ports(self):
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    # =========================
    # 연결
    # =========================
    def connect_device(self):
        port = self.com_combo.currentText()

        self.thread = ModbusThread(port)
        self.thread.data_signal.connect(self.update_data)
        self.thread.start()

    def disconnect_device(self):
        if self.thread:
            self.thread.stop()
            self.thread = None

    # =========================
    # 데이터 업데이트
    # =========================
    def update_data(self, data):
        for row, (mod, val) in enumerate(data.items()):
            self.table.setItem(row, 0, QTableWidgetItem(str(mod)))
            self.table.setItem(row, 1, QTableWidgetItem(f"{val['volt']:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{val['current']:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(str(val['soc'])))
            self.table.setItem(row, 4, QTableWidgetItem(str(val['soh'])))


# =========================
# 실행
# =========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())