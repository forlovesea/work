import unittest
from unittest.mock import Mock,patch
from live_gui import LivePanel


class ShutdownTests(unittest.TestCase):
    def panel(self):
        panel=LivePanel.__new__(LivePanel)
        panel.root=Mock();panel.status=Mock();panel.runtime_text=Mock()
        panel.closing=False;panel.exit_unverified=False;panel.querying=False
        panel.child=None;panel.active=Mock(return_value=False)
        panel.stop=Mock(return_value=True)
        return panel

    def test_idle_closes_immediately(self):
        panel=self.panel();panel.close();panel.root.destroy.assert_called_once()

    def test_queries_finish_before_window_closes(self):
        panel=self.panel();panel.querying=True;panel.close()
        self.assertTrue(panel.closing);panel.root.destroy.assert_not_called()

    def test_running_requests_stop_and_waits(self):
        panel=self.panel();panel.child=Mock();panel.active.return_value=True
        panel.close();panel.close()
        panel.stop.assert_called_once();panel.root.destroy.assert_not_called()

    def test_stop_request_failure_keeps_window(self):
        panel=self.panel();panel.child=Mock();panel.active.return_value=True;panel.stop.return_value=False
        panel.close();self.assertFalse(panel.closing);panel.root.destroy.assert_not_called()

    def test_unconfirmed_exit_never_auto_closes(self):
        for code,confirmed in [(0,False),(1,True),(1,False)]:
            panel=self.panel();panel.closing=True;panel.stop_confirmed=confirmed
            with patch('live_gui.messagebox.showerror') as warning:panel.finish_exit(code)
            self.assertFalse(panel.closing);self.assertTrue(panel.exit_unverified)
            warning.assert_called_once();panel.root.destroy.assert_not_called()

    def test_confirmed_exit_allows_automatic_close(self):
        panel=self.panel();panel.closing=True;panel.stop_confirmed=True
        panel.finish_exit(0)
        self.assertTrue(panel.closing);self.assertFalse(panel.exit_unverified)
