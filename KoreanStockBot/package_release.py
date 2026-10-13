"""Package a clean release; refuse to redistribute private trading data."""
import hashlib
import json
import argparse
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from app_version import VERSION

parser=argparse.ArgumentParser()
parser.add_argument('--dist-path',default='Release/v'+VERSION)
root=Path(__file__).resolve().parent/parser.parse_args().dist_path
app=root/'KoreanStockBot'
for private in ('runtime','research','inputs','reports','logs','.env','STOP'):
    if (app/private).exists():raise RuntimeError('Release contains private/runtime data; use a clean build')
files=[p for p in app.rglob('*') if p.is_file()]
assert len(list(app.glob('*.exe')))==5
assert not any(p.suffix.lower() in ('.dpapi','.ksbkey') for p in files)
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in app.glob('*.exe')}
(root/'SHA256.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
manifest={'news_provider':'NAVER API HUB','news_url':'https://naverapihub.apigw.ntruss.com/search/v1/news','sha256':hashes}
manifest['version']=VERSION
(app/'release_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
target=root/('KoreanStockBot-v'+VERSION+'-Windows-x64.zip')
with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=3) as z:
    for path in app.rglob('*'):
        if path.is_file():z.write(path,path.relative_to(root))
with ZipFile(target) as z:assert z.testzip() is None
print('ZIP verified:',target)
