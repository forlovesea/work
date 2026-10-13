import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from live import main,ROOT,Store
from test_live import FakeBroker


class CandidateTransportTests(unittest.TestCase):
    def test_korean_reports_survive_cp949_worker_utf8_reader(self):
        for missing in (False,True):
            with self.subTest(missing=missing),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                (root/'etf_config.json').write_bytes((ROOT/'etf_config.json').read_bytes())
                broker=FakeBroker()
                def select(*args,**kwargs):
                    if missing:raise FileNotFoundError('private-path')
                bot=SimpleNamespace(initialize=lambda:None,clock=lambda:broker.now,
                    select=select,selection_details={'rows':[{'name':'한글 ETF'}]})
                state=Store(root/'research'/'auto_status.json')
                state.data={'state':'COLLECTION_FAILED','error_type':'PermissionError'};state.save()
                raw=io.BytesIO();stream=io.TextIOWrapper(raw,encoding='cp949')
                with patch('live.ROOT',root),patch('credentials.load_environment'), \
                     patch('etf_live.EtfBot',return_value=bot),patch('sys.stdout',stream):
                    main(['--etf','--candidate-report'],broker=broker)
                stream.flush()
                report=json.loads(raw.getvalue().decode('utf-8').splitlines()[-1])
                if missing:
                    self.assertIn('파일 저장·접근 오류',report['reason'])
                    self.assertEqual(report['market'],'정규장 운영 시간')
                    self.assertNotIn('private-path',str(report))
                else:self.assertEqual(report['selection_details']['rows'][0]['name'],'한글 ETF')
                stream.close()
