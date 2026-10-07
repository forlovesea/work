"""Durable TCP upload, independent of Qt and SNMP."""
import hashlib
import base64
import gzip
import random
import time
from contextlib import closing
import json
import socket
import sqlite3
import ssl
import struct
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

MAX_FRAME = 16 * 1024 * 1024
HISTORY_BATCH_COUNT = 100
HISTORY_BATCH_BYTES = 512 * 1024
HISTORY_INTERVAL = 5
HISTORY_BYTES_PER_SECOND = 64 * 1024


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def encode_frame(value):
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(payload) > MAX_FRAME:
        raise ValueError('Upload frame exceeds 16 MiB')
    return struct.pack('!I', len(payload)) + payload


def receive_frame(sock):
    def exact(size):
        chunks = bytearray()
        while len(chunks) < size:
            part = sock.recv(size - len(chunks))
            if not part:
                raise ConnectionError('Connection closed before complete frame')
            chunks.extend(part)
        return bytes(chunks)
    length = struct.unpack('!I', exact(4))[0]
    if not 0 < length <= MAX_FRAME:
        raise ValueError('Invalid frame size')
    return json.loads(exact(length).decode('utf-8'))


def destination(config):
    # Separate queues when server, identity or credential changes.
    keys = ('host', 'port', 'tls', 'ca_file', 'token', 'site_id', 'device_id')
    return hashlib.sha256(json.dumps({k: config.get(k) for k in keys}, sort_keys=True).encode()).hexdigest()


