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
