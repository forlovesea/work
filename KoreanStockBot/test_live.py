import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from broker import TossBroker, BrokerError
from live import LiveBot, Store, SafetyStop, KST, load_config, process_lock, ROOT


class FakeBroker:
    account='1'

    def __init__(self):
        self.now=datetime(2026,6,30,10,tzinfo=KST)
        self.position=0
        self.open=[]
        self.details={}
        self.sent=[]
        self.canceled=[]
        self.fail_submit=False
        self.stale=False
        self.holiday=False
        self.warnings=[]
        self.price=3000
        self.power='30000'
        self.override={}

    def get(self,path,params=None,account=False):
        if path in self.override:
            return copy.deepcopy(self.override[path])
        if path=='accounts': return [{'accountSeq':1,'accountType':'BROKERAGE'}]
        if path=='conditional-orders': return {'conditionalOrders':[],'hasNext':False}
        if path=='holdings':
            return {'items':([{'symbol':'123456','quantity':str(self.position)}] if self.position else [])}
        if path=='buying-power': return {'currency':'KRW','cashBuyingPower':self.power}
        if path=='sellable-quantity': return {'sellableQuantity':str(self.position)}
        if path=='commissions': return [{'marketCountry':'KR','commissionRate':'0.00015','startDate':None,'endDate':None}]
        if path=='market-calendar/KR':
            day=self.now.date().isoformat()
            regular={'startTime':day+'T09:00:00+09:00','singlePriceAuctionStartTime':day+'T15:20:00+09:00'}
            return {'today':{'date':day,'integrated':None if self.holiday else {'regularMarket':regular}},
                    'previousBusinessDay':{'date':(self.now-timedelta(days=1)).date().isoformat()}}
        if path=='stocks':
            return [{'symbol':'123456','currency':'KRW','market':'KOSPI','securityType':'STOCK',
                     'status':'ACTIVE','isCommonShare':True,'koreanMarketDetail':{'liquidationTrading':False,'krxTradingSuspended':False}}]
        if path.endswith('/warnings'): return self.warnings
        if path=='candles':
            return {'candles':[{'timestamp':(self.now-timedelta(days=i)).isoformat(),
                                'closePrice':str(3000-i*10),'currency':'KRW'} for i in range(30)]}
        timestamp=(self.now-timedelta(seconds=120 if self.stale else 0)).isoformat()
        if path=='prices': return [{'symbol':'123456','timestamp':timestamp,'lastPrice':str(self.price),'currency':'KRW'}]
        if path=='orderbook':
            return {'timestamp':timestamp,'currency':'KRW','asks':[{'price':str(self.price+5),'volume':'100'}],
                    'bids':[{'price':str(self.price),'volume':'100'}]}
        raise AssertionError(path)

    def orders(self): return copy.deepcopy(self.open)
    def detail(self,oid): return copy.deepcopy(self.details[oid])

    def place(self,payload):
        self.sent.append(copy.deepcopy(payload))
        oid=str(len(self.sent))
        self.details[oid]=dict(payload,orderId=oid,status='PENDING',currency='KRW',
                               orderedAt=self.now.isoformat(),canceledAt=None,
                               execution=dict(filledQuantity='0',filledAmount=None,commission=None,tax=None))
        self.open=[self.details[oid]]
        if self.fail_submit: raise BrokerError('Simulated timeout after server accepted order')
        return {'orderId':oid,'clientOrderId':payload['clientOrderId']}

    def cancel(self,oid):
        self.canceled.append(oid)
        return {'orderId':'cancel-'+oid}

    def fill(self,oid,qty,amount,fee='1',tax='0',status='FILLED'):
        d=self.details[oid]
        d['status']=status
        d['execution']=dict(filledQuantity=str(qty),filledAmount=str(amount),commission=fee,tax=tax)
        self.position=qty if d['side']=='BUY' else 0
        if status in ('FILLED','CANCELED','REJECTED'): self.open=[]


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config=json.loads((ROOT/'live_config.json').read_text())
        self.config['symbol']='123456'
        self.path=Path(self.tmp.name)/'state.json'
        self.b=FakeBroker()
        self.bot=LiveBot(self.b,self.config,Store(self.path),live=True,clock=lambda:self.b.now)
        self.bot.initialize()

    def test_live_limit_order_and_budget(self):
        result=self.bot.step()
        self.assertEqual(result['side'],'BUY')
        p=self.b.sent[0]
        self.assertEqual(p['orderType'],'LIMIT')
        self.assertEqual(p['timeInForce'],'DAY')
        self.assertLessEqual(int(p['quantity'])*int(p['price']),9000)
        self.assertEqual(len(p['clientOrderId']),36)
        self.assertEqual(Store(self.path).data['orders'][0]['order_id'],'1')

    def test_partial_fill_restart_exactly_once_and_no_second_order(self):
        self.bot.step()
        self.b.fill('1',1,3005,status='PARTIAL_FILLED')
        self.bot.step()
        cash=self.bot.s['cash']
        restarted=LiveBot(self.b,self.config,Store(self.path),True,clock=lambda:self.b.now)
        restarted.initialize()
        restarted.step()
        self.assertEqual(restarted.s['quantity'],1)
        self.assertEqual(restarted.s['cash'],cash)
        self.assertEqual(len(self.b.sent),1)
        self.b.fill('1',2,6010,fee='2')
        restarted.step()
        self.assertEqual(restarted.s['quantity'],2)
        self.assertEqual(float(restarted.s['cash']),23988)

    def test_ambiguous_submission_persists_and_never_retries(self):
        self.b.fail_submit=True
        with self.assertRaises(BrokerError): self.bot.step()
        self.assertIsNone(Store(self.path).data['orders'][0].get('order_id'))
        self.b.now+=timedelta(minutes=20)
        restarted=LiveBot(self.b,self.config,Store(self.path),True,clock=lambda:self.b.now)
        with self.assertRaises(SafetyStop): restarted.step()
        self.assertEqual(len(self.b.sent),1)
        restarted.recover('1')
        self.assertEqual(restarted.active()['order_id'],'1')

    def test_unknown_recovery_rejects_wrong_order(self):
        self.b.fail_submit=True
        with self.assertRaises(BrokerError): self.bot.step()
        self.b.details['1']['symbol']='654321'
        with self.assertRaises(SafetyStop): self.bot.recover('1')

    def test_cancel_once_then_wait_for_confirmation(self):
        self.bot.step()
        self.b.now+=timedelta(seconds=130)
        self.bot.step()
        self.bot.step()
        self.assertEqual(self.b.canceled,['1'])
        self.b.fill('1',1,3005,status='CANCELED')
        self.bot.step()
        self.assertEqual(self.bot.s['quantity'],1)
        self.assertEqual(len(self.b.sent),1)

    def test_kill_switch_cancels_then_stops_retaining_position(self):
        self.bot.step()
        self.assertEqual(self.bot.step(stop=True)['status'],'STOPPING')
        self.assertEqual(self.b.canceled,['1'])
        self.b.fill('1',1,3005,status='CANCELED')
        result=self.bot.step(stop=True)
        self.assertEqual(result['status'],'STOPPED')
        self.assertEqual(result['holdings_retained'],1)

    def test_stale_quote_no_order(self):
        self.b.stale=True
        with self.assertRaises(SafetyStop): self.bot.step()
        self.assertEqual(self.b.sent,[])

    def test_holiday_no_order(self):
        self.b.holiday=True
        self.assertEqual(self.bot.step()['status'],'OUTSIDE_REGULAR_SESSION')
        self.assertEqual(self.b.sent,[])

    def test_warning_no_buy(self):
        self.b.warnings=[{'warningType':'VI_STATIC'}]
        self.assertEqual(self.bot.step()['status'],'HOLD')
        self.assertEqual(self.b.sent,[])

    def test_external_conditional_order_blocks(self):
        self.b.override['conditional-orders']={'conditionalOrders':[{'conditionalOrderId':'external'}],'hasNext':False}
        with self.assertRaises(SafetyStop): self.bot.step()
        self.assertEqual(self.b.sent,[])

    def test_expensive_share_no_buy(self):
        self.b.price=40000
        self.bot.step()
        self.assertEqual(self.b.sent,[])

    def test_external_holdings_and_orders_block(self):
        self.b.position=1
        with self.assertRaises(SafetyStop): self.bot.step()
        self.b.position=0
        self.b.open=[{'orderId':'external'}]
        with self.assertRaises(SafetyStop): self.bot.step()
        self.assertEqual(self.b.sent,[])

    def test_stop_loss_real_sell_payload(self):
        self.bot.step()
        self.b.fill('1',2,6010,fee='2')
        self.b.price=2800
        result=self.bot.step()
        self.assertEqual(result['side'],'SELL')
        self.assertEqual(result['reason'],'STOP_LOSS')
        self.assertEqual(self.b.sent[-1]['quantity'],'2')
        self.b.fill('2',2,5600,fee='1',tax='10')
        self.bot.step()
        self.assertEqual(float(self.bot.s['cash']),29577)
        self.assertEqual(self.bot.s['quantity'],0)
        self.assertEqual(len(self.b.sent),2)

    def test_targets_latch_and_rollover(self):
        from decimal import Decimal
        hit,loss=self.bot.observe(Decimal(33000),self.b.now)
        self.assertTrue(hit)
        self.assertFalse(loss)
        self.bot.observe(Decimal(32900),self.b.now)
        self.assertTrue(self.bot.s['periods']['daily']['hit'])
        self.bot.observe(Decimal(32900),datetime(2026,7,1,10,tzinfo=KST))
        self.assertFalse(self.bot.s['periods']['daily']['hit'])
        self.assertFalse(self.bot.s['periods']['monthly']['hit'])
        self.assertTrue(self.bot.s['periods']['weekly']['hit'])

    def test_daily_loss_and_drawdown_latch(self):
        from decimal import Decimal
        self.assertTrue(self.bot.observe(Decimal(29300),self.b.now)[1])
        self.bot.observe(Decimal(27000),self.b.now)
        self.assertTrue(self.bot.s['halted'])
        self.bot.observe(Decimal(31000),self.b.now+timedelta(days=1))
        self.assertTrue(self.bot.s['halted'])

    def test_future_candle_excluded(self):
        original=self.b.get('candles')
        original['candles'][0]['closePrice']='1'
        self.b.override['candles']=original
        result=self.bot.step()
        self.assertEqual(result['side'],'BUY')

    def test_config_binding_and_invalid_values(self):
        changed=copy.deepcopy(self.config)
        changed['capital']=60000
        b=LiveBot(self.b,changed,Store(self.path),True,clock=lambda:self.b.now)
        with self.assertRaises(SafetyStop): b.initialize()
        path=Path(self.tmp.name)/'config.json'
        for key,value in [('capital',float('nan')),('symbol',''),('poll_seconds',0),('slow',5),('allocation',2)]:
            bad=dict(self.config,**{key:value})
            path.write_text(json.dumps(bad))
            with self.assertRaises(SafetyStop): load_config(path)

    def test_missing_fill_costs_blocks(self):
        self.bot.step()
        self.b.fill('1',2,6010,fee=None)
        with self.assertRaises(SafetyStop): self.bot.step()
        self.assertEqual(len(self.b.sent),1)

    def test_dry_run_no_mutations(self):
        self.bot.live=False
        result=self.bot.step()
        self.assertEqual(result['mode'],'DRY_RUN')
        self.assertEqual(self.b.sent,[])
        broker=TossBroker(account='1')
        with self.assertRaises(BrokerError): broker.place({})
        with self.assertRaises(BrokerError): broker.cancel('1')

    def test_schema_order_payload_matches_official_contract(self):
        self.bot.step()
        spec=json.loads((ROOT/'toss-openapi.json').read_text(encoding='utf-8-sig'))
        schema=spec['components']['schemas']['OrderCreateRequest']['oneOf'][0]
        payload=self.b.sent[0]
        self.assertTrue(set(schema['required'])<=set(payload))
        self.assertTrue(set(payload)<=set(schema['properties']))
        for key,value in payload.items():
            prop=schema['properties'][key]
            if 'enum' in prop: self.assertIn(value,prop['enum'])
            if 'pattern' in prop: self.assertRegex(value,prop['pattern'])

    def test_os_lock(self):
        path=Path(self.tmp.name)/'lock'
        with process_lock(path):
            with self.assertRaises(SafetyStop):
                with process_lock(path): pass


if __name__=='__main__': unittest.main()
