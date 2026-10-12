"""Synthetic candidate-selection GUI check; never connects to an account."""
import json
import tempfile
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from unittest.mock import patch
from live_gui import LivePanel
from datetime import datetime,timezone
from types import SimpleNamespace
import time


def run():
    root=tk.Tk();root.withdraw()
    try:
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);config=base/'config.json';config.write_text('{}')
            panel=LivePanel.__new__(LivePanel)
            panel.root=root;panel.child=None;panel.querying=False;panel.closing=False;panel.colors={'bg':'#151618'}
            panel.config_path=config;panel.log_line=lambda text:None
            report=dict(checked_at=datetime.now(timezone.utc).isoformat(),complete=True,budget='9000',power='30000',cash='30000',rows=[
                dict(symbol='123456',name='테스트 ETF',rank=1,state='ELIGIBLE',price='3000',required='3040',score=.8),
                dict(symbol='654321',name='예산 초과 ETF',rank=2,state='BUDGET',price='12000',required='12130',score=.9)])
            class Proc:
                returncode=0
                def communicate(self,timeout=None):return json.dumps({'status':'CANDIDATE_REPORT','selection_details':report}),None
            panel.spawn=lambda args,env:Proc()
            with patch('candidate_gui.ROOT',base),patch.object(panel,'env',return_value={'TOSS_ACCOUNT_SEQ':'123'}):
                panel.scope_settings()
                popup=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
                deadline=time.monotonic()+5
                while panel.querying and time.monotonic()<deadline:root.update();time.sleep(.02)
                assert not panel.querying
                from gui_smoke import descendants
                widgets=list(descendants(popup))
                assert not any(isinstance(w,ttk.Combobox) for w in widgets)
                tree=next(w for w in widgets if isinstance(w,ttk.Treeview))
                assert len(tree.get_children())==2
                root.deiconify();popup.deiconify();root.update()
                tree.event_generate('<ButtonRelease-1>',x=20,y=tree.bbox('123456')[1]+5)
                button=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='선택한 종목 적용')
                button.invoke()
                data=json.loads((base/'runtime'/'etf_scope.json').read_text(encoding='utf-8'))
                assert data['symbols']==['123456']
                report['market']='정규장 마감 후'
                for row in report['rows']:row['state']='QUOTE_STALE'
                with patch('candidate_gui.messagebox.showinfo') as notice:
                    panel.scope_settings()
                    deadline=time.monotonic()+5
                    while panel.querying and time.monotonic()<deadline:root.update();time.sleep(.02)
                    notice.assert_called_once()
                    assert '과거 시세: 2종목' in notice.call_args.args[1]
        print('PASS: candidate report, selection and persistence. No account/network/orders.')
    finally:root.destroy()


if __name__=='__main__':run()
