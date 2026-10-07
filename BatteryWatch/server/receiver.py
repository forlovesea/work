"""BatteryWatch v1 TCP/TLS receiver, Python 3.10+ standard library only."""
from communication_log import PeerLog
import asyncio
import base64
import time
import zlib
import hashlib
import hmac
import ipaddress
import json
import logging
import ssl
import struct
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID, uuid4
from storage import SampleConflict

LOG = logging.getLogger('batterywatch')
MAX_FRAME = 16 * 1024 * 1024


class Rejected(ValueError):
    pass


def timestamp(value):
    if not isinstance(value, str) or len(value)>64:
        raise Rejected('invalid_timestamp')
    try:
        dt = datetime.fromisoformat(value.replace('Z','+00:00'))
        if dt.tzinfo is None: raise ValueError()
        dt = dt.astimezone(timezone.utc)
        if dt > datetime.now(timezone.utc)+timedelta(minutes=5):
            raise ValueError()
        return dt.isoformat(timespec='microseconds')
    except (ValueError, OverflowError):
        raise Rejected('invalid_timestamp') from None


def identifier(value):
    return isinstance(value,str) and 0<len(value)<=128 and not any(ord(c)<32 for c in value)


def authenticate(message, collectors):
    token = message.get('token')
    if not isinstance(token,str) or not 1<=len(token)<=4096:
        raise Rejected('unauthorized')
    digest = hashlib.sha256(token.encode()).hexdigest()
    collector = next((c for c in collectors if hmac.compare_digest(c['token_sha256'],digest)),None)
    if collector is None: raise Rejected('unauthorized')
    return collector


def validate(message, collectors):
    if not isinstance(message, dict) or message.get('type')!='upload':
        raise Rejected('invalid_message')
    collector = authenticate(message, collectors)
    p = message.get('payload')
    if not isinstance(p,dict) or type(p.get('schema_version')) is not int or p['schema_version']!=1:
        raise Rejected('invalid_schema')
    if not all(identifier(p.get(k)) for k in ('sample_id','site_id','device_id')):
        raise Rejected('invalid_identifier')
    if {'site_id':p['site_id'],'device_id':p['device_id']} not in collector['devices']:
        raise Rejected('forbidden_device')
    if p.get('kind') not in ('snapshot','trap') or not isinstance(p.get('data'),dict):
        raise Rejected('invalid_payload')
    # Preserve all data fields; only normalize the envelope timestamp for ordering.
    p = dict(p)
    p['captured_at'] = timestamp(p.get('captured_at'))
    if p['kind']=='snapshot':
        if type(p['data'].get('connected')) is not bool:
            raise Rejected('invalid_connection_state')
        for field in ('module_data','module_map','raw_oids'):
            if not isinstance(p['data'].get(field),dict): raise Rejected('invalid_snapshot')
        if not isinstance(p['data'].get('active_alarms'),list): raise Rejected('invalid_snapshot')
        if p['data'].get('last_poll_at') is not None: timestamp(p['data']['last_poll_at'])
        results=p['data'].get('control_results',[])
        if not isinstance(results,list) or len(results)>20:
            raise Rejected('invalid_control_result')
        for result in results:
            if not isinstance(result,dict):
                raise Rejected('invalid_control_result')
            try:
                if str(UUID(result.get('command_id',''))) != result['command_id']:
                    raise ValueError()
            except (ValueError,TypeError,KeyError):
                raise Rejected('invalid_control_result') from None
            if result.get('status') not in ('succeeded','failed'):
                raise Rejected('invalid_control_result')
            applied=result.get('applied_value_centi')
            if applied is not None and (type(applied) is not int or not 5<=applied<=100):
                raise Rejected('invalid_control_result')
            if not isinstance(result.get('message',''),str) or len(result.get('message',''))>200:
                raise Rejected('invalid_control_result')
    else:
        if not isinstance(p['data'].get('raw_trap'),dict): raise Rejected('invalid_trap')
        timestamp(p['data'].get('received_at'))
    return collector['id'],p


