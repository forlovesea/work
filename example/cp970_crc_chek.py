import struct

CRC_TABLE_SIZE = 256

def make_crc_table(id):
    table = []
    for i in range(CRC_TABLE_SIZE):
        k = i
        for j in range(8):
            if k & 1: 
                k = (k >> 1) ^ id
            else:
                k >>= 1
        table.append(k)
    return table

def calc_crc(mem, size, crc, table):
    crc = ~crc
    for i in range(size):
        crc = table[(crc ^ mem[i]) & 0xFF] ^ (crc >> 8)
    return ~crc & 0xFFFFFFFF

def ee_get_file_crc(file_name):
    buf_size = 32768
    crc_table = make_crc_table(0xEDB88320)
    crc = 0

    try:
        with open(file_name, 'rb') as f:
            while (chunk := f.read(buf_size)):
                crc = calc_crc(chunk, len(chunk), crc, crc_table)
    except FileNotFoundError:
        print(f"{file_name} open fail")
        return None

    print(f"{file_name} CRC: {crc:08x}")
    return crc

def fn_compare_file_crc(dev_code, total_crc, file_name):
    file_crc = ee_get_file_crc(file_name)
    if file_crc is not None:
        print(f"read crc: {file_crc:08x}   receive crc: {total_crc:08x}")
        if file_crc != total_crc:
            print("File CRC Fail")
            return False
        else:
            print("File CRC OK")
            return True
    return False

# Example usage
# Replace these variables with appropriate values for your case
modem_fota_db = {
    "dev_code": "PACKAGE_T_CP970",
    "total_crc": 0xDEADBEEF,
    "main_filename": "C:/Users/sktsuser/Downloads/CP-970_1_1_7_2501020.dat"
}

#file_path = f"/root/{modem_fota_db['main_filename']}.dat"
file_path ="C:/Users/sktsuser/Downloads/CP-970_1_1_7_2501020.dat"
fn_compare_file_crc(modem_fota_db["dev_code"], modem_fota_db["total_crc"], modem_fota_db["main_filename"])
