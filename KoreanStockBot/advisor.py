"""Recommendation research, simulated compounding, and individually approved orders.

Polling never enables broker mutations. Real submissions exist only in approve().
"""
import copy
import csv
import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from broker import TossBroker
from live import LiveBot, Store, SafetyStop, MarketDataWait, dec, integer, stamp, now_kst, process_lock
from stock_candidates import screen
from research_sources import Sources
from etf_research import news_summary

DEFAULTS=dict(capital=30000,allocation=.3,max_order_won=9000,fee=.00015,
              sell_reserve=.004,slippage=.001,stop_loss=.03,take_profit=.1,max_drawdown=.1)


def settings(values):
    c=dict(DEFAULTS,**values)
    for key in DEFAULTS:c[key]=float(dec(c[key]))
    if c['capital']<=0 or c['max_order_won']<=0:raise SafetyStop('원금과 주문 상한은 양수여야 합니다.')
    if not 0<c['allocation']<=1:raise SafetyStop('투자 비중은 0 초과 100% 이하여야 합니다.')
    for key in ('fee','sell_reserve','slippage'):
        if not 0<=c[key]<.1:raise SafetyStop('비용 가정은 각각 0% 이상 10% 미만이어야 합니다.')
    for key in ('stop_loss','take_profit','max_drawdown'):
        if not 0<c[key]<1:raise SafetyStop('손익·낙폭 비율은 0% 초과 100% 미만이어야 합니다.')
    return c


def fingerprint(c):
    return hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()


def trading_config(base,c,symbol):
    out=copy.deepcopy(base)
    for key in ('capital','allocation','max_order_won','stop_loss','take_profit','max_drawdown'):out[key]=c[key]
    out.update(symbol=symbol,advisor_sell_reserve=c['sell_reserve'],advisor_estimated_fee=c['fee'])
    return out


def fresh_report(report,now):
    return bool(report and 0<=(now-stamp(report['checked_at'])).total_seconds()<=3600)


def research(broker,base,c,root,progress=lambda message:None,clock=now_kst):
    if broker.live:raise SafetyStop('추천 분석은 읽기 전용 연결에서만 실행합니다.')
    now=clock();sources=Sources(Path(root)/'research/cache',now)
    config=trading_config(base,c,'')
    # Isolated research directory: do not bind to the original bot's ledger.
    result=screen(broker,config,20,lambda **r:progress(f"재무 검사 {r.get('stage','')} · {r.get('done',0)}/{r.get('total','?')}"),
                  root=Path(root)/'screen',sources=sources)
    rows=sorted(result['rows'],key=lambda r:(-sum(r['report']['checks'].values()),-dec(r['market_cap'])))[:12]
    for index,row in enumerate(rows):
        progress(f"뉴스 검사 {index+1}/{len(rows)} · {row['name']}")
        try:
            news=news_summary(sources.news(row['name']),[row['name']],clock())
            row['news']=news
            row['eligible']=news['count']>0 and not news['risk']
            row['score']=sum(row['report']['checks'].values())*20+min(news['positive_count'],5)*2
            row['reason']='최근 7일 관련 기사 없음' if not news['count'] else '뉴스 위험 키워드 발견' if news['risk'] else '재무 통과 · 뉴스 위험 키워드 없음'
        except Exception:
            row.update(eligible=False,score=0,reason='뉴스 확인 실패 · 신규 매수 제외',news={'count':0,'risk':False,'articles':[]})
    rows.sort(key=lambda r:(not r['eligible'],-r['score'],r['symbol']))
    return dict(checked_at=clock().isoformat(),rows=rows,screened=result['screened'],
                scope='업종별 시가총액 상위 20개 중 예산·재무 통과 후보, 재무 우선 상위 12개 뉴스 검토',
                settings=fingerprint(c))


