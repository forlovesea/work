import sys
import serial.tools.list_ports
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QGridLayout, QSpinBox,
    QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from pymodbus.client import ModbusSerialClient

# ---------------------------
# 알람 레지스터 정의
# ---------------------------

# 고정(Static) 레지스터 매핑 (이미지/시트에서 직접 명시된 항목들)
ALARM_STATIC = {
    "DC Overvoltage": 0x500E,
    "DC Undervoltage": 0x500F,
    "Load Fuse Break": 0x5010,
    "Door Alarm": 0x5011,
    "Water Alarm": 0x5012,
    "Smoke Alarm": 0x5013,
    "High Equipment Area Temperature": 0x5014,
    "Equipment Area Temperature Sensor Fault": 0x5015,
    "Ambient Humidity Sensor Fault": 0x5016,
    "LLVD1 Warning": 0x5017,
    "LLVD1 Disconnected": 0x5018,
    "LLVD2 Warning": 0x5019,
    "LLVD2 Disconnected": 0x501A,
    "DC Ultra High Voltage": 0x501B,
    "DC Ultra Low Voltage": 0x501C,
    "Controller Hardware Fault": 0x501D,
    "Battery Test Failure": 0x501E,
    "LVD Disabled": 0x501F,
    "Low Rectifier Remaining Capacity": 0x5020,
    "Battery Discharge": 0x5021,
    "Battery Missing": 0x5022,
    # DI1~DI12 will be generated separately (0x5023~0x502E)
    "Urgent Alarm (CELLNEX)": 0x502F,
    "Non-urgent Alarm (CELLNEX)": 0x5030,
    "Fuse Broken Alarm (CELLNEX)": 0x5031,
    "LLVD3 Warning": 0x5032,
    "LLVD3 Disconnected": 0x5033,
    "LLVD4 Warning": 0x5034,
    "LLVD4 Disconnected": 0x5035,
    # Lithium Battery N Abnormal base (N:1..32) => 0x5036 + (N-1)
    # Battery High Temperature and subsequent
    "Battery High Temperature": 0x5500,
    "Battery Temperature Sensor 1 Fault": 0x5501,
    "BLVD Disconnected": 0x5502,
    "BLVD Warning": 0x5503,
    "Battery Forcibly Connection": 0x5504,
    "Battery Low Temperature": 0x5505,
    "Battery Fuse Blown": 0x5506,
    "Battery Contactor Fault": 0x5507,
    "Battery Reversely Connection": 0x5508,
    # Battery N Fuse Break / Middle Voltage Imbalance per N bank (1..6) pattern handled separately
    # Return Air / Outdoor sensor faults
    "Return Air Temperature Sensor 1 Fault": 0x5700,
    "Outdoor Ambient Temperature Sensor Fault": 0x5701,
    "High Battery Area Temperature": 0x576A,
    "Battery Area Temperature Sensor Fault": 0x576B,
    "Battery 2 High Temperature": 0x576C,
    "Battery Temperature Sensor 2 Fault": 0x576D,
    "Return Air Temperature Sensor 2 Fault": 0x576E,
    "Door Alarm (Battery Area)": 0x576F,
    "Battery Cabinet Communication Failure": 0x5772,
    # SSU/PV patterns handled programmatically (0x5900 and ranges)
    "SSU Lost": 0x5900,
    # Charge/temperature/battery protection area pattern registers start at 0x8431 etc - handled programmatically
    # ... 필요하면 더 추가
}

# ---------------------------
# 패턴 기반 레지스터 생성 함수들
# ---------------------------

def generate_di_registers():
    """DI1 ~ DI12 : 0x5023 ~ 0x502E"""
    regs = {}
    base = 0x5023
    for i in range(1, 13):
        regs[f"DI{i}"] = base + (i - 1)
    return regs

def generate_lithium_battery_regs():
    """
    Lithium Battery N Abnormal:
      base = 0x5036 + (N-1)
      value meanings:
        0x00 normal
        0x01 Fault
        0x02 Protection
        0x03 Communication Fail
    for N in 1..32
    """
    regs = {}
    base = 0x5036
    for n in range(1, 33):
        addr = base + (n - 1)
        regs[f"Lithium Battery {n} Abnormal"] = addr
    return regs

