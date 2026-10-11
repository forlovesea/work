"""Optional current-Windows-user DPAPI storage. Never store plain-text secrets."""
import ctypes
import json
import os
from pathlib import Path
from ctypes import wintypes
from live import ROOT, SafetyStop

KEYS=('TOSS_CLIENT_ID','TOSS_CLIENT_SECRET','TOSS_ACCOUNT_SEQ',
      'KRX_ID','KRX_PW','DART_API_KEY','NAVER_CLIENT_ID','NAVER_CLIENT_SECRET')
DEFAULT_PATH=ROOT/'runtime'/'credentials.dpapi'


class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def crypt(data,decrypt=False):
    if os.name!='nt': raise SafetyStop('Encrypted storage requires Windows; use environment variables on other OSes')
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    output=Blob()
    library=ctypes.WinDLL('crypt32',use_last_error=True)
    function=library.CryptUnprotectData if decrypt else library.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,
                       ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):
        raise SafetyStop('Windows credential encryption/decryption failed')
    try: return ctypes.string_at(output.data,output.size)
    finally:
        free=ctypes.WinDLL('kernel32').LocalFree
        free.argtypes=[ctypes.c_void_p]; free.restype=ctypes.c_void_p
        free(output.data)


def save_credentials(values,path=DEFAULT_PATH):
    values={k:v for k,v in values.items() if k in KEYS and isinstance(v,str) and v}
    payload=crypt(json.dumps(values).encode('utf-8'))
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    with tmp.open('wb') as f:
        f.write(payload); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)


def load_credentials(path=DEFAULT_PATH):
    path=Path(path)
    if not path.exists(): return {}
    values=json.loads(crypt(path.read_bytes(),decrypt=True))
    if not isinstance(values,dict) or any(k not in KEYS or not isinstance(v,str) for k,v in values.items()):
        raise SafetyStop('Invalid encrypted credential record')
    return values


def load_environment():
    for key,value in load_credentials().items():
        os.environ.setdefault(key,value)
