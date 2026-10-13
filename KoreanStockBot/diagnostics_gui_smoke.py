"""Offline checkbox, persistence and ZIP export widget regression."""
import json
import tempfile
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from unittest.mock import patch
from live_gui import LivePanel,ROOT
from gui_smoke import descendants


def run():
    root=tk.Tk();root.withdraw()
    try:
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            (base/'etf_config.json').write_bytes((ROOT/'etf_config.json').read_bytes())
            with patch('live_gui.ROOT',base):
                parent=ttk.Frame(root);buttons=ttk.Frame(root)
                panel=LivePanel(root,parent,buttons,'etf',{'bg':'#111111','panel':'#222222','text':'#ffffff'},tk.StringVar(),lambda *args:None)
                check=next(w for w in descendants(parent) if isinstance(w,ttk.Checkbutton) and w.cget('text')=='진단 로그 파일 생성')
                check.invoke();assert panel.support_log.enabled
                assert json.loads((base/'runtime/diagnostics_settings.json').read_text())=={'enabled':True}
                panel.diagnostic('COLLECTION',state='COLLECTION_FAILED',error_code='LOCAL_FILE_ACCESS')
                export=next(w for w in descendants(parent) if isinstance(w,ttk.Button) and w.cget('text')=='공유용 진단 ZIP 저장')
                with patch('live_gui.filedialog.asksaveasfilename',return_value=str(base/'support.zip')):export.invoke()
                assert (base/'support.zip').exists()
                check.invoke();assert not panel.support_log.enabled
                before=panel.support_log.path.read_bytes();panel.diagnostic('STOP')
                assert before==panel.support_log.path.read_bytes()
                from types import SimpleNamespace
                from datetime import datetime
                from runtime_status import KST
                panel.child=SimpleNamespace(poll=lambda:None)
                panel.guidance_collection={'state':'COLLECTING_DATA','first_collection':True,'updated_at':datetime.now(KST).isoformat()}
                panel.update_guidance()
                assert panel.guidance_last[0]=='blue' and '첫 수집' in panel.guidance_title.cget('text')
                assert int(panel.guidance_frame.grid_info()['row'])==3
                assert panel.guidance_card.pack_info()['side']=='right'
                panel.guidance_collection['state']='COLLECTION_FAILED';panel.update_guidance()
                assert panel.guidance_last[0]=='red'
                panel.guidance_collection['state']='READY';panel.update_guidance()
                assert panel.guidance_last[0]=='green'
                panel.child=None
                # Repeat actual start callback against a finished collection snapshot.
                from credentials import KEYS
                from io import StringIO
                for attempt in range(2):
                    panel.stop_confirmed=True;panel.guidance_runtime='HOLD'
                    process=SimpleNamespace(poll=lambda:None,stdout=StringIO(''))
                    with patch.object(panel,'env',return_value={k:'test' for k in KEYS}),patch.object(panel,'spawn',return_value=process),patch('live_gui.threading.Thread'):
                        panel.start(False)
                    assert panel.guidance_last[0]=='blue'
                    assert '새 점검' in panel.guidance_title.cget('text')
                    assert not panel.stop_confirmed
                    panel.events.put(('log',json.dumps({'status':'BROKER_REQUEST','operation':'ORDERBOOK'})))
                    panel.poll()
                    assert '호가' in panel.guidance_title.cget('text')
                    panel.child=None
                for pending in root.tk.splitlist(root.tk.call('after','info')):root.after_cancel(pending)
        print('PASS: diagnostic checkbox, settings, readable log and ZIP export; no network/orders.')
    finally:root.destroy()


if __name__=='__main__':run()
