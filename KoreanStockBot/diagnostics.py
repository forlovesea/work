"""Explain measured screening results without changing trading limits."""
from collections import Counter

REASONS={'UNSUPPORTED_STRUCTURE':'지원하지 않는 ETF 구조',
 'FINANCIAL_COVERAGE_BELOW_60_PERCENT':'재무 확인 비중 60% 미만',
 'WEAK_FINANCIALS':'재무점수 60% 미만','NO_RECENT_RELEVANT_NEWS':'최근 관련 뉴스 없음',
 'NEWS_RISK_KEYWORD':'뉴스 위험 키워드 감지'}
STATES={'STRUCTURE':'구조 제한','RESEARCH':'재무·뉴스 조건 미달','BUDGET':'1주 예산 부족',
 'QUOTE_STALE':'시세 유효시간 초과','QUOTE_UNAVAILABLE':'최신 원화 시세 미확인','CANDLES':'일봉 부족/기준일 불일치',
 'TREND':'상승 추세 미충족','ELIGIBLE':'재무·뉴스·예산·추세 통과','SELECTED':'후보 선택','NOT_CHECKED':'추가 검사 전','OUTSIDE_RANGE':'사용자 선택 대상 밖'}


def won(value):return f'{float(value):,.0f}원'


def selection_text(details,limit=3):
    if not details or 'budget' not in details:
        return '상세 수치 확인 전 자료 조회가 중단되었습니다. 자료 수집 상태를 확인하세요.'
    rows=details.get('rows',[]); counts=Counter(row['state'] for row in rows)
    text=[f"신규 매수 범위 {details.get('min_rank',1)}~{details.get('max_rank',20)}위 · 후보 {len(rows)}개 · "+' / '.join(f'{STATES.get(k,k)} {v}개' for k,v in counts.items()),
          f"선별 예산 {won(details['budget'])} = 관리 현금 {won(details['cash'])}, 비중 {float(details['allocation'])*100:g}%, 주문 상한 {won(details['cap'])}, 계좌 현금매수가능 {won(details['power'])} 중 제한 적용",
          f"분석 기준일 {details['as_of']} · 생성 {details.get('generated_at') or '기록 없음'} · 토스 계좌 현금 조회 완료"]
    for row in rows[:limit]:
        line=f"{row['name']} ({row['symbol']}): {STATES.get(row['state'],row['state'])}"
        line+=f" · 재무 {float(row['score'])*100:.1f}% / 확인 비중 {float(row['coverage'])*100:.1f}% (각 기준 60%)"
        if row.get('news_count') is not None:line+=f" · 관련 뉴스 {row['news_count']}건"
        if row.get('reasons'):line+=' · '+', '.join(REASONS.get(r,r) for r in row['reasons'])
        if 'required' in row:line+=f" · 현재가 {won(row['price'])}, 1주 필요 추정 {won(row['required'])}, 부족 {won(row['shortfall'])}"
        if 'fast_ma' in row:line+=f" · {details['fast']}일 평균 {won(row['fast_ma'])} / {details['slow']}일 평균 {won(row['slow_ma'])}"
        if row['state']=='CANDLES':line+=f" · 일봉 {row['candles']}개 / 필요 {details['slow']}개, 마지막 {row.get('last_day') or '없음'}"
        text.append(line)
    if len(rows)>limit:text.append(f'나머지 {len(rows)-limit}개 사유는 아래 로그에서 확인하세요.')
    if counts['BUDGET']:text.append('안내: 1주 필요 추정은 현재가 × 1.01 + 10원입니다. 한도를 자동 변경하지 않습니다. 예산 이외의 조건도 통과해야 하므로 증액만으로 매수를 보장하지 않습니다.')
    if counts['RESEARCH'] or counts['QUOTE_UNAVAILABLE'] or counts['CANDLES']:
        text.append('안내: 데이터 부족이면 아래 수집 상태와 갱신 시각을 먼저 확인하세요. 키 재입력이나 조건 완화보다 오류 원인을 확인하는 것이 우선입니다.')
    if counts['TREND']:text.append('안내: 단기 평균이 장기 평균보다 높아질 때까지 기다리는 조건입니다. 대안 전략은 모의매매로 먼저 비교할 수 있습니다.')
    if not details.get('complete'):text.append('일부 검사만 완료된 결과입니다.')
    return '\n'.join(text)


def source_text(state):
    if not state:return '자료 수집 이력 없음 · 인증값 입력만으로 API 연결 성공을 의미하지 않습니다.'
    text=[f"자동 분석 {state.get('state','미확인')} · 기준일 {state.get('as_of','미확인')} · 기록 시각 {state.get('updated_at','미확인')}"]
    if state.get('stage'):text.append('수집 단계: '+state['stage']+' · 로그: '+state.get('log_file','research/logs/collection.log'))
    if state.get('error_code'):
        text.append('오류 분류: '+state['error_code']+' · HTTP '+str(state.get('http_status','해당 없음'))+' · 공급자 코드 '+str(state.get('provider_code','해당 없음')))
    for key,label in [('KRX','KRX ETF·구성정보'),('DART','DART 재무·기업정보'),('NAVER','NAVER 뉴스')]:
        row=state.get('sources',{}).get(key)
        progress=state.get('provider_stages',{}).get(key)
        if not row:
            status={'NOT_REQUESTED':'아직 요청 전 (앞 단계 중단 또는 해당 자료 불필요)',
                    'IN_PROGRESS':'첫 요청/분석 진행 중 · 아직 응답 확인 전','FAILED':'요청/분석 실패 · 로그 확인'}.get(progress,'상세 수집 이력 없음 / 이번 연결 성공 여부 미확인')
            if progress=='NOT_REQUESTED' and state.get('state')=='COLLECTION_FAILED':status='요청하지 못함 · 앞 단계 실패로 중단'
            text.append(label+': '+status);continue
        status={'network':'API 응답 수신','cache':'저장된 자료 사용','error':'조회 오류'}.get(row['state'],'미확인')
        text.append(f"{label}: {status} · API 성공 {row['network']}회 / 캐시 {row['cache']}회 / 오류 {row['errors']}회 · {row['checked_at']}")
    if 'candidates' in state:text.append(f"분석한 ETF {state['candidates']}개 / 재무·뉴스 통과 {state.get('eligible',0)}개 · 구성정보 누락 {len(state.get('composition_unavailable',[]))}개")
    text.append('캐시 사용은 현재 키의 인증 성공을 검증한 것이 아닙니다. READY는 분석 파일 완성 상태이며 모든 ETF 조건 통과를 뜻하지 않습니다.')
    return '\n'.join(text)