def market_data(broker,config,symbol,clock=now_kst):
    check=LiveBot(broker,dict(config,symbol=symbol),Store(Path('__unused_advisor_state__')),clock=clock)
    window=check.market()
    if not window:return None
    previous=window[0]['previousBusinessDay']['date']
    stocks=broker.get('stocks',{'symbols':symbol})
    if len(stocks)!=1 or stocks[0]['symbol']!=symbol:raise SafetyStop('종목 응답을 확인하지 못했습니다.')
    check.check_stock(stocks[0])
    warnings=broker.get('stocks/'+symbol+'/warnings')
    candles=broker.get('candles',{'symbol':symbol,'interval':'1d','count':config['slow']+10,'adjusted':'true'})['candles']
    completed={}
    for row in candles:
        day=stamp(row['timestamp']).date().isoformat()
        if day<=previous:
            if row['currency']!='KRW' or day in completed:raise SafetyStop('일봉 응답을 확인하지 못했습니다.')
            completed[day]=dec(row['closePrice'])
    days=sorted(completed)
    if len(days)<config['slow'] or days[-1]!=previous or any(v<=0 for v in completed.values()):
        raise SafetyStop('기준 거래일의 일봉이 부족합니다. 다음 조회에서 다시 확인하세요.')
    values=[completed[d] for d in days]
    fast=sum(values[-config['fast']:])/config['fast'];slow=sum(values[-config['slow']:])/config['slow']
    quotes=broker.get('prices',{'symbols':symbol})
    if len(quotes)!=1 or quotes[0]['symbol']!=symbol or quotes[0]['currency']!='KRW':raise SafetyStop('시세 응답 종목이 다릅니다.')
    book=broker.get('orderbook',{'symbol':symbol})
    if book['currency']!='KRW':raise SafetyStop('원화 호가가 아닙니다.')
    check.fresh(quotes[0]['timestamp']);check.fresh(book['timestamp'],'orderbook')
    asks=[dec(r['price']) for r in book['asks'] if dec(r['volume'])>0]
    bids=[dec(r['price']) for r in book['bids'] if dec(r['volume'])>0]
    if not asks or not bids or min(asks)<=0 or max(bids)<=0 or min(asks)<max(bids):raise MarketDataWait(None,'orderbook')
    if not window[1]<=clock()<window[2]:return None
    return dict(ask=min(asks),bid=max(bids),trend=fast>slow,warnings=bool(warnings),
                wide=(min(asks)-max(bids))/max(bids)>dec(config['max_spread']))


