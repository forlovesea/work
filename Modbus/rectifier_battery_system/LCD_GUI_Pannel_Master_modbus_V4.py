import sys
import struct
import serial
import serial.tools.list_ports
import datetime
import csv
from PySide6.QtWidgets import QSizePolicy, QFileDialog  # QFileDialog 추가

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QMessageBox, QSplitter, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from pymodbus.client.serial import ModbusSerialClient
from PySide6.QtGui import QFont


# ============================
# CRC
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
        # pymodbus 3.x: send/recv 사용 권장[web:12][web:15]
        self.client.send(frame)
        return self.client.recv(256)


# ============================
# Worker Thread
# ============================
class PollWorker(QThread):
    battery_signal = Signal(str)      # 배터리 텍스트 전체
    time_signal = Signal(str)         # 시간 문자열
    cell_signal = Signal(str)         # 셀 텍스트 전체
    log_signal = Signal(str)          # TX/RX 로그 문자열
    alarm_signal = Signal(str)
    alarm_count_signal = Signal(int)
    error_signal = Signal(str)        # 에러 메시지
    barcode_signal = Signal(str)

    def __init__(self, port: str, parent=None):
        super().__init__(parent)
        self.port = port
        self.master = None
        self.running = True
        self.selected_n = 1

    def stop(self):
        self.running = False
        # Modbus timeout을 0.1초로 줄여서 빠르게 빠져나옴
        if self.master and self.master.client:
            self.master.client.timeout = 0.1

    # ---------- Raw helpers (GUI의 메서드를 그대로 옮김) ----------
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

    def read_uint16(self, addr):
        if not self.running:
            return 0  # 즉시 종료
    
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
        raw = bytearray()
        for i in range(0, len(data), 2):
            raw.append(data[i])
            raw.append(data[i + 1])
        try:
            s = raw.rstrip(b"\x00").decode("ascii", errors="ignore")
        except Exception:
            s = ""
        return s

    def log_frame(self, title, data: bytes):
        hexstr = " ".join(f"{b:02X}" for b in data)
        self.log_signal.emit(f"[{title}] {hexstr}")

    # ---------- Time ----------
    def poll_time(self):
        slave = 33
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

        if len(rx) >= 3 + 6 * 2 + 2:
            data = rx[3:3 + 12]
            regs = struct.unpack(">6H", data)
            year, month, day, hour, minute, second = regs
            text = (
                f"Time : {year:04d}-{month:02d}-{day:02d} "
                f"{hour:02d}:{minute:02d}:{second:02d}"
            )
            self.time_signal.emit(text)

    # ---------- Battery ----------
    def poll_battery(self, n: int):
        text_batt_lines = []
        text_cell_lines = []

        # Temperature (global)
        temp = self.read_int16(0xA706)
        text_batt_lines.append(f"Battery Temperature : {temp} degC")
        text_batt_lines.append(f"[Battery Module N = {n}]")

        # Barcode
        barcode_base = 0xC670 + (n - 1) * 32
        barcode = self.read_string(barcode_base, 15)
        barcode = barcode.strip('\x00').strip()
        text_batt_lines.append(f"Battery Barcode : {barcode}")

        # Voltage (N) UINT32 /10
        v_base = 0xA731 + (n - 1) * 64
        voltage_raw = self.read_uint32(v_base)
        voltage = voltage_raw / 10.0
        text_batt_lines.append(f"Battery Voltage : {voltage:.1f} V")

        # Current (N) INT32 /10
        c_base = 0xA733 + (n - 1) * 64
        current_raw = self.read_int32(c_base)
        current = current_raw / 10.0
        text_batt_lines.append(f"Battery Current : {current:.1f} A")

        # SOC
        soc_base = 0xA739 + (n - 1) * 64
        soc = self.read_uint16(soc_base)
        text_batt_lines.append(f"Battery SOC : {soc} %")

        # 각 Cell 정보
        for i in range(1, 16):
            addr_t = 0xA739 + i + (n - 1) * 64
            t = self.read_int16(addr_t)            

            addr_v = 0xA74F + i + (n - 1) * 64
            v = self.read_uint16(addr_v) / 10
            text_cell_lines.append(f"Cell-{i:2d} Temp : {t:2d} degC / Volt : {v:.1f} V")            

        self.barcode_signal.emit(f"Barcode: {barcode}")
        self.battery_signal.emit("\n".join(text_batt_lines))
        self.cell_signal.emit("\n".join(text_cell_lines))
        
    # ---------- Alarm ----------
    def poll_alarm(self, n: int):
        lines = []
        alarm_count = 0
        fmt = "{:<35} {:<12} {:<15} {:<10}"
        
        # 헤더
        lines.append(fmt.format("ALARM ITEM", "ADDRESS", "STATUS", "VALUE"))
        lines.append("-" * 72)
        
        # 1) Battery Missing (global)
        val = self.read_uint16(0x5022)
        if val == 0:
            st = "normal" 
        else:            
            st = "alarm"
            lines.append(fmt.format("Battery Missing", "(0x5022)", st, f"(0x{val:04X})"))
            alarm_count += 1
        
        # 2) Battery Module 1~10 전체 알람 읽기
        for module_n in range(1, 11):  # 1~10
            # Lithium Battery N Abnormal
            addr = 0x5036 + (module_n - 1) * 1
            val = self.read_uint16(addr)
            if val == 0:
                st = "normal"
            elif val == 1:
                st = "Fault"
            elif val == 2:
                st = "Protection"
            elif val == 3:
                st = "Communication Fail"
            else:
                st = f"Unknown(0x{val:04X})"
            if val != 0:
                alarm_count += 1
                lines.append(fmt.format(f"Lithium Batt {module_n} Abnormal", f"(0x{addr:04X})", st, f"(0x{val:04X})"))
            
            # 각 모듈의 주요 알람들 (0x8431 ~ 0x843D)
            alarms = [
                ("Charge OV", 0x8431),
                ("Charge OC", 0x8432),
                ("Overdischarge", 0x8433),
                ("Heavy Load", 0x8434),
                ("Rev Connection", 0x8435),
                ("Over Temp", 0x8436),
                ("Comm Fail", 0x8437),
                ("Low Temp", 0x8438),
                ("High Temp Prot", 0x8439),
                ("Low Temp Prot", 0x843A),
                ("Overcharge Prot", 0x843B),
                ("Overdis Prot", 0x843C),
                ("Overcur Prot", 0x843D)
            ]
            
            for name, base_addr in alarms:
                addr = base_addr + (module_n - 1) * 64
                v = self.read_uint16(addr)
                
                if v == 0:
                    st = "normal" 
                else:
                    alarm_count += 1
                    st = "alarm"
                    lines.append(fmt.format(f"Batt{module_n} {name}", f"(0x{addr:04X})", st, f"(0x{v:04X})"))
            #lines.append(fmt.format(f"{Battery Module}-{module_n:2d}", "", "", ""))
        self.alarm_signal.emit("\n".join(lines))
        self.alarm_count_signal.emit(alarm_count)
        
    # ---------- 메인 루프 ----------
    def run(self):
        try:
            self.master = ModbusMaster(self.port)
            if not self.master.connect():
                self.error_signal.emit(f"Failed to connect {self.port}")
                return

            while self.running:
                self.poll_time()
                self.poll_battery(self.selected_n)
                self.poll_alarm(self.selected_n) 
                self.msleep(500)  # 500ms 간격
                #self.msleep(1000)  # 1초 간격

        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            if self.master:
                self.master.close()
                self.master = None


