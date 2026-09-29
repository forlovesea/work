"""Durable TCP upload, independent of Qt and SNMP."""
import hashlib
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
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS queue (seq INTEGER PRIMARY KEY, id TEXT UNIQUE, destination TEXT, payload TEXT, size INTEGER)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=2)

    def put(self, route, payload):
        text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        size = len(text.encode('utf-8'))
        if size > MAX_FRAME - 4096:
            raise ValueError('Snapshot too large')
        with self.lock, self.connect() as db:
            total = db.execute('SELECT COALESCE(SUM(size),0) FROM queue').fetchone()[0]
            if total + size > self.max_bytes:
                raise RuntimeError('Upload queue full: new data could not be saved; existing data retained')
            db.execute('INSERT INTO queue(id,destination,payload,size) VALUES(?,?,?,?)',
                       (payload['sample_id'], route, text, size))

    def peek(self, route):
        with self.lock, self.connect() as db:
            row = db.execute('SELECT id,payload FROM queue WHERE destination=? ORDER BY seq LIMIT 1', (route,)).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def acknowledge(self, sample_id):
        with self.lock, self.connect() as db:
            db.execute('DELETE FROM queue WHERE id=?', (sample_id,))

    def count(self):
        with self.lock, self.connect() as db:
            return db.execute('SELECT COUNT(*) FROM queue').fetchone()[0]


class UploadWorker(threading.Thread):
    def __init__(self, outbox, report):
        super().__init__(daemon=True, name='BatteryWatchUpload')
        self.outbox, self.report = outbox, report
        self.lock = threading.Lock()
        self.config = {}
        self.stopping = threading.Event()
        self.wake = threading.Event()
        self.sock = None

    def configure(self, config):
        with self.lock:
            self.config = dict(config)
        self.disconnect()
        self.wake.set()

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
        self.wake.set()

    def run(self):
        route = None
        backoff = 1
        while not self.stopping.is_set():
            self.wake.clear()
            with self.lock:
                config = dict(self.config)
            delay = 0.5
            try:
                if not config.get('enabled'):
                    self.disconnect()
                    self.wake.wait(delay)
                    continue
                current_route = destination(config)
                if current_route != route:
                    self.disconnect()
                    route = current_route
                pending = self.outbox.peek(route)
                if pending:
                    if self.sock is None:
                        sock = socket.create_connection((config['host'], int(config['port'])), timeout=4)
                        self.sock = sock
                        if config.get('tls', True):
                            context = ssl.create_default_context(cafile=config.get('ca_file') or None)
                            self.sock = context.wrap_socket(sock, server_hostname=config['host'])
                        self.sock.settimeout(4)
                    sample_id, payload = pending
                    self.sock.sendall(encode_frame({'type': 'upload', 'token': config['token'], 'payload': payload}))
                    ack = receive_frame(self.sock)
                    if not isinstance(ack, dict) or ack.get('type') != 'ack' or ack.get('sample_id') != sample_id or ack.get('ok') is not True:
                        raise ValueError('Invalid/rejected server ACK')
                    self.outbox.acknowledge(sample_id)
                    self.report('ACK ' + utc_now() + ' | pending ' + str(self.outbox.count()))
                    backoff, delay = 1, 0
            except Exception as exc:
                self.disconnect()
                # Do not expose server response contents or credentials.
                if not self.stopping.is_set():
                    self.report('Upload failed (' + type(exc).__name__ + '); retry in ' + str(backoff) + 's')
                delay = backoff
                backoff = min(backoff * 2, 60)
            self.wake.wait(delay)
        self.disconnect()


def envelope(config, kind, data):
    return {'schema_version': 1, 'sample_id': str(uuid4()), 'captured_at': utc_now(),
            'site_id': config['site_id'], 'device_id': config['device_id'],
            'kind': kind, 'data': data}
