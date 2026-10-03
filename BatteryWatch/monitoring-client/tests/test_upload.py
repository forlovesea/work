import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from upload_transport import Outbox, UploadWorker, destination, envelope, encode_frame, receive_frame
from test_receiver import Receiver


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = dict(enabled=True, host='127.0.0.1', port=9443, tls=False,
                           token='local-test', ca_file='', site_id='s1', device_id='d1')

    def tearDown(self):
        self.temp.cleanup()

    def test_fragmented_frames_and_length_limit(self):
        a,b = socket.socketpair()
        self.addCleanup(a.close); self.addCleanup(b.close)
        frame = encode_frame({'text':'축전지', 'number':42})
        def send():
            for byte in frame: a.sendall(bytes([byte]))
        thread = threading.Thread(target=send); thread.start()
        self.assertEqual(receive_frame(b)['number'],42)
        thread.join()
        a.sendall(b'\xff\xff\xff\xff')
        with self.assertRaises(ValueError): receive_frame(b)

    def test_successful_upload_keeps_old_measurement_time_visible(self):
        payload = envelope(self.config, 'snapshot', {
            'connected': True, 'last_poll_ok': False,
            'last_poll_at': '2026-10-01T07:00:00+00:00',
        })
        payload['captured_at'] = '2026-10-01T07:00:05+00:00'
        event = UploadWorker.result_event(1, payload, True)
        self.assertTrue(event['ok'])
        self.assertEqual(event['last_poll_at'], payload['data']['last_poll_at'])
        self.assertEqual(event['captured_at'], payload['captured_at'])
        self.assertIn('측정 실패/대기', event['summary'])
        self.assertNotIn('token', event)

    def test_upload_ack_passes_remote_command_to_client_handler(self):
        from upload_transport import UploadWorker
        command={'command_id':'12345678-1234-4234-8234-123456789abc',
                 'action':'charge_current_limit','value_centi':75}
        payload=envelope(self.config,'snapshot',{'connected':True})
        event=UploadWorker.result_event(1,payload,True,control_command=command)
        self.assertEqual(event['control_command'],command)

    def test_remote_charge_limit_rejects_unapproved_command_values(self):
        from remote_control import apply_charge_limit
        result=apply_charge_limit({},{
            'command_id':'12345678-1234-4234-8234-123456789abc',
            'action':'charge_current_limit','value_centi':101,
        })
        self.assertEqual(result['status'],'failed')
        self.assertIsNone(result['applied_value_centi'])

    def test_persistence_route_isolation_and_capacity(self):
        box = Outbox(self.root/'outbox.db', max_bytes=1000)
        payload = envelope(self.config,'trap',{'alarm':'raised'})
        route = destination(self.config)
        box.put(route,payload)
        box = Outbox(self.root/'outbox.db', max_bytes=1000)
        self.assertEqual(box.peek(route)[0],payload['sample_id'])
        self.assertIsNone(box.peek(destination(dict(self.config,host='other'))))
        with self.assertRaises(RuntimeError):
            box.put(route,envelope(self.config,'snapshot',{'large':'x'*2000}))
        self.assertEqual(box.count(),1)

    def test_ack_retry_and_deduplication(self):
        server = Receiver(('127.0.0.1',0),self.root/'received.db','local-test')
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        self.addCleanup(server.shutdown)
        self.config['port'] = server.server_address[1]
        payload = envelope(self.config,'snapshot',{'soc':80})
        # Server commits, but client loses ACK; same ID must be accepted on retry.
        with socket.create_connection(server.server_address) as sock:
            sock.sendall(encode_frame(dict(type='upload', token='local-test',payload=payload)))
            self.assertTrue(receive_frame(sock)['ok'])
        box = Outbox(self.root/'queue.db'); box.put(destination(self.config),payload)
        worker = UploadWorker(box,lambda text: None); worker.configure(self.config); worker.start()
        try:
            deadline = time.monotonic()+5
            while box.count() and time.monotonic()<deadline: time.sleep(.02)
            self.assertEqual(box.count(),0)
            with sqlite3.connect(server.database) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM samples').fetchone()[0],1)
        finally:
            worker.stop(); worker.join(5)
        self.assertFalse(worker.is_alive())

    def test_bad_ack_preserves_queue(self):
        listener=socket.socket(); listener.bind(('127.0.0.1',0)); listener.listen()
        self.addCleanup(listener.close)
        self.config['port']=listener.getsockname()[1]
        def reject():
            conn,_=listener.accept()
            with conn:
                receive_frame(conn)
                conn.sendall(encode_frame({'type':'ack','sample_id':'wrong','ok':True}))
        thread=threading.Thread(target=reject,daemon=True); thread.start()
        box=Outbox(self.root/'queue.db'); box.put(destination(self.config),envelope(self.config,'trap',{}))
        failed=threading.Event()
        worker=UploadWorker(box,lambda text: failed.set()); worker.configure(self.config); worker.start()
        try:
            self.assertTrue(failed.wait(5)); self.assertEqual(box.count(),1)
        finally:
            worker.stop(); worker.join(5)
        thread.join(2)

    def test_gui_snapshot_and_fast_alarm_recovery(self):
        from PySide6.QtWidgets import QApplication, QDialog, QSpinBox, QDialogButtonBox
        from PySide6.QtCore import QSettings, QTimer
        import monitor
        app=QApplication.instance() or QApplication([])
        profile=self.root/'test.ini'
        settings=QSettings(str(profile),QSettings.IniFormat)
        settings.setValue('site','test'); settings.sync()
        ui=monitor.BatteryMonitorUI(str(profile),'Slave',forced_slave=True)
        controller=ui.upload_controller
        original_queue=Path(controller.outbox.path)
        try:
            self.assertEqual(controller.config['interval'],5)
            def edit_settings():
                dialog=ui.findChild(QDialog)
                dialog.findChild(QSpinBox,'upload_interval').setValue(12)
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click()
            QTimer.singleShot(0,edit_settings)
            controller.open_settings()
            self.assertEqual(controller.load_config()['interval'],12)
            saved=QSettings(str(profile),QSettings.IniFormat)
            self.assertEqual(saved.value('upload/interval',type=int),12)
            controller.worker.stop(); controller.worker.join(5)
            controller.outbox=Outbox(self.root/'ui.db')
            controller.config=dict(self.config, interval=5)
            ui.module_data={'1':{'soc':83,'cells':[3.2,3.3],'temps':[24,25]}}
            controller.poll(True,{'1.2.3':'raw'})
            controller.trap({'alarm':'raised','_source_ip':'10.0.0.1'})
            controller.trap({'alarm':'recovered','_source_ip':'10.0.0.1'})
            ui.update_summary_value('방전 횟수','17')
            ui.set_summary_alarm('과전압 충전차단',True)
            ui.set_summary_alarm('고온 충전차단',False)
            ui.set_summary_alarm('과전류 충전차단',False)
            ui.set_summary_alarm('차단기 OFF',True)
            ui.charge_limit_button.setText('0.45')
            ui.soc_charge_limit_enabled=2
            ui.soc_charge_limit_value=90
            ui.soc_charge_limit_fail_count=0
            controller.capture()
            with sqlite3.connect(controller.outbox.path) as db:
                data=[json.loads(r[0]) for r in db.execute('SELECT payload FROM queue ORDER BY seq')]
            self.assertEqual([p['kind'] for p in data],['trap','trap','snapshot'])
            self.assertEqual(data[2]['data']['module_data']['1']['soc'],83)
            self.assertEqual(data[2]['data']['raw_oids'],{'1.2.3':'raw'})
            self.assertIsNotNone(data[2]['data']['last_poll_at'])
            self.assertEqual(data[2]['data']['operating_status'],{
                'discharge_count':17,
                'charge_cutoff':{
                    'overvoltage':True,'high_temperature':False,
                    'overcurrent':False,'breaker_off':True,
                },
                'charge_current_limit_c':0.45,
                'soc_charge_limit':{'supported':True,'enabled':True,'value_percent':90},
            })
            ui.soc_charge_limit_fail_count=1
            controller.capture()
            with sqlite3.connect(controller.outbox.path) as db:
                latest=json.loads(db.execute('SELECT payload FROM queue ORDER BY seq DESC LIMIT 1').fetchone()[0])
            self.assertEqual(latest['data']['operating_status']['soc_charge_limit'],
                             {'supported':True,'enabled':None,'value_percent':None})
            ui.soc_charge_limit_enabled=None
            ui.soc_charge_limit_value=None
            ui.soc_charge_limit_fail_count=2
            controller.capture()
            with sqlite3.connect(controller.outbox.path) as db:
                latest=json.loads(db.execute('SELECT payload FROM queue ORDER BY seq DESC LIMIT 1').fetchone()[0])
            self.assertEqual(latest['data']['operating_status']['soc_charge_limit'],
                             {'supported':False,'enabled':None,'value_percent':None})
            controller.config['interval']=12; controller.apply_timer()
            self.assertEqual(controller.timer.interval(),12000)
            self.assertFalse(data[2]['data']['connected'])
            # ACK-driven state, stale configuration events, and live bounded history.
            controller.update_status_button()
            self.assertFalse(ui.btn_upload_status.isEnabled())
            event = UploadWorker.result_event(controller.generation, data[2], False, 'ConnectionError')
            controller.on_upload_result(event)
            self.assertEqual(ui.btn_upload_status.property('uploadState'), 'failed')
            controller.on_upload_result(dict(event, generation=controller.generation - 1, ok=True))
            self.assertEqual(ui.btn_upload_status.property('uploadState'), 'failed')
            controller.on_upload_result(dict(event, ok=True, error=''))
            self.assertTrue(ui.btn_upload_status.isEnabled())
            controller.open_history()
            for i in range(35):
                controller.on_upload_result(dict(event, ok=True, summary=f'기록 {i}'))
            self.assertEqual(len(controller.history), 30)
            lines = controller.history_view.toPlainText().splitlines()
            self.assertEqual(len(lines), 30)
            self.assertIn('기록 34', lines[0])
            self.assertIn('기록 5', lines[-1])
            self.assertIn('실제 측정 ', lines[0])
            self.assertIn('수집 ', lines[0])
            controller.on_upload_result(event)
            self.assertIn('실패 (ConnectionError)', controller.history_view.toPlainText().splitlines()[0])
            controller.config['enabled'] = False
            controller.update_status_button()
            self.assertEqual(ui.btn_upload_status.property('uploadState'), 'disabled')
            controller.history_dialog.close()
            # Clearing the screen must not advertise a live SNMP session as
            # disconnected. Verify the flag in the actual uploaded snapshot.
            controller.config['enabled'] = True
            ui.is_connected = True
            ui.btn_reset.click()
            self.assertTrue(ui.is_connected)
            controller.poll(True, {'1.2.3': 'new reading'})
            controller.capture()
            with sqlite3.connect(controller.outbox.path) as db:
                latest = json.loads(db.execute('SELECT payload FROM queue ORDER BY seq DESC LIMIT 1').fetchone()[0])
            self.assertTrue(latest['data']['connected'])
            self.assertTrue(latest['data']['last_poll_ok'])
            ui.reset_module_state(for_reconnect=True)
            self.assertFalse(ui.is_connected)
            ui.btn_reset.click()
            self.assertFalse(ui.is_connected)
        finally:
            ui.close(); app.processEvents()
            original_queue.unlink(missing_ok=True)


    def test_reconnect_after_server_unavailable(self):
        server=Receiver(('127.0.0.1',0),self.root/'received.db','local-test')
        port=server.server_address[1]
        server.server_close()
        self.config['port']=port
        box=Outbox(self.root/'queue.db')
        box.put(destination(self.config),envelope(self.config,'snapshot',{'offline':True}))
        failed=threading.Event()
        results=[]
        worker=UploadWorker(box,lambda text: failed.set(), results.append)
        worker.configure(self.config); worker.start()
        try:
            self.assertTrue(failed.wait(5))
            self.assertEqual(box.count(),1)
            with Receiver(('127.0.0.1',port),self.root/'received.db','local-test') as server:
                thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
                try:
                    deadline=time.monotonic()+8
                    while box.count() and time.monotonic()<deadline: time.sleep(.02)
                    self.assertEqual(box.count(),0)
                finally: server.shutdown()
        finally:
            worker.stop(); worker.join(5)
        self.assertFalse(results[0]['ok'])
        self.assertTrue(results[-1]['ok'])
        self.assertEqual(results[-1]['device_id'], 'd1')
        self.assertNotIn('token', results[-1])


if __name__=='__main__': unittest.main()
