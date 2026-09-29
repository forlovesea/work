"""Persistent alarm transitions and per-installation delivery queue.

Unknown/stale measurements never clear measurement alarms. Thresholds are
opt-in; communication monitoring runs independently of incoming uploads.
"""
import asyncio
from contextlib import closing
from datetime import datetime, timezone
import json
import logging
import math
import time
import uuid


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def epoch(value):
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return stamp.timestamp() if stamp.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def configure(config):
    opts = config.get('alarms', {})
    if not isinstance(opts, dict):
        raise ValueError('alarms must be an object')
    result = dict(opts)
    for key, default in [('stale_seconds', 60), ('scan_seconds', 5)]:
        value = result.setdefault(key, default)
        if not number(value) or not 1 <= value <= 86400:
            raise ValueError('Invalid alarms.' + key)
    rules = result.setdefault('rules', [])
    if not isinstance(rules, list) or len(rules) > 50:
        raise ValueError('alarms.rules must be a list of at most 50 rules')
    seen = set()
    for r in rules:
        if not isinstance(r, dict) or not isinstance(r.get('id'), str) or not r['id'] or len(r['id']) > 64 or r['id'] in seen:
            raise ValueError('Alarm rule IDs must be unique')
        seen.add(r['id'])
        if r.get('metric') not in ('soc', 'temps', 'cells', 'cell_delta') or r.get('direction') not in ('low', 'high'):
            raise ValueError('Invalid alarm metric/direction')
        for key, default in [('threshold', None), ('hysteresis', 0), ('duration_seconds', 0)]:
            value = r.get(key, default)
            if not number(value) or (key != 'threshold' and value < 0):
                raise ValueError('Invalid alarm ' + key)
        if 'enabled' in r and type(r['enabled']) is not bool:
            raise ValueError('Alarm enabled must be boolean')
    return result


