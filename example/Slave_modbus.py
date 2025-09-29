import sys
import csv
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QMessageBox, QInputDialog
)
from PySide6.QtCore import QTimer
from pymodbus.client import ModbusTcpClient  # 최신 버전 pymodbus에 맞게 수정


THRESHOLD_TEMP = 45.0

class BMSMonitor(QWidget):
    def __init__(self, ip_address):
        super().__init__()
        self.client = ModbusTcpClient(ip_address, port=502)
        if not self.client.connect():
            QMessageBox.critical(self, "연결 실패", f"UPS({ip_address})에 연결할 수 없습니다.")
            sys.exit(1)
        self.ip_address = ip_address
        self.init_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.read_bms)
        self.timer.start(1000)  # 5초 간격

    def init_ui(self):
        self.setWindowTitle(f"UPS 모니터({self.ip_address})")
        layout = QVBoxLayout()

        self.label_voltage = QLabel("전압: --- V")
        self.label_current = QLabel("전류: --- A")
        self.label_temp = QLabel("온도: --- °C")
        self.label_alarm = QLabel("알람 상태: ---")

        layout.addWidget(self.label_voltage)
        layout.addWidget(self.label_current)
        layout.addWidget(self.label_temp)
        layout.addWidget(self.label_alarm)

        self.setLayout(layout)
        self.resize(300, 200)

    def read_bms(self):
        try:
            result = self.client.read_holding_registers(address = 0x1000 ,count =3)            
            if result.isError():
                raise Exception("통신 오류")
            
            print(result.registers[0], result.registers[1], result.registers[2])
            
            voltage = result.registers[0] / 1000.0
            current = result.registers[1] / 1000.0
            temperature = result.registers[2] / 10.0

            self.label_voltage.setText(f"전압: {voltage:.2f} V")
            self.label_current.setText(f"전류: {current:.2f} A")
            self.label_temp.setText(f"온도: {temperature:.1f} °C")

            self.log_to_csv(voltage, current, temperature)

            alarm_result = self.client.read_holding_registers(address = 0x5000, count = 1)
            alarm_code = alarm_result.registers[0] if not alarm_result.isError() else -1

            if alarm_code != 0 or temperature > THRESHOLD_TEMP:
                self.label_alarm.setText(f"알람 상태: 경고 발생!")
                self.show_alarm_popup(alarm_code, temperature)
            else:
                self.label_alarm.setText("알람 상태: 정상")
        except Exception as e:
            self.label_alarm.setText("통신 실패!")
            print(f"오류: {e}")

    def log_to_csv(self, voltage, current, temperature):
        with open("bms_log.csv", mode="a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now(), voltage, current, temperature])

    def show_alarm_popup(self, code, temp):
        msg = QMessageBox(self)
        msg.setWindowTitle(" UPS 알람")
        msg.setText(f"알람 코드: {code}, 온도: {temp:.1f} °C")
        msg.setIcon(QMessageBox.Warning)
        msg.exec()

    def closeEvent(self, event):
        self.client.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    ip, ok = QInputDialog.getText(None, "UPS IP 입력", "UPS 장비의 IP 주소를 입력하세요:")
    if not ok or not ip:
        sys.exit(0)

    monitor = BMSMonitor(ip)
    monitor.show()
    sys.exit(app.exec())
    