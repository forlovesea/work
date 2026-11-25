import queue
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_agg import FigureCanvasAgg


class FakeInstrument:
    def __init__(
        self, response, stop_event, stop_on_response=True, stop_response=None
    ):
        self.responses = list(response) if isinstance(response, (list, tuple)) else [response]
        self.stop_event = stop_event
        self.stop_on_response = stop_on_response
        self.stop_response = stop_response
        self.commands = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def write(self, data):
        self.commands.append(data)
        return len(data)

    def flush(self):
        pass

    def readline(self):
        response = self.responses.pop(0) if self.responses else b""
        if response and (
            self.stop_on_response or response == self.stop_response
        ):
            self.stop_event.set()
        return response


class RawSerialDataTests(unittest.TestCase):
    def make_logger(self):
        logger = main.AgilentLogger.__new__(main.AgilentLogger)
        logger.events = queue.Queue()
        logger.stop_event = threading.Event()
        return logger

    def run_measurement(self, response, timeout_seconds=10, parity="없음"):
        logger = self.make_logger()
        instrument = FakeInstrument(response, logger.stop_event)
        with patch.object(main.serial, "Serial", return_value=instrument) as serial_factory:
            logger.measure("COM1", 9600, 1000, "없음", parity, timeout_seconds)
        events = []
        while not logger.events.empty():
            events.append(logger.events.get_nowait())
        return instrument, events, serial_factory

    def test_measurement_logs_exact_command_and_response_bytes(self):
        response = b"+1.23456789E+00\r\n"
        instrument, events, serial_factory = self.run_measurement(response)

        raw_events = [payload for event, payload in events if event == "raw"]
        self.assertIn(("TX", b"MEAS:VOLT:DC?\n"), raw_events)
        self.assertIn(("RX", response), raw_events)
        self.assertEqual(
            instrument.commands,
            [b"SYST:REM\n", b"MEAS:VOLT:DC?\n"],
        )
        self.assertIn(("TX", b"SYST:REM\n"), raw_events)
        self.assertEqual(serial_factory.call_args.kwargs["timeout"], 10)
        self.assertIn("0D 0A", main.format_raw_event("RX", response))
        self.assertIn(r"\r\n", main.format_raw_event("RX", response))
        samples = [payload for event, payload in events if event == "sample"]
        self.assertEqual(len(samples), 1)
        self.assertAlmostEqual(samples[0][1], 1.23456789)
        self.assertEqual(events[-1], ("stopped", None))

    def test_timeout_logs_empty_receive(self):
        _, events, serial_factory = self.run_measurement(b"", timeout_seconds=20)

        self.assertEqual(serial_factory.call_args.kwargs["timeout"], 20)
        self.assertIn(("raw", ("RX", b"")), events)
        self.assertTrue(any(event == "error" and "20초 동안" in payload for event, payload in events))

    def test_measurement_timeout_drains_interrupted_queries_and_retries(self):
        logger = self.make_logger()
        response = b"+1.76522660E+00\r\n"
        instrument = FakeInstrument(
            [
                b"",
                b'-410,"Query INTERRUPTED"\r\n',
                b'-410,"Query INTERRUPTED"\r\n',
                b'+0,"No error"\r\n',
                response,
            ],
            logger.stop_event,
            stop_on_response=False,
            stop_response=response,
        )

        logger._measure_with_instrument(instrument, "COM1", 1000, 10)

        self.assertEqual(
            instrument.commands,
            [
                b"SYST:REM\n",
                b"MEAS:VOLT:DC?\n",
                b"SYST:ERR?\n",
                b"SYST:ERR?\n",
                b"SYST:ERR?\n",
                b"SYST:REM\n",
                b"MEAS:VOLT:DC?\n",
            ],
        )
        events = list(logger.events.queue)
        self.assertEqual(
            [payload for event, payload in events if event == "sample"],
            [(unittest.mock.ANY, 1.76522660)],
        )
        self.assertIn(
            ("raw", ("RX", b'-410,"Query INTERRUPTED"\r\n')),
            events,
        )
        self.assertIn(
            ("raw", ("RX", b'+0,"No error"\r\n')),
            events,
        )

    def test_measurement_uses_seven_bit_even_parity_when_selected(self):
        _, _, serial_factory = self.run_measurement(b"1.0\r\n", parity="짝수")

        self.assertEqual(serial_factory.call_args.kwargs["bytesize"], main.serial.SEVENBITS)
        self.assertEqual(serial_factory.call_args.kwargs["parity"], main.serial.PARITY_EVEN)

    def test_measurement_reuses_connected_serial_handle(self):
        logger = self.make_logger()
        instrument = FakeInstrument(b"1.0\r\n", logger.stop_event)
        logger.disconnect_requested = False

        with patch.object(main.serial, "Serial") as serial_factory:
            logger.measure("COM1", 9600, 1000, "없음", "없음", 10, instrument)

        serial_factory.assert_not_called()
        self.assertIn(("sample", unittest.mock.ANY), list(logger.events.queue))

    def test_error_queue_query_sends_command_and_logs_response(self):
        logger = self.make_logger()
        response = b'-113,"Undefined header"\r\n'
        instrument = FakeInstrument(response, logger.stop_event)
        with patch.object(main.serial, "Serial", return_value=instrument) as serial_factory:
            logger.read_error_queue("COM1", 9600, "없음", "없음", 10)

        events = []
        while not logger.events.empty():
            events.append(logger.events.get_nowait())
        self.assertEqual(instrument.commands, [b"SYST:ERR?\n"])
        self.assertEqual(serial_factory.call_args.kwargs["timeout"], 10)
        self.assertNotIn(("raw", ("TX", b"SYST:REM\n")), events)
        self.assertIn(("raw", ("TX", b"SYST:ERR?\n")), events)
        self.assertIn(("raw", ("RX", response)), events)
        self.assertIn(("status", '계측기 오류 큐 응답: -113,"Undefined header"'), events)
        self.assertEqual(events[-1], ("diagnostic_done", None))

    def test_even_parity_response_is_configured_for_error_queue_query(self):
        logger = self.make_logger()
        instrument = FakeInstrument(b"+513,\"RS-232 parity error\"\r\n", logger.stop_event)
        with patch.object(main.serial, "Serial", return_value=instrument) as serial_factory:
            logger.read_error_queue("COM1", 9600, "없음", "짝수", 10)

        self.assertEqual(serial_factory.call_args.kwargs["bytesize"], main.serial.SEVENBITS)
        self.assertEqual(serial_factory.call_args.kwargs["parity"], main.serial.PARITY_EVEN)


