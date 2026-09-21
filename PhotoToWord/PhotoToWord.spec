# Build on 64-bit Windows with: python -m PyInstaller PhotoToWord.spec --noconfirm
from PyInstaller.utils.hooks.tcl_tk import tcltk_info

if not tcltk_info.available:
    raise RuntimeError(
        'Tcl/Tk is unavailable. Build from a Windows environment that can '
        'initialize tkinter; otherwise the desktop EXE will be unusable.'
    )

a = Analysis(
    ['desktop.py'], pathex=[], binaries=[], datas=[], hiddenimports=[],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['streamlit', 'pandas', 'pyarrow', 'matplotlib', 'IPython', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PhotoToWord',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='PhotoToWord')
