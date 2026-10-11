"""Local settings template and current-user DPAPI encrypted exchange files."""
import json
import os
import re
import tempfile
from pathlib import Path
from credentials import KEYS, crypt

MAGIC=b'KSBSET1\0'
LIMIT=65536


def validate(data):
    if not isinstance(data,dict) or set(data)!={'format','version','credentials','symbol'}:
        raise ValueError('Invalid settings template')
    if data['format']!='KoreanStockBot' or type(data['version']) is not int or data['version']!=1:
        raise ValueError('Unsupported settings template')
    values=data['credentials']
    if not isinstance(values,dict) or set(values)-set(KEYS) or any(not isinstance(v,str) for v in values.values()):
        raise ValueError('Invalid credentials')
    values={k:v.strip() for k,v in values.items()}
    if not isinstance(data['symbol'],str): raise ValueError('Invalid symbol')
    symbol=data['symbol'].strip().upper()
    if symbol and not re.fullmatch('[0-9A-Z]{6}',symbol): raise ValueError('Invalid symbol')
    if values.get('TOSS_ACCOUNT_SEQ') and not values['TOSS_ACCOUNT_SEQ'].isdigit():
        raise ValueError('Invalid account selector')
    return dict(format='KoreanStockBot',version=1,credentials=values,symbol=symbol)


def atomic_write(path,payload):
    path=Path(path)
    fd,tmp=tempfile.mkstemp(prefix='.ksb-settings-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def create_template(path):
    # Always blank: never export saved secrets into the plaintext template.
    data=dict(format='KoreanStockBot',version=1,credentials={k:'' for k in KEYS},symbol='')
    atomic_write(path,(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


def read_small(path):
    with Path(path).open('rb') as f: payload=f.read(LIMIT+1)
    if len(payload)>LIMIT: raise ValueError('Settings file too large')
    return payload


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('Duplicate settings key')
        result[key]=value
    return result


def parse(payload):
    return validate(json.loads(payload.decode('utf-8-sig'),object_pairs_hook=unique_object))


def encrypt_template(source,destination):
    if Path(source).resolve()==Path(destination).resolve(): raise ValueError('Choose a separate encrypted file')
    data=parse(read_small(source))
    if not data['credentials'].get('TOSS_CLIENT_ID') or not data['credentials'].get('TOSS_CLIENT_SECRET'):
        raise ValueError('Fill Toss Client ID and Secret first')
    payload=json.dumps(data,ensure_ascii=False).encode('utf-8')
    sealed=crypt(payload)
    if crypt(sealed,decrypt=True)!=payload: raise ValueError('Encryption verification failed')
    atomic_write(destination,MAGIC+sealed)


def load_settings(path):
    payload=read_small(path)
    if not payload.startswith(MAGIC): raise ValueError('Select an encrypted settings file')
    return parse(crypt(payload[len(MAGIC):],decrypt=True))
