import sys
import subprocess
import platform
import os

from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QRadioButton, QLineEdit,
    QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSettings
from PySide6.QtGui import QColor, QFont


LABEL_BG = QColor("#E7F1FF")

def ping_host(ip):
    """IP 핑 테스트 (timeout 예외 처리 추가)"""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        result = subprocess.run(["ping", param, "1", ip], 
                              capture_output=True, text=True, timeout=2)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        # 🔹 timeout도 실패로 처리
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
    ping_result = Signal(bool, str)  # 성공여부, 시간
    
    def __init__(self, ip):
        super().__init__()
        self.ip = ip
        self.running = True
    
    def run(self):
        while self.running:
            success = ping_host(self.ip)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.ping_result.emit(success, current_time)
            self.msleep(1000)  # 1초 대기
    
    def stop(self):
        self.running = False
        self.quit()
        self.wait()

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

class BatteryMonitorUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Battery Monitoring System (SNMP v2)")
        self.resize(1200, 850)

        self.ping_thread = None
        self.is_connected = False
        self.last_update_time = ""
        self.settings = QSettings("MyCompany", "BatteryMonitor")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        main_layout.addWidget(self.create_connection_panel())        
        main_layout.addWidget(self.create_header())
        #main_layout.addWidget(self.create_summary_table())
        main_layout.addWidget(self.create_summary_section())
        main_layout.addWidget(self.create_module_table())
        main_layout.addWidget(self.create_fault_table())
    
    def on_connect_clicked(self):
        ip = self.ip_edit.text()
        port = int(self.port_edit.text())
        trap_port = int(self.trap_port_edit.text())
        get_comm = self.get_comm_edit.text()
        set_comm = self.set_comm_edit.text()
        trap_comm = self.trap_comm_edit.text()

        print("=== SNMP 접속 정보 ===")
        print(f"IP          : {ip}")
        print(f"Port        : {port}")
        print(f"GET Comm    : {get_comm}")
        print(f"SET Comm    : {set_comm}")
        print(f"TRAP Comm   : {trap_comm}")
        print(f"TRAP Port   : {trap_port}")

        if not self.is_connected:
            # 🔹 접속 시작
            self.is_connected = True
            self.connect_btn.setText("접속중")
            self.bmu_label.setText(ip)
            self.start_ping_monitoring(ip)
        else:
            # 🔹 접속 종료 - 완전 비활성화
            self.stop_ping_monitoring()
            self.is_connected = False
            self.connect_btn.setText("접속")
            self.bmu_label.setText("접속상태")
            
            # 🔹 상태 원 회색으로 변경 (비활성)
            self.status_circle.setStyleSheet("""
                background-color: #CCCCCC; 
                border-radius: 7px; 
                border: 1px solid #999999;
            """)
            
            # 🔹 마지막 업데이트 시간 유지
            if self.last_update_time:
                self.update_time_label.setText(f"최종업데이트시간 : {self.last_update_time}")
    
    def start_ping_monitoring(self, ip):
        self.ping_thread = PingThread(ip)
        self.ping_thread.ping_result.connect(self.on_ping_result)
        self.ping_thread.start()
    
    def stop_ping_monitoring(self):
        if self.ping_thread:
            self.ping_thread.stop()
            self.ping_thread = None
    
    def on_ping_result(self, success, current_time):
        # 상태 원 색상 변경
        if success:
            self.status_circle.setStyleSheet("background-color: #B2F2BB; border-radius: 7px; border: 1px solid green;")
            self.last_update_time = current_time
        else:
            self.status_circle.setStyleSheet("background-color: #FF6B6B; border-radius: 7px; border: 1px solid red;")
        
        # 최종갱신시간 업데이트
        self.update_time_label.setText(f"최종갱신시간 : {self.last_update_time}")
    
    def show_module_detail(self, module_no):
        dialog = ModuleDetailDialog(module_no, self)
        dialog.exec()

    def closeEvent(self, event):
        self.stop_ping_monitoring()
        event.accept()

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
        site = self.site_edit.text()
        system = self.system_edit.text()

        self.settings.setValue("site", site)
        self.settings.setValue("system", system)

    def load_site_info(self):
        site = self.settings.value("site", "")
        system = self.settings.value("system", "")

        self.site_edit.setText(site)
        self.system_edit.setText(system)
    
    def create_header(self):
        group = QGroupBox()
        layout = QHBoxLayout(group)

        # ===== 좌측 : 설치 장소 + 시스템 이름 =====
        left_layout = QHBoxLayout()

        left_layout.addWidget(QLabel("설치 장소"))
        self.site_edit = QLineEdit()
        self.site_edit.setFixedWidth(180)
        left_layout.addWidget(self.site_edit)

        left_layout.addSpacing(10)

        left_layout.addWidget(QLabel("시스템 이름"))
        self.system_edit = QLineEdit()
        self.system_edit.setFixedWidth(180)
        left_layout.addWidget(self.system_edit)

        save_btn = QPushButton("저장")
        save_btn.setFixedWidth(60)
        save_btn.clicked.connect(self.save_site_info)
        left_layout.addWidget(save_btn)

        left_layout.addSpacing(30)

        # ===== 접속상태 =====
        self.bmu_label = QLabel("접속상태")
        self.status_circle = QLabel()
        self.status_circle.setFixedSize(15, 15)
        self.status_circle.setStyleSheet("""
            background-color: #CCCCCC; 
            border-radius: 7px; 
            border: 1px solid #999999;
        """)

        left_layout.addWidget(self.bmu_label)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.status_circle)

        left_layout.addStretch()

        # ===== 우측 : 업데이트 시간 =====
        self.update_time_label = QLabel("최종업데이트시간 : 대기중")
        self.update_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addLayout(left_layout)
        layout.addWidget(self.update_time_label)

        # 🔹 저장된 값 로드
        self.load_site_info()

        return group

    def create_summary_table(self):
        group = QGroupBox("시스템 요약 정보")
        layout = QVBoxLayout(group)

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
                label_item = QTableWidgetItem(labels[block][col])
                label_item.setTextAlignment(Qt.AlignCenter)
                label_item.setBackground(LABEL_BG)
                label_item.setFont(label_font)
                table.setItem(label_row, col, label_item)

                value_text = values[block][col]
                value_item = QTableWidgetItem(value_text)
                value_item.setTextAlignment(Qt.AlignCenter)
                apply_value_style(value_item, value_text)
                table.setItem(value_row, col, value_item)

        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        layout.addWidget(table)
        return group

    def create_summary_section(self):
        # 수평 레이아웃으로 요약정보 + Trap로그 병렬 배치
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        
        # === 1. 기존 시스템 요약 정보 (왼쪽 70%) ===
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
                value_text = values[block][col]
                value_item = QTableWidgetItem(value_text)
                value_item.setTextAlignment(Qt.AlignCenter)
                apply_value_style(value_item, value_text)
                table.setItem(value_row, col, value_item)
        
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        summary_layout.addWidget(table)
        main_layout.addWidget(summary_group, 2)  # 70% 너비
        
        # === 2. SNMP Trap 로그 (오른쪽 30%) ===
        trap_group = QGroupBox("SNMP Trap 로그")
        trap_layout = QVBoxLayout(trap_group)
        
        # Trap 테이블 헤더
        self.trap_table = QTableWidget(0, 8)        
        trap_headers = ["시간", "Trap OID", "OrdinalNumber", "Alarm", "Level", "EquipID", "EquipName", "FatherEquipname"]
        self.trap_table.setHorizontalHeaderLabels(trap_headers)
        self.trap_table.verticalHeader().setVisible(False)
        self.trap_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Trap 테이블 헤더 스타일
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
            
            for col, value in enumerate(trap):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                
                # 레벨에 따른 색상
                if col == 3:  # Level 컬럼
                    if "Critical" in value:
                        item.setBackground(QColor("#FF6B6B"))
                        item.setForeground(QColor("white"))
                    elif "Major" in value:
                        item.setBackground(QColor("#FFA94D"))
                
                self.trap_table.setItem(row, col, item)
        
        self.trap_table.resizeColumnsToContents()
        trap_layout.addWidget(self.trap_table)
        
        # Clear 버튼
        clear_btn = QPushButton("로그 지우기")
        clear_btn.clicked.connect(self.clear_trap_log)
        trap_layout.addWidget(clear_btn)
        
        main_layout.addWidget(trap_group, 3)  # 30% 너비
        main_layout.addSpacing(10)
        
        return main_widget

    def clear_trap_log(self):
        """Trap 로그 테이블 초기화"""
        self.trap_table.setRowCount(0)

    def add_trap_log(self, trap_oid, trap_data):
        """SNMP Trap 수신 시 호출 - 새로운 로그 추가"""
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        row = self.trap_table.rowCount()
        self.trap_table.insertRow(row)
        
        # 데이터 매핑 (사용자가 지정한 순서대로)
        data = {
            0: current_time,
            1: trap_oid,
            2: trap_data.get("hwAlarmTrapOrdinalNumber", "-"),
            3: trap_data.get("hwAlarmLevel", "-"),
            4: trap_data.get("hwSiteName", "-"),
            5: trap_data.get("hwAcbFatherEquipname", "-")
        }
        
        for col, value in data.items():
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            # 레벨 색상 처리
            if col == 3 and value != "-":  # Level 컬럼
                if "Critical" in value or "critical" in value.lower():
                    item.setBackground(QColor("#FF6B6B"))
                    item.setForeground(QColor("white"))
                elif "Major" in value or "major" in value.lower():
                    item.setBackground(QColor("#FFA94D"))
                elif "Minor" in value or "minor" in value.lower():
                    item.setBackground(QColor("#B2F2BB"))
            
            self.trap_table.setItem(row, col, item)
        
        # 최신 로그로 스크롤
        self.trap_table.scrollToBottom()
        
        # 최대 100줄 유지
        if self.trap_table.rowCount() > 100:
            self.trap_table.removeRow(0)


    def create_module_table(self):
        group = QGroupBox("모듈 상태")
        main_layout = QHBoxLayout(group)

        headers = [
            "모듈", "모듈 전압", "셀 전압 Max/Min[V]", "셀 온도 Max/Min[℃]", "경보", "차단기", "상세"
        ]

        label_bg = QColor("#E7F1FF")
        label_font = QFont()
        label_font.setBold(True)

        def create_table(start_index):
            table = QTableWidget(5, len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.NoEditTriggers)

            for col in range(len(headers)):
                header_item = table.horizontalHeaderItem(col)
                header_item.setBackground(label_bg)
                header_item.setFont(label_font)
                header_item.setTextAlignment(Qt.AlignCenter)
            
            for row in range(5):
                module_no = start_index + row + 1

                module_item = QTableWidgetItem(f"#{module_no:02d}")
                module_item.setTextAlignment(Qt.AlignCenter)
                module_item.setBackground(label_bg)
                module_item.setFont(label_font)
                table.setItem(row, 0, module_item)

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
                    if item is not None:
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
        group = QGroupBox("고장 정보")
        layout = QVBoxLayout(group)

        faults = [
            {"module": "3", "cell": "12", "volt": "2.95", "temp": "62.0"},
            {"module": "5", "cell": "8",  "volt": "2.88", "temp": "58.3"},
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = BatteryMonitorUI()
    win.show()
    sys.exit(app.exec())
