"""Bounded periodic retention; never remove the latest device snapshot."""
import asyncio
from contextlib import closing
from datetime import datetime, timedelta, timezone
import logging

LOG = logging.getLogger('batterywatch.retention')


def configure(config):
    opts = config.get('retention', {})
    if not isinstance(opts, dict):
        raise ValueError('retention must be an object')
    result = dict(opts)
    for key, default, low, high in [('days', 10, 1, 3650), ('alarm_days', 0, 0, 3650),
                                  ('interval_seconds', 3600, 1, 86400), ('batch_size', 500, 1, 5000)]:
        value = result.setdefault(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError('Invalid retention.' + key)
    return result


def cleanup(storage, options, instant=None):
    instant = instant or datetime.now(timezone.utc)
    cutoff = (instant - timedelta(days=options['days'])).isoformat(timespec='microseconds')
    limit = options['batch_size']
    counts = {}
    with storage.lock, closing(storage.connect()) as db, db:
        counts['samples'] = db.execute('''DELETE FROM samples WHERE rowid IN (
            SELECT s.rowid FROM samples s WHERE received_at < ? AND NOT EXISTS (
                SELECT 1 FROM devices d WHERE d.collector_id=s.collector_id AND d.sample_id=s.sample_id)
            ORDER BY received_at LIMIT ?)''', (cutoff, limit)).rowcount
        counts['sessions'] = db.execute('''DELETE FROM sessions WHERE rowid IN (
            SELECT rowid FROM sessions WHERE disconnected_at < ? ORDER BY disconnected_at LIMIT ?)''',
            (cutoff, limit)).rowcount
        counts['alarms'] = 0
        if options['alarm_days']:
            alarm_cutoff = (instant - timedelta(days=options['alarm_days'])).timestamp()
            events = [r[0] for r in db.execute('''SELECT e.event_id FROM alarm_events e
                WHERE e.created_at < ? AND NOT EXISTS (
                    SELECT 1 FROM alarm_state s WHERE s.event_id=e.event_id)
                AND NOT EXISTS (SELECT 1 FROM push_outbox p WHERE p.event_id=e.event_id AND p.sent_at IS NULL)
                ORDER BY e.created_at LIMIT ?''', (alarm_cutoff, limit))]
            for event in events:
                db.execute('DELETE FROM alarm_acknowledgements WHERE event_id=?', (event,))
                db.execute('DELETE FROM push_outbox WHERE event_id=?', (event,))
                db.execute('DELETE FROM alarm_events WHERE event_id=?', (event,))
            counts['alarms'] = len(events)
    return counts


async def monitor(storage, config, stop):
    options = configure(config)
    LOG.info('Retention enabled days=%d alarm_days=%d interval_seconds=%d; latest snapshots retained',
             options['days'], options['alarm_days'], options['interval_seconds'])
    while not stop.is_set():
        totals = dict(samples=0, sessions=0, alarms=0)
        try:
            while not stop.is_set():
                counts = await asyncio.to_thread(cleanup, storage, options)
                for key in totals:
                    totals[key] += counts[key]
                if max(counts.values()) < options['batch_size']:
                    break
                # Release the database between batches and allow ingestion/shutdown.
                try:
                    await asyncio.wait_for(stop.wait(), .05)
                except asyncio.TimeoutError:
                    pass
            LOG.info('Retention removed samples=%d sessions=%d alarms=%d',
                     totals['samples'], totals['sessions'], totals['alarms'])
        except Exception as exc:
            LOG.error('Retention failed reason=%s; will retry', type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), options['interval_seconds'])
        except asyncio.TimeoutError:
            pass
