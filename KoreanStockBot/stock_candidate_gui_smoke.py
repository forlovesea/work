"""Offline end-to-end stock candidate selection UI."""
import io
import json
import tempfile
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from datetime import datetime
from live import ROOT,KST
from gui_smoke import descendants
from stock_candidates import binding,CHECK_NAMES

def run():
    from stock_candidate_gui import show
    root=tk.Tk();root.withdraw()
    try:
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);path=base/'live_config.json'
            config=json.loads((ROOT/'live_config.json').read_text());config['symbol']=''
            path.write_text(json.dumps(config))
            now=datetime.now(KST).isoformat()
            report=dict(status='STOCK_CANDIDATES',binding=binding('1',config),checked_at=now,as_of='2026-10-12',
                budget='9000',power='30000',screened=1,excluded={},errors=[],rows=[dict(symbol='012345',name='테스트',category='IT',
                industry='전기·전자',price='3000',price_at=now,required='3040',quantity=2,
                report=dict(checks={k:True for k in CHECK_NAMES},report_end='2026-06-30',metrics={k:'100000000' for k in ('revenue','operating_profit','net_profit','assets','equity','operating_cash')},sources=[],fs_div='CFS'))])
            panel=SimpleNamespace(root=root,config=config,config_path=path,querying=False,closing=False,
                active=lambda:False,log_line=lambda text:None,diagnostic=lambda *a,**k:None,
                env=lambda:{k:'1' for k in ('TOSS_CLIENT_ID','TOSS_CLIENT_SECRET','TOSS_ACCOUNT_SEQ','KRX_ID','KRX_PW','DART_API_KEY')})
            proc=SimpleNamespace(stdout=io.StringIO(json.dumps(report)+'\n'),wait=lambda:0)
            panel.spawn=lambda args,env:proc
            with patch('stock_candidate_gui.ROOT',base):
                show(panel);window=panel.stock_window
                buttons={w.cget('text'):w for w in descendants(window) if isinstance(w,ttk.Button)}
                ready_provider=window.stock_context['env_provider']
                window.stock_context['env_provider']=lambda:{}
                with patch('stock_candidate_gui.messagebox.showwarning') as warning,patch.object(panel,'spawn') as spawn:
                    buttons['예산·재무 기준 조회'].invoke()
                    warning.assert_called_once();spawn.assert_not_called()
                    assert 'DART 인증키' in warning.call_args.args[1]
                window.stock_context['env_provider']=ready_provider
                buttons['예산·재무 기준 조회'].invoke()
                deadline=time.monotonic()+5
                while panel.querying and time.monotonic()<deadline:root.update();time.sleep(.02)
                assert not panel.querying
                tree=next(w for w in descendants(window) if isinstance(w,ttk.Treeview))
                assert tree.get_children()==('012345',)
                tree.selection_set('012345');tree.event_generate('<<TreeviewSelect>>');root.update()
                with patch('stock_candidate_gui.messagebox.showinfo'):
                    buttons['선택 종목 적용'].invoke()
                assert json.loads(path.read_text())['symbol']=='012345'
                assert not (base/'runtime/live_state.json').exists()
                # Settings integration fills a draft field without silently saving it.
                path.write_text(json.dumps(config))
                draft=tk.StringVar(value='')
                proc.stdout=io.StringIO(json.dumps(report)+'\n')
                show(panel,env_provider=panel.env,on_select=draft.set)
                window=panel.stock_window
                buttons={w.cget('text'):w for w in descendants(window) if isinstance(w,ttk.Button)}
                buttons['예산·재무 기준 조회'].invoke()
                deadline=time.monotonic()+5
                while panel.querying and time.monotonic()<deadline:root.update();time.sleep(.02)
                tree=next(w for w in descendants(window) if isinstance(w,ttk.Treeview))
                tree.selection_set('012345');buttons['선택 종목 적용'].invoke()
                assert draft.get()=='012345'
                assert json.loads(path.read_text())['symbol']==''
        print('PASS: stock category table, leading-zero symbol selection, config save; no network/orders.')
    finally:root.destroy()

if __name__=='__main__':run()
