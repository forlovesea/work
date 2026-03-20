"""
*실행프로그램 명령어
 cd D:\proj\GIT_HUB\work\RMS_Server
 pyinstaller --clean --noconsole --onefile --icon=./#2_battery.ico --collect-all PySide6 --name TBC1000B_감시프로그램_V0.0.1 TBC1000B_감시프로그램_V0.0.4.py
*최적화 실행 파일 옵션
pyinstaller --noconfirm --onefile --icon=./#2_battery.ico --windowed --add-data "install_battery.png;." --clean --strip --noupx --exclude-module tkinter --exclude-module matplotlib --exclude-module numpy --exclude-module pandas --exclude-module scipy --exclude-module IPython --exclude-module jupyter --exclude-module notebook --exclude-module test --exclude-module unittest --exclude-module email --exclude-module http TBC1000B_감시프로그램_V0.1.2.py
Read : sktlfp48r
Write : sktlfp48w
Trap : sktlfp48r
"""
#
#
#전송운용팀에서 IP 추가할당을 더 받아서, 허브설치 후 아래와 같이 IP 설정해놨습니다. 
#UNA : 60.22.64.219
#Pentech : 60.22.64.220

import sys
import os
import re
import time
import subprocess
import platform
import threading
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import asyncore
import psutil

from datetime import datetime
from collections import deque
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QRadioButton, QLineEdit,
    QDialog, QDialogButtonBox, QListWidget,
    QFormLayout, QMessageBox, QSizePolicy, QHeaderView,
    QComboBox
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSettings
from PySide6.QtGui import QColor, QFont, QPixmap, QFontMetrics
from pysnmp.hlapi import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity,
    getCmd, bulkCmd
)
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv

# =======================================================================================================================
# Application Info
# =======================================================================================================================
APP_NAME = "TBC1000B-NDA1 Battery Monitoring System(Base SNMPv2)"

VERSION_MAJOR = 0
VERSION_MINOR = 1
VERSION_PATCH = 3

APP_VERSION = f"v{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
#########################################################################################################################

MAX_TRAP_LOG = 1000
TRAP_QUEUE_SIZE = 2000


DEBUG_FLAGS = {
    "SNMP": False,
    "MODULE": False,
    "TRAP": False,
    "ALARM": False,
    "DEBUG": False
}

#DEBUG_FLAGS = {
#    "SNMP": True,
#    "MODULE": True,
#    "TRAP": True,
#    "ALARM": True
#}

LABEL_BG = QColor("#E7F1FF")

FAULT_ALARMS = [
    "Board hardware fault",
    "Cell 1 Fault",
    "Cell 2 Fault",
    "Cell 3 Fault",
    "Cell 4 Fault",
    "Cell 5 Fault",
    "Cell 6 Fault",
    "Cell 7 Fault",
    "Cell 8 Fault",
    "Cell 9 Fault",
    "Cell 10 Fault",
    "Cell 11 Fault",
    "Cell 12 Fault",
    "Cell 13 Fault",
    "Cell 14 Fault",
    "Cell 15 Fault"
]

def dprint(flag, *args):
    if DEBUG_FLAGS.get(flag, False):
        print(f"[{flag}]", *args)
        
def log(msg):
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{now}] {msg}")
    
