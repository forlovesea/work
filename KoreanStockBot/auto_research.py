"""Bounded background collection. The child never receives brokerage credentials."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from live import ROOT, Store, SafetyStop, now_kst, stamp, process_lock

RESEARCH_KEYS=('KRX_ID','KRX_PW','DART_API_KEY','NAVER_CLIENT_ID','NAVER_CLIENT_SECRET')


def worker(day,output):
    from auto_data import collect_inputs
    from research_sources import Sources
    from build_research import build
    now=now_kst()
    from collection_log import CollectionLog,CollectionError,safe_error
    audit=CollectionLog(ROOT/'research'/'logs')
    status=Store(ROOT/'research'/'auto_status.json')
    def report(state,**details):
        status.data=dict(state=state,as_of=day,updated_at=now_kst().isoformat(),**audit.snapshot(),**details)
        status.save()
        audit.write('STATUS',state=state)
    try:
        audit.write('RUN_START',as_of=day)
        if any(not os.environ.get(k) for k in RESEARCH_KEYS): raise CollectionError('MISSING_RESEARCH_CREDENTIALS')
        if not 0<(now.date()-date.fromisoformat(day)).days<=10: raise SafetyStop('INVALID_AS_OF_DATE')
        with process_lock(ROOT/'research'/'build.lock'):
            report('COLLECTING_KRX')
            sources=Sources(ROOT/'research'/'cache',now)
            sources.audit=audit
            audit.observer=lambda:report('COLLECTING_DATA',sources=sources.health)
            sources.observer=lambda health:report('COLLECTING_DATA',sources=health)
            u,h,failures=collect_inputs(day,ROOT/'research'/'automatic_inputs',sources)
            report('ANALYZING_FINANCIALS_AND_NEWS',composition_unavailable=failures,sources=sources.health)
            # Publish only after the entire collection and analysis succeeds.
            staging=ROOT/'research'/'auto_staging.json'
            book=build(u,h,day,staging,sources,now)
            book.update(source_mode='automatic',max_age_seconds=7200,
                        collection={'provider':'KRX via pykrx 1.2.9 + OpenDART + NAVER',
                                    'composition_unavailable':failures,'sources':sources.health})
            target=Store(output); target.data=book; target.save()
            audit.current='COMPLETE'
            report('READY',sources=sources.health,candidates=len(book['universe']),
                   eligible=sum(a['allow_buy'] for a in book['assessments'].values()),composition_unavailable=failures)
    except Exception as exc:
        # Do not propagate third-party errors: they may contain URLs, headers or passwords.
        audit.current=audit.failed or audit.current
        audit.write('RUN_FAILED',**safe_error(exc))
        report('COLLECTION_FAILED',**safe_error(exc),retry='automatic',
               sources=sources.health if 'sources' in locals() else {})
        return 1
    finally:audit.close()
    return 0


class AutoResearch:
    def __init__(self,output,root=ROOT,popen=subprocess.Popen,clock=time.monotonic,now=now_kst):
        self.root=Path(root)
        self.output=Path(output)
        self.popen,self.clock,self.now=popen,clock,now
        self.child=None
        self.child_day=None
        self.started=0
        self.next_attempt=0
        self.calendar_date=None
        self.as_of=None
        self.state='IDLE'

    def tick_broker(self,broker):
        today=self.now().date().isoformat()
        if self.calendar_date!=today:
            try:
                cal=broker.get('market-calendar/KR',{'date':today})
                day=cal['previousBusinessDay']['date']
                if cal['today']['date']!=today or not 0<(date.fromisoformat(today)-date.fromisoformat(day)).days<=10:
                    raise SafetyStop('Invalid collection calendar')
                self.calendar_date,self.as_of=today,day
            except Exception:
                self.state='CALENDAR_UNAVAILABLE'
                return self.state
        return self.tick(self.as_of)

    def tick(self,day):
        if self.child:
            if day!=self.child_day or self.clock()-self.started>1800:
                self.close()
                self.next_attempt=self.clock()+300
                self.state='WORKER_TIMEOUT_OR_DATE_CHANGED'
                return self.state
            result=self.child.poll()
            if result is None:
                self.state='UPDATING'
                return self.state
            self.child=None
            self.next_attempt=self.clock()+(3600 if result==0 else 300)
            self.state='READY' if result==0 else 'RETRY_WAIT'
            return self.state
        if self.clock()<self.next_attempt: return self.state
        try:
            book=Store(self.output).data
            if (book and book.get('source_mode')=='automatic' and book['as_of']==day and
                    0<=(self.now()-stamp(book['generated_at'])).total_seconds()<3600):
                self.state='READY'
                return self.state
        except (OSError,KeyError,ValueError,TypeError): pass
        missing=[k for k in RESEARCH_KEYS if not os.environ.get(k)]
        if missing:
            self.state='SETUP_REQUIRED: '+','.join(missing)
            self.next_attempt=self.clock()+300
            return self.state
        child_env={k:v for k,v in os.environ.items() if not k.upper().startswith('TOSS_')}
        from app_paths import worker_command
        try:
            self.child=self.popen(worker_command('auto_research',self.root)+
                                  ['--worker','--as-of',day,'--output',str(self.output)],
                                  cwd=str(self.root),env=child_env,stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except OSError:
            self.state='WORKER_START_FAILED'; self.next_attempt=self.clock()+300
            return self.state
        self.child_day=day; self.started=self.clock(); self.state='UPDATING'
        return self.state

    def close(self):
        if self.child is not None:
            if self.child.poll() is None:
                self.child.terminate()
                try: self.child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.child.kill(); self.child.wait(timeout=3)
            self.child=None


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--worker',action='store_true',required=True)
    p.add_argument('--as-of',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    raise SystemExit(worker(args.as_of,args.output))
