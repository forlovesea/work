"""Opt-in support logs. Only allowlisted diagnostic fields enter upload files."""
import json
import platform
import uuid
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from app_version import VERSION
from runtime_status import KST

EVENTS={'SESSION':'프로그램 진단 기록 시작','ENABLED':'로그 생성 켜짐','DISABLED':'로그 생성 꺼짐',
 'STOCK_START':'업종별 재무 종목 조회 시작','STOCK_END':'업종별 종목 조회 종료','STOCK_ERROR':'종목 자료 조회·검증 오류',
 'STOCK_PROGRESS':'업종별 종목 조회 진행',
 'START':'작업 시작 요청','STOP':'중지 요청','EXIT':'작업 프로세스 종료',
 'ACCOUNTS':'계좌 조회 완료','ACCOUNT_START':'계좌 조회 시작',
 'CANDIDATE_START':'최신 계좌·시세 조회 시작','CANDIDATE_REPORT':'후보 검사 완료',
 'CANDIDATE_ERROR':'후보 검사 실패','RUNTIME':'매매 감시 상태','COLLECTION':'자료 수집 상태',
 'DELAY':'작업 응답 지연','ORDER':'주문 신호·제출 응답 (체결 확정 아님)','EXPORT':'공유용 진단 파일 저장'}
LABELS={'status':'처리 상태','stage':'수집 단계','error_code':'오류 코드','error_type':'오류 종류',
 'http_status':'HTTP 응답','provider_code':'공급자 응답 코드','errno':'파일 오류 번호','winerror':'Windows 오류 번호',
 'count':'개수','eligible':'조건 통과 수','candidates':'검사 종목 수','supported':'구조 검사 통과 수',
 'exit_code':'프로세스 종료 코드','confirmed':'정상 중지 확인','elapsed':'경과 초',
 'live':'실주문 모드','capital':'설정 운용 원금','max_order_won':'주문 상한',
 'poll_seconds':'점검 간격(초)','updated_at':'자료 갱신 시각','as_of':'자료 기준일',
 'provider':'수집처','event':'수집 동작','state':'수집 상태','network':'API 응답 수','cache':'캐시 사용 수','errors':'오류 수'}
