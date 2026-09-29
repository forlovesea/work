"""Qt adapter: snapshots are copied on the UI thread; network runs separately."""
import hashlib
import math
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
                               QSpinBox, QCheckBox, QMessageBox, QPushButton, QLabel)
from upload_transport import Outbox, UploadWorker, destination, envelope, utc_now


def plain(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [plain(v) for v in value]
    return str(value)


class UploadController(QObject):
    status = Signal(str)

    def __init__(self, ui):
        super().__init__(ui)
        self.ui = ui
        self.raw_oids = {}
        self.last_poll_at = None
        self.last_poll_ok = False
        self.last_error = None
        self.last_trap_at = None
        self.storage_error = ''
        key = hashlib.sha256(str(Path(ui.profile_path).resolve()).encode()).hexdigest()[:20]
        self.outbox = Outbox(Path(__file__).parent / 'data' / (key + '.sqlite3'))
        self.label = QLabel()
        self.status.connect(self.show_status)
        button = QPushButton('서버 TCP 업로드 설정')
        button.clicked.connect(self.open_settings)
        ui.statusBar().addPermanentWidget(button)
        ui.statusBar().addWidget(self.label, 1)
        self.config = self.load_config()
        self.worker = UploadWorker(self.outbox, self.status.emit)
        self.worker.configure(self.config)
        self.worker.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.capture)
        self.apply_timer()

    def show_status(self, text):
        self.label.setText(self.storage_error or text)
        self.label.setToolTip(self.label.text())

    def load_config(self):
        s = self.ui.settings
        return dict(enabled=s.value('upload/enabled', False, type=bool),
                    host=s.value('upload/host', ''), port=s.value('upload/port', 9443, type=int),
                    interval=max(1, min(3600, s.value('upload/interval', 5, type=int))),
                    tls=s.value('upload/tls', True, type=bool), ca_file=s.value('upload/ca_file', ''),
                    token=s.value('upload/token', ''), site_id=s.value('upload/site_id', ''),
                    device_id=s.value('upload/device_id', ''))

    def apply_timer(self):
        self.timer.stop()
        if self.config['enabled']:
            self.timer.start(self.config['interval'] * 1000)
        self.show_status(('업로드 대기' if self.config['enabled'] else '업로드 사용 안 함') +
                         f" | 주기 {self.config['interval']}초 | 전체 대기 {self.outbox.count()}건")

    def open_settings(self):
        dialog = QDialog(self.ui)
        dialog.setWindowTitle('BatteryWatch 서버 TCP 업로드')
        form = QFormLayout(dialog)
        fields = {}
        for key, label in [('enabled', '업로드 사용'), ('host', '서버 IP / 호스트'),
                           ('port', 'TCP 포트'), ('interval', '업로드 주기 (초)'),
                           ('tls', 'TLS 암호화 / 인증서 검증'), ('ca_file', 'CA 파일 (비우면 시스템 인증서)'),
                           ('token', '업로드 인증 토큰'), ('site_id', '현장 ID'), ('device_id', '장비 ID')]:
            if key in ('enabled', 'tls'):
                field = QCheckBox(); field.setChecked(self.config[key])
            elif key in ('port', 'interval'):
                field = QSpinBox(); field.setRange(1, 65535 if key == 'port' else 3600); field.setValue(self.config[key])
            else:
                field = QLineEdit(str(self.config[key]))
                if key == 'token': field.setEchoMode(QLineEdit.Password)
            field.setObjectName('upload_' + key)
            fields[key] = field
            form.addRow(label, field)
        note = QLabel('기본 5초. TLS 해제는 신뢰할 수 있는 시험망에서만 사용하세요.\n'
                      '서버·토큰·식별자 변경 전 대기 데이터를 전송하세요.\n'
                      '이전 설정의 대기 데이터는 보존되며 해당 설정 복원 시 재전송됩니다.')
        note.setWordWrap(True); form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        form.addRow(buttons)
        def save():
            config = {k: (v.isChecked() if isinstance(v, QCheckBox) else v.value() if isinstance(v, QSpinBox) else v.text().strip()) for k,v in fields.items()}
            if config['enabled'] and not all(config[k] for k in ('host','token','site_id','device_id')):
                QMessageBox.warning(dialog, '설정 확인', '서버, 토큰, 현장 ID, 장비 ID를 입력하세요.'); return
            if config['ca_file'] and not Path(config['ca_file']).is_file():
                QMessageBox.warning(dialog, '설정 확인', 'CA 파일을 찾을 수 없습니다.'); return
            for k,v in config.items(): self.ui.settings.setValue('upload/' + k, v)
            self.ui.settings.sync()
            self.config = config
            self.worker.configure(config)
            self.apply_timer()
            dialog.accept()
        buttons.accepted.connect(save); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def poll(self, success, value):
        self.last_poll_ok = bool(success)
        if success and isinstance(value, dict):
            self.raw_oids = plain(value)
            self.last_poll_at = utc_now()
            self.last_error = None
        elif not success:
            self.last_error = str(value)

    def trap(self, data):
        # Persist every received trap separately: occurrence/recovery between ticks survives.
        self.last_trap_at = utc_now()
        self.enqueue('trap', {'received_at': self.last_trap_at, 'raw_trap': plain(data),
                              'monitored_ip': self.ui.ip_edit.text().strip()})

    def enqueue(self, kind, data):
        if not self.config['enabled']: return
        try:
            self.outbox.put(destination(self.config), envelope(self.config, kind, plain(data)))
        except Exception as exc:
            self.storage_error = '데이터 저장 실패 (일부 유실 가능): ' + str(exc)
            self.show_status(self.storage_error)

    def capture(self):
        u = self.ui
        def table_values(table):
            return [[table.item(r,c).text() if table.item(r,c) else None for c in range(table.columnCount())] for r in range(table.rowCount())]
        data = {
            'source_version': 'TBC1000B V3.2.6', 'mode': u.mode,
            'site_name': u.site_edit.text(), 'system_name': u.system_edit.text(),
            'connection_system_name': u.connection_system_name_label.text(),
            'equipment_ip': u.ip_edit.text().strip(),
            'connected': bool(u.is_connected), 'last_poll_ok': self.last_poll_ok,
            'last_poll_at': self.last_poll_at, 'last_poll_error': self.last_error,
            'last_trap_at': self.last_trap_at,
            'snmp_fail_count': u.snmp_fail_count, 'snmp_total_fail_count': u.snmp_total_fail_count,
            'raw_oids': self.raw_oids, 'module_map': u.module_map, 'module_data': u.module_data,
            'row_to_module': u.row_to_module, 'equip_to_module': u.equip_to_module,
            'module_order': u.module_order, 'module_barcodes': u.module_barcodes,
            'active_alarms': u.current_alarm_table, 'faults': u.fault_list,
            'active_fault_keys': u.active_fault_keys, 'total_capacity': u.total_capacity,
            'group_soh': u.group_soh, 'summary_table': table_values(u.summary_table),
            'module_tables': [table_values(u.module_table_left), table_values(u.module_table_right)],
            'fault_table': table_values(u.fault_table),
            'epo_status': {str(k): v.text() for k,v in u.cutoff_buttons.items()},
        }
        self.enqueue('snapshot', data)

    def close(self):
        self.timer.stop()
        self.worker.stop()
        self.worker.join(timeout=5)
