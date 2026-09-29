"""Loopback-only simulated collector, real receiver/API, and integration checks."""
import argparse
import asyncio
from contextlib import closing
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import secrets
import struct
import tempfile
import time
import uuid

from alarms import AlarmEngine, monitor
from mobile_api import MobileApi
from push import Dispatcher
from receiver import Receiver
from storage import Storage


GRANT = dict(site_id='demo-site', device_id='DEMO-simulated-battery')


def make_config(root, upload_port=0, api_port=18443):
    collector_token, viewer_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    config = dict(host='127.0.0.1', port=upload_port, database=str(root / 'demo.sqlite3'), tls={},
                  max_connections=8, idle_timeout=30, frame_timeout=5, max_frame_bytes=1024 * 1024,
                  collectors=[dict(id='demo-collector', token_sha256=hashlib.sha256(collector_token.encode()).hexdigest(), devices=[GRANT])],
                  api=dict(enabled=True, host='127.0.0.1', port=api_port, viewers=[
                      dict(id='demo-viewer', token_sha256=hashlib.sha256(viewer_token.encode()).hexdigest(), devices=[GRANT])]),
                  alarms=dict(scan_seconds=1, stale_seconds=10, rules=[
                      dict(id='DEMO-low-soc', metric='soc', direction='low', threshold=20, hysteresis=5, duration_seconds=3)]),
                  push=dict(enabled=False))
    return config, collector_token, viewer_token


def sample(soc=80, connected=True, stamp=None):
    stamp = stamp or datetime.now(timezone.utc)
    iso = stamp.isoformat(timespec='microseconds')
    return dict(schema_version=1, sample_id=str(uuid.uuid4()), **GRANT, kind='snapshot', captured_at=iso,
                data=dict(source_version='SIMULATED DEMO - NOT REAL MEASUREMENTS',
                          site_name='DEMO simulated site', system_name='DEMO simulated battery',
                          connected=connected, last_poll_ok=connected, last_poll_at=iso, raw_oids={},
                          module_map={'1': dict(model='SIMULATED')},
                          module_data={'1': dict(soc=soc, soh=98, volt=51.2, current=-2.5,
                                                 cells=[3.2 + (n % 3) * 0.01 for n in range(16)],
                                                 temps=[25 + n % 3 for n in range(16)])}, active_alarms=[]))


class LocalSystem:
    def __init__(self, config, collector_token, viewer_token, ephemeral_api=False):
        self.config, self.collector_token, self.viewer_token = config, collector_token, viewer_token
        self.storage = Storage(config['database'])
        self.engine = AlarmEngine(self.storage, config)
        self.receiver = Receiver(config, self.storage)
        self.api = MobileApi(config, self.storage)
        if ephemeral_api:
            self.api.api['port'] = 0

    async def __aenter__(self):
        await self.receiver.start()
        try:
            await self.api.start()
        except BaseException:
            await self.receiver.close()
            raise
        self.upload_port = self.receiver.server.sockets[0].getsockname()[1]
        self.api_port = self.api.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *args):
        await self.api.close()
        await self.receiver.close()

    async def upload(self, payload):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.upload_port)
        try:
            body = json.dumps(dict(type='upload', token=self.collector_token, payload=payload)).encode()
            writer.write(struct.pack('!I', len(body)) + body)
            await writer.drain()
            size = struct.unpack('!I', await asyncio.wait_for(reader.readexactly(4), 5))[0]
            ack = json.loads(await asyncio.wait_for(reader.readexactly(size), 5))
            if not ack.get('ok') or ack.get('sample_id') != payload['sample_id']:
                raise RuntimeError('Collector ACK failed')
            return ack
        finally:
            writer.close()
            await writer.wait_closed()

    async def request(self, path, method='GET', body=None, token=None):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.api_port)
        try:
            data = json.dumps(body).encode() if body is not None else b''
            secret = self.viewer_token if token is None else token
            head = (f'{method} {path} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {secret}\r\n'
                    f'Content-Type: application/json\r\nContent-Length: {len(data)}\r\n\r\n').encode()
            writer.write(head + data)
            await writer.drain()
            raw = await asyncio.wait_for(reader.read(), 5)
            header, response = raw.split(b'\r\n\r\n', 1)
            return int(header.split()[1]), json.loads(response)
        finally:
            writer.close()
            await writer.wait_closed()


