"""Transactional SQLite storage. One server process per database."""
import json
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class SampleConflict(ValueError):
    pass


class Storage:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        with closing(self.connect()) as db, db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS samples (
                    collector_id TEXT NOT NULL, sample_id TEXT NOT NULL,
                    site_id TEXT NOT NULL, device_id TEXT NOT NULL,
                    kind TEXT NOT NULL, captured_at TEXT NOT NULL,
                    received_at TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(collector_id, sample_id));
                CREATE INDEX IF NOT EXISTS samples_device_time
                    ON samples(site_id, device_id, captured_at DESC);
                CREATE INDEX IF NOT EXISTS samples_received_time ON samples(received_at);
                CREATE TABLE IF NOT EXISTS devices (
                    site_id TEXT NOT NULL, device_id TEXT NOT NULL,
                    collector_id TEXT NOT NULL, sample_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL, last_received_at TEXT NOT NULL,
                    PRIMARY KEY(site_id, device_id));
                CREATE INDEX IF NOT EXISTS devices_sample ON devices(collector_id,sample_id);
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY, collector_id TEXT NOT NULL,
                    peer TEXT NOT NULL, connected_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL, disconnected_at TEXT);
                CREATE INDEX IF NOT EXISTS sessions_disconnected ON sessions(disconnected_at);
                CREATE TABLE IF NOT EXISTS control_commands (
                    command_id TEXT PRIMARY KEY, viewer_id TEXT NOT NULL,
                    collector_id TEXT NOT NULL, site_id TEXT NOT NULL, device_id TEXT NOT NULL,
                    action TEXT NOT NULL, value_centi INTEGER NOT NULL,
                    status TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
                    claim_until REAL, applied_value_centi INTEGER, result_message TEXT);
                CREATE INDEX IF NOT EXISTS control_commands_pending
                    ON control_commands(collector_id,site_id,device_id,status,created_at);
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        return db

    def recover_sessions(self):
        with self.lock, closing(self.connect()) as db, db:
            db.execute('UPDATE sessions SET disconnected_at=? WHERE disconnected_at IS NULL', (now(),))

    def save(self, collector_id, payload, session_id, peer):
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        received = now()
        with self.lock, closing(self.connect()) as db, db:
            existing = db.execute('SELECT payload FROM samples WHERE collector_id=? AND sample_id=?',
                                  (collector_id, payload['sample_id'])).fetchone()
            if existing and existing['payload'] != text:
                raise SampleConflict('sample_id_conflict')
            duplicate = existing is not None
            if not duplicate:
                db.execute('INSERT INTO samples VALUES(?,?,?,?,?,?,?,?)',
                           (collector_id, payload['sample_id'], payload['site_id'], payload['device_id'],
                            payload['kind'], payload['captured_at'], received, text))
            if payload['kind'] == 'snapshot':
                db.execute('''INSERT INTO devices VALUES(?,?,?,?,?,?)
                    ON CONFLICT(site_id,device_id) DO UPDATE SET
                    collector_id=CASE WHEN excluded.captured_at>devices.captured_at THEN excluded.collector_id ELSE devices.collector_id END,
                    sample_id=CASE WHEN excluded.captured_at>devices.captured_at THEN excluded.sample_id ELSE devices.sample_id END,
                    captured_at=MAX(devices.captured_at,excluded.captured_at),
                    last_received_at=excluded.last_received_at''',
                    (payload['site_id'], payload['device_id'], collector_id, payload['sample_id'], payload['captured_at'], received))
                for result in payload['data'].get('control_results', []):
                    command = db.execute('''SELECT value_centi FROM control_commands
                        WHERE command_id=? AND collector_id=? AND site_id=? AND device_id=?
                        AND status='dispatched' ''',
                        (result['command_id'],collector_id,payload['site_id'],payload['device_id'])).fetchone()
                    if command is None:
                        continue
                    applied = result.get('applied_value_centi')
                    status = 'succeeded' if (
                        result['status'] == 'succeeded'
                        and result.get('applied_value_centi') == command['value_centi']
                    ) else 'failed'
                    result_message = (
                        result.get('message','') if status == 'succeeded'
                        else result.get('message','') or '장비 적용값 검증 실패'
                    )
                    db.execute('''UPDATE control_commands SET status=?,claim_until=NULL,
                        applied_value_centi=?,result_message=?
                        WHERE command_id=? AND collector_id=? AND site_id=? AND device_id=?
                        AND status='dispatched' ''',
                        (status,applied,result_message,result['command_id'],collector_id,
                         payload['site_id'],payload['device_id']))
            db.execute('''INSERT INTO sessions VALUES(?,?,?,?,?,NULL)
                ON CONFLICT(session_id) DO UPDATE SET last_seen_at=excluded.last_seen_at''',
                (session_id, collector_id, peer, received, received))
        # Exiting the transaction commits before caller can return an ACK.
        return duplicate

    def disconnected(self, session_id):
        with self.lock, closing(self.connect()) as db, db:
            db.execute('UPDATE sessions SET disconnected_at=? WHERE session_id=?', (now(), session_id))

    def claim_control_command(self, collector_id, site_id, device_id, instant=None):
        instant = time.time() if instant is None else instant
        with self.lock, closing(self.connect()) as db, db:
            db.execute('''UPDATE control_commands SET status='timed_out',claim_until=NULL,
                result_message='명령 시간 초과' WHERE status IN ('queued','dispatched') AND expires_at<=?''',
                (instant,))
            row = db.execute('''SELECT command_id,action,value_centi FROM control_commands
                WHERE collector_id=? AND site_id=? AND device_id=? AND expires_at>?
                AND (status='queued' OR (status='dispatched' AND claim_until<=?))
                ORDER BY created_at LIMIT 1''',
                (collector_id,site_id,device_id,instant,instant)).fetchone()
            if row is None:
                return None
            db.execute('''UPDATE control_commands SET status='dispatched',claim_until=?
                WHERE command_id=?''', (instant + 20,row['command_id']))
            return dict(command_id=row['command_id'],action=row['action'],
                        value_centi=row['value_centi'])

    def control_command_status(self, command_id, viewer_id, instant=None):
        instant = time.time() if instant is None else instant
        with self.lock, closing(self.connect()) as db, db:
            db.execute('''UPDATE control_commands SET status='timed_out',claim_until=NULL,
                result_message='명령 시간 초과' WHERE command_id=? AND viewer_id=?
                AND status IN ('queued','dispatched') AND expires_at<=?''',
                (command_id,viewer_id,instant))
            row = db.execute('''SELECT command_id,site_id,device_id,action,value_centi,status,
                applied_value_centi,result_message,created_at,expires_at
                FROM control_commands WHERE command_id=? AND viewer_id=?''',
                (command_id,viewer_id)).fetchone()
            return dict(row) if row else None

    def inspect(self, site=None, device=None, limit=20):
        with closing(self.connect()) as db:
            clauses, args = [], []
            if site is not None: clauses.append('site_id=?'); args.append(site)
            if device is not None: clauses.append('device_id=?'); args.append(device)
            where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
            rows = db.execute('SELECT * FROM samples' + where + ' ORDER BY received_at DESC LIMIT ?', args+[limit]).fetchall()
            history = [{**dict(row), 'payload': json.loads(row['payload'])} for row in rows]
            latest = db.execute('''SELECT d.*,s.payload FROM devices d JOIN samples s
                ON s.collector_id=d.collector_id AND s.sample_id=d.sample_id''').fetchall()
            latest = [{**dict(r), 'payload': json.loads(r['payload'])} for r in latest
                      if (site is None or r['site_id']==site) and (device is None or r['device_id']==device)]
            sessions = [dict(r) for r in db.execute('SELECT * FROM sessions ORDER BY last_seen_at DESC LIMIT ?', (limit,))]
            count = db.execute('SELECT count(*) FROM samples').fetchone()[0]
        return dict(total_samples=count, latest=latest, history=history, recent_sessions=sessions)

    def backup(self, target):
        target = Path(target)
        if target.exists() or target.resolve() == self.path.resolve():
            raise ValueError('Backup target must be a new file')
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.lock, closing(self.connect()) as src, closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