# ======================
# Ping 기능
# ======================
def ping_host(ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        result = subprocess.run(["ping", param, "1", ip], capture_output=True, text=True, timeout=2)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False

def apply_label_style(item: QTableWidgetItem):
    item.setBackground(LABEL_BG)
    item.setFont(QFont("", weight=QFont.Bold))
    item.setTextAlignment(Qt.AlignCenter)

def apply_value_style(item: QTableWidgetItem, status: str):
    item.setTextAlignment(Qt.AlignCenter)
    if "차단" in status:
        item.setBackground(QColor("#FF6B6B"))
        item.setForeground(QColor("white"))
    elif "경보" in status:
        item.setBackground(QColor("#FFA94D"))
    elif "정상" in status:
        item.setBackground(QColor("#B2F2BB"))


def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS  # PyInstaller 실행 시 임시 폴더
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        return os.path.join(base_path, relative_path)
    
class ModuleOrderDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent_ui = parent

        self.setWindowTitle("설치 모듈 순서 설정")
        self.resize(650, 420)   # 가로 확장

        layout = QVBoxLayout(self)

        # ==============================
        # 상단 메인 영역 (좌: 이미지 / 우: 설정)
        # ==============================
        content_layout = QHBoxLayout()
        layout.addLayout(content_layout)

        # ==============================
        # 1️⃣ 이미지 영역 (왼쪽)
        # ==============================
        self.img_label = QLabel()
        #script_dir = os.path.dirname(os.path.abspath(__file__))
        #img_path = os.path.join(script_dir, "install_battery.png")
        img_path = resource_path("install_battery.png")
        
        # 🔥 중요: 자동 확대 방지
        self.img_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        if os.path.exists(img_path):
            self.pixmap_origin = QPixmap(img_path)
            
            # 🔍 디버깅 (추천)
            if self.pixmap_origin.isNull():
                self.img_label.setText("이미지 로드 실패")
            else:
                self.img_label.setPixmap(self.pixmap_origin)
        else:
            self.img_label.setText("이미지 없음")
        
        self.img_label.setAlignment(Qt.AlignTop | Qt.AlignCenter)
        content_layout.setAlignment(Qt.AlignTop)
        
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.img_label)
        left_layout.addStretch()

        content_layout.addLayout(left_layout, 0)        

        # ==============================
        # 2️⃣ 설정 UI 영역 (오른쪽)
        # ==============================
        self.right_widget = QWidget()
        right_layout = QVBoxLayout(self.right_widget)

        # 🔽 테이블 전체를 아래로 내리는 핵심 코드
        right_layout.addSpacing(38)   # 10~40 사이로 조절 가능
        self.combo_boxes = []
        #self.used_modules = set()

        for pos in range(10, 0, -1):

            row_layout = QHBoxLayout()
            row_layout.setSpacing(5)
            
            label = QLabel(f"{pos:02d}번 위치")
            label.setFixedWidth(80)
            
            combo = QComboBox()
            combo.addItem("-", None)

            # 🔽 정렬 적용
            for m_no in sorted(parent.module_map.keys()):
                info = parent.module_map[m_no]
                
                saved_barcode = parent.module_barcodes.get(str(m_no), "")
                device_barcode = info.get("barcode", "")
                
                barcode = saved_barcode if saved_barcode else (device_barcode if device_barcode else "-")

                # 🔽 드롭다운 리스트는 device_barcode 기준
                device_text = f"모듈{m_no:02d}-{device_barcode if device_barcode else '-'}"
                combo.addItem(device_text, m_no)
                
                saved_order = parent.settings.value("module_order", [])

                if saved_order and len(saved_order) >= pos:
                    saved_module = saved_order[pos - 1]

                    try:
                        saved_module = int(saved_module)
                    except:
                        pass

                    for i in range(combo.count()):
                        if combo.itemData(i) == saved_module:

                            combo.setCurrentIndex(i)

                            # 🔥 여기 핵심 (표시는 saved_barcode로 덮어쓰기)
                            saved_barcode = parent.module_barcodes.get(str(saved_module), "")
                            display_barcode = saved_barcode if saved_barcode else "-"

                            combo.setItemText(i, f"모듈{saved_module:02d}-{display_barcode}")

                            break
                
            # 🔥 추가
            combo.setMaxVisibleItems(11)
            combo.currentIndexChanged.connect(self.check_duplicate)

            row_layout.addWidget(label)
            row_layout.addWidget(combo)

            right_layout.addLayout(row_layout)

            self.combo_boxes.append(combo)

        right_layout.addStretch()

        content_layout.addWidget(self.right_widget, 1)

        # ==============================
        # 저장 버튼
        # ==============================
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_order)
        #right_layout.addWidget(btn_save, alignment=Qt.AlignCenter)
        layout.addWidget(btn_save)

    # ==============================
    # 🔥 핵심: 이미지 높이 자동 맞춤
    # ==============================
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_image()

    def adjust_image(self):

        if not hasattr(self, "pixmap_origin"):
            return

        right_h = self.right_widget.height()
        right_w = self.right_widget.width()

        if right_h <= 0 or right_w <= 0:
            return

        # 🔥 50% 기준
        target_h = int(right_h * 0.5)
        target_w = int(right_w * 0.6)

        scaled = self.pixmap_origin.scaled(
            target_w,
            target_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.img_label.setPixmap(scaled)

        # 🔥 QLabel 크기 고정 (중요)
        self.img_label.setFixedSize(scaled.size())
            
    def showEvent(self, event):
        super().showEvent(event)
        self.adjust_image()


    def check_duplicate(self):

        used = []

        for combo in self.combo_boxes:

            module_no = combo.currentData()

            if module_no and module_no in used:
                QMessageBox.warning(self,"중복 선택","같은 모듈을 두 번 선택할 수 없습니다.")
                combo.setCurrentIndex(0)
                return

            if module_no:
                used.append(module_no)


    def save_order(self):

        order = []

        for combo in self.combo_boxes:

            module_no = combo.currentData()

            order.append(module_no)

        self.parent_ui.save_module_order(order)

        self.accept()

class PingThread(QThread):
    ping_result = Signal(bool, str)
    def __init__(self, ip):
        super().__init__()
        self.ip = ip
        self.running = True
        
    def run(self):
        while self.running:
            success = ping_host(self.ip)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.ping_result.emit(success, current_time)
            self.msleep(1000)
            
    def stop(self):
        self.running = False

        if hasattr(self, "snmpEngine") and self.snmpEngine is not None:
            try:
                self.snmpEngine.transportDispatcher.jobFinished(1)
            except:
                pass

            try:
                self.snmpEngine.transportDispatcher.closeDispatcher()
            except:
                pass

        self.quit()
        self.wait(1000)


# ======================
# Module 상세정보 다이얼로그
# ======================
class ModuleDetailDialog(QDialog):
    def __init__(self, module_no, parent=None):
        super().__init__(parent)

        self.module_no = module_no
        self.parent_ui = parent

        self.setWindowTitle(f"모듈 #{module_no:02d} 상세정보")
        self.setModal(True)
        self.resize(520, 450)

        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(5,5,5,5)
        # ======================================================
        # 1️⃣ module_no → equip_id 매핑
        # ======================================================
        module_info = self.parent_ui.module_map.get(module_no)

        if module_info:
            equip_id = module_info["equip_id"]
            swver_txt = module_info["swver"]
            model_txt = module_info["model"]
            barcode_txt = module_info["barcode"]
            
        if not equip_id:
            QMessageBox.warning(self, "데이터 없음", "해당 모듈의 Equip ID를 찾을 수 없습니다.")
            return       

        module_data = self.parent_ui.module_data.get(equip_id)
            
        if not module_data:
            QMessageBox.warning(self, "데이터 없음", "SNMP 데이터가 아직 수신되지 않았습니다.")
            return

        # ======================================================
        # 2️⃣ 상단 정보 영역
        # ======================================================
        info_group = QGroupBox(f"축전지 모듈 #{module_no:02d}")
        #info_layout = QHBoxLayout(info_group) # 가로
        info_layout = QVBoxLayout(info_group)  # 세로

        status_map = {
            0: "Online",
            1: "Offline",
            2: "Sleep",
            3: "Disconnect",
            4: "Charge",
            5: "Discharge",
            6: "Standby",
            255: "Unknown"
        }

        status = module_data.get("status")
        status_text = status_map.get(status, "Unknown")
        volt = module_data.get("volt")        
        soc = module_data.get("soc")
        soh = module_data.get("soh")

        label_voltage = QLabel(f"1.전압: {volt:.1f} V" if volt is not None else "1.전압: -")
        label_status = QLabel(f"2.상태: {status_text}" if status is not None else "2.: -")
        label_soc = QLabel(f"3.SOC: {soc} %" if soc is not None else "3.SOC: -")
        label_soh = QLabel(f"4.SOH: {soh} %" if soh is not None else "4.SOH: -")        
        if barcode_txt is not None:
            label_barcode = QLabel(f'5.바코드: <span style="color:red;">{barcode_txt}</span>')
        else:
            label_barcode = QLabel('5.바코드: <span style="color:red;">-</span>')
        # 🔹 마우스 드래그 선택 + 복사 가능
        label_barcode.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label_cell_legend = QLabel(
            '※ 셀 전압: '
            '<span style="background-color:#D3F9D8;"> 최고 </span> '
            '<span style="background-color:#FFE3E3;"> 최저 </span> '
            '&nbsp;&nbsp;&nbsp;'
            '※ 온도: '
            '<span style="background-color:#FFF9C4;"> 최고 </span> '
            '<span style="background-color:#FF4D4D; color:white;"> 60℃ 이상 </span>'
        )
        info_layout.addWidget(label_voltage)
        info_layout.addWidget(label_status)
        info_layout.addWidget(label_soc)
        info_layout.addWidget(label_soh)
        info_layout.addWidget(label_barcode)
        info_layout.addWidget(label_cell_legend)
        #info_layout.addStretch()

        layout.addWidget(info_group)

        # ======================================================
        # 3️⃣ Cell Table
        # ======================================================
        self.table = QTableWidget(15, 3)
        self.table.setHorizontalHeaderLabels(["셀", "전압[V]", "온도[℃]"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.horizontalHeader().setFixedHeight(24)

        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.horizontalHeader().setStyleSheet(
            "QHeaderView::section { background-color: #E7F1FF; }"
        )
        cells = module_data.get("cells", [None] * 15)        
        temps = module_data.get("temps", [None] * 15)

        # 길이 보정
        if len(cells) < 15:
            cells += [None] * (15 - len(cells))

        if len(temps) < 15:
            temps += [None] * (15 - len(temps))

        # max/min 계산 (None 제외)
        valid_cells = [v for v in cells if v is not None]
        max_v = max(valid_cells) if valid_cells else None
        min_v = min(valid_cells) if valid_cells else None
        
        # max/min 계산 (None 제외)
        valid_temps = [t for t in temps if t is not None]
        max_t = max(valid_temps) if valid_temps else None
        min_t = min(valid_temps) if valid_temps else None

        for row in range(15):

            # 셀 번호
            cell_item = QTableWidgetItem(f"셀{row+1}")
            cell_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, cell_item)

            # 전압
            volt_value = cells[row]
            volt_text = f"{volt_value:.2f}" if volt_value is not None else "-"

            volt_item = QTableWidgetItem(volt_text)
            volt_item.setTextAlignment(Qt.AlignCenter)

            if volt_value is not None:
                if max_v is not None and volt_value == max_v:
                    volt_item.setBackground(QColor("#D3F9D8"))
                elif min_v is not None and volt_value == min_v:
                    volt_item.setBackground(QColor("#FFE3E3"))

            self.table.setItem(row, 1, volt_item)

            # 온도
            temp_value = temps[row]
            temp_text = f"{temp_value:.1f}" if temp_value is not None else "-"

            temp_item = QTableWidgetItem(temp_text)
            temp_item.setTextAlignment(Qt.AlignCenter)
            
            if temp_value is not None:
                if temp_value >= 60:
                    temp_item.setBackground(QColor("#FF4D4D"))
                if max_t is not None and temp_value == max_t:
                    temp_item.setBackground(QColor("#FFF9C4"))
                    #temp_item.setBackground(QColor("#D3F9D8"))
                #elif min_t is not None and temp_value == min_t:
                #    temp_item.setBackground(QColor("#FFE3E3"))

            
            self.table.setItem(row, 2, temp_item)

        self.table.resizeColumnsToContents()
        
        layout.addWidget(self.table)

        # ======================================================
        # 4️⃣ 버튼
        # ======================================================
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

# ======================
# 프로파일 선택 다이얼로그
# ======================
class ProfileDialog(QDialog):
    def __init__(self, profile_dir):
        super().__init__()
        self.setWindowTitle("프로파일 선택")
        self.profile_dir = profile_dir
        self.selected_profile_path = None
        self.new_profile_data = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("저장된 설치장소 + 시스템"))

        self.profile_list = QListWidget()
        layout.addWidget(self.profile_list)

        self.load_profiles()

        btn_layout = QHBoxLayout()

        self.new_btn = QPushButton("신규 생성")
        self.delete_btn = QPushButton("삭제")

        btn_layout.addWidget(self.new_btn)
        btn_layout.addWidget(self.delete_btn)

        layout.addLayout(btn_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        self.new_btn.clicked.connect(self.create_new_profile)
        self.delete_btn.clicked.connect(self.delete_profile)
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)

    def load_profiles(self):
        if not os.path.exists(self.profile_dir):
            os.makedirs(self.profile_dir)

        self.profile_list.clear()
        files = [f for f in os.listdir(self.profile_dir) if f.endswith(".ini")]
        for f in files:
            self.profile_list.addItem(f.replace(".ini", ""))

    def delete_profile(self):
        current = self.profile_list.currentItem()
        if not current:
            QMessageBox.warning(self, "삭제 오류", "삭제할 프로파일을 선택하세요.")
            return

        name = current.text()
        reply = QMessageBox.question(
            self,
            "삭제 확인",
            f"{name} 프로파일을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            path = os.path.join(self.profile_dir, name + ".ini")
            if os.path.exists(path):
                os.remove(path)
            self.load_profiles()

    def create_new_profile(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("신규 프로파일 생성")
        form = QFormLayout(dialog)

        site_edit = QLineEdit()
        system_edit = QLineEdit()

        form.addRow("설치 장소:", site_edit)
        form.addRow("시스템 이름:", system_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(buttons)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec():
            site = site_edit.text().strip()
            system = system_edit.text().strip()

            if not site or not system:
                QMessageBox.warning(self, "입력 오류", "설치 장소와 시스템 이름을 모두 입력하세요.")
                return

            self.new_profile_data = (site, system)
            self.selected_profile_path = None
            self.accept()

    def accept_selection(self):
        current = self.profile_list.currentItem()
        if current:
            name = current.text()
            self.selected_profile_path = os.path.join(self.profile_dir, name + ".ini")
            self.accept()
        elif self.new_profile_data:
            self.accept()
        else:
            QMessageBox.warning(self, "선택 오류", "기존 프로파일을 선택하거나 신규 생성하세요.")

    
    

#######################################################################################################

# ======================
# SNMP Trap Thread
# ======================
class SNMPTrapThread(QThread):

    trap_signal = Signal(dict)
    rx_signal = Signal()
    trap_time_signal = Signal()
    def __init__(self, listen_ip="0.0.0.0", port=162, community="sktlfp48r"):
        super().__init__()

        self.listen_ip = listen_ip
        self.port = int(port)
        self.community = community
        self.running = True
        self.snmpEngine = None
        self.setTerminationEnabled(True)
        self.trap_counter = 0
        self.trap_rate = 0
        self.last_rate_time = time.time()
        self.trap_queue = deque(maxlen=2000)

    def run(self):
        #print(f"[TRAP] Thread run start (listen {self.listen_ip}:{self.port})")
        dprint("SNMP", f"[TRAP] Thread run start (listen {self.listen_ip}:{self.port})")
        
        self.snmpEngine = engine.SnmpEngine()

        config.addTransport(
            self.snmpEngine,
            udp.domainName,
            udp.UdpTransport().openServerMode(
                (self.listen_ip, self.port)
            )
        )

        config.addV1System(
            self.snmpEngine,
            "trap-area",
            self.community
        )

        ntfrcv.NotificationReceiver(
            self.snmpEngine,
            self.callback
        )

        dprint("SNMP", f"[TRAP] Listening on {self.listen_ip}:{self.port}")
        self.snmpEngine.transportDispatcher.jobStarted(1)

        try:
            self.snmpEngine.transportDispatcher.runDispatcher()

        except Exception as e:
            if "WinError 10038" not in str(e):
                dprint("SNMP", "[TRAP] dispatcher stopped:", e)

        finally:
            try:
                self.snmpEngine.transportDispatcher.jobFinished(1)
            except:
                pass

            try:
                if self.snmpEngine is not None:
                    self.snmpEngine.transportDispatcher.closeDispatcher()
            except:
                pass

        dprint("SNMP", "[TRAP] Thread stopped")

    def callback(self, snmpEngine, stateReference,
                 contextEngineId, contextName,
                 varBinds, cbCtx):

        #print("[TRAP CALLBACK] called")
        dprint("SNMP", "[TRAP CALLBACK] called")
        trap_data = {}

        # LED Rx 업데이트
        self.rx_signal.emit()
        
        # ⭐ 업데이트 시간 갱신
        self.trap_time_signal.emit()

        # ==============================
        # TRAP RATE 계산
        # ==============================
        self.trap_counter += 1        

        now = time.time()

        if now - self.last_rate_time >= 1.0:
            self.trap_rate = self.trap_counter
            self.trap_counter = 0
            self.last_rate_time = now

        for name, val in varBinds:
            dprint("SNMP", "  VARBIND:", str(name), "=", val.prettyPrint())
            trap_data[str(name)] = val.prettyPrint()
        
        # ⭐ queue에 추가
        self.trap_queue.append(trap_data)
        self.trap_signal.emit(trap_data)        
        

    def stop(self):
        #print("[TRAP] stop() called")
        dprint("SNMP", "[TRAP] stop() called")
        self.running = False
        try:
            if hasattr(self, "snmpEngine") and self.snmpEngine is not None:
                try:
                    self.snmpEngine.transportDispatcher.jobFinished(1)
                except:
                    pass

                self.snmpEngine.transportDispatcher.closeDispatcher()
        except Exception as e:
            #print("[TRAP] closeDispatcher error:", e)
            dprint("SNMP", "[TRAP] closeDispatcher error:", e)
        #self.quit()
        #self.wait()

# ======================
# SNMP Worker Thread
# ======================

class SNMPThread(QThread):
    result_signal = Signal(bool, object)  # str → object (dict 전달 가능)

    tx_signal = Signal()
    rx_signal = Signal()
    def __init__(self, ip, community="public", port=161, once=False):
        super().__init__()
        self.ip = ip
        self.community = community
        self.port = port
        self.running = True
        self.once = once  # 최초 테스트 여부
        self.snmpEngine = None   # 🔴 멤버로 보관

    def run(self):

        # ===============================
        # 1️⃣ 최초 연결 테스트 (sysUpTime)
        # ===============================
        if self.once:
            if hasattr(self, "parent_ui"):
                self.tx_signal.emit()
                
            # ✅ 테스트용은 별도 엔진 사용
            test_engine = SnmpEngine()
            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(
                    test_engine,
                    CommunityData(self.community, mpModel=1),
                    UdpTransportTarget(
                        (self.ip, int(self.port)),
                        timeout=2,
                        retries=0
                    ),
                    ContextData(),
                    ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0"))
                )
            )

            if errorIndication or errorStatus:
                self.result_signal.emit(False, "")
                if hasattr(self, "parent_ui"):
                    self.parent_ui.rx_led_on()
            else:
                for varBind in varBinds:
                    value = str(varBind[1])
                    #print(f"[SNMP RESPONSE] sysUpTime: {value}")
                    dprint("SNMP", f"[SNMP RESPONSE] sysUpTime: {value}")
                    self.result_signal.emit(True, value)

            return

        
        # ===============================
        # 2️⃣ 실제 배터리 MIB Polling
        # ===============================

        base_oids = [
            "1.3.6.1.4.1.2011.6.164.1.18.1",
            "1.3.6.1.4.1.2011.6.164.1.17.1",            
            "1.3.6.1.4.1.2011.6.164.1.18.2",
            "1.3.6.1.4.1.2011.6.164.1.1.2.99"
        ]        
        
        # 🔴 polling용 snmpEngine은 멤버에 저장
        self.snmpEngine = SnmpEngine()
        while self.running:

            result_data = {}

            snmpEngine = SnmpEngine()

            for base_oid in base_oids:
                # 🔵 SNMP 요청 전송 (TX blink)
                if hasattr(self, "parent_ui"):
                    self.tx_signal.emit()
                
                for (errorIndication,
                    errorStatus,
                    errorIndex,
                    varBinds) in bulkCmd(
                        snmpEngine,
                        CommunityData(self.community, mpModel=1),
                        UdpTransportTarget((self.ip, int(self.port))),
                        ContextData(),
                        0, 10,
                        ObjectType(ObjectIdentity(base_oid)),
                        lexicographicMode=False):
                        
                    if not self.running:
                        return

                    if errorIndication or errorStatus:
                        self.result_signal.emit(False, "")
                        break
                    
                    if hasattr(self, "parent_ui"):
                        self.rx_signal.emit()
    
                    for varBind in varBinds:
                        oid = str(varBind[0])
                        value = varBind[1].prettyPrint()
                        result_data[oid] = value

            if result_data:
                self.result_signal.emit(True, result_data)

            for _ in range(50):
                if not self.running:
                    return
                self.msleep(100)

    def stop(self):
        self.running = False
        try:
            if self.snmpEngine is not None:
                try:
                    self.snmpEngine.transportDispatcher.jobFinished(1)
                except Exception:
                    pass

                self.snmpEngine.transportDispatcher.closeDispatcher()
        except Exception:
            pass
        self.quit()
        self.wait()
        
# ======================
# 메인 UI
# ======================
class BatteryMonitorUI(QMainWindow):
    def __init__(self, profile_path, new_profile_data=None):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        
        self.current_profile = {}
        
        # 🔥 추가 (여기!)
        self.module_barcodes = {}

        # 상태 표시 라벨 미리 생성
        self.tx_label = QLabel("TX")
        self.rx_label = QLabel("RX")

        self.tx_led = QLabel()
        self.tx_led.setFixedSize(12,12)
        self.tx_led.setStyleSheet("background:#555;border-radius:6px;")

        self.rx_led = QLabel()
        self.rx_led.setFixedSize(12,12)
        self.rx_led.setStyleSheet("background:#555;border-radius:6px;")

        self.update_time_label = QLabel("최종업데이트시간 : 대기중")
        
        self.resize(1200, 850)
        self.ping_thread = None
        self.snmp_thread = None
        self.trap_thread = None
        
        self.trap_queue = deque(maxlen=TRAP_QUEUE_SIZE)

        # ================================
        # 현재 소스 파일 위치 기준 logs 생성
        # ================================
        script_dir = os.path.dirname(os.path.abspath(__file__))  # 소스 파일 경로
        self.log_dir = os.path.join(script_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        dprint("MODULE", f"Log directory created at: {self.log_dir}")
        
        self.is_connected = False
        self.last_update_time = ""
        self.settings = QSettings(profile_path, QSettings.IniFormat)        
        self.profile_path = profile_path
        dprint("DEBUG", "profile_path =", profile_path)
        # ------------------------------
        # 설치 모듈 순서 로드
        # ------------------------------
        order = self.settings.value("module_order")
        #print("로드 module_order =", self.settings.value("module_order"))
        if order:
            self.module_order = [int(x) if x else None for x in order]
        else:
            self.module_order = [None] * 10
    
        # ------------------------------
        # 모듈 데이터 구조
        # ------------------------------
        self.module_map = {}        # {module_no: equip_id}
        self.module_data = {}       # {equip_id: {battery data}}        

        # ------------------------------
        # barcode 수신 상태
        # ------------------------------
        self.module_barcodes_ready = False
        
        self.fault_list = []
        
        self.active_fault_keys = set()
        self.last_fault_snapshot = set()
        # AlarmTable 저장
        self.current_alarm_table = []
        
        # 🔔 Alarm 버튼 초기 상태
        self.alarm_blink_state = False
        self.alarm_active = False

        self.alarm_blink_timer = QTimer()
        self.alarm_blink_timer.timeout.connect(self.blink_alarm_button)
        
        self.tx_timer = QTimer()
        self.tx_timer.setSingleShot(True)        
        self.tx_timer.timeout.connect(self.tx_led_off)

        self.rx_timer = QTimer()
        self.rx_timer.setSingleShot(True)
        self.rx_timer.timeout.connect(self.rx_led_off)
        
        # ==============================
        # 시스템 리소스 모니터
        # ==============================
        self.sys_timer = QTimer()
        self.sys_timer.timeout.connect(self.update_system_resource)
        self.sys_timer.start(1000)   # 1초마다 업데이트

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        main_layout.addWidget(self.create_connection_panel())
        main_layout.addWidget(self.create_header())
        main_layout.addWidget(self.create_summary_section())
        main_layout.addWidget(self.create_module_table())        
        main_layout.addWidget(self.create_fault_table())

        # 신규 프로파일일 경우 기본값 저장
        if new_profile_data:
            site, system = new_profile_data
            self.site_edit.setText(site)
            self.system_edit.setText(system)
            self.save_site_info()
        else:
            self.load_site_info()
            self.module_barcodes = self.settings.value("module_barcodes", {})
            
            if self.module_barcodes is None:
                self.module_barcodes = {}
                
            # QVariant → dict 강제 변환
            if isinstance(self.module_barcodes, dict):
                pass
            else:
                try:
                    self.module_barcodes = dict(self.module_barcodes)
                except:
                    self.module_barcodes = {}
                    
            if self.module_barcodes is None:
                self.module_barcodes = {}
            self.update_module_order_view()    
        
        # ------------------------------
        # 설치 모듈 순서 복원
        # ------------------------------
        order = self.settings.value("module_order")

        if order:
            self.module_order = [int(x) if x else None for x in order]
            self.update_module_order_view()
    
    
    def open_module_order_dialog(self):

        dialog = ModuleOrderDialog(self)

        dialog.exec()
    
    def save_module_order(self, order):

        self.module_order = order

        # 🔥 module_order 기준으로 barcode 저장
        barcode_map = {}

        for pos, module_no in enumerate(order, start=1):

            if module_no is None:
                continue

            info = self.module_map.get(module_no)

            if info:
                barcode = info.get("barcode", "")
                barcode_map[str(module_no)] = barcode if barcode else "-"

        # -------------------------
        # 저장
        # -------------------------
        self.settings.setValue("module_order", order)
        self.settings.setValue("module_barcodes", barcode_map)
        self.settings.sync()

        dprint("MODULE", "저장 module_order =", order)
        dprint("MODULE", "저장 barcode_map =", barcode_map)

        # 🔥 메모리에도 유지
        self.module_barcodes = barcode_map

        self.update_module_order_view()
    
    
    def update_module_order_label(self, index, module_no=None, barcode=None, has_alarm=False):

        label = self.module_order_labels[index]

        if module_no is None:
            # ❌ 비어있는 상태
            label.setText(f"{index+1:02d} : -")

            label.setStyleSheet("""
                QLabel {
                    border: 1px solid #E0E6ED;        /* ← 얇은 테두리 유지 */
                    border-radius: 6px;               /* ← 8px → 6px */
                    padding: 2px 6px;                 /* ← 좌우 4px → 6px */
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                stop:0 #F8FAFC, stop:1 #F1F5F9);
                    color: #64748B;
                    font-weight: 400;                 /* ← 500 → 400 (더 얇게) */
                    font-size: 12px;                  /* ← 13px → 12px */
                    min-height: 20px;                 /* ← 24px → 20px (핵심!) */
                }
                QLabel:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                stop:0 #E2E8F0, stop:1 #F1F5F9);
                    border-color: #CBD5E1;
                }
            """)
        else:
            # ✅ 값 있는 상태
            label.setText(f"{index+1:02d} : 모듈{module_no:02d} [{barcode}]")            
            
            if has_alarm:
                label.setStyleSheet("""
                    QLabel {
                        border: 1px solid #FF9800;
                        border-radius: 6px;
                        padding: 2px 6px;
                        background: #FFF3E0;
                        color: #E65100;
                        font-weight: 600;
                        font-size: 12px;
                    }
                """)
            else:
                label.setStyleSheet("""
                    QLabel {
                        border: 1px solid #3B82F6;
                        border-radius: 6px;
                        padding: 2px 6px;
                        background: #EFF6FF;
                        color: #1E40AF;
                        font-weight: 500;
                        font-size: 12px;
                    }
                """)
        
    def create_module_order_panel(self):

        group = QGroupBox("설치 모듈 순서")

        layout = QVBoxLayout()

        self.module_order_labels = []

        for i in range(10, 0, -1):

            label = QLabel(f"{i:02d} : -")
            label.setMinimumHeight(22)

            label.setStyleSheet("""
            QLabel {
                border: 1px solid #c8c8c8;
                padding-left: 6px;
                background: #fafafa;
            }
            """)

            self.module_order_labels.append(label)
            layout.addWidget(label)

        group.setLayout(layout)

        return group


    def update_system_resource(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            process = psutil.Process()

            app_mem = process.memory_info().rss
            total_mem = psutil.virtual_memory().total

            app_mem_mb = app_mem / (1024 * 1024)
            app_mem_percent = (app_mem / total_mem) * 100

            thr = process.num_threads()

            # TRAP
            if self.trap_thread:
                rate = self.trap_thread.trap_rate
                queue_size = len(self.trap_thread.trap_queue)
                queue_max = self.trap_thread.trap_queue.maxlen
            else:
                rate = 0
                queue_size = 0
                queue_max = 0

            # 🔥 폰트 1회만 설정 (성능 최적화)
            if not hasattr(self, "_status_font"):
                font = QFont("Consolas")
                font.setPointSize(10)
                font.setStyleHint(QFont.TypeWriter)
                self.status_label.setFont(font)
                font.setBold(True)

                # 🔥 스타일 (가독성 개선)
                self.status_label.setStyleSheet("color: #FFFFFF; padding:0px; margin:0px;")


            # 🔥 최종 UI 문자열 (고정폭 + 가독성)
            text = (
                f" CPU[{cpu:06.1f}%]"
                f" MEM[{app_mem_mb:6.1f}MB({app_mem_percent:6.1f}%)]"
                f" Thread[{thr:3d}]"
                f" TRAP[{rate:5d}/s]"
                f" QUEUE[{queue_size:4d}/{queue_max}]"
            )

            self.status_label.setText(text)

        except Exception as e:
            dprint("MODULE", "SYS MON ERROR:", e)

    def show_alarm_list(self):

        dialog = AlarmListDialog(self)
        dialog.exec()
    
    def write_trap_log(self, t, oid, ordinal, alarm, level, equip_id, equip_name, father):

        date_str = datetime.now().strftime("%Y%m%d")

        logfile = os.path.join(self.log_dir, f"trap_{date_str}.log")

        line = f"{t},{oid},{ordinal},{alarm},{level},{equip_id},{equip_name},{father}\n"

        with open(logfile, "a", encoding="utf-8") as f:
            f.write(line)
        
    def tx_led_on(self):

        if not self.is_connected:
            return

        self.tx_led.setStyleSheet(
            "background-color: #00c853;border-radius: 4px;"
        )
        self.tx_timer.start(300)


    def rx_led_on(self):

        if not self.is_connected:
            return

        self.rx_led.setStyleSheet(
            "background-color: #00c853;border-radius: 4px;"
        )
        self.rx_timer.start(300)

    def rx_led_poll(self):

        self.rx_led.setStyleSheet(
            "background:#00c853;border-radius:4px;"
        )

        QTimer.singleShot(120, self.rx_led_off)

    def rx_led_trap(self):

        self.rx_led.setStyleSheet(
            "background:#ff9800;border-radius:4px;"
        )

        QTimer.singleShot(200, self.rx_led_off)
    
    def tx_led_off(self):

        self.tx_led.setStyleSheet(
            "background:#505050;border-radius:4px;"
        )


    def rx_led_off(self):

        #self.rx_led.setStyleSheet(
        #    "background-color: #808080;border-radius: 4px;"
        #)
        self.rx_led.setStyleSheet(
            "background:#505050;border-radius:4px;"
        )

    def update_time_from_trap(self):

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.update_time_label.setText(
            f"최종업데이트시간 : {now}"            
        )
    
    def closeEvent(self, event):
        #print("[INFO] Program closing")
        dprint("MODULE", "[INFO] Program closing")

        # 이미 연결 중이면 종료 로직 호출
        if self.is_connected:
            self.on_connect_clicked()
        
        if hasattr(self, "snmp_thread") and self.snmp_thread:
            if self.snmp_thread.isRunning():
                self.snmp_thread.stop()
                self.snmp_thread.wait(2000)

        if hasattr(self, "trap_thread") and self.trap_thread:
            if self.trap_thread.isRunning():
                self.trap_thread.stop()
                self.trap_thread.wait(2000)

        event.accept()
        
    def show_module_detail(self, module_no):
        dialog = ModuleDetailDialog(module_no, self)
        dialog.exec()
        
    def show_auto_close_message(self, title, message):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.Ok)

        QTimer.singleShot(3000, msg.accept)  # 🔥 3초 후 자동 닫힘
        msg.exec()

    def handle_connection_test(self, success, value):
        ip = self.ip_edit.text().strip()
        port = self.port_edit.text().strip()
        get_comm = self.get_comm_edit.text().strip()
        set_comm = self.set_comm_edit.text().strip()
        trap_comm = self.trap_comm_edit.text().strip()
        trap_port = self.trap_port_edit.text().strip()
        if success:
            # 🔥 profile 저장 (접속 성공 시)
            self.settings.setValue("ip", ip)
            self.settings.setValue("port", port)
            self.settings.setValue("get_comm", get_comm)
            self.settings.setValue("set_comm", set_comm)
            self.settings.setValue("trap_comm", trap_comm)
            self.settings.setValue("trap_port", trap_port)

            self.settings.sync()
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 상태 표시 (녹색)
            self.status_circle.setStyleSheet(
                "background-color: #2ECC71; border-radius: 7px;"
            )
            self.update_time_label.setText(f"최종업데이트시간 : {current_time}")
            
            self.show_auto_close_message("접속 성공", "축전지 시스템 연결 성공")

            self.is_connected = True
            self.connect_btn.setText("접속종료")

            ip = self.ip_edit.text().strip()
            port = self.port_edit.text().strip()
            community = self.get_comm_edit.text().strip()
            trap_comm = self.trap_comm_edit.text().strip()

            # 기존 polling thread 정리
            if hasattr(self, "snmp_thread") and self.snmp_thread:
               self.snmp_thread.stop()

            # 🔥 Trap thread 시작
            if hasattr(self, "trap_thread") and self.trap_thread:
                self.trap_thread.stop()
            
            # 🔥 polling 시작
            self.snmp_thread = SNMPThread(ip, community, port, once=False)
            self.snmp_thread.tx_signal.connect(self.tx_led_on)
            #self.snmp_thread.rx_signal.connect(self.rx_led_on)
            self.snmp_thread.rx_signal.connect(self.rx_led_poll)
            self.snmp_thread.parent_ui = self
            self.snmp_thread.result_signal.connect(self.handle_snmp_result)
            self.snmp_thread.start()
            trap_port = int(self.trap_port_edit.text().strip())
            
            self.trap_thread = SNMPTrapThread(
                listen_ip="0.0.0.0",
                port=trap_port,
                community=trap_comm
            )
            #self.trap_thread.parent_ui = self
            #self.trap_thread.rx_signal.connect(self.rx_led_on)
            self.trap_thread.rx_signal.connect(self.rx_led_trap)
            self.trap_thread.trap_time_signal.connect(self.update_time_from_trap)
            
            self.trap_thread.trap_signal.connect(self.handle_trap)
            self.trap_thread.start()

        else:
            self.show_auto_close_message("접속 실패", "축전지 시스템 연결 실패.")

    
    def show_alarm_popup(self):

        alarm_names = [
            "Battery Fuse Broken",
            "Lithium battery communication failure",
            "Low temperature protection",
            "Low temperature discharge",
            "High temperature protection",
            "Charging high temperature protection",
            "Charging overvoltage",
            "Overcharge",
            "Overcharge Protection",
            "Overdischarge Protection",
            "Charging Overcurrent Protection",
            "Heavy load Overcurrent Protection",
            "Discharge Overcurrent Protection",
            "Upgrade failure",
            "Busbar overvoltage protection",
            "Discharge low temperature protection",
            "Charging low temperature protection",
            "Input reverse connection",
            "Abnormal shutdown",
            "Unlock failure",
            "Board hardware fault",
            "Cell 1 Fault",
            "Cell 2 Fault",
            "Cell 3 Fault",
            "Cell 4 Fault",
            "Cell 5 Fault",
            "Cell 6 Fault",
            "Cell 7 Fault",
            "Cell 8 Fault",
            "Cell 9 Fault",
            "Cell 10 Fault",
            "Cell 11 Fault",
            "Cell 12 Fault",
            "Cell 13 Fault",
            "Cell 14 Fault",
            "Cell 15 Fault"
        ]

        dialog = QDialog(self)
        dialog.setWindowTitle("Active Alarm List")
        dialog.resize(1000,600)

        # 🔴 전체화면(최대화) 버튼 추가
        dialog.setWindowFlags(
            dialog.windowFlags() |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.Window
        )
        
        table = QTableWidget()
        table.setRowCount(len(alarm_names))
        table.setColumnCount(12)

        headers = ["Active Alarm List","시스템"] + [f"모듈-{i}" for i in range(1,11)]
        table.setHorizontalHeaderLabels(headers)

        header = table.horizontalHeader()
        # 첫 번째 열 (Active Alarm List)만 내용에 맞게 자동 조정
        #header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        # 모든 컬럼을 내용 기준으로 자동 확장
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        
        header.setStyleSheet("""
        QHeaderView::section {
            background-color: #E7F1FF;
            color: black;
            font-weight: bold;
            padding: 4px;
            border: 1px solid #CCCCCC;
            text-align: center;
        }
        """)
        
        for i,name in enumerate(alarm_names):            
            table.setItem(i,0,QTableWidgetItem(name))

        # 🔥 Alarm 데이터 매핑
        for alarm in self.current_alarm_table:

            text = alarm.get("text","")
            time = alarm.get("time","")
            equip = alarm.get("equip","")

            if text in alarm_names:

                for i,name in enumerate(alarm_names):
                    if name.lower() == text.lower():
                        row = i
                        break

                module_col = 1  # 기본 System

                try:
                    equip_id = int(equip)

                    module_no = None

                    # module_map 에서 equip_id → module_no 검색
                    for m_no, info in self.module_map.items():
                        if int(info["equip_id"]) == equip_id:
                            module_no = m_no
                            break

                    if module_no is not None:
                        module_col = 1 + module_no   # System 다음 컬럼부터 module1~

                except:
                    pass

                table.setItem(row,module_col,QTableWidgetItem(time))

        layout = QVBoxLayout()
        layout.addWidget(table)

        dialog.setLayout(layout)
        dialog.exec()
            
    # ===== 이전 UI 함수는 그대로 두고 save/load_site_info 적용 =====
    def on_connect_clicked(self):

        # ======================================
        # 종료 모드
        # ======================================
        if self.is_connected:

            #print("[INFO] Disconnect requested")
            dprint("MODULE", "[INFO] Disconnect requested")

            # blink 중지
            if hasattr(self, "alarm_blink_timer"):
                self.alarm_blink_timer.stop()
                if self.alarm_active:
                    self.btn_alarm_popup.setStyleSheet(
                    "background-color:red;color:white;font-weight:bold;"
                    )
                else:
                    self.btn_alarm_popup.setStyleSheet("")

            self.tx_led_off()
            self.rx_led_off()
            
            # SNMP Polling Thread 종료
            if hasattr(self, "snmp_thread") and self.snmp_thread:
                if self.snmp_thread.isRunning():
                    dprint("SNMP", "[INFO] Stopping SNMP thread")
                    self.snmp_thread.stop()
                    # 🔴 타임아웃을 주고, 그래도 안 끝나면 강제 종료 시도
                    if not self.snmp_thread.wait(3000):
                        print("[WARN] SNMP thread did not stop in time, terminating...")
                        self.snmp_thread.terminate()
                        self.snmp_thread.wait(1000)
                self.snmp_thread = None
            # Trap Thread 종료
            if hasattr(self, "trap_thread") and self.trap_thread:
                if self.trap_thread.isRunning():
                    dprint("SNMP", "[INFO] Stopping TRAP thread")
                    self.trap_thread.stop()
                    if not self.trap_thread.wait(3000):
                        dprint("SNMP", "[WARN] TRAP thread did not stop in time, terminating...")
                        self.trap_thread.terminate()
                        self.trap_thread.wait(1000)
                self.trap_thread = None
            
            if hasattr(self, "ping_thread") and self.ping_thread:
                if self.ping_thread.isRunning():
                    self.ping_thread.stop()
                    self.ping_thread.wait(1000)
                self.ping_thread = None
            
            # 상태/데이터 초기화
            self.is_connected = False

            self.connect_btn.setText("접속시작")
            self.status_circle.setStyleSheet(
                "background-color: #CCCCCC; border-radius: 7px;"
            )
            self.btn_module_order.setEnabled(False)
            self.show_auto_close_message("접속 종료", "축전지 시스템 연결 종료.")

            #print("[INFO] Disconnected")
            dprint("MODULE", "[INFO] Disconnected")

            return

        # ======================================
        # 접속 시도 (1회 테스트)
        # ======================================
        ip = self.ip_edit.text().strip()
        port = self.port_edit.text().strip()
        community = self.get_comm_edit.text().strip()

        # 이미 테스트 thread가 실행중이면 실행 금지
        if hasattr(self, "test_thread") and self.test_thread:
            if self.test_thread.isRunning():
                #print("[WARN] Connection test already running")
                dprint("MODULE", "[WARN] Connection test already running")
                return

        #print(f"[INFO] SNMP connection test -> {ip}:{port}")
        dprint("MODULE", f"[INFO] SNMP connection test -> {ip}:{port}")

        self.test_thread = SNMPThread(ip, community, port, once=True)
        self.test_thread.result_signal.connect(self.handle_connection_test)
        self.test_thread.start()

        #print(f"[INFO] SNMP GETNEXT started to {ip}...")
        dprint("MODULE", f"[INFO] SNMP GETNEXT started to {ip}...")
 #################################################################################    
    def update_module_tables(self):

        status_map = {
            0: ("Online", "#B2F2BB"),
            1: ("Offline", "#FF6B6B"),
            2: ("Sleep", "#CED4DA"),
            3: ("Disconnect", "#FF6B6B"),
            4: ("충전중", "#B2F2BB"),
            5: ("방전중", "#4DABF7"),
            6: ("Standby", "#FFD43B"),
            255: ("Unknown", "#CED4DA")
        }
        # -----------------
        # 모듈 알람 목록 생성
        # -----------------
        alarm_modules = set()

        for alarm in self.current_alarm_table:

            equip = alarm.get("equip")

            for m_no, info in self.module_map.items():
                if int(info["equip_id"]) == int(equip):
                    alarm_modules.add(m_no)
                    break
        
        for module_no in range(1, 11):

            if module_no not in self.module_map:
                continue

            equip_id = self.module_map[module_no]["equip_id"]

            if equip_id not in self.module_data:
                continue

            data = self.module_data[equip_id]
            
            if not data:
                continue

            # =========================
            # 🔥 여기 추가 (핵심 위치)
            # =========================
            row = (module_no - 1) % 5
            table = self.module_table_left if module_no <= 5 else self.module_table_right

            # -----------------
            # 모듈 전압
            # -----------------
            if data["volt"] is not None:
                table.item(row, 1).setText(f"{data['volt']:.1f}")

            # -----------------
            # 셀 전압 Max/Min
            # -----------------
            cells = [v for v in data["cells"] if v is not None]
            if cells:
                max_v = max(cells)
                min_v = min(cells)
                table.item(row, 2).setText(f"{max_v:.2f} / {min_v:.2f}")

            # -----------------
            # 온도 Max/Min
            # -----------------            
            temps = [v for v in data["temps"] if v is not None]
            if temps:
                max_t = max(temps)
                min_t = min(temps)
                table.item(row, 3).setText(f"{max_t:.1f} / {min_t:.1f}")

            # -----------------
            # Running Status
            # -----------------
            if data["status"] is not None:

                status_text, color = status_map.get(
                    data["status"],
                    ("Unknown", "#CED4DA")
                )

                item = table.item(row, 5)
                item.setText(status_text)
                item.setBackground(QColor(color))

                if color in ["#FF6B6B", "#4DABF7"]:
                    item.setForeground(QColor("white"))
                else:
                    item.setForeground(QColor("black"))                  
            
                # -----------------
                # 상세 버튼 활성화
                # -----------------
                btn = table.cellWidget(row, 6)
                if btn:
                    btn.setEnabled(True)
            
            # -----------------
            # 경보 상태 표시
            # -----------------
            alarm_item = table.item(row, 4)

            # 🔥 여기 추가 (정확한 위치)
            if not hasattr(self, "module_widgets"):
                self.module_widgets = {}

            self.module_widgets[module_no] = alarm_item
            
            # module_map에 모듈이 없는 경우
            if module_no not in self.module_map:
                if alarm_item:
                    alarm_item.setText("-")
                continue

            # 알람 여부 판단
            if module_no in alarm_modules:
                alarm_text = "이상"
                color = "red"                
                alarm_item.setForeground(QColor("white"))
                alarm_item.setBackground(QColor("#FF6B6B"))
            else:
                alarm_text = "정상"
                color = "black"
                alarm_item.setForeground(QColor("#1E293B"))   # 진한 네이비 (가독성 좋음)
                alarm_item.setBackground(QColor("#F1F5F9"))   # 아주 연한 그레이-블루

            if alarm_item:
                alarm_item.setText(alarm_text)
            
    def update_summary_value(self, label, value, status="정상"):
        if label not in self.summary_position_map:
            return

        row, col = self.summary_position_map[label]
        item = self.summary_table.item(row, col)

        item.setText(str(value))
        apply_value_style(item, status)
    
    # ======================
    # 🔔 Alarm Blink
    # ======================
    def blink_alarm_button(self):

        if not self.alarm_active:
            self.btn_alarm_popup.setStyleSheet("")
            return

        if self.alarm_blink_state:
            self.btn_alarm_popup.setStyleSheet(
                "background-color:red;color:white;font-weight:bold;"
            )
        else:
            self.btn_alarm_popup.setStyleSheet("")

        self.alarm_blink_state = not self.alarm_blink_state
        
    # ======================
    # SNMP 응답 처리
    # ======================
    def debug_dump_modules(self):

        dprint("SNMP", "\n================ MODULE DATA DUMP ================")

        if not self.module_data:
            dprint("SNMP", "No module data")
            return

        for equip_id, data in self.module_data.items():

            dprint("SNMP", f"\n------ MODULE {equip_id} ------")
            dprint("SNMP", "Voltage :", data.get("volt"))
            dprint("SNMP", "Status  :", data.get("status"))
            dprint("SNMP", "SOC     :", data.get("soc"))
            dprint("SNMP", "SOH     :", data.get("soh"))

            dprint("SNMP", "Cells:")
            for i, v in enumerate(data.get("cells", []), 1):
                dprint("SNMP", f"   Cell {i:02d} :", v)

            dprint("SNMP", "Temps:")
            for i, t in enumerate(data.get("temps", []), 1):
                dprint("SNMP", f"   Temp {i:02d} :", t)

        dprint("SNMP", "\n==================================================\n")
    
    def update_module_alarm(self, module_name, alarm_text, alarm_time):

        if alarm_text is None:
            return

        for row in range(self.fault_table.rowCount()):

            name_item = self.fault_table.item(row, 0)

            if not name_item:
                continue

            if name_item.text() == module_name:

                self.fault_table.setItem(row, 6, QTableWidgetItem(alarm_text))
                self.fault_table.setItem(row, 7, QTableWidgetItem(alarm_time))

                break
    
    def clear_fault_table(self):
        for row in range(self.fault_table.rowCount()):
            self.fault_table.setItem(row, 1, QTableWidgetItem(""))
            self.fault_table.setItem(row, 2, QTableWidgetItem(""))
    
        
    def handle_snmp_result(self, success, value):        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if success and isinstance(value, dict):

            # 상태 표시
            self.status_circle.setStyleSheet(
                "background-color: #2ECC71; border-radius: 7px;"
            )
            # 접속 성공 → Alarm 버튼 활성화
            self.btn_alarm_popup.setEnabled(True)
            
            self.update_time_label.setText(f"최종업데이트시간 : {current_time}")

            # 🔥 기존 데이터 초기화
            self.module_map.clear()
            self.module_data.clear()

            # 🔥 Active Alarm 저장 리스트
            active_alarm_texts = []
            
            alarm_entries = {}
            # ===============================
            # OID 처리 시작
            # ===============================
            for oid, val in value.items():

                if str(val) == "2147483647":
                    continue

                val_str = str(val)
                
                
                # 🔥 Alarm 정보 수집
                # AlarmText
                if oid.startswith("1.3.6.1.4.1.2011.6.164.1.1.2.99.1.2."):

                    index = oid.split(".")[-1]

                    if index not in alarm_entries:
                        alarm_entries[index] = {}

                    alarm_entries[index]["text"] = val_str                    
                    active_alarm_texts.append(val_str)

                    # 🔥 추가 (Summary용)
                    active_alarm_texts.append(val_str)


                # Alarm Time
                elif oid.startswith("1.3.6.1.4.1.2011.6.164.1.1.2.99.1.5."):

                    index = oid.split(".")[-1]

                    if index not in alarm_entries:
                        alarm_entries[index] = {}

                    alarm_entries[index]["time"] = val_str


                # hwEquipId
                elif oid.startswith("1.3.6.1.4.1.2011.6.164.1.1.2.99.1.10."):

                    index = oid.split(".")[-1]

                    if index not in alarm_entries:
                        alarm_entries[index] = {}

                    alarm_entries[index]["equip"] = int(val_str)
                        
                # ====================================================
                # 1️⃣ Summary 영역
                # ====================================================
                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.5.96":
                    rack_voltage = int(val_str) / 10
                    self.update_summary_value("Rack 전압[V]", f"{rack_voltage:.1f}")

                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.6.96":
                    rack_current = int(val_str) / 10
                    self.update_summary_value("Rack 전류[A]", f"{rack_current:.1f}")

                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.8.96":
                    self.update_summary_value("SOC 충전율[%]", f"{val_str} %")

                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.23.96":
                    self.update_summary_value("충방전 횟수", val_str)     
                  
                # ====================================================
                # 2️⃣ hwAcbBaseTable - Module 매핑 (EquipID → ModuleNo)
                # ====================================================
                if ".1.18.1.1.2." in oid:
                    row_index = oid.split(".")[-1]
                    equip_id = val_str

                    addr_oid = f"1.3.6.1.4.1.2011.6.164.1.18.1.1.4.{row_index}"
                    swver_oid = f"1.3.6.1.4.1.2011.6.164.1.18.1.1.5.{row_index}"
                    model_oid = f"1.3.6.1.4.1.2011.6.164.1.18.1.1.12.{row_index}"
                    barcode_oid = f"1.3.6.1.4.1.2011.6.164.1.18.1.1.13.{row_index}"
                    
                    # 🔥 안전 처리
                    barcode_val = value.get(barcode_oid)

                    # 🔥 1번만 체크
                    if barcode_val:
                        self.module_barcodes_ready = True
                        self.btn_module_order.setEnabled(True)
                        
                    if addr_oid in value:
                        module_no = int(value[addr_oid])
                        
                        if module_no not in self.module_map:
                            self.module_map[module_no] = {
                                "equip_id": row_index,
                                "swver": None,
                                "model": None,
                                "barcode": None
                            }

                        # 🔥 핵심 (전부 안전 접근)
                        module_info = self.module_map[module_no]
                        module_info["swver"] = value.get(swver_oid)
                        module_info["model"] = value.get(model_oid)
                        module_info["barcode"] = barcode_val
                        
                        
                # ====================================================
                # 3️⃣ SampTable (실제 배터리 데이터)
                # ====================================================
                if ".1.18.2.1." in oid:

                    parts = oid.split(".")
                    column = int(parts[-2])
                    row_index = parts[-1]

                    if row_index not in self.module_data:
                        self.module_data[row_index] = {
                            "volt": None,
                            "status": None,
                            "soc": None,
                            "soh": None,
                            "cells": [0.0] * 15,
                            "temps": [0.0] * 15
                        }

                    # 모듈 전압
                    if column == 1:
                        self.module_data[row_index]["volt"] = int(val_str) / 10

                    # 상태
                    elif column == 3:
                        self.module_data[row_index]["status"] = int(val_str)

                    # SOH
                    elif column == 4:
                        self.module_data[row_index]["soh"] = int(val_str)
                    
                        
                    # 셀 전압 (6~20)
                    elif 6 <= column <= 20:
                        cell_index = column - 6
                        try:                            
                            self.module_data[row_index]["cells"][cell_index] = round(int(val_str) / 100, 2)
                        except:
                            pass

                    # 셀 온도 (22~36)
                    elif 22 <= column <= 36:
                        temp_index = column - 22
                        try:                            
                            self.module_data[row_index]["temps"][temp_index] = round(int(val_str) / 10, 1)
                        except:
                            pass

                    # SOC
                    elif column == 52:
                        self.module_data[row_index]["soc"] = int(val_str)
            
            self.current_alarm_table = list(alarm_entries.values())
            #print(self.current_alarm_table)
            if self.current_alarm_table:
                dprint("ALARM", self.current_alarm_table)
            # 🔔 Alarm 버튼 상태 업데이트
            alarm_count = len(self.current_alarm_table)

            if alarm_count > 0:

                self.alarm_active = True

                # 버튼 텍스트에 알람 개수 표시
                self.btn_alarm_popup.setText(f"발생된 알람 보기 ({alarm_count})")

                if not self.alarm_blink_timer.isActive():
                    self.alarm_blink_timer.start(500)

            else:

                self.alarm_active = False

                self.btn_alarm_popup.setText("발생된 알람 보기")

                if self.alarm_blink_timer.isActive():
                    self.alarm_blink_timer.stop()

                self.btn_alarm_popup.setStyleSheet("")
    
            new_fault_snapshot = set()
            new_fault_keys = set()
            # 🔥 Alarm Equip → Module 변환
            self.alarm_modules = set()
            for alarm in self.current_alarm_table:

                equip = alarm.get("equip")
                alarm_text = alarm.get("text")
                alarm_time = alarm.get("time")

                module_no = None
                module_name = None

                for m_no, info in self.module_map.items():
                    try:
                        if int(info["equip_id"]) == int(equip):
                            module_no = m_no
                            module_name = f"모듈-{module_no}"
                            break
                    except:
                        continue                    
                # 🔥 방어 코드 (핵심)
                if module_name is None:
                    # 매핑 실패 → 로그만 찍고 스킵
                    print(f"[WARN] Equip 매핑 실패: equip={equip}")
                    continue
                
                # 🔥 알람 모듈 저장
                self.alarm_modules.add(module_no)
                
                # 모듈 알람 업데이트
                self.update_module_alarm(module_name, alarm_text, alarm_time)
                
                # 고장 정보 테이블 업데이트
                if alarm_text in FAULT_ALARMS:

                    module_no = int(module_name.replace("모듈-", ""))

                    cell_no = 0
                    if "Cell" in alarm_text:
                        try:
                            cell_no = int(alarm_text.split(" ")[1])
                        except:
                            pass

                    fault_key = (module_no, cell_no)
                    new_fault_keys.add(fault_key)
                    new_fault_snapshot.add(fault_key)
                    
                    if fault_key not in self.active_fault_keys:

                        volt = None
                        temp = None

                        module_info = self.module_map.get(module_no)
                        if module_info:
                            equip_id = module_info["equip_id"]
                            data = self.module_data.get(equip_id)

                            if data:
                                if cell_no > 0:
                                    volt = data["cells"][cell_no-1]
                                    temp = data["temps"][cell_no-1]

                        self.add_fault(
                            module_no,
                            cell_no,
                            volt if volt else 0,
                            temp if temp else 0
                        )

                        self.active_fault_keys.add(fault_key)

            # =========================
            # Fault 변경 여부 체크
            # =========================
            fault_changed = (new_fault_snapshot != self.last_fault_snapshot)
            # -----------------------------
            # 사라진 Fault 제거
            # -----------------------------
            if fault_changed:
                removed_faults = self.active_fault_keys - new_fault_keys

                if removed_faults:

                    rows_to_delete = []

                    for row, fault in enumerate(self.fault_list):

                        key = (fault["module"], fault["cell"])

                        if key in removed_faults:
                            rows_to_delete.append(row)

                    for row in reversed(rows_to_delete):

                        self.fault_table.removeRow(row)
                        del self.fault_list[row]

                    self.active_fault_keys = new_fault_keys

                    self.refresh_fault_numbers()
            # 🔧 Fault 테이블 초기화
            #self.clear_fault_table()
            #self.active_fault_keys.clear()
            #self.fault_list.clear()
            #self.fault_table.setRowCount(0)
            
            self.last_fault_snapshot = new_fault_snapshot
            # ====================================================
            # 🔥 Alarm Summary 업데이트
            # ====================================================

            overcharge = False
            high_temp = False
            overcurrent = False

            for alarm in active_alarm_texts:

                if "Overcharge Protection" in alarm:
                    overcharge = True

                elif "Charging high temperature protection" in alarm:
                    high_temp = True

                elif "Charging Overcurrent Protection" in alarm:
                    overcurrent = True


            self.set_summary_alarm("과전압 충전차단", overcharge)
            self.set_summary_alarm("고온 충전차단", high_temp)
            self.set_summary_alarm("과전류 충전차단", overcurrent)
            # ====================================================
            # 🔥 모듈 테이블 갱신
            # ====================================================
            
            ############################################################################################## S
            volt_list = []
            temp_list = []            
            
            dprint("SNMP", "===== Voltage Calculation =====")

            for module_no in range(1, 11):

                module_info = self.module_map.get(module_no)

                if not module_info:
                    #print(f"module {module_no} → module_map 없음")
                    dprint("SNMP", f"module {module_no} → module_map 없음")
                    continue

                equip_id = module_info["equip_id"]
                data = self.module_data.get(equip_id)

                if not data:                    
                    dprint("SNMP", f"module {module_no} → module_data 없음")
                    continue

                status = data.get("status")
                volt = data.get("volt")                
                dprint("SNMP", f"module {module_no} status={status} volt={volt}")
                cells = data.get("cells", [])
                dprint("SNMP", f"module {module_no} cells={cells}")

                if status in (1,255):
                    #print("  → 제외됨")
                    dprint("SNMP", "  → 제외됨")
                    continue

                if volt is not None:
                    volt_list.append(volt)

                # ======================
                # 온도 (셀1~15)
                # ======================
                temps = data.get("temps", [])
                dprint("SNMP", f"module {module_no} temps={temps}")
                for t in temps:
                    if t is not None:
                        temp_list.append(t)
            
            # ==========================
            # 전압 계산
            # ==========================
            if volt_list:

                max_v = max(volt_list)
                min_v = min(volt_list)
                avg_v = sum(volt_list) / len(volt_list)

                self.update_summary_value("Max 전압[V]", f"{max_v:.1f}V")
                self.update_summary_value("Min 전압[V]", f"{min_v:.1f}V")
                self.update_summary_value("Avg 전압[V]", f"{avg_v:.1f}V")

            else:

                self.update_summary_value("Max 전압[V]", "-")
                self.update_summary_value("Min 전압[V]", "-")
                self.update_summary_value("Avg 전압[V]", "-")
            
            # ======================
            # 온도 계산
            # ======================
            if temp_list:

                max_t = max(temp_list)
                min_t = min(temp_list)
                avg_t = sum(temp_list) / len(temp_list)

                self.update_summary_value("Max 온도[℃]", f"{max_t:.1f}℃")
                self.update_summary_value("Min 온도[℃]", f"{min_t:.1f}℃")
                self.update_summary_value("Avg 온도[℃]", f"{avg_t:.1f}℃")

            else:

                self.update_summary_value("Max 온도[℃]", "-")
                self.update_summary_value("Min 온도[℃]", "-")
                self.update_summary_value("Avg 온도[℃]", "-")
            ############################################################################################## E
            self.update_module_tables()
            #self.debug_dump_modules()
            
            # 모듈 순서 화면 갱신
            self.update_module_order_view()
            # 🔥 여기 추가
            self.check_barcode_mismatch()
            
            now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            #print(f"[{now}] [UPDATE SUCCESS] SNMP 데이터 갱신 완료")
            dprint("SNMP", f"[{now}] [UPDATE SUCCESS] SNMP 데이터 갱신 완료")

        else:
            self.status_circle.setStyleSheet(
                "background-color: #FF6B6B; border-radius: 7px;"
            )
            #print("[SNMP ERROR]")
            dprint("SNMP", "[SNMP ERROR]")
        
        # ----------------------------
        # barcode 확인
        # ----------------------------
        barcode_ready = True

        for m in self.module_map.values():
            if not m.get("barcode"):
                barcode_ready = False
                break

        if barcode_ready:
            self.btn_module_order.setEnabled(True)
    
    def check_barcode_mismatch(self):

        if not hasattr(self, "blink_timers"):
            self.blink_timers = {}

        mismatch_modules = []

        for module_no, info in self.module_map.items():

            saved_barcode = self.module_barcodes.get(str(module_no), "")
            device_barcode = info.get("barcode", "")

            if not saved_barcode:
                continue

            has_alarm = module_no in self.alarm_modules   # 🔥 반드시 추가
            
            """
            # 🔥 디버그 출력 (핵심 정보 전체)
            print(f"[DEBUG][BARCODE_CHECK] module={module_no} | "
                f"saved={saved_barcode} | device={device_barcode} | "
                f"has_alarm={has_alarm} | mismatch={device_barcode != saved_barcode}")
            """
            if device_barcode and saved_barcode != device_barcode:
                mismatch_modules.append(module_no)

                if has_alarm:
                    # 🔥 알람 + mismatch → blink (빨간색 기반)
                    self.start_rack_blink(module_no, has_alarm=True)
                else:
                    # 일반 mismatch
                    self.start_rack_blink(module_no, has_alarm=False)
            else:
                # 🔥 blink 종료 시에도 상태 복원
                self.stop_rack_blink(module_no, has_alarm)
        
    def start_rack_blink(self, module_no, has_alarm=False):

        widget = self.rack_widgets.get(module_no)
        if not widget:
            return

        if not hasattr(self, "rack_blink_timers"):
            self.rack_blink_timers = {}

        # 🔥 base_style (알람 or 기본)
        if has_alarm:
            widget.base_style = """
            QLabel {
                border: 1px solid red;
                border-radius: 6px;
                padding: 2px 6px;
                background: #FFEBEE;
                color: #B71C1C;
                font-weight: 600;
                font-size: 12px;
            }
            """
        else:
            widget.base_style = getattr(widget, "base_style", widget.styleSheet())

        # 🔥 blink용 (border만 제거)
        widget.no_border_style = re.sub(
            r"border:\s*1px\s*solid\s*[^;]+;",
            "border: none;",
            widget.base_style
        )

        widget.is_blink_on = False

        # 🔥 이미 blink 중이면 스타일만 갱신
        if module_no in self.rack_blink_timers:
            # 🔥 이미 blink 중이면 스타일만 갱신
            widget.setStyleSheet(widget.base_style)
            return

        timer = QTimer(self)
        timer.setInterval(500)

        def blink():
            if widget.is_blink_on:
                # 🔴 알람 스타일 (border 있음)
                widget.setStyleSheet(widget.base_style)
                widget.is_blink_on = False
            else:
                # 🔴 알람 유지 + border만 OFF
                widget.setStyleSheet(widget.no_border_style)
                widget.is_blink_on = True

        timer.timeout.connect(blink)
        timer.start()

        self.rack_blink_timers[module_no] = timer
    
    def stop_rack_blink(self, module_no, has_alarm=False):
        timers = getattr(self, "rack_blink_timers", {})
        timer = timers.get(module_no)

        if timer:
            timer.stop()
            timer.deleteLater()
            del timers[module_no]

        widget = self.rack_widgets.get(module_no)
        if not widget:
            return

        # 🔥 알람 유지
        if has_alarm:            
            widget.setStyleSheet("""
            QLabel {
                border: 1px solid red;
                border-radius: 6px;
                padding: 2px 6px;
                background: #FFEBEE;
                color: #B71C1C;
                font-weight: 600;
                font-size: 12px;
            }
            """)
        else:
            # 🔥 정상 상태 스타일로 강제 복원
            normal_style = """
            QLabel {
                border: 1px solid #3B82F6;
                border-radius: 6px;
                padding: 2px 6px;
                background: #EFF6FF;
                color: #1E40AF;
                font-weight: 500;
                font-size: 12px;
            }
            """
            widget.base_style = normal_style  # 🔥 base도 같이 갱신
            widget.setStyleSheet(normal_style)
    
    def start_module_blink(self, module_no):

        if module_no in getattr(self, "blink_timers", {}):
            return

        item = self.module_widgets.get(module_no)
        if not item:
            return

        timer = QTimer(self)
        timer.setInterval(500)

        def blink():
            color = item.background().color().name()

            if color == "#ff0000":
                item.setBackground(QColor("#F1F5F9"))
                item.setForeground(QColor("#1E293B"))
            else:
                item.setBackground(QColor("red"))
                item.setForeground(QColor("white"))

        timer.timeout.connect(blink)
        timer.start()

        if not hasattr(self, "blink_timers"):
            self.blink_timers = {}

        self.blink_timers[module_no] = timer
    
    def stop_module_blink(self, module_no):
        if module_no in getattr(self, "blink_timers", {}):
            self.blink_timers[module_no].stop()
            del self.blink_timers[module_no]

        widget = self.module_widgets.get(module_no)
        if widget:
            widget.setStyleSheet("")
    
    def set_summary_alarm(self, label, is_alarm):
        if label not in self.summary_position_map:
            return

        row, col = self.summary_position_map[label]
        item = self.summary_table.item(row, col)

        if is_alarm:
            item.setText("이상")
            item.setBackground(QColor("#FF6B6B"))
            item.setForeground(QColor("white"))
        else:
            item.setText("정상")
            item.setBackground(QColor("#B2F2BB"))
            item.setForeground(QColor("black"))
        
    def handle_trap(self, trap_data):

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # -----------------------------------------
        # snmpTrapOID (표준 OID)
        # -----------------------------------------
        trap_oid = trap_data.get("1.3.6.1.6.3.1.1.4.1.0", "")

        # -----------------------------------------
        # Trap 이름 매핑
        # -----------------------------------------
        trap_name_map = {
            "1.3.6.1.4.1.2011.6.164.2.1.3.0.99": "hwAcbAlarmTrap",
            "1.3.6.1.4.1.2011.6.164.2.1.3.0.100": "hwAcbAlarmResumeTrap",
            "1.3.6.1.4.1.2011.6.164.2.1.15.0.1": "hwCabinetAlarmTrap",
            "1.3.6.1.4.1.2011.6.164.2.1.15.0.2": "hwCabinetAlarmResumeTrap",
        }

        display_trap_oid = trap_oid
        if trap_oid in trap_name_map:
            display_trap_oid = f"{trap_oid}:{trap_name_map[trap_oid]}"

        # -----------------------------------------
        # 발생 / 해제 OID 그룹 정의
        # -----------------------------------------
        alarm_oids = {
            "1.3.6.1.4.1.2011.6.164.2.1.3.0.99",
            "1.3.6.1.4.1.2011.6.164.2.1.15.0.1",
        }

        resume_oids = {
            "1.3.6.1.4.1.2011.6.164.2.1.3.0.100",
            "1.3.6.1.4.1.2011.6.164.2.1.15.0.2",
        }

        # -----------------------------------------
        # 기본값 초기화
        # -----------------------------------------
        ordinal = ""
        alarm = ""
        level = ""
        equip_id = ""
        equip_name = ""
        father_name = ""

        # -----------------------------------------
        # 동적 Index 대응 Prefix 정의
        # -----------------------------------------
        PREFIX_ORDINAL = "1.3.6.1.4.1.2011.6.164.1.1.2.2.0"
        PREFIX_ALARM = "1.3.6.1.4.1.2011.6.164.1.1.2.100.1.2."
        PREFIX_LEVEL = "1.3.6.1.4.1.2011.6.164.1.1.2.100.1.3."
        PREFIX_EQUIP_NAME = "1.3.6.1.4.1.2011.6.164.1.18.1.1.3."
        PREFIX_EQUIP_ID = "1.3.6.1.4.1.2011.6.164.1.34.1.1.2."
        PREFIX_FATHER_NAME = "1.3.6.1.4.1.2011.6.164.1.34.1.1.3."

        # -----------------------------------------
        # 모든 varBind 순회 → 동적 index 처리
        # -----------------------------------------
        for oid, val in trap_data.items():

            if oid == PREFIX_ORDINAL:
                ordinal = val

            elif oid.startswith(PREFIX_ALARM):
                alarm = val

            elif oid.startswith(PREFIX_LEVEL):
                level = val

            elif oid.startswith(PREFIX_EQUIP_NAME):
                equip_name = val

            elif oid.startswith(PREFIX_EQUIP_ID):
                equip_id = val

            elif oid.startswith(PREFIX_FATHER_NAME):
                father_name = val

        alarm_lower = str(alarm).lower()
        
        # =====================================================
        # 🔥 과전압 충전차단 제어 (col 0)
        # =====================================================
        overcharge_keywords = [
            "overcharge protection",
            "overcharge voltage protection"
        ]

        if any(k in alarm_lower for k in overcharge_keywords):
            if trap_oid.startswith("1.3.6.1.4.1.2011.6.164.2.1.3."):

                if trap_oid in alarm_oids:
                    self.set_summary_alarm("과전압 충전차단", True)
                elif trap_oid in resume_oids:
                    self.set_summary_alarm("과전압 충전차단", False)
                
        # =====================================================
        # 🔥 고온 충전차단 제어 (col 1)
        # =====================================================
        high_temp_keywords = [
            "charging high temperature protection",
            "high temperature protection",
            "charge high temperature protection"
        ]

        if any(k in alarm_lower for k in high_temp_keywords):
            if trap_oid.startswith("1.3.6.1.4.1.2011.6.164.2.1.3."):

                if trap_oid in alarm_oids:
                    self.set_summary_alarm("고온 충전차단", True)
                elif trap_oid in resume_oids:
                    self.set_summary_alarm("고온 충전차단", False)                
        
        # =====================================================
        # 🔥 과전류 충전차단 제어 (col 2)
        # =====================================================
        over_current_temp_keywords = [
            "charge overcurrent protection",
            "charging overcurrent protection"
        ]

        if any(k in alarm_lower for k in over_current_temp_keywords):
            if trap_oid.startswith("1.3.6.1.4.1.2011.6.164.2.1.3."):

                if trap_oid in alarm_oids:
                    self.set_summary_alarm("과전류 충전차단", True)
                elif trap_oid in resume_oids:
                    self.set_summary_alarm("과전류 충전차단", False)

        # -----------------------------------------
        # GUI 삽입
        # -----------------------------------------
        row = self.trap_table.rowCount()
        self.trap_table.insertRow(row)

        values = [
            current_time,
            display_trap_oid,
            ordinal,
            alarm,
            level,
            equip_id,
            equip_name,
            father_name
        ]

        for col, val in enumerate(values):

            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            # 발생은 빨강 / 해제는 초록
            if col == 1:
                if trap_oid in alarm_oids:
                    item.setBackground(QColor("#FF6B6B"))
                    item.setForeground(QColor("white"))
                elif trap_oid in resume_oids:
                    item.setBackground(QColor("#B2F2BB"))
                    item.setForeground(QColor("black"))

            self.trap_table.setItem(row, col, item)

        self.trap_table.resizeColumnsToContents()
        self.trap_table.scrollToBottom()
        # ⭐ 1000개 유지
        if self.trap_table.rowCount() > MAX_TRAP_LOG:
            self.trap_table.removeRow(0)

        # ⭐ 로그 파일 저장
        self.write_trap_log(current_time, display_trap_oid, ordinal, alarm, level, equip_id, equip_name, father_name)
        
        # Fault Trap 처리
        self.handle_fault_trap(trap_data)
        
        #print("[TRAP RECEIVED]")
        dprint("SNMP", "[TRAP RECEIVED]")
        for k, v in trap_data.items():            
            dprint("SNMP", f"[{k}] = [{v}]")
 #################################################################################   
 
    def clear_trap_log(self):
        """SNMP Trap 로그 테이블 초기화"""
        if hasattr(self, "trap_table") and self.trap_table is not None:
            self.trap_table.setRowCount(0)

    # ===== BatteryMonitorUI 클래스 내부 =====

    def create_summary_section(self):
        """시스템 요약 정보 + SNMP Trap 로그 병렬 배치"""
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        ####################################################################
        # 1️⃣ 시스템 요약 정보
        ####################################################################
        summary_group = QGroupBox("시스템 요약 정보")
        summary_layout = QVBoxLayout(summary_group)

        self.summary_table = QTableWidget(8, 5)
        table = self.summary_table

        # 🔴 스크롤바 제거
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)        
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)
        # 편집 금지
        table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 🔴 드래그 선택 가능하도록 수정
        table.setSelectionMode(QTableWidget.ExtendedSelection)
        table.setSelectionBehavior(QTableWidget.SelectItems)

        # 🔴 포커스 허용 (복사용)
        table.setFocusPolicy(Qt.StrongFocus)

        # 🔴 컬럼 자동 크기
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)

        # 🔴 컬럼 자동 확장 설정 (추가)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)

        labels = [
            ["설비번호", "운용 관리자", "제조사", "모델명", "시리얼번호"],
            ["Rack 전압[V]", "SOC 충전율[%]", "Max 전압[V]", "Min 전압[V]", "Avg 전압[V]"],
            ["Rack 전류[A]", "충방전 횟수", "Max 온도[℃]", "Min 온도[℃]", "Avg 온도[℃]"],
            ["과전압 충전차단", "고온 충전차단", "과전류 충전차단", "Fuse 상태", "충전 릴레이"]
        ]

        values = [["-" for _ in range(5)] for _ in range(4)]

        LABEL_BG = QColor(220, 235, 255)
        label_font = QFont()
        label_font.setBold(True)

        # 🔥 summary 값 위치 매핑
        self.summary_position_map = {}

        for block in range(4):
            label_row = block * 2
            value_row = label_row + 1

            for col in range(5):

                # ----- 라벨 -----
                label_text = labels[block][col]
                label_item = QTableWidgetItem(label_text)
                label_item.setTextAlignment(Qt.AlignCenter)
                label_item.setBackground(LABEL_BG)
                label_item.setFont(label_font)
                table.setItem(label_row, col, label_item)

                # ----- 값 -----
                value_item = QTableWidgetItem(values[block][col])
                value_item.setTextAlignment(Qt.AlignCenter)
                apply_value_style(value_item, values[block][col])                
                table.setItem(value_row, col, value_item)

                # 위치 저장
                self.summary_position_map[label_text] = (value_row, col)

        # 🔴 컬럼 최소폭 설정 (시리얼번호 컬럼)
        #table.setColumnWidth(4, 180)

        table.resizeColumnsToContents()
        table.resizeRowsToContents()

        # 🔥 내용 기준 고정 크기 계산
        width = table.verticalHeader().width()
        for i in range(table.columnCount()):
            width += table.columnWidth(i)

        height = table.horizontalHeader().height()
        for i in range(table.rowCount()):
            height += table.rowHeight(i)

        table.setFixedSize(width + 2, height + 2)

        summary_layout.addWidget(table)
        summary_layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        summary_group.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        main_layout.addWidget(summary_group)        
        ####################################################################
        # 2️⃣ SNMP Trap 로그
        ####################################################################
        trap_group = QGroupBox("SNMP Trap 로그 (최대 1000개 저장)")
        trap_layout = QVBoxLayout(trap_group)

        self.trap_table = QTableWidget(0, 8)
        trap_headers = [
            "시간",
            "Trap OID",
            "OrdinalNumber",
            "Alarm",
            "Level",
            "EquipID",
            "EquipName",
            "FatherEquipname"
        ]
        self.trap_table.setHorizontalHeaderLabels(trap_headers)
        self.trap_table.verticalHeader().setVisible(False)
        self.trap_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.trap_table.setSelectionBehavior(QTableWidget.SelectRows)

        header = self.trap_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #E7F1FF;
                color: black;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #CCCCCC;
                text-align: center;
            }
        """)
        trap_layout.addWidget(self.trap_table)

        clear_btn = QPushButton("TRAP 로그 전체 삭제")
        clear_btn.clicked.connect(self.clear_trap_log)
        clear_btn.setStyleSheet("""
        QPushButton {
            background-color: #2E86DE;
            color: white;
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1B4F72;
        }
        QPushButton:pressed {
            background-color: #154360;
        }
        """)
        trap_layout.addWidget(clear_btn)

        main_layout.addWidget(trap_group, 1)

        return main_widget


    def create_module_table(self):
        """모듈 상태 + 설치 모듈 순서"""
        BASE_STYLE = """
        QLabel {
            border: 1px solid #3B82F6;
            border-radius: 6px;
            padding: 2px 6px;
            background: #EFF6FF;
            color: #1E40AF;
            font-weight: 500;
            font-size: 12px;
        }
        """
        container = QWidget()
        container_layout = QHBoxLayout(container)

        # -------------------------
        # 모듈 상태 Group
        # -------------------------

        module_group = QGroupBox("모듈 상태")
        module_layout = QHBoxLayout(module_group)

        module_layout.setContentsMargins(0, 0, 0, 0)
        module_layout.setSpacing(0)
        
        headers = ["모듈", "모듈 전압", "셀 전압 Max/Min[V]", "셀 온도 Max/Min[℃]", "경보", "통신상태", "모듈(셀)"]

        LABEL_BG = QColor("#E7F1FF")

        label_font = QFont()
        label_font.setBold(True)

        def create_table(start_index):

            table = QTableWidget(5, len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.NoEditTriggers)

            for col in range(len(headers)):
                header_item = table.horizontalHeaderItem(col)
                header_item.setBackground(LABEL_BG)
                header_item.setFont(label_font)
                header_item.setTextAlignment(Qt.AlignCenter)

            for row in range(5):

                module_no = start_index + row + 1

                table.setItem(row, 0, QTableWidgetItem(f"#{module_no:02d}"))
                table.setItem(row, 1, QTableWidgetItem("-"))
                table.setItem(row, 2, QTableWidgetItem("- / -"))
                table.setItem(row, 3, QTableWidgetItem("- / -"))
                table.setItem(row, 4, QTableWidgetItem("-"))
                table.setItem(row, 5, QTableWidgetItem("-"))

                btn = QPushButton("상세")
                btn.clicked.connect(lambda checked, no=module_no: self.show_module_detail(no))
                table.setCellWidget(row, 6, btn)
                btn.setEnabled(False)

                for col in range(1, 6):
                    item = table.item(row, col)
                    if item:
                        item.setTextAlignment(Qt.AlignCenter)

            table.resizeColumnsToContents()
            table.resizeRowsToContents()

            table.setColumnWidth(2, 120)   # 셀 전압 Max/Min[V]
            table.setColumnWidth(3, 130)   # 셀 온도 Max/Min[℃]
            table.setColumnWidth(4, 50)   # 셀 온도 Max/Min[℃]
            
            header = table.horizontalHeader()
            header.setSectionResizeMode(6, QHeaderView.Fixed)
            table.setColumnWidth(6, 70)
            
            header.setStyleSheet("""
                QHeaderView::section {
                    background-color: #E7F1FF;
                    color: black;
                    font-weight: bold;
                    padding: 4px;
                    border: 1px solid #CCCCCC;
                    text-align: center;
                }
            """)
            table.horizontalHeader().setStretchLastSection(True)
            #table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            
            return table

        self.module_table_left = create_table(0)
        self.module_table_right = create_table(5)

        module_layout.addWidget(self.module_table_left)
        module_layout.addWidget(self.module_table_right)

        # -------------------------
        # 설치 모듈 순서 Group
        # -------------------------

        order_group = QGroupBox("설치 모듈 순서")
        order_layout = QVBoxLayout(order_group)

        self.module_order_labels = []

        for i in range(10, 0, -1):

            label = QLabel(f"{i:02d} : -")            
            label.setMinimumHeight(22)

            label.setStyleSheet(BASE_STYLE)
            label.base_style = BASE_STYLE   # 🔥 반드시 있어야 함
            #label.setStyleSheet("""
            #    QLabel {
            #        border: 1px solid #CCCCCC;
            #        padding-left: 6px;
            #        background-color: #FAFAFA;
            #    }
            #""")

            order_layout.addWidget(label)
            
            # 리스트는 1~10 순서로 저장
            #self.module_order_labels[i-1] = label
            self.module_order_labels.append(label)

        order_layout.addStretch()

        order_group.setFixedWidth(280)

        # -------------------------
        # layout 배치
        # -------------------------

        container_layout.addWidget(module_group,3)
        container_layout.addWidget(order_group,2)

        return container

    def update_module_order_view(self):
        alarm_modules = set()

        for alarm in self.current_alarm_table:

            equip_id = alarm.get("equip")

            if equip_id is None:
                continue

            for m_no, info in self.module_map.items():
                if int(info["equip_id"]) == int(equip_id):
                    alarm_modules.add(m_no)
                    break
                
        for i, pos in enumerate(range(10, 0, -1)):

            module_no = self.module_order[i]

            barcode = None
            has_alarm = False

            # 1️⃣ 통신 데이터 우선
            if module_no and module_no in self.module_map:
                barcode = self.module_map[module_no].get("barcode")
                has_alarm = module_no in alarm_modules

            # 2️⃣ 🔥 profile barcode fallback
            elif module_no and hasattr(self, "module_barcodes"):
                barcode = self.module_barcodes.get(str(module_no))

            # 3️⃣ 출력 처리
            if module_no and barcode:
                txt = f"Rack {pos:02d}번째: {barcode} (모듈{module_no:02d})"

                real_label = self.module_order_labels[i]

                if not hasattr(self, "rack_widgets"):
                    self.rack_widgets = {}

                self.rack_widgets[module_no] = real_label

                self.update_module_order_label(i, module_no, barcode, has_alarm)

            else:
                txt = f"Rack {pos:02d}번째: -"
                self.update_module_order_label(i)

            self.module_order_labels[i].setText(txt)
            
        
    def handle_fault_trap(self, trap_data):

        #print("\n================ TRAP DEBUG START ================")
        dprint("SNMP", "\n================ TRAP DEBUG START ================")
        #print("TRAP DATA:", trap_data)
        dprint("SNMP", "TRAP DATA:", trap_data)

        alarm_oid = "1.3.6.1.4.1.2011.6.164.2.1.3.0.99"
        equip_oid_prefix = "1.3.6.1.4.1.2011.6.164.1.18.1.1.2."
        alarm_oid_prefix = "1.3.6.1.4.1.2011.6.164.1.1.2.100.1.2."

        alarm_text = None
        equip_id = None

        # -----------------------------------
        # Trap OID 파싱
        # -----------------------------------
        for oid, value in trap_data.items():

            #print(f"[TRAP VAR] {oid} = {value}")
            dprint("SNMP", f"[TRAP VAR] {oid} = {value}")

            # Alarm Text
            if oid.startswith(alarm_oid_prefix):
                alarm_text = value
                #print(f"[PARSE] Alarm Text detected: {alarm_text}")
                dprint("SNMP", f"[PARSE] Alarm Text detected: {alarm_text}")

            # Equip ID
            if oid.startswith(equip_oid_prefix):
                equip_id = int(oid.split(".")[-1])
                #print(f"[PARSE] Equip ID detected: {equip_id}")
                dprint("SNMP", f"[PARSE] Equip ID detected: {equip_id}")

        # -----------------------------------
        # 필수 값 체크
        # -----------------------------------
        if alarm_text is None or equip_id is None:
            #print("[ERROR] alarm_text 또는 equip_id 없음")
            #print("alarm_text =", alarm_text)
            #print("equip_id =", equip_id)
            #print("================ TRAP DEBUG END =================\n")
            dprint("SNMP", "[ERROR] alarm_text 또는 equip_id 없음")
            dprint("SNMP", "alarm_text =", alarm_text)
            dprint("SNMP", "equip_id =", equip_id)
            dprint("SNMP", "================ TRAP DEBUG END =================\n")
            return

        # -----------------------------------
        # Cell Fault 파싱
        # -----------------------------------
        #print("[STEP] Parsing Cell Fault from Alarm Text")
        dprint("SNMP", "[STEP] Parsing Cell Fault from Alarm Text")

        m = re.search(r'cell\s*(\d+)\s*fault', alarm_text, re.IGNORECASE)

        if not m:
            #print("[ERROR] 'Cell N Fault' 패턴이 아님:", alarm_text)
            #print("================ TRAP DEBUG END =================\n")
            dprint("SNMP", "[ERROR] 'Cell N Fault' 패턴이 아님:", alarm_text)
            dprint("SNMP", "================ TRAP DEBUG END =================\n")
            return

        cell_no = int(m.group(1))
        #print(f"[PARSE] Cell Number: {cell_no}")
        dprint("SNMP", f"[PARSE] Cell Number: {cell_no}")

        # -----------------------------------
        # equip_id → module_no 찾기
        # -----------------------------------
        #print("[STEP] Searching module_map for equip_id")
        dprint("SNMP", "[STEP] Searching module_map for equip_id")

        module_no = None

        for m_no, info in self.module_map.items():

            #print(f"[CHECK] module {m_no} -> equip_id {info.get('equip_id')}")            
            dprint("SNMP", f"[CHECK] module {m_no} -> equip_id {info.get('equip_id')}")            

            if int(info["equip_id"]) == int(equip_id):
                module_no = m_no
                break

        if module_no is None:
            #print("[ERROR] module_map에서 equip_id 못찾음:", equip_id)
            #print("module_map =", self.module_map)
            #print("================ TRAP DEBUG END =================\n")
            dprint("SNMP", "[ERROR] module_map에서 equip_id 못찾음:", equip_id)
            dprint("SNMP", "module_map =", self.module_map)
            dprint("SNMP", "================ TRAP DEBUG END =================\n")
            return

        #print(f"[PARSE] module_no found: {module_no}")
        dprint("SNMP", f"[PARSE] module_no found: {module_no}")

        # -----------------------------------
        # module_data 조회
        # -----------------------------------
        module_info = self.module_map.get(module_no)

        equip_id = module_info["equip_id"]

        module_data = self.module_data.get(equip_id)

        if not module_data:
            #print("[ERROR] module_data 없음 equip_id =", equip_id)
            #print("module_data keys =", list(self.module_data.keys()))
            #print("================ TRAP DEBUG END =================\n")
            dprint("SNMP", "[ERROR] module_data 없음 equip_id =", equip_id)
            dprint("SNMP", "module_data keys =", list(self.module_data.keys()))
            dprint("SNMP", "================ TRAP DEBUG END =================\n")
            return

        #print("[STEP] module_data found")
        dprint("SNMP", "[STEP] module_data found")

       # -----------------------------------
        # 셀 데이터 조회
        # -----------------------------------

        cells = module_data.get("cells", [])
        temps = module_data.get("temps", [])

        if cell_no-1 >= len(cells) or cell_no-1 >= len(temps):

            #print(f"[ERROR] Cell index out of range : {cell_no}")
            #print("cells length =", len(cells))
            #print("temps length =", len(temps))
            #print("================ TRAP DEBUG END =================\n")
            dprint("SNMP", f"[ERROR] Cell index out of range : {cell_no}")
            dprint("SNMP", "cells length =", len(cells))
            dprint("SNMP", "temps length =", len(temps))
            dprint("SNMP", "================ TRAP DEBUG END =================\n")

            return

        volt = cells[cell_no-1]
        temp = temps[cell_no-1]

        #print(f"[CELL DATA] Volt = {volt}")
        #print(f"[CELL DATA] Temp = {temp}")
        dprint("SNMP", f"[CELL DATA] Volt = {volt}")
        dprint("SNMP", f"[CELL DATA] Temp = {temp}")

        # -----------------------------
        # 중복 Fault 체크
        # -----------------------------
        for fault in self.fault_list:
            if fault["module"] == module_no and fault["cell"] == cell_no:
                #print("[DUPLICATE] 이미 fault 존재 → 추가 안함")
                #print("================ TRAP DEBUG END =================\n")
                dprint("SNMP", "[DUPLICATE] 이미 fault 존재 → 추가 안함")
                dprint("SNMP", "================ TRAP DEBUG END =================\n")
                return
        
        # -----------------------------------
        # Fault 추가
        # -----------------------------------

        #print("[STEP] Adding fault to table")
        dprint("SNMP", "[STEP] Adding fault to table")

        self.add_fault(module_no, cell_no, volt, temp)

        #print("[SUCCESS] Fault added")
        dprint("SNMP", "[SUCCESS] Fault added")
        #print("================ TRAP DEBUG END =================\n")
        dprint("SNMP", "================ TRAP DEBUG END =================\n")
    
    def refresh_fault_numbers(self):

        for i, fault in enumerate(self.fault_list):
            fault["no"] = i + 1
            item = self.fault_table.item(i, 0)
            if item:
                item.setText(f"#{i+1:02d}")
                
    def delete_fault(self):

        button = self.sender()
        
        if not button:
            return

        index = self.fault_table.indexAt(button.pos())

        if not index.isValid():
            return

        row = index.row()

        #print(f"[FAULT DELETE] Row {row}")
        dprint("MODULE", f"[FAULT DELETE] Row {row}")

        # fault_list에서도 삭제
        if row < len(self.fault_list):
            del self.fault_list[row]

        # 테이블 행 삭제
        self.fault_table.removeRow(row)

        # 번호 다시 정렬
        self.refresh_fault_numbers()
    
    def add_fault(self, module_no, cell_no, volt, temp):

        fault_index = len(self.fault_list) + 1

        fault = {
            "no": fault_index,
            "module": module_no,
            "cell": cell_no,
            "volt": volt,
            "temp": temp
        }

        self.fault_list.append(fault)

        row = self.fault_table.rowCount()
        self.fault_table.insertRow(row)

        # --------------------------------
        # Board hardware fault 처리
        # --------------------------------
        if cell_no == 0:

            values = [
                f"#{fault_index:02d}",
                str(module_no),
                "(Board hardware fault)",
                "-",
                "-"
            ]

            bg_color = QColor("#555555")   # 어두운 회색
            fg_color = QColor("white")

        else:

            values = [
                f"#{fault_index:02d}",
                str(module_no),
                str(cell_no),
                f"{volt:.2f}",
                f"{temp:.1f}"
            ]

            bg_color = QColor("#F25F5C")
            fg_color = QColor("white")

        # --------------------------------
        # 테이블 삽입
        # --------------------------------
        for col, val in enumerate(values):

            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)

            # -----------------------------
            # Board hardware fault
            # -----------------------------
            if cell_no == 0:

                # Fault / Module 컬럼은 기존 스타일 유지
                if col in (0, 1):
                    item.setBackground(QColor("#F25F5C"))
                    item.setForeground(QColor("white"))

                # Cell / Volt / Temp 는 어두운색
                else:
                    item.setBackground(QColor("#555555"))
                    item.setForeground(QColor("white"))

            else:
                # 기존 Fault 스타일
                item.setBackground(QColor("#F25F5C"))
                item.setForeground(QColor("white"))

            self.fault_table.setItem(row, col, item)
        # --------------------------------
        # 삭제 버튼
        # --------------------------------
        btn_delete = QPushButton("삭제")
        btn_delete.clicked.connect(self.delete_fault)

        self.fault_table.setCellWidget(row, len(values), btn_delete)
        
    def create_fault_table(self):

        group = QGroupBox("고장 정보")
        layout = QVBoxLayout(group)

        # 컬럼 6개 (Delete 추가)
        self.fault_table = QTableWidget(0, 6)

        headers = [
            "Fault",
            "고장 모듈 No",
            "고장 셀 No",
            "고장 셀 전압[V]",
            "고장 셀 온도[℃]",
            "삭제"
        ]

        self.fault_table.setHorizontalHeaderLabels(headers)
        self.fault_table.verticalHeader().setVisible(False)

        # Header 스타일
        for col in range(len(headers)):
            header_item = self.fault_table.horizontalHeaderItem(col)
            header_item.setBackground(QColor("#FFF3B0"))
            header_item.setFont(QFont("", weight=QFont.Bold))
            header_item.setTextAlignment(Qt.AlignCenter)

        # 🔴 Header 스타일 (노란색)
        self.fault_table.horizontalHeader().setStyleSheet(
            "QHeaderView::section { background-color: #FFF3B0; font-weight: bold; }"
        )
    
        self.fault_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 삭제 컬럼 width 고정 (UI 안정)
        self.fault_table.setColumnWidth(5, 80)

        layout.addWidget(self.fault_table)

        return group

    #############################################################################
    def create_connection_panel(self):
        group = QGroupBox("Battery System 접속 설정")
        layout = QHBoxLayout(group)
        layout.addWidget(QLabel("IP"))
        self.ip_edit = QLineEdit("60.22.0.0")
        self.ip_edit.setFixedWidth(140)
        layout.addWidget(self.ip_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Port"))
        self.port_edit = QLineEdit("161")
        self.port_edit.setFixedWidth(70)
        layout.addWidget(self.port_edit)
        layout.addSpacing(20)
        layout.addWidget(QLabel("GET"))
        self.get_comm_edit = QLineEdit("sktlfp48r")
        self.get_comm_edit.setFixedWidth(100)
        layout.addWidget(self.get_comm_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("SET"))
        self.set_comm_edit = QLineEdit("sktlfp48w")
        self.set_comm_edit.setFixedWidth(100)
        layout.addWidget(self.set_comm_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("TRAP"))
        self.trap_comm_edit = QLineEdit("sktlfp48r")
        self.trap_comm_edit.setFixedWidth(100)
        layout.addWidget(self.trap_comm_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("TRAP Port"))
        self.trap_port_edit = QLineEdit("162")
        self.trap_port_edit.setFixedWidth(70)
        layout.addWidget(self.trap_port_edit)
        layout.addSpacing(20)
        self.connect_btn = QPushButton("접속시작")
        self.connect_btn.setFixedWidth(80)
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        layout.addWidget(self.connect_btn)
        
        # 🔵 접속 상태 표시 (접속 버튼 옆)
        layout.addSpacing(10)

        self.bmu_label = QLabel("접속상태")
        layout.addWidget(self.bmu_label)

        self.status_circle = QLabel()
        self.status_circle.setFixedSize(15, 15)
        self.status_circle.setStyleSheet(
            "background-color: #CCCCCC; border-radius: 7px; border: 1px solid #999999;"
        )
        
        self.btn_module_order = QPushButton("설치 모듈 순서 설정")
        self.btn_module_order.setFixedHeight(40)

        self.btn_module_order.setStyleSheet("""
        QPushButton {
            background-color: #2E86DE;
            color: white;
            border-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            padding: 6px 12px;
        }

        QPushButton:hover {
            background-color: #3498DB;
        }

        QPushButton:pressed {
            background-color: #21618C;
        }

        /* 🔽 비활성 상태 */
        QPushButton:disabled {
            background-color: #AEB6BF;
            color: #E5E7E9;
        }
        """)
        self.btn_module_order.setEnabled(False)
        self.btn_module_order.clicked.connect(self.open_module_order_dialog)                

        layout.addWidget(self.status_circle)        
        layout.addWidget(self.btn_module_order)
        
        layout.addStretch()
        
        return group

    def save_site_info(self):

        site = self.site_edit.text().strip()
        system = self.system_edit.text().strip()

        equip = self.equip_edit.text().strip()
        manager = self.manager_edit.text().strip()
        maker = self.maker_edit.text().strip()
        model = self.model_edit.text().strip()
        serial = self.serial_edit.text().strip()

        if not site or not system:
            QMessageBox.warning(self, "저장 오류", "설치 장소와 시스템 이름을 입력하세요.")
            return

        safe_name = re.sub(r"[^\w\-]", "_", f"{site}_{system}")
        new_profile_path = os.path.join(os.path.dirname(self.profile_path), safe_name + ".ini")

        try:

            if self.profile_path != new_profile_path:
                self.settings.sync()

                if os.path.exists(self.profile_path):
                    os.rename(self.profile_path, new_profile_path)

                self.profile_path = new_profile_path
                self.settings = QSettings(self.profile_path, QSettings.IniFormat)

            # ==============================
            # 설정 저장
            # ==============================
            self.settings.setValue("site", site)
            self.settings.setValue("system", system)
            self.settings.setValue("equip", equip)
            self.settings.setValue("manager", manager)
            self.settings.setValue("maker", maker)
            self.settings.setValue("model", model)
            self.settings.setValue("serial", serial)

            self.settings.sync()

            # ==============================
            # 시스템 요약 정보 표시
            # ==============================
            self.summary_table.setItem(1, 0, QTableWidgetItem(equip))
            self.summary_table.setItem(1, 1, QTableWidgetItem(manager))
            self.summary_table.setItem(1, 2, QTableWidgetItem(maker))
            self.summary_table.setItem(1, 3, QTableWidgetItem(model))
            self.summary_table.setItem(1, 4, QTableWidgetItem(serial))

            # ==============================
            # 입력창 CLEAR
            # ==============================
            self.equip_edit.clear()
            self.manager_edit.clear()
            self.maker_edit.clear()
            self.model_edit.clear()
            self.serial_edit.clear()

            QMessageBox.information(self, "저장 완료", "시스템 정보가 저장되었습니다.")

        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"저장 중 오류 발생:\n{str(e)}")


    def load_site_info(self):

        site = self.settings.value("site", "")
        system = self.settings.value("system", "")

        equip = self.settings.value("equip", "")
        manager = self.settings.value("manager", "")
        maker = self.settings.value("maker", "")
        model = self.settings.value("model", "")
        serial = self.settings.value("serial", "")

        # 🔥 접속 정보 로드
        self.ip_edit.setText(self.settings.value("ip", "10.30.41.67"))
        self.port_edit.setText(self.settings.value("port", "161"))
        self.get_comm_edit.setText(self.settings.value("get_comm", "sktlfp48r"))
        self.set_comm_edit.setText(self.settings.value("set_comm", "sktlfp48w"))
        self.trap_comm_edit.setText(self.settings.value("trap_comm", "sktlfp48r"))
        self.trap_port_edit.setText(self.settings.value("trap_port", "162"))
        # 상단 표시
        self.site_edit.setText(site)
        self.system_edit.setText(system)
        
        # ==============================
        # 시스템 요약 정보 테이블 표시
        # ==============================
        self.summary_table.setItem(1, 0, QTableWidgetItem(equip))
        self.summary_table.setItem(1, 1, QTableWidgetItem(manager))
        self.summary_table.setItem(1, 2, QTableWidgetItem(maker))
        self.summary_table.setItem(1, 3, QTableWidgetItem(model))
        self.summary_table.setItem(1, 4, QTableWidgetItem(serial))

    def create_header(self):

        group = QGroupBox()

        # 기존 HBox → VBox 로 변경 (두 줄 layout을 만들기 위해)
        layout = QVBoxLayout(group)

        # ===============================
        # 첫번째 줄 (기존 코드 그대로)
        # ===============================
        left_layout = QHBoxLayout()

        left_layout.addWidget(QLabel("설치 장소"))

        self.site_edit = QLineEdit()
        self.site_edit.setFixedWidth(180)
        left_layout.addWidget(self.site_edit)

        left_layout.addSpacing(10)

        left_layout.addWidget(QLabel("축전지명"))

        self.system_edit = QLineEdit()
        self.system_edit.setFixedWidth(202)
        left_layout.addWidget(self.system_edit)
        
        self.btn_alarm_popup = QPushButton("발생된 알람 보기")
        self.btn_alarm_popup.setEnabled(False)
        self.btn_alarm_popup.clicked.connect(self.show_alarm_popup)
        
        self.alarm_list_btn = QPushButton("※ 정의된 알람 리스트")
        self.alarm_list_btn.setStyleSheet("""
        QPushButton {
            background-color: #A8E6CF;
            color: #2c3e50;
            border-radius: 6px;
            padding: 3px 12px;
            font-weight: bold;
        }

        QPushButton:hover {
            background-color: #8ED9BE;
        }

        QPushButton:pressed {
            background-color: #7CCFB0;
        }
        """)
        self.alarm_list_btn.clicked.connect(self.show_alarm_list)        

        left_layout.addSpacing(100)
        left_layout.addWidget(self.btn_alarm_popup)
        left_layout.addWidget(self.alarm_list_btn)
        
        self.status_label = QLabel()

        font = QFont("Consolas")   # fallback 없이 단일 폰트
        font.setPointSize(10)
        font.setBold(True)
        self.status_label.setFont(font)

        # 🔥 핵심 1: HTML 끄기
        self.status_label.setTextFormat(Qt.RichText)

        # 🔥 핵심 2: 크기 고정 (아주 중요)
        self.status_label.setFixedWidth(520)

        # 🔥 핵심 3: 좌측 정렬
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        fm = QFontMetrics(font)

        height = fm.height() + 10   # 🔥 여유 충분히

        self.status_label.setMinimumHeight(height)
        #self.status_label.setMaximumHeight(height + 2)
        # =========================
        # SNMP TX / RX 상태 표시
        # =========================

        self.tx_led = QLabel()
        self.tx_led.setFixedSize(20, 10)
        self.tx_led.setStyleSheet(
            "background:#505050;border-radius:4px;"
        )

        self.rx_led = QLabel()
        self.rx_led.setFixedSize(20, 10)
        self.rx_led.setStyleSheet(
            "background:#505050;border-radius:4px;"
        )

        left_layout.addStretch()

        resource_widget = QWidget()
        resource_layout = QHBoxLayout(resource_widget)

        resource_layout.setContentsMargins(4, 2, 4, 2)
        resource_layout.setSpacing(4)

        resource_layout.addWidget(self.status_label)

        # 🔥 고정 높이 제거 → 최소 높이로 변경
        resource_widget.setMinimumHeight(height + 6)        

        resource_widget.setStyleSheet("""
        QWidget {
            background-color: #1E1E1E;   /* 다크 배경 */
            border-radius: 3px;
            padding: 0px 2px;
        }
        """)
        
        left_layout.addWidget(resource_widget)

        left_layout.addSpacing(20)

        layout.addLayout(left_layout)

        # ==================================
        # 두번째 줄 (신규 입력칸 추가)
        # ==================================
        info_layout = QHBoxLayout()

        info_layout.addWidget(QLabel("설비번호"))
        self.equip_edit = QLineEdit()
        self.equip_edit.setFixedWidth(120)
        info_layout.addWidget(self.equip_edit)

        info_layout.addSpacing(10)

        info_layout.addWidget(QLabel("운용 관리자"))
        self.manager_edit = QLineEdit()
        self.manager_edit.setFixedWidth(120)
        info_layout.addWidget(self.manager_edit)

        info_layout.addSpacing(10)

        info_layout.addWidget(QLabel("제조사"))
        self.maker_edit = QLineEdit()
        self.maker_edit.setFixedWidth(120)
        info_layout.addWidget(self.maker_edit)

        info_layout.addSpacing(10)

        info_layout.addWidget(QLabel("모델명"))
        self.model_edit = QLineEdit()
        self.model_edit.setFixedWidth(120)
        info_layout.addWidget(self.model_edit)

        info_layout.addSpacing(10)

        info_layout.addWidget(QLabel("시리얼번호"))
        self.serial_edit = QLineEdit()
        self.serial_edit.setFixedWidth(140)
        info_layout.addWidget(self.serial_edit)

        info_layout.addSpacing(10)

        # 저장 버튼 (여기로 이동)
        save_btn = QPushButton("저장")
        save_btn.setFixedWidth(60)
        save_btn.clicked.connect(self.save_site_info)
        info_layout.addWidget(save_btn)

        # ==============================
        # 시스템 리소스 표시
        # ==============================
        info_layout.addWidget(self.tx_label)
        info_layout.addWidget(self.tx_led)

        info_layout.addSpacing(10)

        info_layout.addWidget(self.rx_label)
        info_layout.addWidget(self.rx_led)

        info_layout.addSpacing(10)

        info_layout.addWidget(self.update_time_label)

        info_layout.addStretch()

        layout.addLayout(info_layout)

        return group

    # ===== ping, module table, summary, fault table 등 기존 코드 그대로 유지 =====
    # 기존 함수들 그대로 붙이면 됩니다 (on_connect_clicked, start_ping_monitoring, stop_ping_monitoring, show_module_detail 등)
    # 편의상 생략. 전체 코드에 그대로 붙이면 됩니다.


class AlarmListDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("정의된 알람 리스트")
        self.resize(650, 500)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(2)

        self.table.setHorizontalHeaderLabels([
            "Alarm Name",
            "Description"
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.table.setStyleSheet("""
        QHeaderView::section {
            background-color: #DFF5EC;
            color: #2c3e50;
            padding: 6px;
            border: 1px solid #C8E6DC;
            font-weight: bold;
        }
        """)
        
        layout.addWidget(self.table)

        self.load_alarms()
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

        # 헤더 포함 전체 폭 계산
        width = (
            self.table.verticalHeader().width()
            + sum(self.table.columnWidth(i) for i in range(self.table.columnCount()))
            + self.table.frameWidth() * 2
        )

        # 헤더 포함 전체 높이 계산
        height = (
            self.table.horizontalHeader().height()
            + sum(self.table.rowHeight(i) for i in range(self.table.rowCount()))
            + self.table.frameWidth() * 2
        )

        # 다이얼로그 크기 조정
        self.resize(width + 40, min(height + 80, 600))

    def load_alarms(self):

        alarms = [

            ("Overdischarge Protection",                "과방전으로 인해 보호 모드가 활성화된 상태"),
            ("Charging Overcurrent Protection",         "충전 전류가 허용 범위를 초과하여 보호 모드가 활성화된 상태"),
            ("Heavy load Overcurrent Protection",       "방전 중 부하 증가로 과전류 보호 모드가 활성화된 상태"),
            ("Discharge Overcurrent Protection",        "방전 전류가 허용 범위를 초과하여 보호 모드가 활성화된 상태"),
            ("Upgrade failure",                         "축전지 BMS 펌웨어 업그레이드가 실패한 상태"),
            ("Busbar overvoltage protection",           "축전지 버스바 전압이 허용 범위를 초과하여 보호 모드가 활성화된 상태"),
            ("Discharge low temperature protection",    "저온 상태에서 방전을 보호하기 위해 보호 모드가 활성화된 상태"),
            ("Charging low temperature protection",     "저온 상태에서 충전을 보호하기 위해 보호 모드가 활성화된 상태"),
            ("Input reverse connection",                "축전지 입력 전압의 극성이 반대로 연결된 상태"),
            ("Abnormal shutdown",                       "축전지 시스템이 비정상적으로 종료된 상태"),
            ("Unlock failure",                          "축전지 잠금 해제 명령이 실패한 상태"),
            ("Board hardware fault",                    "BMS 제어 보드의 하드웨어 오류가 발생한 상태 (모듈 교체 필요)"),
            ("Cell 1 Fault",                            "셀 1 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 2 Fault",                            "셀 2 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 3 Fault",                            "셀 3 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 4 Fault",                            "셀 4 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 5 Fault",                            "셀 5 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 6 Fault",                            "셀 6 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 7 Fault",                            "셀 7 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 8 Fault",                            "셀 8 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 9 Fault",                            "셀 9 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 10 Fault",                           "셀 10 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 11 Fault",                           "셀 11 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 12 Fault",                           "셀 12 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 13 Fault",                           "셀 13 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 14 Fault",                           "셀 14 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 15 Fault",                           "셀 15 이상 상태 발생 (모듈 교체 필요)")

        ]

        self.table.setRowCount(len(alarms))

        for row, (name, desc) in enumerate(alarms):

            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(desc))


  
# ======================
# 실행부
# ======================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    profile_dir = os.path.join(os.getcwd(), "profiles")
    dialog = ProfileDialog(profile_dir)

    # profiles 폴더가 비어있으면 바로 신규 생성
    if not os.path.exists(profile_dir) or not os.listdir(profile_dir):
        dialog.create_new_profile()
        if not dialog.new_profile_data:
            sys.exit()
    else:
        if not dialog.exec():
            sys.exit()

    if dialog.selected_profile_path:
        profile_path = dialog.selected_profile_path
        win = BatteryMonitorUI(profile_path)
    else:
        site, system = dialog.new_profile_data
        safe_name = re.sub(r"[^\w\-]", "_", f"{site}_{system}")
        profile_path = os.path.join(profile_dir, safe_name + ".ini")
        win = BatteryMonitorUI(profile_path, dialog.new_profile_data)

    win.show()
    sys.exit(app.exec())
