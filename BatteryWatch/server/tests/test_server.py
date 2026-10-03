import asyncio
from contextlib import closing
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT.parent/'monitoring-client'))
from receiver import Receiver, load_config, validate, Rejected
from storage import Storage
from server import initialize, main
from mobile_api import configure_api, mutate, query
from upload_transport import Outbox, UploadWorker, destination, envelope, encode_frame


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        credentials=initialize(self.root/'server.local.json','site-01','battery-01')
        self.client=json.loads(credentials.read_text())
        self.client['enabled']=True; self.client['ca_file']=''
        self.config=load_config(self.root/'server.local.json')
        self.config['port']=0
        self.db=Storage(self.config['database'])
        self.receiver=await Receiver(self.config,self.db).start()
        self.client['port']=self.receiver.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.receiver.close()
        self.temp.cleanup()

    def sample(self,kind='snapshot',**changes):
        data={'connected':True,'module_data':{'1':{'soc':80,'temps':[25,26],'cells':[3.2,3.3]}},
              'module_map':{'1':{'model':'TBC1000B'}},'raw_oids':{'1.2.3':'value'},
              'active_alarms':[{'text':'온도 알람'}], 'last_poll_ok':True,
              'last_poll_at':datetime.now(timezone.utc).isoformat()}
        if kind=='trap': data=dict(raw_trap={'alarm':'resume','_source_ip':'10.0.0.1'},received_at=datetime.now(timezone.utc).isoformat())
        p=envelope(self.client,kind,data); p.update(changes); return p

    async def send(self,payload,token=None,fragment=False):
        reader,writer=await asyncio.open_connection('127.0.0.1',self.client['port'])
        try:
            frame=encode_frame(dict(type='upload',token=token or self.client['token'],payload=payload))
            if fragment:
                for i in range(0,len(frame),3):
                    writer.write(frame[i:i+3]); await writer.drain()
            else: writer.write(frame); await writer.drain()
            head=await asyncio.wait_for(reader.readexactly(4),4)
            return json.loads(await reader.readexactly(struct.unpack('!I',head)[0]))
        finally:
            writer.close(); await writer.wait_closed()

    async def test_upload_debug_ack_and_redaction(self):
        sample=self.sample()
        sample['data']['raw_oids']['secret']='PRIVATE_PAYLOAD'
        with self.assertLogs('batterywatch', level='DEBUG') as logs:
            self.assertTrue((await self.send(sample))['ok'])
            self.assertTrue((await self.send(sample))['duplicate'])
        output='\n'.join(logs.output)
        for expected in ('UPLOAD frame', 'UPLOAD authenticated', 'UPLOAD ack', 'duplicate=True', "device='battery-01'"):
            self.assertIn(expected, output)
        self.assertNotIn(self.client['token'], output)
        self.assertNotIn('PRIVATE_PAYLOAD', output)

    async def test_storage_duplicate_latest_and_traps(self):
        p=self.sample()
        self.assertTrue((await self.send(p,fragment=True))['ok'])
        self.assertTrue((await self.send(p))['duplicate'])
        old=self.sample(captured_at=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat())
        await self.send(old)
        await self.send(self.sample('trap'))
        state=self.db.inspect()
        self.assertEqual(state['total_samples'],3)
        self.assertEqual(state['latest'][0]['sample_id'],p['sample_id'])
        self.assertEqual(state['latest'][0]['payload']['data']['module_data']['1']['soc'],80)
        self.assertEqual(state['latest'][0]['payload']['data']['active_alarms'][0]['text'],'온도 알람')
        self.assertTrue(state['recent_sessions'])
        reopened=Storage(self.config['database'])
        self.assertEqual(reopened.inspect()['total_samples'],3)
        self.db.backup(self.root/'backup.sqlite3')
        self.assertEqual(Storage(self.root/'backup.sqlite3').inspect()['total_samples'],3)

    async def test_auth_scope_invalid_and_conflicting_id(self):
        for payload,token in [(self.sample(),'bad-token'),(self.sample(device_id='unregistered'),None),
                              (self.sample(schema_version=True),None),
                              (self.sample(captured_at='2099-01-01T00:00:00Z'),None)]:
            with self.assertRaises(asyncio.IncompleteReadError): await self.send(payload,token)
        self.assertEqual(self.db.inspect()['total_samples'],0)
        p=self.sample(); await self.send(p)
        p['data']['module_data']['1']['soc']=1
        with self.assertRaises(asyncio.IncompleteReadError): await self.send(p)
        self.assertEqual(self.db.inspect()['total_samples'],1)

    async def test_storage_failure_sends_no_ack(self):
        with patch.object(self.db,'save',side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(asyncio.IncompleteReadError): await self.send(self.sample())
        self.assertEqual(self.db.inspect()['total_samples'],0)

    async def test_frame_limit_and_invalid_json(self):
        for frame in [struct.pack('!I',16777217),struct.pack('!I',3)+b'xxx',struct.pack('!I',5)+b'1e999']:
            reader,writer=await asyncio.open_connection('127.0.0.1',self.client['port'])
            writer.write(frame); await writer.drain()
            self.assertEqual(await asyncio.wait_for(reader.read(1),3),b'')
            writer.close(); await writer.wait_closed()
        self.assertEqual(self.db.inspect()['total_samples'],0)

    async def test_existing_upload_worker_end_to_end(self):
        box=Outbox(self.root/'client.sqlite3')
        samples=[self.sample(),self.sample('trap')]
        for p in samples: box.put(destination(self.client),p)
        worker=UploadWorker(box,lambda _:None); worker.configure(self.client); worker.start()
        try:
            for _ in range(100):
                if not box.count(): break
                await asyncio.sleep(.05)
            self.assertEqual(box.count(),0)
            self.assertEqual(self.db.inspect()['total_samples'],2)
        finally:
            worker.stop(); await asyncio.to_thread(worker.join,5)
        self.assertFalse(worker.is_alive())

    async def test_public_plaintext_rejected_and_init_no_overwrite(self):
        file=self.root/'server.local.json'
        config=json.loads(file.read_text()); config['host']='0.0.0.0'
        file.write_text(json.dumps(config))
        with self.assertRaises(ValueError): load_config(file)
        with self.assertRaises(ValueError): initialize(file,'s','d')

    async def test_shared_upload_and_viewer_tokens_cover_multiple_devices(self):
        shared_root=self.root/'shared'
        shared_root.mkdir()
        file=shared_root/'server.local.json'
        grants=[dict(site_id='north',device_id='rack-1'),dict(site_id='south',device_id='rack-2')]
        credentials=initialize(file,None,None,grants)
        collector_config=load_config(file)
        self.assertEqual(len(collector_config['collectors']),1)
        self.assertEqual(collector_config['collectors'][0]['devices'],grants)

        client=json.loads(credentials.read_text())
        collector_config['port']=0
        shared_db=Storage(collector_config['database'])
        shared_receiver=await Receiver(collector_config,shared_db).start()
        client['port']=shared_receiver.server.sockets[0].getsockname()[1]
        previous_client=self.client
        self.client=client
        try:
            for index,grant in enumerate(grants):
                payload=envelope(client,'snapshot',{
                    'connected':True,'module_data':{},'module_map':{},'raw_oids':{},
                    'active_alarms':[],'last_poll_at':datetime.now(timezone.utc).isoformat(),
                })
                payload.update(grant,sample_id=f'shared-token-sample-{index}')
                self.assertTrue((await self.send(payload,token=client['token']))['ok'])
        finally:
            self.client=previous_client
            await shared_receiver.close()

        for index,grant in enumerate(grants):
            payload=dict(sample_id=f'validation-{index}',site_id=grant['site_id'],
                         device_id=grant['device_id'],schema_version=1,
                         kind='snapshot',captured_at=datetime.now(timezone.utc).isoformat(),
                         data={'connected':True,'module_data':{},'module_map':{},
                               'raw_oids':{},'active_alarms':[]})
            self.assertEqual(validate(dict(type='upload',token=client['token'],payload=payload),
                                      collector_config['collectors'])[0],'collector-01')

        unauthorized=dict(payload,site_id='west',device_id='rack-3')
        with self.assertRaises(Rejected):
            validate(dict(type='upload',token=client['token'],payload=unauthorized),
                     collector_config['collectors'])

        with patch.object(sys,'argv',['server.py','--config',str(file),'enable-api']):
            main()
        configured=load_config(file)
        api=configure_api(configured)
        viewer=api['viewers'][0]
        self.assertEqual(viewer['devices'],grants)
        self.assertNotEqual(viewer['token_sha256'],configured['collectors'][0]['token_sha256'])
        devices=query(shared_db,viewer,'/api/v1/devices',{})[1]['devices']
        self.assertEqual([dict(site_id=item['site_id'],device_id=item['device_id']) for item in devices],grants)
        self.assertTrue(all(item['available'] for item in devices))

    async def test_remote_charge_limit_command_requires_live_authorized_client(self):
        viewer=dict(id='android',devices=[dict(site_id='site-01',device_id='battery-01')])
        self.assertEqual(mutate(self.db,viewer,'POST','/api/v1/commands',{
            'site_id':'site-01','device_id':'battery-01',
            'action':'charge_current_limit','value_centi':50,
        })[0],409)

        reader,writer=await asyncio.open_connection('127.0.0.1',self.client['port'])
        async def upload(payload):
            writer.write(encode_frame(dict(type='upload',token=self.client['token'],payload=payload)))
            await writer.drain()
            header=await asyncio.wait_for(reader.readexactly(4),4)
            return json.loads(await reader.readexactly(struct.unpack('!I',header)[0]))

        self.assertTrue((await upload(self.sample()))['ok'])
        self.assertEqual(mutate(self.db,viewer,'POST','/api/v1/commands',{
            'site_id':'site-01','device_id':'battery-01',
            'action':'charge_current_limit','value_centi':50,
        })[0],200)
        with closing(self.db.connect()) as db:
            command_id=db.execute('SELECT command_id FROM control_commands').fetchone()[0]
        command_ack=await upload(self.sample())
        self.assertEqual(command_ack['control_command'],
                         dict(command_id=command_id,action='charge_current_limit',value_centi=50))

        result=dict(command_id=command_id,status='succeeded',applied_value_centi=50,
                    message='장비 설정 및 GET 확인 완료')
        payload=self.sample()
        payload['data']['control_results']=[result]
        self.assertTrue((await upload(payload))['ok'])
        command_status=self.db.control_command_status(command_id,'android')
        self.assertEqual(command_status['status'],'succeeded')
        self.assertEqual(command_status['applied_value_centi'],50)
        writer.close()
        await writer.wait_closed()

        other=dict(id='other',devices=[])
        self.assertEqual(mutate(self.db,other,'POST','/api/v1/commands',{
            'site_id':'site-01','device_id':'battery-01',
            'action':'charge_current_limit','value_centi':50,
        })[0],403)
        self.assertEqual(mutate(self.db,viewer,'POST','/api/v1/commands',{
            'site_id':'site-01','device_id':'battery-01',
            'action':'charge_current_limit','value_centi':101,
        })[0],400)

    async def test_tls_with_existing_worker(self):
        openssl=shutil.which('openssl')
        bundled=Path('C:/Program Files/Git/usr/bin/openssl.exe')
        if not openssl and bundled.is_file(): openssl=str(bundled)
        if not openssl: self.skipTest('OpenSSL needed only to generate a temporary test certificate')
        cert,key=self.root/'cert.pem',self.root/'key.pem'
        result=await asyncio.to_thread(subprocess.run,[openssl,'req','-x509','-newkey','rsa:2048','-nodes',
            '-keyout',str(key),'-out',str(cert),'-days','2','-subj','/CN=localhost',
            '-addext','subjectAltName=IP:127.0.0.1'],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        await self.receiver.close()
        self.config['tls']=dict(certfile=str(cert),keyfile=str(key))
        self.receiver=await Receiver(self.config,self.db).start()
        self.client.update(port=self.receiver.server.sockets[0].getsockname()[1],tls=True,ca_file=str(cert))
        box=Outbox(self.root/'tls-client.sqlite3')
        box.put(destination(self.client),self.sample())
        worker=UploadWorker(box,lambda _:None); worker.configure(self.client); worker.start()
        try:
            for _ in range(120):
                if not box.count(): break
                await asyncio.sleep(.05)
            self.assertEqual(box.count(),0)
            self.assertEqual(self.db.inspect()['total_samples'],1)
        finally:
            worker.stop(); await asyncio.to_thread(worker.join,5)


if __name__=='__main__': unittest.main()