TOKENS=set('''INITIALIZING BROKER_REQUEST BROKER_CONNECTION_WAIT HOLD STOP_CHECKING PENDING STOPPING STOPPED STOP_REQUESTED HALTED ENTRY_PAUSED RESEARCH_OR_CANDIDATE_DATA_UNAVAILABLE NO_ELIGIBLE_AFFORDABLE_ETF SPREAD_TOO_WIDE SESSION_ENDED OUTSIDE_REGULAR_SESSION CANDIDATE_REPORT CANDIDATE_ERROR IDLE UPDATING READY NO_SUPPORTED_ETF COLLECTION_FAILED COLLECTING_KRX COLLECTING_DATA ANALYZING_FINANCIALS_AND_NEWS WORKER_TIMEOUT_OR_DATE_CHANGED SETUP COMPLETE KRX_ETF_DAILY KRX_ETF_METADATA KRX_CATALOG_VALIDATE KRX_CATALOG_CACHE KRX_COMPOSITION_REQUEST KRX_COMPOSITION_VALIDATE KRX_COMPOSITION_CACHE DART_CORPORATION_MAP DART_FINANCIAL_REQUEST DART_FINANCIAL_ANALYSIS NAVER_NEWS_REQUEST NAVER_NEWS_ANALYSIS KRX DART NAVER START COMPLETED FAILED STATUS SOURCE_RESULT RUN_START RUN_FAILED NOT_REQUESTED IN_PROGRESS VALIDATION_OR_LOCAL_ERROR LOCAL_FILE_ACCESS NETWORK_OR_TIMEOUT HTTP_ERROR DART_API_REJECTED NAVER_API_REJECTED INVALID_RESPONSE INVALID_CORPORATION_MAP MISSING_RESEARCH_CREDENTIALS MISSING_DART_KEY MISSING_NAVER_KEYS MISSING_FILE RESEARCH_STALE BROKER_ERROR AUTH_OR_PERMISSION CAPITAL ACCOUNT UNVERIFIED PermissionError FileNotFoundError SafetyStop BrokerError CollectionError ValueError KeyError TypeError OSError TimeoutError JSONDecodeError network cache error'''.split())
NUMBERS={'count','eligible','candidates','supported','exit_code','elapsed','capital','max_order_won','poll_seconds','network','cache','errors','http_status','errno','winerror'}
TOKENS.update(('WORKER_ERROR','SUCCESS','LOOKUP_FAILED','WORKER_FAILED','START_FAILED'))
TOKENS.update(('BUY','SELL','LIVE','DRY_RUN'))
TOKENS.update(('BROKER_RESPONSE','OTHER','ACCOUNTS','HOLDINGS','BUYING_POWER','CALENDAR','STOCKS','CANDLES','PRICES','ORDERBOOK','ORDERS','CONDITIONS','COMMISSIONS','SELLABLE_QUANTITY','AUTH','ORDER_CANCEL','WARNINGS'))
LABELS['operation']='API 처리 단계'
LABELS.update(side='매매 방향',quantity='주문 수량',price='주문 가격',mode='주문 모드')
NUMBERS.update(('quantity','price'))
TOKENS.add('COLLECTION_STOPPED')
LABELS.update(etf_done='ETF 검사 완료',etf_total='ETF 검사 대상',financial_done='기업 재무 완료',financial_total='기업 재무 대상',news_done='뉴스 검색 완료',news_total='뉴스 검색 대상',current_rank='진행 중 ETF 순위',elapsed_seconds='수집 경과 초')
NUMBERS.update(('etf_done','etf_total','financial_done','financial_total','news_done','news_total','current_rank','elapsed_seconds'))
from collection_log import COMPOSITION_REASONS
TOKENS.update(COMPOSITION_REASONS)
from candidate_feedback import SAFETY_REASONS
TOKENS.update(SAFETY_REASONS)
TOKENS.update(('CompositionError','ETF_EXCLUDED','RESEARCH_FIRST_COLLECTION','RESEARCH_UPDATING'))
LABELS.update(symbol='제외 ETF 종목코드',observed_percent='관측 비중(%)',minimum_percent='허용 최소(%)',maximum_percent='허용 최대(%)')
NUMBERS.update(('observed_percent','minimum_percent','maximum_percent'))
MEANINGS={'READY':'분석 파일 생성 완료','COLLECTION_FAILED':'자료 수집 실패','COMPLETE':'수집·분석 종료',
 'COLLECTING_KRX':'KRX 수집 준비','COLLECTING_DATA':'자료 조회 진행 중',
 'ANALYZING_FINANCIALS_AND_NEWS':'재무·뉴스 분석 중','WORKER_TIMEOUT_OR_DATE_CHANGED':'수집 시간 초과 또는 기준일 변경',
 'NO_SUPPORTED_ETF':'지원 구조 ETF 없음','NOT_REQUESTED':'아직 요청하지 않음','IN_PROGRESS':'진행 중',
 'COMPLETED':'단계 완료','FAILED':'단계 실패','START':'단계 시작','STATUS':'상태 갱신',
 'RUN_START':'수집 실행 시작','RUN_FAILED':'수집 실행 실패','SOURCE_RESULT':'공급자 응답',
 'SUCCESS':'정상 완료','LOOKUP_FAILED':'조회 실패','WORKER_FAILED':'조회 프로세스 실패',
 'network':'API 응답 수신','cache':'저장 자료 사용','error':'오류',
 'KRX_ETF_DAILY':'KRX ETF 시세','KRX_ETF_METADATA':'KRX ETF 기본정보',
 'KRX_CATALOG_VALIDATE':'ETF 목록 검증','KRX_CATALOG_CACHE':'저장 ETF 목록 검증',
 'KRX_COMPOSITION_REQUEST':'KRX 구성종목 조회','KRX_COMPOSITION_VALIDATE':'구성종목 비중 검증',
 'KRX_COMPOSITION_CACHE':'저장 구성종목 검증','DART_CORPORATION_MAP':'DART 기업코드 연결',
 'DART_FINANCIAL_REQUEST':'DART 재무 조회','DART_FINANCIAL_ANALYSIS':'재무 분석',
 'NAVER_NEWS_REQUEST':'NAVER 뉴스 조회','NAVER_NEWS_ANALYSIS':'뉴스 분석'}
