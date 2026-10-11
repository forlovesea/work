"""Point-in-time ETF universe and explainable research gates (not return forecasts)."""
import csv
import hashlib
import html
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
from live import SafetyStop, stamp


def number(value):
    try:
        result=Decimal(str(value).replace(',','').strip())
        if not result.is_finite(): raise ValueError()
        return result
    except (InvalidOperation,ValueError):
        raise SafetyStop('Invalid research number') from None


def source_url(value,allow_http=False):
    url=urlparse(value)
    if url.scheme not in (('https','http') if allow_http else ('https',)) or not url.hostname or url.username or url.password:
        raise SafetyStop('Research source must be a public HTTPS URL')
    return value


def read_csv(path,columns):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not set(columns)<=set(reader.fieldnames or []):
            raise SafetyStop('Missing CSV columns: '+','.join(columns))
        return list(reader)


def universe(path,as_of):
    """Rank BEFORE tradability filters; never backfill rank 21 after exclusions."""
    rows=read_csv(path,['as_of','symbol','name','benchmark','net_assets_won','leverage','structure','source_url'])
    seen=set()
    candidates=[]
    if not rows: raise SafetyStop('ETF universe CSV is empty; import the complete official ETF snapshot')
    dates={r['as_of'] for r in rows}
    if dates!={as_of}:
        raise SafetyStop('ETF universe must contain one complete common valuation date')
    date.fromisoformat(as_of)
    for row in rows:
        if not re.fullmatch('[A-Z0-9]{6}',row['symbol']) or row['symbol'] in seen:
            raise SafetyStop('Duplicate/invalid ETF symbol')
        seen.add(row['symbol'])
        source_url(row['source_url'])
        nav=number(row['net_assets_won'])
        lev=number(row['leverage'])
        if nav<=0: raise SafetyStop('Net assets must be positive and expressed in KRW')
        label=re.sub(r'\s+','',row['name']+' '+row['benchmark']).upper()
        if '코스닥' not in label and 'KOSDAQ' not in label: continue
        row=dict(row,net_assets_won=str(nav),leverage=str(lev))
        row['tradable']=(lev==1 and row['structure']=='physical'
                         and not any(word in label for word in ('인버스','레버리지','선물','숏','INVERSE','LEVERAGE','SHORT')))
        candidates.append(row)
    candidates.sort(key=lambda r:(-number(r['net_assets_won']),r['symbol']))
    return [dict(row,rank=i+1) for i,row in enumerate(candidates[:20])]


def holdings(path,as_of):
    rows=read_csv(path,['as_of','etf_symbol','stock_symbol','corp_code','name','weight','source_url'])
    output={}
    seen=set()
    for row in rows:
        day=date.fromisoformat(row['as_of'])
        if not 0<=(date.fromisoformat(as_of)-day).days<=7:
            raise SafetyStop('ETF composition is future-dated or older than 7 days')
        key=(row['etf_symbol'],row['stock_symbol'])
        if key in seen or not re.fullmatch('[A-Z0-9]{6}',row['stock_symbol']):
            raise SafetyStop('Duplicate/invalid constituent')
        seen.add(key)
        if not re.fullmatch('[0-9]{8}',row['corp_code']):
            raise SafetyStop('DART corp_code must have 8 digits')
        weight=number(row['weight'])
        if not 0<weight<=1: raise SafetyStop('Holdings weight must be fraction 0..1, not percent')
        source_url(row['source_url'])
        output.setdefault(row['etf_symbol'],[]).append(dict(row,weight=str(weight)))
    for items in output.values():
        if len({r['as_of'] for r in items})!=1 or sum(number(r['weight']) for r in items)>Decimal('1.001'):
            raise SafetyStop('Mixed composition dates or constituent weights exceed 100%')
    return output


ACCOUNTS={
    'revenue':('ifrs-full_Revenue',),
    'operating_profit':('dart_OperatingIncomeLoss',),
    'net_profit':('ifrs-full_ProfitLoss',),
    'assets':('ifrs-full_Assets',),
    'equity':('ifrs-full_Equity',),
    'operating_cash':('ifrs-full_CashFlowsFromUsedInOperatingActivities',),
}


