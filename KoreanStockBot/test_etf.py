import copy
import csv
import json
import tempfile
import unittest
from datetime import datetime,timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from live import ROOT,KST,Store,SafetyStop
from etf_live import EtfBot
from etf_research import universe,holdings,financial_summary,news_summary,assess,ResearchBook,ACCOUNTS
from build_research import build
from test_live import FakeBroker


NOW=datetime(2026,6,30,10,tzinfo=KST)


def csv_file(path,rows):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def fund(symbol='123456',nav='1000000000'):
    return dict(as_of='2026-06-29',symbol=symbol,name='테스트 코스닥150',benchmark='KOSDAQ150',
                net_assets_won=nav,leverage='1',structure='physical',source_url='https://example.com/fund')


def constituent():
    return dict(as_of='2026-06-29',etf_symbol='123456',stock_symbol='654321',corp_code='00123456',
                name='테스트기업',weight='0.65',source_url='https://example.com/holdings')


def news_item(title='테스트기업 영업이익 증가',url='https://example.com/news'):
    return dict(title=title,description='',originallink=url,pubDate='Mon, 29 Jun 2026 10:00:00 +0900')


def financial_rows():
    values={'revenue':'1000','operating_profit':'100','net_profit':'80','assets':'2000','equity':'1000','operating_cash':'150'}
    return [dict(account_id=ids[0],sj_div='IS' if k in ('revenue','operating_profit','net_profit') else ('CF' if k=='operating_cash' else 'BS'),
                 corp_code='00123456',bsns_year='2025',reprt_code='11011',currency='KRW',rcept_no='20260331000001',thstrm_amount=values[k])
            for k,ids in ACCOUNTS.items()]


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_top20_net_assets_not_price_or_eligibility(self):
        rows=[fund(f'{i:06}',str(i*1000)) for i in range(1,26)]
        rows[-1].update(leverage='2',structure='derivative')
        rows.append(dict(fund('999999','999999999'),name='코스피 ETF',benchmark='KOSPI200'))
        path=self.root/'u.csv'
        csv_file(path,rows)
        top=universe(path,'2026-06-29')
        self.assertEqual(len(top),20)
        self.assertEqual(top[0]['symbol'],'000025')
        self.assertFalse(top[0]['tradable'])
        self.assertEqual(top[-1]['symbol'],'000006')
        self.assertNotIn('000005',[r['symbol'] for r in top])

    def test_fewer_than20_not_padded(self):
        path=self.root/'u.csv'
        csv_file(path,[fund()])
        self.assertEqual(len(universe(path,'2026-06-29')),1)

    def test_duplicate_mixed_date_and_invalid_nav(self):
        path=self.root/'u.csv'
        for rows in [[fund(),fund()],[dict(fund(),as_of='2026-06-28')],[dict(fund(),net_assets_won='NaN')]]:
            csv_file(path,rows)
            with self.assertRaises(SafetyStop): universe(path,'2026-06-29')

    def test_holdings_weights_and_dates(self):
        path=self.root/'h.csv'
        for change in [{'weight':'65'},{'as_of':'2026-05-01'},{'corp_code':'123456'},{'source_url':'file:///secret'}]:
            csv_file(path,[dict(constituent(),**change)])
            with self.assertRaises(SafetyStop): holdings(path,'2026-06-29')

    def test_financial_standard_accounts_and_losses(self):
        rows=financial_rows()
        report=financial_summary(rows,'00123456',2025,'11011','2025-12-31',NOW)
        self.assertEqual(report['score'],1)
        rows[1]['thstrm_amount']='-100'
        report=financial_summary(rows,'00123456',2025,'11011','2025-12-31',NOW)
        self.assertEqual(report['score'],.8)
        self.assertFalse(report['checks']['operating_profit_positive'])
        self.assertTrue(report['sources'][0].startswith('https://dart.fss.or.kr/'))

    def test_missing_same_day_future_and_ambiguous_reports_fail_closed(self):
        rows=financial_rows()
        for changed in [rows[:-1],[dict(r,rcept_no='20260630000001') for r in rows],rows+[dict(rows[0],thstrm_amount='777')]]:
            self.assertIsNone(financial_summary(changed,'00123456',2025,'11011','2025-12-31',NOW))

    def test_quarter_uses_cumulative_not_three_month(self):
        rows=[dict(r,bsns_year='2026',reprt_code='11013',rcept_no='20260515000001',thstrm_add_amount='-100') for r in financial_rows()]
        report=financial_summary(rows,'00123456',2026,'11013','2026-03-31',NOW)
        self.assertEqual(report['metrics']['operating_profit'],'-100')

    def test_news_relevance_dedupe_future_and_risk(self):
        items=[news_item(),news_item(url='https://example.com/syndicated'),news_item('관계없는 기업 횡령'),
               dict(news_item('테스트기업 횡령'),pubDate='Wed, 01 Jul 2026 10:00:00 +0900')]
        report=news_summary(items,['테스트기업'],NOW)
        self.assertEqual(report['count'],1)
        self.assertFalse(report['risk'])
        report=news_summary(items+[news_item('테스트기업 횡령 조사',url='https://example.com/risk')],['테스트기업'],NOW)
        self.assertTrue(report['risk'])

    def test_coverage_and_news_required(self):
        f=financial_summary(financial_rows(),'00123456',2025,'11011','2025-12-31',NOW)
        etf=dict(fund(),tradable=True)
        n=news_summary([news_item()],['테스트기업'],NOW)
        self.assertTrue(assess(etf,[constituent()],{'00123456':f},n,NOW)['allow_buy'])
        self.assertFalse(assess(etf,[dict(constituent(),weight='.59')],{'00123456':f},n,NOW)['allow_buy'])
        self.assertFalse(assess(etf,[constituent()],{'00123456':f},news_summary([],['테스트기업'],NOW),NOW)['allow_buy'])

    def test_builder_and_stale_snapshot(self):
        u,h,out=self.root/'u.csv',self.root/'h.csv',self.root/'latest.json'
        csv_file(u,[fund()]); csv_file(h,[constituent()])
        class FakeSources:
            def financial(self,corp): return financial_summary(financial_rows(),corp,2025,'11011','2025-12-31',NOW)
            def news(self,query): return [news_item()]
        build(u,h,'2026-06-29',out,FakeSources(),NOW)
        book=ResearchBook(out).load(NOW,'2026-06-29')
        self.assertTrue(book['assessments']['123456']['allow_buy'])
        with self.assertRaises(SafetyStop): ResearchBook(out).load(NOW+timedelta(days=2),'2026-06-29')
        with self.assertRaises(SafetyStop): ResearchBook(out).load(NOW,'2026-06-28')


