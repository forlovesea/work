import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs
from broker import TossBroker, BrokerError


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
