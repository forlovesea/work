#pyinstaller --clean --noconsole --onefile --icon=./lcd.ico --collect-all PySide6 --name TBC1000B_LCD_Modbus LCD_GUI_Pannel_Master_modbus_V5.py
import sys
import struct
import serial
import serial.tools.list_ports
from datetime import datetime
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
    def __init__(self, port, baudrate=9600, slave_id=214):
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
    system_signal = Signal(str)
    
    def __init__(self, port: str, parent=None):
        super().__init__(parent)
        self.port = port
        self.master = None
        self.running = True

    def stop(self):
        self.running = False
        # Modbus timeout을 0.1초로 줄여서 빠르게 빠져나옴
        if self.master and self.master.client:
            self.master.client.timeout = 0.1

    # ---------- Raw helpers (GUI의 메서드를 그대로 옮김) ----------
    def build_read_frame(self, start_addr, count):
        slave = 214
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
        slave = 214
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
    def poll_battery(self):

        lines = []

        # =========================
        # Battery 기본 정보
        # =========================
        bus_v = self.read_uint16(0x0000) * 0.01
        batt_v = self.read_uint16(0x0001) * 0.01
        batt_i = self.read_int16(0x0002) * 0.01
        soc    = self.read_uint16(0x0003)

        max_t  = self.read_int16(0x0005)
        min_t  = self.read_int16(0x0006)

        mode   = self.read_uint16(0x000E)

        # =========================
        # Mode 해석
        # =========================
        mode_map = {
            0: "Hibernation",
            1: "Low Power",
            2: "Charge",
            3: "Discharge",
            4: "Standby"
        }

        mode_str = mode_map.get(mode, f"Unknown({mode})")

        # =========================
        # 출력
        # =========================
        lines.append(f"[{self.last_read_time}]")
        lines.append("-" * 40)
        lines.append(f"Busbar Voltage   : {bus_v:.2f} V")
        lines.append(f"Battery Voltage  : {batt_v:.2f} V")
        lines.append(f"Battery Current  : {batt_i:.2f} A")
        lines.append(f"SOC              : {soc} %")
        lines.append(f"Max Temp         : {max_t} °C")
        lines.append(f"Min Temp         : {min_t} °C")
        lines.append(f"Module Mode      : {mode_str}")

        # 🔥 Battery 전용 emit
        self.battery_signal.emit("\n".join(lines))
    
    def poll_cell(self):

        text_cell_lines = []
        read_time = getattr(self, "last_read_time", "-")
        # 🔥 system info에서 읽은 값 사용
        cell_count = getattr(self, "cell_count", 16)

        temp_base = 0x0012
        volt_base = 0x0022

        temps = []
        volts = []

        # =========================
        # Temperature
        # =========================
        frame = self.build_read_frame(temp_base, cell_count)
        rx = self.send_and_recv(frame)

        if rx and len(rx) >= 3 + cell_count * 2 + 2:
            data = rx[3:3 + cell_count * 2]
            temps = list(struct.unpack(f">{cell_count}h", data))

        # =========================
        # Voltage
        # =========================
        frame = self.build_read_frame(volt_base, cell_count)
        rx = self.send_and_recv(frame)

        if rx and len(rx) >= 3 + cell_count * 2 + 2:
            data = rx[3:3 + cell_count * 2]
            regs = struct.unpack(f">{cell_count}H", data)
            volts = [r * 0.001 for r in regs]

        # =========================
        # 출력
        # =========================
        text_cell_lines.append(f"[{read_time}]")
        text_cell_lines.append("-" * 40)
        for i in range(cell_count):
            t = temps[i] if i < len(temps) else 0
            v = volts[i] if i < len(volts) else 0

            text_cell_lines.append(
                f"Cell-{i+1:02d} : Temp {t} °C / Volt {v:.3f} V"
            )

        self.cell_signal.emit("\n".join(text_cell_lines))
    
    # ---------- Alarm ----------    
    def poll_alarm(self):
        lines = []
        alarm_count = 0

        def check_bits(name, addr):
            nonlocal alarm_count
            val = self.read_uint16(addr)

            if val != 0:
                alarm_count += 1
                lines.append(f"{name} (0x{addr:04X}) : 0x{val:04X}")

        check_bits("Critical Alarm 1", 0x0046)
        check_bits("Critical Alarm 2", 0x0047)
        check_bits("Major Alarm", 0x0048)
        check_bits("Minor Alarm", 0x0049)
        check_bits("Module Alarm", 0x004A)

        if alarm_count == 0:
            lines.append("All Normal")

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
                self.poll_system_info()
                self.poll_battery()
                self.poll_cell()
                self.poll_alarm()
                #self.msleep(500)  # 500ms 간격
                self.msleep(1000)  # 1초 간격

        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            if self.master:
                self.master.close()
                self.master = None

    def poll_system_info(self):
        lines = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_read_time = now  # 🔥 공용 저장

        # 포맷 정렬용 함수 ---------------------------------------------
        def fmt(title, value, width=18):  # 너비 18로 살짝 늘리면 더 안정적
            return f"{title.ljust(width)}: {value}"
        # -------------------------------------------------------------

        # 🔥 Battery Model (0x0332 ~ 0x033D, 총 12개 레지스터)
        frame = self.build_read_frame(0x0332, 12)
        rx = self.send_and_recv(frame)

        model_str = ""
        if rx and len(rx) >= 3 + 12*2 + 2:
            chars = []
            for i in range(12):
                val = (rx[3 + i*2] << 8) | rx[4 + i*2]
                high_byte = (val >> 8) & 0xFF
                low_byte  = val & 0xFF
                if high_byte not in (0x00, 0xFF):
                    chars.append(chr(high_byte))
                if low_byte not in (0x00, 0xFF):
                    chars.append(chr(low_byte))
            model_str = "".join(chars).strip()
        else:
            model_str = "Read Fail"

        lines.append(fmt("Battery Model", model_str))

        # =========================
        # 1. 통계 데이터
        # =========================
        discharge_times = self.read_uint32(0x0042)
        discharge_ah    = self.read_uint32(0x0044)

        lines.append(fmt("Discharge Times", discharge_times))
        lines.append(fmt("Discharge AH", f"{discharge_ah} Ah"))

        # =========================
        # 2. Alarm 상태
        # =========================
        crit1 = self.read_uint16(0x0046)
        crit2 = self.read_uint16(0x0047)
        major = self.read_uint16(0x0048)
        minor = self.read_uint16(0x0049)
        module= self.read_uint16(0x004A)

        # =========================
        # Critical1 (0x0046)
        # =========================
        crit1_desc = []
        if crit1 & (1 << 0):
            crit1_desc.append("Warning")
        for i in range(1, 7):
            if crit1 & (1 << i):
                crit1_desc.append(f"Fault{i}")
        crit1_text = "Normal" if not crit1_desc else ", ".join(crit1_desc)
        lines.append(fmt("Critical1", f"0x{crit1:04X} ({crit1_text})"))

        # =========================
        # Critical2 (0x0047)
        # =========================
        crit2_desc = []
        for i in range(8):
            if crit2 & (1 << i):
                crit2_desc.append(f"Fault{i}")
        crit2_text = "Normal" if not crit2_desc else ", ".join(crit2_desc)
        lines.append(fmt("Critical2", f"0x{crit2:04X} ({crit2_text})"))

        # =========================
        # Major (0x0048)
        # =========================
        major_desc = []
        for i in range(15):   # 0~14
            if major & (1 << i):
                major_desc.append(f"Protection{i}")
        major_text = "Normal" if not major_desc else ", ".join(major_desc)
        lines.append(fmt("Major", f"0x{major:04X} ({major_text})"))

        # =========================
        # Minor (0x0049)
        # =========================
        minor_desc = []
        for i in range(10):   # 0~9
            if minor & (1 << i):
                minor_desc.append(f"Warning{i}")
        minor_text = "Normal" if not minor_desc else ", ".join(minor_desc)
        lines.append(fmt("Minor", f"0x{minor:04X} ({minor_text})"))

        # =========================
        # Module (0x004A)
        # =========================
        module_desc = []
        # Warning bits
        for i in [0, 2, 4, 9, 10, 12]:
            if module & (1 << i):
                module_desc.append(f"Warning{i}")
        # Protection bits
        for i in [3, 5, 7, 8, 11]:
            if module & (1 << i):
                module_desc.append(f"Protection{i}")
        # Fault bits
        for i in [6, 13]:
            if module & (1 << i):
                module_desc.append(f"Fault{i}")
        module_text = "Normal" if not module_desc else ", ".join(module_desc)
        lines.append(fmt("Module", f"0x{module:04X} ({module_text})"))

        # =========================
        # 3. Version / Info
        # =========================
        sw = self.read_uint16(0x0101)
        hw = self.read_uint16(0x0102)
        boot = self.read_uint16(0x0103)
        dtype = self.read_uint16(0x0104)
        manu  = self.read_uint16(0x0105)
        sub   = self.read_uint16(0x0106)
        cap   = self.read_uint16(0x0107)
        cell_count = self.read_uint16(0x010F)

        lines.append(fmt("SW Version", sw))
        lines.append(fmt("HW Version", hw))
        lines.append(fmt("BootLoader", boot))

        BMS_TYPE_MAP = {
            0x01: "BMS(Integrated)",
            0x02: "BMS(Separate)"
        }
        dtype_str = BMS_TYPE_MAP.get(dtype, f"Unknown (0x{dtype:02X})")
        lines.append(fmt("DeviceType", f"0x{dtype:02X} ({dtype_str})"))

        VENDOR_MAP = {
            0x00: "Huawei"
        }
        vendor_str = VENDOR_MAP.get(manu, f"Unknown (0x{manu:02X})")
        lines.append(fmt("Manufacturer", f"0x{manu:02X} ({vendor_str})"))
        lines.append(fmt("Sub SW ID", sub))
        lines.append(fmt("Capacity", f"{cap} Ah"))

        # 유효성 체크
        if cell_count is None or cell_count <= 0 or cell_count > 64:
            cell_count = 15
        self.cell_count = cell_count
        lines.append(fmt("Cell Count", cell_count))

        # =========================
        # 4. Power 정보
        # =========================
        power = self.read_uint16(0x0204)
        ext_v = self.read_uint16(0x0205) * 0.01
        lines.append(fmt("Output Power", f"{power} W"))
        lines.append(fmt("Ext Voltage", f"{ext_v:.2f} V"))

        runtime = self.read_uint32(0x0209)
        if runtime is not None:
            years = runtime // (24 * 365)
            remaining = runtime % (24 * 365)
            days = remaining // 24
            hours = remaining % 24
            lines.append(fmt("Run Time", f"{years}year {days}day {hours}hour ({runtime} h)"))
        else:
            lines.append(fmt("Run Time", "Read Fail"))

        # GUI로 전달
        self.system_signal.emit("\n".join(lines))
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
                    header = ["timestamp"] + [f"cell{i}_temp" for i in range(1, 17)] + [f"cell{i}_volt" for i in range(1, 17)]
                    writer.writerow(header)
                
                # 데이터 행 작성 (Cell 데이터가 부족하면 0으로 채움)
                row = [timestamp] + cell_data
                writer.writerow(row)
                
        except Exception as e:
            QMessageBox.warning(self, "CSV Log Error", str(e))
    
    def parse_cell_data(self, cell_text: str):
        lines = cell_text.split('\n')

        temps = []
        volts = []

        for line in lines:
            if "Cell-" in line:
                try:
                    parts = line.split()

                    # "Cell-01 : Temp 25 °C / Volt 3.210 V"
                    temp = float(parts[3])
                    volt = float(parts[7])

                    temps.append(temp)
                    volts.append(volt)

                except:
                    continue

        # 16개 보장
        while len(temps) < 16:
            temps.append(0.0)
            volts.append(0.0)

        return temps + volts
        
    def build_ui(self):
        root_layout = QVBoxLayout(self)

        # =========================
        # Top (COM)
        # =========================
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

        # =========================
        # Left (TX/RX)
        # =========================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.text_frame = QTextEdit()
        self.text_frame.setReadOnly(True)
        self.text_frame.document().setMaximumBlockCount(1000)

        btn_bar = QHBoxLayout()
        self.btn_toggle_log = QPushButton("Stop Log")
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.toggled.connect(self.on_toggle_log)

        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.clicked.connect(self.text_frame.clear)

        btn_bar.addWidget(self.btn_toggle_log)
        btn_bar.addWidget(self.btn_clear_log)
        btn_bar.addStretch()

        left_layout.addLayout(btn_bar)
        left_layout.addWidget(QLabel("TX / RX Frame"))
        left_layout.addWidget(self.text_frame)

        # =========================
        # Middle (Battery + Cell)
        # =========================
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)

        # Battery
        mid_layout.addWidget(QLabel("Battery Information"))

        self.text_battery = QTextEdit()
        self.text_battery.setReadOnly(True)
        self.text_battery.setMinimumHeight(150)
        mid_layout.addWidget(self.text_battery)

        # Cell
        cell_header_layout = QHBoxLayout()
        cell_header_layout.addWidget(QLabel("Cell Information"))
        cell_header_layout.addStretch()
        mid_layout.addLayout(cell_header_layout)

        self.text_cell = QTextEdit()
        self.text_cell.setReadOnly(True)
        self.text_cell.setMinimumHeight(270)
        mid_layout.addWidget(self.text_cell)

        # =========================
        # Right (System + Alarm)
        # =========================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Time
        #time_bar = QHBoxLayout()
        #time_bar.addWidget(QLabel("Read Time"))
        #self.lbl_time = QLabel("Time : -")
        #self.lbl_time.setStyleSheet("font-size:18px; font-weight:bold;")
        #time_bar.addWidget(self.lbl_time)

        #self.chk_save_log = QCheckBox("Save Log")
        #self.chk_save_log.stateChanged.connect(self.on_save_log_changed)
        #time_bar.addWidget(self.chk_save_log)

        #self.btn_log_path = QPushButton("Log Path")
        #self.btn_log_path.setEnabled(False)
        #self.btn_log_path.clicked.connect(self.on_select_log_path)
        #time_bar.addWidget(self.btn_log_path)

        #time_bar.addStretch()
        #right_layout.addLayout(time_bar)

        # System
        right_layout.addWidget(QLabel("System Information"))

        self.text_system = QTextEdit()
        self.text_system.setReadOnly(True)
        self.text_system.setMinimumHeight(400)
        right_layout.addWidget(self.text_system)

        # Alarm Header
        alarm_header_layout = QHBoxLayout()

        self.lbl_alarm_status = QLabel("Alarm Status")
        self.lbl_alarm_status.setStyleSheet("font-size:12px; font-weight:bold;")

        self.lbl_alarm_count = QLabel("(0)")
        self.lbl_alarm_count.setStyleSheet("color:red; font-weight:bold; font-size:12px;")

        alarm_header_layout.addWidget(self.lbl_alarm_status)
        alarm_header_layout.addWidget(self.lbl_alarm_count)
        alarm_header_layout.addStretch()

        right_layout.addLayout(alarm_header_layout)

        # Alarm
        self.text_alarm = QTextEdit()
        self.text_alarm.setReadOnly(True)
        self.text_alarm.setMinimumHeight(180)
        right_layout.addWidget(self.text_alarm)

        # =========================
        # Splitter (🔥 핵심)
        # =========================
        splitter = QSplitter(Qt.Horizontal)

        splitter.addWidget(left_widget)    # 1열
        splitter.addWidget(mid_widget)     # 2열
        splitter.addWidget(right_widget)   # 3열

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)

        root_layout.addWidget(splitter)

        # =========================
        # Scroll 정책
        # =========================
        self.text_battery.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_system.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_alarm.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_cell.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        #self.resize(1400, 800)
        #self.setMinimumSize(1200, 700)
        
    def update_system(self, text: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.text_system.setPlainText(f"[{timestamp}]\n\n{text}")
    
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
        self.worker.system_signal.connect(self.update_system)
        self.worker.log_signal.connect(self.append_log)
        self.worker.time_signal.connect(self.update_time)
        self.worker.battery_signal.connect(self.update_battery)
        self.worker.cell_signal.connect(self.update_cell)
        self.worker.alarm_signal.connect(self.update_alarm) 
        self.worker.error_signal.connect(self.show_error)
        self.worker.alarm_count_signal.connect(self.update_alarm_count)
        #self.worker.barcode_signal.connect(self.update_barcode)
        
        self.worker.start()
        #QMessageBox.information(self, "Connect", f"Connected to {port}")
        if self.worker.isRunning():  # 연결 성공 확인
            self.is_connected = True
            QMessageBox.information(self, "Connect", f"Connected to {port}")
            self.update_button_styles()  # ← 색상 변경
        else:
            self.worker = None
            self.update_button_styles()  # 실패시 원래대로
            
    #def update_barcode(self, barcode_text: str):
        #self.lbl_barcode.setText(barcode_text)
    
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
         # 🔥 추가 (로그 너무 많을 때 샘플링)
        if len(text) > 200:   # 너무 긴 프레임 컷
            text = text[:200] + "..."
            
        self.text_frame.append(text)

    def update_time(self, text: str):
        self.lbl_time.setText(text)
        self.latest_time_text = text
        #self.append_csv_log()

    def update_battery(self, text: str):
        self.text_battery.setPlainText(text)
        self.latest_battery_text = text

    def update_cell(self, text: str):
        self.text_cell.setPlainText(text)
        self.latest_cell_text = text

    def toggle_expand(self):
        if self.text_cell.height() < 700:
            self.text_cell.setMinimumHeight(800)
            self.btn_expand.setText("축소")
        else:
            self.text_cell.setMinimumHeight(400)
            self.btn_expand.setText("확장")
        
    def update_alarm(self, text: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.text_alarm.setPlainText(f"[{timestamp}]\n\n{text}")
        self.latest_alarm_text = text
        self.append_csv_log()
        
    def show_error(self, msg: str):
        QMessageBox.critical(self, "Error", msg)


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
    #win.show()
    win.showMaximized()
    sys.exit(app.exec())
    