MEANINGS.update(AUTH='증권사 인증',ACCOUNTS='계좌 목록',HOLDINGS='보유 종목',BUYING_POWER='주문 가능 금액',
 CALENDAR='시장 운영일',STOCKS='종목 기본정보',CANDLES='일봉',PRICES='현재 시세',ORDERBOOK='호가',
 ORDERS='주문 상태',CONDITIONS='예약·조건 주문',COMMISSIONS='수수료',SELLABLE_QUANTITY='매도 가능 수량',
 ORDER_CANCEL='주문 취소',WARNINGS='종목 위험 정보')
MEANINGS['COLLECTION_STOPPED']='수집 중단 · 프로그램 중지/종료 요청으로 수집을 멈춤'


def safe_fields(data):
    result={}
    for key,value in data.items():
        if key=='symbol' and isinstance(value,str) and re.fullmatch('[0-9A-Z]{6}',value):
            result[key]=value;continue
        if key in NUMBERS and isinstance(value,(int,float)) and not isinstance(value,bool):result[key]=value
        elif key in ('live','confirmed') and isinstance(value,bool):result[key]=value
        elif key in ('updated_at','as_of') and isinstance(value,str):
            try:result[key]=datetime.fromisoformat(value).isoformat()
            except ValueError:pass
        elif key=='provider_code' and isinstance(value,str) and len(value)==3 and value.isdigit():result[key]=value
        elif key in LABELS and isinstance(value,str) and value in TOKENS:result[key]=value
    return result


def block(event,data):
    fields=safe_fields(data)
    lines=[EVENTS.get(event,'수집 상세 기록')+' ['+event+']']
    lines.extend('  '+LABELS[key]+': '+('예' if value is True else '아니요' if value is False else str(value)) for key,value in fields.items())
    for key in ('status','state','stage','event','operation'):
        value=fields.get(key)
        if value in MEANINGS:lines.append('  설명: '+MEANINGS[value])
    if event=='RUNTIME' and fields.get('status') not in (None,'WORKER_ERROR'):
        from runtime_status import describe_status
        lines.append('  설명: '+describe_status(json.dumps({'status':fields['status']})))
    if fields.get('error_code')=='LOCAL_FILE_ACCESS':lines.append('  안내: 파일 잠금 또는 실행 폴더의 쓰기 권한을 확인하세요.')
    if fields.get('error_code') in SAFETY_REASONS:
        detail=SAFETY_REASONS[fields['error_code']]
        lines.extend(('  종료 사유: '+detail[1],'  다음 행동: '+detail[2]))
    if fields.get('error_code') in COMPOSITION_REASONS:lines.append('  제외 사유: '+COMPOSITION_REASONS[fields['error_code']]+' · 해당 ETF만 매수 보류합니다.')
    if fields.get('status')=='STOPPED':lines.append('  안내: 작업 중지 응답입니다. 프로세스 종료와 정상 중지 확인도 함께 보세요.')
    if fields.get('state')=='READY':lines.append('  안내: 분석 파일 생성 완료이며 모든 종목의 매수 조건 통과를 뜻하지 않습니다.')
    return '\n'.join(lines)


