"""Bounded HTTP/1.1 API: telemetry reads, acknowledgements and push registration."""
import asyncio
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import hmac
import ipaddress
import json
import ssl
import time
import uuid
from alarms import initialize as initialize_alarms
from urllib.parse import urlsplit,parse_qs
from receiver import identifier


def configure_api(config):
    api=config.get('api',{})
    if not isinstance(api,dict): raise ValueError('Invalid API configuration')
    if not api or not api.get('enabled'): return None
    api.setdefault('host','127.0.0.1'); api.setdefault('port',8443)
    if type(api['port']) is not int or not 1<=api['port']<=65535: raise ValueError('Invalid API port')
    if not ipaddress.ip_address(api['host']).is_loopback and not config['tls'].get('certfile'):
        raise ValueError('Network API bind requires TLS certificate')
    viewers=api.get('viewers',[])
    if not isinstance(viewers,list) or not viewers: raise ValueError('API viewers required')
    ids,hashes=set(),set()
    collector_hashes={c['token_sha256'] for c in config['collectors']}
    for viewer in viewers:
        if not isinstance(viewer,dict) or not identifier(viewer.get('id')): raise ValueError('Invalid viewer')
        digest=viewer.get('token_sha256','')
        if not isinstance(digest,str) or len(digest)!=64 or any(ch not in '0123456789abcdef' for ch in digest):
            raise ValueError('Invalid viewer token hash')
        if viewer['id'] in ids or digest in hashes or digest in collector_hashes: raise ValueError('Viewer credentials must be unique and separate from collectors')
        ids.add(viewer['id']); hashes.add(digest)
        if not isinstance(viewer.get('devices'),list) or not viewer['devices']: raise ValueError('Viewer device grants required')
        for g in viewer['devices']:
            if not isinstance(g,dict) or set(g)!={'site_id','device_id'} or not all(identifier(v) for v in g.values()):
                raise ValueError('Invalid viewer device grant')
    return api


def freshness(payload,received_at):
    data=payload.get('data',{})
    observed=data.get('last_poll_at')
    age=None
    if isinstance(observed,str):
        try: age=(datetime.now(timezone.utc)-datetime.fromisoformat(observed.replace('Z','+00:00'))).total_seconds()
        except (ValueError,TypeError): pass
    fresh=age is not None and 0<=age<=60 and data.get('connected') is True and data.get('last_poll_ok') is True
    return dict(fresh=fresh,measurement_age_seconds=round(age,1) if age is not None else None,
                last_poll_at=observed,received_at=received_at)


