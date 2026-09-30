import asyncio
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import Storage
from alarms import AlarmEngine, configure
from mobile_api import MobileApi, query, mutate
from push import Dispatcher, InvalidToken


class AlarmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = Storage(Path(self.temp.name) / 'data.sqlite3')
        self.viewer = dict(id='viewer', token_sha256=hashlib.sha256(b'view-token').hexdigest(),
                           devices=[dict(site_id='site', device_id='battery')])
        self.config = dict(tls={}, collectors=[dict(id='collector', token_sha256='0' * 64,
                           devices=self.viewer['devices'])], api=dict(enabled=True, host='127.0.0.1', port=8443,
                           viewers=[self.viewer]), alarms=dict(stale_seconds=60, rules=[
                               dict(id='low_soc', metric='soc', direction='low', threshold=20,
                                    hysteresis=5, duration_seconds=10)]))
        self.engine = AlarmEngine(self.storage, self.config)
        self.installation = str(uuid.uuid4())

    def sample(self, stamp, soc=10, **changes):
        iso = datetime.fromtimestamp(stamp, timezone.utc).isoformat()
        data = dict(connected=True, last_poll_ok=True, last_poll_at=iso,
                    module_data={'1': dict(soc=soc, cells=[3.2, 3.3], temps=[25, 26])}, active_alarms=[])
        data.update(changes)
        payload = dict(schema_version=1, sample_id=str(uuid.uuid4()), site_id='site', device_id='battery',
                       kind='snapshot', captured_at=iso, data=data)
        self.storage.save('collector', payload, 'session', 'local')
        return payload

    def events(self):
        with closing(self.storage.connect()) as db:
            return [dict(r) for r in db.execute('SELECT * FROM alarm_events ORDER BY created_at')]

    def raise_alarm(self):
        self.sample(1000); self.engine.tick(1000)
        self.sample(1011); self.engine.tick(1011)

    def test_duration_hysteresis_duplicate_and_ack_not_clear(self):
        payload = self.sample(1000); self.engine.tick(1000)
        self.storage.save('collector', payload, 'session', 'local')
        self.engine.tick(1020)  # Same measurement cannot satisfy duration.
        self.assertEqual(self.events(), [])
        self.sample(1021); self.engine.tick(1021)
        self.assertEqual([r['transition'] for r in self.events()], ['raised'])
        event = self.events()[0]
        self.assertEqual(mutate(self.storage, self.viewer, 'POST', '/api/v1/acknowledgements', {'event_id': event['event_id']})[0], 200)
        params = dict(site_id=['site'], device_id=['battery'])
        result = query(self.storage, self.viewer, '/api/v1/alarms', params)[1]
        self.assertEqual(len(result['active']), 1)
        self.assertIsNotNone(result['events'][0]['acknowledged_at'])
        self.sample(1022, 23); self.engine.tick(1022)
        self.assertEqual(len(self.events()), 1)
        self.sample(1023, 26); self.engine.tick(1023)
        self.assertEqual([r['transition'] for r in self.events()], ['raised', 'cleared'])

    def test_stale_unknown_old_replay_and_restart(self):
        self.raise_alarm()
        self.engine.tick(1080)
        self.assertEqual(len(self.events()), 2)  # SOC + communication, no false clear.
        restarted = AlarmEngine(self.storage, self.config)
        restarted.tick(1081)
        self.assertEqual(len(self.events()), 2)
        self.sample(1005, 90); restarted.tick(1082)
        self.assertEqual(len(self.events()), 2)
        self.sample(1083, None); restarted.tick(1083)
        self.assertEqual(self.events()[-1]['rule_key'], 'communication')
        self.assertEqual(self.events()[-1]['transition'], 'cleared')
        with closing(self.storage.connect()) as db:
            self.assertEqual(db.execute("SELECT active FROM alarm_state WHERE rule_key='low_soc:1:0'").fetchone()[0], 1)

    def test_missing_reading_breaks_pending_duration(self):
        self.sample(1000); self.engine.tick(1000)
        self.sample(1005, None); self.engine.tick(1005)
        self.sample(1011); self.engine.tick(1011)
        self.assertEqual(self.events(), [])
        self.sample(1022); self.engine.tick(1022)
        self.assertEqual(len(self.events()), 1)

    def test_never_connected_device_detected_without_upload(self):
        self.engine.started = 1000
        self.engine.tick(1059)
        self.assertEqual(self.events(), [])
        self.engine.tick(1061)
        self.assertEqual(self.events()[0]['rule_key'], 'communication')

    def test_push_retry_invalid_token_and_grant_revocation(self):
        self.assertEqual(mutate(self.storage, self.viewer, 'PUT', '/api/v1/push-devices/' + self.installation, {'token': 'x' * 30})[0], 200)
        self.raise_alarm()
        class Sender:
            calls = 0
            def send(inner, token, event):
                inner.calls += 1
                if inner.calls == 1:
                    raise OSError('network down')
        sender = Sender()
        dispatcher = Dispatcher(self.storage, self.config, sender)
        dispatcher.tick(1011)
        dispatcher.tick(1012)
        self.assertEqual(sender.calls, 1)
        dispatcher.tick(1016)
        dispatcher.tick(1020)
        self.assertEqual(sender.calls, 2)
        self.sample(1021, 90); self.engine.tick(1021)
        self.viewer['devices'] = []
        dispatcher.tick(1021)
        self.assertEqual(sender.calls, 2)
        self.viewer['devices'] = [dict(site_id='site', device_id='battery')]
        self.sample(1022); self.engine.tick(1022)
        self.sample(1033); self.engine.tick(1033)
        sender.send = lambda *args: (_ for _ in ()).throw(InvalidToken())
        dispatcher.tick(1033)
        with closing(self.storage.connect()) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM push_devices').fetchone()[0], 0)

    def test_scope_ownership_and_unregister(self):
        route = '/api/v1/push-devices/' + self.installation
        self.assertEqual(mutate(self.storage, self.viewer, 'PUT', route, {'token': 'a' * 30})[0], 200)
        other = dict(id='other', devices=[])
        self.assertEqual(mutate(self.storage, other, 'DELETE', route, {})[0], 403)
        self.raise_alarm()
        self.assertEqual(query(self.storage, other, '/api/v1/alarms', dict(site_id=['site'],device_id=['battery']))[0], 403)
        self.assertEqual(mutate(self.storage, other, 'POST', '/api/v1/acknowledgements', {'event_id': self.events()[0]['event_id']})[0], 403)
        self.assertEqual(mutate(self.storage, self.viewer, 'DELETE', route, {})[0], 200)
        with closing(self.storage.connect()) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM push_outbox').fetchone()[0], 0)

    def test_bad_rule_rejected(self):
        self.config['alarms']['rules'][0]['threshold'] = float('nan')
        with self.assertRaises(ValueError): configure(self.config)

    def test_cell_rules_disabled_rules_and_missing_cells(self):
        self.config['alarms']['rules'] = [
            dict(id='temp', metric='temps', direction='high', threshold=40, hysteresis=3),
            dict(id='delta', metric='cell_delta', direction='high', threshold=0.2, hysteresis=0.05),
            dict(id='disabled', metric='soc', direction='low', threshold=90, enabled=False)]
        self.engine = AlarmEngine(self.storage, self.config)
        self.sample(1000, module_data={'1': dict(soc=10, temps=[45, None], cells=[3.1, 3.5])})
        self.engine.tick(1000)
        self.assertEqual({r['rule_key'] for r in self.events()}, {'temp:1:1', 'delta:1:0'})
        self.sample(1001, module_data={'1': dict(temps=[None], cells=[3.2, None])})
        self.engine.tick(1001)
        self.assertEqual(len(self.events()), 2)
        self.sample(1002, module_data={'1': dict(temps=[36], cells=[3.2, 3.3])})
        self.engine.tick(1002)
        self.assertEqual([e['transition'] for e in self.events()].count('cleared'), 2)

    def test_future_measurement_never_clears_alarm(self):
        self.raise_alarm()
        self.sample(1200, 95)
        self.engine.tick(1012)
        self.assertFalse(any(e['rule_key'] == 'low_soc:1:0' and e['transition'] == 'cleared' for e in self.events()))

    def test_history_preserves_measurements_and_unknown_alarm_count(self):
        self.sample(1000, active_alarms=None, module_map=None)
        result = query(self.storage, self.viewer, '/api/v1/history', dict(site_id=['site'],device_id=['battery']))[1]
        self.assertEqual(result['history'][0]['module_data']['1']['cells'], [3.2, 3.3])
        devices = query(self.storage, self.viewer, '/api/v1/devices', {})[1]['devices']
        self.assertIsNone(devices[0]['alarm_count'])


class ApiHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Storage(Path(self.temp.name) / 'test.db')
        self.viewer = dict(id='viewer', token_sha256=hashlib.sha256(b'view-token').hexdigest(), devices=[dict(site_id='site',device_id='battery')])
        config = dict(tls={}, collectors=[dict(token_sha256='0'*64)], api=dict(enabled=True,port=8443,host='127.0.0.1',viewers=[self.viewer]))
        self.api = MobileApi(config, self.db)
        self.api.api['port'] = 0
        await self.api.start()
        self.port = self.api.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.api.close()
        self.temp.cleanup()

    async def request(self, method='GET', route='/api/v1/devices', body=None, token='view-token', extra=''):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        data = json.dumps(body).encode() if body is not None else b''
        request = f'{method} {route} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {token}\r\nContent-Length: {len(data)}\r\n{extra}\r\n'.encode() + data
        writer.write(request); await writer.drain()
        result = await reader.read()
        writer.close(); await writer.wait_closed()
        header, payload = result.split(b'\r\n\r\n', 1)
        return int(header.split()[1]), json.loads(payload)

    async def test_http_auth_mutation_and_malformed_request(self):
        self.assertEqual((await self.request(token='wrong'))[0], 401)
        self.assertEqual((await self.request())[0], 200)
        route = '/api/v1/push-devices/' + str(uuid.uuid4())
        self.assertEqual((await self.request('PUT',route,{'token':'x'*30}))[0], 200)
        self.assertEqual((await self.request('DELETE',route,{}))[0], 200)
        self.assertEqual((await self.request('PUT',route,[]))[0], 400)
        self.assertEqual((await self.request(extra='Transfer-Encoding: chunked\r\n'))[0], 400)

    async def test_debug_metadata_redacts_credentials_and_query(self):
        with self.assertLogs('batterywatch.api', level='DEBUG') as logs:
            self.assertEqual((await self.request(route='/api/v1/devices?secret=PRIVATE_QUERY'))[0], 200)
            self.assertEqual((await self.request(token='PRIVATE_BAD_TOKEN'))[0], 401)
            self.assertEqual((await self.request(route='/PRIVATE_PATH'))[0], 404)
        output='\n'.join(logs.output)
        for expected in ('API connected', 'API response', 'status=200', 'status=401', 'status=404', 'elapsed_ms=', 'route=/api/v1/devices'):
            self.assertIn(expected, output)
        for secret in ('view-token', 'PRIVATE_BAD_TOKEN', 'PRIVATE_QUERY', 'PRIVATE_PATH', 'Authorization'):
            self.assertNotIn(secret, output)
