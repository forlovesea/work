"""Qt adapter: snapshots are copied on the UI thread; network runs separately."""
import hashlib
import math
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal, Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
                               QSpinBox, QCheckBox, QMessageBox, QLabel, QTextBrowser,
                               QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QPlainTextEdit)
from upload_transport import Outbox, UploadWorker, destination, envelope, utc_now
from remote_control import apply_charge_limit


def token_visibility_icon(color, visible):
    pixmap = QPixmap(48, 48)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(color, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    eye = QPainterPath()
    eye.moveTo(2, 12)
    eye.cubicTo(7, 4, 17, 4, 22, 12)
    eye.cubicTo(17, 20, 7, 20, 2, 12)
    painter.drawPath(eye)
    painter.drawEllipse(9, 9, 6, 6)
    if not visible:
        painter.drawLine(3, 3, 21, 21)
    painter.end()
    return QIcon(pixmap)


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


MODULE_COMMUNICATION_STATUSES = {
    0: 'Online',
    1: 'Offline',
    2: 'Sleep',
    3: 'Disconnect',
    4: '충전중',
    5: '방전중',
    6: 'Standby',
    255: 'Unknown',
}


def module_communication_status(status):
    if status is None:
        return None
    try:
        code = int(status)
    except (TypeError, ValueError, OverflowError):
        return 'Unknown'
    return MODULE_COMMUNICATION_STATUSES.get(code, 'Unknown')


class UploadController(QObject):
    status = Signal(str)
    upload_result = Signal(object)

    def __init__(self, ui):
        super().__init__(ui)
        self.ui = ui
        self.raw_oids = {}
        self.last_poll_at = None
        self.last_poll_ok = False
        self.last_error = None
        self.last_trap_at = None
        self.storage_error = ''
        self.control_result_lock = threading.Lock()
        self.pending_control_results = []
        self.active_control_commands = set()
        self.history = deque(maxlen=30)
        self.history_dialog = None
        self.history_view = None
        self.connection_state = 'waiting'
        key = hashlib.sha256(str(Path(ui.profile_path).resolve()).encode()).hexdigest()[:20]
        self.outbox = Outbox(Path(__file__).parent / 'data' / (key + '.sqlite3'))
        self.label = QLabel()
        self.status.connect(self.show_status)
        ui.btn_upload_settings.clicked.connect(self.open_settings)
        ui.btn_upload_status.clicked.connect(self.open_history)
        self.upload_result.connect(self.on_upload_result)
        ui.statusBar().addWidget(self.label, 1)
        self.config = self.load_config()
        self.worker = UploadWorker(self.outbox, self.status.emit, self.upload_result.emit)
        self.generation = self.worker.configure(self.config)
        self.worker.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.capture)
        self.apply_timer()

    def show_status(self, text):
        self.label.setText(self.storage_error or text)
        self.label.setToolTip(self.label.text())
        self.update_status_button()

    def update_status_button(self):
        configured = self.config.get('enabled') and all(
            self.config.get(k) for k in ('host', 'token', 'site_id', 'device_id'))
        state = self.connection_state if configured else 'disabled'
        if configured and self.storage_error:
            state = 'failed'
        colors = {
            'disabled': ('#E8ECF1', '#CDD5DF', '#8793A3', '업로드 설정이 없거나 사용하지 않습니다.'),
            'waiting': ('#E8ECF1', '#CDD5DF', '#68788C', '첫 업로드 결과를 기다리는 중입니다.'),
            'failed': ('#F9DEDF', '#E9B8BD', '#A45460', '접속 또는 업로드 실패 · 자동 재시도 중'),
            'success': ('#DDF2E7', '#ACD7C0', '#397A5C', '업로드 정상 · 클릭하면 최근 30건을 확인합니다.'),
        }
        bg, border, fg, tooltip = colors[state]
        button = self.ui.btn_upload_status
        button.setProperty('uploadState', state)
        button.setEnabled(state == 'success')
        button.setCursor(Qt.PointingHandCursor if state == 'success' else Qt.ArrowCursor)
        button.setToolTip(tooltip)
        button.setAccessibleName('업로드 상태: ' + tooltip)
        button.setStyleSheet(f'''
            QPushButton#upload_status {{ background: {bg}; color: {fg};
                border: 1px solid {border}; border-radius: 10px;
                padding: 0px 14px; font-weight: 600; }}
            QPushButton#upload_status:disabled {{ background: {bg}; color: {fg}; }}
            QPushButton#upload_status:hover {{ border: 1px solid {fg}; }}
        ''')
        self.ui.btn_upload_settings.ensurePolished()
        button.setFixedHeight(self.ui.btn_upload_settings.sizeHint().height())

    def on_upload_result(self, event):
        if event['generation'] != self.generation or not self.config.get('enabled'):
            return
        command = event.get('control_command')
        if command:
            self.start_remote_control(command, event)
        self.connection_state = 'success' if event['ok'] else 'failed'
        self.history.appendleft(event)
        self.update_status_button()
        self.refresh_history()

    def start_remote_control(self, command, event):
        command_id = command.get('command_id') if isinstance(command, dict) else None
        if not isinstance(command_id, str) or command_id in self.active_control_commands:
            return
        if (event.get('site_id') != self.config.get('site_id')
                or event.get('device_id') != self.config.get('device_id')):
            return
        ui = self.ui
        try:
            port = int(ui.port_edit.text().strip() or 161)
        except ValueError:
            port = 161
        snmp_config = dict(
            ip=ui.ip_edit.text().strip(),
            port=port,
            get_community=ui.get_comm_edit.text().strip(),
            set_community=ui.set_comm_edit.text().strip(),
        )
        self.active_control_commands.add(command_id)

        def execute():
            try:
                result = apply_charge_limit(snmp_config, command)
            except Exception:
                result = dict(command_id=command_id, status='failed',
                              applied_value_centi=None,
                              message='SNMP 설정 처리 중 예상하지 못한 오류가 발생했습니다.')
            with self.control_result_lock:
                self.pending_control_results.append(result)
            self.active_control_commands.discard(command_id)
            state = '적용 및 확인 완료' if result['status'] == 'succeeded' else '적용 실패'
            self.status.emit('원격 충전전류제한 ' + state + ' · ' + result['message'])

        threading.Thread(target=execute, name='BatteryWatchRemoteControl', daemon=True).start()

    def refresh_history(self):
        if self.history_view is None:
            return
        lines = []
        def local_time(value):
            if not value:
                return '없음'
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError, AttributeError):
                return '시각 형식 오류'
        for event in self.history:
            timestamp = local_time(event['at'])
            result = '성공 (서버 저장 확인)' if event['ok'] else '실패 (' + event['error'] + ')'
            line = (f"전송 {timestamp} | {result} | {event['site_id']}/{event['device_id']} | {event['summary']}"
                    f" | 수집 {local_time(event.get('captured_at'))} | 실제 측정 {local_time(event.get('last_poll_at'))}")
            lines.append(' '.join(line.splitlines()))
        self.history_view.setPlainText('\n'.join(lines))
        self.history_view.verticalScrollBar().setValue(0)

    def open_history(self):
        if not self.ui.btn_upload_status.isEnabled():
            return
        if self.history_dialog is None:
            dialog = QDialog(self.ui)
            dialog.setWindowTitle('업로드 상태 · 최근 전송 기록')
            dialog.resize(940, 520)
            dialog.setStyleSheet('''
                QDialog { background: #F2F7F5; }
                QLabel { color: #4B6B5C; background: transparent; }
                QPlainTextEdit { background: #FFFFFF; color: #385647;
                    border: 1px solid #CFE1D7; border-radius: 10px; padding: 10px; }
                QPushButton { background: #DDF2E7; color: #397A5C;
                    border: 1px solid #ACD7C0; border-radius: 8px; padding: 8px 20px; }
            ''')
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel('최근 전송 결과 30건 · 최신 기록이 맨 위에 실시간 표시됩니다.\n'
                                   '시간은 이 PC의 현지 시각이며, 기록은 프로그램 실행 중에 유지됩니다.\n'
                                   '전송 성공은 서버 저장 확인입니다. 최신 측정 여부는 실제 측정 시각과 측정 성공 상태를 확인하세요.'))
            self.history_view = QPlainTextEdit(dialog)
            self.history_view.setReadOnly(True)
            self.history_view.setLineWrapMode(QPlainTextEdit.NoWrap)
            self.history_view.document().setMaximumBlockCount(30)
            layout.addWidget(self.history_view)
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.button(QDialogButtonBox.Close).setText('닫기')
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            self.history_dialog = dialog
        self.refresh_history()
        self.history_dialog.show()
        self.history_dialog.raise_()
        self.history_dialog.activateWindow()

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
            if key == 'ca_file':
                ca_row = QHBoxLayout()
                ca_row.addWidget(field, 1)
                ca_browse = QPushButton('찾아보기…')
                ca_browse.setObjectName('upload_ca_browse')
                ca_browse.setAutoDefault(False)
                ca_row.addWidget(ca_browse)
                form.addRow(label, ca_row)
            elif key == 'token':
                token_row = QHBoxLayout()
                token_row.addWidget(field, 1)
                token_toggle = QPushButton()
                token_toggle.setObjectName('upload_token_visibility')
                token_toggle.setCheckable(True)
                token_toggle.setAutoDefault(False)
                token_toggle.setFixedSize(36, 32)
                token_toggle.setIconSize(QSize(20, 20))
                token_toggle.setCursor(Qt.PointingHandCursor)
                token_toggle.setStyleSheet('''
                    QPushButton {
                        background: #F2F5FA; border: 1px solid #DCE4EE;
                        border-radius: 9px; padding: 0px;
                    }
                    QPushButton:hover { background: #E7EEF8; border-color: #B6C9E2; }
                    QPushButton:checked { background: #E0F2EE; border-color: #A4CEC3; }
                    QPushButton:checked:hover { background: #D1EAE3; border-color: #86B9AB; }
                    QPushButton:pressed { background: #CEDFEF; }
                    QPushButton:focus { border: 2px solid #7899C3; }
                ''')
                token_row.addWidget(token_toggle)
                form.addRow(label, token_row)
            else:
                form.addRow(label, field)
        def update_token_visibility(visible):
            fields['token'].setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
            token_toggle.setIcon(token_visibility_icon(QColor('#367A69' if visible else '#687C96'), visible))
            description = '토큰 숨기기' if visible else '토큰 보기'
            token_toggle.setToolTip(description)
            token_toggle.setAccessibleName(description)
        token_toggle.toggled.connect(update_token_visibility)
        update_token_visibility(False)
        def browse_ca():
            initial = fields['ca_file'].text().strip() or str(Path(__file__).parent / 'certs')
            filename, _ = QFileDialog.getOpenFileName(
                dialog, 'CA 인증서 파일 선택', initial,
                'PEM 인증서 (*.pem *.crt *.cer);;모든 파일 (*)')
            if filename:
                fields['ca_file'].setText(str(Path(filename).resolve()))
        ca_browse.clicked.connect(browse_ca)
        def update_ca_enabled(enabled):
            fields['ca_file'].setEnabled(enabled)
            ca_browse.setEnabled(enabled)
            form.labelForField(ca_row).setEnabled(enabled)
        fields['tls'].toggled.connect(update_ca_enabled)
        update_ca_enabled(fields['tls'].isChecked())
        note = QLabel('기본 5초. TLS 해제는 신뢰할 수 있는 시험망에서만 사용하세요.\n'
                      '서버·토큰·식별자 변경 전 대기 데이터를 전송하세요.\n'
                      '이전 설정의 대기 데이터는 보존되며 해당 설정 복원 시 재전송됩니다.')
        note.setWordWrap(True); form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('저장')
        buttons.button(QDialogButtonBox.Cancel).setText('취소')
        manual_button = buttons.addButton('설정 매뉴얼', QDialogButtonBox.HelpRole)
        manual_button.setObjectName('upload_manual')
        manual_button.clicked.connect(lambda: self.open_manual(dialog))
        form.addRow(buttons)
        def save():
            config = {k: (v.isChecked() if isinstance(v, QCheckBox) else v.value() if isinstance(v, QSpinBox) else v.text().strip()) for k,v in fields.items()}
            if config['enabled'] and not all(config[k] for k in ('host','token','site_id','device_id')):
                QMessageBox.warning(dialog, '설정 확인', '서버, 토큰, 현장 ID, 장비 ID를 입력하세요.'); return
            if config['tls'] and config['ca_file'] and not Path(config['ca_file']).is_file():
                QMessageBox.warning(dialog, '설정 확인', 'CA 파일을 찾을 수 없습니다.'); return
            for k,v in config.items(): self.ui.settings.setValue('upload/' + k, v)
            self.ui.settings.sync()
            self.config = config
            self.generation = self.worker.configure(config)
            self.connection_state = 'waiting'
            self.apply_timer()
            dialog.accept()
        buttons.accepted.connect(save); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def open_manual(self, parent):
        dialog = QDialog(parent)
        dialog.setWindowTitle('서버 TCP 업로드 설정 매뉴얼')
        dialog.setObjectName('upload_manual_dialog')
        dialog.resize(780, 720)
        dialog.setStyleSheet('''
            QDialog#upload_manual_dialog { background: #F1F5FA; }
            QLabel#manual_title {
                color: #293B55; font-size: 21px; font-weight: 700;
                background: transparent;
            }
            QLabel#manual_subtitle {
                color: #55657A; font-size: 13px; background: transparent;
            }
            QTextBrowser#manual_content {
                background: #FFFFFF; color: #293548;
                border: 1px solid #D9E3EE; border-radius: 12px;
                padding: 8px; selection-background-color: #D7E8FB;
                selection-color: #20354F;
            }
            QTextBrowser#manual_content:focus { border-color: #8AA9CE; }
            QScrollBar:vertical {
                background: #F1F5FA; width: 12px; margin: 4px 1px;
            }
            QScrollBar::handle:vertical {
                background: #B8C9DB; min-height: 36px; border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover { background: #91ABC5; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QPushButton#manual_close {
                color: #304B70; background: #DEEAF9;
                border: 1px solid #B9CFE9; border-radius: 8px;
                padding: 8px 24px; font-size: 14px; font-weight: 600;
            }
            QPushButton#manual_close:hover { background: #CDDEF4; }
            QPushButton#manual_close:pressed { background: #BDD2ED; }
            QPushButton#manual_close:focus { border: 2px solid #688AB6; }
        ''')
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)
        title = QLabel('서버 TCP 업로드 설정 매뉴얼')
        title.setObjectName('manual_title')
        title.setWordWrap(True)
        layout.addWidget(title)
        subtitle = QLabel('설정 순서부터 서버 파일 확인, 연결 문제 해결까지')
        subtitle.setObjectName('manual_subtitle')
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        guide = QTextBrowser(dialog)
        guide.setObjectName('manual_content')
        guide.document().setDocumentMargin(16)
        guide.document().setDefaultStyleSheet('''
            body { font-family: "Malgun Gothic", "Segoe UI", sans-serif; font-size: 11pt; color: #293548; }
            p { margin-top: 10px; margin-bottom: 16px; line-height: 145%; }
            h3 { font-size: 13pt; color: #365A74; background-color: #E7F1F7;
                 margin-top: 26px; margin-bottom: 14px; }
            b { color: #305E65; }
            li { margin-top: 6px; margin-bottom: 8px; line-height: 145%; }
            ul, ol { margin-top: 8px; margin-bottom: 18px; }
        ''')
        guide.setHtml('''
            <p>모니터링 PC에서 수집한 장비 상태와 알람을 BatteryWatch 서버로 보내는 설정입니다.
            Master와 Slave 모드 모두 사용할 수 있습니다.</p>
            <h3>설정 순서</h3>
            <ol>
            <li>서버 관리자에게 TCP 수신 주소·포트, TLS 사용 여부, 수집기 인증 토큰,
            현장 ID와 장비 ID를 받습니다. 사설 인증서를 사용하면 CA 파일도 받습니다.</li>
            <li>아래 설명에 따라 값을 입력하고 ‘업로드 사용’을 체크한 뒤 ‘저장’을 누릅니다.</li>
            <li>메인 화면 하단의 업로드 상태와 ACK를 확인합니다.
            ACK는 서버 저장 완료를 뜻하며, 장비 측정이 정상이라는 뜻은 아닙니다.</li>
            </ol>
            <h3>먼저 실제 서버의 파일을 확인하세요</h3>
            <p>아래 파일은 <b>접속할 실제 서버의 BatteryWatch/server 폴더</b>에서 확인합니다.
            다른 PC에서 별도로 생성한 동명 파일은 토큰이나 설정이 다를 수 있습니다.</p>
            <ul>
            <li><b>client-connection.local.json</b>: 클라이언트 입력용 정보입니다.
            token, site_id, device_id를 확인합니다. host, port, tls, interval도 참고할 수 있지만,
            초기 생성 후 서버 설정 변경이 자동 반영되는 파일은 아니므로 실제 운영 설정과 대조하세요.</li>
            <li><b>server.local.json</b>: 서버 수신 설정과 수집기별 권한입니다.
            서버를 --config 옵션으로 실행했다면 <b>그 옵션에 지정한 파일</b>이 기준입니다.
            예: --config server.public.local.json이면 server.public.local.json을 확인합니다.</li>
            </ul>
            <h3>각 항목 입력 방법</h3>
            <p><b>업로드 사용</b><br>
            체크하면 서버 전송을 시작합니다. 기본값은 꺼짐입니다.
            해제하면 새 업로드 데이터를 쌓지 않으며 기존 전송 대기 데이터는 보존됩니다.</p>
            <p><b>서버 IP / 호스트</b><br>
            BatteryWatch 서버의 IP 또는 도메인만 입력합니다.
            <b>참조: client-connection.local.json → host</b><br>
            안내받은 공인 서버 주소는 <b>61.105.141.21</b>입니다.
            파일에 127.0.0.1이 남아 있다면 원격 접속 시 공인 주소로 바꿔 입력합니다.
            서버 설정의 host=0.0.0.0은 수신 대기 주소이므로 클라이언트 접속 주소로 입력하지 않습니다.<br>
            http://, https://, 경로 또는 :포트는 붙이지 않습니다.
            127.0.0.1은 현재 모니터링 PC 자체이므로 서버가 같은 PC에 있을 때만 사용합니다.</p>
            <p><b>TCP 포트</b><br>
            <b>참조: 실제 서버 설정 파일 → 최상위 port</b>
            (client-connection.local.json의 port와 대조)<br>
            서버의 TCP 수신 포트와 동일하게 입력합니다. 기본값은 9443이며 범위는 1~65535입니다.
            api.port는 앱 조회용이므로 사용하지 않습니다. 포트 포워딩으로 외부 포트가 다르면
            관리자가 안내한 외부 포트를 입력합니다. 서버 방화벽에서도 해당 TCP 포트 접속이 허용되어야 합니다.</p>
            <p><b>업로드 주기 (초)</b><br>
            <b>참조: client-connection.local.json → interval</b> (없으면 기본 5초)<br>
            현재 상태를 전송할 간격입니다. 기본 5초, 설정 범위 1~3600초입니다.
            장비 SNMP 수집 주기는 바뀌지 않습니다.
            알람 발생·복구 Trap은 이 주기를 기다리지 않고 별도로 전송 대기열에 넣습니다.</p>
            <p><b>TLS 암호화 / 인증서 검증</b><br>
            <b>참조: 실제 서버 설정 파일 → tls.certfile, tls.keyfile</b><br>
            서버가 두 파일로 TLS 수신 중이면 체크합니다. 현재 준비한 서버 인증서 설정은
            tls.certfile=certs/server.pem, tls.keyfile=certs/server-key.pem입니다.
            client-connection.local.json의 tls 값도 대조하되 실제 실행 중인 서버 설정이 기준입니다.<br>
            기본값은 켜짐입니다. 서버의 TLS 설정과 맞춰 사용합니다.
            접속 주소는 서버 인증서에 등록된 이름과 일치해야 하며,
            IP로 접속하면 인증서에 해당 IP가 포함되어 있어야 합니다.
            TLS 해제는 신뢰할 수 있는 시험망에서만 사용하세요.</p>
            <p><b>CA 파일 (비우면 시스템 인증서)</b><br>
            <b>받을 파일: 실제 서버 인증서를 발급한 CA의 공개 인증서</b><br>
            이번에 준비한 파일은 서버의 <b>BatteryWatch/server/certs/ca.pem</b>이며,
            클라이언트에는 <b>monitoring-client/certs/batterywatch-ca.pem</b>으로 복사했습니다.
            ‘찾아보기…’를 눌러 이 PC에 있는 파일을 선택하세요.
            client-connection.local.json에 ca_file이 있어도 다른 PC의 경로라면 그대로 사용할 수 없습니다.
            서버의 tls.certfile은 서버 인증서, tls.keyfile은 서버 개인키를 가리키며
            CA 파일 입력란에 개인키를 선택하면 안 됩니다.<br>
            사설 CA를 사용하는 서버라면 이 PC에 저장한 PEM 형식 CA 인증서의 전체 경로를 입력합니다.
            예: C:/BatteryWatch/certs/ca.pem<br>
            비워 두면 시스템의 신뢰 인증서를 사용합니다. TLS를 켰을 때 인증서 검증에 사용됩니다.</p>
            <p><b>업로드 인증 토큰</b><br>
            <b>복사할 값: 실제 서버의 client-connection.local.json → token</b><br>
            서버에서 발급한 수집기용 토큰 원문을 입력합니다.
            server.local.json 등 실제 서버 설정의 collectors 배열에서 해당 수집기의
            token_sha256은 검증용 해시이므로 입력하지 않습니다.
            android-connection.local.json의 token은 앱 조회용이므로 사용하지 않습니다.
            원문 토큰 파일이 없다면 서버 관리자에게 수집기 토큰을 재발급받으세요.
            해시값에서 원문 토큰을 복원할 수는 없습니다.<br>
            토큰은 프로필 설정 파일에 저장되므로 파일을 공유할 때 주의하세요.</p>
            <p><b>현장 ID</b><br>
            <b>복사할 값: client-connection.local.json → site_id</b><br>
            <b>권한 대조: 실제 서버 설정 → collectors 배열의 해당 수집기 → devices 배열 → site_id</b><br>
            서버에서 해당 수집기에 허용한 현장 식별자를 그대로 입력합니다. 예: site-01<br>
            메인 화면의 ‘설치 장소’ 표시 이름과는 별도입니다.</p>
            <p><b>장비 ID</b><br>
            <b>복사할 값: client-connection.local.json → device_id</b><br>
            <b>권한 대조: 실제 서버 설정 → collectors 배열의 해당 수집기 → devices 배열 → device_id</b><br>
            현장 ID와 장비 ID는 같은 devices 항목에 등록된 한 쌍이어야 합니다.<br>
            위 현장에 대해 서버에서 허용한 장비 식별자를 그대로 입력합니다. 예: battery-01<br>
            메인 화면의 ‘축전지명’ 표시 이름과는 별도입니다.</p>
            <h3>저장 후 확인 및 문제 해결</h3>
            <ul>
            <li>접속 실패: 서버 주소·TCP 포트, 서버 실행 여부, 방화벽을 확인합니다.</li>
            <li>인증서 오류: 접속 주소와 인증서의 이름/IP, CA 파일, PC 시간을 확인합니다.</li>
            <li>인증 또는 권한 오류: 수집기 토큰과 허용된 현장 ID·장비 ID 조합을 확인합니다.</li>
            <li>대기 데이터가 계속 증가하면 업로드 상태의 오류를 확인합니다.
            통신이 복구되면 기존 대기 데이터를 순서대로 재전송합니다.</li>
            </ul>
            <p>서버·포트·TLS·CA 파일·토큰·현장 ID·장비 ID 변경 전에는 대기 데이터를 먼저 전송하세요.
            변경 전 설정의 대기 데이터는 보존되며, 해당 설정을 복원하면 재전송됩니다.</p>
            <p>이 매뉴얼을 열거나 닫아도 설정은 저장되지 않습니다.
            설정 창에서 ‘저장’을 눌러야 적용됩니다.</p>
        ''')
        layout.addWidget(guide)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText('닫기')
        buttons.button(QDialogButtonBox.Close).setObjectName('manual_close')
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
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
        if not self.config['enabled']: return False
        try:
            self.outbox.put(destination(self.config), envelope(self.config, kind, plain(data)))
            return True
        except Exception as exc:
            self.storage_error = '데이터 저장 실패 (일부 유실 가능): ' + str(exc)
            self.show_status(self.storage_error)
            return False

    def capture(self):
        u = self.ui
        def table_values(table):
            return [[table.item(r,c).text() if table.item(r,c) else None for c in range(table.columnCount())] for r in range(table.rowCount())]
        def summary_value(label):
            position = getattr(u, 'summary_position_map', {}).get(label)
            if position is None:
                return None
            item = u.summary_table.item(*position)
            return item.text().strip() if item else None
        def alarm_state(label):
            value = summary_value(label)
            if value == '발생':
                return True
            if value == '정상':
                return False
            return None
        def button_number(button, decimals=2):
            try:
                value = float(button.text().strip())
            except (AttributeError, TypeError, ValueError):
                return None
            return round(value, decimals) if math.isfinite(value) else None

        soc_enabled = getattr(u, 'soc_charge_limit_enabled', None)
        soc_value = getattr(u, 'soc_charge_limit_value', None)
        try:
            soc_enabled = int(soc_enabled)
            soc_value = int(soc_value)
        except (TypeError, ValueError):
            soc_enabled = soc_value = None
        soc_supported = (
            True if soc_enabled in (1, 2)
            else False if getattr(u, 'soc_charge_limit_fail_count', 0) >= 2
            else None
        )
        soc_read_ok = soc_enabled in (1, 2) and getattr(u, 'soc_charge_limit_fail_count', 0) == 0
        soc_limit = {
            'supported': soc_supported,
            'enabled': soc_enabled == 2 if soc_read_ok else None,
            'value_percent': soc_value if soc_read_ok and soc_value is not None and 1 <= soc_value <= 100 else None,
        }
        with self.control_result_lock:
            control_results = list(self.pending_control_results)
        module_data = {
            str(row): dict(values, communication_status=module_communication_status(values.get('status')))
            for row, values in u.module_data.items()
        }
        data = {
            'source_version': 'TBC1000B V3.2.6', 'mode': u.mode,
            'site_name': u.site_edit.text(), 'system_name': u.system_edit.text(),
            'connection_system_name': u.connection_system_name_label.text(),
            'equipment_ip': u.ip_edit.text().strip(),
            'connected': bool(u.is_connected), 'last_poll_ok': self.last_poll_ok,
            'last_poll_at': self.last_poll_at, 'last_poll_error': self.last_error,
            'last_trap_at': self.last_trap_at,
            'snmp_fail_count': u.snmp_fail_count, 'snmp_total_fail_count': u.snmp_total_fail_count,
            'raw_oids': self.raw_oids, 'module_map': u.module_map, 'module_data': module_data,
            'row_to_module': u.row_to_module, 'equip_to_module': u.equip_to_module,
            'module_order': u.module_order, 'module_barcodes': u.module_barcodes,
            'active_alarms': u.current_alarm_table, 'faults': u.fault_list,
            'active_fault_keys': u.active_fault_keys, 'total_capacity': u.total_capacity,
            'group_soh': u.group_soh, 'summary_table': table_values(u.summary_table),
            'control_results': control_results,
            'operating_status': {
                'discharge_count': (
                    int(summary_value('방전 횟수'))
                    if summary_value('방전 횟수') and summary_value('방전 횟수').isdigit()
                    else None
                ),
                'charge_cutoff': {
                    'overvoltage': alarm_state('과전압 충전차단'),
                    'high_temperature': alarm_state('고온 충전차단'),
                    'overcurrent': alarm_state('과전류 충전차단'),
                    'breaker_off': alarm_state('차단기 OFF'),
                },
                'charge_current_limit_c': button_number(getattr(u, 'charge_limit_button', None)),
                'soc_charge_limit': soc_limit,
            },
            'module_tables': [table_values(u.module_table_left), table_values(u.module_table_right)],
            'fault_table': table_values(u.fault_table),
            'epo_status': {str(k): v.text() for k,v in u.cutoff_buttons.items()},
        }
        if control_results and self.enqueue('snapshot', data):
            completed = {result['command_id'] for result in control_results}
            with self.control_result_lock:
                self.pending_control_results = [
                    result for result in self.pending_control_results
                    if result['command_id'] not in completed
                ]
        elif not control_results:
            self.enqueue('snapshot', data)

    def close(self):
        self.timer.stop()
        self.worker.stop()
        self.worker.join(timeout=5)
