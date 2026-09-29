import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_demo import self_test, demo_settings


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_local_pipeline(self):
        result = await self_test()
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['checks']), 12)
        self.assertEqual(result['external_messages_sent'], 0)


class DemoSettingsTests(unittest.TestCase):
    def test_demo_credentials_persist_and_production_directory_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                demo_settings(root, 19443, 18443)
            config, collector, viewer = demo_settings(root / 'demo', 19443, 18443)
            again, collector2, viewer2 = demo_settings(root / 'demo', 19444, 18444)
            self.assertEqual((collector, viewer), (collector2, viewer2))
            self.assertEqual(again['api']['host'], '127.0.0.1')
            self.assertEqual(again['api']['port'], 18444)
            self.assertFalse(config['push']['enabled'])
