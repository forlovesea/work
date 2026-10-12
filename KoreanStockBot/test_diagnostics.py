import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics import source_text,selection_text
from etf_live import EtfBot
from live import ROOT,Store
from test_etf import FakeResearch
from test_live import FakeBroker
from research_sources import Sources,NEWS_URL


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.b=FakeBroker();self.research=FakeResearch()
        config=json.loads((ROOT/'etf_config.json').read_text())
        self.bot=EtfBot(self.b,config,Store(Path(self.tmp.name)/'state.json'),True,clock=lambda:self.b.now,research=self.research)
        self.bot.initialize()

    def test_price_budget_and_no_orders(self):
        self.b.price=15000
        result=self.bot.step(); detail=result['selection_details']
        self.assertEqual(detail['budget'],'9000')
        self.assertEqual(detail['rows'][0]['state'],'BUDGET')
        self.assertEqual(float(detail['rows'][0]['required']),15160)
        self.assertEqual(float(detail['rows'][0]['shortfall']),6160)
        self.assertIn('6,160원',selection_text(detail))
        self.assertFalse(self.b.sent)

    def test_actual_cash_limits_selection(self):
        self.b.power='1000'
        result=self.bot.step()
        self.assertEqual(result['selection_details']['budget'],'1000')
        self.assertEqual(result['selection_details']['rows'][0]['state'],'BUDGET')

    def test_negative_research_not_blame_budget(self):
        self.research.allow=False
        row=self.bot.step()['selection_details']['rows'][0]
        self.assertEqual(row['state'],'RESEARCH');self.assertNotIn('required',row)

    def test_cache_not_current_key_verification(self):
        source=Sources(Path(self.tmp.name)/'cache',self.b.now)
        source.cache.mkdir()
        # One synthetic cached API response, no credential or network access.
        import hashlib
        params={'query':'test'}
        key=hashlib.sha256(json.dumps([NEWS_URL,params,self.b.now.strftime('%Y-%m-%dT%H')],sort_keys=True).encode()).hexdigest()
        (source.cache/(key+'.json')).write_text('{"items":[]}',encoding='utf-8')
        source.get(NEWS_URL,params)
        self.assertEqual(source.health['NAVER']['network'],0)
        self.assertEqual(source.health['NAVER']['cache'],1)
        text=source_text({'sources':source.health})
        self.assertIn('저장된 자료 사용',text)
        self.assertIn('현재 키의 인증 성공을 검증한 것이 아닙니다',text)

    def test_provider_error_recorded_without_secret(self):
        source=Sources(Path(self.tmp.name)/'cache',self.b.now)
        with patch.object(source,'_get',side_effect=ValueError('fake-secret')):
            with self.assertRaises(ValueError):source.get(NEWS_URL,{})
        self.assertEqual(source.health['NAVER']['errors'],1)
        self.assertNotIn('fake-secret',json.dumps(source.health))


if __name__=='__main__':unittest.main()
