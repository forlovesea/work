"""Bounded JSON-lines audit. Never log exception text, URLs, headers or key values."""
import json
import logging
import uuid
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from live import SafetyStop,now_kst


class CollectionError(SafetyStop):
    def __init__(self,code,http_status=None,provider_code=None):
        super().__init__('Collection request failed; inspect collection log')
        self.code=code;self.http_status=http_status;self.provider_code=provider_code


def safe_error(exc):
    result={'error_type':type(exc).__name__}
    if isinstance(exc,CollectionError):
        result['error_code']=exc.code
        if exc.http_status is not None:result['http_status']=exc.http_status
        if exc.provider_code is not None:result['provider_code']=exc.provider_code
    else:result['error_code']='VALIDATION_OR_LOCAL_ERROR'
    return result


class CollectionLog:
    def __init__(self,directory):
        directory.mkdir(parents=True,exist_ok=True)
        self.handler=RotatingFileHandler(directory/'collection.log',maxBytes=2_000_000,backupCount=5,encoding='utf-8')
        self.handler.setFormatter(logging.Formatter('%(message)s'))
        self.run_id=uuid.uuid4().hex
        self.current='SETUP';self.failed=None
        self.observer=None
        self.providers={p:'NOT_REQUESTED' for p in ('KRX','DART','NAVER')}

    def write(self,event,**fields):
        data=dict(time=now_kst().isoformat(),run_id=self.run_id,event=event,stage=self.current,**fields)
        self.handler.emit(logging.LogRecord('collection',logging.INFO,'',0,json.dumps(data,ensure_ascii=False),(),None))

    @contextmanager
    def stage(self,name,provider):
        previous=self.current;self.current=name
        self.providers[provider]='IN_PROGRESS';self.write('START',provider=provider)
        if self.observer:self.observer()
        try:
            yield
        except Exception as exc:
            self.providers[provider]='FAILED'
            self.failed=getattr(exc,'collection_stage',name)
            exc.collection_stage=self.failed
            self.write('FAILED',provider=provider,**safe_error(exc));raise
        else:
            self.providers[provider]='COMPLETED';self.write('COMPLETED',provider=provider)
        finally:
            if self.observer:self.observer()
            self.current=previous

    def snapshot(self):
        return dict(run_id=self.run_id,stage=self.current,last_failed_stage=self.failed,provider_stages=dict(self.providers),log_file='research/logs/collection.log')

    def close(self):self.handler.close()


def audited(sources,name,provider,fn,*args,**kwargs):
    audit=getattr(sources,'audit',None)
    if audit is None:return fn(*args,**kwargs)
    with audit.stage(name,provider):return fn(*args,**kwargs)