class ConnectionControlTests(unittest.TestCase):
    def make_app(self):
        app = main.AgilentLogger.__new__(main.AgilentLogger)
        app.instrument = None
        app.connected_port = None
        app.disconnect_requested = False
        app.worker = None
        app.diagnostic_worker = None
        app.stop_event = threading.Event()
        app.port_var = SimpleNamespace(get=lambda: "COM4")
        app.baud_var = SimpleNamespace(get=lambda: "9600")
        app.timeout_var = SimpleNamespace(get=lambda: "10")
        app.handshake_var = SimpleNamespace(get=lambda: "없음")
        app.parity_var = SimpleNamespace(get=lambda: "짝수")
        app.port_combo = Mock()
        app.port_refresh_button = Mock()
        app.baud_combo = Mock()
        app.handshake_combo = Mock()
        app.parity_combo = Mock()
        app.timeout_combo = Mock()
        app.connection_button = Mock()
        app.start_button = Mock()
        app.stop_button = Mock()
        app.error_query_button = Mock()
        app.status_var = Mock()
        return app

    def test_connect_button_opens_selected_port_and_toggles_to_disconnect(self):
        app = self.make_app()
        instrument = Mock()
        with patch.object(main.serial, "Serial", return_value=instrument) as serial_factory:
            app.toggle_connection()
            app.toggle_connection()

        self.assertEqual(app.connected_port, None)
        self.assertIsNone(app.instrument)
        serial_factory.assert_called_once_with(
            port="COM4",
            baudrate=9600,
            bytesize=main.serial.SEVENBITS,
            parity=main.serial.PARITY_EVEN,
            stopbits=main.serial.STOPBITS_ONE,
            timeout=10,
            write_timeout=10,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        instrument.close.assert_called_once_with()
        app.connection_button.configure.assert_any_call(
            text="COM 연결 해제", state=main.tk.NORMAL
        )
        app.connection_button.configure.assert_any_call(
            text="COM 연결", state=main.tk.NORMAL
        )

    def test_disconnect_cancels_read_when_measurement_is_active(self):
        app = self.make_app()
        app.instrument = Mock()
        app.worker = Mock()
        app.worker.is_alive.return_value = True

        app.disconnect_serial()

        self.assertTrue(app.disconnect_requested)
        self.assertTrue(app.stop_event.is_set())
        app.instrument.cancel_read.assert_called_once_with()
        app.instrument.close.assert_not_called()
        app.connection_button.configure.assert_called_once_with(
            text="COM 해제 중...", state=main.tk.DISABLED
        )

    def test_disconnect_releases_port_after_measurement_stops(self):
        app = self.make_app()
        instrument = Mock()
        app.instrument = instrument
        app.connected_port = "COM4"
        app.disconnect_requested = True
        app.stop_event = threading.Event()
        app.events = queue.Queue()
        app.events.put(("stopped", None))
        app.store = None
        app.follow_live = False
        app.root = Mock()
        app.raw_text = Mock()
        app.set_serial_settings_state = Mock()

        app.process_events()

        instrument.close.assert_called_once_with()
        self.assertIsNone(app.instrument)
        self.assertIsNone(app.connected_port)
        app.connection_button.configure.assert_called_with(
            text="COM 연결", state=main.tk.NORMAL
        )


class RawLogCopyTests(unittest.TestCase):
    def make_logger(self, selected_text="selected log"):
        logger = main.AgilentLogger.__new__(main.AgilentLogger)
        logger.raw_text = unittest.mock.Mock()
        logger.raw_text.get.return_value = selected_text
        logger.root = unittest.mock.Mock()
        logger.status_var = unittest.mock.Mock()
        return logger

    def test_selected_raw_log_is_copied(self):
        logger = self.make_logger()

        logger.copy_raw_selection()

        logger.raw_text.get.assert_called_once_with(main.tk.SEL_FIRST, main.tk.SEL_LAST)
        logger.root.clipboard_clear.assert_called_once_with()
        logger.root.clipboard_append.assert_called_once_with("selected log")

    def test_all_raw_log_is_copied(self):
        logger = self.make_logger("complete raw log")

        logger.copy_all_raw_log()

        logger.raw_text.get.assert_called_once_with("1.0", "end-1c")
        logger.root.clipboard_clear.assert_called_once_with()
        logger.root.clipboard_append.assert_called_once_with("complete raw log")

    def test_copy_without_selection_reports_status(self):
        logger = self.make_logger()
        logger.raw_text.get.side_effect = main.tk.TclError("no selection")

        logger.copy_raw_selection()

        logger.root.clipboard_append.assert_not_called()
        logger.status_var.set.assert_called_once_with("복사할 원시 로그를 먼저 선택하세요.")


class ChartUpdateTests(unittest.TestCase):
    def make_app(self, samples):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        store = main.MeasurementStore(Path(temporary_directory.name) / "measurements.sqlite3")
        self.addCleanup(store.close)
        for timestamp, voltage in samples:
            store.append(timestamp, voltage)
        store.flush()

        app = main.AgilentLogger.__new__(main.AgilentLogger)
        app.store = store
        app.samples = []
        app.sample_count = len(samples)
        app.voltage_precision = 3
        app.follow_live = True
        app.user_view_span = None
        app.view_start = None
        app.view_end = None
        app.history_update_after = None
        app.chart_pointer = None
        app.root = Mock()
        app.history_scrollbar = Mock()
        app.figure = main.Figure(figsize=(4, 3), dpi=100)
        app.axes = app.figure.add_subplot(111)
        app.axes.xaxis_date()
        app.date_locator = main.AutoDateLocator(minticks=3, maxticks=8)
        app.axes.xaxis.set_major_locator(app.date_locator)
        app.axes.xaxis.set_major_formatter(main.ConciseDateFormatter(app.date_locator))
        app.line, = app.axes.plot([], [], marker="o")
        app.annotation = app.axes.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points", visible=False
        )
        app.canvas = FigureCanvasAgg(app.figure)
        app.update_chart()
        return app

    def test_chart_scales_to_measurement_time_and_voltage(self):
        first_time = datetime(2026, 11, 24, 13, 30, 0)
        app = self.make_app([
            (first_time, 1.7694),
            (first_time + timedelta(seconds=1), 1.7698),
        ])

        app.update_chart()

        x_min, x_max = app.axes.get_xlim()
        y_min, y_max = app.axes.get_ylim()
        self.assertLess(x_max - x_min, 3 / 86400)
        self.assertLess(y_min, 1.769)
        self.assertGreater(y_max, 1.77)
        self.assertEqual(list(app.line.get_ydata()), [1.769, 1.77])
        self.assertEqual([sample[1] for sample in app.samples], [1.7694, 1.7698])
        self.assertEqual(app.axes.yaxis.get_offset_text().get_text(), "")
        tick_labels = [label.get_text() for label in app.axes.get_yticklabels()]
        self.assertTrue(any(label.startswith("1.769") for label in tick_labels))

    def test_voltage_precision_rounds_graph_without_rounding_samples(self):
        first_time = datetime(2026, 11, 24, 13, 30, 0)
        app = self.make_app([
            (first_time, 1.7694),
            (first_time + timedelta(seconds=1), 1.7698),
        ])
        for precision in (0, 1, 2, 3):
            app.voltage_precision = precision
            app.update_chart()
            tick_labels = [label.get_text() for label in app.axes.get_yticklabels()]
            self.assertTrue(tick_labels)
            self.assertEqual(
                list(app.line.get_ydata()),
                [round(1.7694, precision), round(1.7698, precision)],
            )
            if precision == 0:
                self.assertTrue(all("." not in label for label in tick_labels))
            else:
                self.assertTrue(
                    all(
                        "." in label
                        and len(label.rsplit(".", 1)[1]) == precision
                        for label in tick_labels
                    )
                )
            self.assertEqual([sample[1] for sample in app.samples], [1.7694, 1.7698])

    def test_voltage_readouts_track_run_statistics_and_selected_precision(self):
        app = main.AgilentLogger.__new__(main.AgilentLogger)
        app.sample_count = 0
        app.voltage_precision = 2
        app.current_voltage = None
        app.minimum_voltage = None
        app.maximum_voltage = None
        app.average_voltage = None
        app.current_voltage_var = Mock()
        app.maximum_voltage_var = Mock()
        app.minimum_voltage_var = Mock()
        app.voltage_range_var = Mock()
        app.average_voltage_var = Mock()

        for voltage in (1.234, 2.345, 1.876):
            app.update_measurement_statistics(voltage)

        app.current_voltage_var.set.assert_called_with("현재 전압: 1.88 V")
        app.maximum_voltage_var.set.assert_called_with("Max: 2.35 V")
        app.minimum_voltage_var.set.assert_called_with("Min: 1.23 V")
        app.voltage_range_var.set.assert_called_with("Diff: 1.11 V")
        app.average_voltage_var.set.assert_called_with("Avg: 1.82 V")

    def test_hovering_a_point_shows_timestamp_and_voltage(self):
        first_time = datetime(2026, 11, 24, 13, 30, 0)
        app = self.make_app(
            [(first_time, 1.7694), (first_time + timedelta(seconds=1), 1.7698)]
        )

        x, y = app.axes.transData.transform((main.date2num(first_time), 1.769))
        event = MouseEvent("motion_notify_event", app.canvas, x, y)
        app.on_chart_motion(event)

        self.assertTrue(app.annotation.get_visible())
        self.assertIn("1.769 V", app.annotation.get_text())
        self.assertIn("2026-11-24 13:30:00", app.annotation.get_text())

    def test_measurement_status_uses_selected_precision(self):
        app = main.AgilentLogger.__new__(main.AgilentLogger)
        app.events = queue.Queue()
        timestamp = datetime(2026, 11, 24, 13, 30, 0)
        app.events.put(("sample", (timestamp, 1.7652266)))
        app.store = SimpleNamespace(
            append=Mock(),
            path=Path("recording.sqlite3"),
        )
        app.storage_error_reported = False
        app.follow_live = False
        app.sample_count = 0
        app.status_var = Mock()
        app.root = Mock()
        app.raw_text = Mock()
        app.update_measurement_statistics = Mock()
        app.update_history_scrollbar = Mock()
        app.voltage_precision = 2

        app.process_events()

        app.store.append.assert_called_once_with(timestamp, 1.7652266)
        app.status_var.set.assert_any_call(
            "측정 중 | 2026-11-24 13:30:00 | 1.77 V | 0개 | 기록: recording.sqlite3"
        )

    def test_wheel_zoom_changes_time_range_and_rescales_voltage(self):
        first_time = datetime(2026, 11, 24, 13, 30, 0)
        app = self.make_app([
            (first_time, 1.0),
            (first_time + timedelta(seconds=1), 2.0),
            (first_time + timedelta(seconds=2), 5.0),
        ])
        original_span = app.axes.get_xlim()[1] - app.axes.get_xlim()[0]
        event = SimpleNamespace(
            inaxes=app.axes,
            xdata=main.date2num(first_time),
            button="up",
            step=1,
        )

        app.on_chart_scroll(event)
        app.on_chart_scroll(event)

        x_min, x_max = app.axes.get_xlim()
        y_min, y_max = app.axes.get_ylim()
        self.assertLess(x_max - x_min, original_span)
        self.assertLessEqual(y_max, 5.0)
        self.assertLessEqual(y_min, 1.0)

        event.step = -1
        event.button = "down"
        app.on_chart_scroll(event)
        app.on_chart_scroll(event)
        restored_span = app.axes.get_xlim()[1] - app.axes.get_xlim()[0]
        self.assertAlmostEqual(restored_span, original_span)
        self.assertGreaterEqual(app.axes.get_ylim()[1], 5.0)

    def test_horizontal_scrollbar_displays_earlier_measurements(self):
        first_time = datetime(2026, 11, 24, 13, 30, 0)
        app = self.make_app(
            [
                (first_time + timedelta(seconds=index), float(index))
                for index in range(100)
            ]
        )
        app.user_view_span = 10 / 86400
        app.update_chart()

        app.on_history_scroll("moveto", "0")
        app.render_history_view()

        self.assertFalse(app.follow_live)
        self.assertEqual(app.samples[0][0], first_time)
        self.assertLessEqual(app.samples[-1][0], first_time + timedelta(seconds=10))


if __name__ == "__main__":
    unittest.main()
