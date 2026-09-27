# pyinstaller --clean --noconsole --onefile --icon=./lcd.ico --collect-all PySide6 --name TBC1000B_LCD_Modbus LCD_GUI_Pannel_Master_modbus_V6.py
import sys
import struct
import csv
import time

import serial
import serial.tools.list_ports

from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QMessageBox, QSplitter, QCheckBox, QTableWidget,
    QSizePolicy, QFileDialog, QTableWidgetItem, QStyledItemDelegate, QHeaderView,
    QScrollArea, QAbstractScrollArea
)

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent

from PySide6.QtGui import QFont, QColor, QPen


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


class MonitorScrollArea(QScrollArea):
    """Scroll the page over tables/text when their own scroll reaches an edge."""

    def setWidget(self, widget):
        super().setWidget(widget)
        for child in [widget, *widget.findChildren(QWidget)]:
            child.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel:
            delta = event.pixelDelta().y() or event.angleDelta().y()
            if delta:
                child = watched
                while child is not None and child is not self:
                    if isinstance(child, QAbstractScrollArea):
                        bar = child.verticalScrollBar()
                        if (delta > 0 and bar.value() > bar.minimum()) or (
                            delta < 0 and bar.value() < bar.maximum()
                        ):
                            return False
                    child = child.parentWidget()
                # Tables consume wheel events even when all rows are visible.
                # Move the page directly; redispatching the same Qt event can
                # cause recursive propagation through the nested viewports.
                bar = self.verticalScrollBar()
                pixels = event.pixelDelta().y()
                step = pixels or delta / 120 * bar.singleStep() * QApplication.wheelScrollLines()
                bar.setValue(bar.value() - round(step))
                event.accept()
                return True
        return super().eventFilter(watched, event)


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
class ModbusReadError(Exception):
    """Invalid, missing or exception response; never decode as measurements."""


class ModbusMaster:
    def __init__(self, port, baudrate=9600, slave_id=33):
        self.port = port
        self.baudrate = baudrate
        self.slave_id = slave_id
        self.client = None
        self.silent_interval = max(0.00175, 3.5 * 11 / baudrate)
        self.next_tx = 0.0
        self.recover = False

    def connect(self):
        self.client = serial.Serial(self.port, self.baudrate, timeout=0.02,
                                    write_timeout=0.5, bytesize=8, parity='N', stopbits=1)
        self.client.reset_input_buffer()
        return self.client.is_open

    def close(self):
        if self.client:
            self.client.close()

    def send_raw(self, frame, cancelled=lambda: False, trace=None):
        # One outstanding RTU request. After a failed request discard late bytes
        # before sending again (RTU responses do not contain the register address).
        while time.monotonic() < self.next_tx:
            if cancelled():
                return b''
            if self.recover:
                self.client.read(self.client.in_waiting or 1)
            else:
                time.sleep(min(0.005, max(0, self.next_tx - time.monotonic())))
        if cancelled():
            return b''
        self.client.reset_input_buffer()
        self.recover = False
        count = struct.unpack('>H', frame[4:6])[0]
        expected = 5 + 2 * count
        # Allow device processing time plus the response's wire time at this baud.
        response_timeout = 0.3 + (expected + len(frame)) * 11 / self.baudrate
        if trace:
            trace('TX', frame)
        if self.client.write(frame) != len(frame):
            raise serial.SerialException('Incomplete serial write')
        deadline = time.monotonic() + response_timeout
        received = bytearray()
        try:
            while time.monotonic() < deadline and not cancelled():
                received.extend(self.client.read(self.client.in_waiting or 1))
                # Search all offsets: noise or a corrupt header must not hide a
                # complete, valid frame received later in the same transaction.
                for offset in range(max(0, len(received) - 2)):
                    candidate = received[offset:]
                    if candidate[0] != self.slave_id:
                        continue
                    if candidate[1] == 0x83:
                        size = 5
                    elif candidate[1] == 0x03 and candidate[2] == count * 2:
                        size = expected
                    else:
                        continue
                    if len(candidate) < size:
                        continue
                    packet = bytes(candidate[:size])
                    if count_crc(packet[:-2]) != int.from_bytes(packet[-2:], 'little'):
                        continue
                    if trace:
                        trace('RX', packet)
                    if packet[1] == 0x83:
                        raise ModbusReadError(f'Modbus exception 0x{packet[2]:02X}')
                    return packet
                if len(received) > 1024:
                    del received[:-256]
            if cancelled():
                return b''
            if trace and received:
                trace('RX invalid', bytes(received))
            raise ModbusReadError('Response timeout / invalid address, length or CRC')
        except ModbusReadError:
            self.recover = True
            raise
        finally:
            self.next_tx = time.monotonic() + (response_timeout if self.recover else self.silent_interval)


