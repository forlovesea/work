import sys
import serial.tools.list_ports
import asyncio
from datetime import datetime

from PySide6.QtWidgets import *
from PySide6.QtCore import *

from pymodbus.server import StartSerialServer
from pymodbus.datastore import ModbusServerContext, ModbusSequentialDataBlock
from pymodbus.pdu.device import ModbusDeviceIdentification


# ========================================================
# Modbus RTU Slave 서버 스레드
# ========================================================
class ModbusServerThread(QThread):
    log_signal = Signal(str)

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.context = None

    async def start_modbus(self):
        # -------------------------------------------------
        # 1) 데이터 블록 생성 (Holding Register, 40000개)
        # -------------------------------------------------
        block = ModbusSequentialDataBlock(0, [0] * 40000)

        # 기본 정보
        block.setValues(0x0000, [100, 1, 1, 10, 10])

        # 배터리 정보
        block.setValues(0xA702, [0x0000, 0xC350])
        block.setValues(0xA704, [0xFF38, 0x0000])
        block.setValues(0xA706, [250])

        # 시간 초기값
        block.setValues(0x2000, [2025, 1, 1, 0, 0, 0])

        # -------------------------------------------------
        # 2) Context 생성 (3.11.x 방식)
        # -------------------------------------------------
        self.context = ModbusServerContext(
            slave=block,
            single=True
        )

        # -------------------------------------------------
        # 3) Device Identification
        # -------------------------------------------------
        identity = ModbusDeviceIdentification()
        identity.VendorName = "HuaweiBatterySim"
        identity.ProductCode = "HB01"
        identity.ProductName = "Battery Emulator"
        identity.ModelName = "PC-Simulator"
        identity.MajorMinorRevision = "1.0"

        # -------------------------------------------------
        # 4) Raw Packet Hook
        # -------------------------------------------------
        def raw_request(msg):
            self.log_signal.emit(f"[RX Raw] {msg.hex(' ')}")

        def raw_response(msg):
            self.log_signal.emit(f"[TX Raw] {msg.hex(' ')}")

        # -------------------------------------------------
        # 5) Modbus RTU Slave 서버 실행 (Slave ID = 3)
        # -------------------------------------------------
        await StartSerialServer(
            context=self.context,
            identity=identity,
            framer="rtu",       # 3.11.3 호환
            port=self.port,
            baudrate=self.baudrate,
            stopbits=1,
            bytesize=8,
            parity='N',
            unit_id=[3],        # Slave ID 설정
            custom_handlers={
                "raw_request": raw_request,
                "raw_response": raw_response,
            }
        )

    def run(self):
        asyncio.run(self.start_modbus())


# ========================================================
# GUI
# ========================================================
class ModbusGui(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Huawei Battery Modbus RTU Emulator (pymodbus 3.11.3)")
        self.resize(500, 600)

        layout = QVBoxLayout()

        # COM Port 선택
        self.com_combo = QComboBox()
        for p in serial.tools.list_ports.comports():
            self.com_combo.addItem(p.device)

        # Baudrate 선택
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])

        # 버튼
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)

        self.btn_connect.clicked.connect(self.start_server)
        self.btn_disconnect.clicked.connect(self.stop_server)

        # 로그창
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        # Layout 구성
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Serial Port:"))
        port_layout.addWidget(self.com_combo)

        baud_layout = QHBoxLayout()
        baud_layout.addWidget(QLabel("Baudrate:"))
        baud_layout.addWidget(self.baud_combo)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_disconnect)

        layout.addLayout(port_layout)
        layout.addLayout(baud_layout)
        layout.addLayout(btn_layout)
        layout.addWidget(QLabel("TX / RX Raw Log:"))
        layout.addWidget(self.log)

        self.setLayout(layout)

        self.server_thread = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time_registers)

    # -----------------------------------------------------
    def start_server(self):
        port = self.com_combo.currentText()
        baud = int(self.baud_combo.currentText())

        self.server_thread = ModbusServerThread(port, baud)
        self.server_thread.log_signal.connect(self.add_log)
        self.server_thread.start()

        self.add_log(f"Modbus RTU Slave Started on {port} @ {baud} (Slave ID = 3)")
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)

        self.timer.start(1000)

    # -----------------------------------------------------
    def stop_server(self):
        if self.server_thread:
            self.server_thread.terminate()
            self.add_log("Modbus Server Stopped.")

        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.timer.stop()

    # -----------------------------------------------------
    def update_time_registers(self):
        """PC 시간 → 레지스터에 1초마다 업데이트"""
        if not self.server_thread or self.server_thread.context is None:
            return

        now = datetime.now()
        slave = self.server_thread.context[0]  # 3.11.x Context는 0번 인덱스로 접근
        slave.setValues(0x2000, [
            now.year, now.month, now.day,
            now.hour, now.minute, now.second
        ])

    # -----------------------------------------------------
    def add_log(self, text):
        self.log.append(text)
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum()
        )


# ========================================================
# 실행
# ========================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ModbusGui()
    gui.show()
    sys.exit(app.exec())