class PaperPortfolio:
    def __init__(self,path,c):
        self.store=Store(path);self.c=settings(c)
        if self.store.data is None:
            self.store.data=dict(settings=self.c,cash=str(c['capital']),quantity=0,symbol='',cost='0',
                                 peak=str(c['capital']),equity=str(c['capital']),drawdown='0',halted=False,
                                 last_buy_day=None,trades=[],history=[])
        elif self.store.data['settings']!=self.c:
            raise SafetyStop('기존 모의 기록의 설정과 다릅니다. 모의 기록 보관 후 새로 시작을 사용하세요.')

    @property
    def s(self):return self.store.data

    def tick(self,broker,base,report,clock=now_kst):
        if broker.live:raise SafetyStop('모의매매는 실주문 연결을 사용할 수 없습니다.')
        s=self.s;c=self.c;now=clock()
        current=fresh_report(report,now) and report.get('settings')==fingerprint(c)
        rows=report.get('rows',[]) if current else []
        chosen=next((r for r in rows if r['eligible']),None)
        symbol=s['symbol'] if s['quantity'] else (chosen or {}).get('symbol')
        if not symbol:return '최신 뉴스·재무 후보 없음 · 매수 대기'
        data=market_data(broker,base,symbol,clock)
        if data is None:return '정규 매매시간 밖 · 모의 주문 없이 대기'
        if data['wide']:return '호가 차이가 큼 · 모의 주문 대기'
        fee,slip,reserve=(dec(c[k]) for k in ('fee','slippage','sell_reserve'))
        buy=data['ask']*(1+slip)*(1+fee)
        sell=data['bid']*(1-slip)*(1-fee-reserve)
        equity=dec(s['cash'])+s['quantity']*sell
        peak=max(dec(s['peak']),equity);dd=1-equity/peak
        s['peak']=str(peak);s['drawdown']=str(max(dec(s['drawdown']),dd))
        s['halted']=s['halted'] or dd>=dec(c['max_drawdown'])
        action=None;reason='상승 추세·뉴스·재무 조건 대기'
        row=next((r for r in rows if r['symbol']==symbol),None)
        if s['quantity']:
            net=s['quantity']*sell;cost=dec(s['cost'])
            if s['halted']:reason='최대 낙폭 제한';action='SELL'
            elif net<=cost*(1-dec(c['stop_loss'])):reason='비용 반영 손절';action='SELL'
            elif net>=cost*(1+dec(c['take_profit'])):reason='비용 반영 익절';action='SELL'
            elif row and row['news']['risk']:reason='뉴스 위험';action='SELL'
            elif row and row.get('financial_ok') is False:reason='재무 조건 이탈';action='SELL'
            elif not data['trend']:reason='추세 이탈';action='SELL'
            else:reason='보유 중 · 매도 조건 감시'
            if action:
                qty=s['quantity'];s['cash']=str(dec(s['cash'])+net)
                s.update(quantity=0,symbol='',cost='0')
                s['trades'].append(dict(time=now.isoformat(),side='SELL',symbol=symbol,quantity=qty,price=str(sell),cash=s['cash'],reason=reason))
        elif s['halted']:reason='낙폭 제한 도달 · 신규 모의 매수 중지'
        elif data['trend'] and not data['warnings'] and chosen and s['last_buy_day']!=now.date().isoformat():
            budget=min(dec(s['cash']),dec(s['cash'])*dec(c['allocation']),dec(c['max_order_won']))
            qty=int(budget/buy)
            if qty:
                cost=qty*buy;s['cash']=str(dec(s['cash'])-cost)
                s.update(quantity=qty,symbol=symbol,cost=str(cost),last_buy_day=now.date().isoformat())
                s['company']=copy.deepcopy(chosen)
                action='BUY';reason='재무·뉴스·상승 추세 통과'
                s['trades'].append(dict(time=now.isoformat(),side='BUY',symbol=symbol,quantity=qty,price=str(buy),cash=s['cash'],reason=reason))
            else:reason='수수료 포함 1주 예산 부족'
        equity=dec(s['cash'])+s['quantity']*sell
        s['equity']=str(equity)
        s['history'].append(dict(time=now.isoformat(),equity=str(equity)))
        s['history']=s['history'][-5000:];self.store.save()
        return ('모의 '+action+' · ' if action else '')+reason

    def export(self,path):
        with Path(path).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['time','side','symbol','quantity','price','cash','reason'])
            writer.writeheader();writer.writerows(self.s['trades'])