async def self_test():
    """Full TCP -> DB -> alarm -> HTTP -> ACK -> delivery-queue round trip."""
    passed = []
    def check(condition, label):
        if not condition:
            raise RuntimeError('Integration check failed: ' + label)
        passed.append(label)

    with tempfile.TemporaryDirectory(prefix='batterywatch-selftest-') as directory:
        root = Path(directory)
        config, collector, viewer = make_config(root)
        query = '?site_id=' + GRANT['site_id'] + '&device_id=' + GRANT['device_id']
        async with LocalSystem(config, collector, viewer, ephemeral_api=True) as system:
            installation = str(uuid.uuid4())
            code, _ = await system.request('/api/v1/push-devices/' + installation, 'PUT', {'token': 'SIMULATED-not-a-firebase-token'})
            check(code == 200, 'HTTP push registration')
            base = datetime.now(timezone.utc) - timedelta(seconds=8)
            normal = sample(stamp=base)
            await system.upload(normal)
            duplicate = await system.upload(normal)
            check(duplicate.get('duplicate') is True, 'TCP ACK and duplicate suppression')
            code, latest = await system.request('/api/v1/snapshot' + query)
            check(code == 200 and latest['fresh'] and latest['payload']['data']['module_data']['1']['soc'] == 80,
                  'TCP upload visible through Android snapshot API')
            for seconds in (1, 5):
                payload = sample(10, stamp=base + timedelta(seconds=seconds))
                await system.upload(payload)
                system.engine.tick((base + timedelta(seconds=seconds)).timestamp())
            code, alarms = await system.request('/api/v1/alarms' + query)
            check(code == 200 and len(alarms['active']) == 1, 'Sustained low SOC raises one alarm')
            event = alarms['active'][0]['event_id']
            code, _ = await system.request('/api/v1/acknowledgements', 'POST', {'event_id': event})
            _, acknowledged = await system.request('/api/v1/alarms' + query)
            check(code == 200 and len(acknowledged['active']) == 1 and acknowledged['events'][0]['acknowledged_at'] is not None,
                  'User acknowledgement persists without clearing alarm')

            class FakeSender:
                def __init__(self):
                    self.calls = 0
                def send(self, token, event):
                    self.calls += 1
                    if self.calls == 1:
                        raise OSError('SIMULATED delivery outage')
            sender = FakeSender()
            dispatcher = Dispatcher(system.storage, config, sender)
            clock = time.time()
            dispatcher.tick(clock)
            dispatcher.tick(clock + 1)
            dispatcher.tick(clock + 6)
            check(sender.calls == 2, 'Delivery queue retries after failure (fake sender; no FCM sent)')
            recovery = sample(80, stamp=base + timedelta(seconds=6))
            await system.upload(recovery)
            system.engine.tick((base + timedelta(seconds=6)).timestamp())
            _, cleared = await system.request('/api/v1/alarms' + query)
            check(not cleared['active'] and any(e['transition'] == 'cleared' for e in cleared['events']), 'Recovery persists and is visible through API')
            code, history = await system.request('/api/v1/history' + query)
            check(code == 200 and len(history['history']) == 4 and history['history'][0]['module_data']['1']['soc'] == 80,
                  'History preserves actual measurements, without duplicate rows')
            system.engine.tick(time.time() + 20)
            _, stale = await system.request('/api/v1/alarms' + query)
            check(any(a['rule_key'] == 'communication' for a in stale['active']), 'Communication timeout detected without further uploads')
            code, _ = await system.request('/api/v1/devices', token=collector)
            check(code == 401, 'Collector credentials cannot query Android API')
            code, _ = await system.request('/api/v1/snapshot?site_id=other&device_id=other')
            check(code == 403, 'Cross-device read denied')
            storage_path = system.storage.path
        reopened = Storage(storage_path)
        with closing(reopened.connect()) as db:
            check(db.execute('SELECT count(*) FROM alarm_events').fetchone()[0] == 3, 'Events survive server restart')
    return dict(ok=True, checks=passed, external_messages_sent=0)