def decode_history(message, collectors):
    if message.get('encoding') != 'gzip+base64' or not isinstance(message.get('data'), str):
        raise Rejected('invalid_history_encoding')
    try:
        compressed = base64.b64decode(message['data'], validate=True)
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        raw = inflater.decompress(compressed, MAX_FRAME + 1)
        if len(raw) > MAX_FRAME or not inflater.eof or inflater.unused_data:
            raise ValueError()
        batch = json.loads(raw.decode('utf-8'))
        json.dumps(batch, allow_nan=False)
    except (ValueError, UnicodeError, zlib.error, RecursionError):
        raise Rejected('invalid_history_data') from None
    if not isinstance(batch, list) or not 1 <= len(batch) <= 100:
        raise Rejected('invalid_history_count')
    if len(raw) > 512 * 1024 and len(batch) > 1:
        raise Rejected('history_batch_too_large')
    validated = [validate(dict(type='upload', token=message['token'], payload=p), collectors)[1] for p in batch]
    if len({p['sample_id'] for p in validated}) != len(validated):
        raise Rejected('duplicate_history_id')
    return validated


def load_config(path):
    path=Path(path).resolve()
    c=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(c,dict): raise ValueError('Configuration must be an object')
    for key,default,low,high in [('port',9443,1,65535),('max_connections',32,1,1024),
                               ('idle_timeout',3700,1,7200),('frame_timeout',15,1,60),
                               ('max_frame_bytes',MAX_FRAME,1024,MAX_FRAME),
                               ('history_max_inflight',2,1,16), ('history_min_interval',5,1,300)]:
        value=c.setdefault(key,default)
        if type(value) is not int or not low<=value<=high: raise ValueError('Invalid '+key)
    c.setdefault('host','127.0.0.1')
    address=ipaddress.ip_address(c['host'])
    tls=c.setdefault('tls',{})
    if not isinstance(tls,dict): raise ValueError('Invalid tls configuration')
    if not tls.get('certfile') and not address.is_loopback:
        raise ValueError('Public/network bind requires TLS certfile and keyfile')
    if bool(tls.get('certfile')) != bool(tls.get('keyfile')):
        raise ValueError('Both certfile and keyfile are required')
    for key in ('certfile','keyfile'):
        if tls.get(key): tls[key]=str((path.parent/tls[key]).resolve())
    c['database']=str((path.parent/c.get('database','data/batterywatch.sqlite3')).resolve())
    collectors=c.get('collectors')
    if not isinstance(collectors,list) or not collectors: raise ValueError('At least one collector required')
    ids,hashes=set(),set()
    for item in collectors:
        if not isinstance(item,dict) or not identifier(item.get('id')): raise ValueError('Invalid collector ID')
        digest=item.get('token_sha256','')
        if not isinstance(digest,str) or len(digest)!=64 or any(ch not in '0123456789abcdef' for ch in digest):
            raise ValueError('Invalid token SHA256')
        if item['id'] in ids or digest in hashes: raise ValueError('Duplicate collector ID or token')
        ids.add(item['id']); hashes.add(digest)
        if not isinstance(item.get('devices'),list) or not item['devices']: raise ValueError('Device grants required')
        for grant in item['devices']:
            if not isinstance(grant,dict) or set(grant)!={'site_id','device_id'} or not all(identifier(v) for v in grant.values()):
                raise ValueError('Invalid device grant')
    push=c.get('push',{})
    if not isinstance(push,dict) or type(push.get('enabled',False)) is not bool: raise ValueError('Invalid push configuration')
    if push.get('service_account'): push['service_account']=str((path.parent/push['service_account']).resolve())
    from retention import configure as configure_retention
    configure_retention(c)
    return c