# ============================
# GUI
# ============================
class TimeBatteryGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor Program, Rectifier LFP Battery TBC1000B-NDA1")
        self.resize(900, 700)
        
        self.log_enabled = True
        self.is_connected = False
        self.worker: PollWorker | None = None        
        
        #--- 로그 저장 관련 상태 ---
        self.save_log_enabled = False
        self.log_file_path:str|None = None
        self.latest_battery_text = ""
        self.latest_cell_text = ""
        self.latest_alarm_text = ""
        self.latest_time_text = ""
        self.latest_alarm_count = 0  # 초기화 추가
        self.current_displayed_module = 1  # ← 실제 표시된 모듈 번호
        self.pending_module_change = False  # 대기중인 모듈 변경 플래그
        
        self.build_ui()
        self.update_button_styles()  # ← 초기 스타일 설정
        self.refresh_ports()

    # ---------- UI ----------
    def update_button_styles(self):
        """버튼 색상 상태 업데이트"""
        if self.is_connected:
            # 연결됨: Connect 녹색, Disconnect 빨간색
            self.btn_connect.setEnabled(False)
            self.btn_connect.setStyleSheet("""
                QPushButton {
                    background-color: #28a745; 
                    color: white; 
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
                QPushButton:pressed {
                    background-color: #1e7e34;
                }
            """)
            self.btn_disconnect.setEnabled(True)
            self.btn_disconnect.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545; 
                    color: white; 
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
                QPushButton:pressed {
                    background-color: #a71e2a;
                }
            """)
        else:
            self.btn_connect.setEnabled(True)
            
            # 연결 안됨: 기본 회색 버튼들
            self.btn_connect.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d; 
                    color: white; 
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                }
                QPushButton:pressed {
                    background-color: #545b62;
                }
            """)
            self.btn_disconnect.setEnabled(False)  # ← 비활성화 추가
            self.btn_disconnect.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d; 
                    color: white; 
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                }
                QPushButton:pressed {
                    background-color: #545b62;
                }
            """)    
    
    def on_save_log_changed(self, state: int):
        # 체크되면 True, 아니면 False
        #self.save_log_enabled = (state == Qt.CheckState.Checked)
        self.save_log_enabled = self.chk_save_log.isChecked()
        # 체크됐을 때만 Log Path 버튼 활성화
        self.btn_log_path.setEnabled(self.save_log_enabled)
        # 체크를 해제하면 경로만 유지하거나, 필요 시 초기화 가능
        # 여기서는 경로는 그대로 두고, 단순히 기록만 중지

    def on_select_log_path(self):
        # CSV 파일 저장 경로 선택 다이얼로그
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Select CSV Log File",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if file_name:
            self.log_file_path = file_name
            QMessageBox.information(self, "Log Path", f"Log file set to:\n{file_name}")

    def append_csv_log(self):
        """Battery는 그대로, Cell1~15는 각각 별도 열, Alarm은 비정상 시에만 기록"""
        if not self.save_log_enabled:
            return
        if not self.log_file_path:
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        batt = self.latest_battery_text.replace("\n", " | ")
        
        # Cell 정보를 파싱해서 각각의 열로 분리
        cell_data = self.parse_cell_data(self.latest_cell_text)
        
        # Alarm 처리 (비정상 시에만 전체 내용, 정상은 "All Normal")
        if hasattr(self, 'latest_alarm_count') and self.latest_alarm_count > 0:
            alarm = self.latest_alarm_text.replace("\n", " | ")
        else:
            alarm = "All Normal"

        try:
            file_exists = False
            try:
                with open(self.log_file_path, "r", encoding="utf-8") as f:
                    file_exists = True
            except FileNotFoundError:
                file_exists = False

            with open(self.log_file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    # Cell1~15까지 15개 열 추가한 헤더
                    header = ["timestamp", "battery_info"] + [f"cell{i}_temp" for i in range(1, 16)] + [f"cell{i}_volt" for i in range(1, 16)] + ["alarm_info"]
                    writer.writerow(header)
                
                # 데이터 행 작성 (Cell 데이터가 부족하면 0으로 채움)
                row = [timestamp, batt] + cell_data + [alarm]
                writer.writerow(row)
                
        except Exception as e:
            QMessageBox.warning(self, "CSV Log Error", str(e))
    
    def parse_cell_data(self, cell_text: str):
        """Cell-01 ~ Cell-15 정보를 각각 temp/volt로 파싱"""
        cell_lines = cell_text.split('\n')
        temps = [0.0] * 15
        volts = [0.0] * 15
        
        for line in cell_lines:
            if line.strip() and "Cell-" in line:
                try:
                    # "Cell-01 Temp : 24 degC / Volt : 3.2 V" 형식 파싱
                    parts = line.split()
                    cell_num = int(parts[0].replace("Cell-", ""))
                    temp_str = parts[3]  # "24"
                    volt_str = parts[7]  # "3.2"
                    
                    temps[cell_num-1] = float(temp_str)
                    volts[cell_num-1] = float(volt_str)
                except (ValueError, IndexError):
                    continue
        
        # [temp1, temp2, ..., temp15, volt1, volt2, ..., volt15] 순서로 반환
        return temps + volts
        
    def build_ui(self):
        root_layout = QVBoxLayout(self)

        # Top: COM control
        top = QHBoxLayout()
        self.cmb_port = QComboBox()

        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_connect.clicked.connect(self.connect_port)
        self.btn_disconnect.clicked.connect(self.disconnect_port)

        top.addWidget(QLabel("COM Port"))
        top.addWidget(self.cmb_port)
        top.addWidget(self.btn_connect)
        top.addWidget(self.btn_disconnect)

        root_layout.addLayout(top)

        # Splitter (좌: 로그, 우: 시간/배터리/셀)[web:11][web:13]
        splitter = QSplitter(Qt.Horizontal)

        # ----- Left: 로그 + Clear -----
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        self.text_frame = QTextEdit()
        self.text_frame.setReadOnly(True)
        # 버튼 두 개를 같은 줄에
        btn_bar = QHBoxLayout()
        self.btn_toggle_log = QPushButton("Stop Log")
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.toggled.connect(self.on_toggle_log)

        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.clicked.connect(self.text_frame.clear)
###
        # Alarm Status + Count 라벨 한 줄에
        alarm_header_layout = QHBoxLayout()

        # 메인 라벨
        self.lbl_alarm_status = QLabel("Alarm Status")
        self.lbl_alarm_status.setStyleSheet("font-size:12px; font-weight:bold;")

        # 카운트 라벨 (옆에 배치)
        self.lbl_alarm_count = QLabel("(0)")
        self.lbl_alarm_count.setStyleSheet("color:red; font-weight:bold; font-size:12px;")

        alarm_header_layout.addWidget(self.lbl_alarm_status)
        alarm_header_layout.addWidget(self.lbl_alarm_count)
        alarm_header_layout.addStretch()  # 오른쪽 여백
###
        btn_bar.addWidget(self.btn_toggle_log)
        btn_bar.addWidget(self.btn_clear_log)
        btn_bar.addStretch()   # 오른쪽 여백

        left_layout.addLayout(btn_bar)
        left_layout.addWidget(QLabel("TX / RX Frame"))
        left_layout.addWidget(self.text_frame)

        # ----- Right: 시간 + 배터리 -----
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Time view (+ Save Log / Log Path)
        time_bar = QHBoxLayout()
        time_bar.addWidget(QLabel("Read Time (0x2000, 6 regs)"))        
        
        self.lbl_time = QLabel("Time : -")
        self.lbl_time.setStyleSheet("font-size:18px; font-weight:bold;")
        time_bar.addWidget(self.lbl_time)

        # Save Log 체크박스
        self.chk_save_log = QCheckBox("Save Log")
        self.chk_save_log.stateChanged.connect(self.on_save_log_changed)
        time_bar.addWidget(self.chk_save_log)
        
        # Log Path 버튼 (초기 비활성화)
        self.btn_log_path = QPushButton("Log Path")
        self.btn_log_path.setEnabled(False)
        self.btn_log_path.clicked.connect(self.on_select_log_path)
        time_bar.addWidget(self.btn_log_path)
        
        time_bar.addStretch()
        right_layout.addLayout(time_bar)
        
        # Battery selector
        sel = QHBoxLayout()
        self.cmb_n = QComboBox()
        for i in range(1, 33):
            self.cmb_n.addItem(str(i))
        self.cmb_n.currentIndexChanged.connect(self.on_batt_index_changed)

        sel.addWidget(QLabel("Battery Module N"))
        sel.addWidget(self.cmb_n)
        sel.addStretch()
        right_layout.addLayout(sel)

        self.lbl_barcode = QLabel("Barcode: -")
        self.lbl_barcode.setStyleSheet("""
            font-size: 22px; 
            font-weight: bold; 
            color: #dc3545; 
            background-color: #ffebee; 
            padding: 8px; 
            border: 2px solid #f44336; 
            border-radius: 5px;
            margin-bottom: 5px;
        """)
        self.lbl_barcode.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        right_layout.addWidget(self.lbl_barcode)

        # Battery info area
        right_layout.addWidget(QLabel("Battery Information"))
        self.text_battery = QTextEdit()
        self.text_battery.setReadOnly(True)
        #self.text_battery.setMinimumHeight(140)
        self.text_battery.setMinimumHeight(0) #
        right_layout.addWidget(self.text_battery)

       # → 변경 (한 줄로)
        cell_header_layout = QHBoxLayout()

        # "Cell Information" 라벨
        cell_title = QLabel("Cell Information")
        cell_title.setStyleSheet("font-weight: bold;")

        # Module 라벨
        self.lbl_current_module = QLabel("[Module-1] ")
        self.lbl_current_module.setStyleSheet("""
            font-size: 14px; 
            font-weight: bold; 
            color: #d63384; 
            background-color: #fff3cd; 
            padding: 4px 8px; 
            border: 2px solid #ffc107; 
            border-radius: 5px;
            margin-left: 10px;
        """)

        cell_header_layout.addWidget(cell_title)
        cell_header_layout.addWidget(self.lbl_current_module)
        cell_header_layout.addStretch()  # 오른쪽 여백

        right_layout.addLayout(cell_header_layout)  # ← Layout으로 추가

        # Cell 텍스트 영역
        self.text_cell = QTextEdit()
        self.text_cell.setReadOnly(True)
        self.text_cell.setMinimumHeight(0)
        right_layout.addWidget(self.text_cell)
        
        right_layout.addLayout(alarm_header_layout)
        
        # QTextEdit
        self.text_alarm = QTextEdit()
        self.text_alarm.setReadOnly(True)
        #self.text_alarm.setMinimumHeight(180)
        self.text_alarm.setMinimumHeight(0)
        self.text_alarm.setLineWrapMode(QTextEdit.NoWrap)
        self.text_alarm.setStyleSheet("font-family: 'Courier New', monospace; font-size: 9pt;")
        
        self.text_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.text_battery.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.text_cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.text_alarm.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # build_ui()에서 이미 되어 있어야 함
        self.text_battery.setReadOnly(True)
        self.text_cell.setReadOnly(True)
        self.text_alarm.setReadOnly(True)

        right_layout.setStretchFactor(self.text_battery, 1)
        right_layout.setStretchFactor(self.text_cell, 2)
        right_layout.setStretchFactor(self.text_alarm, 1)
        right_layout.addWidget(self.text_alarm)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        root_layout.addWidget(splitter)
        root_layout.setStretch(0, 0)
        root_layout.setStretch(1, 1)

    # ---------- Serial ----------
    def refresh_ports(self):
        self.cmb_port.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.cmb_port.addItem(p.device)

    def connect_port(self):
        port = self.cmb_port.currentText()
        if not port:
            QMessageBox.warning(self, "Connect", "No COM port selected")
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Connect", "Already connected")
            return
        
        if self.is_connected:  # 이미 연결된 상태면 무시
            return
        
        self.worker = PollWorker(port)
        # 신호 연결[web:14]
        self.worker.log_signal.connect(self.append_log)
        self.worker.time_signal.connect(self.update_time)
        self.worker.battery_signal.connect(self.update_battery)
        self.worker.cell_signal.connect(self.update_cell)
        self.worker.alarm_signal.connect(self.update_alarm) 
        self.worker.error_signal.connect(self.show_error)
        self.worker.alarm_count_signal.connect(self.update_alarm_count)
        self.worker.barcode_signal.connect(self.update_barcode)
        
        self.worker.start()
        #QMessageBox.information(self, "Connect", f"Connected to {port}")
        if self.worker.isRunning():  # 연결 성공 확인
            self.is_connected = True
            QMessageBox.information(self, "Connect", f"Connected to {port}")
            self.update_button_styles()  # ← 색상 변경
        else:
            self.worker = None
            self.update_button_styles()  # 실패시 원래대로
            
    def update_barcode(self, barcode_text: str):
        self.lbl_barcode.setText(barcode_text)
    
    def update_alarm_count(self, count: int):
        self.lbl_alarm_count.setText(f"({count})")
        self.latest_alarm_count = count  # 이 라인 있어야 함
    
    def disconnect_port(self):
        if self.worker:
            self.worker.stop()
            self.worker.master.client.timeout = 0.1  # ← timeout 급감
            self.worker.wait(1500)  # 1.5초만 대기
            if self.worker.isRunning():
                self.worker.terminate()
                self.worker.wait(500)
            
            self.worker.deleteLater()
            self.worker = None
            self.is_connected = False
            self.update_button_styles()
            QMessageBox.information(self, "Disconnect", "Disconnected")


    # ---------- Slots ----------
    def append_log(self, text: str):
        if not self.log_enabled:
            return
        self.text_frame.append(text)

    def update_time(self, text: str):
        self.lbl_time.setText(text)
        self.latest_time_text = text
        self.append_csv_log()

    def update_battery(self, text: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Battery에도 현재 모듈 표시 추가 (선택사항)
        current_n = getattr(self.worker, 'selected_n', self.current_displayed_module)
        
        self.text_battery.setPlainText(f"[{timestamp}]\n\n{text}")
        self.latest_battery_text = text
        self.append_csv_log()


    def update_cell(self, text: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 실제 워커에서 읽은 모듈 번호만 사용
        current_n = getattr(self.worker, 'selected_n', self.current_displayed_module)
        
        # 라벨 업데이트 (실제 데이터와 동기화)
        self.lbl_current_module.setText(f"[Module-{current_n}]")
        self.current_displayed_module = current_n  # 상태 동기화
        self.pending_module_change = False  # 대기 해제
        
        self.text_cell.setPlainText(f"[{timestamp}]\n\n{text}")
        self.latest_cell_text = text
        self.append_csv_log()




    def update_alarm(self, text: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.text_alarm.setPlainText(f"[{timestamp}]\n\n{text}")
        self.latest_alarm_text = text
        self.append_csv_log()

        
    def show_error(self, msg: str):
        QMessageBox.critical(self, "Error", msg)

    def on_batt_index_changed(self, idx: int):
        n = idx + 1
        if self.worker:
            self.worker.selected_n = n
            self.pending_module_change = True  # 변경 요청만 설정
        # 라벨은 절대 건드리지 않음!
        # 현재 모듈의 Cell 정보임을 명확히 표시
        #self.lbl_current_module.setText(f"Battery Module-{n} Cell Information")



    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
            #self.worker.wait(2000)            
            self.worker.wait() #Qt 공식 문서에서도 wait()은 timeout 없이 써야 안전
            self.worker.deleteLater()
            self.worker = None
            self.is_connected = False  # ← 상태 초기화
            
        self.update_button_styles()  # ← 기본 상태로
        super().closeEvent(event)

    def on_toggle_log(self, checked: bool):
        # checked == True 이면 "멈춤" 상태
        self.log_enabled = not checked
        if checked:
            self.btn_toggle_log.setText("Start Log")
        else:
            self.btn_toggle_log.setText("Stop Log")

# ============================
# Main
# ============================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TimeBatteryGui()
    win.show()
    sys.exit(app.exec())
    
