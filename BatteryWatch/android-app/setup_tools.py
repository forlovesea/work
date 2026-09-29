"""Download isolated build tools; leaves system Java and PATH unchanged."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent/'.toolchain'
ROOT.mkdir(exist_ok=True)

def download(url,path,digest):
    if not path.exists():
        urllib.request.urlretrieve(url,path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise ValueError('Checksum mismatch: '+str(path))

def jdk():
    url='https://aka.ms/download-jdk/microsoft-jdk-17.0.20.1-windows-x64.zip'
    with urllib.request.urlopen(url+'.sha256sum.txt',timeout=30) as r:
        checksum=r.read().decode().split()[0]
    archive=ROOT/'jdk.zip'; download(url,archive,checksum)
    with zipfile.ZipFile(archive) as z: z.extractall(ROOT/'java')
    print('JDK ready',flush=True)

def gradle():
    url='https://services.gradle.org/distributions/gradle-8.11.1-bin.zip'
    with urllib.request.urlopen(url+'.sha256') as r: checksum=r.read().decode().strip()
    archive=ROOT/'gradle.zip'; download(url,archive,checksum)
    with zipfile.ZipFile(archive) as z: z.extractall(ROOT)
    print('Gradle ready',flush=True)

def sdk():
    archive=ROOT/'sdk-tools.zip'
    download('https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip',archive,
             '90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a')
    with zipfile.ZipFile(archive) as z: z.extractall(ROOT/'sdk-stage')
    target=ROOT/'sdk'/'cmdline-tools'/'latest'
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists(): (ROOT/'sdk-stage'/'cmdline-tools').rename(target)
    print('SDK command tools ready',flush=True)

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda f:f(),[jdk,gradle,sdk]): pass
