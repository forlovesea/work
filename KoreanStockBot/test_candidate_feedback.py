import unittest
from datetime import datetime,timezone,timedelta
from candidate_feedback import failure,unavailable_message,market_context
from broker import BrokerError
from live import SafetyStop


class CandidateFeedbackTests(unittest.TestCase):
    def test_stale_quotes_explain_actual_exclusion(self):
        text=unavailable_message({'selection_details':{'market':'정규장 마감 후','budget':'9000',
            'rows':[{'state':'QUOTE_STALE'},{'state':'BUDGET'}]}})
        self.assertIn('과거 시세: 1종목',text)
        self.assertIn('예산 부족: 1종목',text)
        self.assertIn('다음 정규장',text)

    def test_success_has_no_unavailable_popup(self):
        self.assertIsNone(unavailable_message({'selection_details':{'rows':[{'state':'ELIGIBLE'}]}}))

    def test_failure_is_specific_without_raw_secret(self):
        self.assertEqual(failure(SafetyStop('Stale assessment'))['code'],'RESEARCH_STALE')
        result=failure(BrokerError('Toss HTTP 403; request not retried SECRET'))
        self.assertEqual(result['code'],'AUTH_OR_PERMISSION')
        self.assertNotIn('SECRET',str(result))
        self.assertNotIn('SECRET',str(failure(RuntimeError('SECRET'))))

    def test_market_uses_calendar_and_time(self):
        now=datetime(2026,10,12,17,tzinfo=timezone(timedelta(hours=9)))
        today={'date':'2026-10-12','integrated':None}
        self.assertEqual(market_context({'today':today},now),'휴장일')
        today['integrated']={'regularMarket':dict(startTime='2026-10-12T09:00:00+09:00',
            endTime='2026-10-12T15:30:00+09:00',singlePriceAuctionStartTime='2026-10-12T15:20:00+09:00')}
        self.assertEqual(market_context({'today':today},now),'정규장 마감 후')

    def test_budget_failure_does_not_invent_market_cause(self):
        text=unavailable_message({'selection_details':{'rows':[{'state':'BUDGET'}]}})
        self.assertNotIn('마감 후',text)
