import tempfile
import unittest
from pathlib import Path
from engine import Bar, Config, PaperEngine, demo_bars, read_bars


def bar(day, price, volume=100):
    return Bar(f'2025-01-{day:02}', price, price, price, price, volume)


class EngineTests(unittest.TestCase):
    def test_next_open_and_cash_limit(self):
        e=PaperEngine(Config(fast=1,slow=2))
        e.step(bar(1,1000))
        e.step(bar(2,1100))
        self.assertEqual(e.qty,0)
        e.step(bar(3,1200))
        self.assertEqual(e.trades[0]['date'],'2025-01-03')
        self.assertAlmostEqual(e.trades[0]['price'],1201.2)
        self.assertGreaterEqual(e.cash,0)
        self.assertEqual(e.qty,7)

    def test_unaffordable(self):
        e=PaperEngine(Config(fast=1,slow=2))
        for i,p in enumerate([30000,31000,32000],1): e.step(bar(i,p))
        self.assertEqual(e.qty,0)
        self.assertEqual(e.cash,30000)

    def test_halt_liquidates_next_tradable_open(self):
        e=PaperEngine(Config(fast=1,slow=2,allocation=1,max_drawdown=.1))
        for i,p in enumerate([1000,1100,1200,800],1): e.step(bar(i,p))
        self.assertTrue(e.halted)
        e.step(bar(5,700,0))
        self.assertGreater(e.qty,0)
        e.step(bar(6,600))
        self.assertEqual(e.qty,0)
        self.assertEqual(e.trades[-1]['reason'],'최대 낙폭 중단')
        e.step(bar(7,2000))
        self.assertEqual(e.qty,0)

    def test_future_does_not_change_past(self):
        bars=demo_bars()
        a,b=PaperEngine(),PaperEngine()
        for row in bars[:80]: a.step(row)
        for row in bars: b.step(row)
        self.assertEqual(a.equity,b.equity[:80])
        self.assertEqual(a.trades,[t for t in b.trades if t['date']<=bars[79].date])

    def test_costs_and_period_returns(self):
        e=PaperEngine(Config(fast=1,slow=2,fee=.01,sell_tax=.02,slippage=0))
        for i,p in enumerate([1000,1100,1200,1000,1000],1): e.step(bar(i,p))
        self.assertEqual(e.qty,0)
        self.assertAlmostEqual(e.cash,30000-7*1200*1.01+7*1000*.97)
        week=[p for p in e.report()['periods'] if p['period']=='week'][0]
        self.assertAlmostEqual(week['return_pct'],(e.cash/30000-1)*100)

    def test_bad_csv_and_settings(self):
        for cfg in [Config(capital=float('nan')),Config(allocation=2),Config(fast=20,slow=5)]:
            with self.assertRaises(ValueError): PaperEngine(cfg)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.csv'
            path.write_text('date,open,high,low,close,volume\n2025-01-01,1,2,1,nan,1\n')
            with self.assertRaises(ValueError): read_bars(path)


if __name__=='__main__': unittest.main()
