import io
import json
import unittest
import threading
import time
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs
from broker import TossBroker, BrokerError, StopRequested


class Transport:
    def __init__(self, responses):
        self.responses=iter(responses)
        self.requests=[]

    def open(self,request,timeout):
        self.requests.append(request)
        result=next(self.responses)
        if isinstance(result,Exception): raise result
        return io.BytesIO(json.dumps(result).encode())


class BrokerTests(unittest.TestCase):
    def test_stop_interrupts_blocked_read(self):
        started=threading.Event();release=threading.Event();stop=threading.Event()
        class Blocked:
            def open(self,request,timeout):
                started.set();release.wait(2)
                return io.BytesIO(b'{"result":{}}')
        broker=TossBroker(account='7');broker.token='fake';broker.expires=float('inf')
        broker.opener=Blocked();broker.stop_requested=stop.is_set
        def request_stop():
            started.wait(1);stop.set()
        helper=threading.Thread(target=request_stop);helper.start()
        before=time.monotonic()
        try:
            with self.assertRaises(StopRequested):broker.get('prices')
            self.assertLess(time.monotonic()-before,1)
        finally:release.set();helper.join()

    def test_total_deadline_does_not_retry_mutation(self):
        release=threading.Event();calls=[]
        class Blocked:
            def open(self,request,timeout):
                calls.append(request);release.wait(2)
                return io.BytesIO(b'{"result":{}}')
        broker=TossBroker(account='7',live=True);broker.token='fake';broker.expires=float('inf')
        broker.opener=Blocked();broker.deadline=time.monotonic()+.15
        broker.stop_requested=lambda:True
        try:
            with self.assertRaises(BrokerError):broker.place({'clientOrderId':'once'})
            self.assertEqual(len(calls),1)
        finally:release.set()

    @patch.dict('os.environ',{'TOSS_CLIENT_ID':'fake-client','TOSS_CLIENT_SECRET':'fake-secret'})
    @patch('broker.time.sleep')
    def test_oauth_envelope_account_header_and_cancel_contract(self,sleep):
        broker=TossBroker(account='7',live=True)
        broker.opener=Transport([
            {'access_token':'fake-token','expires_in':3600},
            {'result':{'orderId':'o1','clientOrderId':'id1'}},
            {'result':{'orderId':'cancel1'}}])
        payload={'clientOrderId':'id1','symbol':'123456','side':'BUY','orderType':'LIMIT','quantity':'1','price':'1000'}
        self.assertEqual(broker.place(payload)['orderId'],'o1')
        broker.cancel('o1')
        requests=broker.opener.requests
        self.assertEqual(len(requests),3)
        auth=parse_qs(requests[0].data.decode())
        self.assertEqual(auth['grant_type'],['client_credentials'])
        self.assertEqual(auth['client_secret'],['fake-secret'])
        order=requests[1]
        self.assertEqual(order.full_url,'https://openapi.tossinvest.com/api/v1/orders')
        self.assertEqual(order.get_header('X-tossinvest-account'),'7')
        self.assertEqual(order.get_header('Authorization'),'Bearer fake-token')
        self.assertEqual(json.loads(order.data),payload)
        self.assertEqual(requests[2].full_url,'https://openapi.tossinvest.com/api/v1/orders/o1/cancel')
        self.assertEqual(json.loads(requests[2].data),{})

    @patch('broker.time.sleep')
    def test_http_failure_is_not_retried(self,sleep):
        broker=TossBroker(account='7',live=True)
        broker.token='fake-token'
        broker.expires=float('inf')
        broker.opener=Transport([HTTPError('https://openapi.tossinvest.com',503,'secret body',{},None)])
        with self.assertRaisesRegex(BrokerError,'HTTP 503') as caught:
            broker.place({'clientOrderId':'unique'})
        self.assertNotIn('secret',str(caught.exception))
        self.assertEqual(len(broker.opener.requests),1)


if __name__=='__main__': unittest.main()
