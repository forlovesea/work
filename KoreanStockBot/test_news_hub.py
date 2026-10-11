import io
import json
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch,Mock
from urllib.parse import urlparse,parse_qs
from research_sources import Sources,NEWS_URL
from live import KST,SafetyStop


class NewsHubTests(unittest.TestCase):
    def test_request_and_hourly_cache(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ',{'NAVER_CLIENT_ID':'dummy-id','NAVER_CLIENT_SECRET':'dummy-secret'}), patch('research_sources.time.sleep'):
            now=datetime(2026,10,11,10,tzinfo=KST)
            source=Sources(tmp,now)
            source.opener=Mock()
            source.opener.open.side_effect=lambda *a,**k:io.BytesIO(json.dumps({'items':[]}).encode())
            self.assertEqual(source.news('코스닥'),[])
            request=source.opener.open.call_args.args[0]
            self.assertTrue(request.full_url.startswith(NEWS_URL+'?'))
            self.assertEqual(parse_qs(urlparse(request.full_url).query)['format'],['json'])
            headers={k.lower():v for k,v in request.header_items()}
            self.assertEqual(headers['x-ncp-apigw-api-key-id'],'dummy-id')
            self.assertEqual(headers['x-ncp-apigw-api-key'],'dummy-secret')
            self.assertNotIn('x-naver-client-id',headers)
            source.news('코스닥');self.assertEqual(source.opener.open.call_count,1)
            source.now=now+timedelta(hours=1)
            source.news('코스닥');self.assertEqual(source.opener.open.call_count,2)
            for file in Path(tmp).glob('*.json'):self.assertNotIn('dummy-secret',file.read_text())

    def test_error_and_malformed_responses_not_cached(self):
        for payload in ({'error':{'errorCode':'210'}},{'errorCode':'SE01'},{'items':None}):
            with self.subTest(payload=payload),tempfile.TemporaryDirectory() as tmp,patch('research_sources.time.sleep'):
                source=Sources(tmp,datetime(2026,10,11,tzinfo=KST))
                source.opener=Mock()
                source.opener.open.return_value=io.BytesIO(json.dumps(payload).encode())
                with self.assertRaises(SafetyStop):source.get(NEWS_URL,{'query':'test'})
                self.assertEqual(list(Path(tmp).glob('*.json')),[])

if __name__=='__main__':unittest.main()
