"""Read-only sector screening. No order or account-ledger mutations."""
import contextlib
import hashlib
import io
import json
import os
import re
from collections import Counter,defaultdict
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from live import ROOT,Store,SafetyStop,dec,stamp,KST,LiveBot,process_lock
from collection_log import safe_error

CATEGORIES=('금융','바이오·헬스케어','IT','소재(매터리얼)','산업재','소비재','유틸리티','기타')
CHECK_NAMES={'revenue_positive':'매출 양수','operating_profit_positive':'영업흑자',
 'net_profit_positive':'순이익 흑자','equity_ratio_30pct':'자기자본비율 30% 이상','operating_cash_positive':'영업현금흐름 양수'}

def category(industry):
    text=re.sub(r'[\s·,/-]','',industry)
    for group,words in [('금융',('금융','은행','보험','증권')),
                        ('바이오·헬스케어',('제약','의약','의료','바이오')),
                        ('IT',('전기전자','IT','반도체','정보','소프트웨어','통신','컴퓨터')),
                        ('소재(매터리얼)',('화학','금속','철강','종이','목재','광업','소재')),
                        ('유틸리티',('전기가스','전기수도','전기가스수도','수도')),
                        ('산업재',('기계','운송','건설','장비')),
                        ('소비재',('음식','식료','섬유','의복','유통','도소매','숙박','오락'))]:
        if any(word in text for word in words):return group
    return '기타'

def binding(account,config):
    return hashlib.sha256((account+'|'+json.dumps(config,sort_keys=True)).encode()).hexdigest()

def budget_for(config,power,cash=None):
    capital=dec(config['capital']);allocation=dec(config['allocation']);cap=dec(config['max_order_won'])
    if capital<=0 or cap<=0 or not 0<allocation<=1:raise SafetyStop('Invalid recommendation budget')
    available=min(capital,dec(cash)) if cash is not None else capital
    return max(Decimal(0),min(available,available*allocation,cap,dec(power)))

def required(price):return dec(price)*Decimal('1.01')+10

def shortlist(rows,budget,limit):
    groups=defaultdict(list);seen=set()
    for row in rows:
        symbol=row['symbol']
        if not re.fullmatch(r'[0-9]{6}',symbol) or symbol in seen:continue
        seen.add(symbol)
        if dec(row['price'])<=0 or required(row['price'])>budget:continue
        groups[category(row['industry'])].append(row)
    result=[]
    for group in CATEGORIES:
        items=sorted(groups[group],key=lambda r:(-dec(r['market_cap']),r['symbol']))
        result.extend(dict(r,category=group) for r in (items[:limit] if limit else items))
    return result,{group:len(groups[group]) for group in CATEGORIES}

def financial_pass(report):
    if not report:return False
    checks=report.get('checks',{})
    return (set(checks)==set(CHECK_NAMES) and sum(v is True for v in checks.values())>=4
            and checks['operating_profit_positive'] is True and checks['net_profit_positive'] is True
            and dec(report['metrics']['equity'])>0)

def top_five(rows):
    result=[]
    for group in CATEGORIES:
        eligible=[r for r in rows if r['category']==group]
        eligible.sort(key=lambda r:(-sum(r['report']['checks'].values()),-dec(r['market_cap']),r['symbol']))
        result.extend(eligible[:5])
    return result

def catalog(day):
    if not os.environ.get('KRX_ID') or not os.environ.get('KRX_PW'):
        raise SafetyStop('KRX credentials required')
    # pykrx may print login details; never forward its stdout/stderr.
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
        from pykrx import stock
        result=[]
        for market in ('KOSPI','KOSDAQ'):
            frame=stock.get_market_sector_classifications(day,market)
            if frame.empty:raise SafetyStop('KRX sector catalog unavailable')
            for symbol,row in frame.iterrows():
                result.append(dict(symbol=str(symbol),name=str(row['종목명']),industry=str(row['업종명']),
                    price=str(row['종가']),market_cap=str(row['시가총액']),market=market))
    return result

