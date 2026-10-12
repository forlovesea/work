# Shared one-folder distribution. Never collect runtime, keys or user caches.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import runpy
version=runpy.run_path('app_version.py')['VERSION']

a=Analysis(['release_entry.py'],pathex=[],
    binaries=[],datas=collect_data_files('pykrx')+[('assets/stock_chart.ico','assets'),('assets/stock_chart.png','assets')],
    hiddenimports=collect_submodules('pykrx'),
    hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[])
pyz=PYZ(a.pure)
executables=[]
for name,console in [('KoreanStockBotETF',False),('KoreanStockBotStock',False),
                     ('KoreanStockBotPaper',False),('trader',True),('research',True)]:
    output_name=name if console else name+'_v'+version
    executables.append(EXE(pyz,a.scripts,[],exclude_binaries=True,name=output_name,version='build/version_info.txt',
        debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=console,icon='assets/stock_chart.ico'))
coll=COLLECT(*executables,a.binaries,a.datas,strip=False,upx=False,name='KoreanStockBot')
