from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

# RS485 (Modbus RTU) 설정
client = ModbusSerialClient(
    port="COM13",        # 윈도우 장치 관리자에서 확인
    baudrate=9600,       # 장비 매뉴얼에 맞게 변경
    stopbits=1,
    bytesize=8,
    parity='N',
    timeout=1
)

# 주요 레지스터 주소 (예시)
REG_SYSTEM_DC_VOLTAGE   = 0x1000  # UINT16, V, 0.1 단위
REG_TOTAL_DC_LOAD_CURR  = 0x1001  # UINT16, A, 0.1 단위
REG_AC_FREQ             = 0x100C  # UINT16, Hz
REG_BATT_STATUS         = 0x1400  # UINT16, 상태 코드
REG_TOTAL_BATT_CURRENT  = 0x1401  # INT16, A, 0.1 단위
REG_BATT_SOC            = 0xA739  # UINT16, %

def read_register(address, count=1, slave=1, signed=False):
    try:
        rr = client.read_holding_registers(address=address, count=count, device_id=slave)
        if rr.isError():
            print(f"❌ Read error at 0x{address:04X}")
            return None
        val = rr.registers[0]
        if signed and val > 0x7FFF:
            val -= 0x10000
        return val
    except ModbusException as e:
        print(f"❌ Modbus Exception: {e}")
        return None

def read_battery_info():
    if not client.connect():
        print("❌ RTU 연결 실패 (포트/통신속도 확인)")
        return

    try:
        vdc = read_register(REG_SYSTEM_DC_VOLTAGE)
        if vdc is not None:
            print(f"System DC Voltage : {vdc/10:.1f} V")

        iload = read_register(REG_TOTAL_DC_LOAD_CURR)
        if iload is not None:
            print(f"Total DC Load Current : {iload/10:.1f} A")

        f_ac = read_register(REG_AC_FREQ)
        if f_ac is not None:
            print(f"AC Frequency : {f_ac} Hz")

        batt_status = read_register(REG_BATT_STATUS)
        if batt_status is not None:
            status_map = {
                0: "Float Charging",
                1: "Equalized Charging",
                2: "Discharging",
                3: "Hibernation"
            }
            print(f"Battery Status : {status_map.get(batt_status, 'Unknown')}")

        ibatt = read_register(REG_TOTAL_BATT_CURRENT, signed=True)
        if ibatt is not None:
            print(f"Total Battery Current : {ibatt/10:.1f} A")

        soc = read_register(REG_BATT_SOC)
        if soc is not None:
            print(f"Battery SOC : {soc} %")

    finally:
        client.close()

if __name__ == "__main__":
    read_battery_info()