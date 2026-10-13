"""Toss OpenAPI 1.2.24 adapter. Mutations are never automatically retried."""
import json
import os
import time
import threading
import queue
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

BASE = 'https://openapi.tossinvest.com'


class BrokerError(RuntimeError):
    pass


class StopRequested(Exception):
    """A read-only operation was interrupted; no mutation was interrupted."""
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BrokerError('API redirect refused')


class TossBroker:
    def __init__(self, account=None, live=False):
        self.account = str(account or os.environ.get('TOSS_ACCOUNT_SEQ', ''))
        self.live = live
        self.token, self.expires, self.last_call = '', 0, 0
        self.opener = build_opener(NoRedirect())
        self.stop_requested = lambda: False
        self.progress = None
        self.deadline = None
        self.operation='OTHER';self.phase='BROKER_REQUEST';self.elapsed=0

    def checkpoint(self):
        if self.stop_requested():
            raise StopRequested()

    def _send(self, request):
        # The socket timeout alone does not bound DNS, TLS or a trickling body.
        # Never retry a mutation after a deadline: its outcome is ambiguous.
        interruptible=request.get_method()=='GET'
        if interruptible:self.checkpoint()
        time.sleep(max(0, 1.1-(time.monotonic()-self.last_call)))
        if interruptible:self.checkpoint()
        self.last_call = time.monotonic()
        deadline=self.last_call+20
        if self.deadline is not None:deadline=min(deadline,self.deadline)
        if time.monotonic()>=deadline:raise BrokerError('Toss request deadline exceeded; request not retried')
        path=request.full_url.split('?',1)[0].removeprefix(BASE)
        endpoint=path.removeprefix('/api/v1/').split('/')[0]
        self.operation={'accounts':'ACCOUNTS','holdings':'HOLDINGS','buying-power':'BUYING_POWER',
            'market-calendar':'CALENDAR','stocks':'STOCKS','candles':'CANDLES','prices':'PRICES',
            'orderbook':'ORDERBOOK','orders':'ORDERS','conditional-orders':'CONDITIONS',
            'commissions':'COMMISSIONS','sellable-quantity':'SELLABLE_QUANTITY'}.get(endpoint,'OTHER')
        if path=='/oauth2/token':self.operation='AUTH'
        if path.endswith('/cancel'):self.operation='ORDER_CANCEL'
        if path.endswith('/warnings'):self.operation='WARNINGS'
        self.phase='BROKER_REQUEST';self.elapsed=0
        if self.progress:self.progress()
        results=queue.Queue(maxsize=1)
        def receive():
            try:
                with self.opener.open(request, timeout=15) as response:
                    result=json.load(response)
                results.put((True,result))
            except Exception as exc:results.put((False,exc))
        threading.Thread(target=receive,daemon=True).start()
        try:
            while True:
                if interruptible:self.checkpoint()
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError()
                try:ok,result=results.get(timeout=min(.1,remaining))
                except queue.Empty:continue
                if not ok:raise result
                self.phase='BROKER_RESPONSE';self.elapsed=round(time.monotonic()-self.last_call,2)
                if self.progress:self.progress()
                return result
        except HTTPError as exc:
            # Never include response bodies, request headers, tokens or account numbers.
            raise BrokerError(f'Toss HTTP {exc.code}; request not retried') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise BrokerError('Toss connection/response error; request not retried') from None

    def authenticate(self):
        if self.token and time.monotonic() < self.expires:
            return
        client, secret = os.environ.get('TOSS_CLIENT_ID'), os.environ.get('TOSS_CLIENT_SECRET')
        if not client or not secret:
            raise BrokerError('Set TOSS_CLIENT_ID and TOSS_CLIENT_SECRET locally')
        data = urlencode(dict(grant_type='client_credentials', client_id=client, client_secret=secret)).encode()
        result = self._send(Request(BASE+'/oauth2/token',data=data,
                                    headers={'Content-Type':'application/x-www-form-urlencoded'}))
        self.token = result['access_token']
        self.expires = time.monotonic()+max(0,int(result['expires_in'])-60)

    def request(self, method, path, params=None, body=None, account=False):
        if method != 'GET' and not self.live:
            raise BrokerError('Read-only mode: order mutation blocked')
        self.authenticate()
        headers = {'Authorization': 'Bearer '+self.token, 'Content-Type':'application/json'}
        if account:
            if not self.account.isdigit():
                raise BrokerError('Set TOSS_ACCOUNT_SEQ to the selected accountSeq')
            headers['X-Tossinvest-Account'] = self.account
        url = BASE+path+('?' + urlencode(params) if params else '')
        result = self._send(Request(url, method=method, headers=headers,
                                   data=json.dumps(body).encode() if body is not None else None))
        if 'result' not in result or 'error' in result:
            raise BrokerError('Unexpected API envelope')
        return result['result']

    def get(self, path, params=None, account=False):
        return self.request('GET','/api/v1/'+path,params=params,account=account)

    def orders(self):
        result = self.get('orders', {'status':'OPEN'}, account=True)
        if result['hasNext']:
            raise BrokerError('Unexpected pagination of OPEN orders')
        return result['orders']

    def detail(self, order_id):
        from urllib.parse import quote
        return self.get('orders/'+quote(order_id,safe=''),account=True)

    def place(self, payload):
        return self.request('POST','/api/v1/orders',body=payload,account=True)

    def cancel(self, order_id):
        from urllib.parse import quote
        return self.request('POST','/api/v1/orders/'+quote(order_id,safe='')+'/cancel',body={},account=True)
