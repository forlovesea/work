from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import runpy
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
version = runpy.run_path(str(root / 'app_info.py'))['VERSION']
metadata = root / 'build' / 'build-info.json'
metadata.parent.mkdir(parents=True, exist_ok=True)
metadata.write_text(json.dumps({'version': version,
    'build_date': datetime.now(timezone(timedelta(hours=9))).date().isoformat()}), encoding='utf-8')
snmp_data, snmp_binaries, snmp_imports = collect_all('pysnmp')
assets = ['alarm.wav', 'install_battery.png', 'battery#3.ico', 'skt_logo.png', 'pantech.png']
a = Analysis(
    [str(root / 'frozen_entry.py')], pathex=[str(root)],
    binaries=snmp_binaries,
    datas=[(str(root / name), '.') for name in assets] + snmp_data + [(str(metadata), '.')],
    hiddenimports=['monitor'] + snmp_imports,
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'jupyter', 'notebook'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='BatteryWatch-Monitor', icon=str(root / 'battery#3.ico'),
          debug=False, strip=False, upx=False, console=False)
