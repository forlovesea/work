"""Choose an unused release version and generate Windows version metadata."""
from pathlib import Path
import runpy

root=Path(__file__).resolve().parent
version=runpy.run_path(str(root/'app_version.py'))['VERSION']
major,minor,patch=map(int,version.split('.'))
while (root/'Release'/f'v{major}.{minor}.{patch}').exists(): patch+=1
version=f'{major}.{minor}.{patch}'
(root/'app_version.py').write_text(f"VERSION = '{version}'\n",encoding='utf-8')
target=root/'build'/'version_info.txt'
target.parent.mkdir(exist_ok=True)
target.write_text(f'''VSVersionInfo(
 ffi=FixedFileInfo(filevers=({major},{minor},{patch},0),prodvers=({major},{minor},{patch},0),
 mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),
 kids=[StringFileInfo([StringTable('040904B0',[
 StringStruct('FileDescription','KoreanStockBot v{version}'),
 StringStruct('FileVersion','{version}'),StringStruct('ProductName','KoreanStockBot'),
 StringStruct('ProductVersion','{version}')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])
''',encoding='utf-8')
print(version)
