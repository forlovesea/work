"""Human-readable worker status; never infer a successful connection from a weekday."""
import json
from datetime import datetime, timedelta, timezone

KST=timezone(timedelta(hours=9))


def display_time(value):
    try: return datetime.fromisoformat(value).astimezone(KST).strftime('%Y-%m-%d %H:%M')+' (한국시간)'
    except (ValueError,TypeError): return '확인되지 않음'


def describe_status(line):
    try: report=json.loads(line)
    except (ValueError,TypeError):
        return {'LIVE ORDERS ENABLED':'계좌 점검 완료 · 시장 운영시간 확인 중',
                'READ ONLY: no orders will be sent':'읽기 전용 연결 완료 · 주문하지 않음'}.get(line,line)
    if not isinstance(report,dict): return '상태 응답 확인 중'
    if report.get('mode') in ('LIVE','DRY_RUN') and report.get('side') in ('BUY','SELL'):
        action='매수' if report['side']=='BUY' else '매도'
        prefix='주문 제출 · 체결 확인 필요' if report['mode']=='LIVE' else '읽기 전용 신호 · 주문하지 않음'
        return f"{prefix} · {action} {report.get('quantity')}주 / {report.get('price')}원"
    code=report.get('status','')
    if code=='OUTSIDE_REGULAR_SESSION':
        state=report.get('market_state')
        title={'HOLIDAY':'휴장 대기','BEFORE_OPEN':'매매 시작 대기',
               'SESSION_FINISHED':'오늘의 봇 매매시간 종료'}.get(state,'정규 매매시간 외 대기')
        text=title+' · 신규 매수·매도 주문 없음\n다음 정규장 개장: '+display_time(report.get('next_open'))
        if report.get('bot_start'): text+=' · 봇 매매 시작: '+display_time(report['bot_start'])
        return text+'\n프로그램을 켜 두면 운영시간과 매매 조건을 다시 확인합니다.'
    messages={
        'INITIALIZING':'연결 확인 중 · 인증·계좌·기존 주문 상태 점검',
        'BROKER_CONNECTION_WAIT':'증권사 연결 확인 실패 · 재연결 대기 · 주문·체결 상태 확인 필요',
        'HOLD':'장중 감시 중 · 매수·매도 조건 확인',
        'PENDING':'미체결 주문 확인 중', 'STOPPING':'중지 처리 중 · 미체결 취소 확인',
        'STOPPED':'중지 완료 · 보유 종목 유지', 'STOP_REQUESTED':'중지 요청 확인 중',
        'HALTED':'위험 한도 도달 · 신규 매수 중단',
        'ENTRY_PAUSED':'수익·손실 한도 또는 당일 매수 제한 · 신규 매수 대기',
        'RESEARCH_OR_CANDIDATE_DATA_UNAVAILABLE':'분석·후보 자료 확인 불가 · 신규 매수 대기',
        'NO_ELIGIBLE_AFFORDABLE_ETF':'조건과 예산을 만족하는 ETF 없음 · 신규 매수 대기',
        'SPREAD_TOO_WIDE':'호가 차이가 커서 주문 대기',
        'SESSION_ENDED':'매매시간 종료 · 신규 주문 없음',
    }
    text=messages.get(code,'처리 상태: '+str(code or '응답 확인 중'))
    if report.get('halted'): text+=' · 위험 한도로 신규 매수 중단'
    elif report.get('target_paused'): text+=' · 수익 목표 도달로 신규 매수 중단'
    if report.get('auto_research'): text+='\n자동 분석: '+str(report['auto_research'])
    return text
