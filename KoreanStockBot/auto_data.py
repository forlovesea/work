"""KRX collection through pinned pykrx, with strict raw schema validation.

pykrx's OHLCV wrapper omits total net assets. Use the raw ETF endpoint instead.
"""
import csv
import os
import re
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from live import SafetyStop, Store
from etf_research import number, universe

KRX_SOURCE='https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd'


def code(value):
    value=str(value).strip()
    if re.fullmatch(r'KR[A-Z0-9]{10}',value): value=value[3:9]
    if not re.fullmatch('[A-Z0-9]{6}',value): return None
    return value


class KrxData:
    def __init__(self):
        if not os.environ.get('KRX_ID') or not os.environ.get('KRX_PW'):
            raise SafetyStop('KRX_ID and KRX_PW are required for automatic KRX collection')
        # The library logs in at import time. Called only inside the bounded worker.
        from pykrx.website.krx.etx import core
        self.core=core

    def call(self,name,*args):
        time.sleep(1.1)
        try:
            frame=getattr(self.core,name)().fetch(*args)
            if frame.empty: raise ValueError()
            return frame.to_dict(orient='records')
        except Exception:
            raise SafetyStop('KRX response unavailable or changed; waiting for valid data') from None

    def daily(self,day): return self.call('전종목시세_ETF',day.replace('-',''))
    def metadata(self): return self.call('ETF_전종목기본종목')
    def composition(self,day,isin): return self.call('PDF',day.replace('-',''),isin)


def normalize_catalog(daily,metadata,day):
    date.fromisoformat(day)
    meta={}
    for row in metadata:
        symbol=code(row['ISU_SRT_CD'])
        if not symbol or symbol in meta: raise SafetyStop('KRX metadata symbols invalid')
        meta[symbol]=row
    rows=[]
    seen=set()
    for item in daily:
        symbol=code(item['ISU_SRT_CD'])
        if not symbol or symbol in seen: raise SafetyStop('KRX daily symbols invalid')
        seen.add(symbol)
        m=meta.get(symbol)
        name=str(item['ISU_ABBRV'])
        benchmark=str(item['IDX_IND_NM'])
        label=(name+benchmark+(str(m.get('ETF_OBJ_IDX_NM','')) if m else '')).upper()
        if '코스닥' not in label and 'KOSDAQ' not in label: continue
        if m is None: raise SafetyStop('Relevant ETF metadata missing; rank cannot be established')
        net=number(item['INVSTASST_NETASST_TOTAMT'])
        if net<=0: raise SafetyStop('Relevant ETF net assets missing; never substitute market cap or NAV')
        listed=str(m['LIST_DD']).replace('/','-')
        if date.fromisoformat(listed)>date.fromisoformat(day):
            raise SafetyStop('ETF listing date is later than snapshot')
        factor=str(m['IDX_CALC_INST_NM2']).strip()
        match=re.search(r'\((-?\d+(?:\.\d+)?)\)\s*$',factor)
        leverage=number(match.group(1)) if match else Decimal(0)
        structure='unknown'
        if m['ETF_REPLICA_METHD_TP_CD']=='실물' and m['IDX_ASST_CLSS_NM']=='주식': structure='physical'
        if m['ETF_REPLICA_METHD_TP_CD']=='합성': structure='synthetic'
        if '파생' in str(m['ISU_NM']): structure='derivative'
        if m['IDX_MKT_CLSS_NM']!='국내': structure='unknown'
        isin=str(m['ISU_CD'])
        if not re.fullmatch(r'KR[A-Z0-9]{10}',isin): raise SafetyStop('Invalid ETF ISIN')
        rows.append(dict(as_of=day,symbol=symbol,name=name,benchmark=benchmark or m['ETF_OBJ_IDX_NM'],
                         net_assets_won=str(net),leverage=str(leverage),structure=structure,
                         source_url=KRX_SOURCE,isin=isin))
    if not rows: raise SafetyStop('No KOSDAQ-related ETFs returned by KRX')
    return rows


