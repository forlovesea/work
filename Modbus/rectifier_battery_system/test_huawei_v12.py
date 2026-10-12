"""Offline Huawei register, transport and GUI regression checks."""
import os
import struct
import time
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pyside6_GUI_V12_modbus as monitor


def packet(data, slave=33):
    body = bytes([slave, 3, len(data)]) + data
    return body + struct.pack('<H', monitor.count_crc(body))


class SerialStub:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks else 0

    def reset_input_buffer(self):
        pass

    def write(self, frame):
        return len(frame)

    def read(self, size):
        if self.chunks:
            return self.chunks.pop(0)
        time.sleep(0.001)
        return b''


class HuaweiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = monitor.QApplication.instance() or monitor.QApplication([])

    def test_original_registers_and_signed_values(self):
        worker = monitor.PollWorker('fake')
        values = []
        worker.reading.connect(lambda name, value: values.append((name, value)))
        from unittest.mock import Mock
        master = Mock()
        master.send_raw.side_effect = [packet(struct.pack(fmt, value)) for fmt, value in
                                       [('>h', -5), ('>I', 512), ('>i', -123), ('>H', 80)]]
        worker.poll_once(master)
        self.assertEqual(values, [('temperature', -5), ('voltage', 51.2), ('current', -12.3), ('soc', 80)])
        requests = [struct.unpack('>BBHH', c.args[0][:6]) for c in master.send_raw.call_args_list]
        self.assertEqual(requests, [(33, 3, 0xA706, 1), (33, 3, 0xA731, 2),
                                    (33, 3, 0xA733, 2), (33, 3, 0xA739, 1)])

    def test_bad_crc_wrong_slave_and_fragmented_reply(self):
        good = packet(struct.pack('>H', 80))
        bad = good[:-1] + bytes([good[-1] ^ 1])
        master = monitor.ModbusMaster('fake')
        master.client = SerialStub([bad, packet(b'\x00\x01', slave=2), good[:3], good[3:]])
        self.assertEqual(master.send_raw(monitor.build_modbus_frame(33, 3, 0xA739, 1)), good)

    def test_invalid_reply_is_never_decoded(self):
        master = monitor.ModbusMaster('fake')
        master.client = SerialStub([packet(b'\x00\x01', slave=2)])
        with self.assertRaises(monitor.ModbusReadError):
            master.send_raw(monitor.build_modbus_frame(33, 3, 0xA739, 1))
        self.assertTrue(master.recover)

    def test_failed_read_does_not_stop_other_fields(self):
        from unittest.mock import Mock
        worker = monitor.PollWorker('fake')
        values = []
        worker.reading.connect(lambda name, value: values.append((name, value)))
        master = Mock()
        master.send_raw.side_effect = [monitor.ModbusReadError('timeout'), packet(struct.pack('>I', 512)),
                                      packet(struct.pack('>i', 10)), packet(struct.pack('>H', 80))]
        worker.poll_once(master)
        self.assertEqual(values[0], ('temperature', None))
        self.assertEqual(values[-1], ('soc', 80))

    def test_gui_no_autoconnect_previous_values_and_blink(self):
        gui = monitor.BMSMonitor()
        try:
            self.assertIsNone(gui.worker)
            gui.is_connected = True
            gui.on_reading('voltage', 51.2)
            gui.on_reading('voltage', None)
            self.assertIn('previous', gui.lbl_voltage.text())
            with patch.object(monitor.time, 'monotonic') as clock:
                clock.return_value = 100
                gui.on_activity('TX')
                clock.return_value = 100.12
                gui.on_activity('TX')
                self.assertEqual(gui.activity_leds['TX'].accessibleName(), 'TX: idle')
                clock.return_value = 100.19
                gui.refresh_leds()
                self.assertEqual(gui.activity_leds['TX'].accessibleName(), 'TX: active')
            gui.on_finished()
            self.assertTrue(all(led.accessibleName().endswith('idle') for led in gui.activity_leds.values()))
        finally:
            gui.close()

    def test_activity_works_with_logging_paused(self):
        worker = monitor.PollWorker('fake')
        worker.log_enabled = False
        seen, logs = [], []
        worker.activity.connect(seen.append)
        worker.frame_log.connect(logs.append)
        worker.trace('TX', b'123')
        worker.trace('RX', b'456')
        self.assertEqual(seen, ['TX', 'RX'])
        self.assertEqual(logs, [])

    def test_close_cancels_pending_serial_read(self):
        gui = monitor.BMSMonitor()
        gui.cmb_port.setCurrentText('FAKE')
        closed = []
        def connect(master):
            master.client = SerialStub([])
            master.client.close = lambda: closed.append(True)
            return True
        with patch.object(monitor.ModbusMaster, 'connect', connect):
            gui.connect_serial()
            deadline = time.monotonic() + 2
            while not gui.is_connected and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)
            self.assertTrue(gui.is_connected)
            gui.close()
            while gui.worker is not None and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)
            self.assertIsNone(gui.worker)
            self.assertEqual(closed, [True])

    def test_connection_failure_releases_worker(self):
        gui = monitor.BMSMonitor()
        gui.cmb_port.setCurrentText('FAKE')
        try:
            with patch.object(monitor.ModbusMaster, 'connect', side_effect=OSError('port busy')):
                gui.connect_serial()
                deadline = time.monotonic() + 3
                while gui.worker is not None and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.005)
                self.assertIsNone(gui.worker)
                self.assertIn('port busy', gui.lbl_connection.text())
                self.assertTrue(gui.cmb_port.isEnabled())
        finally:
            gui.close()


if __name__ == '__main__':
    unittest.main()
