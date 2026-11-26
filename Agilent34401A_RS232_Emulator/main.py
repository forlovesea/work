import os
import queue
import sqlite3
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib
import serial
from serial.tools import list_ports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter, date2num, num2date
from matplotlib.figure import Figure
from matplotlib.ticker import FormatStrFormatter, MaxNLocator, MultipleLocator

from measurement_store import MeasurementStore, PLOT_MAX_POINTS

MAX_MEASUREMENT_RECOVERY_ATTEMPTS = 3
MAX_ERROR_QUEUE_DRAIN = 32
SERIAL_RECOVERY_SETTLE_SECONDS = 0.25
APP_VERSION = "v1.0.2"
RELEASE_DATE = "2026-11-26"


def measurement_interval_ms(hours, minutes, milliseconds):
    if not 0 <= hours <= 24:
        raise ValueError("Hour는 0~24 범위로 설정하세요.")
    if not 0 <= minutes <= 60:
        raise ValueError("Min은 0~60 범위로 설정하세요.")
    if not 0 <= milliseconds <= 30000:
        raise ValueError("ms는 0~30000 범위로 설정하세요.")

    interval_ms = hours * 3_600_000 + minutes * 60_000 + milliseconds
    if interval_ms == 0:
        raise ValueError("측정 간격은 0보다 커야 합니다.")
    return interval_ms

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False


def format_raw_event(direction, data):
    ascii_data = data.decode("ascii", errors="backslashreplace")
    ascii_display = repr(ascii_data) if data else "(응답 없음)"
    hex_display = data.hex(" ").upper() if data else "(수신 바이트 없음)"
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    return f"{timestamp} {direction:<2} ASCII: {ascii_display} | HEX: {hex_display}"


def serial_format_for(parity):
    formats = {
        "없음": (serial.EIGHTBITS, serial.PARITY_NONE),
        "홀수": (serial.SEVENBITS, serial.PARITY_ODD),
        "짝수": (serial.SEVENBITS, serial.PARITY_EVEN),
    }
    return formats[parity]


def serial_options_for(port, baudrate, handshake, parity, timeout_seconds):
    bytesize, parity_mode = serial_format_for(parity)
    return {
        "port": port,
        "baudrate": baudrate,
        "bytesize": bytesize,
        "parity": parity_mode,
        "stopbits": serial.STOPBITS_ONE,
        "timeout": timeout_seconds,
        "write_timeout": timeout_seconds,
        "xonxoff": handshake == "XON/XOFF",
        "rtscts": handshake == "RTS/CTS",
        "dsrdtr": handshake == "DTR/DSR",
    }