def financial_summary(rows,corp_code,year,report_code,report_end,now):
    """No inference from account labels; absent/ambiguous standard IDs stay missing."""
    metrics={}
    receipts=set()
    for metric,ids in ACCOUNTS.items():
        expected=('IS','CIS') if metric in ('revenue','operating_profit','net_profit') else (('CF',) if metric=='operating_cash' else ('BS',))
        matches=[r for r in rows if r.get('account_id') in ids and r.get('sj_div') in expected
                 and r.get('corp_code')==corp_code and str(r.get('bsns_year'))==str(year)
                 and r.get('reprt_code')==report_code and r.get('currency')=='KRW']
        # IS and CIS may both carry profit; prefer IS, never sum the duplicates.
        if any(r['sj_div']=='IS' for r in matches): matches=[r for r in matches if r['sj_div']=='IS']
        parsed=[]
        for row in matches:
            receipt=row.get('rcept_no','')
            if not re.fullmatch(r'\d{14}',receipt): continue
            published=date(int(receipt[:4]),int(receipt[4:6]),int(receipt[6:8]))
            if published>=now.date(): continue # Same-day filing time is unknown: use from next day.
            key='thstrm_amount'
            if metric in ('revenue','operating_profit','net_profit') and report_code!='11011':
                key='thstrm_add_amount'
            if row.get(key) in (None,'','-'): continue
            parsed.append(number(row[key]))
            receipts.add(receipt)
        if parsed and len(set(parsed))==1: metrics[metric]=str(parsed[0])
    if len(metrics)!=len(ACCOUNTS) or len(receipts)!=1: return None
    age=(now.date()-date.fromisoformat(report_end)).days
    if not 0<=age<=400: return None
    m={k:number(v) for k,v in metrics.items()}
    if m['assets']<=0: return None
    checks={'revenue_positive':m['revenue']>0,'operating_profit_positive':m['operating_profit']>0,
            'net_profit_positive':m['net_profit']>0,'equity_ratio_30pct':m['equity']/m['assets']>=Decimal('.3'),
            'operating_cash_positive':m['operating_cash']>0}
    return dict(corp_code=corp_code,year=year,report_code=report_code,report_end=report_end,
                score=sum(checks.values())/5,checks=checks,metrics=metrics,
                sources=['https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+r for r in sorted(receipts)])


NEGATIVE=('상장폐지','거래정지','횡령','배임','회계부정','감사의견 거절','자본잠식','실적 쇼크','실적쇼크','적자전환','유동성 위기')
POSITIVE=('흑자전환','실적 개선','실적개선','사상 최대 실적','영업이익 증가','수주 확대')


def news_summary(items,aliases,now):
    from email.utils import parsedate_to_datetime
    accepted=[]
    seen=set()
    aliases=[re.sub(r'\s+','',a).casefold() for a in aliases if len(a)>1]
    for item in items:
        title=html.unescape(re.sub('<[^>]+>','',item['title']))
        description=html.unescape(re.sub('<[^>]+>','',item.get('description','')))
        text=re.sub(r'\s+','',title+' '+description).casefold()
        if not any(a in text for a in aliases): continue
        published=parsedate_to_datetime(item['pubDate'])
        if published.tzinfo is None or not 0<=(now-published).total_seconds()<=7*86400: continue
        url=source_url(item.get('originallink') or item['link'],allow_http=True)
        title_key=re.sub(r'\W+','',title).casefold()
        if url in seen or title_key in seen: continue
        seen.update((url,title_key))
        negative=[w for w in NEGATIVE if re.sub(r'\s+','',w) in text]
        positive=[w for w in POSITIVE if re.sub(r'\s+','',w) in text]
        accepted.append(dict(title=title,url=url,published_at=published.isoformat(),negative=negative,positive=positive))
    return dict(count=len(accepted),risk=any(a['negative'] for a in accepted),
                positive_count=sum(bool(a['positive']) for a in accepted),articles=accepted)


def assess(etf,components,financials,news,now):
    covered=Decimal(0)
    weighted=Decimal(0)
    evidence=[]
    for row in components:
        report=financials.get(row['corp_code'])
        if not report: continue
        weight=number(row['weight'])
        covered+=weight
        weighted+=weight*number(report['score'])
        evidence.append(dict(symbol=row['stock_symbol'],name=row['name'],weight=str(weight),report=report))
    score=weighted/covered if covered else Decimal(0)
    reasons=[]
    if not etf['tradable']: reasons.append('UNSUPPORTED_STRUCTURE')
    if covered<Decimal('.6'): reasons.append('FINANCIAL_COVERAGE_BELOW_60_PERCENT')
    if score<Decimal('.6'): reasons.append('WEAK_FINANCIALS')
    if not news['count']: reasons.append('NO_RECENT_RELEVANT_NEWS')
    if news['risk']: reasons.append('NEWS_RISK_KEYWORD')
    return dict(symbol=etf['symbol'],allow_buy=not reasons,
                exit=covered>=Decimal('.6') and score<Decimal('.4') and news['risk'],
                score=float(score),coverage=float(covered),reasons=reasons,financials=evidence,news=news,
                assessed_at=now.isoformat())


class ResearchBook:
    """Live reads are bounded local file reads; data failures never prevent risk exits."""
    def __init__(self,path): self.path=Path(path)

    def load(self,now,previous_day):
        raw=self.path.read_bytes()
        book=json.loads(raw)
        age=(now-stamp(book['generated_at'])).total_seconds()
        age_limit=7200 if book.get('source_mode')=='automatic' else 36*3600
        if book['as_of']!=previous_day or not 0<=age<=age_limit:
            raise SafetyStop('Research stale: regenerate using previous business-day universe')
        if book.get('schema')!=1 or book.get('ranking')!='net_assets_won':
            raise SafetyStop('Unsupported ETF research schema')
        universe_rows=book['universe']
        if not 1<=len(universe_rows)<=20 or len({r['symbol'] for r in universe_rows})!=len(universe_rows):
            raise SafetyStop('Invalid top-20 universe')
        last=None
        for i,row in enumerate(universe_rows,1):
            nav=number(row['net_assets_won'])
            if row['rank']!=i or nav<=0 or (last is not None and nav>last):
                raise SafetyStop('Invalid net asset ranking')
            last=nav
            a=book['assessments'][row['symbol']]
            if a['symbol']!=row['symbol'] or not isinstance(a['allow_buy'],bool) or not isinstance(a['exit'],bool):
                raise SafetyStop('Invalid assessment identity')
            if not 0<=number(a['score'])<=1 or not 0<=number(a['coverage'])<=Decimal('1.001'):
                raise SafetyStop('Invalid financial score/coverage')
            if not 0<=(now-stamp(a['assessed_at'])).total_seconds()<=36*3600:
                raise SafetyStop('Stale assessment')
        book['digest']=hashlib.sha256(raw).hexdigest()
        return book
