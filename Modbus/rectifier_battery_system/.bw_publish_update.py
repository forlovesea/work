from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sqlite3
from urllib.parse import quote
root=Path(__file__).resolve().parent
stage=root/'.bw_publish'
target=Path(r'C:\Users\Administrator\Downloads\proj\GITHUB\work\BatteryWatch').resolve()
items=json.loads((root/'.bw_manifest.json').read_text(encoding='utf-8'))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
for item in items:
    src=(stage/item['path']).resolve(); dst=(target/item['path']).resolve()
    assert src.is_relative_to(stage.resolve()) and dst.is_relative_to(target)
    assert digest(src)==item['source'] and digest(dst)==item['previous'], 'File changed since review'
backup=target/'backups'/('pre-github-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True,exist_ok=False)
(backup/'manifest.json').write_text(json.dumps(items,indent=2),encoding='utf-8')
for item in items:
    src=target/item['path']
    if src.exists():
        saved=backup/'previous-source'/item['path']; saved.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,saved)
private=target/'monitoring-client/device-defaults.local.json'
if not private.exists(): shutil.copy2(root/'.bw_private_defaults.json',private)
for component in ('server','monitoring-client'):
    for src in (target/component).glob('*.local.json'):
        dst=backup/'local-state'/src.relative_to(target); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    for folder in ('profiles','certs','data'):
        source=target/component/folder
        if not source.is_dir(): continue
        for src in source.rglob('*'):
            if not src.is_file() or src.name.endswith(('-wal','-shm','-journal')):continue
            dst=backup/'local-state'/src.relative_to(target); dst.parent.mkdir(parents=True,exist_ok=True)
            if src.suffix=='.sqlite3':
                with sqlite3.connect('file:'+quote(src.as_posix(),safe='/:')+'?mode=ro',uri=True) as db,sqlite3.connect(dst) as out: db.backup(out)
            else: shutil.copy2(src,dst)
for item in items:
    src=stage/item['path']; dst=target/item['path']; dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
    assert digest(dst)==item['source']
print('Reproduction files updated:',len(items))
print('Private state backup:',backup/'local-state')