class AgilentLogger:
    def __init__(self, root):
        self.root = root
        self.root.title(
            f"Agilent 34401A 실시간 전압 측정 | {APP_VERSION} | {RELEASE_DATE}"
        )
        icon_path = Path(__file__).resolve().parent / "assets" / "Agilent34401A.ico"
        self.root.iconbitmap(str(icon_path))
        self.root.geometry("1000x790")
        self.root.minsize(760, 620)

        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.instrument = None
        self.connected_port = None
        self.disconnect_requested = False
        self.worker = None
        self.diagnostic_worker = None
        self.export_worker = None
        self.store = None
        self.samples = []
        self.sample_count = 0
        self.current_voltage = None
        self.minimum_voltage = None
        self.maximum_voltage = None
        self.average_voltage = None
        self.measurement_started_at = None
        self.measurement_stopped_at = None
        self.voltage_precision = 3
        self.follow_live = True
        self.user_view_span = None
        self.view_start = None
        self.view_end = None
        self.history_update_after = None
        self.storage_error_reported = False
        self.storage_error_message = None
        self.chart_pointer = None

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="9600")
        self.interval_hours_var = tk.StringVar(value="0")
        self.interval_minutes_var = tk.StringVar(value="0")
        self.interval_milliseconds_var = tk.StringVar(value="1000")
        self.timeout_var = tk.StringVar(value="10")
        self.handshake_var = tk.StringVar(value="없음")
        self.parity_var = tk.StringVar(value="없음")
        self.status_var = tk.StringVar(value="연결 대기")
        self.voltage_precision_var = tk.StringVar(value="3")
        self.current_voltage_var = tk.StringVar(value="현재 전압: --V")
        self.maximum_voltage_var = tk.StringVar(value=" Max: -- V")
        self.minimum_voltage_var = tk.StringVar(value=" Min: -- V")
        self.voltage_range_var = tk.StringVar(value=" Diff: -- V")
        self.average_voltage_var = tk.StringVar(value=" Avg: -- V")
        self.elapsed_time_var = tk.StringVar(
            value="*Elapsed Time: 0 hour 0 min 0 sec"
        )

        self._build_ui()
        self.set_serial_settings_state(connected=False)
        self.refresh_ports()
        self.root.after(100, self.process_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        settings = ttk.LabelFrame(self.root, text="계측기 연결 및 측정 설정", padding=10)
        settings.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(settings, text="COM 포트").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        self.port_combo = ttk.Combobox(settings, textvariable=self.port_var, width=12, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
        self.port_refresh_button = ttk.Button(settings, text="포트 새로고침", command=self.refresh_ports)
        self.port_refresh_button.grid(
            row=0, column=2, sticky=tk.W, padx=4, pady=4
        )

        ttk.Label(settings, text="통신 속도").grid(row=0, column=3, sticky=tk.W, padx=(16, 4), pady=4)
        self.baud_combo = ttk.Combobox(
            settings,
            textvariable=self.baud_var,
            values=(
                "300",
                "600",
                "1200",
                "2400",
                "4800",
                "9600",
                "19200",
                "38400",
                "57600",
                "115200",
            ),
            width=8,
            state="readonly",
        )
        self.baud_combo.grid(row=0, column=4, sticky=tk.W, padx=4, pady=4)

        ttk.Label(settings, text="흐름 제어").grid(row=0, column=5, sticky=tk.W, padx=(16, 4), pady=4)
        self.handshake_combo = ttk.Combobox(
            settings,
            textvariable=self.handshake_var,
            values=("없음", "XON/XOFF", "RTS/CTS", "DTR/DSR"),
            width=10,
            state="readonly",
        )
        self.handshake_combo.grid(row=0, column=6, sticky=tk.W, padx=4, pady=4)

        ttk.Label(settings, text="패리티").grid(row=0, column=7, sticky=tk.W, padx=(12, 4), pady=4)
        self.parity_combo = ttk.Combobox(
            settings,
            textvariable=self.parity_var,
            values=("없음", "홀수", "짝수"),
            width=6,
            state="readonly",
        )
        self.parity_combo.grid(row=0, column=8, sticky=tk.W, padx=4, pady=4)

        ttk.Label(settings, text="측정 간격").grid(
            row=1, column=0, sticky=tk.W, padx=4, pady=4
        )
        interval_frame = ttk.Frame(settings)
        interval_frame.grid(
            row=1, column=1, columnspan=3, sticky=tk.W, padx=4, pady=4
        )
        for variable, maximum, width, label in (
            (self.interval_hours_var, 24, 4, "Hour"),
            (self.interval_minutes_var, 60, 4, "Min"),
            (self.interval_milliseconds_var, 30000, 6, "ms"),
        ):
            ttk.Spinbox(
                interval_frame,
                from_=0,
                to=maximum,
                increment=1,
                textvariable=variable,
                width=width,
            ).pack(side=tk.LEFT)
            ttk.Label(interval_frame, text=label).pack(
                side=tk.LEFT, padx=(2, 8)
            )

        self.start_button = ttk.Button(
            settings, text="측정 시작", command=self.start, state=tk.DISABLED
        )
        self.start_button.grid(row=1, column=4, sticky=tk.W, padx=4, pady=4)
        self.stop_button = ttk.Button(settings, text="측정 중지", command=self.stop, state=tk.DISABLED)
        self.stop_button.grid(row=1, column=5, sticky=tk.W, padx=4, pady=4)
        self.csv_button = ttk.Button(settings, text="CSV 저장", command=self.save_csv)
        self.csv_button.grid(
            row=2, column=4, sticky=tk.W, padx=4, pady=4
        )
        self.excel_button = ttk.Button(settings, text="Excel 저장", command=self.save_excel)
        self.excel_button.grid(
            row=2, column=5, sticky=tk.W, padx=4, pady=4
        )
        ttk.Label(settings, text="응답 대기 (초)").grid(
            row=1, column=6, sticky=tk.W, padx=(12, 4), pady=4
        )
        self.timeout_combo = ttk.Combobox(
            settings,
            textvariable=self.timeout_var,
            values=("3", "5", "10", "20"),
            width=5,
            state="readonly",
        )
        self.timeout_combo.grid(row=1, column=7, sticky=tk.W, padx=4, pady=4)
        self.connection_button = ttk.Button(
            settings, text="COM 연결", command=self.toggle_connection
        )
        self.connection_button.grid(row=1, column=8, sticky=tk.W, padx=4, pady=4)

        ttk.Label(
            settings,
            text="※ 실제 측정 속도는 계측기 응답 및 RS-232 통신 속도에 따라 설정 간격보다 느릴 수 있습니다. 응답 대기는 10초 이상을 권장합니다.",
            foreground="#8a4b08",
        ).grid(row=3, column=0, columnspan=9, sticky=tk.W, padx=4, pady=(5, 0))

        chart_frame = ttk.Frame(self.root)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        readout_frame = ttk.Frame(chart_frame)
        readout_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
        readout_controls = ttk.Frame(readout_frame)
        readout_controls.pack(side=tk.LEFT)
        ttk.Label(readout_controls, text="Y축(전압V) 소수 자릿수").pack(
            side=tk.LEFT, padx=(0, 4)
        )
        self.voltage_precision_combo = ttk.Combobox(
            readout_controls,
            textvariable=self.voltage_precision_var,
            values=tuple(str(precision) for precision in range(7)),
            width=3,
            state="readonly",
        )
        self.voltage_precision_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.voltage_precision_combo.bind(
            "<<ComboboxSelected>>", self.on_voltage_precision_change
        )
        ttk.Label(
            readout_frame,
            textvariable=self.elapsed_time_var,
            font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.RIGHT, padx=(8, 0))

        measurement_readouts = ttk.Frame(readout_frame)
        measurement_readouts.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        ttk.Label(
            measurement_readouts,
            textvariable=self.current_voltage_var,
            foreground="#000000",
        ).pack(side=tk.LEFT)
        ttk.Label(
            measurement_readouts, text=" (", foreground="#000000"
        ).pack(side=tk.LEFT)
        for variable, color in (
            (self.maximum_voltage_var, "#c62828"),
            (self.minimum_voltage_var, "#1565c0"),
            (self.voltage_range_var, "#7b1fa2"),
            (self.average_voltage_var, "#2e7d32"),
        ):
            ttk.Label(
                measurement_readouts,
                textvariable=variable,
                foreground=color,
            ).pack(side=tk.LEFT)
        ttk.Label(
            measurement_readouts, text=")", foreground="#000000"
        ).pack(side=tk.LEFT)

        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.axes.set_title("실시간 DC 전압")
        self.axes.set_xlabel("시간")
        self.axes.set_ylabel("전압 (V)")
        self.axes.grid(True, alpha=0.3)
        self.axes.xaxis_date()
        self.date_locator = AutoDateLocator(minticks=3, maxticks=8)
        self.axes.xaxis.set_major_locator(self.date_locator)
        self.axes.xaxis.set_major_formatter(ConciseDateFormatter(self.date_locator))
        self.figure.tight_layout()
        self.line, = self.axes.plot(
            [], [], color="#1565c0", linewidth=1.2, marker="o", markersize=3
        )
        self.annotation = self.axes.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "#1565c0", "alpha": 0.95},
            arrowprops={"arrowstyle": "->", "color": "#1565c0"},
            visible=False,
            zorder=5,
        )

        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect("motion_notify_event", self.on_chart_motion)
        self.canvas.mpl_connect("scroll_event", self.on_chart_scroll)
        self.canvas.draw()
        self.history_scrollbar = ttk.Scrollbar(
            chart_frame, orient=tk.HORIZONTAL, command=self.on_history_scroll
        )
        self.history_scrollbar.pack(fill=tk.X, padx=8, pady=(0, 3))
        self.history_scrollbar.bind("<ButtonRelease-1>", self.render_history_view)

        raw_frame = ttk.LabelFrame(self.root, text="RS-232 송수신 원시 데이터 (TX/RX)", padding=6)
        raw_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        raw_toolbar = ttk.Frame(raw_frame)
        raw_toolbar.pack(fill=tk.X)
        ttk.Label(
            raw_toolbar,
            text=r"MEAS:VOLT:DC? 명령으로 측정을 요청합니다. TX 끝의 \n은 LF 바이트입니다.",
        ).pack(side=tk.LEFT)
        self.error_query_button = ttk.Button(
            raw_toolbar,
            text="SYST:ERR? 오류 조회",
            command=self.query_error_queue,
            state=tk.DISABLED,
        )
        self.error_query_button.pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(raw_toolbar, text="원시 로그 지우기", command=self.clear_raw_log).pack(side=tk.RIGHT)
        ttk.Button(raw_toolbar, text="전체 복사", command=self.copy_all_raw_log).pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        ttk.Button(raw_toolbar, text="선택 복사", command=self.copy_raw_selection).pack(
            side=tk.RIGHT, padx=(4, 0)
        )

        raw_log_frame = ttk.Frame(raw_frame)
        raw_log_frame.pack(fill=tk.X, pady=(4, 0))
        raw_log_frame.columnconfigure(0, weight=1)
        self.raw_text = tk.Text(raw_log_frame, height=5, wrap=tk.NONE, font=("Consolas", 9))
        self.raw_text.bind("<KeyPress>", self.handle_raw_keypress)
        self.raw_text.bind("<Button-3>", self.show_raw_context_menu)
        self.raw_context_menu = tk.Menu(self.root, tearoff=False)
        self.raw_context_menu.add_command(label="복사", command=self.copy_raw_selection)
        self.raw_context_menu.add_command(label="전체 선택", command=self.select_all_raw_log)
        raw_scroll = ttk.Scrollbar(raw_log_frame, orient=tk.VERTICAL, command=self.raw_text.yview)
        raw_xscroll = ttk.Scrollbar(raw_log_frame, orient=tk.HORIZONTAL, command=self.raw_text.xview)
        self.raw_text.configure(yscrollcommand=raw_scroll.set, xscrollcommand=raw_xscroll.set)
        self.raw_text.grid(row=0, column=0, sticky="nsew")
        raw_scroll.grid(row=0, column=1, sticky="ns")
        raw_xscroll.grid(row=1, column=0, sticky="ew")

        ttk.Label(self.root, textvariable=self.status_var, anchor=tk.W, padding=(12, 4)).pack(
            fill=tk.X, side=tk.BOTTOM
        )

    def refresh_ports(self):
        ports = [port.device for port in list_ports.comports()]
        self.port_combo["values"] = ports
        if self.port_var.get() not in ports:
            self.port_var.set(ports[0] if ports else "")
        if not ports:
            self.status_var.set("사용 가능한 COM 포트가 없습니다. 계측기 연결을 확인하세요.")

    def set_serial_settings_state(self, connected):
        state = tk.DISABLED if connected else "readonly"
        self.port_combo.configure(state=state)
        self.port_refresh_button.configure(state=tk.DISABLED if connected else tk.NORMAL)
        self.baud_combo.configure(state=state)
        self.handshake_combo.configure(state=state)
        self.parity_combo.configure(state=state)
        self.timeout_combo.configure(state=state)

    def toggle_connection(self):
        if self.instrument is None:
            self.connect_serial()
        else:
            self.disconnect_serial()

    def connect_serial(self):
        if (self.worker and self.worker.is_alive()) or (
            self.diagnostic_worker and self.diagnostic_worker.is_alive()
        ):
            messagebox.showwarning("COM 연결 중", "현재 작업이 끝난 뒤 COM 포트를 연결하세요.")
            return

        port = self.port_var.get().strip()
        if not port:
            messagebox.showerror("COM 포트 선택", "계측기가 연결된 COM 포트를 선택하세요.")
            return
        try:
            baudrate = int(self.baud_var.get())
            timeout_seconds = int(self.timeout_var.get())
            options = serial_options_for(
                port,
                baudrate,
                self.handshake_var.get(),
                self.parity_var.get(),
                timeout_seconds,
            )
        except (KeyError, ValueError):
            messagebox.showerror("설정 오류", "통신 속도, 패리티, 흐름 제어 및 응답 대기를 확인하세요.")
            return

        try:
            self.instrument = serial.Serial(**options)
        except (serial.SerialException, OSError, ValueError) as error:
            self.instrument = None
            messagebox.showerror(
                "COM 연결 실패",
                f"{port}에 연결하지 못했습니다. 다른 프로그램이 COM 포트를 사용 중인지 확인하세요.\n{error}",
            )
            return

        self.connected_port = port
        self.disconnect_requested = False
        self.set_serial_settings_state(connected=True)
        self.connection_button.configure(text="COM 연결 해제", state=tk.NORMAL)
        self.start_button.configure(state=tk.NORMAL)
        self.error_query_button.configure(state=tk.NORMAL)
        self.status_var.set(f"{port} COM 연결됨")

    def disconnect_serial(self):
        if self.instrument is None:
            return
        self.disconnect_requested = True
        if (self.worker and self.worker.is_alive()) or (
            self.diagnostic_worker and self.diagnostic_worker.is_alive()
        ):
            self.freeze_elapsed_time()
            self.connection_button.configure(text="COM 해제 중...", state=tk.DISABLED)
            self.start_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.DISABLED)
            self.error_query_button.configure(state=tk.DISABLED)
            self.stop_event.set()
            self.status_var.set("현재 작업을 중지하고 COM 포트를 해제 중...")
            try:
                self.instrument.cancel_read()
            except (serial.SerialException, OSError) as error:
                messagebox.showerror("COM 해제 지연", f"현재 응답 대기가 끝난 뒤 포트를 해제합니다.\n{error}")
            return

        self.release_serial_connection()

    def release_serial_connection(self):
        instrument = self.instrument
        if instrument is not None:
            try:
                instrument.close()
            except (serial.SerialException, OSError) as error:
                messagebox.showerror("COM 연결 해제 오류", f"포트를 해제하지 못했습니다.\n{error}")
                self.disconnect_requested = False
                self.connection_button.configure(text="COM 연결 해제", state=tk.NORMAL)
                self.start_button.configure(state=tk.NORMAL)
                self.error_query_button.configure(state=tk.NORMAL)
                return False

        self.instrument = None
        self.connected_port = None
        self.disconnect_requested = False
        self.set_serial_settings_state(connected=False)
        self.connection_button.configure(text="COM 연결", state=tk.NORMAL)
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.DISABLED)
        self.error_query_button.configure(state=tk.DISABLED)
        self.status_var.set("COM 연결 해제됨")
        return True

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        if self.diagnostic_worker and self.diagnostic_worker.is_alive():
            return
        if self.export_worker and self.export_worker.is_alive():
            messagebox.showwarning("저장 중", "파일 저장이 끝난 뒤 새 측정을 시작하세요.")
            return
        if self.instrument is None:
            messagebox.showwarning("COM 연결 필요", "측정을 시작하기 전에 COM 포트를 연결하세요.")
            return

        port = self.connected_port
        if port is None:
            messagebox.showwarning("COM 연결 필요", "연결된 COM 포트를 확인하세요.")
            return

        try:
            interval_hours = int(self.interval_hours_var.get())
            interval_minutes = int(self.interval_minutes_var.get())
            interval_milliseconds = int(self.interval_milliseconds_var.get())
            baudrate = int(self.baud_var.get())
            timeout_seconds = int(self.timeout_var.get())
        except ValueError:
            messagebox.showerror("설정 오류", "측정 간격, 통신 속도, 응답 대기 시간을 확인하세요.")
            return
        try:
            interval_ms = measurement_interval_ms(
                interval_hours, interval_minutes, interval_milliseconds
            )
        except ValueError as error:
            messagebox.showerror("설정 오류", str(error))
            return
        if timeout_seconds not in (3, 5, 10, 20):
            messagebox.showerror("설정 오류", "응답 대기 시간은 3, 5, 10, 20초 중에서 선택하세요.")
            return

        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            messagebox.showerror(
                "기록 저장 오류", "Windows 로컬 앱 데이터 폴더를 찾을 수 없습니다."
            )
            return
        if self.store is not None:
            try:
                self.store.close()
            except sqlite3.Error as error:
                messagebox.showerror("기록 저장 오류", f"기존 측정 기록을 닫지 못했습니다.\n{error}")
                return

        recording_directory = Path(local_app_data) / "Agilent34401A" / "Recordings"
        recording_name = f"Agilent34401A_{datetime.now():%Y%m%d_%H%M%S_%f}.sqlite3"
        if self.history_update_after is not None:
            self.root.after_cancel(self.history_update_after)
            self.history_update_after = None
        try:
            self.store = MeasurementStore(recording_directory / recording_name)
        except (OSError, sqlite3.Error) as error:
            messagebox.showerror("기록 저장 오류", f"측정 기록 파일을 만들지 못했습니다.\n{error}")
            self.store = None
            return

        self.samples.clear()
        self.reset_measurement_statistics()
        self.follow_live = True
        self.user_view_span = None
        self.view_start = None
        self.view_end = None
        self.storage_error_reported = False
        self.storage_error_message = None
        self.update_chart()
        self.stop_event.clear()
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.error_query_button.configure(state=tk.DISABLED)
        self.status_var.set(f"{port} 연결 및 측정 준비 중... | 기록 파일: {self.store.path}")

        self.measurement_started_at = time.monotonic()
        self.measurement_stopped_at = None
        self.update_elapsed_time()
        self.worker = threading.Thread(
            target=self.measure,
            args=(
                port,
                baudrate,
                interval_ms,
                self.handshake_var.get(),
                self.parity_var.get(),
                timeout_seconds,
                self.instrument,
            ),
            daemon=True,
        )
        self.worker.start()

    def measure(
        self, port, baudrate, interval_ms, handshake, parity, timeout_seconds, instrument=None
    ):
        options = serial_options_for(port, baudrate, handshake, parity, timeout_seconds)
        try:
            if instrument is None:
                with serial.Serial(**options) as opened_instrument:
                    self._measure_with_instrument(
                        opened_instrument, port, interval_ms, timeout_seconds
                    )
            else:
                self._measure_with_instrument(
                    instrument, port, interval_ms, timeout_seconds
                )
        except (serial.SerialException, TimeoutError, ValueError) as error:
            if not (
                getattr(self, "disconnect_requested", False)
                and self.stop_event.is_set()
            ):
                self.events.put(("error", str(error)))
        finally:
            self.events.put(("stopped", None))

    def _measure_with_instrument(self, instrument, port, interval_ms, timeout_seconds):
        self._send_remote_command(instrument)
        self.events.put(("status", f"{port} 연결됨 - DC 전압 측정 중"))

        interval_seconds = interval_ms / 1000
        recovery_attempts = 0
        while not self.stop_event.is_set():
            cycle_start = time.monotonic()
            command = b"MEAS:VOLT:DC?\n"
            instrument.write(command)
            self.events.put(("raw", ("TX", command)))
            response_bytes = instrument.readline()
            self.events.put(("raw", ("RX", response_bytes)))
            if not response_bytes:
                if self.stop_event.is_set():
                    break
                recovery_attempts += 1
                if recovery_attempts > MAX_MEASUREMENT_RECOVERY_ATTEMPTS:
                    raise TimeoutError(
                        f"계측기 측정 응답이 연속 {MAX_MEASUREMENT_RECOVERY_ATTEMPTS}회 "
                        f"없습니다(회당 {timeout_seconds}초). COM 포트, 통신 설정, "
                        "케이블 결선과 계측기 상태를 확인하세요."
                    )

                self.events.put(
                    (
                        "status",
                        "측정 응답이 없어 SYST:ERR?로 계측기 질의 상태를 맞춘 뒤 재시도합니다.",
                    )
                )
                if not self._resynchronize_instrument(instrument, timeout_seconds):
                    break
                if self.stop_event.wait(SERIAL_RECOVERY_SETTLE_SECONDS):
                    break
                self._send_remote_command(instrument)
                continue

            response = response_bytes.decode("ascii", errors="replace").strip()
            try:
                voltage = float(response)
            except ValueError as error:
                raise ValueError(f"계측기에서 숫자가 아닌 응답을 받았습니다: {response}") from error

            recovery_attempts = 0
            self.events.put(("sample", (datetime.now(), voltage)))
            remaining = interval_seconds - (time.monotonic() - cycle_start)
            if remaining > 0:
                self.stop_event.wait(remaining)

    def _send_remote_command(self, instrument):
        command = b"SYST:REM\n"
        instrument.write(command)
        self.events.put(("raw", ("TX", command)))

    def _resynchronize_instrument(self, instrument, timeout_seconds):
        for _ in range(MAX_ERROR_QUEUE_DRAIN):
            if self.stop_event.is_set():
                return False
            response = self._read_error_queue_response(instrument, timeout_seconds)
            if response is None:
                return False

            error_code_text = response.split(",", 1)[0].strip()
            try:
                error_code = int(error_code_text)
            except ValueError as error:
                raise ValueError(
                    f"SYST:ERR?에서 예상하지 못한 응답을 받았습니다: {response}"
                ) from error
            if error_code == 0:
                return True
        raise TimeoutError(
            f"SYST:ERR? 오류 큐가 {MAX_ERROR_QUEUE_DRAIN}회 조회 후에도 비워지지 않았습니다."
        )

    def query_error_queue(self):
        if (self.worker and self.worker.is_alive()) or (
            self.diagnostic_worker and self.diagnostic_worker.is_alive()
        ):
            messagebox.showwarning("측정 중", "오류 큐를 조회하기 전에 측정을 중지하세요.")
            return
        if not messagebox.askyesno(
            "계측기 오류 조회",
            "SYST:ERR?는 계측기 오류 큐의 가장 오래된 항목을 읽고 제거합니다. 계속할까요?",
        ):
            return

        if self.instrument is None or self.connected_port is None:
            messagebox.showwarning("COM 연결 필요", "오류 큐를 조회하기 전에 COM 포트를 연결하세요.")
            return

        try:
            baudrate = int(self.baud_var.get())
            timeout_seconds = int(self.timeout_var.get())
        except ValueError:
            messagebox.showerror("설정 오류", "통신 속도와 응답 대기 시간을 확인하세요.")
            return

        parity = self.parity_var.get()
        self.start_button.configure(state=tk.DISABLED)
        self.error_query_button.configure(state=tk.DISABLED)
        port = self.connected_port
        self.status_var.set(f"{port}에서 SYST:ERR? 응답 대기 중...")
        self.diagnostic_worker = threading.Thread(
            target=self.read_error_queue,
            args=(
                port,
                baudrate,
                self.handshake_var.get(),
                parity,
                timeout_seconds,
                self.instrument,
            ),
            daemon=True,
        )
        self.diagnostic_worker.start()

    def read_error_queue(
        self, port, baudrate, handshake, parity, timeout_seconds, instrument=None
    ):
        options = serial_options_for(port, baudrate, handshake, parity, timeout_seconds)
        try:
            if instrument is None:
                with serial.Serial(**options) as opened_instrument:
                    self._query_error_queue_with_instrument(
                        opened_instrument, timeout_seconds
                    )
            else:
                self._query_error_queue_with_instrument(
                    instrument, timeout_seconds
                )
        except (serial.SerialException, TimeoutError) as error:
            if not getattr(self, "disconnect_requested", False):
                self.events.put(("error", str(error)))
        finally:
            self.events.put(("diagnostic_done", None))

    def _query_error_queue_with_instrument(self, instrument, timeout_seconds):
        response = self._read_error_queue_response(instrument, timeout_seconds)
        if response is not None:
            self.events.put(("status", f"계측기 오류 큐 응답: {response}"))
        return response

    def _read_error_queue_response(self, instrument, timeout_seconds):
        command = b"SYST:ERR?\n"
        instrument.write(command)
        self.events.put(("raw", ("TX", command)))
        response_bytes = instrument.readline()
        self.events.put(("raw", ("RX", response_bytes)))
        if not response_bytes:
            if self.stop_event.is_set() or getattr(self, "disconnect_requested", False):
                return None
            raise TimeoutError(
                f"{timeout_seconds}초 동안 SYST:ERR? 응답이 없습니다. "
                "COM 포트, 계측기 통신 설정 및 케이블 결선을 확인하세요."
            )

        return response_bytes.decode("ascii", errors="replace").strip()
    def stop(self):
        self.stop_event.set()
        self.freeze_elapsed_time()
        self.stop_button.configure(state=tk.DISABLED)
        self.status_var.set("측정 중지 중...")

    def process_events(self):
        changed = False
        raw_lines = []
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "raw":
                    direction, data = payload
                    raw_lines.append(format_raw_event(direction, data))
                elif event == "sample":
                    if self.store is None or self.storage_error_reported:
                        continue
                    timestamp, voltage = payload
                    try:
                        self.store.append(timestamp, voltage)
                    except (OSError, sqlite3.Error) as error:
                        self.stop_event.set()
                        self.storage_error_reported = True
                        self.storage_error_message = str(error)
                        self.status_var.set(f"측정 기록 저장 오류: {error}")
                        messagebox.showerror(
                            "측정 기록 저장 오류",
                            f"디스크 공간 또는 파일 접근을 확인하세요.\n{error}",
                        )
                        continue
                    self.update_measurement_statistics(voltage)
                    changed = self.follow_live
                    self.status_var.set(
                        f"측정 중 | {timestamp:%Y-%m-%d %H:%M:%S} | "
                        f"{self.format_voltage(voltage)} V | "
                        f"{self.sample_count:,}개 | 기록: {self.store.path.name}"
                    )
                elif event == "status":
                    if not self.disconnect_requested:
                        self.status_var.set(payload)
                elif event == "error":
                    if not self.disconnect_requested:
                        self.status_var.set(f"오류: {payload}")
                        messagebox.showerror("계측기 통신 오류", payload)
                elif event == "stopped":
                    if (
                        self.measurement_started_at is not None
                        and self.measurement_stopped_at is None
                    ):
                        self.measurement_stopped_at = time.monotonic()
                    if self.store is not None:
                        try:
                            self.store.flush()
                        except sqlite3.Error as error:
                            if not self.storage_error_reported:
                                self.storage_error_reported = True
                                self.storage_error_message = str(error)
                                self.status_var.set(f"측정 기록 저장 오류: {error}")
                                messagebox.showerror(
                                    "측정 기록 저장 오류",
                                    f"마지막 측정값을 기록하지 못했습니다.\n{error}",
                                )
                    if self.disconnect_requested:
                        self.release_serial_connection()
                    else:
                        self.start_button.configure(state=tk.NORMAL)
                        self.stop_button.configure(state=tk.DISABLED)
                        self.error_query_button.configure(state=tk.NORMAL)
                    if self.stop_event.is_set() and self.instrument is not None:
                        if self.storage_error_message:
                            self.status_var.set(
                                f"측정 중지됨 | 기록 오류: {self.storage_error_message} | "
                                f"파일: {self.store.path if self.store else '없음'}"
                            )
                        else:
                            self.status_var.set(
                                f"측정 중지됨 | {self.sample_count:,}개 | "
                                f"기록 파일: {self.store.path if self.store else '없음'}"
                            )
                elif event == "diagnostic_done":
                    if self.disconnect_requested:
                        self.release_serial_connection()
                    else:
                        self.start_button.configure(state=tk.NORMAL)
                        self.error_query_button.configure(state=tk.NORMAL)
                elif event == "export_done":
                    kind, path, error = payload
                    self.csv_button.configure(state=tk.NORMAL)
                    self.excel_button.configure(state=tk.NORMAL)
                    if error:
                        self.status_var.set(f"{kind} 저장 오류: {error}")
                        messagebox.showerror("저장 오류", f"{kind} 파일을 저장하지 못했습니다.\n{error}")
                    else:
                        self.status_var.set(f"{kind} 저장 완료 | {path}")
        except queue.Empty:
            pass

        if raw_lines:
            self.raw_text.insert(tk.END, "\n".join(raw_lines) + "\n")
            line_count = int(self.raw_text.index(tk.END).split(".")[0])
            if line_count > 501:
                self.raw_text.delete("1.0", f"{line_count - 501}.0")
            self.raw_text.see(tk.END)

        if changed:
            self.update_chart()
        elif self.store is not None:
            self.update_history_scrollbar()
        self.update_elapsed_time()
        self.root.after(100, self.process_events)

    def clear_raw_log(self):
        self.raw_text.delete("1.0", tk.END)

    def handle_raw_keypress(self, event):
        if event.state & 0x4 and event.keysym.lower() == "c":
            self.copy_raw_selection()
        elif event.state & 0x4 and event.keysym.lower() == "a":
            self.select_all_raw_log()
        return "break"

    def show_raw_context_menu(self, event):
        self.raw_context_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def select_all_raw_log(self):
        self.raw_text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def copy_raw_selection(self):
        try:
            selected_text = self.raw_text.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            self.status_var.set("복사할 원시 로그를 먼저 선택하세요.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(selected_text)
        self.status_var.set("선택한 원시 로그를 복사했습니다.")

    def copy_all_raw_log(self):
        text = self.raw_text.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("원시 로그 전체를 복사했습니다.")

    def format_voltage(self, voltage):
        return f"{voltage:.{self.voltage_precision}f}"

    def update_elapsed_time(self):
        if self.measurement_started_at is None:
            elapsed_seconds = 0
        else:
            end_time = self.measurement_stopped_at
            if end_time is None:
                end_time = time.monotonic()
            elapsed_seconds = max(
                0, int(end_time - self.measurement_started_at)
            )

        hours, remainder = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed_time_var.set(
            f"*Elapsed Time: {hours} hour {minutes} min {seconds} sec"
        )

    def freeze_elapsed_time(self):
        if (
            self.measurement_started_at is not None
            and self.measurement_stopped_at is None
        ):
            self.measurement_stopped_at = time.monotonic()
        self.update_elapsed_time()

    def rounded_voltage(self, voltage):
        return round(voltage, self.voltage_precision)

    def update_voltage_readouts(self):
        if self.current_voltage is None:
            self.current_voltage_var.set("현재 전압: --V")
        else:
            self.current_voltage_var.set(
                f"현재 전압: {self.format_voltage(self.current_voltage)}V"
            )

        if self.sample_count == 0:
            self.maximum_voltage_var.set(" Max: -- V")
            self.minimum_voltage_var.set(" Min: -- V")
            self.voltage_range_var.set(" Diff: -- V")
            self.average_voltage_var.set(" Avg: -- V")
            return

        self.maximum_voltage_var.set(
            f" Max: {self.format_voltage(self.maximum_voltage)} V"
        )
        self.minimum_voltage_var.set(
            f" Min: {self.format_voltage(self.minimum_voltage)} V"
        )
        self.voltage_range_var.set(
            f" Diff: {self.format_voltage(self.maximum_voltage - self.minimum_voltage)} V"
        )
        self.average_voltage_var.set(
            f" Avg: {self.format_voltage(self.average_voltage)} V"
        )

    def reset_measurement_statistics(self):
        self.sample_count = 0
        self.current_voltage = None
        self.minimum_voltage = None
        self.maximum_voltage = None
        self.average_voltage = None
        self.update_voltage_readouts()

    def update_measurement_statistics(self, voltage):
        self.sample_count += 1
        self.current_voltage = voltage
        if self.sample_count == 1:
            self.minimum_voltage = voltage
            self.maximum_voltage = voltage
            self.average_voltage = voltage
        else:
            self.minimum_voltage = min(self.minimum_voltage, voltage)
            self.maximum_voltage = max(self.maximum_voltage, voltage)
            self.average_voltage += (voltage - self.average_voltage) / self.sample_count
        self.update_voltage_readouts()

    def on_voltage_precision_change(self, event=None):
        if event is not None and event.widget is not self.voltage_precision_combo:
            return
        self.voltage_precision = int(self.voltage_precision_var.get())
        self.update_voltage_readouts()
        self.update_chart()

    @staticmethod
    def chart_time_limits(samples):
        first_time, last_time = date2num((samples[0][0], samples[-1][0]))
        time_padding = max((last_time - first_time) * 0.05, 0.5 / 86400)
        return first_time - time_padding, last_time + time_padding

    def update_voltage_limits(self, samples):
        if not samples:
            self.axes.set_ylim(0, 1)
            return
        x_min, x_max = self.axes.get_xlim()
        voltages = [
            voltage
            for timestamp, voltage in samples
            if x_min <= date2num(timestamp) <= x_max
        ]
        if not voltages:
            center = (x_min + x_max) / 2
            nearest = min(
                samples,
                key=lambda sample: abs(date2num(sample[0]) - center),
            )
            voltages = [nearest[1]]

        voltage_scale = 10**self.voltage_precision
        scaled_voltages = [
            int(round(self.rounded_voltage(voltage) * voltage_scale))
            for voltage in voltages
        ]
        min_voltage = min(scaled_voltages) - 1
        max_voltage = max(scaled_voltages) + 1

        locator = MaxNLocator(nbins=6, integer=True)
        tick_values = locator.tick_values(min_voltage, max_voltage)
        tick_steps = [
            right - left
            for left, right in zip(tick_values, tick_values[1:])
            if right > left
        ]
        tick_step = min(tick_steps) if tick_steps else 1
        self.axes.set_ylim(
            min_voltage / voltage_scale,
            max_voltage / voltage_scale,
        )
        self.axes.yaxis.set_major_locator(MultipleLocator(tick_step / voltage_scale))

    def update_history_scrollbar(self):
        bounds = self.store.bounds() if self.store is not None else None
        if bounds is None or self.view_start is None or self.view_end is None:
            self.history_scrollbar.set(0, 1)
            return

        full_start, full_end = date2num(bounds)
        total_span = full_end - full_start
        if total_span <= 0:
            self.history_scrollbar.set(0, 1)
            return
        first = min(max((self.view_start - full_start) / total_span, 0), 1)
        last = min(max((self.view_end - full_start) / total_span, first), 1)
        self.history_scrollbar.set(first, last)

    def on_history_scroll(self, *args):
        if not args or self.store is None or self.view_start is None or self.view_end is None:
            return
        bounds = self.store.bounds()
        if bounds is None:
            return

        full_start, full_end = date2num(bounds)
        total_span = full_end - full_start
        if total_span <= 0:
            return
        view_span = min(self.view_end - self.view_start, total_span)
        maximum_start = full_end - view_span

        if args[0] == "moveto":
            new_start = full_start + float(args[1]) * total_span
        elif args[0] == "scroll":
            amount = int(args[1])
            fraction = 0.9 if args[2] == "pages" else 0.1
            new_start = self.view_start + amount * view_span * fraction
        else:
            return

        self.view_start = min(max(new_start, full_start), maximum_start)
        self.view_end = self.view_start + view_span
        self.user_view_span = view_span
        self.follow_live = self.view_end >= full_end - 1e-10
        if self.history_update_after is not None:
            self.root.after_cancel(self.history_update_after)
        self.history_update_after = self.root.after(250, self.render_pending_history_view)

    def render_history_view(self, event=None):
        if event is not None and event.widget is not self.history_scrollbar:
            return
        if self.history_update_after is not None:
            self.root.after_cancel(self.history_update_after)
            self.history_update_after = None
        self.update_chart()

    def render_pending_history_view(self):
        self.history_update_after = None
        self.update_chart()

    def update_chart(self):
        bounds = self.store.bounds() if self.store is not None else None
        if bounds is None:
            self.samples = []
            self.line.set_data([], [])
            self.axes.set_xlim(0, 1)
            self.axes.set_ylim(0, 1)
            self.view_start = None
            self.view_end = None
        else:
            recent = self.store.recent(1000)
            live_start, live_end = self.chart_time_limits(recent)
            if self.follow_live:
                if self.user_view_span is None:
                    self.view_start, self.view_end = live_start, live_end
                else:
                    self.view_end = live_end
                    self.view_start = live_end - self.user_view_span
            elif self.view_start is None or self.view_end is None:
                self.view_start, self.view_end = live_start, live_end

            self.samples = self.store.plot_range(
                num2date(self.view_start).replace(tzinfo=None),
                num2date(self.view_end).replace(tzinfo=None),
                PLOT_MAX_POINTS,
            )
            timestamps = [sample[0] for sample in self.samples]
            voltages = [self.rounded_voltage(sample[1]) for sample in self.samples]
            self.line.set_data(timestamps, voltages)
            self.axes.set_xlim(self.view_start, self.view_end)
            self.update_voltage_limits(self.samples)
            self.figure.autofmt_xdate()

        voltage_formatter = FormatStrFormatter(f"%.{self.voltage_precision}f")
        self.axes.yaxis.set_major_formatter(voltage_formatter)
        self.canvas.draw()
        self.update_history_scrollbar()
        pointer = getattr(self, "chart_pointer", None)
        if pointer is not None:
            self.update_chart_hover(*pointer)

    def on_chart_motion(self, event):
        if event.inaxes is not self.axes or event.x is None or event.y is None:
            self.chart_pointer = None
            self.hide_chart_annotation()
            return
        self.chart_pointer = (event.x, event.y)
        self.update_chart_hover(*self.chart_pointer)

    def hide_chart_annotation(self):
        if self.annotation.get_visible():
            self.annotation.set_visible(False)
            self.canvas.draw_idle()

    def update_chart_hover(self, x, y):
        if not self.axes.bbox.contains(x, y):
            self.hide_chart_annotation()
            return
        visible = self.samples
        if not visible:
            self.hide_chart_annotation()
            return
        display_points = self.axes.transData.transform(
            [
                (date2num(timestamp), self.rounded_voltage(voltage))
                for timestamp, voltage in visible
            ]
        )
        nearest_index = min(
            range(len(visible)),
            key=lambda index: (display_points[index][0] - x) ** 2
            + (display_points[index][1] - y) ** 2,
        )
        point_x, point_y = display_points[nearest_index]
        if (point_x - x) ** 2 + (point_y - y) ** 2 > 12**2:
            self.hide_chart_annotation()
            return

        timestamp, voltage = visible[nearest_index]
        displayed_voltage = self.rounded_voltage(voltage)
        self.annotation.xy = (date2num(timestamp), displayed_voltage)
        self.annotation.set_text(
            f"{timestamp:%Y-%m-%d %H:%M:%S.%f}"[:-3]
            + f"\n{self.format_voltage(displayed_voltage)} V"
        )
        self.annotation.set_visible(True)
        self.canvas.draw_idle()

    def on_chart_scroll(self, event):
        if event.inaxes is not self.axes or event.xdata is None or self.store is None:
            return
        bounds = self.store.bounds()
        if bounds is None:
            return

        data_start, data_end = date2num(bounds)
        time_padding = max((data_end - data_start) * 0.05, 0.5 / 86400)
        full_min = data_start - time_padding
        full_max = data_end + time_padding
        full_span = full_max - full_min
        current_min, current_max = self.axes.get_xlim()
        current_span = current_max - current_min
        step = getattr(event, "step", 0)
        if not step:
            step = 1 if event.button == "up" else -1
        new_span = min(max(current_span * 0.8**step, 0.1 / 86400), full_span)

        if new_span >= full_span:
            self.view_start, self.view_end = full_min, full_max
            self.user_view_span = full_span
            self.follow_live = True
            self.update_chart()
            return

        anchor_fraction = min(max((event.xdata - current_min) / current_span, 0), 1)
        new_min = event.xdata - anchor_fraction * new_span
        new_max = new_min + new_span
        if new_min < full_min:
            new_max += full_min - new_min
            new_min = full_min
        if new_max > full_max:
            new_min -= new_max - full_max
            new_max = full_max

        self.view_start = new_min
        self.view_end = new_max
        self.user_view_span = new_max - new_min
        self.follow_live = new_max >= full_max - 1e-10
        self.update_chart()

    def save_csv(self):
        path = filedialog.asksaveasfilename(
            title="CSV 파일 저장",
            defaultextension=".csv",
            filetypes=(("CSV 파일", "*.csv"),),
            initialfile=f"Agilent34401A_{datetime.now():%Y%m%d_%H%M%S}.csv",
        )
        if not path:
            return
        self.start_export("CSV", path)

    def save_excel(self):
        path = filedialog.asksaveasfilename(
            title="Excel 파일 저장",
            defaultextension=".xlsx",
            filetypes=(("Excel 파일", "*.xlsx"),),
            initialfile=f"Agilent34401A_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
        )
        if not path:
            return
        self.start_export("Excel", path)

    def start_export(self, kind, output_path):
        if self.store is None or self.sample_count == 0:
            messagebox.showwarning("저장할 데이터 없음", "먼저 전압 측정을 시작하세요.")
            return
        if self.export_worker and self.export_worker.is_alive():
            messagebox.showwarning("저장 중", "진행 중인 파일 저장이 끝날 때까지 기다리세요.")
            return
        try:
            self.store.flush()
        except sqlite3.Error as error:
            messagebox.showerror("기록 저장 오류", f"측정 기록을 확정하지 못했습니다.\n{error}")
            return

        self.csv_button.configure(state=tk.DISABLED)
        self.excel_button.configure(state=tk.DISABLED)
        self.status_var.set(f"{kind} 파일 저장 중...")
        self.export_worker = threading.Thread(
            target=self.export_data,
            args=(kind, self.store.path, output_path),
            daemon=True,
        )
        self.export_worker.start()

    def export_data(self, kind, database_path, output_path):
        try:
            if kind == "CSV":
                MeasurementStore.export_csv(database_path, output_path)
            else:
                MeasurementStore.export_excel(database_path, output_path)
        except (OSError, sqlite3.Error, ValueError) as error:
            self.events.put(("export_done", (kind, output_path, str(error))))
        else:
            self.events.put(("export_done", (kind, output_path, None)))

    def close(self):
        if (self.worker and self.worker.is_alive()) or (
            self.diagnostic_worker and self.diagnostic_worker.is_alive()
        ) or (
            self.export_worker and self.export_worker.is_alive()
        ):
            self.stop_event.set()
            if self.instrument is not None:
                self.disconnect_requested = True
                try:
                    self.instrument.cancel_read()
                except (serial.SerialException, OSError) as error:
                    self.status_var.set(f"COM 응답 대기 종료 중 오류: {error}")
            self.root.after(100, self.close)
            return
        if self.history_update_after is not None:
            self.root.after_cancel(self.history_update_after)
        if self.instrument is not None:
            try:
                self.instrument.close()
            except (serial.SerialException, OSError) as error:
                messagebox.showerror("COM 연결 해제 오류", f"프로그램 종료 전에 COM 포트를 해제하지 못했습니다.\n{error}")
                return
            self.instrument = None
            self.connected_port = None
        if self.store is not None:
            try:
                self.store.close()
            except (OSError, sqlite3.Error) as error:
                messagebox.showerror("기록 저장 오류", f"측정 기록 파일을 닫지 못했습니다.\n{error}")
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    AgilentLogger(root)
    root.mainloop()


if __name__ == "__main__":
    main()