class Outbox:
    def __init__(self, path, max_bytes=512 * 1024 * 1024):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.max_bytes = max_bytes
        self.lock = threading.Lock()
        with closing(self.connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS queue (seq INTEGER PRIMARY KEY, id TEXT UNIQUE, destination TEXT, payload TEXT, size INTEGER)')
            columns = {r[1] for r in db.execute('PRAGMA table_info(queue)')}
            if 'lane' not in columns:
                # Existing unacknowledged data is history, never a fresh status.
                db.execute("ALTER TABLE queue ADD COLUMN lane TEXT NOT NULL DEFAULT 'history'")
                db.execute("ALTER TABLE queue ADD COLUMN kind TEXT NOT NULL DEFAULT ''")
                db.execute("ALTER TABLE queue ADD COLUMN captured_at TEXT NOT NULL DEFAULT ''")
            db.execute('CREATE INDEX IF NOT EXISTS queue_route_lane ON queue(destination,lane,seq)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=2)

    def put(self, route, payload):
        text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        size = len(text.encode('utf-8'))
        if size > MAX_FRAME - 4096:
            raise ValueError('Snapshot too large')
        with self.lock, closing(self.connect()) as db, db:
            total = db.execute('SELECT COALESCE(SUM(size),0) FROM queue').fetchone()[0]
            if total + size > self.max_bytes:
                raise RuntimeError('Upload queue full: new data could not be saved; existing data retained')
            if payload['kind'] == 'snapshot':
                db.execute("UPDATE queue SET lane='history' WHERE destination=? AND lane='live' AND kind='snapshot'", (route,))
            db.execute('INSERT INTO queue(id,destination,payload,size,lane,kind,captured_at) VALUES(?,?,?,?,?,?,?)',
                       (payload['sample_id'], route, text, size, 'live', payload['kind'], payload['captured_at']))

    def live(self, route, max_age):
        cutoff = datetime.fromtimestamp(time.time() - max_age, timezone.utc).isoformat()
        with self.lock, closing(self.connect()) as db, db:
            db.execute("UPDATE queue SET lane='history' WHERE destination=? AND lane='live' AND captured_at<?", (route, cutoff))
            row = db.execute("SELECT id,payload FROM queue WHERE destination=? AND lane='live' ORDER BY CASE kind WHEN 'snapshot' THEN 0 ELSE 1 END,seq LIMIT 1", (route,)).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def history_batch(self, route):
        result, size = [], 2
        with self.lock, closing(self.connect()) as db:
            for row in db.execute("SELECT payload,size FROM queue WHERE destination=? AND lane='history' ORDER BY seq LIMIT ?", (route, HISTORY_BATCH_COUNT)):
                if result and size + row[1] + 1 > HISTORY_BATCH_BYTES:
                    break
                result.append(json.loads(row[0]))
                size += row[1] + 1
        return result

    def acknowledge_many(self, sample_ids):
        with self.lock, closing(self.connect()) as db, db:
            db.executemany('DELETE FROM queue WHERE id=?', ((sid,) for sid in sample_ids))

    def peek(self, route):
        with self.lock, closing(self.connect()) as db, db:
            row = db.execute('SELECT id,payload FROM queue WHERE destination=? ORDER BY seq LIMIT 1', (route,)).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def acknowledge(self, sample_id):
        with self.lock, closing(self.connect()) as db, db:
            db.execute('DELETE FROM queue WHERE id=?', (sample_id,))

    def count(self):
        with self.lock, closing(self.connect()) as db, db:
            return db.execute('SELECT COUNT(*) FROM queue').fetchone()[0]


class UploadWorker(threading.Thread):
    def __init__(self, outbox, report, result=None):
        super().__init__(daemon=True, name='BatteryWatchUpload')
        self.outbox, self.report = outbox, report
        self.result = result or (lambda event: None)
        self.generation = 0
        self.lock = threading.Lock()
        self.config = {}
        self.stopping = threading.Event()
        self.wake = threading.Event()
        self.sock = None
        self.history_sock = None
        self.history_supported = False
        self.last_live_success = 0
        self.history_thread = threading.Thread(target=self.run_history, daemon=True, name='BatteryWatchHistory')

    def start(self):
        super().start()
        self.history_thread.start()

    def join(self, timeout=None):
        started = time.monotonic()
        super().join(timeout)
        if self.history_thread.ident is not None:
            self.history_thread.join(None if timeout is None else max(0, timeout - (time.monotonic() - started)))

    def configure(self, config):
        with self.lock:
            self.config = dict(config)
            self.generation += 1
            self.history_supported = False
            self.last_live_success = 0
            generation = self.generation
        self.disconnect()
        self.disconnect_history()
        self.wake.set()
        return generation

    def disconnect(self):
        sock, self.sock = self.sock, None
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    def stop(self):
        self.stopping.set()
        self.disconnect()
        self.disconnect_history()
        self.wake.set()

    def run(self):
        route = None
        backoff = 1
        while not self.stopping.is_set():
            self.wake.clear()
            with self.lock:
                config = dict(self.config)
                generation = self.generation
            delay = 0.5
            pending = None
            try:
                if not config.get('enabled'):
                    self.disconnect()
                    self.wake.wait(delay)
                    continue
                current_route = destination(config)
                if current_route != route:
                    self.disconnect()
                    route = current_route
                pending = self.outbox.live(route, max(30, config.get('interval', 5) * 2 + 10))
                if pending:
                    if self.sock is None:
                        sock = socket.create_connection((config['host'], int(config['port'])), timeout=4)
                        self.sock = sock
                        if config.get('tls', True):
                            context = ssl.create_default_context(cafile=config.get('ca_file') or None)
                            self.sock = context.wrap_socket(sock, server_hostname=config['host'])
                        self.sock.settimeout(4)
                    with self.lock:
                        if generation != self.generation or self.stopping.is_set():
                            continue
                    sample_id, payload = pending
                    self.sock.sendall(encode_frame({'type': 'upload', 'token': config['token'], 'payload': payload}))
                    ack = receive_frame(self.sock)
                    if not isinstance(ack, dict) or ack.get('type') != 'ack' or ack.get('sample_id') != sample_id or ack.get('ok') is not True:
                        raise ValueError('Invalid/rejected server ACK')
                    self.outbox.acknowledge(sample_id)
                    with self.lock:
                        if generation == self.generation:
                            self.history_supported = ack.get('history_batch_v1') is True
                            self.last_live_success = time.monotonic()
                    self.result(self.result_event(generation, payload, True,
                                                  control_command=ack.get('control_command')))
                    self.report('ACK ' + utc_now() + ' | pending ' + str(self.outbox.count()))
                    backoff, delay = 1, 0.1
            except Exception as exc:
                self.disconnect()
                with self.lock:
                    self.last_live_success = 0
                # Do not expose server response contents or credentials.
                if not self.stopping.is_set():
                    self.result(self.result_event(generation, pending[1] if pending else None,
                                                  False, type(exc).__name__))
                    self.report('Upload failed (' + type(exc).__name__ + '); retry in ' + str(backoff) + 's')
                delay = backoff
                backoff = min(backoff * 2, 60)
            self.wake.wait(delay)
        self.disconnect()

    def disconnect_history(self):
        sock, self.history_sock = self.history_sock, None
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    def run_history(self):
        next_send, backoff, previous_generation = 0, HISTORY_INTERVAL, None
        while not self.stopping.wait(0.2):
            with self.lock:
                config, generation = dict(self.config), self.generation
                ready = (self.history_supported and self.last_live_success and
                         time.monotonic() - self.last_live_success < max(30, config.get('interval', 5) * 2 + 10))
            if not config.get('enabled') or not ready:
                next_send = time.monotonic() + random.uniform(2, 5)
                continue
            if generation != previous_generation:
                previous_generation = generation
                next_send = time.monotonic() + random.uniform(2, 5)
            if time.monotonic() < next_send:
                continue
            try:
                batch = self.outbox.history_batch(destination(config))
                if not batch:
                    next_send = time.monotonic() + 1
                    continue
                raw = json.dumps(batch, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
                frame = encode_frame(dict(type='history_batch', token=config['token'],
                                          encoding='gzip+base64', data=base64.b64encode(gzip.compress(raw)).decode('ascii')))
                sock = socket.create_connection((config['host'], int(config['port'])), timeout=4)
                self.history_sock = sock
                if config.get('tls', True):
                    context = ssl.create_default_context(cafile=config.get('ca_file') or None)
                    sock = context.wrap_socket(sock, server_hostname=config['host'])
                    self.history_sock = sock
                sock.settimeout(15)
                with self.lock:
                    if generation != self.generation or self.stopping.is_set():
                        continue
                sock.sendall(frame)
                ack = receive_frame(sock)
                ids = [p['sample_id'] for p in batch]
                if isinstance(ack, dict) and ack.get('type') == 'history_ack' and ack.get('ok') is False:
                    retry = ack.get('retry_after', HISTORY_INTERVAL)
                    if type(retry) not in (int, float) or not 1 <= retry <= 300:
                        raise ValueError('Invalid history retry delay')
                    next_send = time.monotonic() + retry + random.uniform(0, 2)
                    continue
                if not isinstance(ack, dict) or ack.get('type') != 'history_ack' or ack.get('ok') is not True or ack.get('sample_ids') != ids:
                    raise ValueError('Invalid history ACK')
                self.outbox.acknowledge_many(ids)
                if generation == self.generation:
                    self.report('History ACK | saved ' + str(len(ids)) + ' | pending ' + str(self.outbox.count()))
                backoff = HISTORY_INTERVAL
                next_send = time.monotonic() + max(HISTORY_INTERVAL, len(frame) / HISTORY_BYTES_PER_SECOND) + random.uniform(0, 2)
            except Exception as exc:
                if generation == self.generation and not self.stopping.is_set():
                    self.report('History upload failed (' + type(exc).__name__ + '); live upload continues')
                # History failure never changes the live status or triggers commands.
                next_send = time.monotonic() + backoff + random.uniform(0, 2)
                backoff = min(backoff * 2, 60)
            finally:
                self.disconnect_history()

    @staticmethod
    def result_event(generation, payload, ok, error='', control_command=None):
        payload = payload or {}
        data = payload.get('data', {})
        if payload.get('kind') == 'snapshot':
            summary = (f"상태 · 모듈 {len(data.get('module_data') or {})}개 · "
                       f"알람 {len(data.get('active_alarms') or {})}건 · "
                       f"장비 {'연결' if data.get('connected') else '미연결'} · "
                       f"측정 {'성공' if data.get('last_poll_ok') else '실패/대기'}")
        elif payload.get('kind') == 'trap':
            summary = '알람 이벤트 (Trap)'
        else:
            summary = '전송 대기 데이터'
        return dict(generation=generation, at=utc_now(), ok=ok, error=error,
                    site_id=payload.get('site_id', ''), device_id=payload.get('device_id', ''),
                    captured_at=payload.get('captured_at'), last_poll_at=data.get('last_poll_at'),
                    summary=summary, control_command=control_command)


def envelope(config, kind, data):
    return {'schema_version': 1, 'sample_id': str(uuid4()), 'captured_at': utc_now(),
            'site_id': config['site_id'], 'device_id': config['device_id'],
            'kind': kind, 'data': data}
