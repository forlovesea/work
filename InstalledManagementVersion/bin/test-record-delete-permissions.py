"""Check record deletion roles against an isolated PHP server and database.

Usage: python bin/test-record-delete-permissions.py /path/to/php
"""
import os
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error

root = Path(__file__).resolve().parents[1]
Client = runpy.run_path(str(root / 'bin/test-contact-privacy.py'))['Client']
php = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='record-permissions-') as temporary:
    work = Path(temporary)
    for folder in ['public', 'lib']:
        shutil.copytree(root / folder, work / folder)
    (work / 'data').mkdir()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    flags = [str(php)]
    if os.name == 'nt':
        flags += ['-d', 'extension_dir=' + str(php.parent / 'ext'), '-d', 'extension=pdo_sqlite']
    flags += ['-d', 'session.save_path=' + str(work), '-S', f'127.0.0.1:{port}', '-t', str(work / 'public')]
    with (work / 'server.log').open('w+') as log:
        server = subprocess.Popen(flags, stdout=log, stderr=log)
        try:
            client = Client(f'http://127.0.0.1:{port}')
            for attempt in range(50):
                try:
                    assert client.call('api.php?action=session')['can_delete_records'] is False
                    break
                except urllib.error.URLError:
                    time.sleep(0.1)
            assert client.login('pantech')['can_delete_records'] is False
            assert client.call('api.php?action=session')['can_delete_records'] is False
            record = dict(visit_date='2026-11-27', device_name='Door LCD', existing_version='1',
                          upgrade_version='2', rack_count=1, module_counts=[1], work_status='방문예정')
            record_id = client.call(payload=record, expected=201)['record_id']
            client.call(payload=dict(record, action='update_record', id=record_id, upgrade_version='3'))
            assert client.call('api.php?date_mode=all')['records'][0]['upgrade_version'] == '3'
            client.call(payload=dict(record, action='update_record', id=record_id, work_status='작업중'))
            from urllib.parse import quote
            progress_query = 'work_status=' + quote('작업중')
            assert len(client.call('api.php?date_mode=all&' + progress_query)['records']) == 1
            assert client.call('api.php?date_mode=all')['records'][0]['work_status'] == '작업중'
            assert len(client.call('api.php?action=dashboard_records&device=Door%20LCD&' + progress_query)['records']) == 1
            selected = dict(action='delete_selected', record_ids=[record_id])
            filtered = dict(action='delete_filtered', filters={'date_mode': 'all'})
            for payload in [selected, filtered]:
                client.call(payload=payload, expected=403)
                assert len(client.call('api.php?date_mode=all')['records']) == 1
            client.call(payload={'action': 'logout'})
            assert client.login('jjh1234')['can_delete_records'] is True
            assert client.call('api.php?action=session')['can_delete_records'] is True
            assert client.call(payload=selected)['deleted_count'] == 1
            client.call(payload=record, expected=201)
            assert client.call(payload=filtered)['deleted_count'] == 1
            # Changing the primary password does not remove its deletion privilege.
            subprocess.run([str(php), '-r', 'file_put_contents($argv[1], password_hash("test-primary-changed", PASSWORD_DEFAULT));',
                            str(work / 'data/password.hash')], check=True)
            client.call(payload={'action': 'logout'})
            assert client.login('test-primary-changed')['can_delete_records'] is True
            client.call(payload={'action': 'logout'})
            assert client.login('pantech')['can_delete_records'] is False
            client.call(payload=filtered, expected=403)
            print('PASS: secondary create/update allowed, both deletes denied, primary deletes allowed, session and role switching')
        finally:
            server.terminate()
            server.wait(timeout=10)