class PollWorker(QThread):
    time_signal = Signal(str)
    cell_signal = Signal(int, str)
    battery_signal = Signal(int, str)
    log_signal = Signal(str)
    alarm_signal = Signal(str)
    alarm_count_signal = Signal(int)
    error_signal = Signal(str)
    barcode_signal = Signal(int, str)
    module_status_signal = Signal(int, bool)
    connected_signal = Signal()
    cycle_signal = Signal(float)
    discovery_signal = Signal(list)

    ALARMS = [
        ('Charge Over Voltage', 'Warning'), ('Charge Over Current', 'Warning'),
        ('Overdischarge', 'Warning'), ('Heavy Load', 'Warning'),
        ('Reverse Connection', 'Major'), ('Over Temperature', 'Minor'),
        ('Communication Fail', 'Minor'), ('Low Temperature', 'Minor'),
        ('High Temp Protection', 'Minor'), ('Low Temp Protection', 'Minor'),
        ('Overcharge Protection', 'Minor'), ('Overdischarge Protection', 'Minor'),
        ('Overcurrent Protection', 'Minor'),
    ]

    def __init__(self, port, baudrate, parent=None, module_count=10):
        super().__init__(parent)
        self.port, self.baudrate = port, baudrate
        self.auto_detect = module_count is None
        self.module_count = 10 if self.auto_detect else max(1, min(10, module_count))
        self.monitored_modules = set() if self.auto_detect else set(range(1, self.module_count + 1))
        self.master = None
        self.running = True
        self.valid_modules = set()
        self.barcodes = {}
        self.barcode_due = {}
        self.retry_due = {}
        self.alarm_due = {}
        self.module_alarms = {}
        self.alarm_received = {}
        self.global_alarms = None
        self.log_enabled = True

    def stop(self):
        self.running = False
        self.requestInterruption()

    def build_read_frame(self, start_addr, count):
        frame = struct.pack('>BBHH', 33, 3, start_addr, count)
        return frame + struct.pack('<H', count_crc(frame))

    def log_frame(self, title, data):
        if self.log_enabled:
            self.log_signal.emit(f'[{title}] ' + data.hex(' ').upper())

    def read_registers(self, addr, count):
        if not self.running:
            return None
        try:
            rx = self.master.send_raw(self.build_read_frame(addr, count),
                                      lambda: not self.running, self.log_frame)
            return struct.unpack(f'>{count}H', rx[3:-2]) if rx else None
        except ModbusReadError as exc:
            self.log_signal.emit(f'[READ FAIL 0x{addr:04X}, {count}] {exc}')
            return None

    def poll_time(self):
        regs = self.read_registers(0x2000, 6)
        if regs is not None:
            try:
                stamp = datetime(*regs)
                self.time_signal.emit(stamp.strftime('Time : %Y-%m-%d %H:%M:%S'))
            except ValueError:
                self.time_signal.emit('Time : invalid device time')
        else:
            self.time_signal.emit('Time : read failed')

    def poll_battery(self, n):
        # Last used register is SOH at +53; stay within the 64-register module.
        regs = self.read_registers(0xA731 + (n - 1) * 64, 54)
        if regs is None:
            self.valid_modules.discard(n)
            self.barcodes.pop(n, None)
            self.module_alarms[n] = None
            self.retry_due[n] = time.monotonic() + 3.0
            self.module_status_signal.emit(n, False)
            return False
        self.valid_modules.add(n)
        voltage = ((regs[0] << 16) | regs[1]) / 10
        current = (regs[2] << 16) | regs[3]
        if current & 0x80000000:
            current -= 0x100000000
        battery = (f'[Battery Module: {n}]\nBattery Voltage : {voltage:.1f} V\n'
                   f'Battery Current : {current / 10:.1f} A\nBattery SOC : {regs[8]} %\n'
                   f'Battery SOH : {regs[53]} %')
        cells = []
        for i in range(15):
            temp = regs[9 + i]
            if temp & 0x8000:
                temp -= 65536
            cells.append(f'Cell-{i+1:02d} Temp : {temp} degC / Volt : {regs[31+i]/10:.1f} V')
        self.module_status_signal.emit(n, True)
        self.cell_signal.emit(n, '\n'.join(cells))
        self.battery_signal.emit(n, battery)
        return True

    def poll_barcode(self, n):
        if n in self.barcodes or time.monotonic() < self.barcode_due.get(n, 0):
            return
        self.barcode_due[n] = time.monotonic() + 30
        regs = self.read_registers(0xC670 + (n - 1) * 32, 15)
        if regs is not None:
            barcode = struct.pack('>15H', *regs).rstrip(b'\x00').decode('ascii', errors='replace').strip()
            self.barcodes[n] = barcode
            self.barcode_signal.emit(n, barcode or '-')

    def poll_module_alarm(self, n):
        abnormal = self.read_registers(0x5036 + n - 1, 1)
        details = self.read_registers(0x8431 + (n - 1) * 64, 13)
        lines = []
        if abnormal is not None and abnormal[0] & 0xFF:
            status = abnormal[0] & 0xFF
            label = {1: 'Fault', 2: 'Protection', 3: 'Communication Fail'}.get(status, f'Unknown {status}')
            lines.append(f'Batt{n} Abnormal: {label} (Major)')
        if details is not None:
            for (name, severity), value in zip(self.ALARMS, details):
                if value & 0xFF == 1:
                    lines.append(f'Batt{n} {name} ({severity})')
        # Preserve positive alarms even when the other read failed.
        self.module_alarms[n] = (lines, abnormal is not None and details is not None)
        self.alarm_received[n] = time.monotonic()
        self.alarm_due[n] = time.monotonic() + 5

    def publish_alarms(self):
        lines = []
        unknown = []
        if self.global_alarms is None:
            unknown.append('Global alarm read failed / waiting')
        elif self.global_alarms[0] & 0xFF == 1:
            lines.append('Battery Missing (Major)')
        if self.auto_detect and not self.monitored_modules:
            unknown.append('No battery modules detected / reconnect to scan again')
        for n in sorted(self.monitored_modules):
            result = self.module_alarms.get(n)
            if result is not None:
                lines.extend(result[0])
                age = time.monotonic() - self.alarm_received.get(n, 0)
                if age > 15:
                    unknown.append(f'Batt{n}: alarm update delayed ({age:.0f}s)')
            if result is None or not result[1]:
                unknown.append(f'Batt{n}: alarm status unknown (communication / waiting)')
        count = len(lines)
        if not lines and not unknown:
            lines.append('All Modules Normal')
        self.alarm_signal.emit('\n'.join(lines + unknown))
        self.alarm_count_signal.emit(-1 if unknown else count)

    def discover_modules(self):
        for n in range(1, 11):
            if not self.running:
                return
            if self.poll_battery(n):
                self.monitored_modules.add(n)
        self.discovery_signal.emit(sorted(self.monitored_modules))

    def run(self):
        try:
            self.master = ModbusMaster(self.port, self.baudrate)
            self.master.connect()
            self.connected_signal.emit()
            if self.auto_detect:
                self.discover_modules()
            system_due = 0
            while self.running:
                started = time.monotonic()
                for n in sorted(self.monitored_modules):
                    if not self.running:
                        break
                    if time.monotonic() < self.retry_due.get(n, 0):
                        continue
                    self.poll_battery(n)
                # Secondary reads only after every battery has had a turn.
                # One module per cycle keeps alarm traffic from blocking all ten.
                if self.running and time.monotonic() >= system_due:
                    self.poll_time()
                    self.global_alarms = self.read_registers(0x5022, 1)
                    system_due = time.monotonic() + 5
                due = [n for n in sorted(self.valid_modules)
                       if time.monotonic() >= self.alarm_due.get(n, 0)]
                if self.running and due:
                    n = min(due, key=lambda x: self.alarm_due.get(x, 0))
                    self.poll_module_alarm(n)
                barcode_due = [n for n in sorted(self.valid_modules) if n not in self.barcodes
                               and time.monotonic() >= self.barcode_due.get(n, 0)]
                if self.running and barcode_due:
                    self.poll_barcode(barcode_due[0])
                if self.running:
                    self.publish_alarms()
                    self.cycle_signal.emit(time.monotonic() - started)
                for _ in range(10):
                    if not self.running:
                        break
                    self.msleep(10)
        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            if self.master:
                self.master.close()


