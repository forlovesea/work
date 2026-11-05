"""End-to-end privacy checks in a temporary copy with a local fake SMTP server.

Usage: python bin/test-contact-privacy.py /path/to/php
No real application data or external email service is used.
"""
import http.cookiejar
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import socket
import socketserver
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse


class MailCapture(socketserver.StreamRequestHandler):
    messages = []

    def handle(self):
        self.wfile.write(b'220 localhost test SMTP\r\n')
        body = []
        in_data = False
        while True:
            line = self.rfile.readline()
            if not line:
                return
            if in_data:
                if line == b'.\r\n':
                    self.messages.append(b''.join(body).decode('utf-8', errors='replace'))
                    self.wfile.write(b'250 captured\r\n')
                    in_data = False
                else:
                    body.append(line)
                continue
            command = line.split(b' ', 1)[0].strip().upper()
            if command == b'DATA':
                in_data = True
                self.wfile.write(b'354 send message\r\n')
            elif command == b'QUIT':
                self.wfile.write(b'221 bye\r\n')
                return
            else:
                self.wfile.write(b'250 OK\r\n')


class Client:
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = ''

    def call(self, path='api.php', payload=None, expected=200, json_response=True):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.base + '/' + path, data=data,
                                        headers={'Content-Type': 'application/json', 'X-CSRF-Token': self.csrf})
        try:
            response = self.opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        body = response.read().decode()
        assert response.status == expected, (response.status, expected, body)
        return json.loads(body) if json_response else body

    def login(self, password):
        result = self.call(payload={'action': 'login', 'password': password})
        self.csrf = result['csrf_token']
        return result