def query(storage,viewer,path,params):
    grants=viewer['devices']
    with closing(storage.connect()) as db:
        if path=='/api/v1/devices':
            items=[]
            for grant in grants:
                row=db.execute('''SELECT s.payload,s.received_at FROM devices d JOIN samples s
                    ON d.collector_id=s.collector_id AND d.sample_id=s.sample_id
                    WHERE d.site_id=? AND d.device_id=?''',(grant['site_id'],grant['device_id'])).fetchone()
                item=dict(grant,available=row is not None)
                if row:
                    p=json.loads(row['payload']); data=p['data']
                    item.update(freshness(p,row['received_at']))
                    modules=data.get('module_map')
                    alarms=data.get('active_alarms')
                    item.update(system_name=data.get('system_name',''),site_name=data.get('site_name',''),
                                module_count=len(modules) if isinstance(modules,dict) else 0,
                                alarm_count=len(alarms) if isinstance(alarms,(dict,list)) else None)
                items.append(item)
            return 200,dict(devices=items)
        if path not in ('/api/v1/snapshot','/api/v1/history','/api/v1/alarms'): return 404,dict(error='not_found')
        grant=dict(site_id=params.get('site_id',[''])[0],device_id=params.get('device_id',[''])[0])
        if grant not in grants: return 403,dict(error='forbidden')
        args=(grant['site_id'],grant['device_id'])
        if path=='/api/v1/alarms':
            active=[dict(r) for r in db.execute('SELECT rule_key,event_id,message,last_observed FROM alarm_state WHERE site_id=? AND device_id=? AND active=1',args)]
            events=[dict(r) for r in db.execute("""SELECT e.*,a.acknowledged_at FROM alarm_events e LEFT JOIN alarm_acknowledgements a ON e.event_id=a.event_id AND a.viewer_id=? WHERE site_id=? AND device_id=? ORDER BY created_at DESC LIMIT 100""",(viewer['id'],)+args)]
            return 200,dict(active=active,events=events)
        if path=='/api/v1/snapshot':
            row=db.execute('''SELECT s.payload,s.received_at FROM devices d JOIN samples s
                ON d.collector_id=s.collector_id AND d.sample_id=s.sample_id
                WHERE d.site_id=? AND d.device_id=?''',args).fetchone()
            if not row: return 404,dict(error='no_data')
            p=json.loads(row['payload'])
            return 200,dict(payload=p,**freshness(p,row['received_at']))
        try: limit=int(params.get('limit',['20'])[0])
        except ValueError: return 400,dict(error='invalid_limit')
        if not 1<=limit<=100: return 400,dict(error='invalid_limit')
        rows=db.execute('''SELECT sample_id,kind,captured_at,received_at,payload FROM samples
            WHERE site_id=? AND device_id=? ORDER BY received_at DESC LIMIT ?''',args+(limit,)).fetchall()
        items=[]
        for r in rows:
            data=json.loads(r['payload'])['data']
            items.append(dict(sample_id=r['sample_id'],kind=r['kind'],captured_at=r['captured_at'],received_at=r['received_at'],
                              alarms=data.get('active_alarms',[]),faults=data.get('faults',[]),raw_trap=data.get('raw_trap'),
                              module_data=data.get('module_data'),last_poll_at=data.get('last_poll_at'),
                              connected=data.get('connected'),last_poll_ok=data.get('last_poll_ok')))
        return 200,dict(history=items)


def mutate(storage, viewer, method, path, body):
    if not isinstance(body, dict):
        return 400, dict(error='invalid_body')
    with storage.lock, closing(storage.connect()) as db, db:
        if method == 'POST' and path == '/api/v1/acknowledgements':
            event = db.execute('SELECT site_id,device_id FROM alarm_events WHERE event_id=?', (str(body.get('event_id', '')),)).fetchone()
            if event is None:
                return 404, dict(error='not_found')
            if dict(event) not in viewer['devices']:
                return 403, dict(error='forbidden')
            db.execute('INSERT OR IGNORE INTO alarm_acknowledgements VALUES(?,?,?)',
                       (body['event_id'], viewer['id'], time.time()))
            return 200, dict(ok=True)
        prefix = '/api/v1/push-devices/'
        if method in ('PUT', 'DELETE') and path.startswith(prefix):
            installation = path[len(prefix):]
            try:
                if str(uuid.UUID(installation)) != installation:
                    raise ValueError()
            except ValueError:
                return 400, dict(error='invalid_installation')
            owner = db.execute('SELECT viewer_id FROM push_devices WHERE installation_id=?', (installation,)).fetchone()
            if owner and owner['viewer_id'] != viewer['id']:
                return 403, dict(error='forbidden')
            if method == 'DELETE':
                db.execute('DELETE FROM push_outbox WHERE installation_id=?', (installation,))
                db.execute('DELETE FROM push_devices WHERE installation_id=?', (installation,))
            else:
                token = body.get('token')
                if not isinstance(token, str) or not 20 <= len(token) <= 4096 or any(c.isspace() for c in token):
                    return 400, dict(error='invalid_token')
                existing = db.execute('SELECT installation_id FROM push_devices WHERE token=?', (token,)).fetchone()
                if existing and existing['installation_id'] != installation:
                    return 409, dict(error='token_already_registered')
                db.execute("""INSERT INTO push_devices VALUES(?,?,?,?) ON CONFLICT(installation_id) DO UPDATE SET token=excluded.token,updated_at=excluded.updated_at""", (installation,viewer['id'],token,time.time()))
            return 200, dict(ok=True)
        return 405, dict(error='method_not_allowed')


