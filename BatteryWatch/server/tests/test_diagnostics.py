import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagnostics import inspect_config
from server import initialize


class DiagnosticsTests(unittest.TestCase):
    def test_missing_config_and_local_defaults_without_secret_disclosure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'server.local.json'
            self.assertFalse(inspect_config(path)['ok'])
            credentials = initialize(path, 'site', 'device')
            token = json.loads(credentials.read_text())['token']
            result = inspect_config(path)
            self.assertTrue(result['ok'])
            self.assertGreater(result['warnings'], 0)
            self.assertNotIn(token, json.dumps(result))
            self.assertEqual(result['checks'][-1]['name'], 'firebase')

    def test_missing_tls_file_and_android_project_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'server.local.json'
            initialize(path, 'site', 'device')
            config = json.loads(path.read_text())
            config['tls'] = dict(certfile='missing.pem', keyfile='missing.key')
            config['push'] = dict(enabled=True, service_account='service.json')
            secret = 'DO-NOT-PRINT-PRIVATE-KEY'
            (root / 'service.json').write_text(json.dumps(dict(type='service_account', project_id='server-project', client_email='test@example.invalid', private_key=secret)))
            path.write_text(json.dumps(config))
            android = root / 'android.json'
            android.write_text(json.dumps(dict(project_info=dict(project_id='different-project'), client=[dict(client_info=dict(android_client_info=dict(package_name='com.batterywatch.monitor.debug')))])))
            report = inspect_config(path, android)
            self.assertFalse(report['ok'])
            errors = {c['name'] for c in report['checks'] if c['level'] == 'error'}
            self.assertTrue({'tls', 'android_firebase'} <= errors)
            self.assertNotIn(secret, json.dumps(report))
