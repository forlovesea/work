"""Offline RTU fault-injection and GUI regression tests; no serial hardware needed."""
import csv
import os
import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import LCD_GUI_Pannel_Master_modbus_V6 as monitor


def packet(values=(), slave=33, function=3):
    data = bytes([slave, function, len(values) * 2]) + struct.pack(f'>{len(values)}H', *values)
    return data + struct.pack('<H', monitor.count_crc(data))


class FakeSerial:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.writes = []

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks else 0

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def read(self, size):
        if self.chunks:
            return self.chunks.pop(0)
        time.sleep(0.001)
        return b''


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.worker = monitor.PollWorker('fake', 9600)
        self.master = monitor.ModbusMaster('fake', 9600)

    def receive(self, chunks, count=2):
        self.master.client = FakeSerial(chunks)
        return self.master.send_raw(self.worker.build_read_frame(0xA731, count))

    def test_crc_reference(self):
        self.assertEqual(monitor.count_crc(bytes.fromhex('01 03 00 00 00 0A')), 0xCDC5)

    def test_fragmented_response_returns_without_full_timeout(self):
        response = packet([512, 100])
        start = time.monotonic()
        self.assertEqual(self.receive([response[:1], response[1:3], response[3:7], response[7:]]), response)
        self.assertLess(time.monotonic() - start, 0.15)

    def test_noise_wrong_slave_bad_crc_then_valid(self):
        good = packet([1, 2])
        broken = good[:-1] + bytes([good[-1] ^ 1])
        self.assertEqual(self.receive([b'\x99\x00', packet([1, 2], slave=2), broken, good]), good)

    def test_wrong_byte_count_rejected(self):
        with self.assertRaises(monitor.ModbusReadError):
            self.receive([packet([1])])
        self.assertTrue(self.master.recover)

    def test_exception_frame_rejected(self):
        body = bytes([33, 0x83, 2])
        response = body + struct.pack('<H', monitor.count_crc(body))
        with self.assertRaisesRegex(monitor.ModbusReadError, 'exception 0x02'):
            self.receive([response])

    def test_truncated_and_bad_crc_rejected(self):
        for response in (packet([1, 2])[:-1], packet([1, 2])[:-2] + b'\x00\x00'):
            self.master.next_tx = 0
            with self.assertRaises(monitor.ModbusReadError):
                self.receive([response])

    def test_cancel_during_recovery_does_not_transmit(self):
        self.master.client = FakeSerial([])
        self.master.next_tx = time.monotonic() + 10
        self.master.recover = True
        self.assertEqual(self.master.send_raw(self.worker.build_read_frame(0, 1), lambda: True), b'')
        self.assertEqual(self.master.client.writes, [])


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.worker = monitor.PollWorker('fake', 9600, module_count=10)

    def test_auto_discovers_all_addresses_and_keeps_sparse_modules(self):
        worker = monitor.PollWorker('fake', 9600, module_count=None)
        discovered, alarms = [], []
        worker.discovery_signal.connect(discovered.append)
        worker.alarm_signal.connect(alarms.append)
        def reply(addr, count):
            n = (addr - 0xA731) // 64 + 1
            return [0] * 54 if n in (2, 10) else None
        with patch.object(worker, 'read_registers', side_effect=reply) as read:
            worker.discover_modules()
        self.assertEqual([call.args for call in read.call_args_list],
                         [(0xA731 + i * 64, 54) for i in range(10)])
        self.assertEqual(discovered, [[2, 10]])
        worker.global_alarms = (0,)
        worker.module_alarms = {2: ([], True), 10: ([], True)}
        worker.alarm_received = {2: time.monotonic(), 10: time.monotonic()}
        worker.publish_alarms()
        self.assertEqual(alarms[-1], 'All Modules Normal')
        with patch.object(worker, 'read_registers', return_value=None):
            worker.poll_battery(10)
        self.assertEqual(worker.monitored_modules, {2, 10})
        worker.publish_alarms()
        self.assertIn('Batt10: alarm status unknown', alarms[-1])

    def test_auto_empty_scan_is_not_reported_as_normal(self):
        worker = monitor.PollWorker('fake', 9600, module_count=None)
        alarms = []
        worker.alarm_signal.connect(alarms.append)
        with patch.object(worker, 'read_registers', return_value=None):
            worker.discover_modules()
        worker.global_alarms = (0,)
        worker.publish_alarms()
        self.assertIn('No battery modules detected', alarms[-1])
        self.assertNotIn('All Modules Normal', alarms[-1])

    def test_battery_address_signed_values_and_range(self):
        regs = [0] * 54
        regs[1] = 512
        regs[2], regs[3] = 0xFFFF, 0xFF85  # -12.3 A
        regs[8], regs[53], regs[9], regs[31] = 80, 95, 0xFFFB, 32
        batteries, cells = [], []
        self.worker.battery_signal.connect(lambda n, text: batteries.append((n, text)))
        self.worker.cell_signal.connect(lambda n, text: cells.append((n, text)))
        with patch.object(self.worker, 'read_registers', return_value=regs) as read:
            self.assertTrue(self.worker.poll_battery(10))
        read.assert_called_once_with(0xA731 + 9 * 64, 54)
        self.assertIn('-12.3 A', batteries[0][1])
        self.assertIn('-5 degC / Volt : 3.2 V', cells[0][1])

    def test_barcode_cached_per_module(self):
        regs = struct.unpack('>15H', b'BATTERY-10'.ljust(30, b'\x00'))
        with patch.object(self.worker, 'read_registers', return_value=regs) as read:
            self.worker.poll_barcode(10)
            self.worker.poll_barcode(10)
        read.assert_called_once_with(0xC670 + 9 * 32, 15)

    def test_alarm_block_and_partial_failure_not_normal(self):
        output, counts = [], []
        self.worker.alarm_signal.connect(output.append)
        self.worker.alarm_count_signal.connect(counts.append)
        with patch.object(self.worker, 'read_registers', side_effect=[(1,), None]) as read:
            self.worker.poll_module_alarm(1)
        self.assertEqual(read.call_args_list[1].args, (0x8431, 13))
        self.worker.publish_alarms()
        self.assertIn('Fault', output[-1])
        self.assertIn('unknown', output[-1])
        self.assertNotIn('All Modules Normal', output[-1])
        self.assertEqual(counts[-1], -1)

    def test_failed_module_backoff_and_previous_valid_removed(self):
        self.worker.valid_modules.add(2)
        with patch.object(self.worker, 'read_registers', return_value=None):
            self.assertFalse(self.worker.poll_battery(2))
        self.assertNotIn(2, self.worker.valid_modules)
        self.assertGreater(self.worker.retry_due[2], time.monotonic())


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = monitor.QApplication.instance() or monitor.QApplication([])

    def setUp(self):
        self.gui = monitor.TimeBatteryGui()
        self.gui.is_connected = True

    def tearDown(self):
        self.gui.close()

    def feed(self, n):
        self.gui.on_module_status(n, True)
        cells = '\n'.join(f'Cell-{i:02d} Temp : {20+n} degC / Volt : 3.2 V' for i in range(1, 16))
        self.gui.update_cell_table(n, cells)
        self.gui.on_battery_received(n, f'[Battery Module: {n}]\nBattery Voltage : 51.2 V\nBattery Current : -1.0 A\nBattery SOC : 80 %\nBattery SOH : 95 %')
        self.gui.update_barcode(n, f'BAT-{n}')

    def test_ten_module_summary_selection_and_barcode(self):
        for n in range(1, 11):
            self.feed(n)
        self.assertEqual(self.gui.table_modules.item(9, 2).text(), '51.2')
        self.assertEqual(self.gui.lbl_barcode.text(), 'Barcode: BAT-1')
        stamp = self.gui.received_at[10]
        self.gui.on_module_button_clicked(10)
        self.assertEqual(self.gui.lbl_barcode.text(), 'Barcode: BAT-10')
        self.assertEqual(self.gui.received_at[10], stamp)
        self.assertEqual(self.gui.table_cell.item(0, 2).text(), '30')
        self.gui.on_module_status(10, False)
        self.assertIn('이전값', self.gui.table_modules.item(9, 1).text())

    def test_csv_all_modules_correct_cells_no_selection_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.csv'
            self.gui.log_file_path = str(path)
            self.gui.chk_save_log.setChecked(True)
            self.feed(1)
            self.feed(2)
            self.gui.on_module_button_clicked(2)
            with path.open(encoding='utf-8', newline='') as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[2][2], '22.0')
            self.assertEqual(rows[2][17], '3.2')
            self.assertIn('Module: 2', rows[2][1])

    def test_reconnect_clears_previous_data_and_module_count(self):
        self.feed(10)
        self.gui.cmb_modules.setCurrentText('1')
        self.gui.reset_monitor()
        self.assertFalse(self.gui.battery_cache)
        self.assertTrue(self.gui.table_modules.isRowHidden(9))
        self.assertEqual(self.gui.lbl_barcode.text(), 'Barcode: -')

    def test_module_table_descending_order_and_selection(self):
        from PySide6.QtTest import QTest
        self.gui.show()
        self.app.processEvents()
        for n in range(1, 11):
            self.feed(n)
        table = self.gui.table_modules
        header = table.verticalHeader()
        self.assertEqual([table.item(header.logicalIndex(i), 0).text() for i in range(10)],
                         [str(n) for n in range(10, 0, -1)])
        first_item = table.item(header.logicalIndex(0), 0)
        QTest.mouseClick(table.viewport(), monitor.Qt.LeftButton,
                         pos=table.visualItemRect(first_item).center())
        self.assertEqual(self.gui.current_displayed_module, 10)
        self.assertEqual(self.gui.lbl_barcode.text(), 'Barcode: BAT-10')
        self.gui.on_modules_discovered([2, 10])
        visible = [header.logicalIndex(i) + 1 for i in range(10)
                   if not table.isRowHidden(header.logicalIndex(i))]
        self.assertEqual(visible, [10, 2])
        self.gui.cmb_modules.setCurrentText('3')
        self.gui.reset_monitor()
        visible = [header.logicalIndex(i) + 1 for i in range(10)
                   if not table.isRowHidden(header.logicalIndex(i))]
        self.assertEqual(visible, [3, 2, 1])

    def test_auto_selection_discovery_and_rescan_reset(self):
        self.assertEqual(self.gui.cmb_modules.itemText(0), 'Auto')
        self.gui.cmb_modules.setCurrentText('Auto')
        self.gui.reset_monitor()
        self.gui.on_modules_discovered([2, 10])
        self.assertTrue(self.gui.table_modules.isRowHidden(0))
        self.assertFalse(self.gui.table_modules.isRowHidden(1))
        self.assertFalse(self.gui.table_modules.isRowHidden(9))
        self.assertIn('2개 (2, 10)', self.gui.lbl_connection.text())
        self.gui.reset_monitor()
        self.assertTrue(all(not self.gui.table_modules.isRowHidden(i) for i in range(10)))

    def wait_until(self, predicate):
        from PySide6.QtTest import QTest
        deadline = time.monotonic() + 2
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(predicate())

    def test_connection_failure_cleans_thread_and_restores_controls(self):
        self.gui.cmb_port.addItem('TEST-FAKE')
        self.gui.cmb_port.setCurrentText('TEST-FAKE')
        with patch.object(monitor.ModbusMaster, 'connect', side_effect=OSError('Test failure')), \
                patch.object(monitor.QMessageBox, 'critical') as error:
            self.gui.connect_port()
            self.wait_until(lambda: self.gui.worker is None)
            self.assertEqual(error.call_count, 1)
        self.assertFalse(self.gui.is_connected)
        self.assertTrue(self.gui.cmb_modules.isEnabled())

    def test_thread_polling_and_nonblocking_close(self):
        self.gui.cmb_port.addItem('TEST-FAKE')
        self.gui.cmb_port.setCurrentText('TEST-FAKE')
        self.gui.cmb_modules.setCurrentText('1')

        def reply(master, request, cancelled, trace):
            addr, count = struct.unpack('>HH', request[2:6])
            regs = [0] * count
            if addr == 0xA731:
                regs[1], regs[8], regs[53] = 512, 80, 95
            if addr == 0x2000:
                regs = [2026, 9, 21, 12, 0, 0]
            return packet(regs)

        with patch.object(monitor.ModbusMaster, 'connect', return_value=True), \
                patch.object(monitor.ModbusMaster, 'send_raw', reply):
            self.gui.connect_port()
            self.wait_until(lambda: 1 in self.gui.received_at)
            self.assertTrue(self.gui.is_connected)
            self.gui.close()
            self.wait_until(lambda: self.gui.worker is None)
        self.assertFalse(self.gui.is_connected)


if __name__ == '__main__':
    unittest.main()