def generate_battery_bank_regs():
    """
    Battery N Fuse Break / Middle Voltage Imbalance pattern:
      base = 0x5520 + (N-1)*16
      0 -> Fuse Break
      1 -> Middle Voltage Imbalance
    N = 1..6
    """
    regs = {}
    base = 0x5520
    for n in range(1, 7):
        group_base = base + (n - 1) * 16
        regs[f"Battery Bank {n} Fuse Break"] = group_base + 0   # 0x5520+(N-1)*16
        regs[f"Battery Bank {n} Middle Voltage Imbalance"] = group_base + 1  # 0x5521+(N-1)*16
    return regs

def generate_ssu_pv_regs(max_units=60):
    """
    SSU1..N Fault: 0x5901 + (N-1)*16
    SSU1..N Communication Failure: 0x5902 + (N-1)*16
    PV1..N Array Fault: 0x5903 + (N-1)*16
    SSU Protection: 0x5904 + (N-1)*16
    Creates entries up to max_units (default 60)
    """
    regs = {}
    base = 0x5901
    for n in range(1, max_units + 1):
        block = 0x5900 + (n - 1) * 16
        regs[f"SSU{n} Fault"] = block + 1  # 0x5901+(n-1)*16
        regs[f"SSU{n} Communication Failure"] = block + 2
        regs[f"PV{n} Array Fault"] = block + 3
        regs[f"SSU{n} Protection"] = block + 4
    return regs

# ---------------------------
# Rectifier / Cabinet helper (사용자 필요시 호출)
# ---------------------------

def get_rectifier_register(rectifier_cabinet_n, rectifier_m):
    """
    Rectifier M# in rectifier cabinet N:
      addr = 0x7000 + (N-1)*60 + (M-1)
      M range 1..60, N range 1..8
      return addr
    (Value mapping: 0x00 normal, 0x01 fault, 0x02 protection, 0x03 comm failure, 0x04 power failure, 0x05 overvoltage)
    """
    return 0x7000 + (rectifier_cabinet_n - 1) * 60 + (rectifier_m - 1)

def get_combined_rectifier_register(combined_cabinet_n, rectifier_m):
    """
    Rectifier in combined cabinet:
      base 0x71F0 + (N-1)*60 + (M-1)
    """
    return 0x71F0 + (combined_cabinet_n - 1) * 60 + (rectifier_m - 1)

# ---------------------------
# 최종 ALARM 레지스터 맵 (정적 + 생성)
# ---------------------------

ALARM_REGISTERS = {}
ALARM_REGISTERS.update(ALARM_STATIC)
ALARM_REGISTERS.update(generate_di_registers())
ALARM_REGISTERS.update(generate_lithium_battery_regs())
ALARM_REGISTERS.update(generate_battery_bank_regs())
ALARM_REGISTERS.update(generate_ssu_pv_regs(max_units=10))  # 기본 10개만 생성. 필요시 60으로 늘리세요.

# 필요시 콘솔에 몇 개 등록되었는지 확인
# print(f"Total alarm entries: {len(ALARM_REGISTERS)}")

# ---------------------------
# Modbus GUI 클래스
# ---------------------------

class ModbusGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modbus RTU GUI with Alarms")
        self.resize(900, 650)
        self.client = None
        self.monitor_timer = QTimer()
        self.monitor_timer.setInterval(5000)  # default 5s
        self.monitor_timer.timeout.connect(self.read_alarms)

        # UI 구성
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Top: port & baud
        port_layout = QHBoxLayout()
        layout.addLayout(port_layout)
        port_layout.addWidget(QLabel("COM Port:"))
        self.combo_port = QComboBox()
        port_layout.addWidget(self.combo_port)
        port_layout.addWidget(QLabel("Baudrate:"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        port_layout.addWidget(self.combo_baud)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_modbus)
        port_layout.addWidget(self.btn_connect)
        
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self.disconnect_modbus)
        self.btn_disconnect.setEnabled(False)  # 초기에는 비활성화
        port_layout.addWidget(self.btn_disconnect)
        
        port_layout.addStretch()
        port_layout.addWidget(QLabel("Monitor Interval (s):"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 60)
        self.spin_interval.setValue(5)
        self.spin_interval.valueChanged.connect(self.update_monitor_interval)
        port_layout.addWidget(self.spin_interval)

        # middle: existing read buttons
        grid = QGridLayout()
        layout.addLayout(grid)
        # original registers (kept as example)
        self.btn_vdc = QPushButton("Read DC Voltage")
        self.btn_vdc.clicked.connect(lambda: self.read_single(0x1000, self.btn_vdc, "System DC Voltage", scale=0.1))
        grid.addWidget(self.btn_vdc, 0, 0)
        self.btn_iload = QPushButton("Read DC Load Current")
        self.btn_iload.clicked.connect(lambda: self.read_single(0x1001, self.btn_iload, "Total DC Load Current", scale=0.1))
        grid.addWidget(self.btn_iload, 0, 1)
        self.btn_acf = QPushButton("Read AC Frequency")
        self.btn_acf.clicked.connect(lambda: self.read_single(0x100C, self.btn_acf, "AC Frequency"))
        grid.addWidget(self.btn_acf, 1, 0)
        self.btn_ibatt = QPushButton("Read Battery Current")
        self.btn_ibatt.clicked.connect(lambda: self.read_single(0x1401, self.btn_ibatt, "Total Battery Current", signed=True, scale=0.1))
        grid.addWidget(self.btn_ibatt, 1, 1)
        self.btn_soc = QPushButton("Read SOC")
        self.btn_soc.clicked.connect(lambda: self.read_single(0xA739, self.btn_soc, "Battery SOC"))
        grid.addWidget(self.btn_soc, 2, 0)

        # Alarm control buttons
        alarm_layout = QHBoxLayout()
        layout.addLayout(alarm_layout)
        self.btn_read_alarms = QPushButton(f"Read Alarms ({len(ALARM_REGISTERS)})")
        self.btn_read_alarms.clicked.connect(self.read_alarms)
        alarm_layout.addWidget(self.btn_read_alarms)

        self.btn_monitor = QPushButton("Start Monitor")
        self.btn_monitor.setCheckable(True)
        self.btn_monitor.clicked.connect(self.toggle_monitor)
        alarm_layout.addWidget(self.btn_monitor)

        alarm_layout.addStretch()

        # 로그
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        # 포트 목록 초기화
        self.populate_ports()
        self.update_buttons(False)

    def populate_ports(self):
        ports = serial.tools.list_ports.comports()
        self.combo_port.clear()
        for p in ports:
            self.combo_port.addItem(p.device)

    def log_message(self, msg):
        self.log.append(msg)

    def update_buttons(self, enabled):
        self.btn_vdc.setEnabled(enabled)
        self.btn_iload.setEnabled(enabled)
        self.btn_acf.setEnabled(enabled)
        self.btn_ibatt.setEnabled(enabled)
        self.btn_soc.setEnabled(enabled)
        self.btn_read_alarms.setEnabled(enabled)
        self.btn_monitor.setEnabled(enabled)

    def connect_modbus(self):
        port = self.combo_port.currentText()
        if not port:
            self.log_message("❌ No COM port selected")
            QMessageBox.warning(self, "Connection Error", "❌ COM 포트를 선택하세요.")
            return
        baud = int(self.combo_baud.currentText())
        try:
            self.client = ModbusSerialClient(
                port=port,
                baudrate=baud,
                stopbits=1,
                bytesize=8,
                parity='N',
                timeout=1
            )
            
            if self.client.connect():
                self.log_message(f"✅ Connected to {port} @ {baud}bps")
                QMessageBox.information(self, "Connection Success", f"✅ {port} 연결 성공 ({baud}bps)")
                self.update_buttons(True)
                self.btn_connect.setEnabled(False)
            else:
                self.log_message(f"❌ Failed to connect to {port}")
                QMessageBox.critical(self, "Connection Failed", f"❌ {port} 연결 실패\n원인: 장치 응답 없음")
        except Exception as e:
            self.log_message(f"❌ Exception during connection: {e}")
            QMessageBox.critical(self, "Connection Error", f"❌ 연결 중 오류 발생\n원인: {str(e)}")

    def disconnect_modbus(self):
        if self.client:
            try:
                self.client.close()
                self.client = None
                self.log_message("✅ Modbus disconnected")
                QMessageBox.information(self, "Disconnected", "✅ Modbus 연결 해제 완료")
            except Exception as e:
                self.log_message(f"❌ Exception during disconnect: {e}")
                QMessageBox.critical(self, "Disconnect Error", f"❌ 연결 해제 중 오류 발생\n원인: {str(e)}")
        else:
            self.log_message("⚠ Not connected")
            QMessageBox.warning(self, "Disconnect", "⚠ 연결 상태가 아닙니다.")

        self.update_buttons(False)
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)  # ✅ Disconnect 버튼 비활성화
    
    
    def read_register(self, address, count=1, slave=1, signed=False, scale=1):
        """
        단일(또는 연속) 홀딩 레지스터 읽기
        (pymodbus의 read_holding_registers 사용)
        """
        if not self.client:
            self.log_message("❌ Not connected")
            return None
        try:
            rr = self.client.read_holding_registers(address=address, count=count, device_id=slave)
            self.log_message(f"TX: Read 0x{address:04X} Count={count} Slave={slave}")
            if rr is None:
                self.log_message(f"❌ No response for 0x{address:04X}")
                return None
            if hasattr(rr, "isError") and rr.isError():
                self.log_message(f"❌ Read error at 0x{address:04X}")
                return None
            # pymodbus 응답 형식: registers 리스트
            val = rr.registers[0] if hasattr(rr, "registers") and rr.registers else None
            if val is None:
                self.log_message(f"❌ Empty value at 0x{address:04X}")
                return None
            self.log_message(f"RX: 0x{val:04X} ({val})")
            if signed and val > 0x7FFF:
                val -= 0x10000
            return val * scale
        except Exception as e:
            self.log_message(f"❌ Modbus Exception while reading 0x{address:04X}: {e}")
            return None

    def read_single(self, address, button, name, signed=False, scale=1):
        button.setStyleSheet("background-color: lightgreen")
        QApplication.processEvents()
        val = self.read_register(address, signed=signed, scale=scale)
        if val is not None:
            self.log_message(f"{name}: {val}")
        button.setStyleSheet("")

    def read_alarms(self):
        """
        전체 알람 읽기: ALARM_REGISTERS의 모든 항목을 순회
        - 값이 0이 아니면 'ALARM'으로 간주 (시트 대부분은 0x00 normal, 0x01 alarm)
        - Lithium Battery 같은 멀티값 항목(0x01: Fault, 0x02: Protection 등)은 숫자를 그대로 보여줍니다.
        """
        if not self.client:
            self.log_message("❌ Not connected - cannot read alarms")
            return

        self.log_message("=== Reading Alarms ===")
        alarm_found = False
        # 정렬된 주소 순으로 읽으면 읽기 패턴 예측에 유리
        items = sorted(ALARM_REGISTERS.items(), key=lambda kv: kv[1])
        for name, addr in items:
            val = self.read_register(addr)
            if val is None:
                # 통신 실패 또는 값 없음
                continue
            # 대부분 항목은 0=normal, 1=alarm (예외: lithium battery, rectifier 등)
            # 간단 규칙: val == 0 -> normal, val != 0 -> alarm (추가 세부 처리 가능)
            if isinstance(val, (int, float)) and int(val) != 0:
                self.log_message(f"ALARM -> {name} @0x{addr:04X} : 0x{int(val):02X}")
                alarm_found = True
            else:
                self.log_message(f"Normal -> {name} @0x{addr:04X}")

        # 버튼 색상으로 표시 (한 번이라도 알람이면 빨강)
        if alarm_found:
            self.btn_read_alarms.setStyleSheet("background-color: salmon")
        else:
            self.btn_read_alarms.setStyleSheet("background-color: lightgreen")

        self.log_message("=== Alarms Read Complete ===")

    def toggle_monitor(self, checked):
        if checked:
            # 시작
            interval_s = self.spin_interval.value()
            self.monitor_timer.setInterval(interval_s * 1000)
            self.monitor_timer.start()
            self.btn_monitor.setText("Stop Monitor")
            self.log_message(f"🔁 Alarm monitor started (interval {interval_s}s)")
        else:
            self.monitor_timer.stop()
            self.btn_monitor.setText("Start Monitor")
            self.log_message("⏸ Alarm monitor stopped")

    def update_monitor_interval(self, val):
        if self.monitor_timer.isActive():
            self.monitor_timer.setInterval(val * 1000)
            self.log_message(f"Monitor interval updated to {val}s")

# ---------------------------
# 실행부
# ---------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ModbusGUI()
    gui.show()
    sys.exit(app.exec())