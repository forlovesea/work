import chardet

with open("D:/proj/bms_log.xls", 'rb') as f:
    result = chardet.detect(f.read(10))
    print(result)