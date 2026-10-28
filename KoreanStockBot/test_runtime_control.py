"""Offline regression for stop requests arriving inside a trading iteration."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from broker import StopRequested
from live import LiveBot, Store, ROOT, main
from test_live import FakeBroker


class RuntimeControlTests(unittest.TestCase):
    def test_no_symbol_read_only_checks_account_without_trading_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=json.loads((ROOT/'live_config.json').read_text())
            config['symbol']=''
            path=root/'config.json';path.write_text(json.dumps(config))
            broker=FakeBroker();broker.position=3
            output=io.StringIO()
            with patch('live.ROOT',root),patch('credentials.load_environment'),contextlib.redirect_stdout(output):
                main(['--config',str(path)],broker=broker)
            self.assertIn('READ_ONLY_CHECK_COMPLETE',output.getvalue())
            self.assertEqual(broker.sent,[])
            self.assertEqual(list((root/'runtime').glob('*state.json')),[])
            from live import SafetyStop
            with patch('live.ROOT',root),patch('credentials.load_environment'),contextlib.redirect_stdout(output):
                with self.assertRaises(SafetyStop):main(['--live','--config',str(path)],broker=broker)
            self.assertEqual(broker.sent,[])

    def test_stale_data_recovers_and_buys_then_sells_without_restart(self):
        self.run_market_recovery(False)

    def test_empty_orderbook_recovers_and_buys_then_sells_without_restart(self):
        self.run_market_recovery(True)

    def run_market_recovery(self,invalid_book):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=json.loads((ROOT/'live_config.json').read_text())
            config['symbol']='123456'
            path=root/'config.json';path.write_text(json.dumps(config))
            broker=FakeBroker();broker.stale=True
            if invalid_book:
                broker.stale=False
                book=broker.get('orderbook');book['asks']=[]
                broker.override['orderbook']=book
            output=io.StringIO()
            original_step=LiveBot.step
            attempts=[]
            def step(bot,stop=False):
                attempts.append(stop)
                if len(attempts)==2:
                    self.assertEqual(broker.sent,[])
                    broker.stale=False
                    broker.override.pop('orderbook',None)
                result=original_step(bot,stop)
                if result.get('side')=='BUY':
                    order=broker.sent[-1]
                    broker.fill('1',int(order['quantity']),int(order['quantity'])*int(order['price']))
                    broker.price=2500
                elif result.get('side')=='SELL':
                    order=broker.sent[-1]
                    broker.fill('2',int(order['quantity']),int(order['quantity'])*int(order['price']))
                    (root/'STOP').touch()
                if len(attempts)>5:raise AssertionError('Loop did not stop')
                return result
            def create_bot(*args,**kwargs):
                return LiveBot(*args,**kwargs,clock=lambda:broker.now)
            config['poll_seconds']=10
            path.write_text(json.dumps(config))
            ticks=iter(range(0,10000,11))
            with patch('live.ROOT',root),patch('live.LiveBot',side_effect=create_bot),patch.object(LiveBot,'step',step),patch('credentials.load_environment'),patch('live.time.monotonic',side_effect=lambda:next(ticks)),contextlib.redirect_stdout(output):
                main(['--live','--config',str(path)],broker=broker)
            self.assertIn('ORDERBOOK_WAIT' if invalid_book else 'MARKET_DATA_WAIT',output.getvalue())
            self.assertIn('STOPPED',output.getvalue())
            self.assertEqual([o['side'] for o in broker.sent],['BUY','SELL'])

    def test_interrupted_iteration_enters_stop_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=json.loads((ROOT/'live_config.json').read_text())
            config['symbol']='123456'
            path=root/'config.json';path.write_text(json.dumps(config))
            broker=FakeBroker();original=broker.get
            def get(endpoint,*args,**kwargs):
                if endpoint=='stocks':
                    (root/'STOP').touch()
                    raise StopRequested()
                return original(endpoint,*args,**kwargs)
            broker.get=get
            output=io.StringIO()
            def create_bot(*args,**kwargs):
                return LiveBot(*args,**kwargs,clock=lambda:broker.now)
            with patch('live.ROOT',root),patch('live.LiveBot',side_effect=create_bot),patch('credentials.load_environment'),contextlib.redirect_stdout(output):
                main(['--live','--config',str(path)],broker=broker)
            self.assertIn('STOP_CHECKING',output.getvalue())
            self.assertIn('STOPPED',output.getvalue())
            self.assertEqual(broker.sent,[])
            self.assertEqual(Store(root/'runtime'/'live_state.json').data['orders'],[])

    def test_stop_before_submit_creates_no_order_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            broker=FakeBroker()
            config=json.loads((ROOT/'live_config.json').read_text())
            config['symbol']='123456'
            bot=LiveBot(broker,config,Store(Path(directory)/'state.json'),live=True,clock=lambda:broker.now)
            bot.initialize();bot.stop_requested=lambda:True
            with self.assertRaises(StopRequested):bot.submit('BUY',1,3000,'TEST')
            self.assertEqual(bot.s['orders'],[])
            self.assertEqual(broker.sent,[])