class SupportLog:
    def __init__(self,root):
        self.root=Path(root);self.enabled=False;self.path=None
        self.counts=Counter();self.latest={};self.session=uuid.uuid4().hex[:12]

    def enable(self):
        directory=self.root/'logs';directory.mkdir(parents=True,exist_ok=True)
        if self.path is None:
            self.path=directory/('진단_'+datetime.now(KST).strftime('%Y%m%d_%H%M%S')+'_'+self.session+'.txt')
            self.path.write_text(self.header(),encoding='utf-8-sig')
        self.enabled=True
        self.record('ENABLED')

    def header(self):
        return (f'KoreanStockBot 진단 기록 | 버전 {VERSION} | 세션 {self.session}\n'
                f'운영체제: {platform.system()} {platform.release()} | 시각: 한국시간(+09:00)\n'
                '읽는 순서: 시작 → 계좌/후보/수집 단계 → 오류 또는 완료 → 중지 확인\n'
                '기록이 없으면 성공으로 판단할 수 없습니다. 꺼져 있던 시간은 복원하지 않습니다.\n'
                '인증키, 계좌번호·선택값, 주문 ID, 원본 API 응답, 환경변수는 기록하지 않습니다.\n'
                '설정 금액·처리 개수·오류 코드가 포함됩니다. 기본 수집/주문 기록은 별도 유지됩니다.\n\n')

    def disable(self):
        try:self.record('DISABLED')
        finally:self.enabled=False

    def record(self,event,**data):
        if not self.enabled:return
        if event not in EVENTS:return
        fields=safe_fields(data)
        self.counts[event]+=1;self.latest[(event,fields.get('provider',''))]=fields
        if self.path.stat().st_size>2_000_000:
            for index in (3,2,1):
                old=Path(str(self.path)+'.'+str(index))
                if index==3:old.unlink(missing_ok=True)
                elif old.exists():old.replace(Path(str(self.path)+'.'+str(index+1)))
            self.path.replace(Path(str(self.path)+'.1'))
            self.path.write_text(self.header(),encoding='utf-8-sig')
        with self.path.open('a',encoding='utf-8',newline='\n') as stream:
            stream.write(datetime.now(KST).isoformat(timespec='seconds')+' | '+block(event,fields)+'\n\n')

    def export(self,target):
        if self.path is None:raise ValueError('No recorded session')
        summary=[self.header(),'=== 이번 실행의 마지막 확인 상태 ===']
        for (event,provider),data in self.latest.items():summary.append(block(event,data))
        summary.append('\n=== 이벤트 횟수 ===\n'+json.dumps(dict(self.counts),ensure_ascii=False,indent=2))
        summary.append('\n문의 시 함께 적어주세요: 누른 버튼 / 기대한 결과 / 실제 결과 / 문제 발생 시각')
        target=Path(target)
        temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            with ZipFile(temporary,'w',ZIP_DEFLATED) as archive:
                archive.writestr('먼저읽기_진단요약.txt','\ufeff'+'\n\n'.join(summary))
                for index,path in enumerate([self.path]+[Path(str(self.path)+'.'+str(i)) for i in (1,2,3)]):
                    if path.exists():archive.write(path,'진단기록_'+str(index)+'.txt')
                # Do not bundle original files: parse and allowlist audit fields.
                audit=self.root/'research/logs/collection.log'
                if audit.exists():
                    with audit.open('rb') as stream:
                        stream.seek(max(0,audit.stat().st_size-1_000_000));raw=stream.read()
                    rows=[]
                    for line in raw.decode('utf-8',errors='replace').splitlines()[-2000:]:
                        try:item=json.loads(line)
                        except ValueError:continue
                        if not isinstance(item,dict):continue
                        item['updated_at']=item.get('time')
                        rows.append(block('COLLECTION',item))
                    archive.writestr('수집상세_최근기록.txt','\ufeff기존 기본 수집 감사 기록에서 추출한 최근 항목입니다. 이전 실행도 포함될 수 있습니다.\n\n'+'\n\n'.join(rows))
            temporary.replace(target)
        finally:temporary.unlink(missing_ok=True)
