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


COMPOSITION_REASONS={
 'DUPLICATE_CONSTITUENT':'구성종목 코드가 중복되었습니다',
 'INVALID_CONSTITUENT_WEIGHT':'구성종목 비중이 숫자가 아니거나 0~100% 범위를 벗어났습니다',
 'INCOMPLETE_COMPOSITION_WEIGHT':'구성종목 총 비중이 허용 범위(50~100.5%) 밖입니다',
 'MAPPED_WEIGHT_OVER_LIMIT':'기업 연결 후 비중 합계가 100.1%를 초과했습니다',
 'MISSING_COMPOSITION_FIELD':'구성종목 응답의 필수 항목이 누락되었습니다',
 'KRX_DATA_UNAVAILABLE':'구성종목 조회 또는 응답 형식을 확인하지 못했습니다'}


class CompositionError(CollectionError):
    def __init__(self,code,symbol,**measurements):
        super().__init__(code)
        self.symbol=symbol;self.measurements=measurements


def safe_error(exc):
    result={'error_type':type(exc).__name__}
    if isinstance(exc,CollectionError):
        result['error_code']=exc.code
        if exc.http_status is not None:result['http_status']=exc.http_status
        if exc.provider_code is not None:result['provider_code']=exc.provider_code
        if isinstance(exc,CompositionError):
            result['symbol']=exc.symbol
            result.update(exc.measurements)
    elif isinstance(exc,PermissionError):
        result['error_code']='LOCAL_FILE_ACCESS'
        if exc.errno is not None:result['errno']=exc.errno
        if getattr(exc,'winerror',None) is not None:result['winerror']=exc.winerror
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
