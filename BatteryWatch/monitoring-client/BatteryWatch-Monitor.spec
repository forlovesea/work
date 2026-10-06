from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
snmp_data, snmp_binaries, snmp_imports = collect_all('pysnmp')
assets = ['alarm.wav', 'install_battery.png', 'battery#3.ico', 'skt_logo.png', 'pantech.png']
a = Analysis(
    [str(root / 'frozen_entry.py')], pathex=[str(root)],
    binaries=snmp_binaries,
    datas=[(str(root / name), '.') for name in assets] + snmp_data,
    hiddenimports=['monitor'] + snmp_imports,
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'jupyter', 'notebook'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='BatteryWatch-Monitor', icon=str(root / 'battery#3.ico'),
          debug=False, strip=False, upx=False, console=False)
