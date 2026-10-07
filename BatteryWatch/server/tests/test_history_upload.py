"""Real TCP tests for live priority and bounded historical recovery."""
import asyncio
import base64
from contextlib import closing
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_server
from receiver import decode_history, Rejected, MAX_FRAME
from upload_transport import Outbox, UploadWorker, destination, encode_frame, envelope


class HistoryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_server.ServerTests.asyncSetUp
    asyncTearDown = test_server.ServerTests.asyncTearDown
    sample = test_server.ServerTests.sample
    send = test_server.ServerTests.send

    def message(self, batch, token=None):
        return dict(type='history_batch', token=token or self.client['token'], encoding='gzip+base64',
                    data=base64.b64encode(gzip.compress(json.dumps(batch).encode())).decode())

    async def send_history(self, batch=None, message=None):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.client['port'])
        try:
            writer.write(encode_frame(message or self.message(batch)))
            await writer.drain()
            head = await asyncio.wait_for(reader.readexactly(4), 5)
            return json.loads(await reader.readexactly(struct.unpack('!I', head)[0]))
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_history_never_changes_live_state_or_claims_commands(self):
        from alarms import AlarmEngine
        engine = AlarmEngine(self.db, self.config)
        current = self.sample()
        current['data']['active_alarms'] = []
        current['data']['last_poll_at'] = datetime.now(timezone.utc).isoformat()
        await self.send(current)
        before = self.db.inspect()['latest']
        old = self.sample(captured_at=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat())
        with patch.object(self.db, 'claim_control_command', side_effect=AssertionError('history claimed command')):
            ack = await self.send_history([old, self.sample('trap')])
        self.assertTrue(ack['ok'])
        self.assertNotIn('control_command', ack)
        self.assertEqual(self.db.inspect()['latest'], before)
        engine.tick()
        with closing(self.db.connect()) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM alarm_events WHERE rule_key='device_alarms'").fetchone()[0], 0)
        self.assertEqual(self.db.inspect()['total_samples'], 3)

    async def test_history_ack_retry_is_idempotent_and_rate_limited(self):
        batch = [self.sample(), self.sample('trap')]
        first = await self.send_history(batch)
        self.assertTrue(first['ok'])
        busy = await self.send_history(batch)
        self.assertFalse(busy['ok'])
        self.assertGreaterEqual(busy['retry_after'], 1)
        self.receiver.history_next.clear()
        self.assertEqual(await self.send_history(batch), first)
        self.assertEqual(self.db.inspect()['total_samples'], 2)
        self.assertEqual(self.db.inspect()['latest'], [])
        self.assertEqual(self.db.inspect()['recent_sessions'], [])

    async def test_conflict_or_storage_failure_never_acknowledges_batch(self):
        original = self.sample()
        await self.send(original)
        conflicting = json.loads(json.dumps(original))
        conflicting['data']['connected'] = False
        with self.assertRaises(asyncio.IncompleteReadError):
            await self.send_history([self.sample(), conflicting])
        self.assertEqual(self.db.inspect()['total_samples'], 1)
        self.receiver.history_next.clear()
        with patch.object(self.db, 'save_history', side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(asyncio.IncompleteReadError):
                await self.send_history([self.sample()])
        self.assertEqual(self.db.inspect()['total_samples'], 1)

    async def test_invalid_history_is_rejected_before_writing(self):
        for message in [self.message([self.sample()], token='wrong'),
                        self.message([self.sample(device_id='forbidden')]),
                        self.message([self.sample()] * 101),
                        dict(self.message([]), data='not-base64'),
                        dict(self.message([]), data=base64.b64encode(gzip.compress(b'x'*(MAX_FRAME+1))).decode())]:
            self.receiver.history_next.clear()
            with self.assertRaises(asyncio.IncompleteReadError):
                await self.send_history(message=message)
        with self.assertRaises(Rejected):
            decode_history(self.message([self.sample()] * 2), self.config['collectors'])
        self.assertEqual(self.db.inspect()['total_samples'], 0)

    async def test_slow_history_does_not_block_live_ack(self):
        entered, release = threading.Event(), threading.Event()
        save = self.db.save_history
        def slow(identity, payloads):
            entered.set()
            release.wait(5)
            return save(identity, payloads)
        with patch.object(self.db, 'save_history', side_effect=slow):
            pending = asyncio.create_task(self.send_history([self.sample()]))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                self.receiver.history_inflight = 2
                busy = await self.send_history([self.sample()])
                self.assertFalse(busy['ok'])
                live = self.sample()
                self.assertTrue((await asyncio.wait_for(self.send(live), 2))['ok'])
                self.assertEqual(self.db.inspect()['latest'][0]['sample_id'], live['sample_id'])
            finally:
                self.receiver.history_inflight = 1
                release.set()
                self.assertTrue((await pending)['ok'])

    async def test_twelve_collectors_reconnect_live_first_then_paced_history(self):
        workers, boxes, latest_ids, calls = [], [], {}, {}
        original_save = self.db.save_history
        def record(identity, batch):
            calls.setdefault(identity, []).append((time.monotonic(), len(batch)))
            return original_save(identity, batch)
        try:
            with patch.object(self.db, 'save_history', side_effect=record):
                for index in range(12):
                    token, identity, device = 'history-test-' + str(index), 'c' + str(index), 'd' + str(index)
                    self.config['collectors'].append(dict(id=identity, token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                        devices=[dict(site_id=self.client['site_id'], device_id=device)]))
                    config = dict(self.client, token=token, device_id=device)
                    box = Outbox(self.root / ('queue' + str(index) + '.db'))
                    for _ in range(120):
                        old = self.sample(device_id=device, captured_at=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat())
                        box.put(destination(config), old)
                    latest = self.sample(device_id=device)
                    latest_ids[device] = latest['sample_id']
                    box.put(destination(config), latest)
                    worker = UploadWorker(box, lambda _: None)
                    worker.configure(config)
                    workers.append(worker); boxes.append(box)
                for worker in workers:
                    worker.start()
                deadline = time.monotonic() + 4
                while len(self.db.inspect()['latest']) < 12 and time.monotonic() < deadline:
                    await asyncio.sleep(.05)
                self.assertEqual({r['device_id']: r['sample_id'] for r in self.db.inspect()['latest']}, latest_ids)
                self.assertTrue(all(box.count() >= 120 for box in boxes))
                deadline = time.monotonic() + 25
                while any(box.count() for box in boxes) and time.monotonic() < deadline:
                    await asyncio.sleep(.1)
                self.assertEqual(sum(box.count() for box in boxes), 0)
                self.assertEqual(self.db.inspect()['total_samples'], 12 * 121)
                self.assertEqual({r['device_id']: r['sample_id'] for r in self.db.inspect()['latest']}, latest_ids)
                for entries in calls.values():
                    self.assertEqual([size for _, size in entries], [100, 20])
                    self.assertGreaterEqual(entries[1][0] - entries[0][0], 5)
                self.assertEqual(len(calls), 12)
        finally:
            for worker in workers:
                worker.stop()
            for worker in workers:
                if worker.ident is not None:
                    await asyncio.to_thread(worker.join, 5)
                    self.assertFalse(worker.is_alive())
                    self.assertFalse(worker.history_thread.is_alive())

    async def test_worker_retains_history_when_commit_ack_is_lost(self):
        box = Outbox(self.root/'lost-ack.db')
        old, latest = self.sample(), self.sample()
        box.put(destination(self.client), old)
        box.put(destination(self.client), latest)
        committed = threading.Event()
        original = self.db.save_history
        calls = []
        def lose_ack(identity, batch):
            original(identity, batch)
            calls.append(len(batch))
            if len(calls) == 1:
                committed.set()
                raise ConnectionError('simulate disconnect after commit')
        events = []
        worker = UploadWorker(box, lambda _: None, events.append)
        worker.configure(self.client)
        try:
            with patch.object(self.db, 'save_history', side_effect=lose_ack):
                worker.start()
                self.assertTrue(await asyncio.to_thread(committed.wait, 8))
                self.assertEqual(box.count(), 1)
                self.assertEqual(self.db.inspect()['total_samples'], 2)
                deadline = time.monotonic() + 10
                while box.count() and time.monotonic() < deadline:
                    await asyncio.sleep(.05)
                self.assertEqual(box.count(), 0)
                self.assertEqual(calls, [1, 1])
                self.assertEqual(self.db.inspect()['total_samples'], 2)
                self.assertEqual(self.db.inspect()['latest'][0]['sample_id'], latest['sample_id'])
                self.assertTrue(events)
                self.assertTrue(all(event['ok'] for event in events))
        finally:
            worker.stop()
            await asyncio.to_thread(worker.join, 5)

    async def test_outbox_migration_latest_selection_and_stale_traps(self):
        path = self.root/'old-queue.db'
        old = self.sample()
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE queue (seq INTEGER PRIMARY KEY, id TEXT UNIQUE, destination TEXT, payload TEXT, size INTEGER)')
            text = json.dumps(old)
            db.execute('INSERT INTO queue(id,destination,payload,size) VALUES(?,?,?,?)',
                       (old['sample_id'], destination(self.client), text, len(text)))
        box = Outbox(path)
        self.assertIsNone(box.live(destination(self.client), 30))
        self.assertEqual(box.history_batch(destination(self.client))[0]['sample_id'], old['sample_id'])
        first, latest = self.sample(), self.sample()
        box.put(destination(self.client), first)
        box.put(destination(self.client), latest)
        self.assertEqual(box.live(destination(self.client), 30)[0], latest['sample_id'])
        self.assertEqual(len(box.history_batch(destination(self.client))), 2)
        stale = self.sample('trap', captured_at=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat())
        box.put(destination(self.client), stale)
        box.acknowledge(latest['sample_id'])
        self.assertIsNone(box.live(destination(self.client), 30))
        self.assertEqual(len(box.history_batch(destination(self.client))), 3)
        self.assertEqual(box.history_batch(destination(dict(self.client, token='other'))), [])


if __name__ == '__main__':
    unittest.main()
