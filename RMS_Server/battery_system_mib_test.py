import subprocess
import time

def update_battery_data():
    while True:
        # 여기에 당신의 BMS Python/CAN 코드 삽입
        volt = 523 + int(time.time() % 10)  # 시뮬레이션
        curr = -125 + int(time.time() % 5)
        
        # snmpsim 데이터 업데이트
        subprocess.run([
            "snmpsim-data-fold", 
            "--data-dir=D:\proj\GIT_HUB\work\RMS_Server",
            f"--oid=.1.3.6.1.4.1.2011.6.164.1.17.1.1.5.1",
            f"--set-value={volt}"
        ])
        time.sleep(5)

update_battery_data()