# ============================
# GUI
# ============================
class TimeBatteryGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setFont(QFont('Malgun Gothic', 10))
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
        self.barcode_cache = {}
        self.received_at = {}
        self.module_active = {}
        self.data_valid = {}
        self.closing = False

        # 🔥 현재 화면에 표시중인 모듈
        self.current_displayed_module = 1

        self.build_ui()
        self.reset_monitor()
        self.update_button_styles()  # ← 초기 스타일 설정
        self.refresh_ports()
        self.age_timer = QTimer(self)
        self.age_timer.timeout.connect(self.refresh_ages)
        self.age_timer.start(1000)

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
        """단일 Connect 버튼 상태 업데이트"""

        if self.is_connected:
            # 🔴 연결됨 → Disconnect 상태
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText("Disconnect")

            self.btn_connect.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
                QPushButton:pressed {
                    background-color: #a71e2a;
                }
            """)

        else:
            # 🟢 연결 안됨 → Connect 상태
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText("Connect")

            self.btn_connect.setStyleSheet("""
                QPushButton {
                    background-color: #198754;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #157347;
                }
                QPushButton:pressed {
                    background-color: #146c43;
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
        if self.latest_alarm_count != 0:
            alarm = self.latest_alarm_text.replace("\n", " | ") or 'Unknown / waiting'
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
            self.chk_save_log.setChecked(False)
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
                    volt_str = parts[-2]  # "3.2"
                    
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
        self.latest_cell_text = text
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
        stamp = self.received_at.get(n)
        age = time.monotonic() - stamp if stamp is not None else 0
        self.lbl_cell_update_time.setText(f"Last received {age:.0f}s ago")

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
                self.set_module_btn_state(btn, 0)
                continue

            if i == n:
                self.set_module_btn_state(btn, 2)  # 선택 (녹색)
            else:
                self.set_module_btn_state(btn, 1)  # 활성 (진한 회색)

        self.lbl_barcode.setText('Barcode: ' + self.barcode_cache.get(n, '-'))
        self.table_modules.selectRow(n - 1)
        if n not in self.cell_cache:
            self.table_cell.clearContents()
        if n not in self.battery_cache:
            self.text_battery.setPlainText('Waiting for data')
        # 🔥 캐시 표시
        if n in self.cell_cache:
            self.update_cell_table(n, self.cell_cache[n])

        if n in self.battery_cache:
            self.update_battery(n, self.battery_cache[n])
            
    
    def on_connect_toggle(self):
        if self.is_connected:
            self.disconnect_port()
        else:
            self.connect_port()
        
    def build_ui(self):
        root_layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.setSpacing(10)

        # 🔥 COM Port
        self.cmb_port = QComboBox()
        self.cmb_port.setFixedWidth(100)

        # 🔥 Baudrate
        self.cmb_baud = QComboBox()
        self.cmb_baud.addItems([
            "9600", "19200", "38400", "57600", "115200"
        ])
        self.cmb_baud.setCurrentText("9600")
        self.cmb_baud.setFixedWidth(90)

        # 🔥 COM + Baud 그룹 (붙이기)
        port_group = QHBoxLayout()
        port_group.setSpacing(6)

        port_group.addWidget(QLabel("COM"))
        port_group.addWidget(self.cmb_port)

        port_group.addWidget(QLabel("Baud"))
        port_group.addWidget(self.cmb_baud)

        # 🔥 Connect 버튼 (먼저 생성)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setFixedWidth(110)
        self.btn_connect.clicked.connect(self.on_connect_toggle)

        # 🔥 레이아웃 구성 순서 중요
        top.addLayout(port_group)
        top.addSpacing(15)          # 살짝 여백
        top.addWidget(self.btn_connect)
        top.addWidget(QLabel('설치 모듈 수'))
        self.cmb_modules = QComboBox()
        self.cmb_modules.addItems(['Auto'] + [str(n) for n in range(1, 11)])
        self.cmb_modules.setCurrentText('Auto')
        self.cmb_modules.setMinimumContentsLength(4)
        self.cmb_modules.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.cmb_modules.setMinimumWidth(70)
        top.addWidget(self.cmb_modules)
        self.lbl_connection = QLabel('Disconnected')
        top.addWidget(self.lbl_connection)
        self.lbl_cycle = QLabel('Scan: -')
        top.addWidget(self.lbl_cycle)
        top.addStretch()

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

            # 🔥 초기 상태 = 비활성
            self.set_module_btn_state(btn, 0)

            btn.clicked.connect(lambda _, n=i: self.on_module_button_clicked(n))

            self.module_buttons[i] = btn
            sel.addWidget(btn)

        sel.addStretch()
        right_layout.addLayout(sel)
        self.table_modules = QTableWidget(10, 7)
        self.table_modules.setHorizontalHeaderLabels(
            ['모듈', '통신 상태', '전압 (V)', '전류 (A)', 'SOC (%)', 'SOH (%)', '수신 경과'])
        self.table_modules.verticalHeader().hide()
        # Reverse visual rows while retaining logical rows for module updates/clicks.
        module_header = self.table_modules.verticalHeader()
        for visual_row, logical_row in enumerate(reversed(range(self.table_modules.rowCount()))):
            module_header.moveSection(module_header.visualIndex(logical_row), visual_row)
        self.table_modules.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_modules.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_modules.setSelectionMode(QTableWidget.SingleSelection)
        self.table_modules.setAlternatingRowColors(True)
        self.table_modules.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_modules.verticalHeader().setDefaultSectionSize(26)
        self.table_modules.setMinimumHeight(295)
        self.table_modules.cellClicked.connect(lambda row, col: self.on_module_button_clicked(row + 1))
        right_layout.addWidget(self.table_modules)

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
        self.text_battery.setMaximumHeight(125)
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

        self.table_cell.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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

        self.table_cell.setMinimumHeight(185)
        self.table_cell.setMaximumHeight(185)

        right_layout.addWidget(self.table_cell)

        # =========================
        # Alarm Text
        # =========================
        left_layout.addLayout(alarm_header_layout)

        self.text_alarm = QTextEdit()
        self.text_alarm.setReadOnly(True)
        self.text_alarm.setStyleSheet("font-family:Courier New; font-size:9pt;")

        self.text_alarm.setMinimumHeight(200)
        left_layout.addWidget(self.text_alarm)
        left_layout.setStretchFactor(self.text_frame, 2)
        left_layout.setStretchFactor(self.text_alarm, 1)

        # =========================
        # Layout Finish
        # =========================
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setSizes([320, 1100])
        splitter.setStretchFactor(1, 2)

        # Keep the connection controls fixed while the monitor content scrolls.
        splitter.setMinimumHeight(max(780, splitter.minimumSizeHint().height()))
        self.monitor_scroll = MonitorScrollArea()
        self.monitor_scroll.setWidgetResizable(True)
        self.monitor_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.monitor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.monitor_scroll.setWidget(splitter)
        root_layout.addWidget(self.monitor_scroll)
        available = self.screen().availableGeometry()
        self.resize(min(1500, available.width()), min(900, available.height() - 80))
        root_layout.setStretch(0, 0) 
        root_layout.setStretch(1, 1)
        
        BUTTON_STYLE = """
        QPushButton {
            border-radius: 6px;
            padding: 5px;
            font-weight: 600;
            border: 1px solid #adb5bd;
            background-color: #f1f3f5;
            color: #868e96;
        }

        /* 비활성 */
        QPushButton[inactive="true"] {
            background-color: #e9ecef;
            color: #adb5bd;
            border: 1px solid #dee2e6;
        }

        /* 활성 (중간 회색) */
        QPushButton[active="true"] {
            background-color: #868e96;
            color: white;
            border: 1px solid #6c757d;
        }

        /* 선택 */
        QPushButton[selected="true"] {
            background-color: #2f9e44;
            color: white;
            border: 2px solid #2b8a3e;
        }

        /* hover */
        QPushButton:hover {
            border: 1px solid #495057;
        }
        """
        self.setStyleSheet(BUTTON_STYLE)
    
    def set_module_btn_state(self, btn, state):
        """
        state:
            0 = inactive (연결 전)
            1 = active (정상 통신)
            2 = selected (사용자 선택)
        """

        btn.setProperty("inactive", state == 0)
        btn.setProperty("active", state == 1)
        btn.setProperty("selected", state == 2)

        btn.style().unpolish(btn)
        btn.style().polish(btn)
        btn.update()
      
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

    def on_module_status(self, module, is_active):
        self.module_active[module] = is_active
        btn = self.module_buttons[module]
        btn.setEnabled(is_active or module in self.battery_cache)
        self.set_module_btn_state(btn, 2 if module == self.selected_module else (1 if is_active else 0))
        self.set_summary_cell(module, 1, '수신 정상' if is_active else '통신 실패')
        if not is_active:
            self.barcode_cache.pop(module, None)
            self.table_modules.item(module - 1, 1).setBackground(QColor('#f8d7da'))
            if module == self.current_displayed_module:
                self.lbl_barcode.setText('Barcode: - (communication failed)')
        self.refresh_ages()

    def on_modules_discovered(self, modules):
        for n in range(1, 11):
            self.table_modules.setRowHidden(n - 1, n not in modules)
            if n not in modules:
                self.set_summary_cell(n, 1, '미검출')
        numbers = ', '.join(map(str, modules)) or '-'
        self.lbl_connection.setText(f'Connected · Auto: {len(modules)}개 ({numbers})')
        if not modules:
            self.text_battery.setPlainText('검출된 모듈이 없습니다. 연결 상태를 확인한 후 다시 연결하세요.')

    def set_summary_cell(self, n, col, text):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)
        self.table_modules.setItem(n - 1, col, item)

    def reset_monitor(self):
        self.cell_cache.clear()
        self.battery_cache.clear()
        self.barcode_cache.clear()
        self.received_at.clear()
        self.module_active.clear()
        self.data_valid.clear()
        self.selected_module = None
        self.user_selected = False
        self.latest_battery_text = self.latest_cell_text = self.latest_alarm_text = ''
        self.latest_alarm_count = -1
        self.lbl_alarm_count.setText('(Unknown)')
        self.text_alarm.setPlainText('Alarm status unknown / waiting')
        self.text_battery.clear()
        self.table_cell.clearContents()
        self.lbl_barcode.setText('Barcode: -')
        self.lbl_time.setText('Time : -')
        self.lbl_current_module.setText('[Module -]')
        self.lbl_cell_update_time.setText('Waiting for data')
        for n, btn in self.module_buttons.items():
            btn.setEnabled(False)
            self.set_module_btn_state(btn, 0)
            for col in range(7):
                self.set_summary_cell(n, col, n if col == 0 else '-')
            auto = self.cmb_modules.currentText() == 'Auto'
            configured = auto or n <= int(self.cmb_modules.currentText())
            self.set_summary_cell(n, 1, '검색 대기' if auto else ('대기' if configured else '미설치'))
            self.table_modules.setRowHidden(n - 1, not configured)

    def refresh_ages(self):
        for n, stamp in self.received_at.items():
            age = time.monotonic() - stamp
            self.set_summary_cell(n, 6, f'{age:.0f}s')
            if not self.is_connected:
                state = '연결 해제 / 이전값'
            elif not self.module_active.get(n):
                state = '통신 실패 / 이전값'
            elif age > 10:
                state = '갱신 지연 / 이전값'
            elif not self.data_valid.get(n, True):
                state = '데이터 확인 필요'
            else:
                state = '수신 정상'
            self.set_summary_cell(n, 1, state)
            self.table_modules.item(n - 1, 1).setBackground(
                QColor('#e7f5ec' if state == '수신 정상' else '#fff3cd'))
            if n == self.current_displayed_module:
                self.lbl_cell_update_time.setText(f'{state} · {age:.0f}s ago')

    def connect_port(self):
        port = self.cmb_port.currentText()
        if not port:
            QMessageBox.warning(self, 'Connect', 'No COM port selected')
            return
        if self.worker is not None:
            return
        self.reset_monitor()
        self.worker = PollWorker(port, int(self.cmb_baud.currentText()),
                                 module_count=None if self.cmb_modules.currentText() == 'Auto'
                                 else int(self.cmb_modules.currentText()))
        self.worker.discovery_signal.connect(self.on_modules_discovered)
        self.worker.log_enabled = self.log_enabled
        self.worker.log_signal.connect(self.append_log)
        self.worker.time_signal.connect(self.update_time)
        self.worker.battery_signal.connect(self.on_battery_received)
        self.worker.cell_signal.connect(self.update_cell_table)
        self.worker.alarm_signal.connect(self.update_alarm)
        self.worker.error_signal.connect(self.show_error)
        self.worker.alarm_count_signal.connect(self.update_alarm_count)
        self.worker.barcode_signal.connect(self.update_barcode)
        self.worker.module_status_signal.connect(self.on_module_status)
        self.worker.connected_signal.connect(self.on_connected)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.cycle_signal.connect(lambda seconds: self.lbl_cycle.setText(f'Scan: {seconds:.2f}s'))
        self.btn_connect.setEnabled(False)
        self.lbl_connection.setText('Connecting...')
        for widget in (self.cmb_port, self.cmb_baud, self.cmb_modules):
            widget.setEnabled(False)
        self.worker.start()

    def on_connected(self):
        if not self.worker or not self.worker.running:
            return
        self.is_connected = True
        self.lbl_connection.setText('Connected · Auto 검색 중 (1~10)' if self.worker.auto_detect else 'Connected')
        self.update_button_styles()

    def on_worker_finished(self):
        worker = self.worker
        self.worker = None
        self.is_connected = False
        if worker:
            worker.deleteLater()
        self.lbl_connection.setText('Disconnected')
        self.lbl_time.setText('Time : disconnected')
        self.latest_alarm_count = -1
        self.lbl_alarm_count.setText('(Unknown)')
        self.text_alarm.setPlainText('Disconnected — previous alarm data may be outdated\n' + self.latest_alarm_text)
        self.update_button_styles()
        for widget in (self.cmb_port, self.cmb_baud, self.cmb_modules):
            widget.setEnabled(True)
        self.refresh_ages()
        if self.closing:
            self.close()

    def update_barcode(self, n, barcode_text):
        self.barcode_cache[n] = barcode_text
        if n == self.current_displayed_module:
            self.lbl_barcode.setText('Barcode: ' + barcode_text)

    def update_alarm_count(self, count: int):
        self.lbl_alarm_count.setText("(Unknown / partial)" if count < 0 else f"({count})")
        self.latest_alarm_count = count  # 이 라인 있어야 함
    
    def update_connect_button(self):
        if self.is_connected:
            self.btn_connect.setText("Disconnect")
            self.btn_connect.setStyleSheet(
                "background-color:#dc3545; color:white; font-weight:bold;"
            )
        else:
            self.btn_connect.setText("Connect")
            self.btn_connect.setStyleSheet("")
        
    def disconnect_port(self):
        if self.worker:
            self.btn_connect.setEnabled(False)
            self.lbl_connection.setText('Disconnecting...')
            self.worker.stop()

    def append_log(self, text: str):
        if not self.log_enabled:
            return
        self.text_frame.append(text)

    def update_time(self, text: str):
        self.lbl_time.setText(text)
        self.latest_time_text = text
        #self.append_csv_log()

    def update_battery(self, n, text):
        self.battery_cache[n] = text
        self.data_valid[n] = self.is_valid_module_data(text)
        values = [line.split(':', 1)[1].strip().split()[0] for line in text.splitlines()[1:]]
        for col, value in enumerate(values, 2):
            self.set_summary_cell(n, col, value)
        if not self.user_selected:
            self.on_module_button_clicked(n)
        if n == self.current_displayed_module:
            self.text_battery.setPlainText(text)
            self.latest_battery_text = text
        self.refresh_ages()

    def on_battery_received(self, n, text):
        self.received_at[n] = time.monotonic()
        self.update_battery(n, text)
        if self.chk_save_log.isChecked():
            previous = self.latest_battery_text, self.latest_cell_text
            self.latest_battery_text = text
            self.latest_cell_text = self.cell_cache.get(n, '')
            self.append_csv_log()
            self.latest_battery_text, self.latest_cell_text = previous

    def reset_battery_style(self):
        self.text_battery.setStyleSheet("")
        
        
    
    def update_alarm(self, text: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.text_alarm.setPlainText(f"[{timestamp}]\n\n{text}")
        self.latest_alarm_text = text

        
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
            self.closing = True
            self.disconnect_port()
            event.ignore()
            return
        event.accept()

    def on_toggle_log(self, checked: bool):
        # checked == True 이면 "멈춤" 상태
        self.log_enabled = not checked
        if self.worker:
            self.worker.log_enabled = self.log_enabled
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
    