class ApprovalBot(LiveBot):
    """Even repeated step() calls can only create proposals, never mutations."""
    def __init__(self,*args,report=None,**kwargs):
        kwargs['live']=False
        super().__init__(*args,**kwargs)
        self.report=report;self.proposal=None;self.b.live=False

    def cost_buffer(self):return dec(self.c['advisor_sell_reserve'])

    def profit_reached(self,last,bid,entry,fee):return bid*(1-fee-self.cost_buffer())>=entry*(1+dec(self.c['take_profit']))

    def loss_reached(self,last,bid,entry,fee):return bid*(1-fee-self.cost_buffer())<=entry*(1-dec(self.c['stop_loss']))

    def research_gate(self,previous_day):
        rows=self.report.get('rows',[]) if fresh_report(self.report,self.clock()) else []
        row=next((r for r in rows if r['symbol']==self.symbol),None)
        return dict(allow_buy=bool(row and row['eligible']),exit=bool(row and (row['news']['risk'] or row.get('financial_ok') is False)),
                    reasons=[row['reason'] if row else '최신 분석 없음 · 신규 매수 제외'])

    def submit(self,side,quantity,price,reason):
        self.proposal=dict(id=str(uuid.uuid4()),created=self.clock().isoformat(),symbol=self.symbol,
                           side=side,quantity=quantity,price=str(price),reason=reason)
        return dict(self.proposal,status='APPROVAL_REQUIRED')

    def preview(self):
        self.proposal=None
        return self.step()

    def approve(self,proposal_id):
        original=copy.deepcopy(self.proposal);self.proposal=None
        if Store(self.store.path).data!=self.s:
            raise SafetyStop('주문 기록이 변경됐습니다. 주문안을 새로 확인하세요.')
        if not original or original['id']!=proposal_id or not 0<=(self.clock()-stamp(original['created'])).total_seconds()<=120:
            raise SafetyStop('주문안이 만료됐습니다. 새 주문안을 확인하고 승인하세요.')
        # Re-fetch account, signals, fees, session, fresh quotes and orderbook.
        result=self.step();self.proposal=None
        keys=('symbol','side','quantity','price','reason')
        if result.get('status')!='APPROVAL_REQUIRED' or any(result.get(k)!=original[k] for k in keys):
            raise SafetyStop('가격·수량·조건이 변경됐습니다. 새 주문안을 확인하고 다시 승인하세요.')
        if (self.clock()-stamp(original['created'])).total_seconds()>120:
            raise SafetyStop('검사 중 주문안이 만료됐습니다. 다시 확인하세요.')
        try:
            self.live=True;self.b.live=True
            return LiveBot.submit(self,original['side'],original['quantity'],dec(original['price']),original['reason'])
        finally:
            self.live=False;self.b.live=False;self.proposal=None

    def approve_cancel(self):
        self.proposal=None;self.reconcile()
        record=self.active()
        if not record:return '미체결 주문 없음'
        if not record.get('order_id'):raise SafetyStop('주문 결과 불명확 · 토스 앱에서 확인하세요. 재전송하지 않습니다.')
        try:
            self.live=True;self.b.live=True
            self.cancel_pending(force=True)
            return '취소 요청 처리 · 토스 앱 또는 주문안 갱신으로 최종 상태를 확인하세요.'
        finally:self.live=False;self.b.live=False


