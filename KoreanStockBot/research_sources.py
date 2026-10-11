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
from broker import NoRedirect
from live import SafetyStop, Store
from etf_research import financial_summary

NEWS_URL='https://naverapihub.apigw.ntruss.com/search/v1/news'


class Sources:
    def __init__(self,cache,now):
        self.cache=Path(cache)
        self.now=now
        self.opener=build_opener(NoRedirect())

    def get(self,url,params,headers=None):
        public_params={k:v for k,v in params.items() if k!='crtfc_key'}
        bucket=self.now.strftime('%Y-%m-%dT%H') if url==NEWS_URL else self.now.date().isoformat()
        key=hashlib.sha256(json.dumps([url,public_params,bucket],sort_keys=True).encode()).hexdigest()
        path=self.cache/(key+'.json')
        if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
        time.sleep(.4)
        try:
            request=Request(url+'?'+urlencode(params),headers=headers or {})
            with self.opener.open(request,timeout=20) as response: result=json.load(response)
        except Exception:
            # URLs contain DART credentials: never expose the underlying exception.
            raise SafetyStop('Research provider connection/response failed; no credentials logged') from None
        # Do not cache error responses.
        if not isinstance(result,dict): raise SafetyStop('Invalid research provider response')
        if 'status' in result and result['status'] not in ('000','013'):
            raise SafetyStop('DART API returned an error; check key/quota locally')
        if 'errorCode' in result or 'error' in result: raise SafetyStop('NAVER API HUB returned an error; check News permission/key/quota locally')
        if url==NEWS_URL and (not isinstance(result,dict) or not isinstance(result.get('items'),list)):
            raise SafetyStop('Invalid NAVER API HUB news response')
        store=Store(path)
        store.data=result
        store.save()
        return result

    def financial(self,corp_code):
        key=os.environ.get('DART_API_KEY')
        if not key: raise SafetyStop('Set DART_API_KEY locally to retrieve constituent financial statements')
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
        if not client or not secret: raise SafetyStop('Set NAVER_CLIENT_ID and NAVER_CLIENT_SECRET locally')
        result=self.get(NEWS_URL,
                        dict(query=query,display=50,start=1,sort='date',format='json'),
                        {'X-NCP-APIGW-API-KEY-ID':client,'X-NCP-APIGW-API-KEY':secret})
        return result['items']

    def corporations(self):
        """Download the official symbol-to-corporation map; never ask for a CSV."""
        path=self.cache/('corporations-'+self.now.date().isoformat()+'.json')
        if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
        key=os.environ.get('DART_API_KEY')
        if not key: raise SafetyStop('DART_API_KEY is required')
        try:
            request=Request('https://opendart.fss.or.kr/api/corpCode.xml?'+urlencode({'crtfc_key':key}))
            with self.opener.open(request,timeout=30) as response: data=response.read(16_000_001)
            result=parse_corporations(data)
        except Exception:
            raise SafetyStop('DART corporation map download/parse failed') from None
        store=Store(path); store.data=result; store.save()
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