def demo_settings(root, upload_port, api_port):
    marker = root / 'demo-marker.json'
    if root.exists():
        if not marker.exists() or json.loads(marker.read_text()) != {'purpose': 'BatteryWatch local simulated demo'}:
            raise ValueError('Refusing to use a directory without the demo marker')
        saved = json.loads((root / 'demo-credentials.local.json').read_text())
    else:
        root.mkdir(parents=True)
        config, collector, viewer = make_config(root, upload_port, api_port)
        saved = dict(collector=collector, viewer=viewer)
        (root / 'demo-credentials.local.json').write_text(json.dumps(saved), encoding='utf-8')
        marker.write_text(json.dumps({'purpose': 'BatteryWatch local simulated demo'}), encoding='utf-8')
    config, _, _ = make_config(root, upload_port, api_port)
    config['collectors'][0]['token_sha256'] = hashlib.sha256(saved['collector'].encode()).hexdigest()
    config['api']['viewers'][0]['token_sha256'] = hashlib.sha256(saved['viewer'].encode()).hexdigest()
    connection = root / 'android-connection.local.json'
    connection.write_text(json.dumps(dict(server_url=f'http://127.0.0.1:{api_port}',
                                         emulator_url=f'http://10.0.2.2:{api_port}', token=saved['viewer']), indent=2), encoding='utf-8')
    return config, saved['collector'], saved['viewer']


async def demo(root, upload_port=19443, api_port=18443, seconds=None):
    config, collector, viewer = demo_settings(root, upload_port, api_port)
    async with LocalSystem(config, collector, viewer) as system:
        print('SIMULATED DEMO ONLY. No real battery or Firebase connection.', flush=True)
        print(f'Android API: http://127.0.0.1:{system.api_port}', flush=True)
        print('App settings (local test token):', root / 'android-connection.local.json', flush=True)
        stop = asyncio.Event()
        monitor_task = asyncio.create_task(monitor(system.engine, stop))
        started, previous = time.monotonic(), None
        try:
            while seconds is None or time.monotonic() - started < seconds:
                phase = int(time.monotonic() - started) // 15 % 4
                label = ('normal', 'low SOC (SIMULATED)', 'recovered', 'communication failure (SIMULATED)')[phase]
                if label != previous:
                    print(label, flush=True)
                    previous = label
                await system.upload(sample(10 if phase == 1 else 80, connected=phase != 3))
                await asyncio.sleep(2)
        finally:
            stop.set()
            await monitor_task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true', help='Run isolated end-to-end checks and exit')
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).with_name('demo-data'))
    parser.add_argument('--api-port', type=int, default=18443)
    parser.add_argument('--upload-port', type=int, default=19443)
    parser.add_argument('--seconds', type=int, help='Stop demo automatically after this many seconds')
    args = parser.parse_args()
    if not 1 <= args.api_port <= 65535 or not 1 <= args.upload_port <= 65535 or args.api_port == args.upload_port:
        parser.error('Use different ports in the range 1..65535')
    if args.seconds is not None and args.seconds < 1:
        parser.error('--seconds must be positive')
    try:
        if args.self_test:
            print(json.dumps(asyncio.run(self_test()), indent=2))
        else:
            asyncio.run(demo(args.data_dir.resolve(), args.upload_port, args.api_port, args.seconds))
    except KeyboardInterrupt:
        print('Demo stopped.')
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
