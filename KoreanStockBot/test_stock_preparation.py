import unittest
from stock_candidate_gui import preparation_message

class PreparationTests(unittest.TestCase):
    def test_missing_items_and_instructions_without_secrets(self):
        message=preparation_message({'TOSS_CLIENT_SECRET':'secret-value'},dict(capital=30000,allocation=.3,max_order_won=9000))
        self.assertIn('KRX 아이디',message)
        self.assertIn('DART 인증키',message)
        self.assertNotIn('secret-value',message)
        self.assertIn('미리 할 필요가 없습니다',message)

    def test_ready_requires_no_extra_work_or_symbol(self):
        env={k:'1' for k in ('TOSS_CLIENT_ID','TOSS_CLIENT_SECRET','TOSS_ACCOUNT_SEQ','KRX_ID','KRX_PW','DART_API_KEY')}
        config=dict(capital=30000,allocation=.3,max_order_won=9000,symbol='')
        self.assertIsNone(preparation_message(env,config))
        self.assertIn('투자 비중',preparation_message(env,dict(config,allocation=2)))
        self.assertIn('다시 조회',preparation_message(dict(env,TOSS_ACCOUNT_SEQ='bad'),config))