class Receiver:
    def __init__(self, config, storage):
        self.config,self.storage=config,storage
        self.server=None
        self.tasks=set()
        self.writers=set()
        self.history_inflight=0
        self.history_next={}

    async def start(self):
        tls=self.config.get('tls',{})
        context=None
        if tls.get('certfile'):
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version=ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(tls['certfile'],tls['keyfile'])
        options={'ssl':context,'limit':65536}
        if context: options['ssl_handshake_timeout']=5
        self.server=await asyncio.start_server(self.handle,self.config['host'],self.config['port'],**options)
        await asyncio.to_thread(self.storage.recover_sessions)
        LOG.info('Listening on %s (TLS=%s)',self.server.sockets[0].getsockname(),bool(context))
        return self

    async def close(self):
        if self.server:
            self.server.close(); await self.server.wait_closed()
        for writer in list(self.writers): writer.close()
        # Finish any database transaction before shutdown; never ACK uncommitted data.
        if self.tasks: await asyncio.gather(*list(self.tasks),return_exceptions=True)

    async def handle_history(self, message, writer):
        identity = authenticate(message, self.config['collectors'])['id']
        instant = time.monotonic()
        retry = self.history_next.get(identity, 0) - instant
        if self.history_inflight >= self.config.get('history_max_inflight', 2) or retry > 0:
            response = dict(type='history_ack', ok=False, retry_after=max(1, min(300, int(retry) + 1)))
        else:
            self.history_inflight += 1
            self.history_next[identity] = instant + self.config.get('history_min_interval', 5)
            try:
                def save():
                    batch = decode_history(message, self.config['collectors'])
                    self.storage.save_history(identity, batch)
                    return [p['sample_id'] for p in batch]
                ids = await asyncio.to_thread(save)
                response = dict(type='history_ack', ok=True, sample_ids=ids)
            finally:
                self.history_inflight -= 1
        raw = json.dumps(response).encode()
        writer.write(struct.pack('!I', len(raw)) + raw)
        await asyncio.wait_for(writer.drain(), 4)

    async def handle(self, reader, writer):
        log=PeerLog(LOG,writer,'수집기')
        task=asyncio.current_task()
        if len(self.tasks)>=self.config['max_connections']:
            log.debug('UPLOAD rejected peer=%s reason=connection_limit',writer.get_extra_info('peername'))
            writer.close(); return
        self.tasks.add(task); self.writers.add(writer)
        session_id=str(uuid4())
        peer=str(writer.get_extra_info('peername'))
        collector_id=None
        log.debug('UPLOAD connected session=%s peer=%s tls=%s',session_id,peer,bool(writer.get_extra_info('ssl_object')))
        try:
            while True:
                header=await asyncio.wait_for(reader.readexactly(4),self.config['idle_timeout'] if collector_id else 10)
                size=struct.unpack('!I',header)[0]
                if not 0<size<=self.config['max_frame_bytes']: raise Rejected('invalid_frame_size')
                log.debug('UPLOAD frame session=%s bytes=%d',session_id,size)
                raw=await asyncio.wait_for(reader.readexactly(size),self.config['frame_timeout'])
                def bad_constant(_): raise Rejected('non_finite_number')
                try:
                    message=json.loads(raw.decode('utf-8'),parse_constant=bad_constant)
                    # json.loads can produce infinity from 1e999 without parse_constant.
                    json.dumps(message,allow_nan=False)
                except (ValueError,UnicodeError,RecursionError): raise Rejected('invalid_json') from None
                if isinstance(message, dict) and message.get('type') == 'history_batch':
                    if collector_id is not None:
                        raise Rejected('history_requires_separate_connection')
                    await self.handle_history(message, writer)
                    return  # One bounded batch per connection; reserve capacity for live uploads.
                identity,payload=validate(message,self.config['collectors'])
                if collector_id is not None and identity!=collector_id: raise Rejected('identity_changed')
                if collector_id is None:
                    log.debug('UPLOAD authenticated session=%s collector=%r',session_id,identity)
                collector_id=identity
                duplicate=await asyncio.to_thread(self.storage.save,identity,payload,session_id,peer)
                ack_message=dict(type='ack',sample_id=payload['sample_id'],ok=True,duplicate=duplicate,history_batch_v1=True)
                if payload['kind']=='snapshot':
                    command=await asyncio.to_thread(
                        self.storage.claim_control_command,identity,payload['site_id'],payload['device_id'])
                    if command is not None:
                        ack_message['control_command']=command
                ack=json.dumps(ack_message).encode()
                writer.write(struct.pack('!I',len(ack))+ack)
                await asyncio.wait_for(writer.drain(),4)
                log.debug('UPLOAD ack session=%s collector=%r site=%r device=%r sample=%r kind=%s duplicate=%s',
                          session_id,identity,payload['site_id'],payload['device_id'],payload['sample_id'],payload['kind'],duplicate)
        except (Rejected,SampleConflict) as exc:
            log.warning('Rejected session=%s reason=%s',session_id,str(exc))
        except (asyncio.IncompleteReadError,ConnectionError,TimeoutError,asyncio.TimeoutError,OSError) as exc:
            log.debug('UPLOAD transport_closed session=%s reason=%s',session_id,type(exc).__name__)
        except Exception:
            # Never log raw data, request tokens or exception values containing payloads.
            log.error('Storage/processing failed session=%s; no success ACK sent',session_id)
        finally:
            writer.close()
            try: await asyncio.wait_for(writer.wait_closed(),2)
            except (OSError,asyncio.TimeoutError): pass
            if collector_id is not None:
                try: await asyncio.to_thread(self.storage.disconnected,session_id)
                except Exception: log.error('Unable to record disconnect session=%s',session_id)
            self.writers.discard(writer); self.tasks.discard(task)
            log.debug('Disconnected session=%s',session_id)