def screen(broker,config,limit=20,emit=lambda **kw:None,root=ROOT,now=None,sources=None,universe=None):
    from research_sources import Sources
    clock=(lambda:now) if now is not None else (lambda:datetime.now(KST))
    now=clock()
    if broker.live:raise SafetyStop('Recommendation must be read-only')
    emit(stage='ACCOUNT')
    if not any(str(a['accountSeq'])==broker.account for a in broker.get('accounts')):raise SafetyStop('Selected brokerage account not found')
    power=broker.get('buying-power',{'currency':'KRW'},account=True)['cashBuyingPower']
    saved=Store(Path(root)/'runtime/live_state.json').data
    if saved and saved.get('binding')!=binding(broker.account,config):raise SafetyStop('Account/config changed: preserve state; reconcile before changing configuration')
    budget=budget_for(config,power,saved.get('cash') if saved else None)
    calendar=broker.get('market-calendar/KR',{'date':now.date().isoformat()})
    day=calendar['previousBusinessDay']['date']
    emit(stage='KRX')
    rows=universe if universe is not None else catalog(day)
    targets,counts=shortlist(rows,budget,limit)
    sources=sources or Sources(Path(root)/'research/cache',now)
    emit(stage='DART',done=0,total=len(targets))
    corps=sources.corporations() if targets else {}
    qualified=[];accepted=[];excluded=Counter();errors=[]
    for index,row in enumerate(targets):
        emit(stage='DART',done=index,total=len(targets),symbol=row['symbol'])
        try:
            corp=corps.get(row['symbol'])
            if not corp:excluded['NO_DART_MAPPING']+=1;continue
            report=sources.financial(corp['corp_code'])
            if not report:excluded['MISSING_FINANCIALS']+=1;continue
            if not financial_pass(report):excluded['FINANCIAL_RULES']+=1;continue
            qualified.append(dict(row,report=report))
        except Exception as exc:
            fields=safe_error(exc)
            excluded['DATA_ERROR']+=1;errors.append(dict(symbol=row['symbol'],**fields))
            if fields.get('error_code') in ('DART_API_REJECTED','MISSING_DART_KEY'):raise
    # Read prices after the long financial scan, so early rows do not expire during collection.
    power=broker.get('buying-power',{'currency':'KRW'},account=True)['cashBuyingPower']
    budget=budget_for(config,power,saved.get('cash') if saved else None)
    for offset in range(0,len(qualified),200):
        batch=qualified[offset:offset+200]
        emit(stage='PRICES',done=offset,total=len(qualified))
        params={'symbols':','.join(r['symbol'] for r in batch)}
        stocks={s['symbol']:s for s in broker.get('stocks',params)}
        quotes={q['symbol']:q for q in broker.get('prices',params)}
        for row in batch:
            try:
                stock=stocks.get(row['symbol'])
                if not stock:excluded['STOCK_UNAVAILABLE']+=1;continue
                LiveBot.check_stock(None,stock)
                quote=quotes.get(row['symbol'])
                if not quote or quote.get('currency')!='KRW' or dec(quote['lastPrice'])<=0:
                    excluded['QUOTE_UNAVAILABLE']+=1;continue
                if not 0<=(clock()-stamp(quote['timestamp'])).total_seconds()<=config['max_quote_age_seconds']:
                    excluded['QUOTE_STALE']+=1;continue
                cost=required(quote['lastPrice'])
                if cost>budget:excluded['BUDGET']+=1;continue
                accepted.append(dict(row,price=str(quote['lastPrice']),price_at=quote['timestamp'],required=str(cost),quantity=int(budget//cost)))
            except Exception as exc:
                excluded['DATA_ERROR']+=1;errors.append(dict(symbol=row['symbol'],**safe_error(exc)))
    emit(stage='COMPLETE',done=len(targets),total=len(targets))
    return dict(status='STOCK_CANDIDATES',checked_at=datetime.now(KST).isoformat(),as_of=day,
        binding=binding(broker.account,config),budget=str(budget),power=str(power),limit=limit,
        counts=counts,screened=len(targets),rows=top_five(accepted),excluded=dict(excluded),errors=errors)

def apply_selection(root,config_path,account,result,symbol,now=None,save=True):
    now=now or datetime.now(KST);root=Path(root)
    if not re.fullmatch(r'[0-9]{6}',symbol):raise SafetyStop('유효한 6자리 종목을 선택하세요.')
    if not 0<=(now-stamp(result['checked_at'])).total_seconds()<=300:raise SafetyStop('조회 후 5분이 지났습니다. 다시 조회하세요.')
    if symbol not in {r['symbol'] for r in result['rows']}:raise SafetyStop('조회된 후보에서 선택하세요.')
    selected=next(r for r in result['rows'] if r['symbol']==symbol)
    if not 0<=(now-stamp(selected['price_at'])).total_seconds()<=300:raise SafetyStop('선택한 종목의 시세가 오래됐습니다. 다시 조회하세요.')
    with process_lock(root/'runtime/bot.lock'):
        config=json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
        if binding(account,config)!=result['binding']:raise SafetyStop('계좌·설정이 변경되었습니다. 다시 조회하세요.')
        if config.get('symbol')!=symbol and (root/'runtime/live_state.json').exists():
            raise SafetyStop('기존 실전 기록이 있어 종목을 바꿀 수 없습니다. 주문·보유 상태를 먼저 정산하세요.')
        config['symbol']=symbol
        if save:
            store=Store(config_path);store.data=config;store.save()
    return config

def run(broker,config,limit):
    def emit(**data):print(json.dumps(dict(status='STOCK_PROGRESS',**data)),flush=True)
    try:
        report=screen(broker,config,limit,emit)
        print(json.dumps(report),flush=True)
    except Exception as exc:
        from candidate_feedback import failure
        report=failure(exc);report['status']='STOCK_ERROR'
        report['action']='토스·KRX·DART 인증 설정과 연결 상태를 확인하세요. 후보가 없어도 조건을 자동 완화하지 않습니다.'
        print(json.dumps(dict(report,**safe_error(exc))),flush=True)
