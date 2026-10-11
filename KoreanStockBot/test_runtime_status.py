import json
import unittest
from datetime import datetime
from live import LiveBot, KST
from runtime_status import describe_status


class MarketStatusTests(unittest.TestCase):
    def bot(self,when,holiday=False):
        from test_live import FakeBroker
        broker=FakeBroker(); broker.now=datetime.fromisoformat(when); broker.holiday=holiday
        calendar=broker.get('market-calendar/KR')
        calendar['nextBusinessDay']={'date':'2026-10-12','integrated':{'regularMarket':{
            'startTime':'2026-10-12T09:00:00+09:00'}}}
        broker.override['market-calendar/KR']=calendar
        bot=LiveBot.__new__(LiveBot); bot.b=broker; bot.clock=lambda:broker.now
        return bot

    def test_sunday(self):
        bot=self.bot('2026-10-11T12:00:00+09:00',True)
        self.assertIsNone(bot.market())
        text=describe_status(json.dumps(bot.market_status))
        self.assertIn('휴장 대기',text)
        self.assertIn('2026-10-12 09:00',text)
        self.assertIn('신규 매수·매도 주문 없음',text)

    def test_holiday_without_next_session_does_not_guess(self):
        bot=self.bot('2026-10-09T12:00:00+09:00',True)
        del bot.b.override['market-calendar/KR']['nextBusinessDay']
        bot.market()
        self.assertIn('확인되지 않음',describe_status(json.dumps(bot.market_status)))

    def test_session_boundaries_unchanged(self):
        for hour,minute,expected in [(8,59,'BEFORE_OPEN'),(9,1,'BEFORE_OPEN'),
                                     (9,2,None),(15,17,None),(15,18,'SESSION_FINISHED')]:
            bot=self.bot(f'2026-10-12T{hour:02}:{minute:02}:00+09:00')
            result=bot.market()
            if expected:
                self.assertIsNone(result)
                self.assertEqual(bot.market_status['market_state'],expected)
            else: self.assertIsNotNone(result)

    def test_connection_failure_is_not_holiday(self):
        text=describe_status('{"status":"BROKER_CONNECTION_WAIT"}')
        self.assertIn('연결 확인 실패',text)
        self.assertNotIn('휴장',text)


if __name__=='__main__':unittest.main()
