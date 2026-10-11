import copy
import io
import json
import os
import tempfile
import unittest
import zipfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from auto_data import normalize_catalog,normalize_composition,collect_inputs
from auto_research import AutoResearch,RESEARCH_KEYS
from credentials import save_credentials,load_credentials
from research_sources import parse_corporations
from live import SafetyStop,Store
from etf_research import ResearchBook,universe
from build_research import build
from test_etf import NOW,financial_rows,financial_summary,news_item


def krx_row(symbol='123456',net='1,000,000,000'):
    return {'ISU_SRT_CD':symbol,'ISU_ABBRV':'테스트 코스닥150','IDX_IND_NM':'코스닥 150',
            'INVSTASST_NETASST_TOTAMT':net,'NAV':'98765','MKTCAP':'99999999999999'}


def krx_meta(symbol='123456'):
    return {'ISU_SRT_CD':symbol,'ISU_CD':'KR7'+symbol+'001','LIST_DD':'2020/01/01',
            'ETF_OBJ_IDX_NM':'코스닥 150','IDX_CALC_INST_NM2':'일반 (1)',
            'ETF_REPLICA_METHD_TP_CD':'실물','IDX_ASST_CLSS_NM':'주식',
            'ISU_NM':'테스트코스닥150증권상장지수투자신탁(주식)','IDX_MKT_CLSS_NM':'국내'}


CORPS={'654321':{'corp_code':'00123456','name':'테스트기업'}}
COMPOSITION=[{'COMPST_ISU_CD':'KR7654321001','COMPST_RTO':'65.0'},
             {'COMPST_ISU_CD':'CASH','COMPST_RTO':'35.0'}]


class AutoDataTests(unittest.TestCase):
    def test_net_assets_not_nav_or_marketcap(self):
        row=normalize_catalog([krx_row()],[krx_meta()],'2026-06-29')[0]
        self.assertEqual(row['net_assets_won'],'1000000000')
        self.assertEqual(row['structure'],'physical')
        self.assertEqual(row['leverage'],'1')

    def test_missing_net_assets_must_not_fall_back(self):
        for value in ('0','-','NaN'):
            with self.assertRaises(SafetyStop): normalize_catalog([krx_row(net=value)],[krx_meta()],'2026-06-29')

    def test_metadata_missing_or_future_listing_blocks(self):
        with self.assertRaises(SafetyStop): normalize_catalog([krx_row()],[],'2026-06-29')
        m=krx_meta(); m['LIST_DD']='2026/06/30'
        with self.assertRaises(SafetyStop): normalize_catalog([krx_row()],[m],'2026-06-29')

    def test_leverage_and_synthetic_classification(self):
        m=krx_meta(); m.update(IDX_CALC_INST_NM2='인버스 (-1)',ETF_REPLICA_METHD_TP_CD='합성')
        row=normalize_catalog([krx_row()],[m],'2026-06-29')[0]
        self.assertEqual(row['leverage'],'-1')
        self.assertEqual(row['structure'],'synthetic')

    def test_corporations_mapped_without_normalizing_cash_away(self):
        rows=normalize_composition(COMPOSITION,'123456','2026-06-29',CORPS)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['corp_code'],'00123456')
        self.assertEqual(float(rows[0]['weight']),.65)

    def test_bad_weights_or_duplicate_composition_block(self):
        for rows in [[dict(COMPOSITION[0],COMPST_RTO='150')],COMPOSITION+[COMPOSITION[0]],
                     [dict(COMPOSITION[0],COMPST_RTO='20')]]:
            with self.assertRaises(SafetyStop): normalize_composition(rows,'123456','2026-06-29',CORPS)

    def test_corporation_zip_parser_and_duplicate_symbols(self):
        def zipped(text):
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w') as z: z.writestr('CORPCODE.xml',text)
            return data.getvalue()
        row='<list><stock_code>654321</stock_code><corp_code>00123456</corp_code><corp_name>테스트기업</corp_name></list>'
        self.assertEqual(parse_corporations(zipped('<result>'+row+'</result>')),CORPS)
        with self.assertRaises(SafetyStop): parse_corporations(zipped('<result>'+row+row+'</result>'))
        with self.assertRaises(SafetyStop): parse_corporations(zipped('<!DOCTYPE bad><result/>'))

    def test_end_to_end_no_user_input_files(self):
        class FakeKrx:
            calls=0
            def daily(self,day): self.calls+=1; return [krx_row()]
            def metadata(self): return [krx_meta()]
            def composition(self,day,isin): return COMPOSITION
        class FakeSources:
            def corporations(self): return CORPS
            def financial(self,corp): return financial_summary(financial_rows(),corp,2025,'11011','2025-12-31',NOW)
            def news(self,query): return [news_item()]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); krx=FakeKrx(); sources=FakeSources()
            u,h,failures=collect_inputs('2026-06-29',root/'inputs',sources,krx)
            self.assertEqual(failures,[])
            book=build(u,h,'2026-06-29',root/'latest.json',sources,NOW)
            self.assertTrue(book['assessments']['123456']['allow_buy'])
            collect_inputs('2026-06-29',root/'inputs',sources,krx)
            self.assertEqual(krx.calls,1)

    def test_failed_composition_preserves_rank_but_disables_buy(self):
        class FakeKrx:
            def daily(self,day): return [krx_row()]
            def metadata(self): return [krx_meta()]
            def composition(self,*args): raise SafetyStop('unavailable')
        class FakeSources:
            def corporations(self): return CORPS
        with tempfile.TemporaryDirectory() as tmp:
            u,h,failed=collect_inputs('2026-06-29',tmp,FakeSources(),FakeKrx())
            self.assertEqual(failed,['123456'])
            self.assertEqual(universe(u,'2026-06-29')[0]['rank'],1)
            self.assertEqual(len(h.read_text(encoding='utf-8-sig').splitlines()),1)


