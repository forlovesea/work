"""Export just the recommendation app, dependencies and clean default config."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from app_version import VERSION


def main():
    release=Path(__file__).resolve().parent/'Release'/('v'+VERSION)
    source=release/'KoreanStockBot'
    executable=source/('KoreanStockBotAdvisor_v'+VERSION+'.exe')
    required=[executable,source/'live_config.json',source/'ADVISOR_GUIDE.md']
    if not all(p.is_file() for p in required) or not (source/'_internal').is_dir():
        raise RuntimeError('Build the complete release before packaging the advisor')
    paths=required+[p for p in (source/'_internal').rglob('*') if p.is_file()]
    if any(p.suffix.lower() in ('.dpapi','.ksbkey') for p in paths):raise RuntimeError('Private credentials must not be packaged')
    target=release/('RecommendedStockTrader-v'+VERSION+'-Windows-x64.zip')
    with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=3) as archive:
        for path in paths:archive.write(path,Path('RecommendedStockTrader')/path.relative_to(source))
        archive.writestr('RecommendedStockTrader/release_manifest.json',json.dumps(dict(version=VERSION,
            executable=executable.name,sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            real_orders='Individual explicit approval required'),indent=2))
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len([n for n in archive.namelist() if n.endswith('.exe') and '/_internal/' not in n])==1
        assert not any('/advisor/' in n or '/runtime/' in n for n in archive.namelist())
    print('Advisor ZIP verified:',target)


if __name__=='__main__':main()