class FakeResearch:
    def __init__(self):
        self.fail=False
        self.allow=True
        self.exit=False
    def load(self,now,previous):
        if self.fail: raise SafetyStop('stale')
        a={'symbol':'123456','allow_buy':self.allow,'exit':self.exit,'score':.8,'coverage':.8,'reasons':[]}
        return {'universe':[dict(fund(),tradable=True,rank=1)],'assessments':{'123456':a},'digest':'test-digest'}


class EtfLiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config=json.loads((ROOT/'etf_config.json').read_text())
        self.b=FakeBroker()
        stock=self.b.get('stocks')[0]
        stock.update(securityType='ETF',leverageFactor='1')
        self.b.override['stocks']=[stock]
        self.research=FakeResearch()
        self.path=Path(self.tmp.name)/'state.json'
        self.bot=EtfBot(self.b,self.config,Store(self.path),True,clock=lambda:self.b.now,research=self.research)
        self.bot.initialize()

    def test_select_and_live_order_persist_identity_and_research(self):
        result=self.bot.step()
        self.assertEqual(result['side'],'BUY')
        self.assertEqual(self.b.sent[0]['symbol'],'123456')
        state=Store(self.path).data
        self.assertEqual(state['managed_symbol'],'123456')
        self.assertEqual(state['selection']['rank'],1)
        self.assertEqual(state['selection']['research_digest'],'test-digest')

    def test_stale_or_negative_research_no_buy(self):
        self.research.fail=True
        self.assertEqual(self.bot.step()['status'],'RESEARCH_OR_CANDIDATE_DATA_UNAVAILABLE')
        self.research.fail=False; self.research.allow=False
        self.assertEqual(self.bot.step()['status'],'NO_ELIGIBLE_AFFORDABLE_ETF')
        self.assertEqual(self.b.sent,[])

    def test_expensive_etf_does_not_override_budget(self):
        self.b.price=15000
        self.assertEqual(self.bot.step()['status'],'NO_ELIGIBLE_AFFORDABLE_ETF')
        self.assertEqual(self.b.sent,[])

    def test_user_scope_excludes_new_buy_without_erasing_state(self):
        from etf_scope import write_scope
        write_scope(self.bot.scope_path,self.bot.binding,10,20)
        result=self.bot.step()
        self.assertEqual(result['status'],'NO_ELIGIBLE_AFFORDABLE_ETF')
        self.assertEqual(result['selection_details']['rows'][0]['state'],'OUTSIDE_RANGE')
        self.assertFalse(self.b.sent)
        self.assertEqual(self.bot.s['binding'],self.bot.binding)

    def test_selected_symbols_restrict_new_buy(self):
        from etf_scope import write_symbols
        write_symbols(self.bot.scope_path,self.bot.binding,['654321'])
        self.assertEqual(self.bot.step()['status'],'NO_ELIGIBLE_AFFORDABLE_ETF')
        self.assertFalse(self.b.sent)

    def test_preview_ignores_scope_without_orders_or_identity_changes(self):
        from etf_scope import write_symbols
        write_symbols(self.bot.scope_path,self.bot.binding,['654321'])
        before=json.dumps(self.bot.s,sort_keys=True)
        self.bot.select('2026-06-29',preview=True)
        self.assertEqual(self.bot.selection_details['rows'][0]['state'],'ELIGIBLE')
        self.assertEqual(json.dumps(self.bot.s,sort_keys=True),before)
        self.assertFalse(self.b.sent)

    def test_symbol_selection_preserves_existing_exit(self):
        from etf_scope import write_symbols
        self.bot.step();self.b.fill('1',2,6010,fee='2')
        write_symbols(self.bot.scope_path,self.bot.binding,['654321'])
        self.b.price=2800
        self.assertEqual(self.bot.step()['side'],'SELL')

    def test_scope_change_does_not_block_existing_exit(self):
        from etf_scope import write_scope
        self.bot.step();self.b.fill('1',2,6010,fee='2')
        write_scope(self.bot.scope_path,self.bot.binding,10,20)
        self.b.price=2800
        self.assertEqual(self.bot.step()['side'],'SELL')

    def test_range_proposal_counts_are_not_final_buy_signals(self):
        from etf_scope import proposals,write_scope
        write_scope(self.bot.scope_path,self.bot.binding,10,20)
        details=self.bot.step()['selection_details']
        options=proposals(details)
        self.assertEqual(options[0]['affordable'],1)
        self.assertEqual(options[2]['affordable'],0)
        self.assertFalse(self.b.sent)

    def test_research_outage_does_not_disable_stop_loss(self):
        self.bot.step()
        self.b.fill('1',2,6010,fee='2')
        self.research.fail=True
        self.b.price=2800
        result=self.bot.step()
        self.assertEqual(result['side'],'SELL')
        self.assertEqual(result['reason'],'STOP_LOSS')

    def test_net_ten_percent_target(self):
        self.assertFalse(self.bot.profit_reached(Decimal(3300),Decimal(3300),Decimal(3000),Decimal('.00015')))
        self.assertTrue(self.bot.profit_reached(Decimal(3310),Decimal(3310),Decimal(3000),Decimal('.00015')))

    def test_restart_keeps_managed_etf_not_new_universe(self):
        self.bot.step()
        self.b.fill('1',1,3005,status='PARTIAL_FILLED')
        restored=EtfBot(self.b,self.config,Store(self.path),True,clock=lambda:self.b.now,research=self.research)
        restored.initialize()
        self.research.fail=True
        restored.step()
        self.assertEqual(restored.symbol,'123456')
        self.assertEqual(restored.s['quantity'],1)
        self.assertEqual(len(self.b.sent),1)

    def test_fundamentals_and_news_exit(self):
        self.bot.step(); self.b.fill('1',2,6010,fee='2')
        self.research.exit=True
        result=self.bot.step()
        self.assertEqual(result['reason'],'FUNDAMENTALS_AND_NEWS_EXIT')

    def test_leveraged_broker_metadata_rejected(self):
        self.b.override['stocks'][0]['leverageFactor']='2'
        with self.assertRaises(SafetyStop): self.bot.step()
        self.assertEqual(self.b.sent,[])


if __name__=='__main__': unittest.main()
