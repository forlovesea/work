"""Huawei single-battery Modbus RTU monitor (read-only)."""
import sys
import time
import struct
from datetime import datetime

import serial
import serial.tools.list_ports
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QGroupBox, QPlainTextEdit, QSplitter,
    QScrollArea,
)

def count_crc(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


# ============================
# Modbus RTU Frame 생성
# ============================
def build_modbus_frame(slave_id, function, start_addr, count):
    frame = bytearray()
    frame.append(slave_id)
    frame.append(function)
    frame.append((start_addr >> 8) & 0xFF)
    frame.append(start_addr & 0xFF)
    frame.append((count >> 8) & 0xFF)
    frame.append(count & 0xFF)

    crc = count_crc(frame)
    frame.append(crc & 0xFF)        # CRC Low
    frame.append((crc >> 8) & 0xFF) # CRC High
    return frame


class ModbusReadError(Exception):
    """Invalid, missing or exception response; never decode as measurements."""


class ModbusMaster:
    def __init__(self, port, baudrate=9600, slave_id=33):
        self.port = port
        self.baudrate = baudrate
        self.slave_id = slave_id
        self.client = None
        self.silent_interval = max(0.00175, 3.5 * 11 / baudrate)
        self.next_tx = 0.0
        self.recover = False

    def connect(self):
        self.client = serial.Serial(self.port, self.baudrate, timeout=0.02,
                                    write_timeout=0.5, bytesize=8, parity='N', stopbits=1)
        self.client.reset_input_buffer()
        return self.client.is_open

    def close(self):
        if self.client:
            self.client.close()

    def send_raw(self, frame, cancelled=lambda: False, trace=None):
        # One outstanding RTU request. After a failed request discard late bytes
        # before sending again (RTU responses do not contain the register address).
        while time.monotonic() < self.next_tx:
            if cancelled():
                return b''
            if self.recover:
                self.client.read(self.client.in_waiting or 1)
            else:
                time.sleep(min(0.005, max(0, self.next_tx - time.monotonic())))
        if cancelled():
            return b''
        self.client.reset_input_buffer()
        self.recover = False
        count = struct.unpack('>H', frame[4:6])[0]
        expected = 5 + 2 * count
        # Allow device processing time plus the response's wire time at this baud.
        response_timeout = 0.3 + (expected + len(frame)) * 11 / self.baudrate
        if trace:
            trace('TX', frame)
        if self.client.write(frame) != len(frame):
            raise serial.SerialException('Incomplete serial write')
        deadline = time.monotonic() + response_timeout
        received = bytearray()
        try:
            while time.monotonic() < deadline and not cancelled():
                received.extend(self.client.read(self.client.in_waiting or 1))
                # Search all offsets: noise or a corrupt header must not hide a
                # complete, valid frame received later in the same transaction.
                for offset in range(max(0, len(received) - 2)):
                    candidate = received[offset:]
                    if candidate[0] != self.slave_id:
                        continue
                    if candidate[1] == 0x83:
                        size = 5
                    elif candidate[1] == 0x03 and candidate[2] == count * 2:
                        size = expected
                    else:
                        continue
                    if len(candidate) < size:
                        continue
                    packet = bytes(candidate[:size])
                    if count_crc(packet[:-2]) != int.from_bytes(packet[-2:], 'little'):
                        continue
                    if trace:
                        trace('RX', packet)
                    if packet[1] == 0x83:
                        raise ModbusReadError(f'Modbus exception 0x{packet[2]:02X}')
                    return packet
                if len(received) > 1024:
                    del received[:-256]
            if cancelled():
                return b''
            if trace and received:
                trace('RX invalid', bytes(received))
            raise ModbusReadError('Response timeout / invalid address, length or CRC')
        except ModbusReadError:
            self.recover = True
            raise
        finally:
            self.next_tx = time.monotonic() + (response_timeout if self.recover else self.silent_interval)


class PollWorker(QThread):
    connected = Signal()
    reading = Signal(str, object)
    activity = Signal(str)
    frame_log = Signal(str)
    cycle = Signal(float)
    error = Signal(str)

    # Preserve the addresses, widths, signedness and scale of the Huawei V12.
    REGISTERS = (
        ('temperature', 0xA706, 1, '>h', 1),
        ('voltage', 0xA731, 2, '>I', 10),
        ('current', 0xA733, 2, '>i', 10),
        ('soc', 0xA739, 1, '>H', 1),
    )

    def __init__(self, port, baudrate=9600, slave_id=0x21):
        super().__init__()
        self.port, self.baudrate, self.slave_id = port, baudrate, slave_id
        self.log_enabled = True

    def stop(self):
        self.requestInterruption()

    def trace(self, direction, data):
        if direction in ('TX', 'RX'):
            self.activity.emit(direction)
        if self.log_enabled:
            self.frame_log.emit(f'[{direction}] {data.hex(" ").upper()}')

    def poll_once(self, master):
        for name, address, count, fmt, scale in self.REGISTERS:
            if self.isInterruptionRequested():
                break
            try:
                response = master.send_raw(
                    build_modbus_frame(self.slave_id, 3, address, count),
                    self.isInterruptionRequested, self.trace)
                if response:
                    self.reading.emit(name, struct.unpack(fmt, response[3:-2])[0] / scale)
            except ModbusReadError as exc:
                self.reading.emit(name, None)
                self.frame_log.emit(f'[READ FAIL 0x{address:04X}] {exc}')

    def run(self):
        master = ModbusMaster(self.port, self.baudrate, self.slave_id)
        try:
            master.connect()
            self.connected.emit()
            while not self.isInterruptionRequested():
                started = time.monotonic()
                self.poll_once(master)
                self.cycle.emit(time.monotonic() - started)
                # Keep a one-second target scan period with interruptible waits.
                while not self.isInterruptionRequested() and time.monotonic() - started < 1:
                    self.msleep(20)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            master.close()


class BMSMonitor(QWidget):
    FIELDS = (
        ('temperature', 'Battery Temperature', '\u00b0C', 'lbl_temp'),
        ('voltage', 'Battery Voltage', 'V', 'lbl_voltage'),
        ('current', 'Battery Current', 'A', 'lbl_current'),
        ('soc', 'SOC', '%', 'lbl_soc'),
    )

    def __init__(self):
        super().__init__()
        self.worker = None
        self.is_connected = False
        self.closing = False
        self.last_error = ''
        self.activity_at = {}
        self.activity_pending = set()
        self.values = {}
        self.valid = {}
        self.received_at = {}
        self.setWindowTitle('Huawei Single Battery Modbus Monitor')
        self.resize(1100, 720)
        self.build_ui()
        self.refresh_ports()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_leds)
        self.timer.start(20)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(1000)
        self.refresh_leds()
        self.refresh_status()

    def build_ui(self):
        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.cmb_port = QComboBox()
        self.cmb_port.setEditable(True)
        self.btn_refresh = QPushButton('Refresh')
        self.btn_refresh.clicked.connect(self.refresh_ports)
        self.cmb_baud = QComboBox()
        self.cmb_baud.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.spin_slave = QSpinBox()
        self.spin_slave.setRange(1, 247)
        self.spin_slave.setValue(33)
        self.btn_connect = QPushButton('Connect')
        self.btn_connect.clicked.connect(self.toggle_connection)
        self.btn_connect.setStyleSheet('background: #198754; color: white;')
        for label, widget in [('Port', self.cmb_port), ('Baud', self.cmb_baud), ('Slave ID', self.spin_slave)]:
            controls.addWidget(QLabel(label))
            controls.addWidget(widget)
        controls.addWidget(self.btn_refresh)
        controls.addWidget(self.btn_connect)
        controls.addStretch()
        root.addLayout(controls)
        self.lbl_connection = QLabel('Disconnected')
        root.addWidget(self.lbl_connection)
        splitter = QSplitter(Qt.Horizontal)
        logs = QWidget()
        log_layout = QVBoxLayout(logs)
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel('TX / RX Frame'))
        self.btn_log = QPushButton('Pause Log')
        self.btn_log.setCheckable(True)
        self.btn_log.toggled.connect(self.toggle_log)
        clear = QPushButton('Clear')
        log_header.addWidget(self.btn_log)
        log_header.addWidget(clear)
        log_layout.addLayout(log_header)
        self.text_frame = QPlainTextEdit()
        self.text_frame.setReadOnly(True)
        self.text_frame.setMaximumBlockCount(1500)
        self.text_frame.setStyleSheet('font-family: Consolas; font-size: 11px;')
        clear.clicked.connect(self.text_frame.clear)
        log_layout.addWidget(self.text_frame)
        splitter.addWidget(logs)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        header = QHBoxLayout()
        title = QLabel('Battery Information')
        title.setStyleSheet('font-size: 18px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()
        self.activity_leds = {}
        for direction in ('TX', 'RX'):
            header.addWidget(QLabel(f'{direction}:'))
            led = QLabel()
            led.setFixedSize(24, 12)
            led.setToolTip(f'{direction} serial activity')
            header.addWidget(led)
            self.activity_leds[direction] = led
        layout.addLayout(header)
        box = QGroupBox('Huawei Battery')
        form = QFormLayout(box)
        self.field_labels = {}
        for name, caption, unit, attribute in self.FIELDS:
            value = QLabel(f'-- {unit}')
            value.setStyleSheet('font-size: 25px; font-weight: bold; padding: 12px;')
            setattr(self, attribute, value)
            self.field_labels[name] = value
            form.addRow(caption, value)
        layout.addWidget(box)
        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)
        self.lbl_cycle = QLabel('Scan: --')
        layout.addWidget(self.lbl_cycle)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        splitter.addWidget(scroll)
        splitter.setSizes([450, 650])
        root.addWidget(splitter, 1)
        self.setStyleSheet('QWidget { font-family: "Malgun Gothic"; font-size: 13px; } '
                          'QPushButton { padding: 7px; } QGroupBox { margin-top: 10px; }')

    def refresh_ports(self):
        current = self.cmb_port.currentText()
        self.cmb_port.clear()
        self.cmb_port.addItems([p.device for p in serial.tools.list_ports.comports()])
        if current:
            self.cmb_port.setCurrentText(current)

    def toggle_connection(self):
        if self.worker:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        if self.worker:
            return
        port = self.cmb_port.currentText().strip()
        if not port:
            self.lbl_connection.setText('Select a serial port first')
            return
        self.last_error = ''
        self.values.clear()
        self.valid.clear()
        self.received_at.clear()
        self.activity_at.clear()
        self.activity_pending.clear()
        self.lbl_cycle.setText('Scan: --')
        self.refresh_status()
        self.worker = PollWorker(port, int(self.cmb_baud.currentText()), self.spin_slave.value())
        self.worker.log_enabled = not self.btn_log.isChecked()
        self.worker.connected.connect(self.on_connected)
        self.worker.reading.connect(self.on_reading)
        self.worker.activity.connect(self.on_activity)
        self.worker.frame_log.connect(self.append_log)
        self.worker.cycle.connect(lambda seconds: self.lbl_cycle.setText(f'Scan: {seconds:.2f}s'))
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.set_controls_enabled(False)
        self.btn_connect.setEnabled(False)
        self.lbl_connection.setText('Connecting...')
        self.worker.start()

    def set_controls_enabled(self, enabled):
        for widget in (self.cmb_port, self.cmb_baud, self.spin_slave, self.btn_refresh):
            widget.setEnabled(enabled)

    def on_connected(self):
        self.is_connected = True
        self.lbl_connection.setText('Connected')
        self.btn_connect.setText('Disconnect')
        self.btn_connect.setEnabled(True)
        self.btn_connect.setStyleSheet('background: #dc3545; color: white;')
        self.refresh_status()

    def disconnect_serial(self):
        if self.worker:
            self.btn_connect.setEnabled(False)
            self.lbl_connection.setText('Disconnecting...')
            self.worker.stop()

    def on_error(self, message):
        self.last_error = message
        self.append_log(f'[ERROR] {message}')

    def on_finished(self):
        worker, self.worker = self.worker, None
        self.is_connected = False
        self.activity_at.clear()
        self.activity_pending.clear()
        self.refresh_leds()
        self.refresh_status()
        self.lbl_connection.setText(f'Disconnected: {self.last_error}' if self.last_error else 'Disconnected')
        self.btn_connect.setText('Connect')
        self.btn_connect.setStyleSheet('background: #198754; color: white;')
        self.btn_connect.setEnabled(True)
        self.set_controls_enabled(True)
        if worker:
            worker.deleteLater()
        if self.closing:
            self.close()

    def on_reading(self, name, value):
        self.valid[name] = value is not None
        if value is not None:
            self.values[name] = value
            self.received_at[name] = time.monotonic()
        self.refresh_status()

    def refresh_status(self):
        stale = []
        now = time.monotonic()
        for name, caption, unit, _ in self.FIELDS:
            value = self.values.get(name)
            good = self.is_connected and self.valid.get(name, False) and now - self.received_at.get(name, 0) <= 10
            if not good:
                stale.append(caption)
            label = self.field_labels[name]
            text = '--' if value is None else (f'{value:.1f}' if name in ('voltage', 'current') else f'{value:.0f}')
            label.setText(f'{text} {unit}' + (' (previous)' if value is not None and not good else ''))
            color = '#198754' if good else '#6b7280'
            label.setStyleSheet(f'font-size: 25px; font-weight: bold; padding: 12px; color: {color};')
        if not self.is_connected:
            status = 'Disconnected' + (' / previous readings' if self.values else '')
        elif stale:
            status = 'Waiting / read failed / stale: ' + ', '.join(stale)
        else:
            status = 'Receiving normally'
        self.lbl_status.setText(status)

    def on_activity(self, direction):
        if self.is_connected and direction in self.activity_leds:
            self.activity_pending.add(direction)
            self.refresh_leds()

    def refresh_leds(self):
        now = time.monotonic()
        for direction, led in self.activity_leds.items():
            elapsed = now - self.activity_at.get(direction, float('-inf'))
            if self.is_connected and elapsed >= 0.18 and direction in self.activity_pending:
                self.activity_pending.discard(direction)
                self.activity_at[direction] = now
                elapsed = 0
            active = self.is_connected and elapsed < 0.10
            color = '#198754' if active else '#9ca3af'
            led.setStyleSheet(f'background: {color}; border: 1px solid #6b7280; border-radius: 4px;')
            led.setAccessibleName(f'{direction}: {"active" if active else "idle"}')

    def toggle_log(self, paused):
        self.btn_log.setText('Resume Log' if paused else 'Pause Log')
        if self.worker:
            self.worker.log_enabled = not paused

    def append_log(self, text):
        if not self.btn_log.isChecked():
            self.text_frame.appendPlainText(f'{datetime.now():%H:%M:%S} {text}')

    def closeEvent(self, event):
        if self.worker:
            self.closing = True
            self.disconnect_serial()
            event.ignore()
        else:
            event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = BMSMonitor()
    window.show()
    sys.exit(app.exec())
