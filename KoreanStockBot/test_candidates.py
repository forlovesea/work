import unittest
import tempfile
from pathlib import Path
from etf_scope import candidate_rows,read_symbols,write_symbols


class CandidateTests(unittest.TestCase):
    def test_cells_distinguish_skipped_failed_and_measured(self):
        from etf_scope import candidate_cells
        self.assertEqual(candidate_cells({'state':'RESEARCH'})[0],'조회 생략')
        self.assertIn('재무·뉴스',candidate_cells({'state':'RESEARCH'})[2])
        self.assertEqual(candidate_cells({'state':'QUOTE_STALE'})[:2],('시세 시간 초과','산출 불가'))
        self.assertEqual(candidate_cells({'state':'QUOTE_UNAVAILABLE'})[0],'유효 시세 없음')
        self.assertIn('예산 초과',candidate_cells({'state':'BUDGET','price':'1234','required':'1256'})[2])
        self.assertEqual(candidate_cells({'state':'ELIGIBLE','price':'1234','required':'1256','fast_ma':'11','slow_ma':'10'}),('1,234','1,256','상승'))
        self.assertIn('일봉',candidate_cells({'state':'CANDLES'})[2])

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
