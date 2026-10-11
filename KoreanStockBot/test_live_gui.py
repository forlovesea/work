import unittest
import tempfile
import json
from pathlib import Path
from datetime import datetime,timedelta
from decimal import Decimal
from live import LiveBot,Store,ROOT,KST
from live_gui import account_view
from test_live import FakeBroker


class LiveHistoryTests(unittest.TestCase):
    def test_history_persists_and_updates_same_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=json.loads((ROOT/'live_config.json').read_text())
            config['symbol']='123456'
            bot=LiveBot(FakeBroker(),config,Store(Path(tmp)/'state.json'))
            bot.initialize()
            now=datetime(2026,10,12,10,tzinfo=KST)
            bot.observe(Decimal('31000'),now)
            bot.observe(Decimal('29000'),now+timedelta(hours=1))
            bot.observe(Decimal('30000'),now+timedelta(days=1))
            saved=Store(Path(tmp)/'state.json').data
            self.assertEqual(len(saved['equity_history']),2)
            self.assertEqual(saved['equity_history'][0]['equity'],'29000')
            self.assertEqual(saved['equity_history_base'],'30000')
            self.assertAlmostEqual(float(saved['observed_max_drawdown']),2000/31000)
            view=account_view(saved,config)
            self.assertEqual(view.report()['return_pct'],0)

    def test_old_state_has_no_fabricated_history(self):
        view=account_view({'last_equity':'33000','peak':'34000'}, {'capital':30000})
        self.assertEqual(view.equity,[])
        self.assertAlmostEqual(view.report()['return_pct'],10)


if __name__=='__main__':unittest.main()
