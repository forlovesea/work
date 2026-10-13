import unittest,json
from datetime import datetime,timedelta
from runtime_status import KST,describe_status
from user_guidance import guidance
from auto_data import normalize_composition
from collection_log import CompositionError,safe_error
from support_log import block


class GuidanceTests(unittest.TestCase):
    def test_repeat_run_overrides_saved_ready_and_stop_overrides_completion(self):
        now=datetime.now(KST)
        saved={'state':'READY','updated_at':now.isoformat()}
        for _ in range(2):
            self.assertIn('새 점검',guidance(active=True,runtime='INITIALIZING',collection=saved)[1])
            self.assertIn('호가',guidance(active=True,runtime='BROKER_REQUEST',operation='ORDERBOOK',collection=saved)[1])
            self.assertEqual(guidance(active=True,runtime='NO_ELIGIBLE_AFFORDABLE_ETF',collection=saved)[0],'yellow')
            self.assertEqual(guidance(active=True,runtime='HOLD',collection=saved)[0],'green')
            self.assertEqual(guidance(confirmed=True,collection=saved)[0],'red')

    def test_safe_failure_is_readable_without_exporting_arbitrary_exception(self):
        from candidate_feedback import failure
        from live import SafetyStop
        code=failure(SafetyStop('Stale/future market data; no order sent'))['code']
        self.assertEqual(code,'STALE_MARKET_DATA')
        self.assertIn('시세',block('RUNTIME',{'error_code':code}))
        self.assertIn('다음 행동',describe_status(json.dumps({'status':'WORKER_ERROR','error_code':code})))
        self.assertNotIn('secret',str(failure(SafetyStop('secret'))))

    def test_progress_delay_completion_and_stop_have_distinct_actions(self):
        now=datetime(2026,10,13,14,tzinfo=KST)
        state={'state':'COLLECTING_DATA','first_collection':True,'updated_at':now.isoformat(),
               'progress':{'financial_done':63,'financial_total':236,'news_done':0,'news_total':46}}
        color,title,action=guidance(active=True,collection=state,now=now)
        self.assertEqual(color,'blue');self.assertIn('첫 수집',title);self.assertIn('63/236',action)
        self.assertEqual(guidance(active=True,collection=state,now=now+timedelta(seconds=121))[0],'yellow')
        self.assertEqual(guidance(active=False,collection=state,now=now)[0],'red')
        self.assertEqual(guidance(active=True,collection=dict(state,state='READY'),now=now)[0],'green')
        for code in ('COLLECTION_STOPPED','COLLECTION_FAILED'):
            self.assertEqual(guidance(collection=dict(state,state=code),now=now)[0],'red')
        self.assertEqual(guidance(active=True,collection=dict(state,state='READY'),runtime='BROKER_CONNECTION_WAIT',now=now)[0],'red')
        self.assertEqual(guidance(unverified=True,collection=dict(state,state='READY'),now=now)[0],'red')

    def test_initial_wait_does_not_append_interrupted_selection_message(self):
        text=describe_status(json.dumps({'status':'RESEARCH_FIRST_COLLECTION','selection_details':{}}))
        self.assertIn('첫 수집 진행 중',text)
        self.assertNotIn('중단',text)

    def test_composition_error_has_symbol_values_and_readable_export(self):
        with self.assertRaises(CompositionError) as caught:
            normalize_composition([{'COMPST_ISU_CD':'CASH','COMPST_RTO':'20'}],'123456','2026-10-12',{})
        fields=safe_error(caught.exception)
        self.assertEqual(fields['symbol'],'123456')
        self.assertEqual(fields['observed_percent'],20)
        self.assertEqual(fields['minimum_percent'],50)
        text=block('COLLECTION',fields)
        self.assertIn('123456',text);self.assertIn('허용 범위',text);self.assertIn('20.0',text)
