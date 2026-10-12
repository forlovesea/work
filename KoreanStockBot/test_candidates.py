import unittest
import tempfile
from pathlib import Path
from etf_scope import candidate_rows,read_symbols,write_symbols


class CandidateTests(unittest.TestCase):
    def test_dedupe_and_measured_priority(self):
        a=dict(symbol='123456',rank=1,state='BUDGET',score=.9)
        b=dict(symbol='654321',rank=2,state='ELIGIBLE',score=.7)
        self.assertEqual([r['symbol'] for r in candidate_rows({'rows':[a,b,a]})],['654321','123456'])

    def test_saved_selection_account_binding_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'scope.json'
            write_symbols(path,'account-a',['123456','123456'])
            self.assertEqual(read_symbols(path,'account-a'),{'123456'})
            self.assertIsNone(read_symbols(path,'account-b'))
            with self.assertRaises(ValueError):write_symbols(path,'account-a',[])
            with self.assertRaises(ValueError):write_symbols(path,'account-a',['bad'])
