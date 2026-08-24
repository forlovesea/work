"""
*실행프로그램 명령어
 cd D:\proj\GIT_HUB\work\RMS_Server
 pyinstaller --clean --noconsole --onefile --icon=./battery#2.ico --collect-all PySide6 --name TBC1000B_감시프로그램_V2.0.8 TBC1000B_감시프로그램_V2.0.8.py
*최적화 실행 파일 옵션
pyinstaller --noconfirm --onefile --icon=./battery#2.ico --add-data "alarm.wav;." --windowed --add-data "install_battery.png;." --add-data "battery#3.ico;." --clean --strip --noupx --exclude-module tkinter --exclude-module matplotlib --exclude-module numpy --exclude-module pandas --exclude-module scipy --exclude-module IPython --exclude-module jupyter --exclude-module notebook --exclude-module test --exclude-module unittest --exclude-module email --exclude-module http --exclude-module PyQt5 --exclude-module PyQt5.QtCore --exclude-module PyQt5.QtGui --exclude-module PyQt5.QtWidgets --name=Final_v0 TBC1000B_감시프로그램_V3.2.2.py TBC1000B_감시프로그램_V3.2.2.py
Read :  sktlfp48r
Write : sktlfp48w
Trap :  sktlfp48r


*Windows PowerShell 실행 후, 
- 윈도우 TRAP 중지.
Set-Service SNMPTRAP -StartupType Disabled
Stop-Service SNMPTRAP
Stop-Process -Name "MgWTrap3" -Force
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ※프로그램 버전별 목표 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
※최신버전
☆ 원격 차단, SOC충전제한 기능을 제외한 버전.
- iIOT Gateway 버전으로 권장.

☆ v3.0.9 최종 SKT 배포 가능 수준.
======================================================================================
☆ 로그파일명 설명.
Operation_data_2026-07-28_14-41-18_469981_2026-07-28.xlsx
│              │          │        │      └─ 데이터가 기록된 날짜
│              │          │        └─ 중복 방지용 마이크로초
│              │          └─ 기록을 시작한 시각
│              └─ 기록을 시작한 날짜
└─ 운전 데이터 파일
해당 파일을 해석하면:
기록 시작 날짜: 2026-07-28
기록 시작 시각: 14:41:18
고유 식별값: 469981
실제 데이터 기록 날짜: 2026-07-28

마지막 날짜가 별도로 있는 이유는 하나의 기록 작업이 여러 날 이어질 수 있기 때문입니다. 
예를 들어 다음 날이 되면:
Operation_data_2026-07-28_14-41-18_469981_2026-07-29.xlsx
처럼 동일한 기록 작업임을 나타내는 시작 시각은 유지되고, 
실제 기록 날짜만 변경됩니다. 
469981은 같은 초에 기록을 다시 시작해도 파일이 덮어써지지 않게 하는 마이크로초 값입니다.
======================================================================================
* 2026.04.10 기준 : v3.0.2
* 2026.07.28 기준 : v3.0.9 

V1.1.1 -> Single System Moninor 용
v1.2.2 -> Multy Instance System Monitor 용
v1.2.2 -> Multy Instance는 (v2.x.x) 버전업  ->v2.0.7
v2.0.8 -> 종료 시 개선(v3.0.1 Merge).
v2.2.0 -> 충전전류제한 설정(set버튼 추가)
v2.4.0 -> v2.x.x 정식 버전 


v3.0.1  -> Multy Instance + snmp 설정
v3.0.2  -> snmp 설정(EPO 버튼) 추가 예정 (v2.2.0 추가 부분 merge)
v3.0.3  -> Aging 시 Queue full 나는 문제 수정, 모듈 상태 초기화 버튼 추가.
v3.0.4  -> 프로그램 종료 시, 쓰레드 처리.
v3.0.5  -> 전체적인 UI 수정 및 Polling 시간 변경.
v3.0.6  -> SOC 충전전류제한 관련 GET/SET SNMP 적용. 
v3.0.7  -> 원격차단 관련 GET/SET SNMP 적용.
v3.0.8  -> 전체적인 UI 밸런스 수정.
v3.0.9  -> 축전지 원격 차단 적용. 
v3.0.10 -> 운전 데이타 로그 기록 추가.
v3.0.11 -> Master -> Slave 간 Trap 패킷 분배 및 기타 UI 처리 개선.
v3.0.11 -> v3.2.0 으로 정식 Release
v3.2.1  -> skt,pantech logo 추가, snmp port timeout, bind listen port 실패 시 팝업 창으로 원인 제공.
v3.2.3  -> 기타 GUI 버그 수정.
############################################################################################################################################
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
import socket
import json
import random
import queue
import math
import shutil

from datetime import datetime, timedelta
from collections import deque
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QRadioButton, QLineEdit,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QFormLayout, QMessageBox, QSizePolicy, QHeaderView,
    QComboBox, QToolTip, QScrollArea, QGraphicsDropShadowEffect,
    QProgressBar, QCheckBox, QGridLayout, QSpinBox
)
from PySide6.QtCore import Qt, QTimer, QDateTime, QThread, Signal, QSettings, QEvent, QPoint
from PySide6.QtGui import QColor, QFont, QPixmap, QFontMetrics, QIcon, QCursor
from pysnmp.hlapi import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity,
    getCmd, bulkCmd, setCmd
)

from pysnmp.entity import engine, config
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.proto.rfc1902 import Integer32, Unsigned32
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

# =======================================================================================================================
# Application Info
# =======================================================================================================================
APP_NAME = "TBC1000B-NDA1/IoT Gateway Battery Monitoring System(Base SNMPv2)"

VERSION_MAJOR = 3
VERSION_MINOR = 2
VERSION_PATCH = 4

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

def is_first_instance():
    count = 0
    current_pid = os.getpid()

    for p in psutil.process_iter(['pid', 'name']):
        try:
            if p.info['pid'] == current_pid:
                continue

            name = p.info['name']
            if name and "TBC1000B" in name:
                count += 1

        except:
            pass

    return count == 0


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

        self.setWindowTitle("모듈 설치 순서 설정")
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
                            # 빈 설치 위치(None)는 콤보박스의 "-" 항목과 매칭된다.
                            # 이 경우 숫자 형식(:02d)을 적용하면 TypeError가 발생하므로
                            # 실제 모듈 번호가 선택된 경우에만 표시 문구를 갱신한다.
                            if saved_module is not None:
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
        # 초기화 / 저장 버튼
        # ==============================
        button_layout = QHBoxLayout()

        btn_reset = QPushButton("초기화")
        btn_reset.clicked.connect(self.reset_order)

        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_order)

        button_layout.addWidget(btn_reset)
        button_layout.addWidget(btn_save)
        layout.addLayout(button_layout)

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

    def reset_order(self):

        self.parent_ui.reset_module_order()

        # 팝업의 선택 상태도 즉시 초기 상태로 표시한다.
        for combo in self.combo_boxes:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)

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
        if self.sock:
            self.sock.close()
        
        self.timer.stop()
        self.quit()
        self.wait(2000)


# ======================
# Module 상세정보 다이얼로그
# ======================
class ModuleDetailDialog(QDialog):
    def __init__(self, module_no, parent=None):
        super().__init__(parent)

        self.module_no = module_no
        self.parent_ui = parent

        # 🔥 추가 (핵심)
        self.is_master = False
        if parent and hasattr(parent, "is_master"):
            self.is_master = parent.is_master

        self.setWindowTitle(f"모듈 #{module_no:02d} 상세정보")
        self.setModal(True)
        self.resize(520, 450)

        layout = QVBoxLayout(self)
        # 🔴 상단 우측 시간 표시
        top_layout = QHBoxLayout()

        self.label_update_time = QLabel("업데이트: -")
        self.label_update_time.setAlignment(Qt.AlignRight)

        top_layout.addStretch()
        top_layout.addWidget(self.label_update_time)

        layout.addLayout(top_layout)
        
        layout.setSpacing(3)
        layout.setContentsMargins(5,5,5,5)
        
        # ======================================================
        # 1️⃣ module_no → equip_id 매핑
        # ======================================================
        module_info = self.parent_ui.module_map.get(module_no)        

        if not module_info:
            QMessageBox.warning(self, "데이터 없음", "모듈 정보를 찾을 수 없습니다.")
            return

        equip_id    = module_info.get("equip_id")
        swver_txt   = module_info.get("swver") or "-"
        model_txt   = module_info["model"]
        barcode_txt = module_info["barcode"]
            
        if equip_id is None:
            QMessageBox.warning(self, "데이터 없음", "해당 모듈의 Equip ID를 찾을 수 없습니다.")
            return       

        row_index = module_info["row_index"]
        module_data = self.parent_ui.module_data.get(row_index)
            
        if not module_data:
            QMessageBox.warning(self, "데이터 없음", "SNMP 데이터가 아직 수신되지 않았습니다.")
            return

        # ======================================================
        # 2️⃣ 상단 정보 영역
        # ======================================================
        info_group = QGroupBox(
            f"축전지 모듈 #{module_no:02d} (SW버전: {swver_txt})"
        )
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
        current = module_data.get("current")        
        soc = module_data.get("soc")
        soh = module_data.get("soh")

        self.label_voltage = QLabel(f"1.전압: {volt:.1f} V" if volt is not None else "1.전압: -")        
        self.label_current = QLabel(f"2.전류: {current:.1f} A" if current is not None else "2.전류: -")
        self.label_status = QLabel(f"3.상태: {status_text}" if status is not None else "3.: -")
        self.label_soc = QLabel(f"4.SOC: {soc} %" if soc is not None else "4.SOC: -")
        self.label_soh = QLabel(f"5.SOH: {soh} %" if soh is not None else "5.SOH: -")        
        if barcode_txt is not None:
            self.label_barcode = QLabel(f'6.바코드: <span style="color:red;">{barcode_txt}</span>')
        else:
            self.label_barcode = QLabel('6.바코드: <span style="color:red;">-</span>')
        # 🔹 마우스 드래그 선택 + 복사 가능
        self.label_barcode.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label_cell_legend = QLabel(
            '※ 셀 전압: '
            '<span style="background-color:#D3F9D8;"> 최고 </span> '
            '<span style="background-color:#FFE3E3;"> 최저 </span> '
            '&nbsp;&nbsp;&nbsp;'
            '※ 온도: '
            '<span style="background-color:#FFF9C4;"> 최고 </span> '
            '<span style="background-color:#FF4D4D; color:white;"> 60℃ 이상 </span>'
        )
        info_layout.addWidget(self.label_voltage)
        info_layout.addWidget(self.label_current)
        info_layout.addWidget(self.label_status)
        info_layout.addWidget(self.label_soc)
        info_layout.addWidget(self.label_soh)
        info_layout.addWidget(self.label_barcode)
        info_layout.addWidget(self.label_cell_legend)
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
        
        self.resize(520, 650)
        self.setMinimumSize(520, 600)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        layout.addWidget(self.table)

        # ======================================================
        # 4️⃣ 버튼
        # ======================================================
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
        # 🔴 3초 주기 업데이트
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(3000)

        # 🔴 최초 1회 실행
        self.update_data()
    
    def closeEvent(self, event):
        event.accept()
        
    def update_data(self):
        module_info = self.parent_ui.module_map.get(self.module_no)
        if not module_info:
            return

        row_index = module_info["row_index"]
        module_data = self.parent_ui.module_data.get(row_index)

        if not module_data:
            return

        status_map = {
            0: "Online", 1: "Offline", 2: "Sleep", 3: "Disconnect",
            4: "Charge", 5: "Discharge", 6: "Standby", 255: "Unknown"
        }

        status = module_data.get("status")
        status_text = status_map.get(status, "Unknown")
        volt = module_data.get("volt")
        current = module_data.get("current")
        soc = module_data.get("soc")
        soh = module_data.get("soh")

        # 🔴 상단 라벨 업데이트
        self.label_voltage.setText(f"1.전압: {volt:.1f} V" if volt is not None else "1.전압: -")
        self.label_current.setText(f"2.전류: {current:.1f} A" if current is not None else "2.전류: -")
        self.label_status.setText(f"3.상태: {status_text}")
        self.label_soc.setText(f"4.SOC: {soc} %" if soc is not None else "4.SOC: -")
        self.label_soh.setText(f"5.SOH: {soh} %" if soh is not None else "5.SOH: -")

        module_info = self.parent_ui.module_map.get(self.module_no)
        barcode_txt = module_info.get("barcode") if module_info else None

        if barcode_txt:
            self.label_barcode.setText(f'6.바코드: <span style="color:red;">{barcode_txt}</span>')
        else:
            self.label_barcode.setText('6.바코드: <span style="color:red;">-</span>')

        # 🔴 테이블 업데이트
        cells = module_data.get("cells", [None]*15)
        temps = module_data.get("temps", [None]*15)

        valid_cells = [v for v in cells if v is not None]
        max_v = max(valid_cells) if valid_cells else None
        min_v = min(valid_cells) if valid_cells else None

        valid_temps = [t for t in temps if t is not None]
        max_t = max(valid_temps) if valid_temps else None

        for row in range(15):

            volt_value = cells[row]
            volt_text = f"{volt_value:.2f}" if volt_value is not None else "-"
            volt_item = self.table.item(row, 1)
            temp_item = self.table.item(row, 2)

            if not volt_item or not temp_item:
                continue

            volt_item.setBackground(QColor("white"))
            temp_item.setBackground(QColor("white"))

            volt_item.setText(volt_text)

            if not volt_item or not temp_item:
                continue
            
            if volt_value is not None:
                if max_v is not None and volt_value == max_v:
                    volt_item.setBackground(QColor("#D3F9D8"))
                elif min_v is not None and volt_value == min_v:
                    volt_item.setBackground(QColor("#FFE3E3"))

            temp_value = temps[row]
            temp_text = f"{temp_value:.1f}" if temp_value is not None else "-"
            temp_item = self.table.item(row, 2)
            temp_item.setText(temp_text)

            if temp_value is not None:
                if temp_value >= 60:
                    temp_item.setBackground(QColor("#FF4D4D"))  # 최우선
                elif max_t is not None and temp_value == max_t:
                    temp_item.setBackground(QColor("#FFF9C4"))

        # 🔴 시간 업데이트
        now = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.label_update_time.setText(f"업데이트: {now}")


class AllModuleDetailDialog(QDialog):
    """개별 모듈 상세정보를 한 테이블에서 비교하는 창."""

    STATUS_MAP = {
        0: "Online", 1: "Offline", 2: "Sleep", 3: "Disconnect",
        4: "Charge", 5: "Discharge", 6: "Standby", 255: "Unknown"
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_ui = parent
        self.setWindowTitle("전체 모듈 상세정보")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowMinMaxButtonsHint
        )
        self.resize(1500, 700)
        self.setMinimumSize(1000, 520)

        layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        title = QLabel("전체 모듈 상세정보")
        title.setStyleSheet("font-size:14px; font-weight:bold;")
        self.update_label = QLabel("업데이트: -")
        self.update_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(self.update_label)
        layout.addLayout(top_layout)

        legend = QLabel(
            '※ 셀 전압: '
            '<span style="background-color:#D3F9D8;"> 최고 </span> '
            '<span style="background-color:#FFE3E3;"> 최저 </span> '
            '&nbsp;&nbsp; ※ 온도: '
            '<span style="background-color:#FFF9C4;"> 최고 </span> '
            '<span style="background-color:#FF4D4D; color:white;"> 60℃ 이상 </span>'
        )
        layout.addWidget(legend)

        base_headers = [
            "모듈", "SW버전", "Equip ID", "모델", "바코드",
            "전압[V]", "전류[A]", "상태", "SOC[%]", "SOH[%]"
        ]
        voltage_headers = [
            f"셀{cell_no} 전압[V]" for cell_no in range(1, 16)
        ]
        temperature_headers = [
            f"셀{cell_no} 온도[℃]" for cell_no in range(1, 16)
        ]
        self.headers = base_headers + voltage_headers + temperature_headers

        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStyleSheet(
            "QHeaderView::section { font-weight:bold; "
            "padding:4px; border:1px solid #CBD5E1; }"
        )
        for col in range(len(self.headers)):
            header_item = self.table.horizontalHeaderItem(col)
            if not header_item:
                continue
            if col < 10:
                header_item.setBackground(QColor("#E7F1FF"))
            elif col < 25:
                header_item.setBackground(QColor("#DCEEFF"))
            else:
                header_item.setBackground(QColor("#FFE7D1"))
        for col in range(5):
            self.table.setColumnWidth(col, 105 if col != 4 else 160)
        for col in range(5, len(self.headers)):
            self.table.setColumnWidth(col, 88)
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(3000)
        self.update_data()

    @staticmethod
    def format_value(value, decimals=None):
        if value is None:
            return "-"
        if decimals is not None:
            try:
                return f"{float(value):.{decimals}f}"
            except (TypeError, ValueError):
                pass
        return str(value)

    def update_data(self):
        module_numbers = sorted(self.parent_ui.module_map.keys())
        self.table.setRowCount(len(module_numbers))

        for row, module_no in enumerate(module_numbers):
            info = self.parent_ui.module_map.get(module_no, {})
            row_index = info.get("row_index")
            data = self.parent_ui.module_data.get(row_index)
            if data is None:
                data = self.parent_ui.module_data.get(str(row_index), {})
            data = data or {}

            cells = list(data.get("cells", []))[:15]
            temps = list(data.get("temps", []))[:15]
            cells += [None] * (15 - len(cells))
            temps += [None] * (15 - len(temps))
            valid_cells = [value for value in cells if value is not None]
            valid_temps = [value for value in temps if value is not None]
            max_cell = max(valid_cells) if valid_cells else None
            min_cell = min(valid_cells) if valid_cells else None
            max_temp = max(valid_temps) if valid_temps else None

            status_code = data.get("status")
            base_values = [
                f"#{int(module_no):02d}",
                info.get("swver"),
                info.get("equip_id"),
                info.get("model"),
                info.get("barcode"),
                self.format_value(data.get("volt"), 1),
                self.format_value(data.get("current"), 1),
                self.STATUS_MAP.get(status_code, "Unknown")
                if status_code is not None else "-",
                data.get("soc"),
                data.get("soh"),
            ]

            for col, value in enumerate(base_values):
                text = self.format_value(value)
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setToolTip(text)
                self.table.setItem(row, col, item)

            voltage_start_col = len(base_values)
            temperature_start_col = voltage_start_col + 15

            # 셀 1~15 전압을 먼저 연속으로 표시한다.
            for index in range(15):
                cell_value = cells[index]
                cell_item = QTableWidgetItem(
                    self.format_value(cell_value, 2)
                )
                cell_item.setTextAlignment(Qt.AlignCenter)
                cell_item.setBackground(QColor("#EEF6FF"))
                if cell_value is not None:
                    if cell_value == max_cell:
                        cell_item.setBackground(QColor("#D3F9D8"))
                    elif cell_value == min_cell:
                        cell_item.setBackground(QColor("#FFE3E3"))
                self.table.setItem(row, voltage_start_col + index, cell_item)

            # 셀 1~15 온도를 전압 열 다음에 연속으로 표시한다.
            for index in range(15):
                temp_value = temps[index]
                temp_item = QTableWidgetItem(
                    self.format_value(temp_value, 1)
                )
                temp_item.setTextAlignment(Qt.AlignCenter)
                temp_item.setBackground(QColor("#FFF7ED"))
                if temp_value is not None:
                    if temp_value >= 60:
                        temp_item.setBackground(QColor("#FF4D4D"))
                        temp_item.setForeground(QColor("white"))
                    elif temp_value == max_temp:
                        temp_item.setBackground(QColor("#FFF9C4"))
                self.table.setItem(row, temperature_start_col + index, temp_item)

        now = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.update_label.setText(f"업데이트: {now}")

# ======================
# 프로파일 선택 다이얼로그
# ======================
class ProfileDialog(QDialog):
    def __init__(self, profile_dir, forced_slave=False):
        super().__init__()

        self.setWindowTitle("프로파일 선택")

        # 🔥 먼저 초기화 (순서 중요)
        self.profile_dir = profile_dir
        self.forced_slave = forced_slave
        # 🔥 profiles 폴더 없으면 생성
        if not os.path.exists(self.profile_dir):
            os.makedirs(self.profile_dir, exist_ok=True)
        self.selected_profile_path = None
        self.new_profile_data = None

        # =========================
        # 🔥 Master profile 읽기
        # =========================
        self.master_profile_path = None

        master_file = os.path.join(self.profile_dir, "master_profile.txt")
        if os.path.exists(master_file):
            with open(master_file, "r") as f:
                self.master_profile_path = f.read().strip()

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("저장된 설치장소 + 시스템"))

        self.profile_list = QListWidget()
        layout.addWidget(self.profile_list)

        # 🔥 수정된 load (Master profile 제외)
        self.load_profiles()

        btn_layout = QHBoxLayout()

        self.new_btn = QPushButton("신규 생성")
        self.delete_btn = QPushButton("삭제")

        # =========================
        # 🔽 모드 선택 UI
        # =========================
        mode_layout = QHBoxLayout()

        mode_layout.addWidget(QLabel("동작 모드:"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Master", "Slave"])
        mode_layout.addWidget(self.mode_combo)

        # =========================
        # 🔥 Master 존재 시 강제 Slave
        # =========================
        if self.master_profile_path:
            self.mode_combo.setCurrentText("Slave")
            self.mode_combo.setEnabled(False)
            self.forced_slave = True

            msg = QMessageBox(self)
            msg.setWindowTitle("안내")
            msg.setText("이미 Master가 실행 중입니다.\nSlave 모드로 실행됩니다.")
            msg.setIcon(QMessageBox.Information)

            # 🔥 버튼 추가
            msg.setStandardButtons(QMessageBox.Ok)

            # 🔥 3초 후 자동 닫기 (확실한 방법)
            timer = QTimer(msg)
            timer.setSingleShot(True)
            timer.timeout.connect(msg.accept)
            timer.start(3000)

            msg.exec()
        else:
            self.forced_slave = False

        btn_layout.addWidget(self.new_btn)
        btn_layout.addWidget(self.delete_btn)

        layout.addLayout(mode_layout)
        layout.addLayout(btn_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        self.new_btn.clicked.connect(self.create_new_profile)
        self.delete_btn.clicked.connect(self.delete_profile)
        self.profile_list.itemDoubleClicked.connect(
            self.accept_profile_double_click
        )
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)

    def load_profiles(self):
        self.profile_list.clear()

        if not os.path.exists(self.profile_dir):
            return

        for file in os.listdir(self.profile_dir):
            if file.endswith(".ini"):
                full_path = os.path.join(self.profile_dir, file)

                # 🔥 Master에서 사용 중인 profile 제외
                if self.master_profile_path and full_path == self.master_profile_path:
                    continue

                self.profile_list.addItem(file)

        # 목록 로드 직후 첫 항목이 암묵적으로 선택되지 않게 한다.
        self.profile_list.clearSelection()
        self.profile_list.setCurrentRow(-1)

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

    def accept_profile_double_click(self, item):
        """프로파일 목록 더블클릭을 OK 버튼과 동일하게 처리한다."""
        if not item:
            return
        self.profile_list.setCurrentItem(item)
        self.accept_selection()

    def create_new_profile(self):
        self.new_profile_dialog = QDialog(self)
        dialog = self.new_profile_dialog
        dialog.setWindowTitle("신규 프로파일 생성")
        form = QFormLayout(dialog)

        self.site_edit = QLineEdit()
        self.system_edit = QLineEdit()

        form.addRow("설치 장소:", self.site_edit)
        form.addRow("시스템 이름:", self.system_edit)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Master", "Slave"])
        
        # 🔥 강제 Slave 모드 처리
        if self.forced_slave:
            self.mode_combo.setCurrentText("Slave")
            self.mode_combo.setEnabled(False)
        form.addRow("동작 모드:", self.mode_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(buttons)

        buttons.accepted.connect(self.on_new_profile_ok)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec():
            site = self.site_edit.text().strip()
            system = self.system_edit.text().strip()

            if not site or not system:
                return

            #self.new_profile_data = (site, system)
            mode = self.mode_combo.currentText()
            if self.forced_slave:
                mode = "Slave"
            dprint("DEBUG",f"#2 mode:{mode} forced_slave:{self.forced_slave}")
            self.selected_mode = mode
            
            self.new_profile_data = (site, system, mode, self.forced_slave)
            self.selected_profile_path = None
            self.accept()

    def on_new_profile_ok(self):
        dprint("DEBUG","on_new_profile_ok-start")
        site = self.site_edit.text()
        system = self.system_edit.text()
        mode = self.mode_combo.currentText()

        if self.forced_slave:
            mode = "Slave"

        self.new_profile_data = (site, system, mode, self.forced_slave)

        # 🔥 이게 핵심
        self.selected_profile_path = None

        dprint("DEBUG","on_new_profile_ok-end")
        self.new_profile_dialog.accept()
    
    def accept_selection(self):
        selected_items = self.profile_list.selectedItems()
        current = selected_items[0] if selected_items else None

        dprint("DEBUG","accept_selection start")

        # =========================
        # ✔ 신규 프로파일 생성 (우선 처리)
        # =========================
        if self.new_profile_data:
            site, system, mode, forced_slave = self.new_profile_data

            self.selected_mode = mode
            dprint("DEBUG","🔥 신규 생성 mode:", self.selected_mode)

        # =========================
        # ✔ 기존 프로파일 선택
        # =========================
        elif current:
            name = current.text()

            if not name.endswith(".ini"):
                name += ".ini"

            self.selected_profile_path = os.path.join(self.profile_dir, name)

            if hasattr(self, "mode_combo"):
                self.selected_mode = self.mode_combo.currentText()
            else:
                self.selected_mode = "Slave"

        # =========================
        # ❌ 아무것도 없음
        # =========================
        else:
            QMessageBox.warning(
                self,
                "프로파일 선택",
                "프로파일 목록을 선택하세요.",
                QMessageBox.Ok
            )
            return

        dprint("DEBUG","🔥 SELECTED PROFILE:", self.selected_profile_path)
        dprint("DEBUG","🔥 SELECTED MODE:", self.selected_mode)

        self.accept()
    
    

#######################################################################################################

# ======================
# SNMP Trap Thread
# ======================
class SNMPTrapThread(QThread):

    trap_signal = Signal(dict)
    rx_signal = Signal()
    trap_time_signal = Signal()
    listener_status_signal = Signal(bool, str)
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
        print(
            #f"[TRAP TEST] 수신 스레드 시작: {self.listen_ip}:{self.port}, "
            #f"community={self.community}",
            flush=True
        )
        dprint("SNMP", f"[TRAP] Thread run start (listen {self.listen_ip}:{self.port})")
        
        try:
            self.snmpEngine = engine.SnmpEngine()

            config.addTransport(
                self.snmpEngine,
                udp.domainName,
                udp.UdpTransport().openServerMode(
                    (self.listen_ip, self.port)
                )
            )
        except Exception as e:
            error_text = str(e) or repr(e)
            dprint(
                "SNMP",
                f"[TRAP] UDP bind failed {self.listen_ip}:{self.port}: {error_text}"
            )
            self.listener_status_signal.emit(False, error_text)
            try:
                if self.snmpEngine is not None:
                    self.snmpEngine.transportDispatcher.closeDispatcher()
            except Exception:
                pass
            return

        self.listener_status_signal.emit(True, "")
        print(
            #f"[TRAP TEST] UDP 바인딩 성공: {self.listen_ip}:{self.port}",
            flush=True
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
        
        print(
            #f"[TRAP TEST] Trap 수신됨: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, "
            #f"varBind 수={len(varBinds)}",
            flush=True
        )
        dprint("SNMP", "[TRAP CALLBACK] called")
        
        source_ip = ""
        try:
            transport_info = snmpEngine.msgAndPduDsp.getTransportInfo(
                stateReference
            )
            dprint("DEBUG", f"🔥 transport_info: {transport_info}")
            if transport_info and len(transport_info) > 1:
                source_ip = str(transport_info[1][0])
        except Exception as e:
            # 송신지 주소 확인에 실패해도 Trap 본문은 UI로 전달한다.
            dprint("SNMP", "[TRAP] source IP 확인 실패:", e)
        
        trap_data = {
            "_source_ip": source_ip
        }

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
            dprint("SNMP", "[TRAP] closeDispatcher error:", e)
        self.quit()
        self.wait(2000)


class SlaveRegisterThread(QThread):
    register_signal = Signal(dict)

    def __init__(self, port=50000):
        super().__init__()
        self.port = port
        self.running = True
        self.sock = None

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", self.port))
        self.sock.settimeout(1.0)

        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                if not self.running:
                    break
                msg = json.loads(data.decode())
                msg["_addr"] = addr
                self.register_signal.emit(msg)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                if self.running:
                    dprint("DEBUG","❌ register recv error:", e)

        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.quit()
        self.wait(2000)
        
# ======================
# Trap 재전송 SET Worker
# ======================
class TrapRetransmitSetThread(QThread):
    result_signal = Signal(bool, str)

    def __init__(self, ip, port, community, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.port = port
        self.community = community

    def run(self):
        try:
            oid = "1.3.6.1.4.1.2011.6.164.1.1.2.4.0"
            iterator = setCmd(
                SnmpEngine(),
                CommunityData(self.community, mpModel=1),
                UdpTransportTarget(
                    (self.ip, self.port),
                    timeout=2,
                    retries=2
                ),
                ContextData(),
                ObjectType(ObjectIdentity(oid), Integer32(1))
            )

            error_indication, error_status, error_index, var_binds = next(iterator)

            if error_indication:
                self.result_signal.emit(False, f"SNMP 오류: {error_indication}")
            elif error_status:
                self.result_signal.emit(
                    False,
                    f"{error_status.prettyPrint()} at {error_index}"
                )
            else:
                self.result_signal.emit(True, "")

        except Exception as e:
            self.result_signal.emit(False, str(e))

    def stop(self):
        # 동기식 pysnmp 호출은 즉시 취소할 수 없지만, 공통 스레드 종료
        # 절차에서 안전하게 대기/최종 종료할 수 있도록 인터페이스를 맞춘다.
        self.requestInterruption()

# ======================
# 모듈 EPO 순차 SET Worker
# ======================
class EpoCutoffThread(QThread):
    result_signal = Signal(bool, str, int)

    EPO_PREPARE_OID = "1.3.6.1.4.1.2011.6.164.1.2.2.1.1.11.1"
    MODULE_CUTOFF_OID = "1.3.6.1.4.1.2011.6.164.1.18.3.1.2"

    def __init__(
        self, ip, port, community, row_index, module_no,
        command_value=2, parent=None
    ):
        super().__init__(parent)
        self.ip = ip
        self.port = port
        self.community = community
        self.row_index = str(row_index)
        self.module_no = int(module_no)
        self.command_value = int(command_value)

    def set_and_verify(self, snmp_engine, oid, expected_value):
        iterator = setCmd(
            snmp_engine,
            CommunityData(self.community, mpModel=1),
            UdpTransportTarget(
                (self.ip, self.port),
                timeout=2,
                retries=2
            ),
            ContextData(),
            ObjectType(ObjectIdentity(oid), Integer32(expected_value))
        )

        error_indication, error_status, error_index, var_binds = next(iterator)

        if error_indication:
            return False, f"SNMP 응답 없음: {error_indication}"
        if error_status:
            return False, f"{error_status.prettyPrint()} at {error_index}"
        if not var_binds:
            return False, "SNMP SET 응답값이 없습니다."

        try:
            response_value = int(var_binds[0][1])
        except (TypeError, ValueError):
            return False, f"SNMP SET 응답값을 확인할 수 없습니다: {var_binds[0][1]}"

        if response_value != expected_value:
            return (
                False,
                f"SNMP SET 응답값 불일치 (요청: {expected_value}, 응답: {response_value})"
            )

        return True, ""

    def run(self):
        try:
            snmp_engine = SnmpEngine()

            success, message = self.set_and_verify(
                snmp_engine,
                self.EPO_PREPARE_OID,
                1
            )
            if not success:
                self.result_signal.emit(False, message, self.module_no)
                return

            cutoff_oid = f"{self.MODULE_CUTOFF_OID}.{self.row_index}"
            success, message = self.set_and_verify(
                snmp_engine, cutoff_oid, self.command_value
            )
            if not success:
                self.result_signal.emit(False, message, self.module_no)
                return

            self.result_signal.emit(True, "", self.module_no)

        except Exception as e:
            self.result_signal.emit(False, str(e), self.module_no)

    def stop(self):
        self.requestInterruption()

# 기록시각과 모듈 번호는 행 식별을 위해 항상 저장한다.
OPERATION_RECORD_FIELD_SPECS = [
    ("equipment", "장비 기본정보", ["Row Index", "Equip ID", "모델", "Barcode"]),
    ("voltage", "모듈 전압", ["모듈 전압[V]"]),
    ("current", "모듈 전류", ["모듈 전류[A]"]),
    ("soc_soh", "SOC / SOH", ["SOC[%]", "SOH[%]"]),
    ("status", "통신상태", ["상태 코드", "통신상태"]),
    ("alarm", "경보", ["경보"]),
    ("cell_summary", "셀 전압 Max / Min", ["셀 전압 Max[V]", "셀 전압 Min[V]"]),
    (
        "cell_detail",
        "셀 전압 상세 (01~15)",
        [f"Cell {i:02d}[V]" for i in range(1, 16)]
    ),
    ("temp_summary", "셀 온도 Max / Min", ["셀 온도 Max[℃]", "셀 온도 Min[℃]"]),
    (
        "temp_detail",
        "셀 온도 상세 (01~15)",
        [f"Temp {i:02d}[℃]" for i in range(1, 16)]
    ),
    ("epo", "EPO 상태 / 차단시각", ["EPO 버튼"]),
]

# ======================
# 운전 데이터 Excel 기록 Worker
# ======================
class OperationDataRecordThread(QThread):
    saved_signal = Signal(str, int)
    error_signal = Signal(str)

    def __init__(self, output_dir, headers, session_id, parent=None):
        super().__init__(parent)
        self.output_dir = output_dir
        self.headers = list(headers)
        self.session_id = session_id
        self.running = True
        self.record_queue = queue.Queue()

    def enqueue(self, recorded_at, rows):
        if self.running:
            self.record_queue.put((recorded_at, rows))

    def run(self):
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except Exception as e:
            self.error_signal.emit(f"기록 폴더 준비 실패: {e}")
            return

        while self.running or not self.record_queue.empty():
            try:
                payload = self.record_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if payload is None:
                continue

            recorded_at, rows = payload
            if not rows:
                continue

            try:
                path = self.write_excel(recorded_at, rows)
                self.saved_signal.emit(path, len(rows))
            except Exception as e:
                self.error_signal.emit(f"Excel 저장 실패: {e}")

    def write_excel(self, recorded_at, rows):
        filename = (
            f"Operation_data_{self.session_id}_"
            f"{recorded_at.strftime('%Y-%m-%d')}.xlsx"
        )
        path = os.path.join(self.output_dir, filename)

        if os.path.exists(path):
            workbook = load_workbook(path)
            worksheet = None
            for candidate in workbook.worksheets:
                existing_headers = [
                    candidate.cell(1, col).value
                    for col in range(1, candidate.max_column + 1)
                ]
                if existing_headers == self.headers:
                    worksheet = candidate
                    break

            if worksheet is None:
                sheet_number = len(workbook.worksheets) + 1
                worksheet = workbook.create_sheet(f"모듈 상태_{sheet_number}")
                self.initialize_worksheet(worksheet)
        else:
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = "모듈 상태"
            self.initialize_worksheet(worksheet)

        timestamp = recorded_at.strftime("%Y-%m-%d %H:%M:%S")
        for row in rows:
            worksheet.append([timestamp] + row)

        temp_path = path + ".tmp.xlsx"
        workbook.save(temp_path)
        workbook.close()
        os.replace(temp_path, path)
        return path

    def initialize_worksheet(self, worksheet):
        worksheet.append(self.headers)
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = (
            f"A1:{worksheet.cell(1, len(self.headers)).coordinate}"
        )

        header_fill = PatternFill("solid", fgColor="DCEBFF")
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        worksheet.column_dimensions["A"].width = 20
        for column in range(2, len(self.headers) + 1):
            letter = worksheet.cell(1, column).column_letter
            worksheet.column_dimensions[letter].width = 15

    def stop(self):
        self.running = False
        self.record_queue.put(None)

# ======================
# SNMP Worker Thread
# ======================

class SNMPThread(QThread):
    result_signal = Signal(bool, object)  # str → object (dict 전달 가능)
    soc_charge_limit_signal = Signal(bool, object)
    initial_load_complete_signal = Signal()

    tx_signal = Signal()
    rx_signal = Signal()

    # SNMP 안정성/응답 속도 균형 설정
    # 장비의 순간 응답 누락을 Timeout으로 확정하지 않도록 1회 재시도한다.
    # 한 응답의 row 수를 늘려 전체 요청 패킷 수와 최초 화면 표시 시간을 줄인다.
    SNMP_TIMEOUT_SEC = 2.5
    SNMP_RETRIES = 1
    BULK_MAX_REPETITIONS = 30
    BULK_ROW_DELAY_MS = 2
    BASE_OID_DELAY_MS = 10
    POLL_IDLE_LOOP_COUNT = 20
    POLL_IDLE_SLEEP_MS = 100
    SOC_CHARGE_ENABLE_OID = "1.3.6.1.4.1.2011.6.164.1.17.2.1.29.96"
    SOC_CHARGE_VALUE_OID  = "1.3.6.1.4.1.2011.6.164.1.17.2.1.30.96"

    def __init__(self, ip, community="public", port=161, once=False):
        super().__init__()
        self.ip = ip
        self.community = community
        self.port = port
        self.running = True
        self.once = once  # 최초 테스트 여부
        self.snmpEngine = None   # 🔴 멤버로 보관
        self.initial_ui_emitted = False
        self.initial_load_complete_emitted = False

    def run(self):

        # ===============================
        # 1️⃣ 최초 연결 테스트 (sysUpTime)
        # ===============================
        if self.once:
            if hasattr(self, "parent_ui"):
                self.tx_signal.emit()
                
            # ✅ 테스트용은 별도 엔진 사용
            test_engine = SnmpEngine()
            try:
                errorIndication, errorStatus, errorIndex, varBinds = next(
                    getCmd(
                        test_engine,
                        CommunityData(self.community, mpModel=1),
                        UdpTransportTarget(
                            (self.ip, int(self.port)),
                            timeout=self.SNMP_TIMEOUT_SEC,
                            retries=self.SNMP_RETRIES
                        ),
                        ContextData(),
                        ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0"))
                    )
                )
            except Exception as e:
                self.result_signal.emit(
                    False, f"{type(e).__name__}: {str(e) or repr(e)}"
                )
                return

            if errorIndication or errorStatus:
                if errorIndication:
                    error_message = str(errorIndication)
                else:
                    error_message = str(errorStatus.prettyPrint())
                    if errorIndex:
                        error_message += f" (index: {errorIndex})"
                self.result_signal.emit(False, error_message)
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
            "1.3.6.1.4.1.2011.6.164.1.18.2",
            "1.3.6.1.4.1.2011.6.164.1.17.1",
            "1.3.6.1.4.1.2011.6.164.1.17.2",
            "1.3.6.1.4.1.2011.6.164.1.1.2.99"
        ]        
        
        # 🔴 polling용 snmpEngine은 멤버에 저장
        self.snmpEngine = SnmpEngine()
        
        while self.running:

            result_data = {}
            cycle_failed = False
            snmpEngine = self.snmpEngine
            for base_index, base_oid in enumerate(base_oids):
                # 🔵 SNMP 요청 전송 (TX blink)
                # TX LED는 base_oid 요청 1회당 1번만 blink
                if hasattr(self, "parent_ui"):
                    self.tx_signal.emit()

                # RX LED도 실제 응답 row/varBind 개수가 아니라
                # 위 TX 요청 1회에 대한 응답 수신 1회만 blink되도록 제한
                rx_blink_emitted = False
                
                try:
                    for (errorIndication,
                        errorStatus,
                        errorIndex,
                        varBinds) in bulkCmd(
                            snmpEngine,
                            CommunityData(self.community, mpModel=1),
                            UdpTransportTarget(
                                (self.ip, int(self.port)),
                                timeout=self.SNMP_TIMEOUT_SEC,
                                retries=self.SNMP_RETRIES
                            ),
                            ContextData(),
                            0, self.BULK_MAX_REPETITIONS,
                            ObjectType(ObjectIdentity(base_oid)),
                            lexicographicMode=False):
                            
                        if not self.running:
                            return

                        if errorIndication or errorStatus:
                            cycle_failed = True
                            break
                        
                        if (not rx_blink_emitted) and hasattr(self, "parent_ui"):
                            self.rx_signal.emit()
                            rx_blink_emitted = True
        
                        for varBind in varBinds:
                            oid = str(varBind[0])
                            value = varBind[1].prettyPrint()
                            result_data[oid] = value

                        # 18.2 테이블의 운전상태까지 들어온 첫 응답에서
                        # 모듈 기본 화면을 우선 표시한다.
                        if (
                            base_index == 1
                            and not self.initial_ui_emitted
                            and any(
                                oid.startswith(
                                    "1.3.6.1.4.1.2011.6.164.1.18.2.1.3."
                                )
                                for oid in result_data
                            )
                        ):
                            self.result_signal.emit(True, dict(result_data))
                            self.initial_ui_emitted = True

                        self.msleep(self.BULK_ROW_DELAY_MS)
                except Exception as e:
                    print("SNMP ERROR:", e)
                    cycle_failed = True
                    self.msleep(50)
                
                # 하나의 기본 OID라도 실패하면 부분 데이터를 더 수집하지 않는다.
                if cycle_failed:
                    break

                # 최초 접속에서는 모듈 기본정보(18.1)와 상태정보(18.2)가
                # 준비되는 즉시 먼저 표시하고 나머지 Summary/Alarm은 이어서 조회한다.
                if base_index == 1 and not self.initial_ui_emitted and result_data:
                    self.result_signal.emit(True, dict(result_data))
                    self.initial_ui_emitted = True

                # MIB 트리 사이에 짧은 간격을 두어 장비 SNMP 처리 부하를 낮춘다.
                self.msleep(self.BASE_OID_DELAY_MS)

            # 기본 모듈 데이터 결과를 SOC 별도 조회보다 먼저 UI에 전달한다.
            # 실패한 주기의 부분 데이터는 폐기해 마지막 정상 UI를 유지한다.
            if cycle_failed or not result_data:
                self.result_signal.emit(False, "")
            else:
                self.result_signal.emit(True, result_data)
                if not self.initial_load_complete_emitted:
                    self.initial_load_complete_emitted = True
                    self.initial_load_complete_signal.emit()

            # SOC 충전제한 상태/설정값은 매 polling 주기마다 정확한 OID로 GET한다.
            try:
                self.tx_signal.emit()
                errorIndication, errorStatus, errorIndex, varBinds = next(
                    getCmd(
                        snmpEngine,
                        CommunityData(self.community, mpModel=1),
                        UdpTransportTarget(
                            (self.ip, int(self.port)),
                            timeout=self.SNMP_TIMEOUT_SEC,
                            retries=self.SNMP_RETRIES
                        ),
                        ContextData(),
                        ObjectType(ObjectIdentity(self.SOC_CHARGE_ENABLE_OID)),
                        ObjectType(ObjectIdentity(self.SOC_CHARGE_VALUE_OID))
                    )
                )

                if errorIndication or errorStatus or len(varBinds) < 2:
                    error_text = (
                        str(errorIndication)
                        if errorIndication
                        else errorStatus.prettyPrint() if errorStatus else "응답값 부족"
                    )
                    self.soc_charge_limit_signal.emit(False, error_text)
                else:
                    self.rx_signal.emit()
                    soc_values = {
                        "enabled": int(varBinds[0][1]),
                        "value": int(varBinds[1][1])
                    }
                    self.soc_charge_limit_signal.emit(True, soc_values)
            except Exception as e:
                self.soc_charge_limit_signal.emit(False, str(e))

            for _ in range(self.POLL_IDLE_LOOP_COUNT):
                if not self.running:
                    return
                self.msleep(self.POLL_IDLE_SLEEP_MS)

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
        self.wait(2000)
        
# ======================
# 메인 UI
# ======================
class BatteryMonitorUI(QMainWindow):
    def __init__(self, profile_path, mode, new_profile_data=None, forced_slave=False):
        super().__init__()

        self.profile_path = profile_path
        self.settings = QSettings(profile_path, QSettings.IniFormat)
        self.has_ever_connected = False
        self.mode = mode
        self.total_capacity = None
        self.group_soh = None

        if forced_slave:
            self.mode = "Slave"

        self.is_master = (self.mode == "Master")
        self.is_slave = not self.is_master

        self.setWindowIcon(QIcon(resource_path("battery#3.ico")))
        mode_text = "MASTER" if self.is_master else "SLAVE"
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}  ({mode_text})")

        dprint("DEBUG","👉 FINAL mode:", self.mode)
        dprint("DEBUG","👉 is_master:", self.is_master)

        # =========================
        # 🔥 2. Master 동작
        # =========================
        if self.is_master:
            try:
                self.register_thread = SlaveRegisterThread(50000)
                self.register_thread.register_signal.connect(self.handle_register)
                self.register_thread.start()
                dprint("DEBUG","🔥 MASTER MODE - PORT 50000 BIND SUCCESS")

                master_file = os.path.join(os.path.dirname(self.profile_path), "master_profile.txt")
                with open(master_file, "w") as f:
                    f.write(self.profile_path)

                dprint("DEBUG","🔥 master_profile.txt 생성 완료")

            except Exception as e:
                dprint("DEBUG","❌ Master bind 실패:", e)
                self.is_master = False
                self.is_slave = True

        # =========================
        # 🔥 3. 공통 상태 변수 초기화 (UI보다 먼저!)
        # =========================
        self.is_connected = False
        
        # 🔥 SNMP 응답 실패 카운트
        self.snmp_fail_count = 0
        self.snmp_total_fail_count = 0

        self.timeout_popup_shown = False   # 5회 팝업 1회만
        self.timeout_disconnect_popup_shown = False # 10회 팝업 1회만
        self.initial_load_message = None
        self.initial_load_timer = QTimer(self)
        self.initial_load_timer.timeout.connect(self.update_initial_load_message)
        self.initial_load_started_at = None

        self.alarm_volume_level = int(self.settings.value("alarm/volume", 0))

        self.alarm_level_enable = {
            1: self.settings.value("alarm/level/1", True, type=bool),
            2: self.settings.value("alarm/level/2", True, type=bool),
            3: self.settings.value("alarm/level/3", True, type=bool),
            4: self.settings.value("alarm/level/4", False, type=bool),
            255: self.settings.value("alarm/level/255", False, type=bool),
        }

        # =========================
        # 🔧 기본 변수
        # =========================
        self.module_map = {}
        self.row_to_module = {}
        self.equip_to_module = {}
        self.current_profile = {}
        self.module_barcodes = {}

        # =========================
        # 🔥 IP → Slave Port 매핑 (핵심)
        # =========================
        self.ip_to_slave_port = {}   # {"192.168.0.10": 50001, ...}
        self.slave_registry = {}     # {profile_file: {ip, port, last_seen}}
        
        # =========================
        # UI 기본 요소
        # =========================
        self.tx_label = QLabel("TX")
        self.rx_label = QLabel("RX")

        self.tx_led = QLabel()
        self.tx_led.setFixedSize(12, 12)
        self.tx_led.setStyleSheet("background:#555;border-radius:6px;")

        self.rx_led = QLabel()
        self.rx_led.setFixedSize(12, 12)
        self.rx_led.setStyleSheet("background:#555;border-radius:6px;")

        self.update_time_label = QLabel("최종업데이트시간 : 대기중")

        self.resize(1200, 850)

        # =========================
        # 로그 디렉토리
        # =========================
        base_dir = os.path.dirname(os.path.abspath(__file__))
        profile_name = os.path.basename(self.profile_path).replace(".ini", "")
        self.log_dir = os.path.join(base_dir, "logs", profile_name)
        self.profile_dir = os.path.dirname(self.profile_path)

        os.makedirs(self.log_dir, exist_ok=True)

        # =========================
        # 🔥 module_order 초기화 (필수)
        # =========================
        order = self.settings.value("module_order")

        if order:
            try:
                self.module_order = [int(x) if x else None for x in order]
            except:
                self.module_order = [None] * 10
        else:
            self.module_order = [None] * 10
    
        # =========================
        # 🔔 Alarm 상태 초기화 (필수)
        # =========================
        self.alarm_blink_state = False
        self.alarm_active = False

        # =========================
        # 🔊 Alarm Sound 초기화 (필수)
        # =========================
        self.alarm_sound = QSoundEffect()
        self.alarm_sound.setSource(QUrl.fromLocalFile(resource_path("alarm.wav")))

        # 무한 반복 (버전 호환 안전 처리)
        try:
            loop_infinite = getattr(QSoundEffect, "Infinite", None)

            if loop_infinite is not None:
                # ✅ 정상적인 방식 (Qt5/Qt6 공통)
                self.alarm_sound.setLoopCount(loop_infinite)
            else:
                # ⚠️ 아주 구버전 fallback (거의 없음)
                self.alarm_sound.setLoopCount(0)  # 최소 1회 재생으로 안전 처리

        except Exception as e:
            dprint("DEBUG",f"[WARN] setLoopCount failed: {e}")
            self.alarm_sound.setLoopCount(1)  # 안전 fallback

        # 볼륨 적용
        volume_map = {0:0.0, 1:0.2, 2:0.5, 3:1.0}
        self.alarm_sound.setVolume(volume_map.get(self.alarm_volume_level, 0.0))
        
        # =========================
        # 🔥 런타임 객체 초기화 (필수)
        # =========================

        # SNMP / 데이터
        self.module_data = {}

        # 모듈 차단 버튼 보관용 - create_module_table()에서 먼저 사용됨
        self.cutoff_buttons = {}

        # Thread 객체는 UI 생성/연결 전에도 안전하게 참조될 수 있도록 기본값 설정
        self.snmp_thread = None
        self.trap_thread = None
        self.local_trap = None
        self.ping_thread = None

        # Slave -> Master heartbeat: 5초 주기의 작은 UDP JSON 1개만 전송
        self.slave_heartbeat_timer = QTimer(self)
        self.slave_heartbeat_timer.setInterval(5000)
        self.slave_heartbeat_timer.timeout.connect(
            lambda: self.register_to_master("heartbeat")
        )

        # TX / RX Timer
        self.tx_timer = QTimer()
        self.tx_timer.setSingleShot(True)
        self.tx_timer.timeout.connect(self.tx_led_off)

        self.rx_timer = QTimer()
        self.rx_timer.setSingleShot(True)
        self.rx_timer.timeout.connect(self.rx_led_off)

        # LED 표시 보정
        # pcap 기준: TX 주기 약 0.18~0.22초, RX는 TX 후 약 0.02~0.04초 응답
        # 300ms 점등은 다음 패킷과 겹쳐 계속 켜진 것처럼 보여 70ms 펄스로 보정
        self.LED_PULSE_MS = 70
        self.LED_MIN_INTERVAL_SEC = 0.12
        self._last_tx_led_ts = 0.0
        self._last_rx_led_ts = 0.0

        # Alarm Blink Timer
        self.alarm_blink_timer = QTimer()
        self.alarm_blink_timer.timeout.connect(self.blink_alarm_button)

        # Trap Queue
        from collections import deque
        self.trap_queue = deque(maxlen=TRAP_QUEUE_SIZE)

        # 상태 관리
        self.fault_list = []
        self.active_fault_keys = set()
        self.last_fault_snapshot = set()
        self.current_alarm_table = []
        # =========================
        # 🔥 UI 생성
        # =========================
        # 노트북 해상도에서 하단 "고장 정보"가 잘리지 않도록
        # 전체 메인 화면을 QScrollArea로 감싼다.
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(scroll_area)

        central = QWidget()
        scroll_area.setWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        main_layout.addWidget(self.create_connection_panel())
        main_layout.addWidget(self.create_header())
        main_layout.addWidget(self.create_summary_section())
        main_layout.addWidget(self.create_module_table())
        main_layout.addWidget(self.create_fault_table())

        # =========================
        # Slave 로컬 Trap 포트는 자동 할당 후에도 수동 변경 가능
        # =========================
        if self.is_slave:
            self.trap_port_edit.setReadOnly(False)
            self.trap_port_edit.setToolTip(
                "Slave 로컬 Trap 수신 포트 (51000~52000, 0은 자동 할당)"
            )
            self.trap_port_edit.editingFinished.connect(
                self.on_slave_trap_port_changed
            )
        # =========================
        # 📊 시스템 리소스 타이머 (필수)
        # =========================
        self.sys_timer = QTimer()
        self.sys_timer.timeout.connect(self.update_system_resource)
        self.sys_timer.start(1000)   # 1초마다 갱신

        # =========================
        # 🔥 Master UI 반영
        # =========================
        if hasattr(self, "btn_slave_list"):
            self.btn_slave_list.setVisible(self.is_master)

        # =========================
        # Profile 초기값 (수정)
        # =========================
        if new_profile_data:
            site, system, mode, forced_slave = new_profile_data

            # 🔥 1. UI 먼저 반영 (핵심)
            self.site_edit.setText(site)
            self.system_edit.setText(system)

            # 🔥 2. 저장 (신규 생성일 때만)
            if not os.path.exists(self.profile_path):
                self.save_site_info()
        else:
            # 기존 profile
            self.load_site_info()

        self.slave_targets = self.load_slave_targets()
        dprint("DEBUG","MODE:", mode)
        dprint("DEBUG","is_master:", self.is_master)
        dprint("DEBUG","is_slave:", self.is_slave)

    def handle_register(self, msg):
        try:
            if not isinstance(msg, dict):
                dprint("DEBUG","❌ register: invalid message type")
                return

            message_type = msg.get("type")
            if message_type not in ("register", "heartbeat", "unregister"):
                return

            ip = msg.get("ip")
            port = msg.get("port")
            profile_file = os.path.basename(str(msg.get("profile") or ""))

            if not ip or not port or not profile_file:
                dprint("DEBUG","❌ register: invalid data", msg)
                return

            port = int(port)
            registry_key = profile_file

            if message_type == "unregister":
                self.slave_registry.pop(registry_key, None)
                self.ip_to_slave_port.pop(ip, None)
                dprint("DEBUG", f"⏹ Slave 등록 해제: {profile_file} {ip}:{port}")
                return

            already_registered = registry_key in self.slave_registry
            self.slave_registry[registry_key] = {
                "profile": profile_file,
                "ip": ip,
                "port": port,
                "system": str(msg.get("system") or "").strip(),
                "last_seen": time.monotonic(),
            }
            # 기존 코드 호환용 매핑도 같이 유지한다.
            self.ip_to_slave_port[ip] = port

            found = False
            for t in self.slave_targets:
                if t.get("file") == profile_file:
                    t["ip"] = ip
                    t["port"] = port
                    found = True
                    break

            if not found:
                self.slave_targets.append({
                    "ip": ip,
                    "port": port,
                    "file": profile_file
                })

            if message_type == "register":
                action = "재등록" if already_registered else "신규 등록"
                dprint("DEBUG", f"🔄 Slave {action}: {profile_file} {ip}:{port}")

        except Exception as e:
            dprint("DEBUG","❌ handle_register error:", e)
        
    def register_to_master(self, message_type="register"):
        try:
            target_ip = self.settings.value("ip")

            if not target_ip or not getattr(self, "local_trap_port", 0):
                dprint("DEBUG", "❌ Slave 등록 실패: IP 또는 로컬 Trap 포트 없음")
                return

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            msg = {
                "type": message_type,
                "ip": target_ip,
                "port": self.local_trap_port,
                "profile": os.path.basename(self.profile_path),
                "system": self.settings.value("system", ""),
            }

            sock.sendto(json.dumps(msg).encode(), ("127.0.0.1", 50000))
            sock.close()

            if message_type == "register":
                dprint("DEBUG",f"🔥 Slave 등록 완료: target_ip:{target_ip}:{self.local_trap_port}")

        except Exception as e:
            dprint("DEBUG","❌ Slave 등록 실패:", e)

    @staticmethod
    def is_local_trap_port_available(port):
        """localhost UDP 포트를 현재 바인딩할 수 있는지 확인한다."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", int(port)))
            return True
        except OSError:
            return False
        finally:
            sock.close()

    def allocate_local_trap_port(self):
        """51000~52000 범위에서 사용 가능한 UDP 포트를 무작위로 할당한다."""
        candidates = list(range(51000, 52001))
        random.shuffle(candidates)
        for port in candidates:
            if self.is_local_trap_port_available(port):
                return port
        raise RuntimeError("51000~52000 범위에 사용 가능한 UDP 포트가 없습니다.")

    def start_slave_trap_listener(self, port, register=True):
        """Slave 로컬 리스너를 시작하고 Master에 IP/포트를 등록한다."""
        port = int(port)
        if not 51000 <= port <= 52000:
            raise ValueError("Slave Trap 포트는 51000~52000 범위여야 합니다.")

        current_port = int(getattr(self, "local_trap_port", 0) or 0)
        current_listener = getattr(self, "local_trap", None)

        if current_listener and current_listener.isRunning() and current_port == port:
            if register:
                self.register_to_master()
                self.slave_heartbeat_timer.start()
            return

        # 새 포트를 먼저 확인해 실패 시 기존 리스너를 유지한다.
        if not self.is_local_trap_port_available(port):
            raise OSError(f"UDP {port} 포트를 이미 다른 프로세스가 사용 중입니다.")

        if current_listener:
            current_listener.stop()
            self.local_trap = None

        self.local_trap_port = port
        self.settings.setValue("local_trap_port", port)
        self.settings.sync()
        self.trap_port_edit.setText(str(port))

        self.local_trap = LocalTrapReceiver(port)
        self.local_trap.trap_signal.connect(self.handle_trap)
        self.local_trap.listener_status_signal.connect(
            self.handle_trap_listener_status
        )
        self.local_trap.start()

        if register:
            QTimer.singleShot(500, self.register_to_master)
            self.slave_heartbeat_timer.start()

    def on_slave_trap_port_changed(self):
        """Slave 운영 중 수동 포트 변경을 반영하고 Master에 재등록한다."""
        if not self.is_slave:
            return

        old_port = int(getattr(self, "local_trap_port", 0) or 0)
        try:
            port = int(self.trap_port_edit.text().strip())
            if not 51000 <= port <= 52000:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self, "Trap 포트 오류",
                "Slave Trap 포트는 51000~52000 범위로 입력하세요."
            )
            self.trap_port_edit.setText(str(old_port or 0))
            return

        # 접속 전에는 입력값만 유지하고 접속 성공 후 리스너를 시작한다.
        if not self.is_connected:
            return

        try:
            self.start_slave_trap_listener(port, register=True)
        except Exception as e:
            self.trap_port_edit.setText(str(old_port or 0))
            QMessageBox.warning(self, "Trap 포트 변경 실패", str(e))
        
    def load_slave_targets(self):
        targets = []

        for f in os.listdir(self.profile_dir):
            if not f.endswith(".ini"):
                continue

            if f == os.path.basename(self.profile_path):
                continue

            file_path = os.path.join(self.profile_dir, f)
            settings = QSettings(file_path, QSettings.IniFormat)

            ip = settings.value("ip", "")
            local_port = int(settings.value("local_trap_port", 0))  # 🔥 변경

            if ip and local_port:
                targets.append({
                    "ip": ip,
                    "port": local_port,
                    "file": f
                })

        return targets
    
    

    def forward_trap_to_slaves(self, trap_data, source_ip):
        now = time.monotonic()
        delivery_results = []
        for target in list(self.slave_registry.values()):
            ip = target.get("ip")
            port = int(target.get("port", 0) or 0)
            if ip and source_ip and ip != source_ip:
                continue

            system_name = str(target.get("system") or "").strip()
            if not system_name:
                profile_file = target.get("profile", "")
                profile_path = os.path.join(self.profile_dir, profile_file)
                if os.path.exists(profile_path):
                    profile_settings = QSettings(
                        profile_path, QSettings.IniFormat
                    )
                    system_name = str(
                        profile_settings.value("system", "") or ""
                    ).strip()
            if not system_name:
                system_name = os.path.splitext(
                    target.get("profile", "Slave")
                )[0]

            result = {
                "system": system_name,
                "ip": ip,
                "success": False,
            }
            delivery_results.append(result)

            # 12초 이상 heartbeat가 없는 Slave는 실패로 기록한다.
            if now - target.get("last_seen", 0) > 12:
                continue

            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(
                    json.dumps(trap_data).encode(),
                    ("127.0.0.1", port)
                )
                result["success"] = True
            except Exception as e:
                dprint("DEBUG","❌ Slave 전송 실패:", e)
            finally:
                if sock:
                    sock.close()

        return delivery_results

    def toggle_alarm_sound(self):
        self.alarm_volume_level = (self.alarm_volume_level + 1) % 4
        self.update_sound_icon()

        volume_map = {0:0.0, 1:0.2, 2:0.5, 3:1.0}
        self.alarm_sound.setVolume(volume_map[self.alarm_volume_level])

        # 🔥 실시간 저장
        self.settings.setValue("alarm/volume", self.alarm_volume_level)
        self.settings.sync()
        
    def set_alarm_level(self, level, checkbox):
        self.alarm_level_enable[level] = checkbox.isChecked()

        # 🔥 실시간 저장
        self.settings.setValue(f"alarm/level/{level}", checkbox.isChecked())
        self.settings.sync()
    
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:

            if hasattr(self, "alarm_sound") and self.alarm_sound.isPlaying():
                self.alarm_sound.stop()

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if self.alarm_sound.isPlaying():
            self.alarm_sound.stop()

        super().mousePressEvent(event)

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

    def reset_module_order(self):

        # 프로파일에 저장된 모듈 설치 순서 관련 값을 모두 삭제한다.
        self.settings.remove("module_order")
        self.settings.remove("module_barcodes")
        self.settings.sync()

        # 실행 중인 바코드 불일치 깜박임도 함께 정리한다.
        for module_no in list(getattr(self, "rack_blink_timers", {}).keys()):
            self.stop_rack_blink(module_no, False)

        self.module_order = [None] * 10
        self.module_barcodes = {}
        self.rack_widgets = {}
        self.update_module_order_view()

        dprint("MODULE", "모듈 설치 순서 초기화 완료")
    
    
    def update_module_order_label(
        self, index, module_no=None, barcode=None,
        has_alarm=False, is_disconnected=False
    ):

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
            
            # 차단 후 Disconnect 상태는 차단 버튼의 비활성 색상으로 우선 표시한다.
            # 통신상태가 복구되면 다음 화면 갱신에서 정상/알람 스타일로 돌아간다.
            if is_disconnected:
                label.setStyleSheet("""
                    QLabel {
                        border: 1px solid #868E96;
                        border-radius: 6px;
                        padding: 2px 6px;
                        background: #ADB5BD;
                        color: #FFFFFF;
                        font-weight: 600;
                        font-size: 12px;
                    }
                """)
            elif has_alarm:
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
    

    def update_sound_icon(self):
        icons = {
            0: "🔇",
            1: "🔈",
            2: "🔉",
            3: "🔊"
        }

        level = int(self.alarm_volume_level) if self.alarm_volume_level is not None else 0
        level = max(0, min(level, 3))  # 범위 제한

        # 🔥 버튼 존재 확인
        if hasattr(self, "btn_alarm_sound"):
            self.btn_alarm_sound.setText(icons[level])
        
        self.btn_alarm_sound.setText(icons[level])


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
            if hasattr(self, "trap_thread") and self.trap_thread:
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

        profile_name = os.path.basename(self.profile_path).replace(".ini", "")
        logfile = os.path.join(self.log_dir, f"{profile_name}_trap_{date_str}.log")

        line = f"{t},{oid},{ordinal},{alarm},{level},{equip_id},{equip_name},{father}\n"

        with open(logfile, "a", encoding="utf-8") as f:
            f.write(line)
        
    def tx_led_on(self):

        # pcap 기준 TX 주기는 약 180~220ms 수준입니다.
        # LED 점등 시간이 너무 길면 계속 켜진 것처럼 보여 70ms 짧은 펄스로 표시합니다.
        now = time.monotonic()
        if now - getattr(self, "_last_tx_led_ts", 0.0) < getattr(self, "LED_MIN_INTERVAL_SEC", 0.12):
            return

        self._last_tx_led_ts = now
        self.tx_led.setStyleSheet(
            "background:#FFD54F;border-radius:8px;"
        )
        self.tx_timer.start(getattr(self, "LED_PULSE_MS", 70))


    def rx_led_on(self):

        self.rx_led_poll()


    def rx_led_poll(self):

        # RX는 bulkCmd 내부 row/varBind 개수가 아니라 실제 응답 패킷 기준으로 1회만 표시합니다.
        # TX와 동일한 70ms 펄스/최소 간격을 적용해 TX/RX 1:1 패턴이 눈에 맞게 보이도록 합니다.
        now = time.monotonic()
        if now - getattr(self, "_last_rx_led_ts", 0.0) < getattr(self, "LED_MIN_INTERVAL_SEC", 0.12):
            return

        self._last_rx_led_ts = now
        self.rx_led.setStyleSheet(
            "background:#00C853;border-radius:8px;"
        )
        self.rx_timer.start(getattr(self, "LED_PULSE_MS", 70))


    def rx_led_trap(self):

        self.rx_led.setStyleSheet(
            "background:#FF9800;border-radius:8px;"
        )
        self.rx_timer.start(120)

    def tx_led_off(self):

        self.tx_led.setStyleSheet(
            "background:#505050;border-radius:8px;"
        )


    def rx_led_off(self):

        self.rx_led.setStyleSheet(
            "background:#505050;border-radius:8px;"
        )

    def update_time_from_trap(self):

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.update_time_label.setText(
            f"최종업데이트시간 : {now}"            
        )
    
    def closeEvent(self, event):
    
        # 이미 연결 중이면 종료 로직 호출
        if self.is_connected:
            self.on_connect_clicked()

        if self.is_operation_recording() or getattr(
            self, "operation_record_thread", None
        ) is not None:
            self.stop_operation_data_recording()
        
        dprint("DEBUG","🔥 프로그램 종료 시작")

        for module_no, thread in list(
            getattr(self, "epo_cutoff_threads", {}).items()
        ):
            if thread:
                self.stop_thread(thread, f"EPO_{module_no}")
        self.epo_cutoff_threads = {}

        # 🔥 1. thread 종료 (중앙에서만 관리)
        for attr_name, log_name in (
            ("snmp_thread", "SNMP"),
            ("trap_thread", "TRAP"),
            ("local_trap", "LOCAL_TRAP"),
            ("ping_thread", "PING"),
            ("register_thread", "REGISTER"),
            ("trap_retransmit_thread", "TRAP_RETRANSMIT"),
        ):
            thread = getattr(self, attr_name, None)
            if thread:
                self.stop_thread(thread, log_name)
                setattr(self, attr_name, None)

        # 🔥 2. Master 파일 정리
        if self.is_master:
            master_file = os.path.join(os.path.dirname(self.profile_path), "master_profile.txt")
            if os.path.exists(master_file):
                os.remove(master_file)
                dprint("DEBUG","🔥 master_profile.txt 삭제됨")

        dprint("DEBUG","🔥 프로그램 종료 완료")

        event.accept()
    
        
    def show_module_detail(self, module_no):
        dialog = ModuleDetailDialog(module_no, self)
        dialog.exec()

    def show_all_module_details(self):
        if not self.module_map:
            QMessageBox.information(
                self, "데이터 없음",
                "전체정보를 표시할 모듈 데이터가 아직 없습니다."
            )
            return
        dialog = AllModuleDetailDialog(self)
        dialog.exec()
        
    def show_auto_close_message(self, title, message, duration_ms=1500):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.Ok)

        QTimer.singleShot(duration_ms, msg.accept)
        msg.exec()

    def show_timed_guide_message(
        self, title, message, icon=QMessageBox.Warning, duration_ms=10000
    ):
        """조치 가이드를 표시하고 확인 클릭 또는 지정 시간 경과 시 닫는다."""
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setTextFormat(Qt.RichText)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.Ok)
        ok_button = msg.button(QMessageBox.Ok)
        if ok_button is not None:
            ok_button.setText("확인")

        if duration_ms is not None:
            QTimer.singleShot(duration_ms, msg.accept)
        msg.exec()

    @staticmethod
    def describe_trap_bind_error(error_text):
        """운영체제의 UDP 바인딩 오류를 사용자가 이해할 수 있게 변환한다."""
        normalized = str(error_text or "").lower()
        if "10048" in normalized or "address already in use" in normalized:
            return "선택한 UDP 포트를 다른 프로그램 또는 서비스가 이미 사용 중입니다."
        if "10013" in normalized or "permission" in normalized or "access" in normalized:
            return "UDP 포트를 열 권한이 없거나 보안 정책에서 사용을 차단했습니다."
        if "10049" in normalized or "cannot assign requested address" in normalized:
            return "현재 PC에서 사용할 수 없는 수신 주소로 바인딩을 시도했습니다."
        return "운영체제에서 UDP 수신 포트를 열지 못했습니다."

    def show_snmp_connection_failure_guide(self, error_text):
        ip = self.ip_edit.text().strip()
        port = self.port_edit.text().strip()
        technical_reason = str(error_text or "응답 시간 초과 또는 원인 정보 없음")
        message = (
            f"<b>*축전지 시스템의 SNMP 응답을 받지 못했습니다.</b><br><br>"
            f"대상: <b>{ip}:{port}/UDP</b><br>"
            f"오류: {technical_reason}<br><br>"
            "<b>*확인 및 조치 방법</b><br>"
            "1. 대상 장비의 전원과 네트워크 연결을 확인합니다.<br>"
            "2. IP 주소와 SNMP Port가 장비 설정과 같은지 확인합니다.<br>"
            "3. 장비에서 SNMP 서비스와 SNMP v2c가 활성화되어 있는지 확인합니다.<br>"
            "4. GET Community 문자열과 장비의 접근 허용 IP(ACL)를 확인합니다.<br>"
            "5. PC·네트워크 방화벽에서 대상 UDP 포트 통신을 허용합니다.<br><br>"
            "※ 이 Port는 프로그램의 로컬 수신 포트가 아니라 대상 장비의 "
            "SNMP GET/SET 서비스 포트입니다."
        )
        self.show_timed_guide_message(
            "SNMP 접속 실패 - 확인 및 조치 안내",
            message,
            QMessageBox.Critical,
            None
        )

    def handle_trap_listener_status(self, success, error_text):
        if success:
            dprint("SNMP", "[TRAP] listener bind confirmed")
            return

        trap_port = self.trap_port_edit.text().strip()
        reason = self.describe_trap_bind_error(error_text)
        message = (
            f"<b>*SNMP 접속은 정상이나 Trap 이벤트 수신 포트를 열지 못했습니다.</b><br><br>"
            f"수신 포트: <b>0.0.0.0:{trap_port}/UDP</b><br>"
            f"원인: {reason}<br>"
            f"상세 오류: {str(error_text or '원인 정보 없음')}<br><br>"
            "<b>*영향</b><br>"
            "주기적인 SNMP 상태 조회는 계속되지만 실시간 알람/복구 Trap은 "
            "수신할 수 없습니다.<br><br>"
            "<b>*확인 및 조치 방법</b><br>"
            "1. Windows SNMP Trap 서비스 또는 동일 포트를 쓰는 프로그램을 종료합니다.<br>"
            "2. 다른 UDP Trap Port를 사용한다면 장비의 Trap 목적지 포트도 동일하게 변경합니다.<br>"
            "3. Windows 방화벽에서 해당 UDP 포트의 인바운드 수신을 허용합니다.<br>"
            "4. 권한 오류가 계속되면 관리자 권한 및 보안 정책을 확인합니다.<br>"
            "5. 조치 후 프로그램 접속을 종료하고 다시 시작합니다."
        )
        self.show_timed_guide_message(
            "Trap 수신 포트 실패 - 제한 기능 및 조치 안내",
            message,
            QMessageBox.Warning,
            None
        )

    def show_initial_load_message(self):
        self.close_initial_load_message()

        self.initial_load_started_at = time.monotonic()
        self.initial_load_message = QMessageBox(self)
        self.initial_load_message.setIcon(QMessageBox.Information)
        self.initial_load_message.setWindowTitle("정보 수신 중")
        self.initial_load_message.setStandardButtons(QMessageBox.Close)
        close_button = self.initial_load_message.button(QMessageBox.Close)
        if close_button is not None:
            close_button.setText("닫기")
        self.initial_load_message.rejected.connect(
            self.dismiss_initial_load_message
        )
        self.update_initial_load_message()
        self.initial_load_message.show()
        self.initial_load_timer.start(1000)

    def dismiss_initial_load_message(self):
        """안내창만 닫고 실제 SNMP 정보 수신은 계속 진행한다."""
        self.initial_load_timer.stop()
        message = self.initial_load_message
        self.initial_load_message = None
        if message is not None:
            message.deleteLater()

    def update_initial_load_message(self):
        if self.initial_load_message is None or self.initial_load_started_at is None:
            return

        elapsed = max(0, int(time.monotonic() - self.initial_load_started_at))
        estimated_seconds = self.settings.value(
            "connection/initial_load_seconds", 0, type=float
        )

        message = "현재 축전지 시스템으로부터 정보를 수신 중에 있습니다..."
        if estimated_seconds > 0:
            remaining = max(0, int(round(estimated_seconds - elapsed)))
            message += f"\n\n약 {remaining}초 남았습니다."
        else:
            message += f"\n\n수신 경과 시간: {elapsed}초"

        self.initial_load_message.setText(message)

    def close_initial_load_message(self, completed=False):
        if completed and self.initial_load_started_at is not None:
            elapsed = max(1.0, time.monotonic() - self.initial_load_started_at)
            previous = self.settings.value(
                "connection/initial_load_seconds", 0, type=float
            )
            # 최근 환경 변화도 반영하면서 순간적인 편차는 완화한다.
            estimated = elapsed if previous <= 0 else (previous * 0.7 + elapsed * 0.3)
            self.settings.setValue("connection/initial_load_seconds", estimated)
            self.settings.sync()

        self.initial_load_timer.stop()
        self.initial_load_started_at = None
        if self.initial_load_message is not None:
            self.initial_load_message.accept()
            self.initial_load_message.deleteLater()
            self.initial_load_message = None

    def handle_connection_test(self, success, value):
        # 접속 시험 결과가 확정된 뒤에만 버튼을 다시 활성화한다.
        self.connect_btn.setText("접속종료" if success else "접속시작")
        self.connect_btn.setEnabled(True)

        ip = self.ip_edit.text().strip()
        port = self.port_edit.text().strip()
        get_comm = self.get_comm_edit.text().strip()
        set_comm = self.set_comm_edit.text().strip()
        trap_comm = self.trap_comm_edit.text().strip()
        trap_port = int(self.trap_port_edit.text().strip() or 0)
            
        if success:
            # 🔥 profile 저장 (접속 성공 시)
            self.settings.setValue("ip", ip)
            self.settings.setValue("port", port)
            self.settings.setValue("get_comm", get_comm)
            self.settings.setValue("set_comm", set_comm)
            self.settings.setValue("trap_comm", trap_comm)
            if self.is_master:
                self.settings.setValue("trap_port", trap_port)
            
            # Slave의 0 값은 자동 할당, 51000~52000 값은 수동 지정으로 처리
            if self.is_slave:
                if not 51000 <= trap_port <= 52000:
                    trap_port = self.allocate_local_trap_port()
                elif not self.is_local_trap_port_available(trap_port):
                    QMessageBox.information(
                        self, "Trap 포트 자동 변경",
                        f"UDP {trap_port} 포트가 사용 중이어서 다른 포트를 자동 할당합니다."
                    )
                    trap_port = self.allocate_local_trap_port()
                self.local_trap_port = trap_port
                self.settings.setValue("local_trap_port", trap_port)
                self.trap_port_edit.setText(str(trap_port))
            # 🔊 Alarm 저장
            self.settings.setValue("alarm/volume", self.alarm_volume_level)

            for level, enabled in self.alarm_level_enable.items():
                self.settings.setValue(f"alarm/level/{level}", enabled)
                
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
            
            if hasattr(self, "local_trap") and self.local_trap:
                self.local_trap.stop()
            
            # 🔥 polling 시작
            self.snmp_thread = SNMPThread(ip, community, port, once=False)
            self.snmp_thread.tx_signal.connect(self.tx_led_on)
            #self.snmp_thread.rx_signal.connect(self.rx_led_on)
            self.snmp_thread.rx_signal.connect(self.rx_led_poll)
            self.snmp_thread.parent_ui = self
            self.snmp_thread.result_signal.connect(self.handle_snmp_result)
            self.snmp_thread.initial_load_complete_signal.connect(
                lambda: self.close_initial_load_message(completed=True)
            )
            self.snmp_thread.soc_charge_limit_signal.connect(
                self.handle_soc_charge_limit_result
            )
            self.show_initial_load_message()
            self.snmp_thread.start()
            trap_port = int(self.trap_port_edit.text().strip())

            # ============================
            # 🔥 Master / Slave 분기
            # ============================
            if self.is_master:

                print(
                    #f"[TRAP TEST] Master 모드: UDP {trap_port} 직접 수신 시작",
                    flush=True
                )
                dprint("DEBUG",f"🔥 MASTER: Trap listen {trap_port}")
                # 기존 SNMP Trap 수신
                self.trap_thread = SNMPTrapThread(
                    listen_ip="0.0.0.0",
                    port=trap_port,
                    community=trap_comm
                )

                self.trap_thread.rx_signal.connect(self.rx_led_trap)
                self.trap_thread.trap_time_signal.connect(self.update_time_from_trap)
                self.trap_thread.trap_signal.connect(self.handle_trap)
                self.trap_thread.listener_status_signal.connect(
                    self.handle_trap_listener_status
                )
                self.trap_thread.start()

            else:
                local_port = int(self.settings.value("local_trap_port", 0))
                print(
                    #f"[TRAP TEST] Slave 모드: UDP {local_port} 로컬 전달 수신",
                    flush=True
                )
                dprint("DEBUG",f"🔥 Slave: LocalTrapReceiver start {local_port}")
                # Slave → Local Trap 수신 시작 후 Master에 IP/포트 등록
                try:
                    self.start_slave_trap_listener(local_port, register=True)
                except Exception as e:
                    dprint("SNMP", f"[TRAP] Slave listener start failed: {e}")
                    self.handle_trap_listener_status(False, str(e))

        else:
            self.show_snmp_connection_failure_guide(value)

    
    def show_alarm_popup(self):
        alarm_names = [
            "Battery Fuse Broken",
            "Lithium battery Missing",
            "Lithium battery communication failure",
            "Lithium battery communication has failed.",
            "All Lithium Battery Communication Failure",
            "Upgrade Failed",
            "Low temperature protection",
            "Low temperature discharge",
            "High temperature protection",
            "Charging overvoltage",
            "Overcharge",
            "Overdischarge",
            "Overcharge Protection",
            "Overdischarge Protection",
            "Charging Overcurrent Protection",
            "Heavy load Overcurrent Protection",
            "Discharge Overcurrent Protection",
            "Upgrade failure",
            "Busbar overvoltage protection",
            "Input reverse connection",
            "Abnormal shutdown",
            "Unlock failure",
            "Board hardware fault",
            "BMU Missing",
            "Lithium Battery Protection",
            "Discharge Low Temperature",
            "Charge Overcurrent Protection",
            "Discharge High Temperature Protection",
            "Charge High Temperature Protection",
            "Discharge Low Temperature Protection",
            "Charge Low Temperature Protection",
            "High Battery Temperature",
            "Low Battery Temperature",
            "Low Temperature",
            "Overall Lithium Battery Protection",
            "Overvoltage Protection",
            "Undervoltage Protection",  
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

        self.alarm_level_text = {
            1: "Critical",
            2: "Major",
            3: "Minor",
            4: "Warning",
            255: "Unknown"
        }

        # 🔴 이미 열려있으면 재사용
        if hasattr(self, "alarm_dialog") and self.alarm_dialog.isVisible():
            self.alarm_dialog.raise_()
            return

        dialog = QDialog(self)
        self.alarm_dialog = dialog

        dialog.setWindowTitle("Active Alarm List")
        dialog.resize(1000, 600)

        dialog.setWindowFlags(
            dialog.windowFlags()
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.Window
        )

        table = QTableWidget()
        table.setRowCount(len(alarm_names))
        table.setColumnCount(12)

        headers = ["Active Alarm List", "시스템"] + [f"모듈-{i}" for i in range(1, 11)]
        table.setHorizontalHeaderLabels(headers)

        header = table.horizontalHeader()
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

        # 🔴 Alarm 이름 초기화
        for i, name in enumerate(alarm_names):
            item = QTableWidgetItem(name)
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 0, item)

        # 🔥 매핑 테이블
        alarm_map = {name.lower(): i for i, name in enumerate(alarm_names)}

        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        # --------------------------------
        # 🔥 실시간 업데이트 함수
        # --------------------------------
        def update_table():

            # 정의된 목록과 매칭되지 않는 Alarm Text는 팝업 하단에 동적으로 추가한다.
            undefined_alarm_rows = {}
            for alarm in self.current_alarm_table:
                text = str(alarm.get("text", "")).strip()
                text_lower = text.lower()

                is_defined = any(key in text_lower for key in alarm_map)
                if not is_defined:
                    display_text = text if text else "(Alarm Text 없음)"
                    undefined_key = display_text.lower()
                    if undefined_key not in undefined_alarm_rows:
                        undefined_alarm_rows[undefined_key] = (
                            len(alarm_names) + len(undefined_alarm_rows),
                            display_text,
                        )

            table.setRowCount(len(alarm_names) + len(undefined_alarm_rows))
            table.clearContents()

            # 이름 다시 세팅 (clearContents 때문에 필요)
            for i, name in enumerate(alarm_names):
                item = QTableWidgetItem(name)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(i, 0, item)

            # 미정의 알람 행은 행 전체를 흐린 회색으로 구분한다.
            undefined_background = QColor("#E9ECEF")
            for row, display_text in undefined_alarm_rows.values():
                for col in range(table.columnCount()):
                    item = QTableWidgetItem(display_text if col == 0 else "")
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setBackground(undefined_background)
                    table.setItem(row, col, item)

            for alarm in self.current_alarm_table:

                text = str(alarm.get("text", "")).strip()
                time = alarm.get("time", "")
                level_raw = alarm.get("level", 255)

                # Level 변환
                try:
                    level_value = int(str(level_raw).strip())
                except:
                    level_value = 255

                alarm_level = self.alarm_level_text.get(level_value, "Unknown")

                # 🔥 부분 매칭 (핵심)
                text_lower = text.strip().lower()
                row = None
                for key, idx in alarm_map.items():
                    if key in text_lower:
                        row = idx
                        break

                if row is None:
                    display_text = text if text else "(Alarm Text 없음)"
                    row = undefined_alarm_rows[display_text.lower()][0]

                # --------------------------------
                # 🔥 module 매핑
                # --------------------------------
                row_index = alarm.get("row_index")

                module_col = 1   # 🔥 기본은 "시스템 컬럼"

                if row_index is not None:

                    module_no = self.row_to_module.get(str(row_index))

                    if module_no is not None:
                        try:
                            module_no = int(module_no)
                            module_col = 1 + module_no
                        except:
                            module_col = 1   # 🔥 실패 시 시스템으로

                # 🔥 컬럼 범위 체크
                if module_col >= table.columnCount():
                    module_col = 1   # 🔥 강제 시스템 처리

                item_text = f"{time}\n({alarm_level})"

                item = QTableWidgetItem(item_text)
                item.setTextAlignment(Qt.AlignCenter)

                # 🔥 Level 색상 (가독성)
                if row >= len(alarm_names):
                    item.setBackground(undefined_background)
                elif level_value == 1:
                    item.setBackground(QColor("#FF4D4F"))
                elif level_value == 2:
                    item.setBackground(QColor("#FFA940"))
                elif level_value == 3:
                    item.setBackground(QColor("#FFD666"))
                elif level_value == 4:
                    item.setBackground(QColor("#91D5FF"))

                table.setItem(row, module_col, item)

            table.viewport().update()

        # 🔥 타이머로 실시간 업데이트
        timer = QTimer(dialog)
        timer.timeout.connect(update_table)
        timer.start(1000)

        # 최초 1회 실행
        update_table()

        layout = QVBoxLayout()
        layout.addWidget(table)
        dialog.setLayout(layout)

        dialog.exec()
    
    def update_fail_ui(self):
        count = self.snmp_fail_count
        snmp_total_fail_count  = self.snmp_total_fail_count
        self.fail_label.setText(f"Timeout : {count} / {snmp_total_fail_count}")
    
        # 🔥 색상 단계별 변경
        if count == 0:
            color = "#8E44AD"   # 보라
        elif count < 10:
            color = "#E67E22"   # 주황
        else:
            color = "#E74C3C"   # 빨강

        self.fail_label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 2px 6px;")
    
    def stop_thread(self, thread, name="THREAD"):
        if thread and thread.isRunning():
            dprint(name, f"[INFO] Stopping {name}")

            thread.stop()   # 사용자 정의 종료 플래그
            thread.quit()   # 이벤트 루프 종료 요청

            if not thread.wait(3000):
                dprint(name, f"[WARN] {name} did not stop in time")
                # ⚠️ terminate는 진짜 마지막에만
                thread.terminate()
                thread.wait(1000)
            
    # ===== 이전 UI 함수는 그대로 두고 save/load_site_info 적용 =====
    def on_connect_clicked(self):

        # ======================================
        # 종료 모드
        # ======================================
        if self.is_connected:

            #print("[INFO] Disconnect requested")
            dprint("MODULE", "[INFO] Disconnect requested")
            if self.is_operation_recording() or getattr(
                self, "operation_record_thread", None
            ) is not None:
                self.stop_operation_data_recording()
            self.close_initial_load_message()
            self.has_ever_connected = False
            self.snmp_fail_count = 0
            self.timeout_popup_shown = False
            self.timeout_disconnect_popup_shown = False
            self.update_fail_ui()

            # blink 중지
            if hasattr(self, "alarm_blink_timer"):
                self.alarm_blink_timer.stop()
                if self.alarm_active:
                    self.set_alarm_popup_style(True)
                else:
                    self.set_alarm_popup_style(False)

            self.tx_led_off()
            self.rx_led_off()
            
            # SNMP Polling Thread 종료
            if hasattr(self, "snmp_thread") and self.snmp_thread:
                self.stop_thread(self.snmp_thread, "SNMP")
                self.snmp_thread = None
            # Trap Thread 종료
            if hasattr(self, "trap_thread") and self.trap_thread:
                self.stop_thread(self.trap_thread, "SNMP")
                self.trap_thread = None
            
            if hasattr(self, "ping_thread") and self.ping_thread:
                self.stop_thread(self.ping_thread, "SNMP")
                self.ping_thread = None

            if self.is_slave:
                self.slave_heartbeat_timer.stop()
                self.register_to_master("unregister")

            if self.local_trap:
                self.stop_thread(self.local_trap, "LOCAL_TRAP")
                self.local_trap = None
                
            # 상태/데이터 초기화
            self.is_connected = False
            self.update_full_cutoff_button_state()

            self.connect_btn.setText("접속시작")
            self.status_circle.setStyleSheet(
                "background-color: #CCCCCC; border-radius: 7px;"
            )
            self.btn_module_order.setEnabled(False)
            self.show_auto_close_message("접속 종료", "축전지 시스템 연결 종료.")

            #print("[INFO] Disconnected")
            dprint("MODULE", "[INFO] Disconnected")

            return
        
        # 이미 테스트 thread가 실행중이면 실행 금지
        if hasattr(self, "test_thread") and self.test_thread:
            if self.test_thread.isRunning():
                #print("[WARN] Connection test already running")
                dprint("MODULE", "[WARN] Connection test already running")
                return

        if getattr(self, "connection_start_pending", False):
            return

        # 이전 현장의 모듈 정보를 먼저 지우고 5초 후 새 연결을 시작한다.
        self.reset_module_state(for_reconnect=True)
        self.connection_start_pending = True
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("접속대기")
        dprint("MODULE", "[INFO] 모듈 상태 초기화 완료, 즉시 접속 시작")
        QTimer.singleShot(0, self.start_delayed_connection)

    def start_delayed_connection(self):
        if not getattr(self, "connection_start_pending", False):
            return

        self.connection_start_pending = False

        # ======================================
        # 접속 시도 (1회 테스트)
        # ======================================
        ip = self.ip_edit.text().strip()
        port = self.port_edit.text().strip()
        community = self.get_comm_edit.text().strip()

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
            2: ("Sleep", "#A6A9AD"),
            3: ("Disconnect", "#FF6B6B"),
            4: ("충전중", "#B2F2BB"),
            5: ("방전중", "#4DABF7"),
            6: ("Standby", "#FFD43B"),
            255: ("Unknown", "#CED4DA")
        }
        # -----------------
        # 모듈 알람 목록 생성
        # -----------------        
        alarm_modules = {}   # module_no : max_level

        for alarm in self.current_alarm_table:

            # 🔥 level 처리
            try:
                level = int(alarm.get("level", 255))
            except (ValueError, TypeError):
                level = 255

            if level not in (1, 2, 3, 4):
                level = 255

            module_no = None

            # 🔥 1차: row_index 기반
            row_index = alarm.get("row_index")
            if row_index is not None:
                module_no = self.row_to_module.get(str(row_index))

            # 🔥 2차: fallback
            if module_no is None:
                equip = alarm.get("equip")
                if equip is not None:
                    module_no = self.equip_to_module.get(str(equip))

            if module_no is None:
                continue

            # 🔥 타입 보정
            try:
                module_no = int(module_no)
            except:
                continue

            # 🔥 최고 레벨 유지 (숫자 낮을수록 위험)
            if module_no in alarm_modules:
                alarm_modules[module_no] = min(alarm_modules[module_no], level)
            else:
                alarm_modules[module_no] = level
        
        for module_no, module_info in self.module_map.items():            

            row_index = module_info["row_index"]

            if row_index not in self.module_data:
                continue

            data = self.module_data[row_index]
            
            if not data:
                continue

            # =========================
            # 🔥 여기 추가 (핵심 위치)
            # =========================
            row = (module_no - 1) % 5
            table = self.module_table_left if module_no <= 5 else self.module_table_right

            table.item(row, 1).setText("-")
            table.item(row, 2).setText("- / -")
            table.item(row, 3).setText("- / -")
            table.item(row, 5).setText("-")
            table.item(row, 4).setText("-")
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

                status = data["status"]   # 🔥 핵심: 변수로 통일

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
                
                # 🔥 버튼 활성화 조건
                #print(f"[DEBUG] module_no={module_no}, status={status}, has_btn={module_no in self.cutoff_buttons}")
                #print(f"[DEBUG] RAW status = {data['status']} ({type(data['status'])})")
                if module_no in self.cutoff_buttons:
                    if getattr(self, "full_cutoff_active", False):
                        self.cutoff_buttons[module_no].setEnabled(False)
                    elif status in (4, 5, 6):
                        self.cutoff_buttons[module_no].setEnabled(True)
                    else:
                        self.cutoff_buttons[module_no].setEnabled(False)
                
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

            alarm_item.setBackground(QColor("white"))
            alarm_item.setForeground(QColor("black"))
            
            if module_no in alarm_modules:

                try:
                    level = int(alarm_modules.get(module_no, 0))
                except (ValueError, TypeError):
                    level = 0

                alarm_text = "이상"

                # 🔴 Level별 색상 (가독성 최적화)
                if level == 1:      # Critical
                    bg_color = "#E03131"   # 딥 레드 (눈 덜 아픔)
                    fg_color = "white"

                elif level == 2:    # Major
                    bg_color = "#F76707"   # 오렌지 레드
                    fg_color = "white"

                elif level == 3:    # Minor
                    bg_color = "#FFD43B"   # 옐로우
                    fg_color = "black"

                elif level == 4:    # Warning (선택적)
                    alarm_text = "정상"
                    bg_color = "#74C0FC"   # 연한 블루
                    fg_color = "black"

                else:               # fallback                    
                    bg_color = "#DEE2E6"   # 회색
                    fg_color = "black"

                alarm_item.setBackground(QColor(bg_color))
                alarm_item.setForeground(QColor(fg_color))

            else:
                alarm_text = "정상"
                alarm_item.setForeground(QColor("#1E293B"))
                alarm_item.setBackground(QColor("#B2F2BB"))

            alarm_item.setText(alarm_text)

        # 접속 중이고 차단 명령을 받을 수 있는 모듈이 하나라도 있을 때만
        # EPO 전체차단 버튼을 활성화한다.
        self.update_full_cutoff_button_state()
            
    def update_summary_value(self, label, value, status="정상"):
        if label not in self.summary_position_map:
            return

        row, col = self.summary_position_map[label]
        item = self.summary_table.item(row, col)
        if item is None:
            return

        item.setText(str(value))
        apply_value_style(item, status)
    
    # ======================
    # 🔔 Alarm Blink
    # ======================
    def set_alarm_popup_style(self, alarm_on=False):
        """
        알람 버튼의 크기/테두리/padding을 항상 동일하게 유지한다.
        blink 시 background/color만 바뀌게 하여 주변 테이블 layout 흔들림을 방지한다.
        """
        if not hasattr(self, "btn_alarm_popup"):
            return

        if alarm_on:
            bg_color = "#D32F2F"
            fg_color = "white"
            border_color = "#D32F2F"
        else:
            bg_color = "#F1F3F5"
            fg_color = "#2C3E50"
            border_color = "#9E9E9E"

        self.btn_alarm_popup.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg_color};
            color: {fg_color};
            border: 1px solid {border_color};
            border-radius: 5px;
            padding: 1px 8px;
            font-weight: bold;
            min-width: 155px;
            max-width: 155px;
            min-height: 24px;
            max-height: 24px;
        }}
        QPushButton:disabled {{
            background-color: #E9ECEF;
            color: #868E96;
            border: 1px solid #ADB5BD;
            border-radius: 5px;
            padding: 1px 8px;
            font-weight: bold;
            min-width: 155px;
            max-width: 155px;
            min-height: 24px;
            max-height: 24px;
        }}
        QPushButton:hover {{
            background-color: {bg_color};
        }}
        """)

    def blink_alarm_button(self):

        if not self.alarm_active:
            self.set_alarm_popup_style(False)
            return

        # 중요: blink 시에도 버튼의 크기/테두리/padding은 고정하고 색상만 변경한다.
        self.set_alarm_popup_style(self.alarm_blink_state)

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
            dprint("SNMP", "Current :", data.get("current"))
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
            # 🟢 성공 시
            self.has_ever_connected = True
            self.snmp_fail_count = 0
            self.timeout_popup_shown = False
            self.timeout_disconnect_popup_shown = False
            self.update_fail_ui()
            
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
            self.equip_to_module.clear()   # 🔥 추가
            self.row_to_module.clear()     # 🔥 추가

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

                    # 🔥 추가 (Summary용)
                    active_alarm_texts.append(val_str)

                elif oid.startswith("1.3.6.1.4.1.2011.6.164.1.1.2.99.1.3."):
                    index = oid.split(".")[-1]

                    if index not in alarm_entries:
                        alarm_entries[index] = {}

                    alarm_entries[index]["level"] = val_str

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
                    
                    # 🔥 이름 변경 Range(3668 ~ 3678)
                    alarm_entries[index]["row_index"] = val_str   
                        
                # ====================================================
                # 1️⃣ Summary 영역
                # ====================================================
                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.5.96":
                    rack_voltage = int(val_str) / 10
                    self.update_summary_value("Rack 전압[V]", f"{rack_voltage:.1f}")

                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.6.96":
                    rack_current = int(val_str) / 10
                    self.update_summary_value("Rack 전류[A]", f"{rack_current:.1f}")

                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.7.96":
                    # Total Capacity (Ah)
                    self.total_capacity = int(val_str) / 10
                    self.update_summary_title()
                    
                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.8.96":
                    self.update_summary_value("SOC 충전율[%]", f"{val_str} %")

                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.13.96":
                    # Battery SOH (%)
                    self.group_soh = int(val_str)
                    self.update_summary_title()
                    
                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.23.96":
                    self.update_summary_value("방전 횟수", val_str)     
    
                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.2.1.13.96":
                    charge_curr_limit = int(val_str) / 100

                    # 🔥 버튼 직접 업데이트
                    if hasattr(self, "charge_limit_button"):
                        self.charge_limit_button.setText(f"{charge_curr_limit:.2f}")
                        # 🔥 다른 정상값과 동일한 연두색 배경 적용
                        self.charge_limit_button.setStyleSheet("""
                            QPushButton {
                                background-color: #D3F9D8;   /* 연두색 */
                                border: 1px solid #B2F2BB;
                                border-radius: 4px;
                                padding: 2px 6px;
                                color: black;
                            }
                        """)
                # ====================================================
                # 2️⃣ hwAcbBaseTable - Module 매핑 (EquipID → ModuleNo)
                # ====================================================
                if ".1.18.1.1.2." in oid:
                    row_index = oid.split(".")[-1]
                    equip_id = val_str

                    equip_oid =   f"1.3.6.1.4.1.2011.6.164.1.18.1.1.2.{row_index}"
                    addr_oid =    f"1.3.6.1.4.1.2011.6.164.1.18.1.1.4.{row_index}"
                    swver_oid =   f"1.3.6.1.4.1.2011.6.164.1.18.1.1.5.{row_index}"
                    model_oid =   f"1.3.6.1.4.1.2011.6.164.1.18.1.1.12.{row_index}"
                    barcode_oid = f"1.3.6.1.4.1.2011.6.164.1.18.1.1.13.{row_index}"

                    barcode_val = value.get(barcode_oid)

                    # 🔥 버튼 활성화
                    if barcode_val:
                        self.module_barcodes_ready = True
                        self.btn_module_order.setEnabled(True)

                    # 🔥 module_no 확보
                    if addr_oid in value:
                        try:
                            module_no = int(value[addr_oid])
                        except (ValueError, TypeError):
                            return

                        # ================================
                        # 🔥 핵심 추가 (인덱스 매핑)
                        # ================================
                        self.row_to_module[row_index] = module_no
                        self.equip_to_module[equip_id] = module_no

                        # ================================
                        # 🔥 module_map 생성
                        # ================================
                        if module_no not in self.module_map:
                            self.module_map[module_no] = {
                                "equip_id": equip_id,
                                "row_index": row_index,
                                "swver": None,
                                "model": None,
                                "barcode": None
                            }

                        # 🔥 안전 접근
                        module_info = self.module_map[module_no]

                        # 🔥 값 갱신
                        module_info["equip_id"] = equip_id
                        module_info["row_index"] = row_index
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
                            "current": None,
                            "status": None,
                            "soc": None,
                            "soh": None,
                            "cells": [None] * 15,
                            "temps": [None] * 15
                        }

                    # 모듈 전압
                    if column == 1:
                        self.module_data[row_index]["volt"] = int(val_str) / 10
                    
                    # 모듈 전류
                    elif column == 2:
                        self.module_data[row_index]["current"] = int(val_str) / 10

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

            # 🔊 사운드 발생 조건 체크
            play_sound = False

            for alarm in self.current_alarm_table:

                level = alarm.get("level")

                try:
                    level = int(level)
                except:
                    continue

                if self.alarm_level_enable.get(level, False):
                    play_sound = True
                    break

            # 🔊 사운드 실행
            if play_sound and self.alarm_volume_level > 0:
                if not self.alarm_sound.isPlaying():
                    self.alarm_sound.play()
            else:
                self.alarm_sound.stop()

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

                self.set_alarm_popup_style(False)
    
            new_fault_snapshot = set()
            new_fault_keys = set()
            # 🔥 Alarm Equip → Module 변환
            self.alarm_modules = set()
            for alarm in self.current_alarm_table:
                equip = alarm.get("equip")
                alarm_text = alarm.get("text")
                alarm_time = alarm.get("time")
                row_index = alarm.get("row_index")

                #print(f"equip:{equip}, row_index:{row_index}, alarm_text:{alarm_text}")

                module_no = None

                # =========================================
                # 🔥 1. row_index 기반 매핑 (우선)
                # =========================================
                if row_index is not None:
                    module_no = self.row_to_module.get(str(row_index))
                    if module_no is not None:
                        module_no = int(module_no)

                # =========================================
                # 🔥 2. equip 기반 fallback
                # =========================================
                if module_no is None and equip is not None:
                    module_no = self.equip_to_module.get(str(equip))
                    if module_no is not None:
                        module_no = int(module_no)

                # =========================================
                # 🔥 3. Board hardware fault (module 없음)
                # =========================================
                alarm_lower = str(alarm_text).lower()

                if module_no is None:

                    if "board hardware fault" in alarm_lower:

                        module_no = 0
                        cell_no = 0

                        fault_key = (module_no, cell_no)
                        new_fault_keys.add(fault_key)
                        new_fault_snapshot.add(fault_key)

                        if fault_key not in self.active_fault_keys:
                            self.add_fault(module_no, cell_no, 0, 0)
                            self.active_fault_keys.add(fault_key)

                        continue

                    else:
                        dprint("SNMP", f"[WARN] module 매핑 실패: equip={equip}, row_index={row_index}")
                        continue

                # =========================================
                # 🔥 정상 module fault 처리
                # =========================================
                module_name = f"모듈-{module_no}"

                self.alarm_modules.add(module_no)
                self.update_module_alarm(module_name, alarm_text, alarm_time)

                # -----------------------------------------
                # Fault 조건
                # -----------------------------------------
                if alarm_text in FAULT_ALARMS:

                    # 🔥 cell 번호 파싱
                    cell_no = 0
                    m = re.search(r'cell\s*(\d+)', alarm_text, re.IGNORECASE)
                    if m:
                        cell_no = int(m.group(1))

                    fault_key = (module_no, cell_no)
                    new_fault_keys.add(fault_key)
                    new_fault_snapshot.add(fault_key)

                    if fault_key not in self.active_fault_keys:

                        volt = 0
                        temp = 0

                        module_info = self.module_map.get(module_no)
                        if module_info:
                            row_idx = module_info["row_index"]
                            data = self.module_data.get(row_idx)

                            if data and cell_no > 0:
                                volt = data["cells"][cell_no-1]
                                temp = data["temps"][cell_no-1]

                        self.add_fault(module_no, cell_no, volt, temp)
                        self.active_fault_keys.add(fault_key)
################################################################################################################################
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
            breaker_fault_active = False
            
            for alarm in active_alarm_texts:

                if "Overcharge Protection" in alarm:
                    overcharge = True

                elif "Charging high temperature protection" in alarm:
                    high_temp = True

                elif "Charging Overcurrent Protection" in alarm:
                    overcurrent = True
                
                elif "Battery Fuse Broken" in alarm:
                    breaker_fault_active = True


            self.set_summary_alarm("과전압 충전차단", overcharge)
            self.set_summary_alarm("고온 충전차단", high_temp)
            self.set_summary_alarm("과전류 충전차단", overcurrent)
            self.set_summary_alarm("차단기 OFF", breaker_fault_active)
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
                    dprint("SNMP", f"module {module_no} → module_map 없음")
                    continue
                
                row_index = module_info["row_index"]
                data = self.module_data.get(row_index)

                #print(f"module_map keys: {list(self.module_map.keys())}")
                #print(f"module_data keys: {list(self.module_data.keys())}")
                if not data:                    
                    dprint("SNMP", f"module {module_no} → module_data 없음")
                    continue

                status = data.get("status")
                volt = data.get("volt")                
                dprint("SNMP", f"module {module_no} status={status} volt={volt}")
                cells = data.get("cells", [])
                dprint("SNMP", f"module {module_no} cells={cells}")

                # 충전중(4), 방전중(5), Standby(6) 모듈만
                # 시스템 요약의 전압/온도 통계 계산에 포함한다.
                if status not in (4, 5, 6):
                    dprint(
                        "SNMP",
                        f"  → 요약 통계 제외 (상태={status})"
                    )
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
        
        # ======================================
        # 🔴 실패 처리 (핵심 추가)
        # ======================================
        if not success:
            # 🔥 한 번도 성공한 적 없으면 무시
            if not self.has_ever_connected:
                return
            
            self.snmp_fail_count += 1
            self.snmp_total_fail_count += 1   # ✅ 누적 카운트 추가
            self.update_fail_ui()
            
            site = self.site_edit.text().strip()
            system = self.system_edit.text().strip()
            ip = self.ip_edit.text().strip()

            # 🔴 5회 실패 → 경고
            if self.snmp_fail_count == 5 and not self.timeout_popup_shown:
                self.timeout_popup_shown = True

                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Timeout 발생")

                msg.setTextFormat(Qt.RichText)
                msg.setText(f"""
                <b>※배터리 시스템</b><br><br>
                <table style="font-size:10pt;">
                    <tr>
                        <td align="left">설치 장소</td>
                        <td width="10">:</td>
                        <td>{site}</td>
                    </tr>
                    <tr>
                        <td align="left">축전지명</td>
                        <td>:</td>
                        <td>{system}</td>
                    </tr>
                    <tr>
                        <td align="left">IP</td>
                        <td>:</td>
                        <td>{ip}</td>
                    </tr>
                </table>
                <br>
                접속 중 Timeout이 발생했습니다.
                """)

                msg.exec_()


            # 🔴 30회 이상 → 접속 강제 종료
            if self.snmp_fail_count >= 30 and not self.timeout_disconnect_popup_shown:
                self.timeout_disconnect_popup_shown = True

                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("연결 종료")

                msg.setTextFormat(Qt.RichText)
                msg.setText(f"""
                <b>※배터리 시스템</b><br><br>
                <table style="font-size:10pt;">
                    <tr>
                        <td align="left">설치 장소</td>
                        <td width="10">:</td>
                        <td>{site}</td>
                    </tr>
                    <tr>
                        <td align="left">축전지명</td>
                        <td>:</td>
                        <td>{system}</td>
                    </tr>
                    <tr>
                        <td align="left">IP</td>
                        <td>:</td>
                        <td>{ip}</td>
                    </tr>
                </table>
                <br>
                지속적인 Timeout으로 접속을 종료합니다.
                """)

                msg.exec_()

                # 🔥 연결 해제 처리 (기존 버튼 로직 재사용)
                if self.is_connected:
                    self.on_connect_clicked()

                return

            return  # 🔴 실패 시 여기서 종료
    
    def update_summary_title(self):
        if self.total_capacity is None or self.group_soh is None:
            return

        capacity = f"{int(self.total_capacity):,}"

        self.summary_group.setTitle(
            f"시스템 요약 정보 (Rack 전체용량: {capacity}Ah, SOH: {self.group_soh}%)"
        )
        
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

        # blink 중에도 1px 테두리 공간은 유지한다.
        # border를 none으로 바꾸면 QLabel의 sizeHint가 달라져 부모 레이아웃과
        # 아래의 고장 정보 영역 높이가 깜박일 때마다 재배치된다.
        widget.no_border_style = re.sub(
            r"border:\s*1px\s*solid\s*[^;]+;",
            "border: 1px solid transparent;",
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
        if item is None:
            return

        if is_alarm:
            item.setText("발생")
            item.setBackground(QColor("#FFD43B"))
            item.setForeground(QColor("black"))
        else:
            item.setText("정상")
            item.setBackground(QColor("#B2F2BB"))
            item.setForeground(QColor("black"))
        
    def handle_trap(self, trap_data):

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        source_ip = trap_data.get("_source_ip")
        local_ip = self.ip_edit.text().strip()

        # 🔧 IP 정규화 (안정성)
        def normalize_ip(ip):
            if not ip:
                return ""
            if "::ffff:" in ip:
                ip = ip.split("::ffff:")[-1]
            if ":" in ip:
                ip = ip.split(":")[0]
            return ip

        source_ip = normalize_ip(source_ip)
        local_ip = normalize_ip(local_ip)
        forwarded_slaves = []

        # =========================
        # Master 모드
        # =========================
        if self.is_master and source_ip:
            dprint("DEBUG", f"[DEBUG] source_ip={source_ip}, local_ip={local_ip}, is_master={self.is_master}")

            # ✅ 1️⃣ 자기 장비 → UI 업데이트
            if source_ip == local_ip:
                dprint("DEBUG", "[TRAP] Local device → UI update")

            # 🔁 2️⃣ 외부 장비 → Slave Forward (등록된 Slave 있을 때만)
            else:
                if hasattr(self, "slave_targets") and len(self.slave_targets) > 0:
                    try:
                        dprint("DEBUG", f"[TRAP] Forward to slaves ({len(self.slave_targets)})")
                        forwarded_slaves = self.forward_trap_to_slaves(
                            trap_data, source_ip
                        )
                    except Exception as e:
                        dprint("DEBUG", f"❌ forward error: {e}")
                else:
                    dprint("DEBUG", "[TRAP] No slave registered → skip forwarding")

        # =========================
        # 🔥 UI 업데이트는 항상 수행
        # =========================
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
            "1.3.6.1.4.1.2011.6.164.2.1.2.0.99": "hwAcbGroupAlarmTrap",
            "1.3.6.1.4.1.2011.6.164.2.1.2.0.100": "hwAcbGroupAlarmResumeTrap"
        }

        display_trap_oid = trap_oid
        if trap_oid in trap_name_map:
            display_trap_oid = f"{trap_oid}:{trap_name_map[trap_oid]}"

        # -----------------------------------------
        # 발생 / 해제 OID 그룹 정의
        # -----------------------------------------
        alarm_oids = {
            "1.3.6.1.4.1.2011.6.164.2.1.2.0.99",
            "1.3.6.1.4.1.2011.6.164.2.1.3.0.99",
            "1.3.6.1.4.1.2011.6.164.2.1.15.0.1",
        }

        resume_oids = {
            "1.3.6.1.4.1.2011.6.164.2.1.2.0.100",
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
        PREFIX_ORDINAL =    "1.3.6.1.4.1.2011.6.164.1.1.2.2.0"
        PREFIX_ALARM =      "1.3.6.1.4.1.2011.6.164.1.1.2.100.1.2."
        PREFIX_LEVEL =      "1.3.6.1.4.1.2011.6.164.1.1.2.100.1.3."
        PREFIX_EQUIP_NAME = "1.3.6.1.4.1.2011.6.164.1.18.1.1.3."
        PREFIX_EQUIP_ID =   "1.3.6.1.4.1.2011.6.164.1.34.1.1.2."
        PREFIX_FATHER_NAME ="1.3.6.1.4.1.2011.6.164.1.34.1.1.3."

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

        # Trap Level 열거값을 알람 등급 명칭으로 표시한다.
        trap_level_map = {
            1: "Critical",
            2: "Major",
            3: "Minor",
            4: "Warning",
            255: "Unknown"
        }
        try:
            level_value = int(str(level).strip())
            display_level = trap_level_map.get(level_value, "Unknown")
        except (TypeError, ValueError):
            display_level = "Unknown"
        
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

         # =====================================================
        # 🔥 차단기 상태 (col 3)
        # =====================================================
        breaker_fault_active_temp_keywords = [
            "battery fuse broken"
        ]
        
        if any(k in alarm_lower for k in breaker_fault_active_temp_keywords):
            if trap_oid.startswith("1.3.6.1.4.1.2011.6.164.2.1.15."):
                if trap_oid in alarm_oids:
                    self.set_summary_alarm("차단기 상태", True)
                elif trap_oid in resume_oids:
                    self.set_summary_alarm("차단기 상태", False)
        # -----------------------------------------
        # GUI 삽입
        # -----------------------------------------
        row = self.trap_table.rowCount()
        self.trap_table.insertRow(row)

        is_external_master_trap = bool(
            self.is_master and source_ip and source_ip != local_ip
        )
        trap_oid_display = display_trap_oid
        if forwarded_slaves:
            slave_lines = [
                f"({target['system']}:{source_ip})"
                for target in forwarded_slaves
            ]
            trap_oid_display = "\n".join([display_trap_oid] + slave_lines)
        elif is_external_master_trap:
            trap_oid_display = (
                f"{display_trap_oid}\n(Unregistered Slave:{source_ip})"
            )

        values = [
            current_time,
            trap_oid_display,
            ordinal,
            alarm,
            display_level,
            equip_id,
            equip_name,
            father_name
        ]

        for col, val in enumerate(values):

            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item.setToolTip(str(val))

            # 발생은 빨강 / 해제는 초록
            if col == 1:
                if trap_oid in alarm_oids:
                    item.setBackground(QColor("#FF6B6B"))
                    item.setForeground(QColor("white"))
                elif trap_oid in resume_oids:
                    item.setBackground(QColor("#B2F2BB"))
                    item.setForeground(QColor("black"))

            # Slave Trap 전달 성공/실패를 시간 칸 색으로 구분
            if col == 0 and is_external_master_trap:
                delivery_succeeded = all(
                    target.get("success", False)
                    for target in forwarded_slaves
                ) if forwarded_slaves else False
                if delivery_succeeded:
                    item.setBackground(QColor("#D9F2E3"))
                    item.setForeground(QColor("#166534"))
                else:
                    item.setBackground(QColor("#EEF2F6"))
                    item.setForeground(QColor("#64748B"))

            self.trap_table.setItem(row, col, item)

        if forwarded_slaves or is_external_master_trap:
            self.trap_table.resizeRowToContents(row)

        self.trap_table.scrollToBottom()
        # ⭐ 1000개 유지
        if self.trap_table.rowCount() > MAX_TRAP_LOG:
            self.trap_table.removeRow(0)

        # ⭐ 로그 파일 저장
        self.write_trap_log(current_time, display_trap_oid, ordinal, alarm, level, equip_id, equip_name, father_name)
        
        # Fault Trap 처리
        is_resume = trap_oid in resume_oids
        self.handle_fault_trap(trap_data, is_resume)
        
        #print("[TRAP RECEIVED]")
        dprint("SNMP", "[TRAP RECEIVED]")
        for k, v in trap_data.items():            
            dprint("SNMP", f"[{k}] = [{v}]")

            
 #################################################################################  
        
    def clear_trap_log(self):
        """SNMP Trap 로그 테이블 초기화"""
        if hasattr(self, "trap_table") and self.trap_table is not None:
            self.trap_table.setRowCount(0)

    def request_trap_retransmission(self):
        """축전지 시스템에 미수신 Trap 재전송을 요청한다."""
        if not self.is_connected:
            QMessageBox.warning(self, "재전송 요청 실패", "먼저 축전지 시스템에 접속해 주세요.")
            return

        current_thread = getattr(self, "trap_retransmit_thread", None)
        if current_thread is not None and current_thread.isRunning():
            return

        ip = self.ip_edit.text().strip()
        set_community = self.set_comm_edit.text().strip()
        try:
            port = int(self.port_edit.text().strip())
        except ValueError:
            port = 161

        self.trap_retransmit_btn.setEnabled(False)
        self.trap_retransmit_thread = TrapRetransmitSetThread(
            ip, port, set_community, self
        )
        self.trap_retransmit_thread.result_signal.connect(
            self.handle_trap_retransmit_result
        )
        self.trap_retransmit_thread.finished.connect(
            self.finish_trap_retransmit_request
        )
        self.trap_retransmit_thread.start()
        self.show_auto_close_message(
            "재전송 요청",
            "시스템으로 부터 Trap 재전송을 요청했습니다.",
            duration_ms=1000
        )

    def handle_trap_retransmit_result(self, success, message):
        if not success:
            QMessageBox.warning(self, "재전송 요청 실패", message)

    def finish_trap_retransmit_request(self):
        thread = getattr(self, "trap_retransmit_thread", None)
        if thread is not None:
            thread.deleteLater()
        self.trap_retransmit_thread = None
        if hasattr(self, "trap_retransmit_btn"):
            self.trap_retransmit_btn.setEnabled(True)

    # ===== BatteryMonitorUI 클래스 내부 =====
    def on_summary_item_clicked(self, item):
        if not item:
            return

        row = item.row()
        col = item.column()

        # 🔥 설비정보 (row 1, col 0~4)만 적용
        if row == self.summary_info_row and col <= 4:
            QToolTip.showText(QCursor.pos(), item.text())

    def get_charge_limit(self):
        try:
            ip = self.ip_edit.text().strip()
            community = self.get_comm_edit.text().strip()
            
            try:
                port = int(self.port_edit.text().strip())
            except:
                port = 161

            oid = "1.3.6.1.4.1.2011.6.164.1.17.2.1.13.96"

            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),
                UdpTransportTarget((ip, port), timeout=2, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )

            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

            if errorIndication:
                return False, str(errorIndication)

            if errorStatus:
                return False, errorStatus.prettyPrint()

            for varBind in varBinds:
                val = int(varBind[1])
                return True, val

        except Exception as e:
            return False, str(e)
    
    def set_charge_limit(self, value):
        try:
            ip = self.ip_edit.text().strip()
            set_community = self.set_comm_edit.text().strip()

            try:
                port = int(self.port_edit.text().strip())
            except:
                port = 161

            oid = "1.3.6.1.4.1.2011.6.164.1.17.2.1.13.96"

            if not (5 <= value <= 105):
                return False, "SNMP 값 범위 오류 (5~105)"

            iterator = setCmd(
                SnmpEngine(),
                CommunityData(set_community, mpModel=1),
                UdpTransportTarget((ip, port), timeout=2, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid), Unsigned32(value))
            )

            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

            if errorIndication:
                return False, f"ErrorIndication: {errorIndication}"

            if errorStatus:
                return False, f"{errorStatus.prettyPrint()} at {errorIndex}"

            return True, "SET 성공"

        except Exception as e:
            return False, f"Exception: {str(e)}"
        
    def open_charge_limit_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("충전전류제한 설정")

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("충전전류제한 설정 (0.05 ~ 1[C])"))

        input_edit = QLineEdit()
        input_edit.setPlaceholderText("예: 0.5")
        layout.addWidget(input_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def on_ok():
            try:
                value = float(input_edit.text())

                if not (0.05 <= value <= 1.0):
                    QMessageBox.warning(self, "설정 오류", "충전전류제한 설정 범위: 0.05 ~ 1.0[C]")
                    return

                snmp_value = int(value * 100)

                # 🔥 1. SET 시도
                success, msg = self.set_charge_limit(snmp_value)

                if not success:
                    QMessageBox.warning(self, "설정 실패", msg)
                    return

                # 🔥 2. GET 검증
                ok, result = self.get_charge_limit()

                if not ok:
                    QMessageBox.warning(self, "검증 실패", f"GET 실패: {result}")
                    return

                # 🔥 3. 값 비교
                if result == snmp_value:
                    # ✅ 성공
                    if hasattr(self, "charge_limit_button"):
                        self.charge_limit_button.setText(f"{value:.2f}")
                    QMessageBox.information(
                        self,
                        "설정 성공",
                        f"충전 전류 제한 값이 정상적으로 적용되었습니다. ({snmp_value/100:.2f} C)"
                    )
                    dialog.accept()

                else:
                    # ❌ 값 불일치
                    QMessageBox.warning(
                        self,
                        "설정 실패",
                        f"설정값({snmp_value}) ≠ 장비값({result})"
                    )

            except:
                QMessageBox.warning(self, "입력 오류", "숫자를 입력하세요")

        buttons.accepted.connect(on_ok)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()

    SOC_CHARGE_ENABLE_OID = "1.3.6.1.4.1.2011.6.164.1.17.2.1.29.96"
    SOC_CHARGE_VALUE_OID = "1.3.6.1.4.1.2011.6.164.1.17.2.1.30.96"

    SOC_CHARGE_NORMAL_STYLE = """
        QPushButton {
            background-color: #D3F9D8;
            border: 1px solid #B2F2BB;
            border-radius: 4px;
            padding: 2px 6px;
            color: black;
        }
    """
    SOC_CHARGE_UNUSED_STYLE = """
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
            border-radius: 4px;
            padding: 2px 6px;
            color: black;
        }
    """
    SOC_CHARGE_DISABLED_STYLE = """
        QPushButton {
            background-color: #E0E0E0;
            border: 1px solid #C8C8C8;
            border-radius: 4px;
            padding: 2px 6px;
            color: #888888;
        }
    """

    def get_soc_charge_limit(self):
        try:
            ip = self.ip_edit.text().strip()
            community = self.get_comm_edit.text().strip()

            try:
                port = int(self.port_edit.text().strip())
            except:
                port = 161

            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),
                UdpTransportTarget((ip, port), timeout=2, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(self.SOC_CHARGE_ENABLE_OID)),
                ObjectType(ObjectIdentity(self.SOC_CHARGE_VALUE_OID))
            )

            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

            if errorIndication:
                return False, str(errorIndication)

            if errorStatus:
                return False, errorStatus.prettyPrint()

            if len(varBinds) < 2:
                return False, "응답값 부족"

            return True, (int(varBinds[0][1]), int(varBinds[1][1]))

        except Exception as e:
            return False, str(e)

    def set_soc_charge_limit(self, enabled, value):
        try:
            ip = self.ip_edit.text().strip()
            set_community = self.set_comm_edit.text().strip()

            try:
                port = int(self.port_edit.text().strip())
            except:
                port = 161

            if enabled not in (1, 2):
                return False, "SOC 충전제한 사용 여부 값 오류"

            if enabled == 2 and not (1 <= value <= 100):
                return False, "SOC 충전제한 값 범위 오류 (1~100)"

            def set_single_oid(oid, set_value, value_type):
                iterator = setCmd(
                    SnmpEngine(),
                    CommunityData(set_community, mpModel=1),
                    UdpTransportTarget((ip, port), timeout=2, retries=2),
                    ContextData(),
                    ObjectType(
                        ObjectIdentity(oid),
                        value_type(set_value)
                    )
                )

                error_indication, error_status, error_index, var_binds = next(
                    iterator
                )

                if error_indication:
                    return False, f"ErrorIndication: {error_indication}"

                if error_status:
                    return False, f"{error_status.prettyPrint()} at {error_index}"

                return True, "SET 성공"

            # 1. SOC 충전제한 상태 OID를 먼저 SET한다.
            success, message = set_single_oid(
                self.SOC_CHARGE_ENABLE_OID,
                enabled,
                Integer32
            )
            if not success:
                return False, f"상태값 SET 실패: {message}"

            # 사용안함(상태값 1)은 상태 OID만 SET한다.
            if enabled == 1:
                return True, "사용안함 상태값 SET 성공"

            # 장비가 상태값을 처리할 시간을 확보한 후 설정값을 SET한다.
            time.sleep(0.1)

            # 2. SOC 충전제한 설정값 OID를 SET한다.
            success, message = set_single_oid(
                self.SOC_CHARGE_VALUE_OID,
                value,
                Unsigned32
            )
            if not success:
                return False, f"설정값 SET 실패: {message}"

            return True, "상태값 SET 후 500ms 뒤 설정값 SET 성공"

        except Exception as e:
            return False, f"Exception: {str(e)}"

    def handle_soc_charge_limit_result(self, success, result):
        if not hasattr(self, "soc_charge_limit_button"):
            return

        if not success:
            self.soc_charge_limit_fail_count = (
                getattr(self, "soc_charge_limit_fail_count", 0) + 1
            )
            if self.soc_charge_limit_fail_count >= 2:
                self.soc_charge_limit_button.setEnabled(False)
                self.soc_charge_limit_button.setText("-")
                self.soc_charge_limit_button.setStyleSheet(
                    self.SOC_CHARGE_DISABLED_STYLE
                )
            return

        self.soc_charge_limit_fail_count = 0
        self.soc_charge_limit_button.setEnabled(True)

        enabled = result.get("enabled")
        value = result.get("value")
        self.soc_charge_limit_enabled = enabled
        self.soc_charge_limit_value = value

        self.soc_charge_limit_button.setText(
            str(value) if 1 <= value <= 100 else "-"
        )
        if enabled == 2:
            self.soc_charge_limit_button.setStyleSheet(
                self.SOC_CHARGE_NORMAL_STYLE
            )
        else:
            self.soc_charge_limit_button.setStyleSheet(
                self.SOC_CHARGE_UNUSED_STYLE
            )

    def open_soc_charge_limit_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("SOC충전제한 설정")

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("SOC충전제한 설정"))

        radio_90 = QRadioButton("90%")
        radio_95 = QRadioButton("95%")
        radio_100 = QRadioButton("100%")
        radio_unused = QRadioButton("사용안함")

        # 라디오 버튼 순번이 아니라 실제 SNMP 설정값을 직접 보관한다.
        radio_90.setProperty("snmp_value", 90)
        radio_95.setProperty("snmp_value", 95)
        radio_100.setProperty("snmp_value", 100)

        radio_options = [
            (radio_90, 90),
            (radio_95, 95),
            (radio_100, 100),
            (radio_unused, None)
        ]

        for radio, value in radio_options:
            layout.addWidget(radio)
            if (
                value is not None
                and getattr(self, "soc_charge_limit_enabled", None) == 2
                and getattr(self, "soc_charge_limit_value", None) == value
            ):
                radio.setChecked(True)

        if getattr(self, "soc_charge_limit_enabled", None) == 1:
            radio_unused.setChecked(True)
        elif not any(radio.isChecked() for radio, _ in radio_options):
            radio_90.setChecked(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def on_ok():
            if radio_unused.isChecked():
                enabled = 1
                # 사용안함은 설정값 OID를 SET하지 않는다.
                set_value = None
            else:
                enabled = 2
                selected_radio = next(
                    (
                        radio
                        for radio in (radio_90, radio_95, radio_100)
                        if radio.isChecked()
                    ),
                    None
                )
                if selected_radio is None:
                    QMessageBox.warning(
                        self,
                        "설정 실패",
                        "SOC 충전제한 값을 선택하세요."
                    )
                    return

                # 버튼 인덱스가 아닌 90, 95, 100 중 실제 값을 사용한다.
                set_value = int(selected_radio.property("snmp_value"))

            dprint(
                "SNMP",
                f"[SOC SET] 상태값={enabled}, 실제 설정값={set_value}"
            )

            success, msg = self.set_soc_charge_limit(enabled, set_value)
            if not success:
                QMessageBox.warning(self, "설정 실패", msg)
                return

            ok, result = self.get_soc_charge_limit()
            if not ok:
                QMessageBox.warning(self, "검증 실패", f"GET 실패: {result}")
                return

            read_enabled, read_value = result
            setting_matches = (
                read_enabled == enabled
                and (enabled == 1 or read_value == set_value)
            )
            if setting_matches:
                self.handle_soc_charge_limit_result(
                    True,
                    {"enabled": read_enabled, "value": read_value}
                )
                setting_text = (
                    "사용안함"
                    if enabled == 1
                    else f"{set_value}%"
                )
                QMessageBox.information(
                    self,
                    "설정 성공",
                    f"SOC 충전제한이 정상적으로 적용되었습니다. ({setting_text})"
                )
                dialog.accept()
            else:
                QMessageBox.warning(
                    self,
                    "설정 실패",
                    "설정값과 장비에서 다시 읽은 값이 일치하지 않습니다."
                )

        buttons.accepted.connect(on_ok)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()
    
    def create_summary_section(self):
        BUTTON_STYLE = """
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 12px;
            color: black;
        }

        QPushButton:hover {
            background-color: #E7F1FF;
            border: 1px solid #3B82F6;
        }

        QPushButton:pressed {
            background-color: #D0E3FF;
        }
        """

        """시스템 요약 정보 + SNMP Trap 로그 병렬 배치"""
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        ####################################################################
        # 1️⃣ 시스템 요약 정보
        ####################################################################
        self.summary_group = QGroupBox("시스템 요약 정보")
        summary_layout = QVBoxLayout(self.summary_group)

        self.summary_table = QTableWidget(8, 6)
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
            ["설비번호", "운용 관리자", "제조사", "모델명", "상면", ""],
            ["Rack 전압[V]", "SOC 충전율[%]", "Max 전압[V]", "Min 전압[V]", "Avg 전압[V]", ""],
            ["Rack 전류[A]", "방전 횟수", "Max 온도[℃]", "Min 온도[℃]", "Avg 온도[℃]", "EPO(전체모듈)"],
            ["과전압 충전차단", "고온 충전차단", "과전류 충전차단", "차단기 OFF", "충전전류제한[C]", "SOC충전제한[%]"]
        ]

        values = [["-" for _ in range(6)] for _ in range(4)]

        LABEL_BG = QColor(220, 235, 255)
        label_font = QFont()
        label_font.setBold(True)

        # 🔥 summary 값 위치 매핑
        self.summary_position_map = {}

        for block in range(4):
            label_row = block * 2
            value_row = label_row + 1
            
            # 🔥 첫 번째 블록 row 저장
            if block == 0:
                self.summary_info_row = value_row
                
            for col in range(6):

                # ----- 라벨 -----
                label_text = labels[block][col]
                label_item = QTableWidgetItem(label_text)
                label_item.setTextAlignment(Qt.AlignCenter)
                label_item.setBackground(LABEL_BG)
                label_item.setFont(label_font)
                table.setItem(label_row, col, label_item)

                # ----- 값 -----
                if label_text == "충전전류제한[C]":
                    btn = QPushButton("-")
                    btn.setFixedHeight(22)   # 🔥 셀 높이 맞춤
                    btn.setStyleSheet(BUTTON_STYLE)
                    btn.clicked.connect(self.open_charge_limit_dialog)

                    table.setCellWidget(value_row, col, btn)

                    # 🔥 나중에 값 업데이트용 저장
                    self.charge_limit_button = btn

                elif label_text == "SOC충전제한[%]":
                    btn = QPushButton("-")
                    btn.setFixedHeight(22)
                    btn.setStyleSheet(BUTTON_STYLE)
                    btn.clicked.connect(self.open_soc_charge_limit_dialog)

                    table.setCellWidget(value_row, col, btn)
                    self.soc_charge_limit_button = btn

                elif label_text == "EPO(전체모듈)":
                    epo_widget = QWidget()
                    epo_layout = QHBoxLayout(epo_widget)
                    epo_layout.setContentsMargins(0, 0, 0, 0)
                    epo_layout.setSpacing(3)
                    cutoff_btn = QPushButton("차단")
                    cutoff_btn.setEnabled(False)
                    cutoff_btn.setFixedHeight(24)
                    cutoff_btn.setMinimumWidth(44)
                    cutoff_btn.setToolTip("전체 모듈 강제 차단")
                    cutoff_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #DC2626;
                        color: white;
                        border: 1px solid #DC2626;
                        border-radius: 6px;
                        padding: 2px 8px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #B91C1C;
                        border-color: #B91C1C;
                    }
                    QPushButton:pressed {
                        background-color: #991B1B;
                    }
                    QPushButton:disabled {
                        background-color: #E2E8F0;
                        color: #94A3B8;
                        border-color: #CBD5E1;
                    }
                    """)
                    cutoff_btn.clicked.connect(self.confirm_full_cutoff)

                    restore_btn = QPushButton("복구")
                    restore_btn.setEnabled(False)
                    restore_btn.setFixedHeight(24)
                    restore_btn.setMinimumWidth(44)
                    restore_btn.setToolTip("전체 모듈 차단 복구")
                    restore_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #F0FDFA;
                        color: #0F766E;
                        border: 1px solid #14B8A6;
                        border-radius: 6px;
                        padding: 2px 8px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #CCFBF1;
                        border-color: #0D9488;
                    }
                    QPushButton:pressed {
                        background-color: #99F6E4;
                    }
                    QPushButton:disabled {
                        background-color: #F1F5F9;
                        color: #94A3B8;
                        border-color: #CBD5E1;
                    }
                    """)
                    restore_btn.clicked.connect(self.confirm_full_restore)

                    epo_layout.addWidget(cutoff_btn)
                    epo_layout.addWidget(restore_btn)
                    table.setCellWidget(value_row, col, epo_widget)
                    self.full_cutoff_button = cutoff_btn
                    self.full_restore_button = restore_btn

                else:
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

        #table.setFixedSize(width + 2, height + 2)
        table.setFixedSize(width, height-20) #여백 줄이기
        
        # 🔥 셀 클릭 시 전체 텍스트 보기
        table.itemClicked.connect(self.on_summary_item_clicked)

        summary_layout.addWidget(table)
        summary_layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        self.summary_group.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        main_layout.addWidget(self.summary_group)
        ####################################################################
        # 2️⃣ SNMP Trap 로그
        ####################################################################
        trap_group = QGroupBox()
        trap_layout = QVBoxLayout(trap_group)

        trap_title_layout = QHBoxLayout()
        trap_title = QLabel("SNMP Trap 로그 (최대 1000개 저장)")
        trap_title.setStyleSheet("font-weight: bold;")
        trap_title_layout.addWidget(trap_title)

        self.trap_retransmit_btn = QPushButton("재전송요청")
        self.trap_retransmit_btn.setStyleSheet("""
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
        self.trap_retransmit_btn.clicked.connect(self.request_trap_retransmission)
        trap_title_layout.addWidget(self.trap_retransmit_btn)
        trap_title_layout.addStretch()
        trap_layout.addLayout(trap_title_layout)

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
        for column, header_text in enumerate(trap_headers):
            header_item = self.trap_table.horizontalHeaderItem(column)
            if header_item:
                header_item.setToolTip(header_text)
        self.trap_table.verticalHeader().setVisible(False)
        self.trap_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.trap_table.setSelectionBehavior(QTableWidget.SelectRows)

        header = self.trap_table.horizontalHeader()
        header.setStretchLastSection(False)
        # 모든 열을 마우스로 자유롭게 넓히거나 좁힐 수 있게 한다.
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.trap_table.setColumnWidth(0, 145)
        self.trap_table.setColumnWidth(1, 260)
        self.trap_table.setColumnWidth(2, 110)
        self.trap_table.setColumnWidth(3, 240)
        self.trap_table.setColumnWidth(4, 85)
        self.trap_table.setColumnWidth(5, 110)
        self.trap_table.setColumnWidth(6, 160)
        self.trap_table.setColumnWidth(7, 160)

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


    def get_alive_module_numbers(self):
        """접속 상태에서 EPO 차단 명령을 받을 수 있는 모듈 번호를 반환한다."""
        if not self.is_connected:
            return []

        alive_modules = []
        for module_no, module_info in self.module_map.items():
            row_index = module_info.get("row_index")
            data = self.module_data.get(row_index)
            if data and data.get("status") in (4, 5, 6):
                alive_modules.append(module_no)

        return alive_modules

    def update_full_cutoff_button_state(self):
        operation_active = getattr(self, "full_cutoff_active", False)
        if hasattr(self, "full_cutoff_button"):
            self.full_cutoff_button.setEnabled(
                bool(self.get_alive_module_numbers()) and not operation_active
            )
        if hasattr(self, "full_restore_button"):
            self.full_restore_button.setEnabled(
                self.is_connected
                and bool(self.module_map)
                and not operation_active
            )


    def execute_full_cutoff(self):
        """통신 가능한 모듈을 한 번에 하나씩, 100ms 간격으로 차단한다."""
        self.execute_full_epo_operation("차단", 2)

    def execute_full_restore(self):
        """인식된 모듈을 한 번에 하나씩, 100ms 간격으로 복구한다."""
        self.execute_full_epo_operation("복구", 1)

    def execute_full_epo_operation(self, operation, command_value):
        if getattr(self, "full_cutoff_active", False):
            return

        if operation == "차단":
            module_list = sorted(self.get_alive_module_numbers())
        else:
            module_list = sorted(
                int(no)
                for no, info in self.module_map.items()
                if info.get("row_index") is not None
            )

        if not module_list:
            self.show_cutoff_result_popup(
                False, f"{operation} 가능한 모듈이 없습니다.", operation
            )
            return

        self.full_cutoff_active = True
        self.full_epo_operation = operation
        self.full_epo_command_value = int(command_value)
        self.full_cutoff_queue = deque(int(no) for no in module_list)
        self.full_cutoff_current_module = None
        self.full_cutoff_failures = []
        self.full_cutoff_total_count = len(module_list)
        self.full_cutoff_completed_count = 0

        self.update_full_cutoff_button_state()
        for cutoff_btn in self.cutoff_buttons.values():
            cutoff_btn.setEnabled(False)

        self.show_full_cutoff_progress(module_list, operation)
        self.start_next_full_cutoff()

    def show_full_cutoff_progress(self, module_list, operation):
        old_dialog = getattr(self, "full_cutoff_progress_dialog", None)
        if old_dialog is not None:
            old_dialog.close()
            old_dialog.deleteLater()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"전체{operation} 진행상태")
        dialog.setModal(False)
        dialog.setMinimumWidth(390)
        dialog.resize(390, min(500, 175 + len(module_list) * 30))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel(f"모듈별 강제 {operation} 진행상태")
        title.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #1E293B;"
        )
        layout.addWidget(title)

        self.full_cutoff_progress_label = QLabel(
            f"{operation} 준비 중 · 0/{len(module_list)}"
        )
        self.full_cutoff_progress_label.setStyleSheet(
            "color: #475569; font-size: 12px;"
        )
        layout.addWidget(self.full_cutoff_progress_label)

        self.full_cutoff_progress_bar = QProgressBar()
        self.full_cutoff_progress_bar.setRange(0, len(module_list))
        self.full_cutoff_progress_bar.setValue(0)
        self.full_cutoff_progress_bar.setTextVisible(True)
        self.full_cutoff_progress_bar.setFormat("%v / %m 완료")
        self.full_cutoff_progress_bar.setFixedHeight(18)
        self.full_cutoff_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                background: #F1F5F9;
                text-align: center;
                color: #334155;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 7px;
            }
        """)
        layout.addWidget(self.full_cutoff_progress_bar)

        table = QTableWidget(len(module_list), 3)
        table.setHorizontalHeaderLabels(["모듈", "진행상태", "처리시각"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        table.setColumnWidth(0, 70)
        table.setColumnWidth(2, 90)

        self.full_cutoff_progress_rows = {}
        for row, module_no in enumerate(module_list):
            self.full_cutoff_progress_rows[module_no] = row
            module_item = QTableWidgetItem(f"#{module_no:02d}")
            status_item = QTableWidgetItem("대기")
            time_item = QTableWidgetItem("-")
            for item in (module_item, status_item, time_item):
                item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QColor("#64748B"))
            table.setItem(row, 0, module_item)
            table.setItem(row, 1, status_item)
            table.setItem(row, 2, time_item)

        table.resizeRowsToContents()
        self.full_cutoff_progress_table = table
        layout.addWidget(table)

        self.full_cutoff_progress_close_btn = QPushButton("진행 중...")
        self.full_cutoff_progress_close_btn.setEnabled(False)
        self.full_cutoff_progress_close_btn.clicked.connect(dialog.accept)
        self.full_cutoff_progress_close_btn.setStyleSheet("""
            QPushButton {
                background: #2563EB;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1D4ED8; }
            QPushButton:disabled {
                background: #CBD5E1;
                color: #64748B;
            }
        """)
        layout.addWidget(
            self.full_cutoff_progress_close_btn,
            alignment=Qt.AlignRight
        )

        self.full_cutoff_progress_dialog = dialog
        dialog.show()
        dialog.raise_()

    def update_full_cutoff_progress(self, module_no, status, detail=""):
        table = getattr(self, "full_cutoff_progress_table", None)
        row = getattr(self, "full_cutoff_progress_rows", {}).get(module_no)
        if table is None or row is None:
            return

        status_item = table.item(row, 1)
        time_item = table.item(row, 2)
        status_item.setText(status)
        status_item.setToolTip(detail)

        status_styles = {
            "대기": ("#64748B", "#FFFFFF"),
            "진행 중": ("#1D4ED8", "#DBEAFE"),
            "성공": ("#166534", "#DCFCE7"),
            "실패": ("#991B1B", "#FEE2E2"),
        }
        foreground, background = status_styles.get(
            status, ("#334155", "#FFFFFF")
        )
        status_item.setForeground(QColor(foreground))
        status_item.setBackground(QColor(background))

        if status in ("성공", "실패"):
            time_item.setText(datetime.now().strftime("%H:%M:%S"))

        if status == "진행 중":
            operation = getattr(self, "full_epo_operation", "차단")
            self.full_cutoff_progress_label.setText(
                f"모듈 #{module_no:02d} {operation} 진행 중 · "
                f"{self.full_cutoff_completed_count}/{self.full_cutoff_total_count}"
            )

    def finish_full_cutoff_progress(self, failures):
        operation = getattr(self, "full_epo_operation", "차단")
        progress_bar = getattr(self, "full_cutoff_progress_bar", None)
        if progress_bar is not None:
            progress_bar.setValue(self.full_cutoff_total_count)

        label = getattr(self, "full_cutoff_progress_label", None)
        if label is not None:
            if failures:
                label.setText(
                    f"전체{operation} 완료 · 성공 "
                    f"{self.full_cutoff_total_count - len(failures)}개 / "
                    f"실패 {len(failures)}개"
                )
                label.setStyleSheet(
                    "color: #B91C1C; font-size: 12px; font-weight: bold;"
                )
            else:
                label.setText(
                    f"전체{operation} 완료 · "
                    f"{self.full_cutoff_total_count}개 모두 성공"
                )
                label.setStyleSheet(
                    "color: #15803D; font-size: 12px; font-weight: bold;"
                )

        close_btn = getattr(self, "full_cutoff_progress_close_btn", None)
        if close_btn is not None:
            close_btn.setText("닫기")
            close_btn.setEnabled(True)

    def start_next_full_cutoff(self):
        if not getattr(self, "full_cutoff_active", False):
            return

        if not self.full_cutoff_queue:
            failures = list(self.full_cutoff_failures)
            operation = getattr(self, "full_epo_operation", "차단")
            self.full_cutoff_active = False
            self.full_cutoff_current_module = None

            alive_modules = set(self.get_alive_module_numbers())
            for module_no, cutoff_btn in self.cutoff_buttons.items():
                cutoff_btn.setEnabled(module_no in alive_modules)
            self.update_full_cutoff_button_state()
            self.finish_full_cutoff_progress(failures)

            if failures:
                failed_modules = ", ".join(f"{no:02d}" for no in failures)
                self.show_cutoff_result_popup(
                    False,
                    f"실패 모듈: {failed_modules}",
                    operation
                )
            else:
                self.show_cutoff_result_popup(True, operation=operation)
            return

        module_no = self.full_cutoff_queue.popleft()
        self.full_cutoff_current_module = module_no
        self.update_full_cutoff_progress(module_no, "진행 중")
        if not self.execute_cutoff(module_no):
            self.full_cutoff_failures.append(module_no)
            self.full_cutoff_completed_count += 1
            self.update_full_cutoff_progress(
                module_no,
                "실패",
                f"{getattr(self, 'full_epo_operation', '차단')} 요청을 시작할 수 없습니다."
            )
            self.full_cutoff_progress_bar.setValue(
                self.full_cutoff_completed_count
            )
            self.full_cutoff_current_module = None
            QTimer.singleShot(100, self.start_next_full_cutoff)

    def confirm_full_cutoff(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("전체차단 확인")
        msg.setText(
            "⚠ 모든 축전지 모듈에 전원 차단 명령이 실행됩니다.\n"
            "시스템이 즉시 종료될 수 있습니다.\n"
            "정말로 전체차단을 실행하시겠습니까?"
        )

        run_btn = msg.addButton("전체차단 실행", QMessageBox.AcceptRole)
        cancel_btn = msg.addButton("취소", QMessageBox.RejectRole)

        msg.exec_()

        if msg.clickedButton() == run_btn:
            self.execute_full_cutoff()

    def confirm_full_restore(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("전체복구 확인")
        msg.setText(
            "모든 축전지 모듈에 복구 명령이 실행됩니다.\n"
            "정말로 전체복구를 실행하시겠습니까?"
        )

        run_btn = msg.addButton("복구 실행", QMessageBox.AcceptRole)
        msg.addButton("취소", QMessageBox.RejectRole)
        msg.exec_()

        if msg.clickedButton() == run_btn:
            self.execute_full_restore()

    def execute_cutoff(self, module_no):
        module_info = self.module_map.get(module_no)
        row_index = module_info.get("row_index") if module_info else None
        if row_index is None:
            if not getattr(self, "full_cutoff_active", False):
                self.show_cutoff_result_popup(False, "모듈 인덱스를 찾을 수 없습니다.")
            return False

        if not self.is_connected:
            if not getattr(self, "full_cutoff_active", False):
                self.show_cutoff_result_popup(False, "축전지 시스템에 접속되어 있지 않습니다.")
            return False

        if not hasattr(self, "epo_cutoff_threads"):
            self.epo_cutoff_threads = {}

        current_thread = self.epo_cutoff_threads.get(module_no)
        if current_thread is not None and current_thread.isRunning():
            return False

        ip = self.ip_edit.text().strip()
        community = self.set_comm_edit.text().strip()
        try:
            port = int(self.port_edit.text().strip())
        except ValueError:
            port = 161

        cutoff_btn = self.cutoff_buttons.get(module_no)
        if cutoff_btn:
            cutoff_btn.setEnabled(False)

        command_value = (
            getattr(self, "full_epo_command_value", 2)
            if getattr(self, "full_cutoff_active", False)
            else 2
        )
        thread = EpoCutoffThread(
            ip, port, community, row_index, module_no,
            command_value, self
        )
        self.epo_cutoff_threads[module_no] = thread
        thread.result_signal.connect(self.handle_cutoff_result)
        thread.finished.connect(
            lambda no=module_no: self.finish_cutoff_request(no)
        )
        thread.start()
        return True

    def get_cutoff_button_text(self, module_no):
        """프로파일에 저장된 모듈별 마지막 차단 성공 시각을 버튼 문구로 반환한다."""
        cutoff_time = str(
            self.settings.value(f"epo/cutoff_time/{int(module_no)}", "") or ""
        ).strip()
        return f"차단\n({cutoff_time})" if cutoff_time else "차단"

    def handle_cutoff_result(self, success, message, module_no):
        is_full_cutoff = (
            getattr(self, "full_cutoff_active", False)
            and self.full_cutoff_current_module == module_no
        )

        if success:
            operation = (
                getattr(self, "full_epo_operation", "차단")
                if is_full_cutoff else "차단"
            )

            if operation == "복구":
                self.settings.remove(f"epo/cutoff_time/{int(module_no)}")
            else:
                cutoff_time = datetime.now().strftime("%m.%d %H:%M")
                self.settings.setValue(
                    f"epo/cutoff_time/{int(module_no)}", cutoff_time
                )
            self.settings.sync()

            cutoff_btn = self.cutoff_buttons.get(module_no)
            if cutoff_btn:
                cutoff_btn.setText(self.get_cutoff_button_text(module_no))
                self.normalize_module_table_row_heights()
            if is_full_cutoff:
                self.update_full_cutoff_progress(module_no, "성공")
            if not is_full_cutoff:
                self.show_cutoff_result_popup(True)
        else:
            dprint("EPO", f"[FAIL] module={module_no}, reason={message}")
            if is_full_cutoff:
                self.full_cutoff_failures.append(module_no)
                self.update_full_cutoff_progress(module_no, "실패", message)
            else:
                self.show_cutoff_result_popup(False, message)

    def finish_cutoff_request(self, module_no):
        thread = getattr(self, "epo_cutoff_threads", {}).pop(module_no, None)
        if thread is not None:
            thread.deleteLater()

        cutoff_btn = self.cutoff_buttons.get(module_no)
        is_full_cutoff = (
            getattr(self, "full_cutoff_active", False)
            and self.full_cutoff_current_module == module_no
        )
        if cutoff_btn and self.is_connected and not is_full_cutoff:
            cutoff_btn.setEnabled(True)

        if is_full_cutoff:
            self.full_cutoff_completed_count += 1
            progress_bar = getattr(self, "full_cutoff_progress_bar", None)
            if progress_bar is not None:
                progress_bar.setValue(self.full_cutoff_completed_count)
            self.full_cutoff_current_module = None
            QTimer.singleShot(100, self.start_next_full_cutoff)

    def normalize_module_table_row_heights(self):
        """차단 시간 표시 여부와 관계없이 좌우 모듈 행 높이를 동일하게 유지한다."""
        row_height = getattr(self, "module_table_row_height", 44)
        for table in (self.module_table_left, self.module_table_right):
            table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
            table.verticalHeader().setDefaultSectionSize(row_height)
            for row in range(table.rowCount()):
                table.setRowHeight(row, row_height)

    def show_cutoff_result_popup(self, success, detail="", operation="차단"):
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WA_TranslucentBackground)
        dialog.setModal(True)

        if success:
            symbol = "✓"
            title = f"축전지 강제 {operation} 성공"
            accent = "#22C55E"
            soft_background = "#F0FDF4"
            title_color = "#166534"
            duration_ms = 1000
        else:
            symbol = "!"
            title = f"축전지 강제 {operation} 실패"
            accent = "#EF4444"
            soft_background = "#FEF2F2"
            title_color = "#991B1B"
            duration_ms = 3000

        outer_layout = QVBoxLayout(dialog)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        card = QWidget()
        card.setObjectName("cutoffResultCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 13, 16, 13)
        card_layout.setSpacing(12)

        symbol_label = QLabel(symbol)
        symbol_label.setObjectName("cutoffResultSymbol")
        symbol_label.setAlignment(Qt.AlignCenter)
        symbol_label.setFixedSize(34, 34)
        card_layout.addWidget(symbol_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)

        title_label = QLabel(title)
        title_label.setObjectName("cutoffResultTitle")
        text_layout.addWidget(title_label)

        if not success and detail:
            detail_label = QLabel(detail)
            detail_label.setObjectName("cutoffResultDetail")
            detail_label.setWordWrap(True)
            detail_label.setMaximumWidth(235)
            text_layout.addWidget(detail_label)

        card_layout.addLayout(text_layout, 1)
        outer_layout.addWidget(card)

        shadow = QGraphicsDropShadowEffect(dialog)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 70))
        card.setGraphicsEffect(shadow)

        dialog.setStyleSheet(f"""
            QWidget#cutoffResultCard {{
                background-color: {soft_background};
                border: 1px solid {accent};
                border-radius: 12px;
            }}
            QLabel#cutoffResultSymbol {{
                background-color: {accent};
                color: white;
                border-radius: 17px;
                font-size: 21px;
                font-weight: bold;
            }}
            QLabel#cutoffResultTitle {{
                color: {title_color};
                font-size: 14px;
                font-weight: bold;
            }}
            QLabel#cutoffResultDetail {{
                color: #64748B;
                font-size: 10px;
            }}
        """)

        dialog.setFixedWidth(300)
        dialog.adjustSize()
        QTimer.singleShot(duration_ms, dialog.accept)
        dialog.exec()

    def confirm_cutoff(self, module_no):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("전원 차단 확인")
        msg.setText("⚠ 축전지 전원이 강제로 차단됩니다.\n시스템이 즉시 종료될 수 있습니다.\n정말로 실행하시겠습니까?")
        
        run_btn = msg.addButton("실행", QMessageBox.AcceptRole)
        cancel_btn = msg.addButton("취소", QMessageBox.RejectRole)

        msg.exec_()

        if msg.clickedButton() == run_btn:
            self.execute_cutoff(module_no)

    def reset_module_state(self, checked=False, for_reconnect=False):

        # 1️⃣ 데이터 초기화
        self.module_map.clear()
        self.module_data.clear()
        self.equip_to_module.clear()
        self.row_to_module.clear()
        self.current_alarm_table.clear()
        self.fault_list.clear()
        self.active_fault_keys.clear()
        self.alarm_modules = set()

        for module_no in list(getattr(self, "blink_timers", {}).keys()):
            self.stop_module_blink(module_no)

        self.module_widgets = {}

        # 2️⃣ 테이블 초기화
        for table in [self.module_table_left, self.module_table_right]:
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    # 🔥 모듈 번호 컬럼(0번)은 건드리지 않음
                    if col == 0:
                        continue
                    item = table.item(row, col)
                    if item:
                        item.setText("-")
                        item.setBackground(QColor("white"))
                        item.setForeground(QColor("black"))

                detail_btn = table.cellWidget(row, 6)
                if detail_btn:
                    detail_btn.setEnabled(False)

        for module_no, cutoff_btn in self.cutoff_buttons.items():
            cutoff_btn.setEnabled(False)
            cutoff_btn.setText(self.get_cutoff_button_text(module_no))

        self.normalize_module_table_row_heights()

        # 3️⃣ Fault 테이블 초기화
        self.fault_table.setRowCount(0)

        # 4️⃣ 상태 초기화
        self.is_connected = False
        self.update_full_cutoff_button_state()
        if for_reconnect:
            self.update_time_label.setText("최종업데이트시간 : 대기중")
        else:
            self.update_time_label.setText("최종업데이트시간 : 초기화됨")

        # 5️⃣ LED 초기화
        self.tx_led_off()
        self.rx_led_off()
        dprint("DEBUG", "✔ 상태 초기화 완료")
    
    def get_operation_record_directory(self):
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "Operation data record")

    def calculate_operation_record_storage(
        self, interval_minutes, duration_days, selected_fields
    ):
        module_count = max(1, len(self.module_map) or 10)
        total_minutes = int(duration_days) * 24 * 60
        snapshot_count = math.ceil(total_minutes / int(interval_minutes))
        row_count = snapshot_count * module_count

        selected_set = set(selected_fields)
        column_count = 2  # 기록시각, 모듈 번호
        for key, label, headers in OPERATION_RECORD_FIELD_SPECS:
            if key in selected_set:
                column_count += len(headers)

        # 실제 XLSX 압축률은 값에 따라 달라진다. 셀당 16바이트와 행
        # 오버헤드 96바이트를 적용하고, 저장 중 임시 일자 파일 및
        # 파일시스템 여유분 20%, 고정 50MiB를 추가한 안전 추정치다.
        estimated_row_bytes = 96 + column_count * 16
        data_bytes = row_count * estimated_row_bytes
        daily_rows = math.ceil((24 * 60) / int(interval_minutes)) * module_count
        temporary_file_bytes = daily_rows * estimated_row_bytes
        required_bytes = int(
            (data_bytes + temporary_file_bytes) * 1.20
            + 50 * 1024 * 1024
        )

        output_parent = os.path.dirname(self.get_operation_record_directory())
        free_bytes = shutil.disk_usage(output_parent).free
        return {
            "required_bytes": required_bytes,
            "free_bytes": free_bytes,
            "row_count": row_count,
            "column_count": column_count,
            "module_count": module_count,
        }

    def format_storage_size(self, byte_count):
        mib = byte_count / (1024 * 1024)
        if mib >= 1024:
            return f"{mib / 1024:.2f} GB"
        return f"{mib:.0f} MB"

    def open_operation_record_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("운전 데이타 기록 설정")
        dialog.setFixedWidth(390)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("운전 데이터 기록 주기")
        title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1E293B;"
        )
        layout.addWidget(title)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("기록 간격"))
        interval_combo = QComboBox()
        for minutes in (1, 5, 10, 30, 60):
            interval_combo.addItem(f"{minutes}분", minutes)

        saved_interval = int(
            self.settings.value("operation_record/interval_minutes", 5)
        )
        index = interval_combo.findData(saved_interval)
        interval_combo.setCurrentIndex(index if index >= 0 else 1)
        interval_layout.addWidget(interval_combo, 1)
        layout.addLayout(interval_layout)

        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("기록 기간"))
        duration_spin = QSpinBox()
        duration_spin.setRange(1, 30)
        duration_spin.setSingleStep(1)
        duration_spin.setSuffix("일")
        duration_spin.setValue(
            int(self.settings.value("operation_record/duration_days", 30))
        )
        duration_spin.setToolTip(
            "기록을 시작한 시점부터 선택한 일수 동안 자동으로 기록합니다."
        )
        duration_layout.addWidget(duration_spin, 1)
        layout.addLayout(duration_layout)

        field_title_layout = QHBoxLayout()
        field_title = QLabel("Excel 기록 항목")
        field_title.setStyleSheet("font-weight: bold; color: #334155;")
        field_title_layout.addWidget(field_title)
        field_title_layout.addStretch()
        select_all_btn = QPushButton("전체선택")
        clear_all_btn = QPushButton("전체해제")
        select_all_btn.setFixedHeight(22)
        clear_all_btn.setFixedHeight(22)
        field_title_layout.addWidget(select_all_btn)
        field_title_layout.addWidget(clear_all_btn)
        layout.addLayout(field_title_layout)

        required_label = QLabel("※ 기록시각과 모듈 번호는 항상 기록됩니다.")
        required_label.setStyleSheet("color: #64748B; font-size: 10px;")
        layout.addWidget(required_label)

        saved_fields_text = self.settings.value(
            "operation_record/selected_fields", ""
        )
        if saved_fields_text:
            saved_fields = {
                value for value in str(saved_fields_text).split(",") if value
            }
        else:
            saved_fields = {
                key for key, label, headers in OPERATION_RECORD_FIELD_SPECS
            }

        field_grid = QGridLayout()
        field_grid.setHorizontalSpacing(14)
        field_grid.setVerticalSpacing(5)
        field_checkboxes = {}
        for index, (key, label, headers) in enumerate(
            OPERATION_RECORD_FIELD_SPECS
        ):
            checkbox = QCheckBox(label)
            checkbox.setChecked(key in saved_fields)
            field_checkboxes[key] = checkbox
            field_grid.addWidget(checkbox, index // 2, index % 2)
        layout.addLayout(field_grid)

        output_dir = self.get_operation_record_directory()
        path_label = QLabel(f"저장 위치\n{output_dir}")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("""
            QLabel {
                background: #F1F5F9;
                color: #475569;
                border-radius: 6px;
                padding: 8px;
                font-size: 10px;
            }
        """)
        layout.addWidget(path_label)

        storage_label = QLabel()
        storage_label.setWordWrap(True)
        storage_label.setStyleSheet("""
            QLabel {
                background: #EFF6FF;
                color: #1E40AF;
                border: 1px solid #BFDBFE;
                border-radius: 6px;
                padding: 7px;
                font-size: 10px;
            }
        """)
        layout.addWidget(storage_label)

        status_label = QLabel()
        status_label.setWordWrap(True)
        layout.addWidget(status_label)
        self.operation_record_status_label = status_label

        button_layout = QHBoxLayout()
        start_btn = QPushButton("기록시작")
        stop_btn = QPushButton("기록중지")
        close_btn = QPushButton("닫기")

        start_btn.setStyleSheet("""
            QPushButton {
                background: #16A34A;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #15803D; }
            QPushButton:disabled { background: #CBD5E1; color: #64748B; }
        """)
        stop_btn.setStyleSheet("""
            QPushButton {
                background: #DC2626;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #B91C1C; }
            QPushButton:disabled { background: #CBD5E1; color: #64748B; }
        """)

        is_recording = self.is_operation_recording()
        start_btn.setEnabled(not is_recording)
        stop_btn.setEnabled(is_recording)
        interval_combo.setEnabled(not is_recording)
        duration_spin.setEnabled(not is_recording)
        for checkbox in field_checkboxes.values():
            checkbox.setEnabled(not is_recording)
        select_all_btn.setEnabled(not is_recording)
        clear_all_btn.setEnabled(not is_recording)

        if is_recording:
            minutes = getattr(self, "operation_record_interval_minutes", 5)
            duration_days = getattr(
                self, "operation_record_duration_days", 30
            )
            end_at = getattr(self, "operation_record_end_at", None)
            end_text = end_at.strftime("%m.%d %H:%M") if end_at else "-"
            status_label.setText(
                f"● {minutes}분 간격 기록 중 · {duration_days}일간 "
                f"(종료 {end_text})"
            )
            status_label.setStyleSheet(
                "color: #15803D; font-weight: bold;"
            )
        else:
            status_label.setText("기록이 중지되어 있습니다.")
            status_label.setStyleSheet("color: #64748B;")

        def selected_field_keys():
            return [
                key
                for key, checkbox in field_checkboxes.items()
                if checkbox.isChecked()
            ]

        def update_storage_estimate(*_args):
            selected_fields = selected_field_keys()
            if not selected_fields:
                storage_label.setText("기록 항목을 한 개 이상 선택해 주세요.")
                storage_label.setStyleSheet(
                    "color: #DC2626; background: #FEF2F2; "
                    "border: 1px solid #FECACA; border-radius: 6px; padding: 7px;"
                )
                return

            estimate = self.calculate_operation_record_storage(
                int(interval_combo.currentData()),
                int(duration_spin.value()),
                selected_fields
            )
            enough = estimate["free_bytes"] >= estimate["required_bytes"]
            storage_label.setText(
                f"예상 기록량: {estimate['row_count']:,}행 / "
                f"{estimate['column_count']}열\n"
                f"권장 최소 여유 공간: "
                f"{self.format_storage_size(estimate['required_bytes'])} · "
                f"현재 여유 공간: "
                f"{self.format_storage_size(estimate['free_bytes'])}"
            )
            if enough:
                storage_label.setStyleSheet(
                    "color: #1E40AF; background: #EFF6FF; "
                    "border: 1px solid #BFDBFE; border-radius: 6px; padding: 7px;"
                )
            else:
                storage_label.setStyleSheet(
                    "color: #B91C1C; background: #FEF2F2; "
                    "border: 1px solid #FCA5A5; border-radius: 6px; "
                    "padding: 7px; font-weight: bold;"
                )

        def start_recording():
            minutes = int(interval_combo.currentData())
            duration_days = int(duration_spin.value())
            selected_fields = selected_field_keys()
            if not selected_fields:
                QMessageBox.warning(
                    dialog,
                    "기록 항목 선택",
                    "Excel에 기록할 데이터 항목을 한 개 이상 선택해 주세요."
                )
                return

            if self.start_operation_data_recording(
                minutes, duration_days, selected_fields
            ):
                start_btn.setEnabled(False)
                stop_btn.setEnabled(True)
                interval_combo.setEnabled(False)
                duration_spin.setEnabled(False)
                for checkbox in field_checkboxes.values():
                    checkbox.setEnabled(False)
                select_all_btn.setEnabled(False)
                clear_all_btn.setEnabled(False)
                status_label.setText(
                    f"● {minutes}분 간격 기록 중 · {duration_days}일간 "
                    f"(종료 {self.operation_record_end_at.strftime('%m.%d %H:%M')})"
                )
                status_label.setStyleSheet(
                    "color: #15803D; font-weight: bold;"
                )

        def stop_recording():
            self.stop_operation_data_recording()
            start_btn.setEnabled(True)
            stop_btn.setEnabled(False)
            interval_combo.setEnabled(True)
            duration_spin.setEnabled(True)
            for checkbox in field_checkboxes.values():
                checkbox.setEnabled(True)
            select_all_btn.setEnabled(True)
            clear_all_btn.setEnabled(True)
            status_label.setText("기록이 중지되었습니다.")
            status_label.setStyleSheet("color: #64748B;")

        start_btn.clicked.connect(start_recording)
        stop_btn.clicked.connect(stop_recording)
        close_btn.clicked.connect(dialog.accept)
        select_all_btn.clicked.connect(
            lambda: [
                checkbox.setChecked(True)
                for checkbox in field_checkboxes.values()
            ]
        )
        clear_all_btn.clicked.connect(
            lambda: [
                checkbox.setChecked(False)
                for checkbox in field_checkboxes.values()
            ]
        )
        interval_combo.currentIndexChanged.connect(update_storage_estimate)
        duration_spin.valueChanged.connect(update_storage_estimate)
        for checkbox in field_checkboxes.values():
            checkbox.stateChanged.connect(update_storage_estimate)
        update_storage_estimate()

        button_layout.addWidget(start_btn)
        button_layout.addWidget(stop_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        dialog.exec()

    def is_operation_recording(self):
        timer = getattr(self, "operation_record_timer", None)
        return timer is not None and timer.isActive()

    def start_operation_data_recording(
        self, interval_minutes, duration_days, selected_fields
    ):
        if not self.is_connected:
            QMessageBox.warning(
                self,
                "기록 시작 불가",
                "먼저 축전지 시스템에 접속해 주세요."
            )
            return False

        if self.is_operation_recording():
            return True

        try:
            storage = self.calculate_operation_record_storage(
                interval_minutes, duration_days, selected_fields
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "디스크 용량 확인 실패",
                f"저장 디스크의 여유 공간을 확인할 수 없습니다.\n{e}"
            )
            return False

        if storage["free_bytes"] < storage["required_bytes"]:
            QMessageBox.critical(
                self,
                "디스크 용량 부족",
                "운전 데이터 기록을 시작하기 위한 디스크 공간이 부족합니다.\n\n"
                f"권장 최소 여유 공간: "
                f"{self.format_storage_size(storage['required_bytes'])}\n"
                f"현재 여유 공간: "
                f"{self.format_storage_size(storage['free_bytes'])}\n\n"
                "저장 공간을 확보하거나 기록 간격·기간·항목을 줄여 주세요."
            )
            return False

        self.operation_record_selected_fields = list(selected_fields)
        self.operation_record_duration_days = max(
            1, min(30, int(duration_days))
        )
        record_started_at = datetime.now()
        self.operation_record_end_at = (
            record_started_at
            + timedelta(days=self.operation_record_duration_days)
        )
        session_id = record_started_at.strftime("%Y-%m-%d_%H-%M-%S_%f")
        selected_set = set(self.operation_record_selected_fields)
        headers = ["기록시각", "모듈"]
        for key, label, field_headers in OPERATION_RECORD_FIELD_SPECS:
            if key in selected_set:
                headers.extend(field_headers)

        output_dir = self.get_operation_record_directory()
        self.operation_record_thread = OperationDataRecordThread(
            output_dir,
            headers,
            session_id,
            self
        )
        self.operation_record_thread.saved_signal.connect(
            self.handle_operation_record_saved
        )
        self.operation_record_thread.error_signal.connect(
            self.handle_operation_record_error
        )
        self.operation_record_thread.start()

        self.operation_record_interval_minutes = int(interval_minutes)
        self.settings.setValue(
            "operation_record/interval_minutes",
            self.operation_record_interval_minutes
        )
        self.settings.setValue(
            "operation_record/selected_fields",
            ",".join(self.operation_record_selected_fields)
        )
        self.settings.setValue(
            "operation_record/duration_days",
            self.operation_record_duration_days
        )
        self.settings.sync()

        self.operation_record_timer = QTimer(self)
        self.operation_record_timer.timeout.connect(
            self.queue_operation_data_snapshot
        )
        self.operation_record_timer.start(
            self.operation_record_interval_minutes * 60 * 1000
        )

        self.operation_record_deadline_timer = QTimer(self)
        self.operation_record_deadline_timer.timeout.connect(
            self.check_operation_record_deadline
        )
        self.operation_record_deadline_timer.start(30000)

        self.btn_operation_record.setText("운전 데이타 기록 ●")
        self.btn_operation_record.setStyleSheet("""
            QPushButton {
                background-color: #16A34A;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 3px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #15803D; }
        """)

        # 시작 시점의 데이터도 즉시 한 번 기록한다.
        self.queue_operation_data_snapshot()
        return True

    def check_operation_record_deadline(self):
        end_at = getattr(self, "operation_record_end_at", None)
        if end_at is None or datetime.now() < end_at:
            return

        # 설정한 기록 기간의 마지막 데이터까지 큐에 넣은 후 종료한다.
        self.queue_operation_data_snapshot()
        self.stop_operation_data_recording()
        self.show_auto_close_message(
            "운전 데이터 기록 완료",
            "설정한 운전 데이터 기록 기간이 완료되었습니다.",
            duration_ms=3000
        )

    def stop_operation_data_recording(self):
        timer = getattr(self, "operation_record_timer", None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
            self.operation_record_timer = None

        deadline_timer = getattr(
            self, "operation_record_deadline_timer", None
        )
        if deadline_timer is not None:
            deadline_timer.stop()
            deadline_timer.deleteLater()
            self.operation_record_deadline_timer = None

        thread = getattr(self, "operation_record_thread", None)
        if thread is not None:
            thread.stop()
            if not thread.wait(10000):
                dprint("RECORD", "[WARN] 기록 스레드 종료 대기시간 초과")
            thread.deleteLater()
            self.operation_record_thread = None

        self.operation_record_end_at = None

        if hasattr(self, "btn_operation_record"):
            self.btn_operation_record.setText("운전 데이타 기록")
            self.btn_operation_record.setStyleSheet("""
                QPushButton {
                    background-color: #2563EB;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 3px 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #1D4ED8; }
            """)

    def queue_operation_data_snapshot(self):
        thread = getattr(self, "operation_record_thread", None)
        if thread is None or not thread.isRunning():
            return

        status_map = {
            0: "Online", 1: "Offline", 2: "Sleep", 3: "Disconnect",
            4: "충전중", 5: "방전중", 6: "Standby", 255: "Unknown"
        }
        selected_fields = set(
            getattr(self, "operation_record_selected_fields", [])
        )
        rows = []

        for module_no in sorted(self.module_map):
            module_info = self.module_map.get(module_no, {})
            row_index = str(module_info.get("row_index", ""))
            data = self.module_data.get(row_index)
            if not data:
                continue

            cells = list(data.get("cells", []))[:15]
            temps = list(data.get("temps", []))[:15]
            cells += [None] * (15 - len(cells))
            temps += [None] * (15 - len(temps))
            valid_cells = [value for value in cells if value is not None]
            valid_temps = [value for value in temps if value is not None]

            table = (
                self.module_table_left
                if int(module_no) <= 5
                else self.module_table_right
            )
            table_row = (int(module_no) - 1) % 5
            alarm_item = table.item(table_row, 4)
            alarm_text = alarm_item.text() if alarm_item else "-"
            status_code = data.get("status")
            status_text = status_map.get(status_code, "Unknown")
            cutoff_btn = self.cutoff_buttons.get(int(module_no))
            epo_text = (
                cutoff_btn.text().replace("\n", " ")
                if cutoff_btn is not None else "-"
            )

            field_values = {
                "equipment": [
                    row_index,
                    module_info.get("equip_id"),
                    module_info.get("model"),
                    module_info.get("barcode"),
                ],
                "voltage": [data.get("volt")],
                "current": [data.get("current")],
                "soc_soh": [data.get("soc"), data.get("soh")],
                "status": [status_code, status_text],
                "alarm": [alarm_text],
                "cell_summary": [
                    max(valid_cells) if valid_cells else None,
                    min(valid_cells) if valid_cells else None,
                ],
                "cell_detail": cells,
                "temp_summary": [
                    max(valid_temps) if valid_temps else None,
                    min(valid_temps) if valid_temps else None,
                ],
                "temp_detail": temps,
                "epo": [epo_text],
            }

            row_values = [f"#{int(module_no):02d}"]
            for key, label, field_headers in OPERATION_RECORD_FIELD_SPECS:
                if key in selected_fields:
                    row_values.extend(field_values[key])
            rows.append(row_values)

        thread.enqueue(datetime.now(), rows)

    def handle_operation_record_saved(self, path, row_count):
        label = getattr(self, "operation_record_status_label", None)
        if label is not None:
            label.setText(
                f"● 기록 중 · {datetime.now().strftime('%H:%M:%S')} "
                f"({row_count}개 모듈 저장)"
            )
            label.setStyleSheet("color: #15803D; font-weight: bold;")
            label.setToolTip(path)

    def handle_operation_record_error(self, message):
        dprint("RECORD", f"[ERROR] {message}")
        label = getattr(self, "operation_record_status_label", None)
        if label is not None:
            label.setText(message)
            label.setStyleSheet("color: #DC2626; font-weight: bold;")

    def create_module_table(self):
        """모듈 상태 + 모듈 설치 순서"""

        # "차단\n(월.일 시:분)" 두 줄이 처음부터 들어갈 수 있는 고정 행 높이
        self.module_table_row_height = 44

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
        container_layout.setContentsMargins(0, 0, 0, 0)   # 🔥 추가
        container_layout.setSpacing(4)                    # 🔥 기본값보다 줄이기 (보통 9~11)
        # -------------------------
        # 모듈 상태 Group
        # -------------------------

        module_group = QGroupBox()
        module_layout = QVBoxLayout(module_group)   # 🔥 VBox으로 변경

        module_layout.setContentsMargins(0, 0, 0, 0)
        module_layout.setSpacing(2)

        headers = ["모듈", "모듈 전압", "셀 전압 Max/Min[V]", "셀 온도 Max/Min[℃]", "경보", "통신상태", "모듈(셀)", "EPO"]

        LABEL_BG = QColor("#E7F1FF")

        label_font = QFont()
        label_font.setBold(True)

        # -------------------------
        # 🔥 상단 Header (타이틀 + Legend)
        # -------------------------
        header_layout = QHBoxLayout()

        title_label = QLabel("모듈 상태")
        title_label.setFont(label_font)

        self.btn_reset = QPushButton("상태 초기화")
        self.btn_reset.setObjectName("resetButton")
        self.btn_reset.setFixedHeight(20)
        self.btn_reset.clicked.connect(self.reset_module_state)
        self.btn_reset.setStyleSheet("""
        QPushButton#resetButton {
            background-color: #E74C3C;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 4px 12px;
            font-weight: bold;
        }

        QPushButton#resetButton:hover {
            background-color: #C0392B;
        }

        QPushButton#resetButton:pressed {
            background-color: #922B21;
        }

        QPushButton#resetButton:disabled {
            background-color: #BDC3C7;
            color: #7F8C8D;
        }
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.btn_reset)
        self.btn_operation_record = QPushButton("운전 데이타 기록")
        self.btn_operation_record.setFixedHeight(20)
        self.btn_operation_record.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 3px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:pressed {
                background-color: #1E40AF;
            }
        """)
        self.btn_operation_record.clicked.connect(
            self.open_operation_record_dialog
        )
        header_layout.addWidget(self.btn_operation_record)

        self.btn_all_module_info = QPushButton("전체모듈정보")
        self.btn_all_module_info.setFixedHeight(20)
        self.btn_all_module_info.setStyleSheet("""
            QPushButton {
                background-color: #0F766E;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 3px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0D9488; }
            QPushButton:pressed { background-color: #115E59; }
        """)
        self.btn_all_module_info.clicked.connect(
            self.show_all_module_details
        )
        header_layout.addWidget(self.btn_all_module_info)
        header_layout.addStretch()

        def create_legend(text, bg, fg):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    color: {fg};
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 11px;
                }}
            """)
            return lbl

        # 🔥 여기 추가
        desc_label = QLabel("※경보 색상 기준:")
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                color: #333333;
                padding-right: 6px;
            }
        """)
        header_layout.addWidget(desc_label)
        
        # 🔴 Critical
        header_layout.addWidget(create_legend("Critical", "#E03131", "white"))

        # 🟠 Major
        header_layout.addWidget(create_legend("Major", "#F76707", "white"))

        # 🟡 Minor
        header_layout.addWidget(create_legend("Minor", "#FFD43B", "black"))

        # 🔵 Warning
        header_layout.addWidget(create_legend("Warning", "#74C0FC", "black"))

        # -------------------------
        # 테이블 생성 함수
        # -------------------------
        def create_table(start_index):

            table = QTableWidget(5, len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
            table.verticalHeader().setDefaultSectionSize(
                self.module_table_row_height
            )
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

                # -------------------------
                # 상세정보 버튼 (컬럼 6)
                # -------------------------
                detail_btn = QPushButton("상세정보")
                detail_btn.clicked.connect(lambda checked, no=module_no: self.show_module_detail(no))
                detail_btn.setEnabled(False)

                table.setCellWidget(row, 6, detail_btn)

                # -------------------------
                # 전원차단 버튼 (컬럼 7 = EPO)
                # -------------------------
                cutoff_btn = QPushButton("차단")   # 텍스트도 짧게 추천
                cutoff_btn.setEnabled(False)  # 🔥 기본 비활성화
                cutoff_btn.setText(self.get_cutoff_button_text(module_no))

                cutoff_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #E03131;
                        color: white;
                        border-radius: 4px;
                        padding: 2px 6px;   /* 🔥 여기 적용 */
                        min-width: 0px;
                    }

                    QPushButton:hover {
                        background-color: #C92A2A;
                    }

                    QPushButton:disabled {
                        background-color: #ADB5BD;
                        color: #E9ECEF;
                    }
                """)

                cutoff_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                cutoff_btn.setMinimumWidth(0)
                cutoff_btn.setFixedHeight(self.module_table_row_height - 6)

                cutoff_btn.clicked.connect(lambda checked, no=module_no: self.confirm_cutoff(no))

                # 🔥 버튼 저장 (핵심)
                self.cutoff_buttons[int(module_no)] = cutoff_btn

                # 가운데 정렬
                btn_container = QWidget()
                btn_layout = QHBoxLayout(btn_container)
                btn_layout.setContentsMargins(3, 3, 3, 3)
                for col in range(1, 7):
                    item = table.item(row, col)
                    if item:
                        item.setTextAlignment(Qt.AlignCenter)
                btn_layout.addWidget(cutoff_btn)

                # 🔥 반드시 있어야 함 (빠져있던 핵심)
                table.setCellWidget(row, 7, btn_container)
            table.resizeColumnsToContents()
            for row in range(table.rowCount()):
                table.setRowHeight(row, self.module_table_row_height)

            table.setColumnWidth(2, 120)
            table.setColumnWidth(3, 130)
            table.setColumnWidth(4, 50)
            table.setColumnWidth(5, 90)
            header = table.horizontalHeader()
            # 차단 시간 두 줄 표시 공간을 확보하고 통신상태 칸은 줄인다.
            header.setStretchLastSection(False)
            header.setSectionResizeMode(2, QHeaderView.Stretch)
            header.setSectionResizeMode(5, QHeaderView.Fixed)
            table.setColumnWidth(5, 70)
            header.setSectionResizeMode(6, QHeaderView.Fixed)
            table.setColumnWidth(6, 80)   # 상세정보

            header.setSectionResizeMode(7, QHeaderView.Fixed)           
            table.setColumnWidth(7, 112)

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

            return table

        # -------------------------
        # 테이블 배치
        # -------------------------
        self.module_table_left = create_table(0)
        self.module_table_right = create_table(5)

        table_layout = QHBoxLayout()
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        table_layout.addWidget(self.module_table_left)
        table_layout.addWidget(self.module_table_right)

        # 🔥 Header + Table 결합
        module_layout.addLayout(header_layout)
        module_layout.addLayout(table_layout)

        # -------------------------
        # 모듈 설치 순서 Group
        # -------------------------

        order_group = QGroupBox("모듈 설치 순서")
        order_group.setFont(label_font)
        order_layout = QVBoxLayout()   # 🔥 parent 없이 생성

        # 🔥 설명 라벨
        legend_label = QLabel(
            "●빨간색: 알람발생   ●회색: 차단(Disconnect)\n"
            "●깜박임: 바코드 불일치"
        )
        legend_label.setWordWrap(True)
        legend_label.setMinimumHeight(34)
        legend_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        legend_label.setStyleSheet("""
            QLabel {
                color: #555;
                font-size: 11px;
                padding: 1px 4px;
            }
        """)

        order_layout.addWidget(legend_label)

        # 🔥 마지막에 한 번만 setLayout
        order_group.setLayout(order_layout)

        self.module_order_labels = []

        for i in range(10, 0, -1):

            label = QLabel(f"{i:02d} : -")
            # blink 스타일 변경이 주변 영역의 세로 배치에 영향을 주지 않도록 고정
            label.setFixedHeight(22)

            label.setStyleSheet(BASE_STYLE)
            label.base_style = BASE_STYLE

            order_layout.addWidget(label)
            self.module_order_labels.append(label)

        order_layout.addStretch()
        order_group.setFixedWidth(280)

        # -------------------------
        # layout 배치
        # -------------------------

        container_layout.addWidget(module_group, 3)
        container_layout.addWidget(order_group, 2)
        
        return container

    def update_module_order_view(self):
        alarm_modules = {}  # 🔴 module_no : level 저장

        for alarm in self.current_alarm_table:

            try:
                level = int(str(alarm.get("level", 255)).strip())
            except (TypeError, ValueError):
                level = 255

            # 🔴 Minor 이상만 대상
            if level not in [1, 2, 3]:
                continue

            # Active Alarm Table의 위치 값은 현재 row_index로 저장되므로
            # row 매핑을 우선 사용하고, 구형/Trap 데이터는 equip으로 보완한다.
            module_no = None
            row_index = alarm.get("row_index")
            if row_index is not None:
                module_no = self.row_to_module.get(str(row_index))

            if module_no is None:
                equip_id = alarm.get("equip")
                if equip_id is not None:
                    module_no = self.equip_to_module.get(str(equip_id))

            if module_no is None:
                continue

            try:
                module_no = int(module_no)
            except (TypeError, ValueError):
                continue

            # 🔴 같은 모듈에 여러 알람 있을 경우 → 더 높은 레벨 우선
            if module_no not in alarm_modules:
                alarm_modules[module_no] = level
            else:
                alarm_modules[module_no] = min(alarm_modules[module_no], level)
                
        for i, pos in enumerate(range(10, 0, -1)):

            module_no = self.module_order[i]

            barcode = None
            has_alarm = False
            is_disconnected = False

            # 1️⃣ 통신 데이터 우선
            if module_no and module_no in self.module_map:
                barcode = self.module_map[module_no].get("barcode")
                has_alarm = module_no in alarm_modules

                row_index = self.module_map[module_no].get("row_index")
                module_data = self.module_data.get(row_index)
                if module_data is None:
                    module_data = self.module_data.get(str(row_index), {})
                is_disconnected = (module_data or {}).get("status") == 3

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

                self.update_module_order_label(
                    i, module_no, barcode, has_alarm, is_disconnected
                )

            else:
                txt = f"Rack {pos:02d}번째: -"
                self.update_module_order_label(i)

            self.module_order_labels[i].setText(txt)            
        
    
    def handle_fault_trap(self, trap_data, is_resume):
        
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
            
            dprint("SNMP", f"[TRAP VAR] {oid} = {value}")

            # Alarm Text
            if oid.startswith(alarm_oid_prefix):
                alarm_text = value
                dprint("SNMP",f"[DEBUG] alarm_text type = {type(alarm_text)}")
                dprint("SNMP",f"[DEBUG] alarm_text raw = {repr(alarm_text)}")

            # Equip ID
            if oid.startswith(equip_oid_prefix):
                row_index = int(oid.split(".")[-1])   # 위치 정보
                equip_id = int(value)                 # 실제 ID
                dprint("SNMP", f"[PARSE] row_index = {row_index}")
                dprint("SNMP", f"[PARSE] equip_id  = {equip_id}")
            

        # -----------------------------------
        # 필수 값 체크 (수정)
        # -----------------------------------

        # -----------------------------------
        # Alarm Text 없으면 무조건 종료
        # -----------------------------------
        if alarm_text is None:
            dprint("SNMP", "[ERROR] alarm_text 없음")
            return

        alarm_lower = alarm_text.lower()

        # -----------------------------------
        # 🔥 1. Board fault (System 알람)
        # -----------------------------------
        if re.search(r'board.*fault', alarm_lower):
            module_no = self.equip_to_module.get(str(equip_id)) or self.equip_to_module.get(equip_id)

            if module_no is None:
                dprint("SNMP", "[ERROR] module 매핑 실패")
                return
            
            dprint("SNMP", "[PARSE] Board hardware fault")
            if is_resume:
                dprint("SNMP", "[RESUME] System fault 제거")
                self.remove_fault(module_no, 0)
            else:
                dprint("SNMP", "[ALARM] System fault 추가")
                self.add_fault(module_no, 0, 0, 0)

            return


        # -----------------------------------
        # 🔥 2. Cell fault 파싱
        # -----------------------------------
        m = re.search(r'cell\s*(\d+)\s*fault', alarm_lower)

        if not m:
            dprint("SNMP", "[SKIP] Cell fault 아님:", alarm_text)
            return

        cell_no = int(m.group(1))


        # -----------------------------------
        # 🔥 3. Resume인데 equip_id 없으면 무시
        # -----------------------------------
        if equip_id is None:
            dprint("SNMP", "[ERROR] equip_id 없음")
            return


        # -----------------------------------
        # 🔥 4. module 매핑
        # -----------------------------------
        module_no = self.equip_to_module.get(str(equip_id)) or self.equip_to_module.get(equip_id)

        if module_no is None:
            dprint("SNMP", "[ERROR] module 매핑 실패")
            return


        # -----------------------------------
        # 🔥 5. Resume → 삭제
        # -----------------------------------
        if is_resume:
            dprint("SNMP", f"[RESUME] module={module_no}, cell={cell_no}")
            self.remove_fault(module_no, cell_no)
            return


        # -----------------------------------
        # 🔥 6. Fault → 추가
        # -----------------------------------
        module_info = self.module_map.get(module_no)
        if not module_info:
            return

        row_index = module_info["row_index"]
        module_data = self.module_data.get(row_index)

        if not module_data:
            dprint("SNMP", "[WARN] module_data 없음 → 그래도 추가")

            self.add_fault(module_no, cell_no, 0, 0)
            return

        cells = module_data.get("cells", [])
        temps = module_data.get("temps", [])

        index = cell_no - 1
        if index < 0 or index >= len(cells) or index >= len(temps):
            return
        
        volt = cells[index]
        temp = temps[index]

        self.add_fault(module_no, cell_no, volt, temp)

    def refresh_fault_numbers(self):
        for i, fault in enumerate(self.fault_list):
            fault["no"] = i + 1

            if i < self.fault_table.rowCount():
                item = self.fault_table.item(i, 0)
                if item:
                    item.setText(f"#{i+1:02d}")

                # 🔥 추가: 버튼 row 재설정
                btn = self.fault_table.cellWidget(i, 5)
                if btn:
                    btn.setProperty("row", i)


    def delete_fault(self):
        button = self.sender()
        if not button:
            return

        pos = button.mapTo(self.fault_table.viewport(), QPoint(0, 0))
        index = self.fault_table.indexAt(pos)

        if not index.isValid():
            return

        row = index.row()

        dprint("MODULE", f"[FAULT DELETE] Row {row}")

        # fault_list에서도 삭제
        if row < len(self.fault_list):
            del self.fault_list[row]

        # 테이블 행 삭제
        self.fault_table.removeRow(row)

        # 번호 다시 정렬
        self.refresh_fault_numbers()
        
    
    def add_fault(self, module_no, cell_no, volt, temp):

        for f in self.fault_list:
            if f["module"] == module_no and f["cell"] == cell_no:
                dprint("SNMP", "[DUPLICATE] 이미 fault 존재 → 추가 안함")
                dprint("SNMP", "================ TRAP DEBUG END =================\n")
                return  # 중복 방지
            
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
                "SMU02C" if module_no == "SYSTEM" else str(module_no),
                "(BMS hardware fault)",
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
        btn_delete.setProperty("row", row)
        self.fault_table.setCellWidget(row, len(values), btn_delete)

    def remove_fault(self, module_no, cell_no):

        for i, f in enumerate(self.fault_list):
            if f["module"] == module_no and f["cell"] == cell_no:

                dprint("SNMP", f"[REMOVE] module={module_no}, cell={cell_no}")

                del self.fault_list[i]

                if i < self.fault_table.rowCount():
                    self.fault_table.removeRow(i)

                self.refresh_fault_numbers()
                return

        dprint("SNMP", "[INFO] 삭제 대상 없음")

    def create_fault_table(self):

        group = QGroupBox("고장 정보")
        layout = QVBoxLayout(group)

        # 컬럼 6개 (Delete 추가)
        self.fault_table = QTableWidget(0, 6)
        self.fault_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.fault_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.fault_table.setSelectionMode(QTableWidget.SingleSelection)
        self.fault_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.fault_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.fault_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.fault_table.setMinimumHeight(180)

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
        self.fault_table.verticalHeader().setDefaultSectionSize(24)

        # 삭제 컬럼 width 고정 (UI 안정)
        self.fault_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.fault_table.setColumnWidth(5, 80)

        # 고장 정보 영역은 화면 하단에서 잘리지 않도록 최소 높이를 보장하고,
        # 항목이 많아지면 테이블 내부 스크롤로 확인한다.
        group.setMinimumHeight(230)
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.fault_table)

        return group

    #############################################################################
    def create_connection_panel(self):
        group = QGroupBox("축전지 시스템 접속 설정")
        layout = QHBoxLayout(group)
        layout.addWidget(QLabel("IP"))
        self.ip_edit = QLineEdit("60.22.0.0")
        self.ip_edit.setFixedWidth(110)
        layout.addWidget(self.ip_edit)
        layout.addSpacing(5)
        layout.addWidget(QLabel("Port"))
        self.port_edit = QLineEdit("161")
        self.port_edit.setFixedWidth(50)
        layout.addWidget(self.port_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("GET"))
        self.get_comm_edit = QLineEdit("sktlfp48r")
        self.get_comm_edit.setFixedWidth(80)
        layout.addWidget(self.get_comm_edit)
        layout.addSpacing(5)
        layout.addWidget(QLabel("SET"))
        self.set_comm_edit = QLineEdit("sktlfp48w")
        self.set_comm_edit.setFixedWidth(80)
        layout.addWidget(self.set_comm_edit)
        layout.addSpacing(5)
        layout.addWidget(QLabel("TRAP"))
        self.trap_comm_edit = QLineEdit("sktlfp48r")
        self.trap_comm_edit.setFixedWidth(80)
        layout.addWidget(self.trap_comm_edit)
        layout.addSpacing(5)
        layout.addWidget(QLabel("TRAP Port"))
        self.trap_port_edit = QLineEdit("162")
        self.trap_port_edit.setFixedWidth(50)
        layout.addWidget(self.trap_port_edit)
        layout.addSpacing(20)
        self.connect_btn = QPushButton("접속시작")
        self.connect_btn.setFixedWidth(80)
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        layout.addWidget(self.connect_btn)

        self.connection_input_fields = [
            self.ip_edit,
            self.port_edit,
            self.get_comm_edit,
            self.set_comm_edit,
            self.trap_comm_edit,
            self.trap_port_edit,
        ]
        for field in self.connection_input_fields:
            field.returnPressed.connect(self.handle_connection_enter)
        
        # 🔵 접속 상태 표시 (접속 버튼 옆)
        layout.addSpacing(10)

        self.bmu_label = QLabel("접속상태")
        layout.addWidget(self.bmu_label)

        self.status_circle = QLabel()
        self.status_circle.setFixedSize(15, 15)
        self.status_circle.setStyleSheet(
            "background-color: #CCCCCC; border-radius: 7px; border: 1px solid #999999;"
        )
        # 🔥 SNMP Fail Count 표시 라벨
        self.fail_label = QLabel(f"Timeout : 0 / 0")
        self.fail_label.setStyleSheet("color: #8E44AD; font-weight: bold; padding: 2px 6px;")
        #self.fail_label.setFixedWidth(100)

        self.btn_module_order = QPushButton("모듈 설치 순서 설정")
        self.btn_module_order.setFixedHeight(27)   # 40 → 약 27 (2/3)

        self.btn_module_order.setStyleSheet("""
        QPushButton {
            background-color: #2E86DE;
            color: white;
            border-radius: 5px;        /* 8 → 5 */
            font-size: 12px;           /* 14 → 12 */
            font-weight: bold;
            padding: 4px 8px;          /* 6x12 → 축소 */
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

        # =========================
        # 🔘 모듈 순서 + 알람 묶음 레이아웃
        # =========================
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)

        # 👉 모듈 버튼 먼저 추가
        btn_layout.addWidget(self.btn_module_order)


        # =========================
        # 🔊 Alarm UI
        # =========================
        alarm_layout = QHBoxLayout()
        alarm_layout.setSpacing(5)

        # 🔊 사운드 버튼
        self.btn_alarm_sound = QPushButton("🔊")
        # 🔥 여기 추가
        self.update_sound_icon()
        self.btn_alarm_sound.setFixedSize(32, 32)
        self.btn_alarm_sound.setToolTip("알람 사운드 설정")

        self.btn_alarm_sound.setStyleSheet("""
        QPushButton {
            border-radius:16px;
            background:#F1F5F9;
            font-size:16px;
        }
        QPushButton:hover {
            background:#E2E8F0;
        }
        """)

        self.btn_alarm_sound.clicked.connect(self.toggle_alarm_sound)

        alarm_layout.addWidget(self.btn_alarm_sound)


        # 🔊 체크박스
        from PySide6.QtWidgets import QCheckBox

        self.chk_critical = QCheckBox("CRIT")
        self.chk_major = QCheckBox("MAJOR")
        self.chk_minor = QCheckBox("MINOR")
        self.chk_warning = QCheckBox("WARN")

        self.chk_critical.setChecked(True)
        self.chk_major.setChecked(True)
        self.chk_minor.setChecked(True)

        # 이벤트
        self.chk_critical.stateChanged.connect(lambda: self.set_alarm_level(1, self.chk_critical))
        self.chk_major.stateChanged.connect(lambda: self.set_alarm_level(2, self.chk_major))
        self.chk_minor.stateChanged.connect(lambda: self.set_alarm_level(3, self.chk_minor))
        self.chk_warning.stateChanged.connect(lambda: self.set_alarm_level(4, self.chk_warning))

        alarm_layout.addWidget(self.chk_critical)
        alarm_layout.addWidget(self.chk_major)
        alarm_layout.addWidget(self.chk_minor)
        alarm_layout.addWidget(self.chk_warning)

        # 👉 btn_layout에 붙이기
        btn_layout.addLayout(alarm_layout)


        # =========================
        # 👉 기존 layout에 추가 (이게 핵심!)
        # =========================
        layout.addWidget(self.status_circle)
        # 👉 기존 레이아웃에 추가 (예: status 옆)
        layout.addWidget(self.fail_label)
        layout.addLayout(btn_layout)   # 🔥 중요: addWidget이 아니라 addLayout        
        layout.addWidget(self.btn_module_order)
        
        layout.addStretch()

        self.skt_logo = QLabel()
        self.skt_logo.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.skt_logo.setStyleSheet("background:transparent;")
        skt_pixmap = QPixmap(resource_path("skt_logo.png"))
        if not skt_pixmap.isNull():
            self.skt_logo.setPixmap(
                # SKT 원본은 상하 여백이 더 커서 실제 글자 높이를 기준으로 보정한다.
                skt_pixmap.scaledToHeight(48, Qt.SmoothTransformation)
            )
        else:
            self.skt_logo.setToolTip("skt_logo.png 이미지를 불러올 수 없습니다.")
        layout.addWidget(self.skt_logo)
        layout.addSpacing(10)

        self.pantech_logo = QLabel()
        self.pantech_logo.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pantech_logo.setStyleSheet("background:transparent;")
        pantech_pixmap = QPixmap(resource_path("pantech.png"))
        if not pantech_pixmap.isNull():
            self.pantech_logo.setPixmap(
                pantech_pixmap.scaledToHeight(34, Qt.SmoothTransformation)
            )
        else:
            self.pantech_logo.setToolTip("pantech.png 이미지를 불러올 수 없습니다.")
        layout.addWidget(self.pantech_logo)
        
        return group

    def handle_connection_enter(self):
        """Enter 입력 시 누락된 접속값으로 이동하거나 접속을 시작한다."""
        for field in self.connection_input_fields:
            if not field.text().strip():
                field.setFocus(Qt.TabFocusReason)
                return

        if (
            not self.is_connected
            and self.connect_btn.isEnabled()
            and not getattr(self, "connection_start_pending", False)
        ):
            self.connect_btn.click()

    def save_site_info(self):

        site = self.site_edit.text().strip()
        system = self.system_edit.text().strip()

        equip = self.equip_edit.text().strip()
        manager = self.manager_edit.text().strip()
        maker = self.maker_edit.text().strip()
        model = self.model_edit.text().strip()
        serial = self.serial_edit.text().strip()

        if not site or not system:
            return

        safe_name = re.sub(r"[^\w\-]", "_", f"{site}_{system}")
        new_profile_path = os.path.join(os.path.dirname(self.profile_path), safe_name + ".ini")

        try:

            if self.profile_path != new_profile_path:
                self.settings.sync()

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
            # ==============================
            # 🔥 UI 즉시 반영 (추가)
            # ==============================
            self.site_edit.setText(site)
            self.system_edit.setText(system)

            self.settings.sync()

            # ==============================
            # 시스템 요약 정보 표시
            # ==============================
            summary_values = [equip, manager, maker, model, serial]
            for col, summary_value in enumerate(summary_values):
                display_value = summary_value if summary_value else "-"
                item = QTableWidgetItem(display_value)
                item.setTextAlignment(Qt.AlignCenter)
                self.summary_table.setItem(1, col, item)

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

        # 🔊 Alarm 설정 로드
        self.alarm_volume_level = int(self.settings.value("alarm/volume", 0))

        self.alarm_level_enable = {
            1: self.settings.value("alarm/level/1", True, type=bool),
            2: self.settings.value("alarm/level/2", True, type=bool),
            3: self.settings.value("alarm/level/3", True, type=bool),
            4: self.settings.value("alarm/level/4", False, type=bool),
            255: self.settings.value("alarm/level/255", False, type=bool),
        }
        
        site = self.settings.value("site", "")
        system = self.settings.value("system", "")

        equip = self.settings.value("equip", "")
        manager = self.settings.value("manager", "")
        maker = self.settings.value("maker", "")
        model = self.settings.value("model", "")
        serial = self.settings.value("serial", "")

        # 🔥 접속 정보 로드
        self.ip_edit.setText(self.settings.value("ip", "60.22.0.0"))
        self.port_edit.setText(self.settings.value("port", "161"))
        self.get_comm_edit.setText(self.settings.value("get_comm", "sktlfp48r"))
        self.set_comm_edit.setText(self.settings.value("set_comm", "sktlfp48w"))
        self.trap_comm_edit.setText(self.settings.value("trap_comm", "sktlfp48r"))
        if self.is_slave:
            local_port = int(self.settings.value("local_trap_port", 0))
            if local_port > 0:
                self.trap_port_edit.setText(str(local_port))
            else:
                self.trap_port_edit.setText("0")
        else:
            trap_port = int(self.settings.value("trap_port", 162))
            self.trap_port_edit.setText(str(trap_port))
        # 상단 표시
        self.site_edit.setText(site)
        self.system_edit.setText(system)
        
        # ==============================
        # 시스템 요약 정보 테이블 표시
        # ==============================
        summary_values = [equip, manager, maker, model, serial]
        for col, summary_value in enumerate(summary_values):
            text = str(summary_value or "").strip()
            item = QTableWidgetItem(text if text else "-")
            item.setTextAlignment(Qt.AlignCenter)
            self.summary_table.setItem(1, col, item)

    def apply_full_text_view(self, line_edit):
        # 🔥 tooltip으로 전체 표시
        line_edit.textChanged.connect(lambda text: line_edit.setToolTip(text))

        # 🔥 클릭 시 전체 선택 + 처음으로 이동
        def on_click(event):
            line_edit.setCursorPosition(0)
            line_edit.selectAll()
            QLineEdit.mousePressEvent(line_edit, event)

        line_edit.mousePressEvent = on_click
    
    def create_header(self):

        group = QGroupBox()

        layout = QVBoxLayout(group)

        # ===============================
        # 첫번째 줄
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

        # 🔥 Slave 목록 버튼 (위치 수정)
        self.btn_slave_list = QPushButton("Slave 목록")
        self.btn_slave_list.clicked.connect(self.open_slave_list_dialog)

        left_layout.addSpacing(5)
        left_layout.addWidget(self.btn_slave_list)

        # ❌ 여기서 setVisible 하지 마라
        # self.btn_slave_list.setVisible(self.is_master)

        self.btn_alarm_popup = QPushButton("발생된 알람 보기")
        # 텍스트 크기에 맞게 버튼을 한 번 계산한 뒤 고정(레이아웃 흔들림 방지)
        self.btn_alarm_popup.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_alarm_popup.adjustSize()
        hint = self.btn_alarm_popup.sizeHint()
        self.btn_alarm_popup.setFixedSize(hint.width() + 12, max(22, hint.height() - 2))
        self.btn_alarm_popup.setEnabled(False)
        self.btn_alarm_popup.clicked.connect(self.show_alarm_popup)
        self.set_alarm_popup_style(False)

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

        font = QFont("Consolas")
        font.setPointSize(10)
        font.setBold(True)
        self.status_label.setFont(font)

        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setFixedWidth(520)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        fm = QFontMetrics(font)
        height = fm.height() + 10

        self.status_label.setMinimumHeight(height)

        # =========================
        # SNMP TX / RX 상태 표시
        # =========================
        self.tx_led = QLabel()
        self.tx_led.setFixedSize(20, 10)
        self.tx_led.setStyleSheet("background:#505050;border-radius:4px;")

        self.rx_led = QLabel()
        self.rx_led.setFixedSize(20, 10)
        self.rx_led.setStyleSheet("background:#505050;border-radius:4px;")

        left_layout.addStretch()

        resource_widget = QWidget()
        resource_layout = QHBoxLayout(resource_widget)

        resource_layout.setContentsMargins(4, 2, 4, 2)
        resource_layout.setSpacing(4)

        resource_layout.addWidget(self.status_label)

        resource_widget.setMinimumHeight(height + 6)

        resource_widget.setStyleSheet("""
        QWidget {
            background-color: #1E1E1E;
            border-radius: 3px;
            padding: 0px 2px;
        }
        """)

        left_layout.addWidget(resource_widget)

        left_layout.addSpacing(20)

        layout.addLayout(left_layout)

        # ==================================
        # 두번째 줄
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

        info_layout.addWidget(QLabel("상면"))
        self.serial_edit = QLineEdit()
        self.serial_edit.setFixedWidth(140)
        self.apply_full_text_view(self.serial_edit)
        info_layout.addWidget(self.serial_edit)
        

        info_layout.addSpacing(10)

        save_btn = QPushButton("저장")
        save_btn.setFixedWidth(60)
        save_btn.clicked.connect(self.save_site_info)
        info_layout.addWidget(save_btn)

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

    def open_slave_list_dialog(self):
        dialog = SlaveListDialog(self)
        dialog.exec()

class SlaveListDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Slave 목록")
        self.resize(850, 400)

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.update_btn = QPushButton("업데이트")
        layout.addWidget(self.update_btn)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(btns)

        self.update_btn.clicked.connect(self.load_profiles)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        self.load_profiles()

        # 다이얼로그가 열려 있는 동안 heartbeat 상태를 5초마다 반영
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_profiles)
        self.refresh_timer.start(5000)

    def safe_stop_thread(thread):
        if thread and thread.isRunning():
            thread.stop()     # 내부 루프 종료 플래그
            thread.quit()     # Qt 이벤트 루프 종료
            thread.wait(3000) # 최대 3초 대기
        
    def load_profiles(self):
        self.list_widget.clear()

        parent = self.parent()
        profile_dir = parent.profile_dir if hasattr(parent, "profile_dir") else os.getcwd()
        current_profile = os.path.basename(parent.profile_path)
        registry = getattr(parent, "slave_registry", {})
        now = time.monotonic()
        displayed_profiles = set()

        if not os.path.exists(profile_dir):
            return

        for f in sorted(os.listdir(profile_dir)):
            if not f.endswith(".ini"):
                continue

            # 🔥 현재 Master 프로파일 제외
            if f == current_profile:
                continue

            file_path = os.path.join(profile_dir, f)

            settings = QSettings(file_path, QSettings.IniFormat)
            file_ip = settings.value("ip", "N/A")
            file_port = settings.value("local_trap_port", "N/A")
            runtime = registry.get(f)
            alive = bool(runtime and now - runtime.get("last_seen", 0) <= 12)
            status = "(alive)" if alive else "(-)"

            if runtime:
                registered = f"{runtime.get('ip', 'N/A')}:{runtime.get('port', 'N/A')}"
            else:
                registered = "미등록"

            item = QListWidgetItem(
                f"{status} {f} | 파일: {file_ip}:{file_port} | 등록상태: {registered}"
            )
            item.setForeground(QColor("#16803A" if alive else "#6B7280"))
            self.list_widget.addItem(item)
            displayed_profiles.add(f)

        # 프로파일 파일을 찾을 수 없지만 런타임에 등록된 Slave도 표시
        for profile_file, runtime in sorted(registry.items()):
            if profile_file in displayed_profiles or profile_file == current_profile:
                continue
            alive = now - runtime.get("last_seen", 0) <= 12
            status = "(alive)" if alive else "(-)"
            item = QListWidgetItem(
                f"{status} {profile_file} | 파일: 없음 | "
                f"등록상태: {runtime.get('ip', 'N/A')}:{runtime.get('port', 'N/A')}"
            )
            item.setForeground(QColor("#16803A" if alive else "#6B7280"))
            self.list_widget.addItem(item)
                

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
            ("Battery Fuse Broken",                      "축전지 내부 퓨즈 단선으로 전류 공급이 차단된 상태"),
            ("Lithium battery Missing",                  "SMU 재시작 후 이전보다 적은 수의 축전지가 감지된 상태"),
            ("Lithium battery communication failure",    "축전지와 SMU02C 또는 IoT 장비 간 통신이 불가능한 상태"),
            ("Lithium battery communication has failed.","축전지와 SMU02C 또는 IoT 장비 간 통신이 불가능한 상태"),
            ("All Lithium Battery Communication Failure","전체 축전지와 SMU02C 또는 IoT 장비 간 통신이 불가능한 상태"),
            ("Upgrade Failed",                           "축전지 모듈 펌웨어 업그레이드가 정상적으로 완료되지 않은 상태"),
            ("Low temperature protection",               "저온 환경에서 축전지를 보호하기 위해 보호 모드가 활성화된 상태"),
            ("Low temperature discharge",                "저온 상태에서 방전 성능 저하 또는 방전 제한이 발생한 상태"),
            ("High temperature protection",              "고온 환경에서 축전지를 보호하기 위해 보호 모드가 활성화된 상태"),
            ("Charging overvoltage",                     "충전 전압이 허용 범위를 초과한 상태"),
            ("Overcharge",                               "축전지가 허용된 최대 전압/용량 이상으로 충전된 상태"),
            ("Overdischarge",                            "축전지가 허용된 최소 전압/용량 이하로 방전된 상태"),
            ("Overcharge Protection",                    "과충전 상태로 인해 보호 모드가 활성화된 상태"),
            ("Overdischarge Protection",                 "과방전 상태로 인해 보호 모드가 활성화된 상태"),
            ("Charging Overcurrent Protection",          "충전 전류가 허용 범위를 초과하여 보호 모드가 활성화된 상태"),
            ("Heavy load Overcurrent Protection",        "부하 증가로 인해 과전류 보호 모드가 활성화된 상태"),
            ("Discharge Overcurrent Protection",         "방전 전류가 허용 범위를 초과하여 보호 모드가 활성화된 상태"),
            ("Upgrade failure",                          "축전지 BMS 펌웨어 업그레이드가 실패한 상태"),
            ("Busbar overvoltage protection",            "축전지 버스바 전압이 허용 범위를 초과하여 보호 모드가 활성화된 상태"),
            ("Input reverse connection",                 "축전지 입력 전압의 극성이 반대로 연결된 상태"),
            ("Abnormal shutdown",                        "축전지 시스템이 비정상적으로 종료된 상태"),
            ("Unlock failure",                           "축전지 잠금 해제 명령이 실패한 상태"),
            ("Board hardware fault",                     "BMS 제어 보드의 하드웨어 오류가 발생한 상태 (모듈 교체 필요)"),
            ("BMU Missing",                              "축전지 모듈 인식 불가 상태 (전원 또는 통신 이상)"),
            ("Lithium Battery Protection",               "축전지 보호 모드가 동작하여 충·방전이 차단된 상태"),                        
            ("Discharge Low Temperature",                "저온 상태로 인해 방전 성능 저하 또는 방전 제한이 발생한 상태"),
            ("Charge Overcurrent Protection",            "충전 중 과전류로 인해 보호 모드가 활성화된 상태"),        
            ("Discharge High Temperature Protection",    "방전 중 고온(65↑°C) 상태로 인해 보호 모드가 활성화된 상태"),
            ("Charge High Temperature Protection",       "충전 중 고온(60↑°C) 상태로 인해 보호 모드가 활성화된 상태"),            
            ("Discharge Low Temperature Protection",     "방전 중 저온(-20↓°C) 상태로 인해 보호 모드가 활성화된 상태"),
            ("Charge Low Temperature Protection",        "충전 중 저온(0↓°C) 상태로 인해 보호 모드가 활성화된 상태"),
            ("High Battery Temperature",                 "축전지 온도가 허용 기준 이상으로 상승한 상태"),
            ("Low Battery Temperature",                  "축전지 온도가 허용 기준 이하로 저하된 상태"),
            ("Low Temperature",                          "주변 또는 축전지 온도가 낮아 성능 저하가 발생할 수 있는 상태"),
            ("Overall Lithium Battery Protection",       "축전지 전체에 대한 보호 모드가 활성화된 상태 (시스템 레벨 차단)"),            
            ("Overvoltage Protection",                   "최대 셀 전압이 3.8V 초과한 상태"),
            ("Undervoltage Protection",                  "최소 셀 전압이 2.5V 미만인 상태"),            
            ("Cell 1 Fault",                             "셀 1 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 2 Fault",                             "셀 2 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 3 Fault",                             "셀 3 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 4 Fault",                             "셀 4 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 5 Fault",                             "셀 5 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 6 Fault",                             "셀 6 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 7 Fault",                             "셀 7 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 8 Fault",                             "셀 8 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 9 Fault",                             "셀 9 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 10 Fault",                            "셀 10 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 11 Fault",                            "셀 11 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 12 Fault",                            "셀 12 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 13 Fault",                            "셀 13 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 14 Fault",                            "셀 14 이상 상태 발생 (모듈 교체 필요)"),
            ("Cell 15 Fault",                            "셀 15 이상 상태 발생 (모듈 교체 필요)")
        ]

        self.table.setRowCount(len(alarms))

        for row, (name, desc) in enumerate(alarms):

            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(desc))

class LocalTrapReceiver(QThread):
    trap_signal = Signal(dict)
    listener_status_signal = Signal(bool, str)

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.running = True
        self.sock = None   # 🔥 멤버로 유지

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("127.0.0.1", self.port))
        except Exception as e:
            error_text = str(e) or repr(e)
            dprint("SNMP", f"[LOCAL TRAP] UDP bind failed 127.0.0.1:{self.port}: {error_text}")
            self.listener_status_signal.emit(False, error_text)
            try:
                if self.sock:
                    self.sock.close()
            except Exception:
                pass
            self.sock = None
            return

        self.listener_status_signal.emit(True, "")

        # 🔥 블로킹 탈출용
        self.sock.settimeout(1.0)

        while self.running:
            try:
                data, _ = self.sock.recvfrom(65535)

                # 🔥 running False 이후 들어온 데이터 무시
                if not self.running:
                    break

                trap_data = json.loads(data.decode())
                self.trap_signal.emit(trap_data)

            except socket.timeout:
                continue

            except OSError:
                # 🔥 socket.close() 시 발생 → 정상 종료
                break

            except Exception as e:
                if self.running:   # 🔥 종료 중이면 무시
                    dprint("DEBUG","❌ LocalTrapReceiver error:", e)

        # 🔥 안전 종료
        try:
            if self.sock:
                self.sock.close()
        except:
            pass

    def stop(self):
        self.running = False

        # 🔥 핵심: recvfrom 깨기
        try:
            if self.sock:
                self.sock.close()
        except:
            pass

        # 🔥 quit 제거 (이벤트 루프 없음)
        self.wait(2000)
            

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # =========================
    # 📁 profiles 폴더 준비
    # =========================
    profile_dir = os.path.join(os.getcwd(), "profiles")
    os.makedirs(profile_dir, exist_ok=True)
    dprint("DEBUG",f"profile={profile_dir}")

    # =========================
    # 🔥 싱글 인스턴스 체크 (핵심)
    # =========================
    from PySide6.QtCore import QLockFile

    lock_path = os.path.join(os.getcwd(), "app.lock")
    lock = QLockFile(lock_path)
    lock.setStaleLockTime(0)

    is_single = lock.tryLock(100)
    forced_slave = not is_single

    # 🔥 중요: lock 객체 유지 (안 하면 자동 해제됨)
    app.lock = lock

    dprint("DEBUG",f"🔥 is_single={is_single} → forced_slave={forced_slave}")

    # =========================
    # 🔥 단일 실행이면 상태 초기화
    # =========================
    if is_single:
        master_file = os.path.join(profile_dir, "master_profile.txt")
        if os.path.exists(master_file):
            try:
                os.remove(master_file)
                dprint("DEBUG","🔥 단일 실행 → master_profile.txt 삭제 완료")
            except Exception as e:
                dprint("DEBUG",f"❌ master_profile.txt 삭제 실패: {e}")

    # =========================
    # 🔥 Profile 선택/생성
    # =========================
    dialog = ProfileDialog(profile_dir, forced_slave=forced_slave)

    ini_files = [f for f in os.listdir(profile_dir) if f.endswith(".ini")]

    if not ini_files:
        # 👉 최초 실행 → 신규 생성
        dialog.create_new_profile()

        if not dialog.new_profile_data:
            sys.exit()
    else:
        # 👉 기존 profile 선택
        if not dialog.exec():
            sys.exit()

    # =========================
    # 🔥 mode 결정
    # =========================
    mode = getattr(dialog, "selected_mode", "Slave")
    forced_slave = getattr(dialog, "forced_slave", forced_slave)

    dprint("DEBUG",f"🔥mode:{mode} 🔥forced_slave:{forced_slave}")

    # =========================
    # 🔥 profile_path 결정
    # =========================
    if dialog.selected_profile_path:
        # ✔ 기존 profile 선택
        profile_path = dialog.selected_profile_path

        # 🔥 Master profile 선택 방지
        if dialog.master_profile_path and profile_path == dialog.master_profile_path:
            QMessageBox.warning(None, "오류", "Master에서 사용 중인 Profile은 선택할 수 없습니다.")
            sys.exit()

        new_profile_data = None

    else:
        # ✔ 신규 생성
        if not dialog.new_profile_data:
            sys.exit()

        data = dialog.new_profile_data
        site = data[0] if len(data) > 0 else ""
        system = data[1] if len(data) > 1 else ""

        safe_name = re.sub(r"[^\w\-]", "_", f"{site}_{system}")
        profile_path = os.path.join(profile_dir, safe_name + ".ini")

        new_profile_data = (site, system, mode, forced_slave)

    # =========================
    # 🔥 메인 UI 실행
    # =========================
    win = BatteryMonitorUI(profile_path, mode, new_profile_data, forced_slave)
    win.show()

    sys.exit(app.exec())
