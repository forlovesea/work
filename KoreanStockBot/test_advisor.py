import copy
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from advisor import ApprovalBot, PaperPortfolio, DEFAULTS, trading_config, settings, fingerprint
from broker import BrokerError
from live import ROOT,Store,SafetyStop
from test_live import FakeBroker


class AdvisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name);self.b=FakeBroker();self.b.live=False
        self.c=settings(DEFAULTS)
        self.base=json.loads((ROOT/'live_config.json').read_text())
        self.config=trading_config(self.base,self.c,'123456')
        self.report=dict(checked_at=self.b.now.isoformat(),settings=fingerprint(self.c),rows=[dict(symbol='123456',eligible=True,reason='재무·뉴스 통과',news={'risk':False})])
        self.patch=patch('live.ROOT',self.path);self.patch.start();self.addCleanup(self.patch.stop)

    def bot(self):
        bot=ApprovalBot(self.b,self.config,Store(self.path/'approved.json'),report=self.report,clock=lambda:self.b.now)
        bot.initialize();return bot

    def test_preview_and_polling_never_submit(self):
        bot=self.bot()
        for _ in range(3):self.assertEqual(bot.preview()['status'],'APPROVAL_REQUIRED')
        self.assertEqual(self.b.sent,[])
        self.assertEqual(bot.s['orders'],[])
        with self.assertRaises(SafetyStop):bot.approve('not-approved')
        self.assertEqual(self.b.sent,[])

    def test_exact_approval_sends_once_then_sell_needs_new_approval(self):
        bot=self.bot();offer=bot.preview()
        result=bot.approve(offer['id'])
        self.assertEqual(result['mode'],'LIVE');self.assertEqual(len(self.b.sent),1)
        self.assertFalse(self.b.live);self.assertFalse(bot.live)
        with self.assertRaises(SafetyStop):bot.approve(offer['id'])
        self.b.fill('1',2,6010)
        self.b.price=2600
        sell=bot.preview();self.assertEqual(sell['side'],'SELL')
        self.assertEqual(len(self.b.sent),1)
        bot.approve(sell['id']);self.assertEqual(len(self.b.sent),2)

    def test_changed_price_or_expired_offer_is_not_sent(self):
        bot=self.bot();offer=bot.preview();self.b.price=3010
        with self.assertRaises(SafetyStop):bot.approve(offer['id'])
        self.assertEqual(self.b.sent,[])
        offer=bot.preview();self.b.now+=timedelta(seconds=121)
        with self.assertRaises(SafetyStop):bot.approve(offer['id'])
        self.assertEqual(self.b.sent,[])

    def test_unknown_submit_outcome_never_resubmits(self):
        bot=self.bot();offer=bot.preview();self.b.fail_submit=True
        with self.assertRaises(BrokerError):bot.approve(offer['id'])
        self.assertFalse(self.b.live)
        with self.assertRaises(SafetyStop):bot.preview()
        with self.assertRaises(SafetyStop):bot.approve(offer['id'])
        self.assertEqual(len(self.b.sent),1)

    def test_paper_compounds_net_costs_and_never_places_orders(self):
        paper=PaperPortfolio(self.path/'paper.json',self.c)
        text=paper.tick(self.b,self.base,self.report,clock=lambda:self.b.now)
        self.assertIn('BUY',text);self.assertEqual(paper.s['quantity'],2)
        self.assertLess(float(paper.s['equity']),self.c['capital'])
        self.b.price=3400
        text=paper.tick(self.b,self.base,self.report,clock=lambda:self.b.now)
        self.assertIn('SELL',text);self.assertEqual(paper.s['quantity'],0)
        self.assertGreater(float(paper.s['cash']),self.c['capital'])
        self.assertEqual(self.b.sent,[])
        self.assertFalse(self.b.live)
        restored=PaperPortfolio(self.path/'paper.json',self.c)
        self.assertEqual(restored.s,paper.s)
        restored.export(self.path/'trades.csv')
        self.assertIn('SELL',(self.path/'trades.csv').read_text(encoding='utf-8-sig'))

    def test_paper_stale_research_blocks_new_buys(self):
        paper=PaperPortfolio(self.path/'paper.json',self.c)
        self.report['checked_at']=(self.b.now-timedelta(hours=2)).isoformat()
        text=paper.tick(self.b,self.base,self.report,clock=lambda:self.b.now)
        self.assertIn('후보 없음',text);self.assertEqual(paper.s['quantity'],0)

    def test_external_ledger_change_requires_new_preview(self):
        bot=self.bot();offer=bot.preview()
        changed=Store(bot.store.path);changed.data['halted']=True;changed.save()
        with self.assertRaises(SafetyStop):bot.approve(offer['id'])
        self.assertEqual(self.b.sent,[])

    def test_paper_rejects_live_broker_and_setting_changes(self):
        paper=PaperPortfolio(self.path/'paper.json',self.c);paper.store.save()
        self.b.live=True
        with self.assertRaises(SafetyStop):paper.tick(self.b,self.base,self.report)
        with self.assertRaises(SafetyStop):PaperPortfolio(self.path/'paper.json',dict(self.c,capital=60000))

    def test_unapproved_polling_does_not_cancel_pending_orders(self):
        bot=self.bot();offer=bot.preview();bot.approve(offer['id'])
        self.b.now+=timedelta(seconds=130)
        self.assertEqual(bot.preview()['status'],'PENDING')
        self.assertEqual(self.b.canceled,[])
        bot.approve_cancel();self.assertEqual(self.b.canceled,['1'])
        self.assertFalse(self.b.live)

    def test_research_negative_news_excludes_candidate_without_orders(self):
        from advisor import research
        from test_stock_candidates import financial
        from email.utils import format_datetime
        row=dict(symbol='123456',name='테스트기업',market_cap='1000000',report=financial())
        article=dict(title='테스트기업 횡령 조사',description='',pubDate=format_datetime(self.b.now),originallink='https://example.com/news/1')
        with patch('advisor.screen',return_value={'rows':[row],'screened':1}),patch('advisor.Sources') as sources:
            sources.return_value.news.return_value=[article]
            result=research(self.b,self.base,self.c,self.path,clock=lambda:self.b.now)
        self.assertFalse(result['rows'][0]['eligible'])
        self.assertTrue(result['rows'][0]['news']['risk'])
        self.assertEqual(self.b.sent,[])

    def test_changing_approved_symbol_preserves_cash_and_history(self):
        from advisor import Advisor
        service=Advisor(self.path,self.b,self.base,self.c,clock=lambda:self.b.now)
        service.report=self.report
        offer=service.prepare('123456')
        self.assertEqual(offer['status'],'APPROVAL_REQUIRED')
        state=Store(service.data/'approved_state.json');state.data['cash']='31000';state.save()
        row=copy.deepcopy(self.report['rows'][0]);row['symbol']='654321'
        service.report['rows'].append(row)
        original=self.b.get
        def get(endpoint,params=None,account=False):
            result=original(endpoint,params,account)
            if endpoint in ('stocks','prices'):result[0]['symbol']='654321'
            return result
        self.b.get=get
        service.prepare('654321')
        self.assertEqual(service.bot.s['cash'],'31000')
        self.assertEqual(service.bot.s['advisor_config']['symbol'],'654321')
        self.assertEqual(self.b.sent,[])


if __name__=='__main__':unittest.main()