class Child:
    def __init__(self): self.result=None; self.terminated=False
    def poll(self): return self.result
    def terminate(self): self.terminated=True; self.result=-1
    def wait(self,timeout): return self.result


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.calls=[]; self.t=0
        def popen(*a,**kw):
            self.calls.append((a,kw)); return Child()
        self.auto=AutoResearch(self.root/'latest.json',root=self.root,popen=popen,clock=lambda:self.t,now=lambda:NOW)
        self.env=patch.dict(os.environ,{**{k:'fake' for k in RESEARCH_KEYS},'TOSS_CLIENT_SECRET':'never-in-child'})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_nonblocking_single_worker_and_no_broker_secrets(self):
        self.assertEqual(self.auto.tick('2026-06-29'),'UPDATING')
        self.auto.tick('2026-06-29')
        self.assertEqual(len(self.calls),1)
        env=self.calls[0][1]['env']
        self.assertFalse(any(k.upper().startswith('TOSS_') for k in env))
        self.auto.close(); self.assertIsNone(self.auto.child)

    def test_failure_backoff_then_retry(self):
        self.auto.tick('2026-06-29'); self.auto.child.result=1
        self.assertEqual(self.auto.tick('2026-06-29'),'RETRY_WAIT')
        self.t=299; self.auto.tick('2026-06-29'); self.assertEqual(len(self.calls),1)
        self.t=301; self.auto.tick('2026-06-29'); self.assertEqual(len(self.calls),2)

    def test_worker_timeout_and_date_change_terminate(self):
        self.auto.tick('2026-06-29'); child=self.auto.child
        self.t=1801; self.auto.tick('2026-06-29')
        self.assertTrue(child.terminated)
        self.t=2200; self.auto.tick('2026-06-29'); child=self.auto.child
        self.auto.tick('2026-06-30'); self.assertTrue(child.terminated)

    def test_fresh_snapshot_not_recollected(self):
        store=Store(self.auto.output)
        store.data={'source_mode':'automatic','as_of':'2026-06-29','generated_at':NOW.isoformat()}; store.save()
        self.assertEqual(self.auto.tick('2026-06-29'),'READY')
        self.assertEqual(self.calls,[])

    def test_missing_credentials_no_child(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertTrue(self.auto.tick('2026-06-29').startswith('SETUP_REQUIRED'))
        self.assertEqual(self.calls,[])

    def test_auto_snapshot_expires_at_two_hours(self):
        store=Store(self.auto.output)
        store.data={'source_mode':'automatic','as_of':'2026-06-29','generated_at':(NOW-timedelta(hours=3)).isoformat()}; store.save()
        with self.assertRaises(SafetyStop): ResearchBook(self.auto.output).load(NOW,'2026-06-29')


@unittest.skipUnless(os.name=='nt','DPAPI requires Windows')
class CredentialTests(unittest.TestCase):
    def test_dpapi_roundtrip_never_plaintext(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.dpapi'
            values={'KRX_ID':'dummy-user','KRX_PW':'dummy-password-for-test'}
            save_credentials(values,path)
            self.assertNotIn(b'dummy-password-for-test',path.read_bytes())
            self.assertEqual(load_credentials(path),values)


if __name__=='__main__': unittest.main()
