# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Administrator\\Downloads\\proj\\GITHUB\\work\\RMS_Server\\TBC1000B_감시프로그램_V3.2.7.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Administrator\\Downloads\\proj\\GITHUB\\work\\RMS_Server\\alarm.wav', '.'), ('C:\\Users\\Administrator\\Downloads\\proj\\GITHUB\\work\\RMS_Server\\install_battery.png', '.'), ('C:\\Users\\Administrator\\Downloads\\proj\\GITHUB\\work\\RMS_Server\\battery#3.ico', '.'), ('C:\\Users\\Administrator\\Downloads\\proj\\GITHUB\\work\\RMS_Server\\skt_logo.png', '.'), ('C:\\Users\\Administrator\\Downloads\\proj\\GITHUB\\work\\RMS_Server\\pantech.png', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TBC1000B_Monitor_v3.2.8',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Administrator\\Downloads\\proj\\GITHUB\\work\\RMS_Server\\battery#2.ico'],
)
