import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import initialize, managed_process_matches, pid_file_for, start_background


class PlatformSupportTests(unittest.TestCase):
    def test_background_mode_reports_linux_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / 'server.local.json'
            with patch('server.sys.platform', 'win32'):
                with self.assertRaisesRegex(ValueError, 'supported on Linux only'):
                    start_background(config_path)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Managed process control is Linux-only')
class BackgroundServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config_path = self.root / 'server.local.json'
        initialize(self.config_path, 'site-01', 'battery-01')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            self.port = listener.getsockname()[1]
        config = json.loads(self.config_path.read_text(encoding='utf-8'))
        config['port'] = self.port
        self.config_path.write_text(json.dumps(config), encoding='utf-8')

    def tearDown(self):
        subprocess.run(
            [sys.executable, str(ROOT / 'server.py'), '--config', str(self.config_path), 'stop'],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.temp.cleanup()

    def command(self, *arguments):
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / 'server.py'),
                '--config',
                str(self.config_path),
                *arguments,
            ],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )

    def test_background_start_duplicate_restart_and_stop(self):
        started = self.command('run', '--background', '--debug')
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn('started in background', started.stdout)

        pid_file = pid_file_for(self.config_path)
        record = json.loads(pid_file.read_text(encoding='utf-8'))
        original_pid = record['pid']
        self.assertTrue(record['debug'])
        self.assertTrue(managed_process_matches(original_pid, self.config_path))

        duplicate = self.command('run', '--background')
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn('already running', duplicate.stderr)

        restarted = self.command('restart')
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        new_record = json.loads(pid_file.read_text(encoding='utf-8'))
        self.assertTrue(new_record['debug'])
        self.assertTrue(managed_process_matches(new_record['pid'], self.config_path))

        stopped = self.command('stop')
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertFalse(pid_file.exists())


if __name__ == '__main__':
    unittest.main()
