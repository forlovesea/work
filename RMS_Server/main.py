import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QRadioButton, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLineEdit, QFormLayout

LABEL_BG = QColor("#E7F1FF")

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
        
class BatteryMonitorUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Battery Monitoring System (SNMP v2)")
        self.resize(1200, 850)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        main_layout.addWidget(self.create_connection_panel())        
        main_layout.addWidget(self.create_header())
        main_layout.addWidget(self.create_summary_table())
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

        # TODO:
        # 1. SNMP GET 테스트
        # 2. 응답 성공 시 상태 표시
        
    # ---------------- Header ----------------
    def create_connection_panel(self):
        group = QGroupBox("Battery System 접속 설정")
        layout = QHBoxLayout(group)

        # IP
        layout.addWidget(QLabel("IP"))
        self.ip_edit = QLineEdit("192.168.0.100")
        self.ip_edit.setFixedWidth(140)
        layout.addWidget(self.ip_edit)

        # SNMP Port
        layout.addSpacing(10)
        layout.addWidget(QLabel("Port"))
        self.port_edit = QLineEdit("161")
        self.port_edit.setFixedWidth(70)
        layout.addWidget(self.port_edit)

        # GET Community
        layout.addSpacing(20)
        layout.addWidget(QLabel("GET"))
        self.get_comm_edit = QLineEdit("public")
        self.get_comm_edit.setFixedWidth(100)
        layout.addWidget(self.get_comm_edit)

        # SET Community
        layout.addSpacing(10)
        layout.addWidget(QLabel("SET"))
        self.set_comm_edit = QLineEdit("private")
        self.set_comm_edit.setFixedWidth(100)
        layout.addWidget(self.set_comm_edit)

        # TRAP Community
        layout.addSpacing(10)
        layout.addWidget(QLabel("TRAP"))
        self.trap_comm_edit = QLineEdit("public")
        self.trap_comm_edit.setFixedWidth(100)
        layout.addWidget(self.trap_comm_edit)

        # TRAP Port (✅ 추가)
        layout.addSpacing(10)
        layout.addWidget(QLabel("TRAP Port"))
        self.trap_port_edit = QLineEdit("162")
        self.trap_port_edit.setFixedWidth(70)
        layout.addWidget(self.trap_port_edit)

        # 접속 버튼 (✅ 추가)
        layout.addSpacing(20)
        self.connect_btn = QPushButton("접속")
        self.connect_btn.setFixedWidth(80)
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        layout.addWidget(self.connect_btn)

        layout.addStretch()
        return group

    def apply_label_style(item: QTableWidgetItem):
        item.setBackground(QColor("#E7F1FF"))   # 연한 파란색
        item.setFont(QFont("", weight=QFont.Bold))
        item.setTextAlignment(Qt.AlignCenter)
        
    def create_header(self):
        group = QGroupBox()
        layout = QHBoxLayout(group)

        bmu_radio = QRadioButton("BMU#2")
        bmu_radio.setChecked(True)

        last_update = QLabel("최종갱신시간 : 2025-10-23 20:54:26.0")
        last_update.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(bmu_radio)
        layout.addStretch()
        layout.addWidget(last_update)
        return group

    # ---------------- Summary (5 columns) ----------------
    def create_summary_table(self):
        group = QGroupBox("시스템 요약 정보")
        layout = QVBoxLayout(group)

        # (라벨행 + 값행) x 4블록 = 8행, 열은 5개 고정
        table = QTableWidget(8, 5)
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)

        # ===== 데이터 정의 =====
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

        # ===== 스타일 =====
        LABEL_BG = QColor(220, 235, 255)   # 연한 파란색

        label_font = QFont()
        label_font.setBold(True)

        # ===== 테이블 채우기 =====
        for block in range(4):
            label_row = block * 2
            value_row = label_row + 1

            for col in range(5):
                # ---- 라벨 셀 ----
                label_item = QTableWidgetItem(labels[block][col])
                label_item.setTextAlignment(Qt.AlignCenter)
                label_item.setBackground(LABEL_BG)
                label_item.setFont(label_font)
                table.setItem(label_row, col, label_item)

                # ---- 값 셀 ----
                value_text = values[block][col]
                value_item = QTableWidgetItem(value_text)
                value_item.setTextAlignment(Qt.AlignCenter)
                apply_value_style(value_item, value_text)  # 상태값 색상 처리
                table.setItem(value_row, col, value_item)

        table.resizeColumnsToContents()
        table.resizeRowsToContents()

        layout.addWidget(table)
        return group

    # ---------------- Module Table ----------------
    def create_module_table(self):
        group = QGroupBox("모듈 상태")
        main_layout = QHBoxLayout(group)

        headers = [
            "모듈",
            "모듈 전압",
            "셀 전압 Max/Min[V]",
            "셀 온도 Max/Min[℃]",
            "경보",
            "차단기",
            "상세"
        ]

        # 시스템 요약 정보의 라벨 색과 동일하게 사용
        label_bg = QColor("#E7F1FF")
        label_font = QFont()
        label_font.setBold(True)

        def create_table(start_index):
            table = QTableWidget(5, len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.NoEditTriggers)

            # 🔹 헤더 셀 색/폰트 적용
            for col in range(len(headers)):
                header_item = table.horizontalHeaderItem(col)
                header_item.setBackground(label_bg)
                header_item.setFont(label_font)
                header_item.setTextAlignment(Qt.AlignCenter)
            
            for row in range(5):
                module_no = start_index + row + 1

                # ----- 항목 셀 (첫 번째 컬럼) : 설비번호 라벨과 동일 스타일 -----
                module_item = QTableWidgetItem(f"#{module_no:02d}")
                module_item.setTextAlignment(Qt.AlignCenter)
                module_item.setBackground(label_bg)
                module_item.setFont(label_font)
                table.setItem(row, 0, module_item)

                # 나머지 값 셀
                table.setItem(row, 1, QTableWidgetItem("-"))
                table.setItem(
                    row, 2,
                    QTableWidgetItem("17.00 / 16.00" if module_no <= 2 else "- / -")
                )
                table.setItem(
                    row, 3,
                    QTableWidgetItem("30.0 / 29.0" if module_no <= 2 else "- / -")
                )
                table.setItem(row, 4, QTableWidgetItem("정상"))
                table.setItem(row, 5, QTableWidgetItem("-"))

                btn = QPushButton("상세")
                table.setCellWidget(row, 6, btn)

                # 값 셀 가운데 정렬
                for col in range(1, 6):
                    item = table.item(row, col)
                    if item is not None:
                        item.setTextAlignment(Qt.AlignCenter)

            table.resizeColumnsToContents()
            table.resizeRowsToContents()
            
            # ✅ 헤더 색상 확실히 적용 (return 전에!)
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
            
            return table  # ✅ 이 부분이 빠져서 None 반환!

        left_table = create_table(0)   # 모듈 1~5
        right_table = create_table(5)  # 모듈 6~10

        main_layout.addWidget(left_table)
        main_layout.addWidget(right_table)

        return group



    # ---------------- Fault Table (항목명 셀 회색 처리) ----------------
    def create_fault_table(self):
        group = QGroupBox("고장 정보")
        layout = QVBoxLayout(group)

        faults = [
            {"module": "3", "cell": "12", "volt": "2.95", "temp": "62.0"},
            {"module": "5", "cell": "8",  "volt": "2.88", "temp": "58.3"},
        ]

        table = QTableWidget(len(faults), 5)
        table.verticalHeader().setVisible(False)

        headers = [
            "Fault",
            "고장 모듈 No",
            "고장 셀 No",
            "고장 셀 전압[V]",
            "고장 셀 온도[℃]"
        ]
        table.setHorizontalHeaderLabels(headers)

        # 🔵 헤더 = 라벨 색
        for col in range(len(headers)):
            header_item = table.horizontalHeaderItem(col)
            header_item.setBackground(QColor("#E7F1FF"))
            header_item.setFont(QFont("", weight=QFont.Bold))
            header_item.setTextAlignment(Qt.AlignCenter)

        for row, fault in enumerate(faults):
            values = [
                f"Fault#{row+1}",
                fault["module"],
                fault["cell"],
                fault["volt"],
                fault["temp"]
            ]

            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)

                # 고장은 무조건 차단 색
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