"""Approval alerts tested offline, without credentials or broker access."""
import unittest
from unittest.mock import Mock, patch

from advisor_gui import AdvisorWindow


class AlertTests(unittest.TestCase):
    def window(self):
        app=AdvisorWindow.__new__(AdvisorWindow)
        app.watch_symbol='123456';app.watch_seen=None;app.watch_timer=None
        app.closing=False;app.busy=False;app.automatic=False;app.offer=None
        app.root=Mock();app.book=Mock();app.tabs={'실제 주문 승인':Mock()}
        app.order_text=Mock();app.set_text=Mock();app.offer_text=Mock(return_value='Order details')
        app.service=Mock();app.task=Mock();app.approve_button=Mock()
        return app

    def offer(self,side='BUY',identity='one'):
        return dict(status='APPROVAL_REQUIRED',symbol='123456',side=side,
                    reason='condition',id=identity)

    @patch('advisor_gui.messagebox.askyesno',return_value=False)
    def test_decline_dedup_and_rearm(self,popup):
        app=self.window()
        app.watch_result(self.offer());app.watch_result(self.offer(identity='two'))
        self.assertEqual(popup.call_count,1);app.task.assert_not_called()
        app.service.approve.assert_not_called()
        app.watch_result({'status':'WAIT'})
        app.watch_result(self.offer())
        self.assertEqual(popup.call_count,2)
        app.watch_result(self.offer('SELL'))
        self.assertEqual(popup.call_count,3)

    @patch('advisor_gui.messagebox.askyesno',return_value=True)
    def test_explicit_approval_only(self,popup):
        app=self.window();app.watch_result(self.offer('SELL'))
        app.service.approve.assert_not_called()
        kind,work=app.task.call_args.args
        self.assertEqual(kind,'실제 승인');work()
        app.service.approve.assert_called_once_with('one')
        self.assertIsNone(app.offer)

    @patch('advisor_gui.messagebox.askyesno')
    def test_stop_ignores_pending_result(self,popup):
        app=self.window();app.watch_timer='timer'
        app.stop_watch();app.watch_result(self.offer())
        app.root.after_cancel.assert_called_once_with('timer')
        popup.assert_not_called();app.task.assert_not_called()

    def test_tick_only_prepares(self):
        app=self.window();app.watch_tick()
        kind,work=app.task.call_args.args
        self.assertEqual(kind,'승인 알림');work()
        app.service.prepare.assert_called_once_with('123456')
        app.service.approve.assert_not_called()


if __name__=='__main__':unittest.main()
