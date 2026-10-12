"""Safe, evidence-based explanations for candidate queries."""
from collections import Counter
from datetime import datetime
import re
from broker import BrokerError


def market_context(calendar,now):
    today=calendar.get('today',{})
    if today.get('date')!=now.date().isoformat():return '시장 운영일 확인 불가'
    session=(today.get('integrated') or {}).get('regularMarket')
    if not session:return '휴장일'
    try:
        if now<datetime.fromisoformat(session['startTime']):return '정규장 개장 전'
        if session.get('endTime') and now>=datetime.fromisoformat(session['endTime']):return '정규장 마감 후'
        if now>=datetime.fromisoformat(session['singlePriceAuctionStartTime']):return '종가 단일가 시작 이후 · 봇 매매시간 종료'
        return '정규장 운영 시간'
    except (KeyError,ValueError,TypeError):return '시장 운영시간 확인 불가'


def failure(exc,market=None):
    raw=str(exc)
    code='UNVERIFIED'
    reason='응답 형식 또는 실행 상태를 확인하지 못했습니다.'
    action='읽기 전용 점검의 상태와 수집 로그를 확인한 뒤 다시 조회하세요.'
    if isinstance(exc,FileNotFoundError):
        code='MISSING_FILE';reason='필요한 분석 파일 또는 실행파일이 없습니다.'
        action='읽기 전용 점검에서 자동 수집 완료(READY)를 확인하세요. 실행파일은 배포 폴더 전체를 압축 해제하세요.'
    elif raw in ('Research stale: regenerate using previous business-day universe','Stale assessment'):
        code='RESEARCH_STALE';reason='재무·뉴스 분석 자료가 만료됐거나 분석 기준 거래일이 맞지 않습니다.'
        action='읽기 전용 점검에서 자동 수집 완료(READY)를 확인한 뒤 중지하고 다시 조회하세요.'
    elif isinstance(exc,BrokerError):
        match=re.search(r'Toss HTTP (\d{3});',raw)
        status=int(match.group(1)) if match else None
        code='BROKER_ERROR';reason='증권사 연결 또는 응답 확인에 실패했습니다.'
        action='인터넷 연결과 읽기 전용 점검의 연결 상태를 확인하세요.'
        if status in (401,403):
            code='AUTH_OR_PERMISSION';reason=f'증권사가 인증 또는 접근을 거부했습니다(HTTP {status}).'
            action='토스 인증키·이용 권한·접속 IP 설정을 확인하세요. 이 응답만으로 잘못된 항목 하나를 단정할 수는 없습니다.'
        elif status:
            reason=f'증권사 API가 오류를 반환했습니다(HTTP {status}).'
    elif raw=='Cash buying power below configured capital':
        code='CAPITAL';reason='계좌 원화 주문 가능액이 설정된 운용 원금보다 적어 초기 점검을 통과하지 못했습니다.'
        action='계좌 주문 가능액과 운용 원금 설정을 확인하세요.'
    elif raw in ('Selected brokerage account not found','Set TOSS_ACCOUNT_SEQ locally; --accounts lists available selectors'):
        code='ACCOUNT';reason='설정한 계좌를 확인하지 못했습니다.'
        action='인증·계좌 설정에서 계좌를 다시 조회하고 선택하세요.'
    return dict(status='CANDIDATE_ERROR',code=code,reason=reason,action=action,market=market)


def unavailable_message(report):
    if report.get('status')=='CANDIDATE_ERROR':
        market=report.get('market')
        return ('시장 상태: '+market+'\n\n' if market else '')+report['reason']+'\n\n'+report['action']
    details=report['selection_details']
    rows=details.get('rows',[])
    if any(r['state'] in ('ELIGIBLE','SELECTED') for r in rows):return None
    counts=Counter(r['state'] for r in rows)
    labels={'QUOTE_STALE':'허용 시간을 초과한 과거 시세','QUOTE_UNAVAILABLE':'최신 원화 시세 미확인',
            'RESEARCH':'재무·뉴스 조건 미달','STRUCTURE':'지원하지 않는 ETF 구조',
            'BUDGET':'1주 매수 예산 부족','TREND':'상승 추세 미충족','CANDLES':'일봉 부족 또는 기준일 불일치',
            'OUTSIDE_RANGE':'사용자 선택 대상 밖','NOT_CHECKED':'검사 미완료'}
    lines=['현재 조건으로 제안할 후보가 없습니다.','시장 상태: '+details.get('market','미확인'),
           f"적용 예산: {float(details.get('budget',0)):,.0f}원",'']
    lines.extend(f'{labels.get(key,"기타 확인 필요")}: {count}종목' for key,count in counts.items())
    if not rows:lines.append('분석 가능한 ETF 목록이 없습니다.')
    if counts['QUOTE_STALE']:
        lines.append('\n마감 후·휴장 중에는 마지막 거래 시세가 오래되어 최신 시세 조건을 통과하지 못할 수 있습니다. 장외 종가 기반 추천은 아직 지원하지 않습니다. 다음 정규장에 다시 조회하세요.')
    elif counts['QUOTE_UNAVAILABLE']:
        lines.append('\n시세 응답이나 시각을 확인하지 못했습니다. 시세 수신·통신 상태를 확인하고 다시 조회하세요.')
    if counts['RESEARCH'] or counts['CANDLES']:
        lines.append('\n종목별 제외 사유와 자동 수집 상태를 확인하세요. 데이터가 있어도 분석 조건에 미달할 수 있습니다.')
    if counts['BUDGET']:lines.append('\n종목별 1주 필요액과 적용 예산을 비교하세요. 매수 한도는 자동 변경하지 않습니다.')
    if counts['TREND']:lines.append('\n현재 추세 조건이 충족될 때까지 대기합니다.')
    lines.append('\n후보가 없다는 것만으로 인증키 오류를 의미하지는 않습니다.')
    return '\n'.join(lines)
