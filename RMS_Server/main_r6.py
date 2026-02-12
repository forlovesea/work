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
    QDialog, QDialogButtonBox, QListWidget, QFormLayout, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSettings
from PySide6.QtGui import QColor, QFont

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
        self.quit()
        self.wait()

# ======================
# Module 상세정보 다이얼로그
# ======================
class ModuleDetailDialog(QDialog):
    def __init__(self, module_no, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"모듈 #{module_no:02d} 상세정보")
        self.setModal(True)
        self.resize(500, 400)
        layout = QVBoxLayout(self)
        info_group = QGroupBox(f"모듈 #{module_no:02d}")
        info_layout = QHBoxLayout(info_group)
        info_layout.addWidget(QLabel("SOH: 98.5%"))
        info_layout.addWidget(QLabel("SOC: 85.2%"))
        info_layout.addStretch()
        layout.addWidget(info_group)
        self.table = QTableWidget(15, 3)
        self.table.setHorizontalHeaderLabels(["셀", "전압[V]", "온도[℃]"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = self.table.horizontalHeader()
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
        sample_voltages = [3.25, 3.28, 3.30, 3.27, 3.29, 3.26, 3.31, 3.24, 3.28, 3.27, 3.30, 3.25, 3.29, 3.26, 3.28]
        sample_temps = [28.5, 29.1, 28.8, 29.3, 28.7, 29.0, 28.6, 29.2, 28.9, 29.1, 28.8, 29.0, 28.7, 29.4, 28.9]
        for row in range(15):
            cell_item = QTableWidgetItem(f"셀{row+1}")
            cell_item.setBackground(QColor("#E7F1FF"))
            cell_item.setFont(QFont("", weight=QFont.Bold))
            cell_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, cell_item)
            volt_item = QTableWidgetItem(f"{sample_voltages[row]:.2f}")
            volt_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, volt_item)
            temp_item = QTableWidgetItem(f"{sample_temps[row]:.1f}")
            temp_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, temp_item)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)
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

# ======================
# 메인 UI
# ======================
class BatteryMonitorUI(QMainWindow):
    def __init__(self, profile_path, new_profile_data=None):
        super().__init__()
        self.setWindowTitle("Battery Monitoring System (SNMP v2)")
        self.resize(1200, 850)
        self.ping_thread = None
        self.is_connected = False
        self.last_update_time = ""
        self.settings = QSettings(profile_path, QSettings.IniFormat)
        self.profile_path = profile_path

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

    # ===== 이전 UI 함수는 그대로 두고 save/load_site_info 적용 =====
    def on_connect_clicked(self):
        ip = self.ip_edit.text()
        print(f"Connecting to {ip}...")
    
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
        
        table = QTableWidget(8, 5)
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
            ["53.0", "100", "3.7", "3.2", "3.5"],
            ["0.0", "8", "30.0", "28.0", "29.0"],
            ["정상", "정상", "정상", "정상", "정상"]
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
        
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        summary_layout.addWidget(table)
        main_layout.addWidget(summary_group, 2)  # 70% 너비
        
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
        sample_traps = [
            ["2026-02-02 16:20:15", "hwAcbAlarmTrap:1.3.6.1.4.1.2011.6.164.2.1.3.0.99", "1", "OverCharge_Protection", "3", "31002", "Li Battery2", "Extend Li Battery Cabinet1"],
            ["2026-02-02 16:19:45", "hwAcbAlarmResumeTrap:1.3.6.1.4.1.2011.6.164.2.1.3.0.100", "2", "OverCharge_Resume", "3", "31002", "Li Battery2", "Extend Li Battery Cabinet1"]
        ]
        
        for trap in sample_traps:
            row = self.trap_table.rowCount()
            self.trap_table.insertRow(row)
            for col, val in enumerate(trap):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.trap_table.setItem(row, col, item)
        
        self.trap_table.resizeColumnsToContents()
        trap_layout.addWidget(self.trap_table)
        
        clear_btn = QPushButton("로그 지우기")
        clear_btn.clicked.connect(self.clear_trap_log)
        trap_layout.addWidget(clear_btn)
        
        main_layout.addWidget(trap_group, 1)  # 30% 너비
        return main_widget


    def create_module_table(self):
        """모듈 상태 테이블 (좌우 5개씩 총 10개)"""
        group = QGroupBox("모듈 상태")
        main_layout = QHBoxLayout(group)

        headers = ["모듈", "모듈 전압", "셀 전압 Max/Min[V]", "셀 온도 Max/Min[℃]", "경보", "차단기", "상세"]
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
                table.setItem(row, 2, QTableWidgetItem("17.00 / 16.00" if module_no <= 2 else "- / -"))
                table.setItem(row, 3, QTableWidgetItem("30.0 / 29.0" if module_no <= 2 else "- / -"))
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
        self.ip_edit = QLineEdit("192.168.0.100")
        self.ip_edit.setFixedWidth(140)
        layout.addWidget(self.ip_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Port"))
        self.port_edit = QLineEdit("161")
        self.port_edit.setFixedWidth(70)
        layout.addWidget(self.port_edit)
        layout.addSpacing(20)
        layout.addWidget(QLabel("GET"))
        self.get_comm_edit = QLineEdit("public")
        self.get_comm_edit.setFixedWidth(100)
        layout.addWidget(self.get_comm_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("SET"))
        self.set_comm_edit = QLineEdit("private")
        self.set_comm_edit.setFixedWidth(100)
        layout.addWidget(self.set_comm_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("TRAP"))
        self.trap_comm_edit = QLineEdit("public")
        self.trap_comm_edit.setFixedWidth(100)
        layout.addWidget(self.trap_comm_edit)
        layout.addSpacing(10)
        layout.addWidget(QLabel("TRAP Port"))
        self.trap_port_edit = QLineEdit("162")
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
        left_layout.addWidget(QLabel("축전지 이름"))
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
