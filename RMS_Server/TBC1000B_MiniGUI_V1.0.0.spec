# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['TBC1000B_MiniGUI_V1.0.0.py'],
    pathex=[],
    binaries=[],
    datas=[('install_battery.png', '.'), ('battery#3.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'jupyter', 'notebook', 'test', 'unittest', 'email', 'http', 'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets'],
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
    name='TBC1000B_MiniGUI_V1.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['battery#5.ico'],
)