def main():
    php = Path(sys.argv[1]).resolve()
    root = Path(__file__).resolve().parents[1]
    smtp = socketserver.ThreadingTCPServer(('127.0.0.1', 0), MailCapture)
    threading.Thread(target=smtp.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='contact-privacy-test-') as temporary:
        work = Path(temporary)
        shutil.copytree(root / 'public', work / 'public')
        shutil.copytree(root / 'lib', work / 'lib')
        (work / 'data').mkdir()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        env = dict(os.environ, APP_PUBLIC_URL='https://example.invalid', APP_MAIL_FROM='test@example.invalid')
        flags = [str(php)]
        if os.name == 'nt':
            flags += ['-d', 'extension_dir=' + str(php.parent / 'ext'), '-d', 'extension=pdo_sqlite',
                      '-d', 'SMTP=127.0.0.1', '-d', 'smtp_port=' + str(smtp.server_address[1])]
        flags += ['-d', 'session.save_path=' + str(work), '-S', f'127.0.0.1:{port}', '-t', str(work / 'public')]
        with (work / 'server.log').open('w+') as log:
            server = subprocess.Popen(flags, env=env, stdout=log, stderr=log)
            try:
                base = f'http://127.0.0.1:{port}'
                admin = Client(base)
                for attempt in range(50):
                    try:
                        admin.call('api.php?action=session')
                        break
                    except urllib.error.URLError:
                        time.sleep(0.1)
                assert admin.login('jjh1234')['contacts_restricted'] is False
                record = {'visit_date': '2026-11-03', 'device_name': 'Door LCD', 'existing_version': '1',
                          'upgrade_version': '2', 'rack_count': 1, 'module_counts': [1], 'site_name': 'Test',
                          'work_status': '방문예정', 'contacts': [{'name': '홍길동', 'phone': '010-1234-5678'},
                                                               {'name': '김철', 'phone': '02-123-4567'}]}
                record_id = admin.call(payload=record, expected=201)['record_id']
                # Legacy generated notes are hidden without removing user-authored lines.
                with closing(sqlite3.connect(work / 'data' / 'installed-management.sqlite')) as db, db:
                    db.execute('UPDATE records SET notes = ? WHERE id = ?', ['사용자 메모\n[엑셀 임시값] 현장방문날짜: 2026-11-04', record_id])
                assert admin.call()['records'][0]['notes'] == '사용자 메모'
                assert admin.call()['input_history'][0]['notes'] == '사용자 메모'
                popup = admin.call('api.php?action=dashboard_records&device=Door%20LCD&work_status=' + urllib.parse.quote('방문예정'))
                assert popup['records'][0]['existing_version'] == '1'
                assert popup['records'][0]['upgrade_version'] == '2'
                restricted = Client(base)
                assert restricted.login('pantech')['contacts_restricted'] is True
                outsider = Client(base)
                outsider.login('pantech')
                data = restricted.call()
                contacts = data['records'][0]['contacts']
                assert contacts == [{'name': '홍*동', 'phone': '010-****-5678'}, {'name': '김*', 'phone': '02-***-4567'}]
                assert '홍길동' not in json.dumps(data, ensure_ascii=False)
                assert data['input_history'][0]['contacts'] == contacts
                editable = [dict(contact, original_contact=dict(contact, index=index)) for index, contact in enumerate(contacts)]
                restricted.call(payload=dict(record, action='update_record', id=record_id, contacts=editable))
                assert admin.call()['records'][0]['contacts'] == record['contacts']
                changed = [dict(contact) for contact in editable]
                changed[0]['name'] = '이수진'
                changed[1]['phone'] = '02-555-6789'
                restricted.call(payload=dict(record, action='update_record', id=record_id, contacts=changed))
                assert admin.call()['records'][0]['contacts'] == [{'name': '이수진', 'phone': '010-1234-5678'}, {'name': '김철', 'phone': '02-555-6789'}]
                restricted.call(payload=dict(record, action='update_record', id=record_id, contacts=editable), expected=422)
                restricted.call(payload=dict(record, action='update_record', id=record_id, contacts=[{'name': '홍*동', 'phone': '010-****-5678'}]), expected=422)
                restricted.call(payload=dict(record, action='update_record', id=record_id, contacts=[{'name': '새담당', 'phone': '010-9999-0000'}]))
                assert len(admin.call()['records'][0]['contacts']) == 1
                admin.call(payload=dict(record, action='update_record', id=record_id))
                activity = restricted.call('api.php?action=activity')
                assert '홍길동' not in json.dumps(activity, ensure_ascii=False)
                database_path = work / 'data' / 'installed-management.sqlite'

                def request_approval(purpose='view'):
                    with closing(sqlite3.connect(database_path)) as db, db:
                        if db.execute("SELECT name FROM sqlite_master WHERE name='contact_approvals'").fetchone():
                            db.execute('UPDATE contact_approvals SET created_at = created_at - 61')
                    result = restricted.call(payload={'action': 'request_contact_approval', 'purpose': purpose, 'ids': [record_id]})
                    message = MailCapture.messages[-1]
                    assert 'forlovesea@gmail.com' in message
                    link = next(line for line in message.splitlines() if line.startswith('https://'))
                    assert not urlparse(link).query
                    return result['request_id'], parse_qs(urlparse(link).fragment)['token'][0]

                def approve(token):
                    request = urllib.request.Request(base + '/approve-contacts.php', data=('token=' + token).encode(),
                                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
                    with urllib.request.urlopen(request) as response:
                        assert '인증 완료.' in response.read().decode()

                request_id, token = request_approval()
                payload = {'action': 'consume_contact_approval', 'purpose': 'view', 'request_id': request_id}
                restricted.call(payload=payload, expected=403)
                restricted.call('approve-contacts.php?token=' + token, json_response=False)
                restricted.call(payload=payload, expected=403)  # Email scanner GET must not approve.
                inspect = urllib.request.Request(base + '/approve-contacts.php', data=('intent=inspect&token=' + token).encode(),
                                                 headers={'Content-Type': 'application/x-www-form-urlencoded'})
                with urllib.request.urlopen(inspect) as response:
                    assert '인증 완료</button>' in response.read().decode()
                restricted.call(payload=payload, expected=403)  # Fragment preview must not approve either.
                approve(token)
                outsider.call(payload=payload, expected=403)
                restricted.call(payload=dict(payload, purpose='excel'), expected=403)
                assert restricted.call(payload=payload)['records'][0]['contacts'] == record['contacts']
                restricted.call(payload=payload, expected=403)
                assert restricted.call()['records'][0]['contacts'] == contacts
                request_id, token = request_approval('excel')
                approve(token)
                excel = dict(payload, request_id=request_id, purpose='excel')
                assert restricted.call(payload=excel)['records'][0]['contacts'] == record['contacts']
                restricted.call(payload=excel, expected=403)
                request_id, token = request_approval()
                approve(token)
                with closing(sqlite3.connect(database_path)) as db, db:
                    db.execute('UPDATE contact_approvals SET expires_at = 0 WHERE id = ?', [request_id])
                restricted.call(payload=dict(payload, request_id=request_id), expected=403)
                request_id, token = request_approval()
                approve(token)
                admin.call(payload=dict(record, action='update_record', id=record_id, contacts=[{'name': 'Changed', 'phone': '010-1111-2222'}]))
                restricted.call(payload=dict(payload, request_id=request_id), expected=409)
                request_id, token = request_approval()
                approve(token)
                restricted.call(payload={'action': 'logout'})
                restricted.login('pantech')
                restricted.call(payload=dict(payload, request_id=request_id), expected=403)
                print('PASS: API masking, history masking, original preservation, fake email recipient, explicit approval, scope/session/purpose binding, expiry, changed contacts and replay denial')
            except Exception:
                log.flush()
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                server.terminate()
                server.wait(timeout=10)
    smtp.shutdown()
    smtp.server_close()


if __name__ == '__main__':
    main()
