"""Persistent single-symbol live trader. Default invocation is read-only.

Ledger is attributed to this bot's executions, not account cash buying power.
Any ambiguous mutation or external position change blocks further orders.
"""
import argparse
import hashlib
import json
import os
import re
import time
import uuid
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from broker import TossBroker, BrokerError

# ETF modules import shared types from live; keep one identity for script execution.
if __name__ == '__main__':
    sys.modules.setdefault('live',sys.modules[__name__])

from app_paths import ROOT
KST = timezone(timedelta(hours=9))


class SafetyStop(RuntimeError):
    pass


def dec(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError()
        return result
    except (InvalidOperation, ValueError):
        raise SafetyStop('Invalid numeric API/config value') from None


def integer(value):
    value = dec(value)
    if value != value.to_integral_value():
        raise SafetyStop('Fractional domestic quantity/price refused')
    return int(value)


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:
        raise SafetyStop('Timestamp missing timezone')
    return result.astimezone(KST)


def now_kst():
    return datetime.now(KST)


def load_config(path):
    c = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if c.get('strategy')!='kosdaq_etf_top20' and not re.fullmatch('[0-9A-Z]{6}',c['symbol']):
        raise SafetyStop('live_config.json: choose a domestic 6-character symbol first')
    for key in ('capital','max_order_won'):
        if dec(c[key]) <= 0:
            raise SafetyStop('Capital/order limit must be positive')
    for key in ('allocation','stop_loss','take_profit','daily_loss_limit','max_drawdown',
                'daily_target','weekly_target','monthly_target','max_spread'):
        if not 0 < dec(c[key]) < 1:
            raise SafetyStop('Ratio must be between 0 and 1: '+key)
    if not 1 <= integer(c['fast']) < integer(c['slow']) <= 100:
        raise SafetyStop('Require 1 <= fast < slow <= 100')
    if not 10 <= integer(c['poll_seconds']) <= 3600:
        raise SafetyStop('Polling must be between 10 and 3600 seconds')
    if not 1 <= integer(c['max_quote_age_seconds']) <= 60:
        raise SafetyStop('Quote age limit must be 1..60 seconds')
    if not 30 <= integer(c['cancel_after_seconds']) <= 3600:
        raise SafetyStop('Cancel timeout must be 30..3600 seconds')
    if c.get('strategy')=='kosdaq_etf_top20':
        if not 0<=dec(c['liquidation_cost_buffer'])<Decimal('.1'):
            raise SafetyStop('ETF liquidation cost buffer must be below 10%')
        if not isinstance(c['research_file'],str) or not c['research_file']:
            raise SafetyStop('ETF research file must be configured')
    return c


@contextmanager
def process_lock(path):
    """OS-released lock; one bot process per workspace, including dry runs."""
    path.parent.mkdir(parents=True,exist_ok=True)
    f = path.open('a+b')
    try:
        f.seek(0)
        if not f.read(1):
            f.write(b'0')
            f.flush()
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        f.close()
        raise SafetyStop('Another bot process holds the lock') from None
    try:
        yield
    finally:
        f.close()


class Store:
    def __init__(self,path):
        self.path=Path(path)
        self.data=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else None

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp')
        with tmp.open('w',encoding='utf-8') as f:
            json.dump(self.data,f,ensure_ascii=False,indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,self.path)


class LiveBot:
    def __init__(self,broker,config,store,live=False,clock=now_kst):
        self.b,self.c,self.store,self.live,self.clock=broker,config,store,live,clock
        self.symbol=config['symbol']
        self.binding=hashlib.sha256((broker.account+'|'+json.dumps(config,sort_keys=True)).encode()).hexdigest()

    @property
    def s(self):
        return self.store.data

    def holdings(self):
        rows=self.b.get('holdings',account=True)['items']
        if any(r['symbol'] != self.symbol and dec(r['quantity']) > 0 for r in rows):
            raise SafetyStop('Use an isolated account: unrelated holdings found')
        rows=[r for r in rows if r['symbol']==self.symbol]
        if len(rows)>1:
            raise SafetyStop('Duplicate holdings rows')
        return integer(rows[0]['quantity']) if rows else 0

    def check_conditions(self):
        result=self.b.get('conditional-orders',{'status':'OPEN','limit':1},account=True)
        if result['conditionalOrders'] or result['hasNext']:
            raise SafetyStop('External conditional orders found; use an isolated account')

    def initialize(self):
        accounts=self.b.get('accounts')
        if not any(str(a['accountSeq'])==self.b.account and a['accountType']=='BROKERAGE' for a in accounts):
            raise SafetyStop('Selected brokerage account not found')
        self.check_conditions()
        if self.s:
            if self.s['binding'] != self.binding:
                raise SafetyStop('Account/config changed: preserve state; reconcile before changing configuration')
            return
        if self.b.orders() or self.holdings():
            raise SafetyStop('First start requires no holdings or pending orders')
        power=dec(self.b.get('buying-power',{'currency':'KRW'},account=True)['cashBuyingPower'])
        if power < dec(self.c['capital']):
            raise SafetyStop('Cash buying power below configured capital')
        self.store.data=dict(version=1,binding=self.binding,cash=str(self.c['capital']),quantity=0,
                             cost='0',peak=str(self.c['capital']),last_equity=str(self.c['capital']),
                             periods={},halted=False,orders=[],last_buy_day=None)
        self.store.save()

    def active(self):
        return next((o for o in self.s['orders'] if not o.get('done')),None)

    def verify_order(self,record,order):
        p=record['payload']
        if any(order[k] != p[k] for k in ('symbol','side','orderType')):
            raise SafetyStop('Broker order identity mismatch')
        if (order['currency']!='KRW' or integer(order['quantity'])!=integer(p['quantity'])
                or dec(order['price'])!=dec(p['price'])):
            raise SafetyStop('Broker order quantity/price mismatch')

    def reconcile(self):
        """Apply cumulative execution deltas exactly once, including fees and tax."""
        record=self.active()
        if record is None:
            return
        if not record.get('order_id'):
            raise SafetyStop('UNKNOWN order outcome. Do not resend. Inspect Toss and use --recover-order ID.')
        order=self.b.detail(record['order_id'])
        self.verify_order(record,order)
        ex=order['execution']
        filled=integer(ex['filledQuantity'])
        if filled > integer(record['payload']['quantity']):
            raise SafetyStop('Fill exceeds requested quantity')
        if order['status']=='FILLED' and filled != integer(record['payload']['quantity']):
            raise SafetyStop('FILLED status with incomplete execution')
        if filled:
            if any(ex.get(k) is None for k in ('filledAmount','commission','tax')):
                raise SafetyStop('Fill costs not yet available; restart later to reconcile')
            amount,fee,tax=(dec(ex[k]) for k in ('filledAmount','commission','tax'))
        else:
            amount=fee=tax=Decimal(0)
        old=record.get('applied',{'qty':0,'amount':'0','fee':'0','tax':'0'})
        dq=filled-old['qty']
        da,df,dt=amount-dec(old['amount']),fee-dec(old['fee']),tax-dec(old['tax'])
        if min(dq,da,df,dt)<0:
            raise SafetyStop('Execution regressed; manual reconciliation needed')
        cash,cost=dec(self.s['cash']),dec(self.s['cost'])
        if record['payload']['side']=='BUY':
            cash-=da+df+dt
            cost+=da+df+dt
            self.s['quantity']+=dq
        else:
            if dq>self.s['quantity']:
                raise SafetyStop('Sell fill exceeds managed position')
            if self.s['quantity']:
                cost*=Decimal(self.s['quantity']-dq)/self.s['quantity']
            cash+=da-df-dt
            self.s['quantity']-=dq
        if cash<0:
            raise SafetyStop('Managed cash became negative')
        self.s.update(cash=str(cash),cost=str(cost))
        record['applied']=dict(qty=filled,amount=str(amount),fee=str(fee),tax=str(tax))
        record['status']=order['status']
        # PARTIAL_FILLED can also occur in CLOSED; never assume completion from quantity alone.
        record['done']=order['status'] in ('FILLED','CANCELED','REJECTED') or (
            order['status']=='PARTIAL_FILLED' and bool(order.get('canceledAt')))
        if order['status'] not in ('PENDING','PARTIAL_FILLED','PENDING_CANCEL','FILLED','CANCELED','REJECTED'):
            self.store.save()
            raise SafetyStop('Unexpected order status; manual inspection required')
        self.store.save()

    def recover(self,order_id):
        record=self.active()
        if not record or record.get('order_id'):
            raise SafetyStop('No unknown order to recover')
        order=self.b.detail(order_id)
        self.verify_order(record,order)
        delta=(stamp(order['orderedAt'])-stamp(record['created'])).total_seconds()
        if not -5 <= delta <= 120:
            raise SafetyStop('Recovery order timestamp does not match submission')
        if not self.live:
            raise SafetyStop('Recovery requires --live to modify live state')
        record['order_id']=order_id
        self.store.save()
        self.reconcile()

    def cancel_pending(self,force=False):
        record=self.active()
        if not record:
            return False
        age=(self.clock()-stamp(record['created'])).total_seconds()
        if not force and age < self.c['cancel_after_seconds']:
            return True
        if not self.live:
            return True
        if record.get('cancel_attempted'):
            if (self.clock()-stamp(record['cancel_attempted'])).total_seconds()>120:
                raise SafetyStop('Cancel unconfirmed. Check remaining order in Toss.')
            return True
        # Persist before mutation; an unknown cancellation is never blindly repeated.
        record['cancel_attempted']=self.clock().isoformat()
        self.store.save()
        result=self.b.cancel(record['order_id'])
        record['cancel_response_id']=result['orderId']
        self.store.save()
        return True

    def observe(self,equity,now):
        iso=now.isocalendar()
        keys={'daily':now.date().isoformat(),'weekly':f'{iso.year}-W{iso.week:02}',
              'monthly':now.strftime('%Y-%m')}
        rates={}
        target_hit=False
        for kind,key in keys.items():
            p=self.s['periods'].get(kind)
            if not p or p['key']!=key:
                p={'key':key,'base':self.s['last_equity'],'hit':False,'loss_hit':False}
                self.s['periods'][kind]=p
            base=dec(p['base'])
            rate=equity/base-1 if base else Decimal(0)
            p['hit']=p['hit'] or rate>=dec(self.c[kind+'_target'])
            if kind=='daily':
                p['loss_hit']=p['loss_hit'] or rate<=-dec(self.c['daily_loss_limit'])
            rates[kind]=str(rate)
            target_hit=target_hit or p['hit']
        peak=max(dec(self.s['peak']),equity)
        self.s['halted']=self.s['halted'] or equity<=peak*(1-dec(self.c['max_drawdown']))
        self.s.setdefault('equity_history_base',self.s['last_equity'])
        self.s['observed_max_drawdown']=str(max(dec(self.s.get('observed_max_drawdown','0')),1-equity/peak if peak else Decimal(0)))
        self.s.update(peak=str(peak),last_equity=str(equity),returns=rates)
        history=self.s.setdefault('equity_history',[])
        row={'date':now.date().isoformat(),'equity':str(equity),'timestamp':now.isoformat()}
        if history and history[-1]['date']==row['date']: history[-1]=row
        else: history.append(row)
        self.store.save()
        return target_hit,self.s['periods']['daily']['loss_hit']

    def market(self):
        now=self.clock()
        cal=self.b.get('market-calendar/KR',{'date':now.date().isoformat()})
        today=cal['today']
        if today['date']!=now.date().isoformat():
            raise SafetyStop('Market calendar date mismatch')
        session=(today.get('integrated') or {}).get('regularMarket')
        next_session=((cal.get('nextBusinessDay') or {}).get('integrated') or {}).get('regularMarket') or {}
        self.market_status={'status':'OUTSIDE_REGULAR_SESSION','market_state':'HOLIDAY',
                            'checked_at':now.isoformat(),'next_open':next_session.get('startTime')}
        if not session:
            return None
        start=stamp(session['startTime'])+timedelta(minutes=2)
        end=stamp(session['singlePriceAuctionStartTime'])-timedelta(minutes=2)
        self.market_status.update(market_state='BEFORE_OPEN' if now<start else 'SESSION_FINISHED',
            next_open=session['startTime'] if now<start else next_session.get('startTime'))
        if now<start: self.market_status['bot_start']=start.isoformat()
        if not start<=now<end:
            return None
        return cal,start,end

    def fresh(self,value):
        age=(self.clock()-stamp(value)).total_seconds()
        if not -2<=age<=self.c['max_quote_age_seconds']:
            raise SafetyStop('Stale/future market data; no order sent')

    def submit(self,side,quantity,price,reason):
        if side not in ('BUY','SELL') or integer(quantity)<=0 or integer(price)<=0:
            raise SafetyStop('Invalid order proposal')
        if not self.live:
            return {'mode':'DRY_RUN','side':side,'quantity':quantity,'price':str(price),'reason':reason}
        if self.active():
            raise SafetyStop('An order is already pending')
        payload=dict(clientOrderId=str(uuid.uuid4()),symbol=self.symbol,side=side,
                     orderType='LIMIT',timeInForce='DAY',quantity=str(quantity),price=str(price))
        record=dict(payload=payload,created=self.clock().isoformat(),reason=reason,done=False)
        self.s['orders'].append(record)
        if side=='BUY':
            self.s['last_buy_day']=self.clock().date().isoformat()
        self.store.save()
        result=self.b.place(payload)
        if result.get('clientOrderId')!=payload['clientOrderId'] or not result.get('orderId'):
            raise SafetyStop('Unknown submit response; inspect broker before recovery')
        record['order_id']=result['orderId']
        self.store.save()
        return {'mode':'LIVE','side':side,'quantity':quantity,'price':str(price),'reason':reason}

    def check_stock(self,stock):
        detail=stock['koreanMarketDetail']
        if (stock['currency']!='KRW' or stock['market'] not in ('KOSPI','KOSDAQ') or
                stock['securityType']!='STOCK' or stock['isCommonShare'] is not True or stock['status']!='ACTIVE' or not detail or
                detail['liquidationTrading'] or detail['krxTradingSuspended']):
            raise SafetyStop('Only active KOSPI/KOSDAQ ordinary stocks are supported')

    def research_gate(self,previous_day):
        return {'allow_buy':True,'exit':False,'reasons':[]}

    def cost_buffer(self):
        return Decimal('0.004')

    def profit_reached(self,last,bid,entry,fee):
        return last>=entry*(1+dec(self.c['take_profit']))

    def step(self,stop=False):
        self.reconcile()
        opens=self.b.orders()
        own=self.active()
        if any(o['orderId']!=(own or {}).get('order_id') for o in opens):
            raise SafetyStop('Unmanaged open order found; no new orders sent')
        if own:
            self.cancel_pending(force=stop)
            return {'status':'STOPPING' if stop else 'PENDING','order_status':own.get('status')}
        if stop:
            return {'status':'STOPPED','holdings_retained':self.s['quantity']}
        if self.holdings()!=self.s['quantity']:
            raise SafetyStop('Broker/managed holdings differ; manual activity or corporate action detected')
        self.check_conditions()
        window=self.market()
        if not window:
            return self.market_status
        cal,start,end=window
        stocks=self.b.get('stocks',{'symbols':self.symbol})
        if len(stocks)!=1 or stocks[0]['symbol']!=self.symbol:
            raise SafetyStop('Stock metadata missing')
        stock=stocks[0]
        self.check_stock(stock)
        research=self.research_gate(cal['previousBusinessDay']['date'])
        warnings=self.b.get('stocks/'+self.symbol+'/warnings')
        candles=self.b.get('candles',{'symbol':self.symbol,'interval':'1d','count':self.c['slow']+10,'adjusted':'true'})['candles']
        now=self.clock()
        completed={}
        for row in candles:
            day=stamp(row['timestamp']).date().isoformat()
            if day<now.date().isoformat():
                if day in completed or row['currency']!='KRW':
                    raise SafetyStop('Invalid daily candles')
                close=dec(row['closePrice'])
                if close<=0:
                    raise SafetyStop('Invalid closing price')
                completed[day]=close
        days=sorted(completed)
        if len(days)<self.c['slow'] or days[-1]!=cal['previousBusinessDay']['date']:
            raise SafetyStop('Completed daily candles unavailable or stale')
        closes=[completed[d] for d in days]
        fast=sum(closes[-self.c['fast']:])/self.c['fast']
        slow=sum(closes[-self.c['slow']:])/self.c['slow']
        power=dec(self.b.get('buying-power',{'currency':'KRW'},account=True)['cashBuyingPower'])
        commissions=self.b.get('commissions',account=True)
        day=now.date().isoformat()
        fees=[dec(r['commissionRate']) for r in commissions if r['marketCountry']=='KR'
              and (r.get('startDate') is None or r['startDate']<=day)
              and (r.get('endDate') is None or r['endDate']>=day)]
        if len(fees)!=1 or fees[0]>=1:
            raise SafetyStop('Current commission unavailable')
        sellable=integer(self.b.get('sellable-quantity',{'symbol':self.symbol},account=True)['sellableQuantity']) if self.s['quantity'] else 0
        # Get fresh quotes last; use displayed prices to respect exchange tick sizes.
        quotes=self.b.get('prices',{'symbols':self.symbol})
        if len(quotes)!=1 or quotes[0]['symbol']!=self.symbol or quotes[0]['currency']!='KRW':
            raise SafetyStop('Invalid quote identity')
        quote=quotes[0]
        book=self.b.get('orderbook',{'symbol':self.symbol})
        self.fresh(quote['timestamp'])
        self.fresh(book['timestamp'])
        if book['currency']!='KRW':
            raise SafetyStop('Invalid book currency')
        asks=[integer(r['price']) for r in book['asks'] if dec(r['volume'])>0]
        bids=[integer(r['price']) for r in book['bids'] if dec(r['volume'])>0]
        if not asks or not bids or min(asks)<=0 or max(bids)<=0 or min(asks)<max(bids):
            raise SafetyStop('Empty/crossed orderbook')
        ask,bid=Decimal(min(asks)),Decimal(max(bids))
        last=dec(quote['lastPrice'])
        if last<=0:
            raise SafetyStop('Invalid last price')
        quantity=self.s['quantity']
        # Conservative liquidation estimate for targets; actual fills use actual tax/fees.
        equity=dec(self.s['cash'])+quantity*bid*(1-fees[0]-self.cost_buffer())
        target_hit,daily_loss=self.observe(equity,self.clock())
        report={'status':'HOLD','equity':str(equity),'returns':self.s['returns'],
                'target_paused':target_hit,'halted':self.s['halted'],'quantity':quantity,
                'symbol':self.symbol,'research_reasons':research['reasons']}
        reason=None
        side=None
        if quantity:
            entry=dec(self.s['cost'])/quantity
            if self.s['halted'] or daily_loss: reason='LOSS_LIMIT'
            elif last<=entry*(1-dec(self.c['stop_loss'])): reason='STOP_LOSS'
            elif self.profit_reached(last,bid,entry,fees[0]): reason='TAKE_PROFIT'
            elif target_hit: reason='PERIOD_TARGET'
            elif research['exit']: reason='FUNDAMENTALS_AND_NEWS_EXIT'
            elif fast<slow: reason='TREND_EXIT'
            if reason:
                quantity=min(quantity,sellable)
                side,price='SELL',bid
        elif (not target_hit and not daily_loss and not self.s['halted'] and not warnings
              and research['allow_buy'] and fast>slow and self.s['last_buy_day']!=self.clock().date().isoformat()):
            budget=min(dec(self.s['cash']),power,dec(self.c['max_order_won']),equity*dec(self.c['allocation']))
            quantity=max(0,int((budget-Decimal(10))/(ask*(1+fees[0]+Decimal('0.001')))))
            side,price,reason='BUY',ask,'TREND_ENTRY'
        if side and quantity>0:
            if (ask-bid)/bid>dec(self.c['max_spread']):
                return dict(report,status='SPREAD_TOO_WIDE')
            # Recheck pending orders and the kill switch immediately before submission.
            if self.b.orders():
                raise SafetyStop('Open order appeared before submission')
            if not start<=self.clock()<end:
                return dict(report,status='SESSION_ENDED')
            self.fresh(quote['timestamp'])
            self.fresh(book['timestamp'])
            if (ROOT/'STOP').exists():
                return {'status':'STOP_REQUESTED'}
            return self.submit(side,quantity,price,reason)
        return report


def main(argv=None,broker=None):
    p=argparse.ArgumentParser(description='Toss live trader; default is read-only signal check')
    p.add_argument('--config',type=Path,default=ROOT/'live_config.json')
    p.add_argument('--live',action='store_true',help='Enable real orders; local credentials required')
    p.add_argument('--etf',action='store_true',help='KOSDAQ-related ETF top-20 by net assets')
    p.add_argument('--once',action='store_true')
    p.add_argument('--candidate-report',action='store_true',help='Read-only ETF candidate analysis, no orders')
    p.add_argument('--accounts',action='store_true',help='List accountSeq/type, never account numbers')
    p.add_argument('--recover-order',help='Bind broker-confirmed order ID after ambiguous submission; never resends')
    args=p.parse_args(argv)
    if args.candidate_report and (args.live or not args.etf or args.recover_order):
        p.error('Candidate report requires --etf and forbids --live/--recover-order')
    runtime=ROOT/'runtime'
    with process_lock(runtime/'bot.lock'):
        from credentials import load_environment
        load_environment()
        broker=broker or TossBroker(live=args.live)
        broker.live=args.live
        if args.accounts:
            print(json.dumps([{'accountSeq':a['accountSeq'],'accountType':a['accountType']} for a in broker.get('accounts')]))
            return
        if not broker.account.isdigit():
            raise SafetyStop('Set TOSS_ACCOUNT_SEQ locally; --accounts lists available selectors')
        config=load_config(ROOT/'etf_config.json' if args.etf and args.config==ROOT/'live_config.json' else args.config)
        if args.etf != (config.get('strategy')=='kosdaq_etf_top20'):
            raise SafetyStop('ETF configuration requires --etf')
        prefix='etf_' if args.etf else ''
        other=Store(runtime/('live_state.json' if args.etf else 'etf_live_state.json')).data
        if other and (other.get('quantity') or any(not o.get('done') for o in other['orders'])):
            raise SafetyStop('Other strategy has positions/orders: reconcile it first')
        # Dry runs cannot update live execution state or risk baselines.
        store=Store(runtime/(prefix+('live_state.json' if args.live else 'dry_state.json')))
        if not args.live:
            live_snapshot=Store(runtime/(prefix+'live_state.json')).data
            if live_snapshot is not None:
                store.data=live_snapshot
            else:
                store.data=None
        if args.etf:
            from etf_live import EtfBot
            bot=EtfBot(broker,config,store,live=args.live)
        else:
            bot=LiveBot(broker,config,store,live=args.live)
        print(json.dumps({'status':'INITIALIZING'},ensure_ascii=False),flush=True)
        bot.initialize()
        if args.candidate_report:
            from candidate_feedback import market_context,failure
            cal=broker.get('market-calendar/KR',{'date':bot.clock().date().isoformat()})
            market=market_context(cal,bot.clock())
            try:bot.select(cal['previousBusinessDay']['date'],preview=True)
            except Exception as exc:
                print(json.dumps(failure(exc,market),ensure_ascii=False),flush=True)
                return
            bot.selection_details['market']=market
            print(json.dumps({'status':'CANDIDATE_REPORT','selection_details':bot.selection_details},ensure_ascii=False),flush=True)
            return
        if args.recover_order:
            bot.recover(args.recover_order)
            print('Recovery saved. Inspect state, then restart normally.')
            return
        print('LIVE ORDERS ENABLED' if args.live else 'READ ONLY: no orders will be sent',flush=True)
        updater=None
        if args.etf and config.get('auto_research') and not args.once:
            from auto_research import AutoResearch
            updater=AutoResearch(ROOT/config['research_file'])
        try:
            while True:
                stopped=(ROOT/'STOP').exists()
                if stopped:
                    print(json.dumps({'status':'STOP_CHECKING'},ensure_ascii=False),flush=True)
                    if updater: updater.close()
                update_state=updater.tick_broker(broker) if updater and not stopped else None
                try:
                    result=bot.step(stop=stopped)
                except BrokerError:
                    pending=bot.active()
                    if pending and not pending.get('order_id'):
                        raise SafetyStop('UNKNOWN order outcome; automatic resubmission blocked') from None
                    result={'status':'BROKER_CONNECTION_WAIT'}
                if update_state: result['auto_research']=update_state
                print(json.dumps(result,ensure_ascii=False),flush=True)
                if result.get('status')=='STOPPED' or args.once:
                    break
                deadline=time.monotonic()+config['poll_seconds']
                while time.monotonic()<deadline:
                    if not stopped and (ROOT/'STOP').exists(): break
                    time.sleep(min(0.25,max(0,deadline-time.monotonic())))
        finally:
            if updater: updater.close()


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Process stopped. Existing broker orders/holdings remain; check Toss.')
    except (SafetyStop,BrokerError,KeyError,ValueError,OSError,TypeError) as exc:
        if '--candidate-report' in sys.argv:
            from candidate_feedback import failure
            print(json.dumps(failure(exc),ensure_ascii=False),flush=True)
        # Exceptions from API parsing may contain private values; print only known-safe messages.
        print('STOP:',str(exc) if isinstance(exc,(SafetyStop,BrokerError)) else type(exc).__name__)
        print('No automatic retry. Check runtime state and Toss orders before restarting.')
        raise SystemExit(1)
