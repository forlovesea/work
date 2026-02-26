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
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSettings
from PySide6.QtGui import QColor, QFont
from pysnmp.hlapi import *

from pysnmp.hlapi import *
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv
import asyncore


LABEL_BG = QColor("#E7F1FF")

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
        
        if hasattr(self, "snmpEngine"):
            try:
                self.snmpEngine.transportDispatcher.closeDispatcher()
            except:
                pass
        
        self.quit()
        self.wait()

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

        # ======================================================
        # 1️⃣ module_no → equip_id 매핑
        # ======================================================
        equip_id = None
        module_data = None

        if module_no in self.parent_ui.module_map:
            equip_id = self.parent_ui.module_map[module_no]

        if equip_id and equip_id in self.parent_ui.module_data:
            module_data = self.parent_ui.module_data[equip_id]

        # 데이터 없을 경우 방어 처리
        if not module_data:
            module_data = {
                "volt": 0,
                "status": 255,
                "soc": 0,
                "soh": 0,
                "cells": [0]*15,
                "temps": [0]*15
            }

        # ======================================================
        # 2️⃣ 상단 정보 영역
        # ======================================================
        info_group = QGroupBox(f"모듈 #{module_no:02d}")
        info_layout = QHBoxLayout(info_group)

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

        status_text = status_map.get(module_data["status"], "Unknown")

        soc_text = f"{module_data['soc']} %" if module_data["soc"] is not None else "-"
        soh_text = f"{module_data['soh']} %" if module_data["soh"] is not None else "-"

        label_voltage = QLabel(f"Voltage: {module_data['volt']:.1f} V")        
        label_status = QLabel(f"Status: {status_text}")
        label_soc = QLabel(f"( SOC: {soc_text}")
        label_soh = QLabel(f"SOH: {soh_text})")

        info_layout.addWidget(label_voltage)        
        info_layout.addWidget(label_status)
        info_layout.addWidget(label_soc)
        info_layout.addWidget(label_soh)
        info_layout.addStretch()

        layout.addWidget(info_group)

        # ======================================================
        # 3️⃣ Cell Table
        # ======================================================
        self.table = QTableWidget(15, 3)
        self.table.setHorizontalHeaderLabels(["셀", "전압[V]", "온도[℃]"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.table.horizontalHeader()
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #E7F1FF;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #CCCCCC;
            }
        """)

        cells = module_data["cells"][:]
        temps = module_data["temps"][:]

        while len(cells) < 15:
            cells.append(0)

        while len(temps) < 15:
            temps.append(0)

        max_v = max(cells)
        min_v = min(cells)

        for row in range(15):

            # 셀 번호
            cell_item = QTableWidgetItem(f"셀{row+1}")
            cell_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, cell_item)

            # 전압
            volt_value = cells[row]
            volt_item = QTableWidgetItem(f"{volt_value:.2f}")
            volt_item.setTextAlignment(Qt.AlignCenter)

            if volt_value == max_v:
                volt_item.setBackground(QColor("#D3F9D8"))  # 초록
            elif volt_value == min_v:
                volt_item.setBackground(QColor("#FFE3E3"))  # 빨강

            self.table.setItem(row, 1, volt_item)

            # 온도
            temp_value = temps[row]
            temp_item = QTableWidgetItem(f"{temp_value:.1f}")
            temp_item.setTextAlignment(Qt.AlignCenter)
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

    def __init__(self, listen_ip="0.0.0.0", port=1162, community="skt_public"):
        super().__init__()

        self.listen_ip = listen_ip
        self.port = int(port)
        self.community = community
        self.running = True

    def run(self):
        print(f"[TRAP] Thread run start (listen {self.listen_ip}:{self.port})")
        
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

        print(f"[TRAP] Listening on {self.listen_ip}:{self.port}")

        #while self.running:
        #    asyncore.loop(timeout=1, count=1)
        
        self.snmpEngine.transportDispatcher.jobStarted(1)

        try:
            self.snmpEngine.transportDispatcher.runDispatcher()
        except Exception as e:
            print("Trap dispatcher error:", e)
            self.snmpEngine.transportDispatcher.closeDispatcher()

        print("[TRAP] Thread stopped")

    def callback(self, snmpEngine, stateReference,
                 contextEngineId, contextName,
                 varBinds, cbCtx):

        print("[TRAP CALLBACK] called")
        trap_data = {}

        for name, val in varBinds:
            print("  VARBIND:", str(name), "=", val.prettyPrint())
            trap_data[str(name)] = val.prettyPrint()

        self.trap_signal.emit(trap_data)

    def stop(self):
        print("[TRAP] stop() called")
        self.running = False
        try:
            if hasattr(self, "snmpEngine"):
                self.snmpEngine.transportDispatcher.closeDispatcher()
        except Exception as e:
            print("[TRAP] closeDispatcher error:", e)
        self.quit()
        self.wait()

# ======================
# SNMP Worker Thread
# ======================

class SNMPThread(QThread):
    result_signal = Signal(bool, object)  # str → object (dict 전달 가능)

    def __init__(self, ip, community="public", port=161, once=False):
        super().__init__()
        self.ip = ip
        self.community = community
        self.port = port
        self.running = True
        self.once = once  # 최초 테스트 여부

    def run(self):

        # ===============================
        # 1️⃣ 최초 연결 테스트 (sysUpTime)
        # ===============================
        if self.once:
            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(
                    SnmpEngine(),
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
            else:
                for varBind in varBinds:
                    value = str(varBind[1])
                    print(f"[SNMP RESPONSE] sysUpTime: {value}")
                    self.result_signal.emit(True, value)

            return

        # ===============================
        # 2️⃣ 실제 배터리 MIB Polling
        # ===============================

        base_oids = [
            "1.3.6.1.4.1.2011.6.164.1.18",
            "1.3.6.1.4.1.2011.6.164.1.17.1"
        ]
        
        snmpEngine = SnmpEngine()
        
        while self.running:

            result_data = {}

            for base_oid in base_oids:

                #for (errorIndication,
                #    errorStatus,
                #    errorIndex,
                #    varBinds) in nextCmd(
                #        SnmpEngine(),
                #        CommunityData(self.community, mpModel=1),
                #        UdpTransportTarget(
                #            (self.ip, int(self.port)),
                #            timeout=2,
                #            retries=0
                #        ),                
                #        ContextData(),
                #        ObjectType(ObjectIdentity(base_oid)),
                #        lexicographicMode=False):
                for (errorIndication,
                    errorStatus,
                    errorIndex,
                    varBinds) in bulkCmd(
                        SnmpEngine(),
                        CommunityData(self.community, mpModel=1),
                        UdpTransportTarget((self.ip, int(self.port))),
                        ContextData(),
                        0, 25,   # nonRepeaters, maxRepetitions
                        ObjectType(ObjectIdentity(base_oid)),
                        lexicographicMode=False):
                        
                    if not self.running:
                        return

                    if errorIndication or errorStatus:
                        self.result_signal.emit(False, "")
                        break

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
        if hasattr(self, "snmpEngine"):
            try:
                self.snmpEngine.transportDispatcher.closeDispatcher()
            except:
                pass
        self.quit()
        self.wait()
        
# ======================
# 메인 UI
# ======================
class BatteryMonitorUI(QMainWindow):
    def __init__(self, profile_path, new_profile_data=None):
        super().__init__()
        self.setWindowTitle("Battery Monitoring System(Base SNMPv2)")
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
            self.connect_btn.setText("종료")

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
            self.snmp_thread.result_signal.connect(self.handle_snmp_result)
            self.snmp_thread.start()
            trap_port = int(self.trap_port_edit.text().strip())
            
            self.trap_thread = SNMPTrapThread(
                listen_ip="0.0.0.0",
                port=trap_port,
                community=trap_comm
            )
            self.trap_thread.trap_signal.connect(self.handle_trap)
            self.trap_thread.start()

        else:
            self.show_auto_close_message("접속 실패", "축전지 시스템 연결 실패.")


    # ===== 이전 UI 함수는 그대로 두고 save/load_site_info 적용 =====
    def on_connect_clicked(self):
        # ======================
        # 종료 모드
        # ======================
        if self.is_connected:
            if self.snmp_thread and self.snmp_thread.isRunning():
                self.snmp_thread.stop()
                
            if self.trap_thread and self.trap_thread.isRunning():
                self.trap_thread.stop()
        
            self.is_connected = False
            self.connect_btn.setText("접속")
            self.status_circle.setStyleSheet(
                "background-color: #CCCCCC; border-radius: 7px;"
            )
            self.show_auto_close_message("접속 종료", "축전지 시스템 연결 종료.")
            
            return

        # ======================
        # 접속 시도 (1회 테스트)
        # ======================
        ip = self.ip_edit.text().strip()
        port = self.port_edit.text().strip()
        community = self.get_comm_edit.text().strip()

        self.test_thread = SNMPThread(ip, community, port, once=True)
        self.test_thread.result_signal.connect(self.handle_connection_test)
        self.test_thread.start()

        print(f"[INFO] SNMP GETNEXT started to {ip}...")
 #################################################################################
    def update_module_tables(self):

        status_map = {
            0: ("Online", "#B2F2BB"),
            1: ("Offline", "#FF6B6B"),
            2: ("Sleep", "#CED4DA"),
            3: ("Disconnect", "#FF6B6B"),
            4: ("Charge", "#B2F2BB"),
            5: ("Discharge", "#4DABF7"),
            6: ("Standby", "#FFD43B"),
            255: ("Unknown", "#CED4DA")
        }

        for module_no in range(1, 11):

            if module_no not in self.module_map:
                continue

            equip_id = self.module_map[module_no]

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
            if data["cells"]:
                max_v = max(data["cells"])
                min_v = min(data["cells"])
                table.item(row, 2).setText(f"{max_v:.2f} / {min_v:.2f}")

            # -----------------
            # 온도 Max/Min
            # -----------------
            if data["temps"]:
                max_t = max(data["temps"])
                min_t = min(data["temps"])
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
    # ======================
    # SNMP 응답 처리
    # ======================
    def handle_snmp_result(self, success, value):

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if success and isinstance(value, dict):

            # ===============================
            # 상태 표시 (녹색)
            # ===============================
            self.status_circle.setStyleSheet(
                "background-color: #2ECC71; border-radius: 7px;"
            )
            self.update_time_label.setText(f"최종업데이트시간 : {current_time}")

            # 🔥 모듈 데이터 초기화
            self.module_map.clear()      # {module_no: equip_id}
            self.module_data.clear()     # {equip_id: {volt, status, cells[], temps[]}}

            # ===============================
            # OID 데이터 처리
            # ===============================
            for oid, val in value.items():

                if str(val) == "2147483647":
                    continue

                val_str = str(val)

                # ====================================================
                # 🔵 1️⃣ Summary / Base 정보 (기존 로직 유지)
                # ====================================================

                if oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.5.96":
                    rack_voltage = int(val_str) / 10
                    item = self.summary_table.item(2, 0)
                    item.setText(f"{rack_voltage:.1f}")
                    apply_value_style(item, "정상")

                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.6.96":
                    rack_current = int(val_str) / 10
                    item = self.summary_table.item(4, 0)
                    item.setText(f"{rack_current:.1f}")
                    apply_value_style(item, "정상")

                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.8.96":
                    item = self.summary_table.item(2, 1)
                    item.setText(f"{val_str} %")
                    apply_value_style(item, "정상")

                elif oid == "1.3.6.1.4.1.2011.6.164.1.17.1.1.23.96":
                    item = self.summary_table.item(4, 1)
                    item.setText(val_str)
                    apply_value_style(item, "정상")

                elif ".1.18.1.1.3." in oid:
                    self.label_equip_name.setText(val_str)

                elif ".1.18.1.1.5." in oid:
                    self.label_soft_ver.setText(val_str)

                elif ".1.18.1.1.11." in oid:
                    self.label_hw_ver.setText(val_str)

                elif ".1.18.1.1.12." in oid:
                    self.label_model.setText(val_str)

                # ====================================================
                # 🔵 2️⃣ BaseTable → module 매핑 추가
                # ====================================================
                if ".1.18.1.1.2." in oid:   # equipId
                    index = oid.split(".")[-1]
                    equip_id = val_str

                    addr_oid = oid.replace(".1.2.", ".1.3.")
                    if addr_oid in value:
                        module_no = int(value[addr_oid])
                        self.module_map[module_no] = equip_id

                # ====================================================
                # 🔵 3️⃣ SampTable → 모듈 데이터 수집
                # ====================================================
                if ".1.18.2.1." in oid:

                    parts = oid.split(".")
                    column = parts[-2]
                    equip_id = parts[-1]

                    if equip_id not in self.module_data:
                        self.module_data[equip_id] = {
                            "volt": None,
                            "status": None,
                            "soc": None,
                            "soh": None,
                            "cells": [],
                            "temps": []
                        }

                    # 모듈 전압
                    if column == "1":
                        self.module_data[equip_id]["volt"] = int(val_str) / 10

                    # Running Status
                    elif column == "3":
                        self.module_data[equip_id]["status"] = int(val_str)

                     # SOH
                    elif column == "4":
                        self.module_data[equip_id]["soh"] = int(val_str)                    

                    # Cell Voltage (6~20)
                    elif 6 <= int(column) <= 20:
                        self.module_data[equip_id]["cells"].append(int(val_str) / 10)

                    # Cell Temp (22~36)
                    elif 22 <= int(column) <= 36:
                        self.module_data[equip_id]["temps"].append(int(val_str) / 10)
                    
                    # SOC
                    elif column == "52":
                        self.module_data[equip_id]["soh"] = int(val_str)

                # ====================================================
                # 🔵 4️⃣ 기존 단일 Sample 표시 유지
                # ====================================================

                elif ".1.18.2.1.1." in oid:
                    self.label_voltage.setText(f"{int(val_str)/10:.1f} V")

                elif ".1.18.2.1.2." in oid:
                    self.label_current.setText(f"{int(val_str)/10:.1f} A")

                elif ".1.18.2.1.3." in oid:
                    status_map = {
                        "0": "Online",
                        "1": "Offline",
                        "2": "Sleep",
                        "3": "Disconnect",
                        "4": "Charge",
                        "5": "Discharge",
                        "6": "Standby",
                        "255": "Unknown"
                    }
                    self.label_status.setText(status_map.get(val_str, val_str))

                elif ".1.18.2.1.4." in oid:
                    self.label_soh.setText(f"{val_str} %")

                elif ".1.18.2.1.5." in oid:
                    self.label_capacity.setText(f"{int(val_str)/10:.1f} Ah")

                # Cell Voltage 1~15
                for i in range(1, 16):
                    if f".1.18.2.1.{5+i}." in oid:
                        getattr(self, f"label_cell{i}_volt").setText(
                            f"{int(val_str)/10:.1f} V"
                        )

                # Cell Temp 1~15
                for i in range(1, 16):
                    if f".1.18.2.1.{21+i}." in oid:
                        getattr(self, f"label_cell{i}_temp").setText(
                            f"{int(val_str)/10:.1f} °C"
                        )

            # ====================================================
            # 🔥 5️⃣ 모듈 테이블 갱신
            # ====================================================
            self.update_module_tables()

            print("[UPDATE SUCCESS] SNMP 데이터 갱신 완료")

        else:
            self.status_circle.setStyleSheet(
                "background-color: #FF6B6B; border-radius: 7px;"
            )
            print("[SNMP ERROR]")
    
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

                item = self.summary_table.item(7, 0)

                if trap_oid in alarm_oids:
                    item.setText("이상")
                    item.setBackground(QColor("#FF6B6B"))
                    item.setForeground(QColor("white"))

                elif trap_oid in resume_oids:
                    item.setText("정상")
                    item.setBackground(QColor("#B2F2BB"))
                    item.setForeground(QColor("black"))
                
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

                item = self.summary_table.item(7, 1)

                if trap_oid in alarm_oids:
                    item.setText("이상")
                    item.setBackground(QColor("#FF6B6B"))
                    item.setForeground(QColor("white"))

                elif trap_oid in resume_oids:
                    item.setText("정상")
                    item.setBackground(QColor("#B2F2BB"))
                    item.setForeground(QColor("black"))
        
        # =====================================================
        # 🔥 과전류 충전차단 제어 (col 2)
        # =====================================================
        over_current_temp_keywords = [
            "charge overcurrent protection",
            "charging overcurrent protection"
        ]

        if any(k in alarm_lower for k in over_current_temp_keywords):
            if trap_oid.startswith("1.3.6.1.4.1.2011.6.164.2.1.3."):

                item = self.summary_table.item(7, 2)

                if trap_oid in alarm_oids:
                    item.setText("이상")
                    item.setBackground(QColor("#FF6B6B"))
                    item.setForeground(QColor("white"))

                elif trap_oid in resume_oids:
                    item.setText("정상")
                    item.setBackground(QColor("#B2F2BB"))
                    item.setForeground(QColor("black"))

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

        print("[TRAP RECEIVED]")
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
        
        # === 1. 시스템 요약 정보 ===
        summary_group = QGroupBox("시스템 요약 정보")
        summary_layout = QVBoxLayout(summary_group)
        
        self.summary_table = QTableWidget(8, 5)
        table = self.summary_table
        
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        labels = [
            ["설비번호", "운용 관리자", "제조사", "모델명", "시리얼번호"],
            ["Rack 전압[V]", "SOC 충전율[%]", "Max 전압[V]", "Min 전압[V]", "Avg 전압[V]"],
            ["Rack 전류[A]", "충방전 횟수", "Max 온도[℃]", "Min 온도[℃]", "Avg 온도[℃]"],
            ["과전압 충전차단", "고온 충전차단", "과전류 충전차단", "Fuse 상태", "충전 릴레이"]
        ]
        
        values = [
            ["-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-"]
        ]
        
        LABEL_BG = QColor(220, 235, 255)
        label_font = QFont()
        label_font.setBold(True)
        
        for block in range(4):
            label_row = block * 2
            value_row = label_row + 1
            for col in range(5):
                # 라벨
                label_item = QTableWidgetItem(labels[block][col])
                label_item.setTextAlignment(Qt.AlignCenter)
                label_item.setBackground(LABEL_BG)
                label_item.setFont(label_font)
                table.setItem(label_row, col, label_item)
                
                # 값
                value_item = QTableWidgetItem(values[block][col])
                value_item.setTextAlignment(Qt.AlignCenter)
                apply_value_style(value_item, values[block][col])
                table.setItem(value_row, col, value_item)
        
        #table.resizeColumnsToContents()
        #table.resizeRowsToContents()
        #summary_layout.addWidget(table)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()

        # 🔥 테이블 전체 크기를 내용에 맞게 계산
        width = table.verticalHeader().width()
        for i in range(table.columnCount()):
            width += table.columnWidth(i)

        height = table.horizontalHeader().height()
        for i in range(table.rowCount()):
            height += table.rowHeight(i)

        table.setFixedSize(width + 2, height + 2)  # border 여유 2px

        summary_layout.addWidget(table)
        
        ########################################################################################################################
        summary_layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        summary_group.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        #main_layout.addWidget(summary_group, 2)  # 70% 너비
        main_layout.addWidget(summary_group)
        
        # === 2. SNMP Trap 로그 ===
        trap_group = QGroupBox("SNMP Trap 로그")
        trap_layout = QVBoxLayout(trap_group)
        
        self.trap_table = QTableWidget(0, 8)
        trap_headers = ["시간", "Trap OID", "OrdinalNumber", "Alarm", "Level", "EquipID", "EquipName", "FatherEquipname"]
        self.trap_table.setHorizontalHeaderLabels(trap_headers)
        self.trap_table.verticalHeader().setVisible(False)
        self.trap_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        header = self.trap_table.horizontalHeader()
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
        
        # 샘플 Trap 데이터
        #sample_traps = [
        #    ["2026-02-02 16:20:15", "hwAcbAlarmTrap:1.3.6.1.4.1.2011.6.164.2.1.3.0.99", "1", "OverCharge_Protection", "3", "31002", "Li Battery2", "Extend Li Battery Cabinet1"],
        #    ["2026-02-02 16:19:45", "hwAcbAlarmResumeTrap:1.3.6.1.4.1.2011.6.164.2.1.3.0.100", "2", "OverCharge_Resume", "3", "31002", "Li Battery2", "Extend Li Battery Cabinet1"]
        #]
        #
        #for trap in sample_traps:
        #    row = self.trap_table.rowCount()
        #    self.trap_table.insertRow(row)
        #    for col, val in enumerate(trap):
        #        item = QTableWidgetItem(val)
        #        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        #        self.trap_table.setItem(row, col, item)
        
        self.trap_table.resizeColumnsToContents()
        trap_layout.addWidget(self.trap_table)
        
        clear_btn = QPushButton("TRAP 로그 지우기")
        clear_btn.clicked.connect(self.clear_trap_log)
        trap_layout.addWidget(clear_btn)
        
        #main_layout.addWidget(trap_group, 1)  # 30% 너비
        main_layout.addWidget(trap_group, 1)
        return main_widget


    def create_module_table(self):
        """모듈 상태 테이블 (좌우 5개씩 총 10개)"""
        group = QGroupBox("모듈 상태")
        main_layout = QHBoxLayout(group)

        headers = ["모듈", "모듈 전압", "셀 전압 Max/Min[V]", "셀 온도 Max/Min[℃]", "경보", "통신상태", "상세"]
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
                table.setItem(row, 4, QTableWidgetItem("정상"))
                table.setItem(row, 5, QTableWidgetItem("-"))

                btn = QPushButton("상세")
                btn.clicked.connect(lambda checked, no=module_no: self.show_module_detail(no))
                table.setCellWidget(row, 6, btn)

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

        left_table = create_table(0)
        right_table = create_table(5)
        main_layout.addWidget(left_table)
        main_layout.addWidget(right_table)
        return group


    def create_fault_table(self):
        """고장 정보 테이블"""
        group = QGroupBox("고장 정보")
        layout = QVBoxLayout(group)

        faults = [
            {"module": "3", "cell": "12", "volt": "2.95", "temp": "62.0"},
            {"module": "5", "cell": "8", "volt": "2.88", "temp": "58.3"},
        ]

        table = QTableWidget(len(faults), 5)
        table.verticalHeader().setVisible(False)
        headers = ["Fault", "고장 모듈 No", "고장 셀 No", "고장 셀 전압[V]", "고장 셀 온도[℃]"]
        table.setHorizontalHeaderLabels(headers)

        for col in range(len(headers)):
            header_item = table.horizontalHeaderItem(col)
            header_item.setBackground(QColor("#E7F1FF"))
            header_item.setFont(QFont("", weight=QFont.Bold))
            header_item.setTextAlignment(Qt.AlignCenter)

        for row, fault in enumerate(faults):
            values = [f"Fault#{row+1}", fault["module"], fault["cell"], fault["volt"], fault["temp"]]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                item.setBackground(QColor("#FF6B6B"))
                item.setForeground(QColor("white"))
                table.setItem(row, col, item)

        table.resizeColumnsToContents()
        layout.addWidget(table)
        return group

    #############################################################################
    def create_connection_panel(self):
        group = QGroupBox("Battery System 접속 설정")
        layout = QHBoxLayout(group)
        layout.addWidget(QLabel("IP"))
        self.ip_edit = QLineEdit("10.30.41.61")
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
        self.connect_btn = QPushButton("접속")
        self.connect_btn.setFixedWidth(80)
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        layout.addWidget(self.connect_btn)
        layout.addStretch()
        return group

    def save_site_info(self):
        site = self.site_edit.text().strip()
        system = self.system_edit.text().strip()

        if not site or not system:
            QMessageBox.warning(self, "저장 오류", "설치 장소와 시스템 이름을 입력하세요.")
            return

        safe_name = re.sub(r"[^\w\-]", "_", f"{site}_{system}")
        new_profile_path = os.path.join(os.path.dirname(self.profile_path), safe_name + ".ini")

        try:
            # 파일명 변경 필요 시 rename
            if self.profile_path != new_profile_path:
                self.settings.sync()
                if os.path.exists(self.profile_path):
                    os.rename(self.profile_path, new_profile_path)
                self.profile_path = new_profile_path
                self.settings = QSettings(self.profile_path, QSettings.IniFormat)

            self.settings.setValue("site", site)
            self.settings.setValue("system", system)
            self.settings.sync()

            QMessageBox.information(self, "저장 완료", "프로파일이 정상적으로 저장되었습니다.")

        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"저장 중 오류 발생:\n{str(e)}")


    def load_site_info(self):
        self.site_edit.setText(self.settings.value("site", ""))
        self.system_edit.setText(self.settings.value("system", ""))

    def create_header(self):
        group = QGroupBox()
        layout = QHBoxLayout(group)
        left_layout = QHBoxLayout()
        left_layout.addWidget(QLabel("설치 장소"))
        self.site_edit = QLineEdit()
        self.site_edit.setFixedWidth(180)
        left_layout.addWidget(self.site_edit)
        left_layout.addSpacing(10)
        left_layout.addWidget(QLabel("축전지명"))
        self.system_edit = QLineEdit()
        self.system_edit.setFixedWidth(180)
        left_layout.addWidget(self.system_edit)
        save_btn = QPushButton("저장")
        save_btn.setFixedWidth(60)
        save_btn.clicked.connect(self.save_site_info)
        left_layout.addWidget(save_btn)
        left_layout.addSpacing(30)
        self.bmu_label = QLabel("접속상태")
        self.status_circle = QLabel()
        self.status_circle.setFixedSize(15, 15)
        self.status_circle.setStyleSheet("background-color: #CCCCCC; border-radius: 7px; border: 1px solid #999999;")
        left_layout.addWidget(self.bmu_label)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.status_circle)
        left_layout.addStretch()
        self.update_time_label = QLabel("최종업데이트시간 : 대기중")
        self.update_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(left_layout)
        layout.addWidget(self.update_time_label)
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
