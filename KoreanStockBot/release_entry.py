"""Shared executable entry; filename determines GUI or worker role."""
import argparse
import json
import sys
from pathlib import Path


def main():
    name=Path(sys.executable).stem.lower().split('_v',1)[0]
    if '--self-test' in sys.argv:
        # Offline packaging check: no credentials read and no network calls.
        from app_paths import ROOT,worker_command
        from engine import PaperEngine,demo_bars
        from live import load_config
        from auto_data import normalize_catalog
        from credentials import crypt
        bot=PaperEngine()
        for bar in demo_bars():bot.step(bar)
        load_config(ROOT/'etf_config.json')
        if crypt(crypt(b'packaging-check'),decrypt=True)!=b'packaging-check':raise RuntimeError('DPAPI failed')
        import importlib.util
        assert importlib.util.find_spec('pykrx') is not None
        import pandas,numpy
        from research_sources import NEWS_URL
        assert NEWS_URL=='https://naverapihub.apigw.ntruss.com/search/v1/news'
        assert (ROOT/'trader.exe').exists() and (ROOT/'research.exe').exists()
        print(json.dumps({'status':'PASS','worker':name,'root':str(ROOT),'bars':len(bot.equity),'news_provider':NEWS_URL,'command':worker_command('live')},ensure_ascii=False))
        return
    if '--candidate-gui-smoke' in sys.argv:
        from scope_gui_smoke import run
        run()
        return
    if '--stock-candidate-gui-smoke' in sys.argv:
        from stock_candidate_gui_smoke import run
        run()
        return
    if '--account-gui-smoke' in sys.argv:
        from account_selector_smoke import run
        run()
        return
    if '--diagnostics-gui-smoke' in sys.argv:
        from diagnostics_gui_smoke import run
        run()
        return
    if '--gui-smoke' in sys.argv:
        from gui_smoke import smoke
        for mode in ('paper','etf','stock'):smoke(mode)
        print('PASS: packaged GUI modes, graph and calendar')
        return
    if name=='trader':
        from live import main as trade_main
        trade_main()
    elif name=='research':
        from auto_research import worker
        parser=argparse.ArgumentParser()
        parser.add_argument('--worker',action='store_true',required=True)
        parser.add_argument('--as-of',required=True)
        parser.add_argument('--output',type=Path,required=True)
        args=parser.parse_args()
        raise SystemExit(worker(args.as_of,args.output))
    else:
        from app import gui
        gui('stock' if name=='koreanstockbotstock' else 'paper' if name=='koreanstockbotpaper' else 'etf')


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except Exception as exc:
        from candidate_feedback import failure
        if sys.stdout is not None and '--candidate-report' not in sys.argv:
            print(json.dumps({'status':'WORKER_ERROR','error_code':failure(exc)['code'],'error_type':type(exc).__name__}),flush=True)
        if '--candidate-report' in sys.argv:
            from candidate_feedback import failure
            print(json.dumps(failure(exc)),flush=True)
        from live import SafetyStop
        from broker import BrokerError
        safe=str(exc) if isinstance(exc,(SafetyStop,BrokerError)) else type(exc).__name__
        if sys.stdout is not None:
            print('STOP: '+safe)
            print('Check orders in Toss before restarting. No automatic resubmission.')
        else:
            import tkinter.messagebox
            tkinter.messagebox.showerror('실행 중단',safe+'\n토스 주문 내역을 확인하세요. 자동 재주문하지 않습니다.')
        raise SystemExit(1)
