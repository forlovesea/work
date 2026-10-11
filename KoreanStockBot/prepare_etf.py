"""Interactive research setup; secrets are entered locally and never written."""
import getpass
import os
from pathlib import Path
from live import ROOT, SafetyStop, process_lock
from build_research import build


def prepare():
    print('코스닥 관련 ETF 순자산 상위 최대 20개 분석')
    print('ETF_GUIDE.md 형식에 맞춘 공식 순자산·편입내역 CSV가 필요합니다.')
    catalog=Path(input('전체 ETF 순자산 CSV 경로: ').strip().strip('"'))
    composition=Path(input('편입 기업 CSV 경로: ').strip().strip('"'))
    as_of=input('공식 자료 기준일 YYYY-MM-DD (거래 시 전 영업일): ').strip()
    if not catalog.is_file() or not composition.is_file(): raise SafetyStop('CSV 파일을 찾을 수 없습니다.')
    for name in ('DART_API_KEY','NAVER_CLIENT_ID','NAVER_CLIENT_SECRET'):
        if not os.environ.get(name): os.environ[name]=getpass.getpass(name+' (비표시/파일 저장 안 함): ').strip()
    with process_lock(ROOT/'research'/'build.lock'):
        book=build(catalog,composition,as_of,ROOT/'research'/'latest.json')
    print('분석 완료:',len(book['universe']),'개. research/latest_summary.csv에서 순위와 보류사유를 확인하세요.')


if __name__=='__main__':
    try: prepare()
    except (SafetyStop,OSError,ValueError,KeyError,TypeError,EOFError) as exc:
        print('분석 중단:',str(exc) if isinstance(exc,SafetyStop) else type(exc).__name__)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print('분석 취소. 실제 주문은 하지 않았습니다.')
