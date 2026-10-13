import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from live import Store
from collection_log import safe_error


class StoreRetryTests(unittest.TestCase):
    def test_transient_reader_lock_does_not_abort_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'status.json';store=Store(path)
            store.data={'state':'OLD'};store.save();store.data={'state':'한글 완료'}
            replace=os.replace
            calls=[]
            def locked(source,target):
                calls.append(source)
                if len(calls)<3:raise PermissionError('locked')
                return replace(source,target)
            with patch('live.os.replace',side_effect=locked),patch('live.time.sleep'):
                store.save()
            self.assertEqual(Store(path).data,store.data)
            self.assertEqual(len(calls),3)
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])

    def test_persistent_failure_preserves_last_complete_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'status.json';store=Store(path)
            store.data={'state':'OLD'};store.save();store.data={'state':'NEW'}
            with patch('live.os.replace',side_effect=PermissionError('private-path')) as replace,patch('live.time.sleep'):
                with self.assertRaises(PermissionError):store.save()
            self.assertEqual(replace.call_count,21)
            self.assertEqual(Store(path).data,{'state':'OLD'})
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])
            self.assertEqual(safe_error(PermissionError('private-path'))['error_code'],'LOCAL_FILE_ACCESS')
