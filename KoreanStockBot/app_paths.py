"""One shared, writable application directory in source and frozen builds."""
import sys
from pathlib import Path

ROOT=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent


def worker_command(name,root=ROOT):
    root=Path(root)
    if getattr(sys,'frozen',False):
        return [str(root/('trader.exe' if name=='live' else 'research.exe'))]
    python=root/'.venv'/'Scripts'/'python.exe'
    return [str(python) if python.exists() else sys.executable,'-u','-X','utf8',str(root/(name+'.py'))]
