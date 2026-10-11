import unittest
from pathlib import Path
from unittest.mock import patch
import app_paths


class ReleasePathsTests(unittest.TestCase):
    def test_frozen_workers_are_dedicated_exes(self):
        with patch.object(app_paths.sys,'frozen',True,create=True):
            root=Path('C:/Trading App')
            self.assertEqual(app_paths.worker_command('live',root),[str(root/'trader.exe')])
            self.assertEqual(app_paths.worker_command('auto_research',root),[str(root/'research.exe')])

    def test_source_worker_uses_python(self):
        with patch.object(app_paths.sys,'frozen',False,create=True):
            command=app_paths.worker_command('live',Path('missing-test-directory'))
            self.assertEqual(command[0],app_paths.sys.executable)
            self.assertTrue(command[-1].endswith('live.py'))


if __name__=='__main__':unittest.main()
