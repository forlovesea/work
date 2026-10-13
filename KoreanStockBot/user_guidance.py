"""User actions based on observed state; colors never imply trade permission."""
from datetime import datetime
from runtime_status import KST

COLORS={'blue':('#102c48','#8dc8ff'),'yellow':('#3a3012','#ffe08a'),
        'red':('#401d24','#ffacb5'),'green':('#15392b','#91e4b5'),'gray':('#252a32','#d4dae3')}
BUSY={'COLLECTING_KRX','COLLECTING_DATA','ANALYZING_FINANCIALS_AND_NEWS'}


def guidance(*,active=False,querying=False,stopping=False,confirmed=False,unverified=False,
             runtime='',collection=None,age=0,now=None,operation=''):
    state=collection or {};code=state.get('state');now=now or datetime.now(KST)
    if unverified:return 'red','종료 확인 필요','정상 중지를 확인하지 못했습니다. 토스 앱의 미체결·보유분을 확인하고 진단 ZIP을 저장하세요.'
    if stopping and active:return 'red','중지 처리 중','중지 요청을 받았습니다. 주문 정리 확인이 끝날 때까지 기다려 주세요.'
    if querying:return 'blue','조회 진행 중','계좌·시세를 확인하고 있습니다. 결과가 나올 때까지 잠시 기다려 주세요.'
    if confirmed and not active:return 'red','작업 중지 완료','요청대로 작업을 멈췄습니다. 다시 확인하려면 읽기 전용 점검을 시작하세요.'
    if active and runtime=='INITIALIZING':
        return 'blue','새 점검 시작 · 연결 확인 중','이전 수집 결과와 별개로 인증·계좌·기존 주문을 다시 확인합니다. 잠시 기다려 주세요.'
    if runtime in ('BROKER_CONNECTION_WAIT','WORKER_ERROR') and active:
        return 'red','연결·작업 확인 필요','인터넷 연결과 하단 오류 내용을 확인하세요. 반복되면 진단 ZIP을 저장해 주세요.'
    if code in ('COLLECTION_FAILED','WORKER_TIMEOUT_OR_DATE_CHANGED'):
        return 'red','자료 수집 문제 발생','실패 단계와 오류 사유를 확인하세요. 자동 재시도 후에도 반복되면 공유용 진단 ZIP을 저장해 주세요.'
    if code=='COLLECTION_STOPPED':
        return 'red','자료 수집 중단','중지·종료 요청으로 수집을 멈췄습니다. 다시 수집하려면 읽기 전용 점검을 시작하고 완료까지 기다려 주세요.'
    if code in BUSY:
        if not active:return 'red','이전 수집 미완료','현재 작업은 실행 중이 아닙니다. 읽기 전용 점검을 시작하면 저장된 캐시를 재사용합니다.'
        try:stale=(now-datetime.fromisoformat(state['updated_at'])).total_seconds()>120
        except (KeyError,ValueError,TypeError):stale=True
        if stale:return 'yellow','수집 응답 지연 확인 중','진행 기록이 2분 이상 갱신되지 않았습니다. 자동 시간 제한 확인을 기다리세요. 오류로 바뀌면 진단 ZIP을 저장하세요.'
        progress=state.get('progress',{})
        counts=(f"재무 {progress.get('financial_done',0)}/{progress.get('financial_total',0)}개 · 뉴스 {progress.get('news_done',0)}/{progress.get('news_total',0)}건" if progress else 'KRX 종목·구성 정보를 먼저 확인하고 있습니다.')
        title='첫 수집 진행 중—분석 완료 대기' if state.get('first_collection') else '자료 수집 진행 중 · 기다려 주세요'
        return 'blue',title,counts+'\n진행 숫자가 증가하면 정상 진행입니다. 첫 수집은 수분 이상 걸릴 수 있으며 완료 전에는 후보 분석을 기다립니다.'
    if active and age>90:return 'yellow','작업 응답 대기','최근 상태 응답이 늦어지고 있습니다. 잠시 기다리되 지연이 계속되면 진단 ZIP을 저장하세요.'
    if active and runtime in ('BROKER_REQUEST','BROKER_RESPONSE'):
        from support_log import MEANINGS
        phase=MEANINGS.get(operation,'계좌·시세')
        return 'blue',phase+' 확인 중',('응답을 기다리고 있습니다.' if runtime=='BROKER_REQUEST' else '응답을 받았습니다. 다음 검사를 진행합니다.')+'\n이전 자료 수집 완료와 현재 점검 진행은 별개입니다. 잠시 기다려 주세요.'
    if active and runtime in ('RESEARCH_FIRST_COLLECTION','RESEARCH_UPDATING'):
        return 'blue','자료 준비 중—분석 완료 대기','저장된 분석 자료를 확인하거나 갱신하고 있습니다. 새 진행 표시를 기다려 주세요.'
    if active and runtime in ('HALTED','ENTRY_PAUSED','NO_ELIGIBLE_AFFORDABLE_ETF','SPREAD_TOO_WIDE','RESEARCH_OR_CANDIDATE_DATA_UNAVAILABLE'):
        from runtime_status import describe_status
        import json
        return 'yellow',describe_status(json.dumps({'status':runtime})).split('\n')[0],'현재 점검 결과입니다. 아래 상세 사유를 확인하세요. 프로그램은 다음 점검 주기에 다시 확인합니다.'
    if active and runtime in ('HOLD','OUTSIDE_REGULAR_SESSION','SESSION_ENDED'):
        return 'green','이번 점검 완료 · 다음 확인 대기','현재 점검을 마쳤습니다. 실행 중에는 주기적으로 다시 확인합니다. 시장 시간·조건에 따라 주문 없이 대기할 수 있습니다.'
    if code=='READY':
        if active and runtime=='RESEARCH_OR_CANDIDATE_DATA_UNAVAILABLE':return 'yellow','분석 자료 확인 필요','수집 완료 기록은 있지만 후보 자료를 확인하지 못했습니다. 다음 점검에서도 반복되면 진단 ZIP을 저장하세요.'
        try:fresh=0<=(now-datetime.fromisoformat(state['updated_at'])).total_seconds()<7200
        except (KeyError,ValueError,TypeError):fresh=False
        if not fresh:return 'yellow','자료 갱신 필요','저장된 완료 기록이 오래됐습니다. 읽기 전용 점검에서 최신 수집 완료를 확인하세요.'
        excluded=len(state.get('composition_unavailable',[]))
        return 'green','자료 수집 완료',('미확인 구성정보 '+str(excluded)+'개는 제외했습니다. ' if excluded else '')+('중지 완료 후 최신 계좌·시세 조회를 눌러 후보를 확인하세요.' if active else '최신 계좌·시세 조회로 후보를 확인하세요.')+' 완료는 매수 조건 통과나 수익 보장을 뜻하지 않습니다.'
    if code=='NO_SUPPORTED_ETF':return 'yellow','분석 대상 확인 필요','지원 구조의 ETF가 없습니다. 구조 제외 사유와 진단 기록을 확인하세요.'
    if confirmed and not active:return 'red','작업 중지 완료','요청대로 작업을 멈췄습니다. 다시 확인하려면 읽기 전용 점검을 시작하세요.'
    if active and runtime in ('INITIALIZING',''):return 'blue','연결 준비 중','계좌와 기존 주문 상태를 확인하고 있습니다. 잠시 기다려 주세요.'
    if active and runtime in ('RESEARCH_FIRST_COLLECTION','RESEARCH_UPDATING'):
        return 'blue','첫 수집 진행 중—분석 완료 대기','자료를 준비하고 있습니다. 중지하지 않고 진행 숫자와 완료 표시를 기다려 주세요.'
    if active and runtime=='RESEARCH_OR_CANDIDATE_DATA_UNAVAILABLE':return 'yellow','분석 자료 확인 필요','아직 후보를 분석할 수 없습니다. 자동 수집 상태와 진단 기록을 확인하세요.'
    if active:return 'blue','상태 확인 중','프로그램이 계좌·매매 조건을 확인하고 있습니다. 조건 미충족으로 대기하는 것은 수집 실패와 다릅니다.'
    return 'gray','실행 대기','읽기 전용 점검으로 시작하세요. 진단 로그를 켜 두면 문제가 생겼을 때 확인하기 쉽습니다.'
