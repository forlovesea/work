# Build from project root: python -m PyInstaller windows-app/AI-Blog-Auto.spec
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / 'run_gui.py')], pathex=[str(root)],
    binaries=[], datas=[],
    hiddenimports=['keyring.backends.Windows', 'win32ctypes.pywin32', 'PIL.ImageDraw', 'apscheduler.triggers.cron'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest', 'matplotlib', 'tkinter', 'PySide6.QtWebEngineWidgets'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='AI-Blog-Auto',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    version=str(root / 'version_info.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='AI-Blog-Auto')