def initialize(storage):
    with storage.lock, closing(storage.connect()) as db, db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS alarm_state (
                site_id TEXT, device_id TEXT, rule_key TEXT, active INTEGER NOT NULL DEFAULT 0,
                candidate_since REAL, last_observed REAL, event_id TEXT, message TEXT,
                PRIMARY KEY(site_id,device_id,rule_key));
            CREATE TABLE IF NOT EXISTS alarm_events (
                event_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, device_id TEXT NOT NULL,
                rule_key TEXT NOT NULL, transition TEXT NOT NULL, created_at REAL NOT NULL,
                message TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS alarm_event_time ON alarm_events(site_id,device_id,created_at DESC);
            CREATE TABLE IF NOT EXISTS alarm_acknowledgements (
                event_id TEXT, viewer_id TEXT, acknowledged_at REAL NOT NULL,
                PRIMARY KEY(event_id,viewer_id));
            CREATE TABLE IF NOT EXISTS push_devices (
                installation_id TEXT PRIMARY KEY, viewer_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL, updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS push_outbox (
                event_id TEXT, installation_id TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt REAL NOT NULL, sent_at REAL, last_error TEXT,
                PRIMARY KEY(event_id,installation_id));
        ''')


class AlarmEngine:
    def __init__(self, storage, config):
        self.storage, self.config = storage, config
        self.options = configure(config)
        self.started = time.time()
        initialize(storage)

    def transition(self, db, site, device, key, bad, message, observed, now, duration=0, fresh=True):
        row = db.execute('SELECT * FROM alarm_state WHERE site_id=? AND device_id=? AND rule_key=?',
                         (site, device, key)).fetchone()
        active = bool(row and row['active'])
        candidate = row['candidate_since'] if row else None
        last = row['last_observed'] if row else None
        event_id = row['event_id'] if row else None
        if not fresh:
            # Break a pending duration when data goes stale; retain active alarms.
            db.execute('UPDATE alarm_state SET candidate_since=NULL WHERE site_id=? AND device_id=? AND rule_key=?',
                       (site, device, key))
            return
        if last is not None and observed <= last:
            return
        if not active and bad:
            if candidate is None or last is None or observed - last > self.options['stale_seconds']:
                candidate = observed
            desired = observed - candidate >= duration
        else:
            candidate = None
            desired = bool(bad)
        if desired != active:
            event_id = str(uuid.uuid4())
            db.execute('INSERT INTO alarm_events VALUES(?,?,?,?,?,?,?)',
                       (event_id, site, device, key, 'raised' if desired else 'cleared', now, message))
            for viewer in (self.config.get('api') or {}).get('viewers', []):
                if dict(site_id=site, device_id=device) not in viewer['devices']:
                    continue
                db.execute('''INSERT OR IGNORE INTO push_outbox(event_id,installation_id,next_attempt)
                    SELECT ?,installation_id,? FROM push_devices WHERE viewer_id=?''', (event_id, now, viewer['id']))
        db.execute('''INSERT INTO alarm_state VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(site_id,device_id,rule_key) DO UPDATE SET active=excluded.active,
            candidate_since=excluded.candidate_since,last_observed=excluded.last_observed,
            event_id=excluded.event_id,message=excluded.message''',
                   (site, device, key, int(desired), candidate, observed, event_id, message))

    def tick(self, now=None):
        now = time.time() if now is None else now
        grants = {(g['site_id'], g['device_id']) for c in self.config['collectors'] for g in c['devices']}
        with self.storage.lock, closing(self.storage.connect()) as db, db:
            for site, device in sorted(grants):
                row = db.execute('''SELECT s.payload FROM devices d JOIN samples s
                    ON d.collector_id=s.collector_id AND d.sample_id=s.sample_id
                    WHERE d.site_id=? AND d.device_id=?''', (site, device)).fetchone()
                data = json.loads(row['payload']).get('data', {}) if row else {}
                observed = epoch(data.get('last_poll_at'))
                fresh = (observed is not None and 0 <= now - observed <= self.options['stale_seconds']
                         and data.get('connected') is True and data.get('last_poll_ok') is True)
                if row or now - self.started >= self.options['stale_seconds']:
                    self.transition(db, site, device, 'communication', not fresh,
                                    'Measurement communication unavailable' if not fresh else 'Measurement communication restored',
                                    now, now)
                if not fresh:
                    db.execute("UPDATE alarm_state SET candidate_since=NULL WHERE site_id=? AND device_id=? AND rule_key!='communication'",
                               (site, device))
                    continue
                # Track the device's reported alarm set as one aggregate condition.
                alarms = data.get('active_alarms')
                if isinstance(alarms, (list, dict)):
                    self.transition(db, site, device, 'device_alarms', bool(alarms),
                                    'Device reports active alarms' if alarms else 'Device alarms cleared', observed, now)
                modules = data.get('module_data', {})
                if not isinstance(modules, dict):
                    continue
                evaluated = set()
                for rule in self.options['rules']:
                    if not rule.get('enabled', True):
                        continue
                    metric = rule['metric']
                    for module, values in modules.items():
                        if not isinstance(values, dict):
                            continue
                        raw = values.get(metric)
                        if metric == 'cell_delta':
                            cells = values.get('cells')
                            raw = max(cells) - min(cells) if isinstance(cells, list) and len(cells) >= 2 and all(number(v) and v > 0 for v in cells) else None
                        readings = enumerate(raw, 1) if isinstance(raw, list) and metric in ('temps', 'cells') else [(0, raw)]
                        for cell, value in readings:
                            key = f"{rule['id']}:{module}:{cell}"
                            if not number(value) or (metric == 'cells' and value <= 0) or (metric == 'soc' and not 0 <= value <= 100):
                                continue
                            evaluated.add(key)
                            state = db.execute('SELECT active FROM alarm_state WHERE site_id=? AND device_id=? AND rule_key=?',
                                               (site, device, key)).fetchone()
                            active = bool(state and state['active'])
                            limit = rule['threshold']
                            if active:
                                limit += rule.get('hysteresis', 0) * (1 if rule['direction'] == 'low' else -1)
                            bad = value < limit if rule['direction'] == 'low' else value > limit
                            self.transition(db, site, device, key, bad,
                                            f"{metric} module {module}" + (f' cell {cell}' if cell else '') + f': {value:g}',
                                            observed, now, rule.get('duration_seconds', 0))
                for state in db.execute("SELECT rule_key FROM alarm_state WHERE site_id=? AND device_id=? AND rule_key NOT IN ('communication','device_alarms')", (site, device)).fetchall():
                    if state['rule_key'] not in evaluated:
                        self.transition(db, site, device, state['rule_key'], False, '', observed, now, fresh=False)


async def monitor(engine, stop):
    while not stop.is_set():
        try:
            await asyncio.to_thread(engine.tick)
        except Exception:
            logging.exception('Alarm evaluation failed; existing alarm state retained')
        try:
            await asyncio.wait_for(stop.wait(), engine.options['scan_seconds'])
        except asyncio.TimeoutError:
            pass
