"""Run the existing transport/GUI suite against V7 plus group regressions."""
import time
import unittest
import test_modbus_v6 as previous
import LCD_GUI_Pannel_Master_modbus_V7 as monitor

previous.monitor = monitor
TransportTests = previous.TransportTests
GuiTests = previous.GuiTests


class GroupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = monitor.QApplication.instance() or monitor.QApplication([])

    def setUp(self):
        self.gui = monitor.TimeBatteryGui()
        self.gui.cmb_modules.setCurrentText('2')
        self.gui.is_connected = True
        for n, voltage, current, soc in ((1, 50, -10, 60), (2, 52, 4, 80)):
            self.gui.on_module_status(n, True)
            self.gui.update_cell_table(n, '\n'.join(
                f'Cell-{i:02d} Temp : {20+n} degC / Volt : 3.2 V' for i in range(1, 16)))
            self.gui.on_battery_received(n, f'[Battery Module: {n}]\nBattery Voltage : {voltage} V\n'
                f'Battery Current : {current} A\nBattery SOC : {soc} %\nBattery SOH : 90 %')
            self.gui.on_group_protection(n, [0] * 13)

    def tearDown(self):
        self.gui.close()

    def values(self):
        return [item.text() for item in self.gui.group_values]

    def test_signed_sum_mean_extrema_and_temperature(self):
        self.assertEqual(self.values()[:9], ['51.0', '-6.0', '70.0', '90.0', '52.0', '50.0', '22.0', '21.0', '21.5'])
        self.assertEqual(self.values()[9:], ['정상'] * 3)

    def test_failure_stale_disconnect_reset(self):
        self.gui.on_module_status(2, False)
        self.assertEqual(self.values()[1], '-10.0')
        self.assertEqual(self.values()[9], '확인 불가')
        self.gui.received_at[1] = time.monotonic() - 11
        self.gui.refresh_ages()
        self.assertEqual(self.values()[:9], ['-'] * 9)
        self.gui.is_connected = False
        self.gui.refresh_ages()
        self.assertEqual(self.values()[9:], ['확인 불가'] * 3)
        self.gui.reset_monitor()
        self.assertFalse(self.gui.group_protections)

    def test_alarm_positive_partial_unknown_and_expiry(self):
        details = [0] * 13
        details[10] = 1
        self.gui.on_group_protection(1, details)
        self.gui.on_group_protection(2, None)
        self.assertEqual(self.values()[9:], ['발생', '확인 불가', '확인 불가'])
        self.gui.group_protections[1] = (time.monotonic() - 16, details)
        self.gui.refresh_ages()
        self.assertEqual(self.values()[9], '확인 불가')

    def test_auto_noncontiguous_targets_and_invalid_measurements(self):
        self.gui.cmb_modules.setCurrentText('Auto')
        self.gui.on_modules_discovered([2, 10])
        self.assertEqual(self.values()[0], '52.0')
        self.gui.battery_cache[2] = self.gui.battery_cache[2].replace('80 %', '101 %')
        self.gui.refresh_ages()
        self.assertEqual(self.values()[0], '-')


def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromModule(previous)
    suite.addTests(loader.loadTestsFromTestCase(GroupTests))
    return suite


if __name__ == '__main__':
    unittest.main()
