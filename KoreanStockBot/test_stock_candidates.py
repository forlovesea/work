import copy
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from stock_candidates import category,shortlist,budget_for,financial_pass,top_five,screen,apply_selection,binding,CHECK_NAMES
from live import ROOT,SafetyStop
from test_live import FakeBroker

def financial():
    return dict(checks={k:True for k in CHECK_NAMES},metrics=dict(revenue='100',operating_profit='10',net_profit='8',
        assets='200',equity='100',operating_cash='12'),report_end='2026-03-31',sources=[],fs_div='CFS')

class StockCandidatesTests(unittest.TestCase):
    def test_category_budget_and_limited_universe(self):
        for industry,expected in [('은행','금융'),('제약','바이오·헬스케어'),('전기·전자','IT'),('비금속','소재(매터리얼)')]:
            self.assertEqual(category(industry),expected)
        config={'capital':30000,'allocation':.3,'max_order_won':9000}
        self.assertEqual(budget_for(config,5000),5000)
        self.assertEqual(budget_for(config,30000,10000),3000)
        rows=[dict(symbol=f'{i:06}',industry='제약',price='1000',market_cap=str(i)) for i in range(1,30)]
        rows.append(dict(symbol='999999',industry='제약',price='99999',market_cap='10000'))
        targets,counts=shortlist(rows,9000,20)
        self.assertEqual(len(targets),20);self.assertEqual(counts['바이오·헬스케어'],29)
        self.assertEqual(targets[0]['symbol'],'000029')
        self.assertEqual(len(shortlist(rows,9000,0)[0]),29)

    def test_financial_requirements_and_five_per_category(self):
        f=financial();self.assertTrue(financial_pass(f));self.assertFalse(financial_pass(None))
        f['checks']['operating_profit_positive']=False;self.assertFalse(financial_pass(f))
        rows=[dict(symbol=f'{i:06}',category=group,market_cap=str(i),report=financial()) for group in ('금융','IT') for i in range(10)]
        self.assertEqual(len(top_five(rows)),10)
        self.assertEqual(sum(r['category']=='IT' for r in top_five(rows)),5)

    def test_screen_and_selection_without_orders(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=json.loads((ROOT/'live_config.json').read_text());config['symbol']=''
            path=root/'live_config.json';path.write_text(json.dumps(config))
            broker=FakeBroker();broker.live=False
            sources=SimpleNamespace(corporations=lambda:{'123456':{'corp_code':'12345678'}},financial=lambda corp:financial())
            universe=[dict(symbol='123456',name='테스트',industry='제약',price='3000',market_cap='1000000')]
            report=screen(broker,config,root=root,now=broker.now,sources=sources,universe=universe)
            self.assertEqual(len(report['rows']),1);self.assertEqual(broker.sent,[])
            self.assertEqual(report['rows'][0]['quantity'],2)
            report['checked_at']=broker.now.isoformat()
            with self.assertRaises(SafetyStop):apply_selection(root,path,'2',report,'123456',broker.now)
            with self.assertRaises(SafetyStop):apply_selection(root,path,'1',report,'123456',broker.now+timedelta(minutes=6))
            config2=apply_selection(root,path,'1',report,'123456',broker.now)
            self.assertEqual(config2['symbol'],'123456')
            # No live ledger is created by preview or selection.
            self.assertFalse((root/'runtime/live_state.json').exists())
            broker.stale=True
            stale=screen(broker,config2,root=root,now=broker.now,sources=sources,universe=universe)
            self.assertEqual(stale['rows'],[]);self.assertEqual(stale['excluded']['QUOTE_STALE'],1)
            broker.stale=False;broker.price=10000
            expensive=screen(broker,config2,root=root,now=broker.now,sources=sources,universe=universe)
            self.assertEqual(expensive['rows'],[]);self.assertEqual(expensive['excluded']['BUDGET'],1)

    def test_existing_live_record_blocks_symbol_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'runtime').mkdir()
            (root/'runtime/live_state.json').write_text('{}')
            config={'symbol':'654321'};path=root/'live_config.json';path.write_text(json.dumps(config))
            broker=FakeBroker();now=broker.now
            report=dict(binding=binding('1',config),checked_at=now.isoformat(),rows=[{'symbol':'123456','price_at':now.isoformat()}])
            with self.assertRaises(SafetyStop):apply_selection(root,path,'1',report,'123456',now)
            self.assertEqual(json.loads(path.read_text())['symbol'],'654321')
