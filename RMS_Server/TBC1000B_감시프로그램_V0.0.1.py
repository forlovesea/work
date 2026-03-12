# 실행프로그램 명령어
# cd D:\proj\GIT_HUB\work\RMS_Server
# pyinstaller --noconsole --onefile --icon=battery#2.ico --collect-all PySide6 --name TBC1000B_감시프로그램_V0.0.1 TBC1000B_감시프로그램_V0.0.1.py
#*최적화 실행 파일 옵션
#pyinstaller --noconfirm --onefile --windowed --clean --strip --noupx --exclude-module tkinter --exclude-module matplotlib --exclude-module numpy ^
#--exclude-module pandas --exclude-module scipy --exclude-module IPython --exclude-module jupyter #--exclude-module notebook --exclude-module test ^
#--exclude-module unittest --exclude-module email --exclude-module http TBC1000B_감시프로그램_V0.0.1.py

import sys
import subprocess
import platform
import os
import re
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QRadioButton, QLineEdit,
    QDialog, QDialogButtonBox, QListWidget, QFormLayout, QMessageBox,
    QSizePolicy, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSettings
from PySide6.QtGui import QColor, QFont
from pysnmp.hlapi import *

from pysnmp.hlapi import *
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv
import asyncore
from datetime import datetime

DEBUG_FLAGS = {
    "SNMP": False,
    "MODULE": False,
    "TRAP": False,
    "ALARM": False
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
    def __init__(self, listen_ip="0.0.0.0", port=1162, community="skt_public"):
        super().__init__()

        self.listen_ip = listen_ip
        self.port = int(port)
        self.community = community
        self.running = True
        self.snmpEngine = None
        self.setTerminationEnabled(True)

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
        for name, val in varBinds:
            print("  VARBIND:", str(name), "=", val.prettyPrint())
            trap_data[str(name)] = val.prettyPrint()

        # RX LED blink
        self.rx_signal.emit()
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
            "1.3.6.1.4.1.2011.6.164.1.17.1",
            "1.3.6.1.4.1.2011.6.164.1.18.1",
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
        self.setWindowTitle("TBC1000B-NDA1_Battery Monitoring System(Base SNMPv2) v0.0.1")
        
        self.resize(1200, 850)
        self.ping_thread = None
        self.snmp_thread = None
        self.trap_thread = None

        self.is_connected = False
        self.last_update_time = ""
        self.settings = QSettings(profile_path, QSettings.IniFormat)
        self.profile_path = profile_path
        
        self.module_map = {}        # {module_no: equip_id}
        self.module_data = {}       # {equip_id: {battery data}}
                
        self.fault_list = []
        
        self.active_fault_keys = set()
        
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

        if success:
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
                    print("[INFO] Stopping SNMP thread")
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
                    print("[INFO] Stopping TRAP thread")
                    self.trap_thread.stop()
                    if not self.trap_thread.wait(3000):
                        print("[WARN] TRAP thread did not stop in time, terminating...")
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
                    
                    if addr_oid in value:
                        module_no = int(value[addr_oid])
                        
                        if module_no not in self.module_map:
                            self.module_map[module_no] = {
                                "equip_id": row_index,
                                "swver": None,
                                "model": None,
                                "barcode": None
                            }
                        self.module_map[module_no]["swver"] = value[swver_oid]
                        self.module_map[module_no]["model"] = value[model_oid]
                        self.module_map[module_no]["barcode"] = value[barcode_oid]
                        
                        
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
            
            # 🔧 Fault 테이블 초기화
            self.clear_fault_table()
            self.active_fault_keys.clear()
            self.fault_list.clear()
            self.fault_table.setRowCount(0)
            
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
    
            # 🔥 Alarm Equip → Module 변환
            for alarm in self.current_alarm_table:

                equip = alarm.get("equip")
                alarm_text = alarm.get("text")
                alarm_time = alarm.get("time")

                module_no = None

                for m_no, info in self.module_map.items():
                    if int(info["equip_id"]) == int(equip):
                        module_no = m_no                        
                        module_name = f"모듈-{module_no}"
                        break

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
            
            #print("===== Voltage Calculation =====")
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
                    #print(f"module {module_no} → module_data 없음")
                    dprint("SNMP", f"module {module_no} → module_data 없음")
                    continue

                status = data.get("status")
                volt = data.get("volt")

                #print(f"module {module_no} status={status} volt={volt}")
                dprint("SNMP", f"module {module_no} status={status} volt={volt}")

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
            
            now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            #print(f"[{now}] [UPDATE SUCCESS] SNMP 데이터 갱신 완료")
            dprint("SNMP", f"[{now}] [UPDATE SUCCESS] SNMP 데이터 갱신 완료")

        else:
            self.status_circle.setStyleSheet(
                "background-color: #FF6B6B; border-radius: 7px;"
            )
            #print("[SNMP ERROR]")
            dprint("SNMP", "[SNMP ERROR]")
    
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
        
        # Fault Trap 처리
        self.handle_fault_trap(trap_data)
        
        #print("[TRAP RECEIVED]")
        dprint("SNMP", "[TRAP RECEIVED]")
        for k, v in trap_data.items():
            print(k, v)
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
        trap_group = QGroupBox("SNMP Trap 로그")
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

        clear_btn = QPushButton("TRAP 로그 지우기")
        clear_btn.clicked.connect(self.clear_trap_log)
        trap_layout.addWidget(clear_btn)

        main_layout.addWidget(trap_group, 1)

        return main_widget


    def create_module_table(self):
        """모듈 상태 테이블 (좌우 5개씩 총 10개)"""
        group = QGroupBox("모듈 상태")
        main_layout = QHBoxLayout(group)

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
            header = table.horizontalHeader()
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

        self.module_table_left = create_table(0)
        self.module_table_right = create_table(5)

        main_layout.addWidget(self.module_table_left)
        main_layout.addWidget(self.module_table_right)
        
        return group

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

        values = [
            f"#{fault_index:02d}",
            str(module_no),
            str(cell_no),
            f"{volt:.2f}",
            f"{temp:.1f}"
        ]

        for col, val in enumerate(values):

            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)

            item.setBackground(QColor("#F25F5C"))
            item.setForeground(QColor("white"))

            self.fault_table.setItem(row, col, item)
        
        # -----------------------------
        # 삭제 버튼 추가
        # -----------------------------
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
        self.ip_edit = QLineEdit("10.30.41.67")
        self.ip_edit.setFixedWidth(140)
        layout.addWidget(self.ip_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Port"))
        self.port_edit = QLineEdit("161")
        self.port_edit.setFixedWidth(70)
        layout.addWidget(self.port_edit)
        layout.addSpacing(20)
        layout.addWidget(QLabel("GET"))
        self.get_comm_edit = QLineEdit("skt_public")
        self.get_comm_edit.setFixedWidth(100)
        layout.addWidget(self.get_comm_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("SET"))
        self.set_comm_edit = QLineEdit("private")
        self.set_comm_edit.setFixedWidth(100)
        layout.addWidget(self.set_comm_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("TRAP"))
        self.trap_comm_edit = QLineEdit("skt_public")
        self.trap_comm_edit.setFixedWidth(100)
        layout.addWidget(self.trap_comm_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("TRAP Port"))
        self.trap_port_edit = QLineEdit("1162")
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
        layout.addWidget(self.status_circle)
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
        
        left_layout.addSpacing(100)
        left_layout.addWidget(self.btn_alarm_popup)

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

        self.update_time_label = QLabel("최종업데이트시간 : 대기중")
        self.update_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.tx_label = QLabel("Tx")
        self.tx_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.rx_label = QLabel("Rx")
        self.rx_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        left_layout.addStretch()
        
        left_layout.addWidget(self.tx_label)
        left_layout.addWidget(self.tx_led)
        left_layout.addSpacing(6)
        left_layout.addWidget(self.rx_label)
        left_layout.addWidget(self.rx_led)
        left_layout.addSpacing(10)
        
        left_layout.addWidget(self.update_time_label)

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

        info_layout.addStretch()

        layout.addLayout(info_layout)

        return group

    # ===== ping, module table, summary, fault table 등 기존 코드 그대로 유지 =====
    # 기존 함수들 그대로 붙이면 됩니다 (on_connect_clicked, start_ping_monitoring, stop_ping_monitoring, show_module_detail 등)
    # 편의상 생략. 전체 코드에 그대로 붙이면 됩니다.

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
