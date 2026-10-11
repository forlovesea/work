"""Interactive launcher with optional Windows-encrypted credential storage."""
import getpass
import json
import os
from broker import TossBroker, BrokerError
from live import ROOT, main, load_config, SafetyStop, process_lock


def launch(etf=False):
    print('토스증권 자동매매 설정 · 일/주/월 각각 10%는 목표이며 수익 보장이 아닙니다.')
    with process_lock(ROOT/'runtime'/'bot.lock'):
        from credentials import load_environment,save_credentials,KEYS
        load_environment()
        path=ROOT/('etf_config.json' if etf else 'live_config.json')
        config=json.loads(path.read_text(encoding='utf-8-sig'))
        if not etf and not config['symbol']:
            config['symbol']=input('자동매매할 국내 보통주 6자리 종목코드: ').strip().upper()
            import re
            if not re.fullmatch('[A-Z0-9]{6}',config['symbol']):
                raise SafetyStop('올바른 6자리 종목코드가 필요합니다.')
            path.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        config=load_config(path)
        for key,label in [('TOSS_CLIENT_ID','Client ID'),('TOSS_CLIENT_SECRET','Client Secret')]:
            if not os.environ.get(key):
                os.environ[key]=getpass.getpass(label+' (화면 비표시/평문 저장 없음): ').strip()
        if etf:
            print('자동 수집용 최초 인증 설정입니다. CSV나 종목 목록은 필요하지 않습니다.')
            for key in ('KRX_ID','KRX_PW','DART_API_KEY','NAVER_CLIENT_ID','NAVER_CLIENT_SECRET'):
                if not os.environ.get(key): os.environ[key]=getpass.getpass(key+' (비표시): ').strip()
        broker=TossBroker()
        accounts=broker.get('accounts')
        eligible=[str(a['accountSeq']) for a in accounts if a['accountType']=='BROKERAGE']
        print('선택 가능한 종합매매 accountSeq:', ', '.join(eligible))
        account=os.environ.get('TOSS_ACCOUNT_SEQ') or input('사용할 accountSeq (계좌번호 아님): ').strip()
        if account not in eligible:
            raise SafetyStop('선택한 계좌를 찾을 수 없습니다.')
        broker.account=account
        os.environ['TOSS_ACCOUNT_SEQ']=account
        if etf and not (ROOT/'runtime'/'credentials.dpapi').exists():
            if input('다음 실행부터 입력하지 않도록 Windows 암호화 저장? [Y/n]: ').strip().lower() in ('','y','yes'):
                save_credentials({k:os.environ.get(k,'') for k in KEYS})
        target='코스닥 관련 ETF 순자산 상위 최대 20개 → 조건 충족 1개' if etf else config['symbol']
        print(f"대상 {target} / 운용 원금 {config['capital']:,}원 / 1회 매수 최대 {config['max_order_won']:,}원")
        print(f"손절 {config['stop_loss']:.0%}, 일 손실 중단 {config['daily_loss_limit']:.0%}, 최대 낙폭 중단 {config['max_drawdown']:.0%}")
        print('기본: 읽기 전용 점검. ETF 모드는 자동 수집을 포함해 연속 실행합니다. 실제 주문은 LIVE를 입력하세요.')
        mode=input('실행 모드 [Enter=점검 / LIVE=실제 자동주문]: ').strip()
        if mode not in ('','LIVE'):
            raise SafetyStop('실행을 취소했습니다.')
    main((['--etf'] if etf else [])+(['--live'] if mode=='LIVE' else ([] if etf else ['--once'])),broker=broker)


if __name__=='__main__':
    try:
        import argparse
        parser=argparse.ArgumentParser()
        parser.add_argument('--etf',action='store_true')
        launch(etf=parser.parse_args().etf)
    except KeyboardInterrupt:
        print('프로세스 중지. 기존 미체결 주문/보유 주식은 토스에서 확인하세요.')
    except (SafetyStop,BrokerError,KeyError,ValueError,OSError,TypeError,EOFError) as exc:
        print('중단:',str(exc) if isinstance(exc,(SafetyStop,BrokerError)) else type(exc).__name__)
        print('주문을 자동 재시도하지 않습니다. 토스 주문 내역과 runtime 기록을 확인하세요.')
        raise SystemExit(1)
