"""Exercise the real account worker/transport stdout contract without networking."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from broker import TossBroker
from live import main
from test_broker import Transport


def account_output(accounts):
    broker=TossBroker()
    broker.opener=Transport([
        {'access_token':'synthetic-token','expires_in':3600},
        {'result':accounts},
    ])
    output=io.StringIO()
    with tempfile.TemporaryDirectory() as directory:
        with patch('live.ROOT',Path(directory)),patch('credentials.load_environment'), \
             patch.dict('os.environ',{'TOSS_CLIENT_ID':'synthetic','TOSS_CLIENT_SECRET':'synthetic'}), \
             patch('broker.time.sleep'),contextlib.redirect_stdout(output):
            main(['--accounts'],broker=broker)
    return output.getvalue(),broker.opener.requests


class AccountProtocolTests(unittest.TestCase):
    def test_success_is_one_json_document_even_during_authentication(self):
        accounts=[{'accountSeq':101,'accountType':'BROKERAGE','accountNumber':'must-not-be-output'}]
        output,requests=account_output(accounts)
        self.assertEqual(json.loads(output),[{'accountSeq':101,'accountType':'BROKERAGE'}])
        self.assertNotIn('must-not-be-output',output)
        self.assertNotIn('synthetic-token',output)
        self.assertEqual(len(requests),2)
        self.assertEqual(requests[1].get_method(),'GET')
        self.assertTrue(requests[1].full_url.endswith('/accounts'))

    def test_empty_and_multiple_accounts_remain_parseable(self):
        for accounts in ([],[{'accountSeq':i,'accountType':'BROKERAGE'} for i in (101,202)]):
            with self.subTest(count=len(accounts)):
                output,_=account_output(accounts)
                self.assertEqual(json.loads(output),accounts)
