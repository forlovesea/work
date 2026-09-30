import asyncio
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage import Storage
from alarms import initialize
from smartphone_demo import sample
from retention import cleanup, configure, monitor

class RetentionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage=Storage(Path(self.temp.name)/'test.db')
        initialize(self.storage)
        self.now=datetime.now(timezone.utc)
        self.old=(self.now-timedelta(days=11)).isoformat(timespec='microseconds')
        self.boundary=(self.now-timedelta(days=10)).isoformat(timespec='microseconds')

    def seed(self):
        for i in range(5):
            p=sample(i)
            p['sample_id']=str(i)
            p['captured_at']=(self.now+timedelta(seconds=i)).isoformat()
            self.storage.save('collector',p,'session','local')
        with closing(self.storage.connect()) as db,db:
            db.execute('UPDATE samples SET received_at=?',(self.old,))
            db.execute("UPDATE samples SET received_at=? WHERE sample_id='3'",(self.boundary,))

    def test_old_rows_batched_latest_and_boundary_preserved(self):
        self.seed()
        opts=configure({'retention':{'batch_size':2}})
        self.assertEqual(cleanup(self.storage,opts,self.now)['samples'],2)
        self.assertEqual(cleanup(self.storage,opts,self.now)['samples'],1)
        self.assertEqual(cleanup(self.storage,opts,self.now)['samples'],0)
        with closing(self.storage.connect()) as db:
            self.assertEqual({r[0] for r in db.execute('SELECT sample_id FROM samples')},{'3','4'})
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],1)
        self.storage.disconnected('session')
        with closing(self.storage.connect()) as db,db:
            db.execute('UPDATE sessions SET disconnected_at=?',(self.old,))
        self.assertEqual(cleanup(self.storage,opts,self.now)['sessions'],1)

    def test_alarm_retention_preserves_state_and_pending_delivery(self):
        with closing(self.storage.connect()) as db,db:
            for event in ('old','state','pending'):
                db.execute('INSERT INTO alarm_events VALUES(?,?,?,?,?,?,?)',
                           (event,'s','d','rule','raised',0,'test'))
                db.execute('INSERT INTO alarm_acknowledgements VALUES(?,?,?)',(event,'viewer',0))
            db.execute("INSERT INTO alarm_state(site_id,device_id,rule_key,active,event_id) VALUES('s','d','rule',1,'state')")
            db.execute("INSERT INTO push_outbox VALUES('pending','phone',0,0,NULL,NULL)")
            db.execute("INSERT INTO push_outbox VALUES('old','phone',1,0,1,NULL)")
        self.assertEqual(cleanup(self.storage,configure({}),self.now)['alarms'],0)
        self.assertEqual(cleanup(self.storage,configure({'retention':{'alarm_days':10}}),self.now)['alarms'],1)
        with closing(self.storage.connect()) as db:
            self.assertEqual({r[0] for r in db.execute('SELECT event_id FROM alarm_events')},{'state','pending'})
            self.assertEqual(db.execute("SELECT count(*) FROM alarm_acknowledgements WHERE event_id='old'").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT count(*) FROM push_outbox WHERE event_id='old'").fetchone()[0],0)

    async def test_worker_cleans_at_start_and_stops_promptly(self):
        self.seed()
        stop=asyncio.Event()
        job=asyncio.create_task(monitor(self.storage,{},stop))
        try:
            for _ in range(100):
                with closing(self.storage.connect()) as db:
                    remaining=db.execute('SELECT count(*) FROM samples').fetchone()[0]
                if remaining==1: break
                await asyncio.sleep(.01)
            self.assertEqual(remaining,1)
        finally:
            stop.set()
            await asyncio.wait_for(job,2)

    def test_configuration_validation(self):
        self.assertEqual(configure({})['days'],10)
        for opts in (None,{'days':0},{'days':True},{'alarm_days':-1},{'batch_size':0},{'interval_seconds':0}):
            with self.assertRaises(ValueError): configure({'retention':opts})