def normalize_composition(items,etf,day,corporations):
    total=Decimal(0)
    seen=set()
    rows=[]
    for item in items:
        raw=str(item['COMPST_ISU_CD']).strip()
        if raw in seen: raise SafetyStop('Duplicate constituent in KRX composition')
        seen.add(raw)
        weight=number(item['COMPST_RTO'])/100
        if not 0<=weight<=1: raise SafetyStop('Invalid KRX constituent weight')
        total+=weight
        symbol=code(raw)
        corp=corporations.get(symbol)
        if not corp or weight==0: continue # Cash, futures, other funds and unmapped companies stay unscored.
        rows.append(dict(as_of=day,etf_symbol=etf,stock_symbol=symbol,corp_code=corp['corp_code'],
                         name=corp['name'],weight=str(weight),source_url=KRX_SOURCE))
    # Never renormalize missing cash/derivative/unknown weights to 100%.
    if total>Decimal('1.005') or total<Decimal('.5'):
        raise SafetyStop('KRX composition weights are incomplete or exceed 100%')
    # Percent fields are rounded; downstream budget remains bounded to full ETF weight.
    if sum(number(r['weight']) for r in rows)>Decimal('1.001'):
        raise SafetyStop('Rounded composition exceeds accepted weight bound')
    return rows


def write_csv(path,rows,columns):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    with temp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore')
        w.writeheader(); w.writerows(rows)
    os.replace(temp,path)


def collect_inputs(day,directory,sources,krx=None):
    from collection_log import audited
    directory=Path(directory)
    raw_path=directory/('krx-'+day+'.json')
    cached=Store(raw_path).data
    if cached is None:
        krx=krx or KrxData()
        daily=audited(sources,'KRX_ETF_DAILY','KRX',krx.daily,day)
        metadata=audited(sources,'KRX_ETF_METADATA','KRX',krx.metadata)
        catalog=audited(sources,'KRX_CATALOG_VALIDATE','KRX',normalize_catalog,daily,metadata,day)
        store=Store(raw_path); store.data={'daily':daily,'metadata':metadata}; store.save()
    else:
        catalog=audited(sources,'KRX_CATALOG_CACHE','KRX',normalize_catalog,cached['daily'],cached['metadata'],day)
    catalog_path=directory/'universe.csv'
    if hasattr(sources,'record'):sources.record('KRX','cache' if cached is not None else 'network')
    write_csv(catalog_path,catalog,list(catalog[0]))
    top=universe(catalog_path,day)
    corps=sources.corporations()
    compositions=[]
    failures=[]
    for etf in top:
        if not etf['tradable']: continue
        path=directory/(etf['symbol']+'-'+day+'.json')
        try:
            items=Store(path).data
            from_cache=items is not None
            if items is None:
                krx=krx or KrxData()
                items=audited(sources,'KRX_COMPOSITION_REQUEST','KRX',krx.composition,day,etf['isin'])
                normalized=audited(sources,'KRX_COMPOSITION_VALIDATE','KRX',normalize_composition,items,etf['symbol'],day,corps)
                store=Store(path); store.data=items; store.save()
            else:
                normalized=audited(sources,'KRX_COMPOSITION_CACHE','KRX',normalize_composition,items,etf['symbol'],day,corps)
            compositions.extend(normalized)
            if hasattr(sources,'record'):sources.record('KRX','cache' if from_cache else 'network')
        except (SafetyStop,ValueError,KeyError,TypeError):
            # The ETF retains its rank; absent holdings prevents this ETF from buying.
            failures.append(etf['symbol'])
            if hasattr(sources,'record'):sources.record('KRX','error')
    holdings_path=directory/'holdings.csv'
    write_csv(holdings_path,compositions,['as_of','etf_symbol','stock_symbol','corp_code','name','weight','source_url'])
    return catalog_path,holdings_path,failures
