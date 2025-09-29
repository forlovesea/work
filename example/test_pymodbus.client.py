from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient("10.0.0.200", port=502, timeout=3)
client.connect()
read=client.read_holding_registers(address = 0x1000 ,count =3)
print(read.registers[0], read.registers[1], read.registers[2])