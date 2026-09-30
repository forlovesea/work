import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_demo import make_config, LocalSystem
from smartphone_demo import prepare, sample, feed, GRANT

class SmartphoneDemoTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_ten_modules_and_isolated_database(self):
        with tempfile.TemporaryDirectory() as directory:
            config, collector, viewer = make_config(Path(directory))
            original = copy.deepcopy(config)
            demo = prepare(config)
            self.assertEqual(config, original)
            self.assertNotEqual(config['database'],demo['database'])
            self.assertFalse(demo['push']['enabled'])
            self.assertEqual(demo['collectors'],[])
            async with LocalSystem(demo,collector,viewer,ephemeral_api=True) as system:
                stop=asyncio.Event()
                job=asyncio.create_task(feed(system.storage,stop))
                try:
                    for _ in range(100):
                        status, devices=await system.request('/api/v1/devices')
                        if devices['devices'][0]['available']: break
                        await asyncio.sleep(.01)
                    self.assertEqual(status,200)
                    self.assertEqual(devices['devices'][0]['module_count'],10)
                    route='?site_id='+GRANT['site_id']+'&device_id='+GRANT['device_id']
                    status,response=await system.request('/api/v1/snapshot'+route)
                    self.assertEqual(status,200)
                    self.assertTrue(response['fresh'])
                    data=response['payload']['data']
                    self.assertIn('DEMO',data['system_name'])
                    for n in range(1,11):
                        row=str(data['module_map'][str(n)]['row_index'])
                        self.assertEqual(len(data['module_data'][row]['cells']),15)
                        self.assertEqual(len(data['module_data'][row]['temps']),15)
                    _,history=await system.request('/api/v1/history'+route)
                    self.assertEqual(len(history['history']),1)
                    self.assertNotEqual(sample(0)['data']['module_data'],sample(5)['data']['module_data'])
                finally:
                    stop.set()
                    await job
            self.assertFalse(Path(config['database']).exists())

    def test_requires_enabled_api(self):
        with self.assertRaises(ValueError): prepare({'api': {}})
