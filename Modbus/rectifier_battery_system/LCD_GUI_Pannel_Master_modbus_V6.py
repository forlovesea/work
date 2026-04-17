#pyinstaller --clean --noconsole --onefile --icon=./lcd.ico --collect-all PySide6 --name TBC1000B_LCD_Modbus LCD_GUI_Pannel_Master_modbus_V5.py
import sys
import struct
import csv

import serial
import serial.tools.list_ports

from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QMessageBox, QSplitter, QCheckBox, QTableWidget,
    QSizePolicy, QFileDialog, QTableWidgetItem, QStyledItemDelegate, QHeaderView
)

from PySide6.QtCore import Qt, QThread, Signal, QTimer

from PySide6.QtGui import QFont, QColor, QPen

from pymodbus.client.serial import ModbusSerialClient

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


class BlockSeparatorDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        # 🔥 3번째, 6번째 컬럼 오른쪽에 굵은 라인
        if index.column() in [2, 5]:
            pen = QPen(QColor("#495057"))
            pen.setWidth(3)
            painter.setPen(pen)

            rect = option.rect
            painter.drawLine(rect.topRight(), rect.bottomRight())
            
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
    time_signal = Signal(str)         # 시간 문자열
    cell_signal = Signal(int, str)   # (module_n, text)
    battery_signal = Signal(int, str)
    log_signal = Signal(str)          # TX/RX 로그 문자열
    alarm_signal = Signal(str)
    alarm_count_signal = Signal(int)
    error_signal = Signal(str)        # 에러 메시지
    barcode_signal = Signal(str)
    module_signal = Signal(int)

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

        try:
            # 🔥 1. RX 버퍼 강제 클리어 (핵심)
            if self.master and self.master.client:
                self.master.client.socket.reset_input_buffer()
                self.master.client.socket.reset_output_buffer()
        except Exception:
            pass

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

        print("Polling module:", n)
        base = (n - 1) * 64

        # 🔥 1. 한번에 블록 읽기 (핵심)
        start = 0xA731 + base
        count = 80

        frame = self.build_read_frame(start, count)
        rx = self.send_and_recv(frame)

        if not rx or len(rx) < 3 + count * 2 + 2:
            return

        data = rx[3:3 + count * 2]
        regs = struct.unpack(f">{count}H", data)

        # ===== 변환 함수 =====
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

        # ===== 기본 정보 =====
        text_batt_lines.append(f"[Battery Module: {n}]")

        voltage = u32(0) / 10
        current = s32(2) / 10
        soc = u16(8)
        soh = u16((0xA766 - 0xA731))

        text_batt_lines.append(f"Battery Voltage : {voltage:.1f} V")
        text_batt_lines.append(f"Battery Current : {current:.1f} A")
        text_batt_lines.append(f"Battery SOC : {soc} %")
        text_batt_lines.append(f"Battery SOH : {soh} %")

        # ===== 온도 (15개 지원) =====
        temps = []
        for i in range(15):
            offset = (0xA73A + i) - 0xA731
            temps.append(s16(offset))

        # ===== 전압 (15개 지원) =====
        volts = []
        for i in range(15):
            offset = (0xA750 + i) - 0xA731
            volts.append(u16(offset) / 10)

        # ===== 출력 =====
        for i in range(15):
            text_cell_lines.append(
                f"Cell-{i+1:02d} Temp : {temps[i]} degC / Volt : {volts[i]:.1f} V"
            )

        # ===== Barcode (별도 1회만 읽기 유지) =====
        barcode_base = 0xC670 + (n - 1) * 32
        barcode = self.read_string(barcode_base, 15)
        barcode = barcode.strip('\x00').strip()

        self.barcode_signal.emit(f"Barcode: {barcode}")
        
        # 🔥 데이터 최소 검증 후 emit
        if voltage <= 0 or voltage > 1000:
            return

        if soc < 0 or soc > 100:
            return
        self.cell_signal.emit(n, "\n".join(text_cell_lines))
        self.battery_signal.emit(n, "\n".join(text_batt_lines))
        self.module_signal.emit(n)
    # ---------- Alarm ----------
    def poll_alarm(self, n: int):
        lines = []
        alarm_count = 0
        fmt = "{:<35} {:<12} {:<15} {:<10}"
        
        # 헤더
        lines.append(fmt.format("ALARM ITEM", "ADDRESS", "STATUS", "VALUE"))
        if alarm_count < 100:  # 제한
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

                # 🔥 반드시 1 → 10 순서
                for n in range(1, 11):
                    self.msleep(50)
                    self.poll_battery(n)
                    self.msleep(50)
                    self.poll_alarm(n)

                # 🔥 전체 루프 간격
                self.msleep(500)   # 👉 전체 refresh 주기

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
        
        self.current_displayed_module = None
        self.user_selected = False

        #--- 로그 저장 관련 상태 ---
        self.save_log_enabled = False
        self.log_file_path:str|None = None
        self.latest_battery_text = ""
        self.latest_cell_text = ""
        self.latest_alarm_text = ""
        self.latest_time_text = ""
        self.latest_alarm_count = 0  # 초기화 추가
        self.pending_module_change = False  # 대기중인 모듈 변경 플래그
        
        # 🔥 모듈별 데이터 캐시
        self.cell_cache = {}
        self.battery_cache = {}

        # 🔥 현재 화면에 표시중인 모듈
        self.current_displayed_module = 1

        self.build_ui()
        self.update_button_styles()  # ← 초기 스타일 설정
        self.refresh_ports()

    def is_valid_module_data(self, text: str) -> bool:
        try:
            soc = None
            soh = None
            volts = []

            lines = text.split("\n")

            for line in lines:
                if "SOC" in line:
                    soc = int(line.split(":")[1].strip().replace("%", ""))
                elif "SOH" in line:
                    soh = int(line.split(":")[1].strip().replace("%", ""))
                elif "Cell-" in line and "Volt" in line:
                    parts = line.split()
                    volt = float(parts[-2])
                    volts.append(volt)

            # ===== 조건 1: SOC / SOH =====
            if soc is None or soh is None:
                return False

            if not (0 <= soc <= 100):
                return False

            if not (0 <= soh <= 100):
                return False

            # ===== 조건 2: Cell Voltage =====
            for v in volts:
                if v <= 0 or v > 5.0:   # 🔥 기준 (LiFePO4 기준 여유 포함)
                    return False

            return True

        except Exception:
            return False
    
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

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    
    def reset_cell_time_style(self):
        self.lbl_cell_update_time.setStyleSheet("""
            font-size: 13px;
            color: #6c757d;
            margin-left: 8px;
        """)
    
    def update_cell_table(self, n, text):
        # =========================
        # 🔥 1. 캐시 저장 (핵심)
        # =========================
        self.cell_cache[n] = text

        # =========================
        # 🔥 2. 사용자 선택 전 표시 금지
        # =========================
        if not self.user_selected:
            return

        # =========================
        # 🔥 3. 선택된 모듈만 표시
        # =========================
        if n != self.current_displayed_module:
            return

        # =========================
        # 🔥 4. 데이터 파싱
        # =========================
        lines = text.split("\n")
        data = []

        for line in lines:
            if not line.strip():
                continue

            try:
                parts = line.split()

                cell_no = int(parts[0].split("-")[1])
                temp = int(parts[3])
                volt = float(parts[-2])

                data.append((cell_no, volt, temp))

            except Exception:
                continue  # 안전 처리

        # =========================
        # 🔥 5. 테이블 초기화
        # =========================
        self.table_cell.clearContents()

        # =========================
        # 🔥 6. 테이블 채우기 (5x3 블럭)
        # =========================
        for i, (cell_no, volt, temp) in enumerate(data):

            if i >= 15:
                break

            row = i % 5
            block = i // 5
            col_base = block * 3

            # ===== Cell 번호 =====
            item_cell = QTableWidgetItem(f"{cell_no:02d}")
            item_cell.setTextAlignment(Qt.AlignCenter)
            item_cell.setBackground(QColor("#e7f1ff"))
            item_cell.setForeground(QColor("#0d6efd"))
            item_cell.setFont(QFont("Arial", 10, QFont.Bold))

            # ===== Volt =====
            item_volt = QTableWidgetItem(f"{volt:.2f}")
            item_volt.setTextAlignment(Qt.AlignCenter)

            if volt < 3.0:
                item_volt.setBackground(QColor("#f8d7da"))
            elif volt > 3.6:
                item_volt.setBackground(QColor("#fff3cd"))

            # ===== Temp =====
            item_temp = QTableWidgetItem(str(temp))
            item_temp.setTextAlignment(Qt.AlignCenter)

            if temp > 45:
                item_temp.setBackground(QColor("#f8d7da"))
            elif temp > 35:
                item_temp.setBackground(QColor("#fff3cd"))

            # ===== 적용 =====
            self.table_cell.setItem(row, col_base + 0, item_cell)
            self.table_cell.setItem(row, col_base + 1, item_volt)
            self.table_cell.setItem(row, col_base + 2, item_temp)

        # =========================
        # 🔥 7. Module 라벨 업데이트 (중요)
        # =========================
        #self.lbl_current_module.setText(f"[Module-{self.current_displayed_module}]")

        # =========================
        # 🔥 8. 업데이트 시간 표시
        # =========================
        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_cell_update_time.setText(f"Updated {now}")

        # =========================
        # 🔥 9. 갱신 강조 효과
        # =========================
        self.lbl_cell_update_time.setStyleSheet("""
            font-size: 13px;
            color: red;
            font-weight: bold;
            margin-left: 8px;
        """)

        QTimer.singleShot(500, self.reset_cell_time_style)
        
    
    def on_module_button_clicked(self, n):

        self.user_selected = True
        self.selected_module = n
        self.current_displayed_module = n

        self.lbl_current_module.setText(f"[Module-{n}]")

        # 🔥 버튼 색상 재정리 (핵심)
        for i, btn in self.module_buttons.items():

            if not btn.isEnabled():
                continue   # ⭐ disabled는 절대 건드리지 않음

            if i == n:
                btn.setStyleSheet("""
                    background-color: #28a745;
                    color: white;
                    font-weight: bold;
                    border-radius: 5px;
                """)
            else:
                btn.setStyleSheet("""
                    background-color: #0d6efd;
                    color: white;
                    border-radius: 5px;
                """)

        # 🔥 캐시 표시
        if n in self.cell_cache:
            self.update_cell_table(n, self.cell_cache[n])

        if n in self.battery_cache:
            self.update_battery(n, self.battery_cache[n])
            
        
    def build_ui(self):
        root_layout = QVBoxLayout(self)

        # =========================
        # Top: COM control
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
        # Splitter
        # =========================
        splitter = QSplitter(Qt.Horizontal)

        # =========================
        # LEFT (로그)
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

        # Alarm header
        alarm_header_layout = QHBoxLayout()

        self.lbl_alarm_status = QLabel("Alarm Status")
        self.lbl_alarm_status.setStyleSheet("font-weight:bold;")

        self.lbl_alarm_count = QLabel("(0)")
        self.lbl_alarm_count.setStyleSheet("color:red; font-weight:bold;")

        alarm_header_layout.addWidget(self.lbl_alarm_status)
        alarm_header_layout.addWidget(self.lbl_alarm_count)
        alarm_header_layout.addStretch()

        left_layout.addLayout(btn_bar)
        left_layout.addWidget(QLabel("TX / RX Frame"))
        left_layout.addWidget(self.text_frame)

        # =========================
        # RIGHT
        # =========================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # ===== Time =====
        time_bar = QHBoxLayout()

        time_bar.addWidget(QLabel("Read Time"))

        self.lbl_time = QLabel("Time : -")
        self.lbl_time.setStyleSheet("font-size:18px; font-weight:bold;")
        time_bar.addWidget(self.lbl_time)

        self.chk_save_log = QCheckBox("Save Log")
        self.chk_save_log.stateChanged.connect(self.on_save_log_changed)
        time_bar.addWidget(self.chk_save_log)

        self.btn_log_path = QPushButton("Log Path")
        self.btn_log_path.setEnabled(False)
        self.btn_log_path.clicked.connect(self.on_select_log_path)
        time_bar.addWidget(self.btn_log_path)

        time_bar.addStretch()
        right_layout.addLayout(time_bar)

        # =========================
        # 🔥 모듈 버튼 영역
        # =========================
        sel = QHBoxLayout()

        self.module_buttons = {}
        self.selected_module = None
        self.current_displayed_module = 1
        self.user_selected = False

        sel.addWidget(QLabel("축전지 모듈 선택"))

        for i in range(1, 11):
            btn = QPushButton(f"{i}")
            btn.setFixedSize(40, 30)
            btn.setEnabled(False)

            btn.setStyleSheet("""
                QPushButton {
                    background-color: #dee2e6;
                    border: 1px solid #adb5bd;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #ced4da;
                }
            """)

            btn.clicked.connect(lambda _, n=i: self.on_module_button_clicked(n))

            self.module_buttons[i] = btn
            sel.addWidget(btn)

        sel.addStretch()
        right_layout.addLayout(sel)

        # =========================
        # Barcode
        # =========================
        self.lbl_barcode = QLabel("Barcode: -")
        self.lbl_barcode.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #dc3545;
            background-color: #ffebee;
            padding: 6px;
            border-radius: 5px;
        """)
        right_layout.addWidget(self.lbl_barcode)

        # =========================
        # Battery Info
        # =========================
        right_layout.addWidget(QLabel("Battery Information"))

        self.text_battery = QTextEdit()
        self.text_battery.setReadOnly(True)
        right_layout.addWidget(self.text_battery)

        # =========================
        # Cell Header
        # =========================
        cell_header_layout = QHBoxLayout()

        cell_title = QLabel("Cell Information")
        cell_title.setStyleSheet("font-weight:bold;")

        self.lbl_current_module = QLabel("[Module -]")
        self.lbl_current_module.setStyleSheet("""
            font-weight:bold;
            background-color:#fff3cd;
            padding:4px;
            border-radius:5px;
        """)

        self.lbl_cell_update_time = QLabel("Updated --:--:--")
        self.lbl_cell_update_time.setStyleSheet("color:gray;")

        cell_header_layout.addWidget(cell_title)
        cell_header_layout.addWidget(self.lbl_current_module)
        cell_header_layout.addWidget(self.lbl_cell_update_time)
        cell_header_layout.addStretch()

        right_layout.addLayout(cell_header_layout)

        # =========================
        # 🔥 Cell Table
        # =========================
        self.table_cell = QTableWidget(5, 9)

        self.table_cell.setHorizontalHeaderLabels([
            "Cell", "Volt", "Temp",
            "Cell", "Volt", "Temp",
            "Cell", "Volt", "Temp"
        ])

        self.table_cell.verticalHeader().setVisible(False)
        self.table_cell.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_cell.setSelectionMode(QTableWidget.NoSelection)
        self.table_cell.setFocusPolicy(Qt.NoFocus)

        # 크기 고정
        for i, w in enumerate([50, 70, 70] * 3):
            self.table_cell.setColumnWidth(i, w)

        for i in range(5):
            self.table_cell.setRowHeight(i, 32)

        self.table_cell.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table_cell.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        self.table_cell.setStyleSheet("""
            QTableWidget {
                background-color: #f8f9fa;
                gridline-color: #adb5bd;
                font-size: 11pt;
            }
            QTableWidget::item {
                padding: 4px;
                text-align: center;
            }
        """)

        self.table_cell.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #343a40;
                color: white;
                font-weight: bold;
            }
        """)

        self.table_cell.setItemDelegate(BlockSeparatorDelegate(self.table_cell))

        self.table_cell.setMinimumHeight(220)
        self.table_cell.setMaximumHeight(220)

        right_layout.addWidget(self.table_cell)

        # =========================
        # Alarm Text
        # =========================
        right_layout.addLayout(alarm_header_layout)

        self.text_alarm = QTextEdit()
        self.text_alarm.setReadOnly(True)
        self.text_alarm.setStyleSheet("font-family:Courier New; font-size:9pt;")

        right_layout.addWidget(self.text_alarm)

        # =========================
        # Layout Finish
        # =========================
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        root_layout.addWidget(splitter)
        self.resize(1500, 750)
        root_layout.setStretch(0, 0) 
        root_layout.setStretch(1, 1)
         
    def reset_module_style(self):
        self.lbl_current_module.setStyleSheet("""
            font-size: 14px; 
            font-weight: bold; 
            color: #d63384; 
            background-color: #fff3cd; 
            padding: 4px 8px; 
            border: 2px solid #ffc107; 
            border-radius: 5px;
        """)
        
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
        self.worker.cell_signal.connect(self.update_cell_table)
        self.worker.alarm_signal.connect(self.update_alarm) 
        self.worker.error_signal.connect(self.show_error)
        self.worker.alarm_count_signal.connect(self.update_alarm_count)
        self.worker.barcode_signal.connect(self.update_barcode)
        #self.worker.module_signal.connect(self.update_module_label)
        
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
         # 🔥 추가 (로그 너무 많을 때 샘플링)
        if len(text) > 200:   # 너무 긴 프레임 컷
            text = text[:200] + "..."
            
        self.text_frame.append(text)

    def update_time(self, text: str):
        self.lbl_time.setText(text)
        self.latest_time_text = text
        #self.append_csv_log()

    def update_battery(self, n, text: str):

        # =========================
        # 🔥 0. 데이터 유효성 검사
        # =========================
        is_valid = self.is_valid_module_data(text)

        if n in self.module_buttons:
            btn = self.module_buttons[n]

            if is_valid:
                btn.setEnabled(True)

                # 🔥 선택 안된 경우만 파란색
                if not self.user_selected or self.selected_module != n:
                    btn.setStyleSheet("""
                        background-color: #0d6efd;
                        color: white;
                        border-radius: 5px;
                    """)
            else:
                # 🔥 핵심: invalid → 무조건 회색 유지
                btn.setEnabled(False)
                btn.setStyleSheet("""
                    background-color: #dee2e6;
                    border: 1px solid #adb5bd;
                    border-radius: 5px;
                """)

                return   # 🔥 중요: 여기서 끝내야 아래 코드 실행 안됨

        # =========================
        # 🔥 1. 캐시 저장 (핵심)
        # =========================
        self.battery_cache[n] = text

        # =========================
        # 🔥 2. 사용자 선택 전 표시 금지
        # =========================
        if not self.user_selected:
            return

        # =========================
        # 🔥 3. 선택된 모듈만 표시
        # =========================
        if n != self.current_displayed_module:
            return

        # =========================
        # 🔥 4. UI 업데이트
        # =========================
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.text_battery.setPlainText(f"[{timestamp}]\n\n{text}")
        self.latest_battery_text = text

        # =========================
        # 🔥 6. Module 라벨 동기화
        # =========================
        #self.lbl_current_module.setText(f"[Module-{self.current_displayed_module}]")

        # =========================
        # 🔥 7. 갱신 강조 효과
        # =========================
        self.text_battery.setStyleSheet("""
            border: 2px solid red;
            background-color: #fff5f5;
        """)

        QTimer.singleShot(300, self.reset_battery_style)

        # =========================
        # 🔥 8. CSV 저장 (옵션)
        # =========================
        if self.chk_save_log.isChecked():
            self.append_csv_log(n, text)

    def reset_battery_style(self):
        self.text_battery.setStyleSheet("")
        
        
    
    def update_alarm(self, text: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.text_alarm.setPlainText(f"[{timestamp}]\n\n{text}")
        self.latest_alarm_text = text
        self.append_csv_log()

        
    def show_error(self, msg: str):
        QMessageBox.critical(self, "Error", msg)

    def on_batt_index_changed(self, idx: int):
        n = idx + 1

        self.current_displayed_module = n

        # 🔥 UI 즉시 변경
        self.lbl_current_module.setText(f"[Module-{n}]")

        # 🔥 worker에 요청
        if self.worker:
            self.worker.selected_n = n

        # =========================
        # 🔥 핵심: 해당 모듈의 "이전 데이터" 즉시 표시
        # =========================
        if n in self.cell_cache:
            self.update_cell_table(n, self.cell_cache[n])
        else:
            self.table_cell.clearContents()  # 또는 "No Data"

        if n in self.battery_cache:
            self.update_battery(n, self.battery_cache[n])
        else:
            self.text_battery.setText("No Data")



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
    
