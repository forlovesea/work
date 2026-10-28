"""Charge/discharge CSV recorder, matching WinForms v3.2.13.

Only completed SNMP cycles may call observe_raw. Qt controls are imported lazily.
"""
import csv
import os
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path


@dataclass(frozen=True)
class Options:
    charge_enabled: bool = True
    charge_amps: Decimal = Decimal('50')
    charge_minutes: int = 10
    discharge_enabled: bool = True
    discharge_percent: Decimal = Decimal('50')
    discharge_minutes: int = 5


@dataclass(frozen=True)
class Sample:
    time: datetime
    system: str
    current: Decimal
    capacity: Decimal
    limit_c: Decimal
    soc: int

    @property
    def maximum(self):
        return (self.capacity * self.limit_c).quantize(Decimal('.1'), rounding=ROUND_FLOOR)


@dataclass
class ActiveEvent:
    id: str
    direction: str
    start: Sample
    last: Sample
    next_at: datetime
    threshold: Decimal
    interval: int


class ChargeDischargeRecorder:
    HEADER = ['이벤트ID', '시스템', '종류', '기록구분', '기록시각', '측정시각',
              '시작시각', '전류[A]', 'SOC[%]', '총용량[Ah]', '시작임계전류[A]', '인터벌[분]', '사유']

    def __init__(self, directory, on_error=None):
        self.path = Path(directory) / '충방전 이벤트 기록.csv'
        self.on_error = on_error or (lambda message: None)
        self.options = Options()
        self.monitoring = True
        self.initialize_threshold = True
        self.active = {}
        self.last_time = None
        self.sample = None
        self.known_maximum = None
        self.blocked = False
        self.status = '충방전 이벤트 기본 사용 · 장비 데이터 수신 대기'

    @property
    def state_text(self):
        if not self.monitoring:
            return '중지'
        if not (self.options.charge_enabled or self.options.discharge_enabled):
            return '미사용'
        if self.sample is None:
            return '데이터 대기'
        for direction in ('방전', '충전'):
            if direction in self.active:
                return direction + ' 기록 중'
        return ('충전 보류 · 방전 감시' if self.options.discharge_enabled else '충전 보류') if self.blocked else '감시 중'

    def _error(self, exc):
        self.monitoring = False
        self.active.clear()
        self.status = '이벤트 저장 오류 · 감시 중지'
        self.on_error('충방전 이벤트 기록 실패: ' + str(exc))

    def _write(self, event, phase, sample, at, reason):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stamp = lambda t: t.isoformat(sep=' ', timespec='milliseconds')
        row = [event.id, sample.system, event.direction, phase, stamp(at), stamp(sample.time),
               stamp(event.start.time), sample.current, sample.soc, sample.capacity,
               event.threshold, event.interval, reason]
        row = ["'" + v if isinstance(v, str) and v[:1] in ('=', '+', '-', '@', '\t', '\r', '\n') else v for v in row]
        # Lock the whole append transaction, including header creation, across processes.
        with self.path.open('a+b') as stream:
            locked = False
            try:
                if os.name == 'nt':
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                stream.seek(0, os.SEEK_END)
                empty = stream.tell() == 0
                import io
                output = io.StringIO(newline='')
                writer = csv.writer(output, quoting=csv.QUOTE_ALL)
                if empty:
                    writer.writerow(self.HEADER)
                writer.writerow(row)
                stream.write(output.getvalue().encode('utf-8-sig' if empty else 'utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
            finally:
                if locked:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def _interrupt(self, reason, at):
        for direction, event in list(self.active.items()):
            self._write(event, '중단', event.last, at, reason + ' · 종료시각 미확정')
            del self.active[direction]

    def invalidate(self, reason='통신 또는 필수 측정값 누락'):
        self.sample = None
        self.last_time = None
        try:
            self._interrupt(reason, datetime.now())
            if self.monitoring:
                self.status = '최신 전류·용량·SOC 수신 대기'
        except Exception as exc:
            self._error(exc)

    def observe_raw(self, success, values, system='', at=None):
        if not success or not isinstance(values, dict):
            self.invalidate()
            return
        root = '1.3.6.1.4.1.2011.6.164.1'
        def integer(suffix):
            value = int(str(values[root + suffix]))
            if value == 2147483647:
                raise ValueError('unavailable')
            return value
        try:
            capacity = Decimal(integer('.17.1.1.7.96')) / 10
            try:
                limit = max(Decimal(0), Decimal(integer('.17.2.1.13.96')) / 100)
            except (KeyError, ValueError, TypeError):
                limit = Decimal(0)
            if capacity > 0 and limit > 0:
                self.known_maximum = (capacity * limit).quantize(Decimal('.1'), rounding=ROUND_FLOOR)
            current = Decimal(integer('.17.1.1.6.96')) / 10
            soc = integer('.17.1.1.8.96')
            if capacity <= 0 or not 0 <= soc <= 100:
                raise ValueError('invalid sample')
        except (KeyError, ValueError, TypeError):
            self.invalidate()
            return
        self.observe(Sample(at or datetime.now(), system, current, capacity, limit, soc))

    def observe(self, sample):
        if self.last_time is not None and sample.time <= self.last_time:
            return
        # Keep current telemetry available for validation even while stopped.
        self.sample = sample
        if sample.maximum >= Decimal('.1'):
            self.known_maximum = sample.maximum
        if not self.monitoring:
            return
        self.last_time = sample.time
        try:
            if self.initialize_threshold and sample.maximum >= Decimal('.1'):
                self.options = replace(self.options, charge_amps=min(self.options.charge_amps, sample.maximum))
                self.initialize_threshold = False
            for direction, event in list(self.active.items()):
                if (direction == '충전' and sample.current <= 0) or (direction == '방전' and sample.current >= 0):
                    reason = '전류 0A' if sample.current == 0 else '전류 방향 전환 (0A 미관측)'
                    self._write(event, '종료', sample, sample.time, reason)
                    del self.active[direction]
            o = self.options
            allowed = o.charge_enabled and o.charge_amps <= sample.maximum
            self.blocked = o.charge_enabled and not allowed
            if not allowed and '충전' in self.active:
                event = self.active['충전']
                self._write(event, '중단', event.last, sample.time, '충전 임계값 상한 변경 · 종료시각 미확정')
                del self.active['충전']
            for direction, enabled, magnitude, threshold, interval in (
                ('충전', allowed, sample.current, o.charge_amps, o.charge_minutes),
                ('방전', o.discharge_enabled, -sample.current, sample.capacity * o.discharge_percent / 100, o.discharge_minutes)):
                if not enabled:
                    continue
                event = self.active.get(direction)
                if event is None:
                    if magnitude < threshold:
                        continue
                    event = ActiveEvent(uuid.uuid4().hex, direction, sample, sample,
                                        sample.time + timedelta(minutes=interval), threshold, interval)
                    self._write(event, '시작', sample, sample.time, '임계전류 이상 감지')
                    self.active[direction] = event
                else:
                    if sample.time >= event.next_at:
                        self._write(event, '인터벌', sample, sample.time, '주기 기록')
                        event.next_at = sample.time + timedelta(minutes=event.interval)
                    event.last = sample
            self.status = '충전 감시 보류: 임계값 상한 확인 후 재설정' if self.blocked else '충방전 이벤트 감시 중'
            for direction in self.active:
                self.status += ' · ' + direction + ' 진행'
        except Exception as exc:
            self._error(exc)

    def configure(self, options):
        if not 1 <= options.discharge_percent <= 90:
            raise ValueError('방전 임계값은 1~90%입니다.')
        if options.charge_amps < Decimal('.1') or options.charge_amps * 10 != int(options.charge_amps * 10):
            raise ValueError('충전 임계값은 0.1A 이상, 0.1A 단위입니다.')
        if any(v not in (5, 10, 15, 20, 25, 30) for v in (options.charge_minutes, options.discharge_minutes)):
            raise ValueError('이벤트 기록 간격은 5분 단위, 5~30분입니다.')
        if (options.charge_enabled or options.discharge_enabled) and self.sample is None:
            raise ValueError('최신 전류·총용량·SOC 수신 후 설정하세요.')
        if options.charge_enabled and options.charge_amps > self.sample.maximum:
            raise ValueError('충전 임계값이 총용량 × 충전전류제한(C) 상한을 초과합니다.')
        self.initialize_threshold = False
        if options == self.options:
            return True
        try:
            self._interrupt('설정 변경', datetime.now())
        except Exception as exc:
            self._error(exc)
            return False
        self.options = options
        self.last_time = None
        self.blocked = False
        if not (options.charge_enabled or options.discharge_enabled):
            self.monitoring = False
        self.status = '충방전 이벤트 감시 중' if self.monitoring else '이벤트 기록 중지 · 시작 버튼으로 재개'
        return True

    def start(self, options):
        if not (options.charge_enabled or options.discharge_enabled):
            raise ValueError('충전 또는 방전 이벤트를 하나 이상 선택하세요.')
        if not self.configure(options):
            return
        self.monitoring = True
        self.last_time = None
        self.observe(self.sample)

    def stop(self, reason='사용자 중지'):
        self.monitoring = False
        try:
            self._interrupt(reason, datetime.now())
            self.status = '이벤트 기록 중지 · 시작 버튼으로 재개'
        except Exception as exc:
            self._error(exc)
        finally:
            self.active.clear()
            self.last_time = None


def add_event_controls(owner, dialog, layout):
    """Add independent event controls below the existing operation recording controls."""
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                                   QCheckBox, QDoubleSpinBox, QComboBox, QPushButton, QMessageBox)
    recorder = owner.get_charge_discharge_recorder()
    panel = QFrame(dialog)
    panel.setStyleSheet('QFrame {background: #ECFDF5; border-radius: 6px;}')
    box = QVBoxLayout(panel)
    heading = QLabel()
    heading.setStyleSheet('font-weight: bold; color: #166534;')
    box.addWidget(heading)
    controls = []
    for name, enabled, threshold, interval, maximum, unit in (
        ('방전', recorder.options.discharge_enabled, recorder.options.discharge_percent, recorder.options.discharge_minutes, 90, '%'),
        ('충전', recorder.options.charge_enabled, recorder.options.charge_amps, recorder.options.charge_minutes, 2147483647, 'A')):
        row = QHBoxLayout()
        check = QCheckBox(name + ' 이벤트 사용')
        check.setChecked(enabled)
        spin = QDoubleSpinBox()
        spin.setDecimals(1 if name == '충전' else 0)
        spin.setRange(.1 if name == '충전' else 1, maximum)
        spin.setSingleStep(.1 if name == '충전' else 1)
        spin.setSuffix(' ' + unit)
        spin.setValue(float(threshold))
        combo = QComboBox()
        for minutes in (5, 10, 15, 20, 25, 30):
            combo.addItem(f'{minutes}분', minutes)
        combo.setCurrentIndex(combo.findData(interval))
        row.addWidget(check)
        row.addWidget(QLabel('시작 임계값'))
        row.addWidget(spin)
        row.addWidget(QLabel('기록 간격'))
        row.addWidget(combo)
        box.addLayout(row)
        controls.append((check, spin, combo))
    limits = QLabel()
    limits.setWordWrap(True)
    box.addWidget(limits)
    status = QLabel()
    status.setWordWrap(True)
    status.setTextFormat(Qt.PlainText)
    box.addWidget(status)
    row = QHBoxLayout()
    action = QPushButton()
    stop = QPushButton('이벤트 기록중지')
    row.addWidget(action)
    row.addWidget(stop)
    row.addStretch()
    box.addLayout(row)
    path = QLabel('이벤트 파일: ' + str(recorder.path))
    path.setTextFormat(Qt.PlainText)
    path.setWordWrap(True)
    box.addWidget(path)
    layout.addWidget(panel)
    loaded = [recorder.options]

    def current():
        d, c = controls
        return Options(c[0].isChecked(), Decimal(str(c[1].value())), c[2].currentData(),
                       d[0].isChecked(), Decimal(str(d[1].value())), d[2].currentData())

    def refresh():
        # Reflect first-connection auto initialization without replacing edited drafts.
        if current() == loaded[0] and loaded[0] != recorder.options:
            controls[1][1].blockSignals(True)
            controls[1][1].setValue(float(recorder.options.charge_amps))
            controls[1][1].blockSignals(False)
            loaded[0] = recorder.options
        for check, spin, combo in controls:
            spin.setEnabled(check.isChecked())
            combo.setEnabled(check.isChecked())
        heading.setText('충방전 이벤트 기록  ·  ' + recorder.state_text)
        maximum = recorder.known_maximum
        # Preserve the draft if the device cap falls; apply validates the current cap.
        limits.setText(('충전 입력 상한: ' + str(maximum) + 'A (총용량 × 충전전류제한(C), 마지막 확인값)' if maximum is not None
                        else '충전 상한 미확인 · 임계값과 간격을 미리 입력할 수 있습니다.') +
                       '\n방전: 총용량 × 1~90% · 적용 시 최신 측정값과 충전 상한을 검증합니다.')
        status.setText(recorder.status + '\n기본값 자동 시작 · 설정 변경 후 적용 · 중지 후 시작으로 재개')
        action.setText('설정 변경 적용' if recorder.monitoring else '이벤트 기록시작')
        action.setEnabled(current() != recorder.options if recorder.monitoring else
                          any(c[0].isChecked() for c in controls))
        stop.setEnabled(recorder.monitoring)

    def apply():
        try:
            if recorder.monitoring:
                if recorder.configure(current()) and recorder.sample is not None:
                    recorder.observe(recorder.sample)
            else:
                recorder.start(current())
            loaded[0] = recorder.options
        except ValueError as exc:
            QMessageBox.warning(dialog, '이벤트 설정 확인', str(exc))
        refresh()

    action.clicked.connect(apply)
    stop.clicked.connect(lambda: (recorder.stop(), refresh()))
    for check, spin, combo in controls:
        check.toggled.connect(refresh)
        spin.valueChanged.connect(refresh)
        combo.currentIndexChanged.connect(refresh)
    timer = QTimer(dialog)
    timer.timeout.connect(refresh)
    timer.start(500)
    dialog.finished.connect(timer.stop)
    refresh()
    return panel
