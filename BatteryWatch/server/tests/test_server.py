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
from receiver import Receiver, load_config
from storage import Storage
from server import initialize
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
              'active_alarms':[{'text':'온도 알람'}], 'last_poll_at':datetime.now(timezone.utc).isoformat()}
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
