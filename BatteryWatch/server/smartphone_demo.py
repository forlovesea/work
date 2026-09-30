"""Ten-module smartphone demonstration using an isolated persistent database."""
import asyncio
import copy
from datetime import datetime, timezone
import logging
import math
from pathlib import Path
import uuid

GRANT = {'site_id': 'DEMO-site', 'device_id': 'DEMO-battery-10-modules'}
LOG = logging.getLogger('batterywatch.demo')


def prepare(config):
    if not config.get('api', {}).get('enabled') or not config['api'].get('viewers'):
        raise ValueError('Enable Android API before using --demo-data')
    result = copy.deepcopy(config)
    original = Path(config['database'])
    target = original.with_name('smartphone-demo.sqlite3')
    if target.resolve() == original.resolve():
        raise ValueError('Production database must not be named smartphone-demo.sqlite3')
    result['database'] = str(target)
    result['push'] = {'enabled': False}
    result['alarms'] = {}
    for viewer in result['api']['viewers']:
        viewer['devices'] = [dict(GRANT)]
    # No real collector is accepted by this demonstration server.
    result['collectors'] = []
    return result


def sample(tick=0):
    stamp = datetime.now(timezone.utc).isoformat(timespec='microseconds')
    modules = {}
    for n in range(1, 11):
        wave = math.sin(tick / 6 + n)
        cells = [round(3.25 + n * .002 + j * .001 + wave * .005, 3) for j in range(15)]
        modules[str(n)] = dict(soc=round(75 + n + wave, 1), soh=round(99 - n * .2, 1),
                               volt=round(sum(cells), 3), current=round(-2 - n * .1 + wave * .2, 2),
                               cells=cells, temps=[round(24 + n * .3 + j * .05 + wave * .3, 1) for j in range(15)])
    return dict(schema_version=1, sample_id=str(uuid.uuid4()), **GRANT, kind='snapshot', captured_at=stamp,
                data=dict(source_version='SIMULATED DEMO - NOT REAL MEASUREMENTS',
                          site_name='DEMO 테스트 현장', system_name='DEMO 배터리 모듈 10개 (가상 데이터)',
                          connected=True, last_poll_ok=True, last_poll_at=stamp, raw_oids={},
                          module_map={str(n): {'row_index': n, 'model': 'SIMULATED'} for n in range(1, 11)}, module_data=modules,
                          active_alarms=[]))


async def feed(storage, stop):
    session = 'demo-' + uuid.uuid4().hex
    tick = 0
    try:
        while not stop.is_set():
            await asyncio.to_thread(storage.save, 'DEMO-generator', sample(tick), session, 'internal-demo')
            LOG.debug('DEMO saved modules=10 tick=%d', tick)
            tick += 1
            try:
                await asyncio.wait_for(stop.wait(), 5)
            except asyncio.TimeoutError:
                pass
    except Exception as exc:
        LOG.error('DEMO generator stopped reason=%s', type(exc).__name__)
        stop.set()
        raise
    finally:
        await asyncio.to_thread(storage.disconnected, session)