class MobileApi:
    def __init__(self,config,storage):
        self.config=config; self.api=configure_api(config); self.storage=storage
        initialize_alarms(storage)
        self.server=None; self.tasks=set(); self.writers=set()

    async def start(self):
        if not self.api: return self
        context=None
        if self.config['tls'].get('certfile'):
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version=ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.config['tls']['certfile'],self.config['tls']['keyfile'])
        options={'ssl':context,'limit':16384}
        if context: options['ssl_handshake_timeout']=5
        self.server=await asyncio.start_server(self.handle,self.api['host'],self.api['port'],**options)
        return self

    async def close(self):
        if self.server: self.server.close(); await self.server.wait_closed()
        for w in list(self.writers): w.close()
        if self.tasks: await asyncio.gather(*list(self.tasks),return_exceptions=True)

    async def handle(self,reader,writer):
        task=asyncio.current_task()
        if len(self.tasks)>=32: writer.close(); return
        self.tasks.add(task); self.writers.add(writer)
        code,body=400,dict(error='bad_request')
        try:
            request=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),10)
            if len(request)>16384: raise ValueError()
            lines=request.decode('ascii').split('\r\n')
            method,target,version=lines[0].split(' ')
            headers={}
            for line in lines[1:]:
                if not line: continue
                key,value=line.split(':',1); key=key.strip().lower()
                if key in headers: raise ValueError()
                headers[key]=value.strip()
            if version not in ('HTTP/1.0','HTTP/1.1') or headers.get('transfer-encoding'):
                raise ValueError()
            length=int(headers.get('content-length','0'))
            if not 0<=length<=8192 or (method=='GET' and length):
                raise ValueError()
            token=headers.get('authorization','')
            digest=hashlib.sha256(token[7:].encode()).hexdigest() if token.startswith('Bearer ') else ''
            viewer=next((v for v in self.api['viewers'] if hmac.compare_digest(v['token_sha256'],digest)),None)
            if viewer is None: code,body=401,dict(error='unauthorized')
            else:
                url=urlsplit(target)
                if url.scheme or url.netloc: raise ValueError()
                if method=='GET':
                    code,body=await asyncio.to_thread(query,self.storage,viewer,url.path,parse_qs(url.query,max_num_fields=10))
                else:
                    raw=await asyncio.wait_for(reader.readexactly(length),5) if length else b'{}'
                    data=json.loads(raw)
                    code,body=await asyncio.to_thread(mutate,self.storage,viewer,method,url.path,data)
        except (ValueError,UnicodeError,asyncio.IncompleteReadError,asyncio.LimitOverrunError,asyncio.TimeoutError): pass
        except Exception: code,body=503,dict(error='temporarily_unavailable')
        try:
            body['server_time']=datetime.now(timezone.utc).isoformat()
            payload=json.dumps(body,ensure_ascii=False,allow_nan=False).encode('utf-8')
            if len(payload)>20*1024*1024: code,payload=413,b'{"error":"response_too_large"}'
            reason={200:'OK',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',405:'Method Not Allowed',409:'Conflict',413:'Content Too Large',503:'Service Unavailable'}[code]
            writer.write((f'HTTP/1.1 {code} {reason}\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(payload)}\r\nCache-Control: no-store\r\nConnection: close\r\nX-Content-Type-Options: nosniff\r\n\r\n').encode()+payload)
            await asyncio.wait_for(writer.drain(),5)
        except (ConnectionError,OSError,asyncio.TimeoutError): pass
        finally:
            writer.close()
            try: await asyncio.wait_for(writer.wait_closed(),2)
            except (OSError,asyncio.TimeoutError): pass
            self.writers.discard(writer); self.tasks.discard(task)
