import unittest
from runtime_status import exit_status, describe_status


class StopStatusTests(unittest.TestCase):
    def test_exit_needs_both_confirmation_and_success(self):
        self.assertIn('중지 완료',exit_status(0,True))
        for code,confirmed in [(0,False),(1,True),(1,False)]:
            self.assertIn('정상 중지 미확인',exit_status(code,confirmed))

    def test_checking_does_not_claim_cancellation(self):
        text=describe_status('{"status":"STOP_CHECKING"}')
        self.assertIn('확인 중',text)
        self.assertNotIn('중지 완료',text)
