import asyncio
import logging
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from communication_log import PeerLog, control_path, write_control, apply_control, watch

class Writer:
    def get_extra_info(self, key): return ('192.0.2.15',54321)

class CommunicationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger=logging.getLogger('batterywatch')
        self.level=self.logger.level
        self.addCleanup(self.logger.setLevel,self.level)

    def test_direction_and_peer(self):
        with self.assertLogs('batterywatch',level='DEBUG') as captured:
            app=PeerLog(self.logger,Writer(),'앱')
            app.debug('API request route=/api/v1/devices')
            app.debug('API response status=200')
            upload=PeerLog(self.logger,Writer(),'수집기')
            upload.debug('UPLOAD frame bytes=123')
            upload.debug('UPLOAD ack duplicate=False')
        text='\n'.join(captured.output)
        for value in ('서버 <- 앱(192.0.2.15)','서버 -> 앱(192.0.2.15)',
                      '서버 <- 수집기(192.0.2.15)','서버 -> 수집기(192.0.2.15)'):
            self.assertIn(value,text)

    async def test_runtime_switch_and_invalid_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=control_path(Path(directory)/'server.local.json')
            write_control(path,True)
            self.logger.setLevel(logging.INFO)
            stop=asyncio.Event()
            job=asyncio.create_task(watch(path,stop))
            try:
                for _ in range(100):
                    if self.logger.isEnabledFor(logging.DEBUG): break
                    await asyncio.sleep(.01)
                self.assertTrue(self.logger.isEnabledFor(logging.DEBUG))
                write_control(path,False)
                for _ in range(200):
                    if not self.logger.isEnabledFor(logging.DEBUG): break
                    await asyncio.sleep(.01)
                self.assertFalse(self.logger.isEnabledFor(logging.DEBUG))
                self.assertTrue(self.logger.isEnabledFor(logging.WARNING))
                path.write_text('{"enabled":"false"}',encoding='utf-8')
                with self.assertRaises(ValueError): apply_control(path)
                self.assertEqual(self.logger.level,logging.INFO)
            finally:
                stop.set()
                await asyncio.wait_for(job,2)
