"""Official OpenDART and NAVER Search adapters, with local daily caches."""
import hashlib
import json
import os
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from urllib.error import HTTPError,URLError
from collection_log import CollectionError,audited
from broker import NoRedirect
from live import SafetyStop, Store
from etf_research import financial_summary

NEWS_URL='https://naverapihub.apigw.ntruss.com/search/v1/news'


class Sources:
    def __init__(self,cache,now):
        self.cache=Path(cache)
        self.now=now
        self.opener=build_opener(NoRedirect())
        self.health={}
        self.observer=None
        self.audit=None

    def record(self,provider,state):
        from live import now_kst
        row=self.health.setdefault(provider,{'network':0,'cache':0,'errors':0})
        row['state']=state; row['checked_at']=now_kst().isoformat()
        if state in ('network','cache'):row[state]+=1
        if state=='error':row['errors']+=1
        if self.audit:self.audit.write('SOURCE_RESULT',provider=provider,result=state)
        if self.observer:self.observer(self.health)

    def get(self,url,params,headers=None):
        provider='NAVER' if url==NEWS_URL else 'DART'
        try:return audited(self,'NAVER_NEWS_REQUEST' if provider=='NAVER' else 'DART_FINANCIAL_REQUEST',provider,self._get,url,params,headers,provider)
        except Exception:
            self.record(provider,'error');raise

    def _get(self,url,params,headers,provider):
        public_params={k:v for k,v in params.items() if k!='crtfc_key'}
        bucket=self.now.strftime('%Y-%m-%dT%H') if url==NEWS_URL else self.now.date().isoformat()
        key=hashlib.sha256(json.dumps([url,public_params,bucket],sort_keys=True).encode()).hexdigest()
        path=self.cache/(key+'.json')
        if path.exists():
            result=json.loads(path.read_text(encoding='utf-8'));self.record(provider,'cache');return result
        time.sleep(.4)
        try:
            request=Request(url+'?'+urlencode(params),headers=headers or {})
            with self.opener.open(request,timeout=20) as response: result=json.load(response)
        except HTTPError as exc:
            raise CollectionError('HTTP_ERROR',http_status=exc.code) from None
        except (URLError,TimeoutError,OSError):
            raise CollectionError('NETWORK_OR_TIMEOUT') from None
        except Exception:
            # URLs contain DART credentials: never expose the underlying exception.
            raise CollectionError('INVALID_RESPONSE') from None
        # Do not cache error responses.
        if not isinstance(result,dict): raise SafetyStop('Invalid research provider response')
        if 'status' in result and result['status'] not in ('000','013'):
            code=str(result['status'])
            raise CollectionError('DART_API_REJECTED',provider_code=code if re.fullmatch(r'\d{3}',code) else None)
        if 'errorCode' in result or 'error' in result: raise CollectionError('NAVER_API_REJECTED')
        if url==NEWS_URL and (not isinstance(result,dict) or not isinstance(result.get('items'),list)):
            raise SafetyStop('Invalid NAVER API HUB news response')
        store=Store(path)
        store.data=result
        store.save()
        self.record(provider,'network')
        return result

    def financial(self,corp_code):
        key=os.environ.get('DART_API_KEY')
        if not key: raise CollectionError('MISSING_DART_KEY')
        if not re.fullmatch(r'\d{8}',corp_code): raise SafetyStop('Invalid DART corporation code')
        periods=[]
        for year in (self.now.year,self.now.year-1,self.now.year-2):
            for month,day,code in [(12,31,'11011'),(9,30,'11014'),(6,30,'11012'),(3,31,'11013')]:
                end=date(year,month,day)
                if 0<(self.now.date()-end).days<=400: periods.append((end,year,code))
        periods.sort(reverse=True)
        for end,year,code in periods:
            for fs in ('CFS','OFS'):
                result=self.get('https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json',
                                dict(crtfc_key=key,corp_code=corp_code,bsns_year=str(year),reprt_code=code,fs_div=fs))
                if result['status']=='013': continue
                report=financial_summary(result['list'],corp_code,year,code,end.isoformat(),self.now)
                if report: report['fs_div']=fs
                # Latest report with missing metrics is unknown, not an excuse to use older good results.
                return report
        return None

    def news(self,query):
        client=os.environ.get('NAVER_CLIENT_ID')
        secret=os.environ.get('NAVER_CLIENT_SECRET')
        if not client or not secret: raise CollectionError('MISSING_NAVER_KEYS')
        result=self.get(NEWS_URL,
                        dict(query=query,display=50,start=1,sort='date',format='json'),
                        {'X-NCP-APIGW-API-KEY-ID':client,'X-NCP-APIGW-API-KEY':secret})
        return result['items']

    def corporations(self):
        try:return audited(self,'DART_CORPORATION_MAP','DART',self._corporations)
        except Exception:
            self.record('DART','error');raise

    def _corporations(self):
        """Download the official symbol-to-corporation map; never ask for a CSV."""
        path=self.cache/('corporations-'+self.now.date().isoformat()+'.json')
        if path.exists():
            result=json.loads(path.read_text(encoding='utf-8'));self.record('DART','cache');return result
        key=os.environ.get('DART_API_KEY')
        if not key: raise CollectionError('MISSING_DART_KEY')
        try:
            request=Request('https://opendart.fss.or.kr/api/corpCode.xml?'+urlencode({'crtfc_key':key}))
            with self.opener.open(request,timeout=30) as response: data=response.read(16_000_001)
            result=parse_corporations(data)
        except HTTPError as exc:
            raise CollectionError('HTTP_ERROR',http_status=exc.code) from None
        except (URLError,TimeoutError,OSError):
            raise CollectionError('NETWORK_OR_TIMEOUT') from None
        except Exception:
            raise CollectionError('INVALID_CORPORATION_MAP') from None
        store=Store(path); store.data=result; store.save()
        self.record('DART','network')
        return result


def parse_corporations(data):
    import io
    import zipfile
    import xml.etree.ElementTree as ET
    if len(data)>16_000_000: raise SafetyStop('Corporation archive too large')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos=[i for i in archive.infolist() if i.filename.upper()=='CORPCODE.XML']
        if len(infos)!=1 or infos[0].file_size>80_000_000: raise SafetyStop('Unexpected corporation archive')
        raw=archive.read(infos[0])
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): raise SafetyStop('XML declarations refused')
    result={}
    for item in ET.fromstring(raw).findall('list'):
        symbol=(item.findtext('stock_code') or '').strip()
        corp=(item.findtext('corp_code') or '').strip()
        if not re.fullmatch('[A-Z0-9]{6}',symbol): continue
        if not re.fullmatch(r'\d{8}',corp) or symbol in result: raise SafetyStop('Ambiguous corporation map')
        result[symbol]={'corp_code':corp,'name':(item.findtext('corp_name') or '').strip()}
    if not result: raise SafetyStop('No listed companies in corporation map')
    return result
