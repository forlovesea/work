import serial
import time

# 시리얼 포트 설정
SERIAL_PORT = 'COM13'  # Windows의 경우 'COM3', Linux/Unix는 '/dev/ttyUSB0' 등
BAUD_RATE = 115200      # 보드레이트 (예: 9600)
TIMEOUT = 0.1           # 타임아웃 (초 단위)
HEADER_SIZE =        1
HEADER_BODY_SIZE =   2

rx_count = 0
tx_count = 0
other_count = 0
rx_chk_fail = 0
chk_ver_count = 0
# 시리얼 통신 객체 생성
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)

def CDCCheckSum(data, len):    
    checksum = 0
    for byte in data[1:len+1]:
        checksum += byte

    return (checksum & 0xff);

def calculate_total_length(high_byte, low_byte):
    total_length = (high_byte << 8) | low_byte
    return total_length

def send_hex_data(data):
    """
    헥사 데이터 전송
    :param data: 전송할 헥사 데이터 (예: b'\x01\x02\x03')
    """
    ser.write(data)
    print(f"Send: {data.hex()}")

def receive_hex_data():
    """
    헥사 데이터 수신
    :return: 수신한 헥사 데이터
    """
    if ser.in_waiting > 0:
        data = ser.read(ser.in_waiting)
        print(f"Received: {data.hex()}")
        return data
    return None
"""
7e 00 02 00 00        02 0a323031
7e 00 02 40 00        42 00 00 00 00
"""

def send_normal_poll_ack():
    global rx_count, tx_count
    normal_poll_ack = bytes([0x7E, 0x00, 0x02, 0x40, 0x00, 0x42])
    #print("send_data:", normal_poll_ack.hex())
    #print("send_data:", ' '.join(f"{byte:02X}" for byte in normal_poll_ack))
    send_hex_data(normal_poll_ack)
    tx_count+=1

def send_normal_chk_version():
    global chk_ver_count
    # bytes[0], bytes[1]: length h, bytes[2]: length l, bytes[3:cmd]: ACaaS_FW_OTA_REQ 0xE6, bytes[4]: ACaaS_FOTA_VERSION_CHECK 0xF0
    #normal_poll_chk_version = bytes([0x7E, 0x00, 0x08, 0xE6, 0xF0, 0x00, 0x01, 0x07, 0x00, 0x11, 0x41, 0x42])
    #normal_poll_chk_version = bytes([0x7E, 0x00, 0x08, 0xE6, 0xF0, 0x00, 0x63, 0x07, 0x00, 0x10, 0x41, 0x00])
    #bytes 변수는 생성 후 변경이 불가함.
    normal_poll_chk_version = bytearray([0x7E, 0x00, 0x08, 0xE6, 0xF0, 0x00, 0x63, 0x07, 0x00, 0x10, 0x41, 0x00])
    normal_poll_chk_version_chs = CDCCheckSum(normal_poll_chk_version, 8+2)
    normal_poll_chk_version[11] = normal_poll_chk_version_chs
    #print("send_data:", normal_poll_ack.hex())
    #print("send_data:", ' '.join(f"{byte:02X}" for byte in normal_poll_ack))
    send_hex_data(normal_poll_chk_version)
    print(f"Send chk_version Hex Data: {normal_poll_chk_version.hex()}")
    chk_ver_count+=1
    
def main():    
    global rx_count, tx_count, other_count, rx_chk_fail
    global chk_ver_count
    
    try:
        while True:
            # 송신 예시            
            #send_hex_data(b'\x7E\x00\x02\x00\x00\x02')  # 헥사 데이터 송신\
            # 수신 예시
            received_data = receive_hex_data()            
            if received_data is not None:                
                if received_data[0] == 0x7e:
                    received_len = calculate_total_length(received_data[1], received_data[2])
                    print("Received_len:", received_len)
                    chs = CDCCheckSum(received_data, received_len+2)
                    print(f"Received Hex Data: {received_data.hex()} checksum:hex({chs:#04x})")
                    if chs == received_data[HEADER_SIZE+HEADER_BODY_SIZE+received_len]:
                        print("checksum ok")
                        rx_count+=1
                        
                        if rx_count % 10 == 0:
                            send_normal_chk_version()
                        else:
                            send_normal_poll_ack()
                        
                        #send_hex_data(b'\x7E\x00\x02\x00\x00\x02')
                    else:
                        print("checksum fail")
                        rx_chk_fail += 1
                        #input("Enter 키를 누르면 계속 진행됩니다...")
                else:
                    other_count+=1
                    print(f"Wrong First byte:[{hex(received_data[0])}]")                    
                    if isinstance(received_data, str):
                        print("Data is a string:", received_data)
                    #input("Enter 키를 누르면 계속 진행됩니다...")
            time.sleep(0.2)  # 반복 주기 (1초)
            print("Rx Count: ", rx_count, " Tx Count: ", tx_count, "Rx chk fail: ", rx_chk_fail, "Other Count: ", other_count, "Check version: ", chk_ver_count)

    except KeyboardInterrupt:
        print("Program interrupted. Closing serial connection...")
    finally:
        ser.close()

if __name__ == "__main__":
    main()