class Advisor:
    def __init__(self,root,broker,base,c,clock=now_kst):
        self.root=Path(root);self.b=broker;self.base=base;self.c=settings(c);self.clock=clock
        self.data=self.root/'advisor';self.paper=PaperPortfolio(self.data/'paper.json',self.c)
        self.report=Store(self.data/'recommendations.json').data;self.bot=None

    def analyze(self,progress=lambda message:None):
        self.report=research(self.b,self.base,self.c,self.data,progress,self.clock)
        approved=Store(self.data/'approved_state.json').data or {}
        if approved.get('quantity') and approved.get('advisor_company'):
            progress('실제 보유 관리 종목의 뉴스·재무 추가 확인')
            held=self.inspect_company(approved['advisor_company'])
            self.report['rows']=[r for r in self.report['rows'] if r['symbol']!=held['symbol']]+[held]
        store=Store(self.data/'recommendations.json');store.data=self.report;store.save()
        return self.report

    def refresh_holding(self,progress=lambda message:None):
        """Refresh the held company even after it leaves the shortlist."""
        symbol=self.paper.s['symbol']
        row=next((r for r in (self.report or {}).get('rows',[]) if r['symbol']==symbol),None) or self.paper.s.get('company')
        if not row:return self.analyze(progress)
        progress('보유 모의 종목의 재무·뉴스 갱신 중')
        row=self.inspect_company(row)
        self.report=dict(checked_at=self.clock().isoformat(),settings=fingerprint(self.c),rows=[row],
                         scope='보유 모의 종목 재무·뉴스 재검사',screened=1)
        store=Store(self.data/'recommendations.json');store.data=self.report;store.save()
        return self.report

    def inspect_company(self,row):
        symbol=row['symbol'];sources=Sources(self.data/'research/cache',self.clock())
        corps=sources.corporations();corp=corps.get(symbol)
        financial=sources.financial(corp['corp_code']) if corp else None
        from stock_candidates import financial_pass
        row=copy.deepcopy(row)
        news=news_summary(sources.news(row['name']),[row['name']],self.clock())
        row['news']=news;row['eligible']=bool(financial_pass(financial) and news['count'] and not news['risk'])
        row['financial_ok']=bool(financial_pass(financial)) if financial else None
        row['reason']='보유 종목 분석 갱신 · '+('통과' if row['eligible'] else '재무·뉴스 조건 미충족')
        if financial:row['report']=financial
        row['score']=(sum(financial['checks'].values())*20 if financial else 0)+min(news['positive_count'],5)*2
        return row

    def prepare(self,symbol):
        with process_lock(self.root/'runtime/bot.lock'):
            # Legacy strategies must be closed/reconciled before a new ledger.
            for name in ('live_state.json','etf_live_state.json'):
                legacy=Store(self.root/'runtime'/name).data
                if legacy and (legacy.get('quantity') or any(not o.get('done') for o in legacy.get('orders',[]))):
                    raise SafetyStop('기존 자동매매의 보유분·미완료 주문을 먼저 확인하세요.')
            config_store=Store(self.data/'approved_config.json')
            state=Store(self.data/'approved_state.json')
            existing=(state.data or {}).get('advisor_config') or config_store.data
            proposed=trading_config(self.base,self.c,symbol)
            if existing and existing!=proposed:
                if dict(existing,symbol=symbol)!=proposed:
                    raise SafetyStop('승인매매 기록의 예산·위험 설정과 다릅니다. 기존 설정을 유지하고 기록을 삭제하지 마세요.')
                old=ApprovalBot(self.b,existing,state,report=self.report,clock=self.clock)
                old.initialize();old.reconcile()
                if old.active() or old.s['quantity'] or old.holdings() or self.b.orders():
                    raise SafetyStop('기존 승인 종목의 보유분·미체결을 먼저 정리하세요. 관리 종목: '+existing['symbol'])
                old.check_conditions()
                # Explicit user-selected symbol rotation, preserving realized
                # cash, risk limits, execution history, and the daily buy limit.
                replacement=ApprovalBot(self.b,proposed,state,report=self.report,clock=self.clock)
                state.data.update(binding=replacement.binding,advisor_config=proposed)
                state.save()
            if self.report is None or self.report.get('settings')!=fingerprint(self.c):
                raise SafetyStop('현재 예산으로 뉴스·재무 분석을 먼저 실행하세요.')
            bot=ApprovalBot(self.b,proposed,state,report=self.report,clock=self.clock)
            bot.initialize()
            bot.s['advisor_config']=proposed;bot.store.save()
            company=next((r for r in self.report.get('rows',[]) if r['symbol']==symbol),None)
            if company:bot.s['advisor_company']=copy.deepcopy(company);bot.store.save()
            config_store.data=proposed;config_store.save()
            result=bot.preview();self.bot=bot
            return result

    def approve(self,proposal_id):
        if self.bot is None:raise SafetyStop('주문안을 먼저 생성하세요.')
        with process_lock(self.root/'runtime/bot.lock'):
            return self.bot.approve(proposal_id)

    def cancel(self):
        if self.bot is None:raise SafetyStop('기존 종목으로 주문안/체결 확인을 먼저 실행하세요.')
        with process_lock(self.root/'runtime/bot.lock'):return self.bot.approve_cancel()
