"""Exercise account selection using synthetic accounts; no network or credentials."""
import queue
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from button_theme import button_style, install_buttons
from live_gui import LivePanel


def run():
    root=tk.Tk(); root.withdraw()
    style=ttk.Style(root); style.theme_use('clam')
    style.configure('TEntry',padding=7)
    install_buttons(root,style)
    panel=LivePanel.__new__(LivePanel)
    panel.root=root; panel.mode='stock'; panel.colors={'bg':'#111111'}
    panel.child=None; panel.querying=False; panel.events=queue.Queue()
    panel.config={'symbol':'005930'}
    with patch.object(panel,'env',return_value={'TOSS_CLIENT_ID':'test','TOSS_CLIENT_SECRET':'test'}):
        panel.settings()
    window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
    widgets=window.winfo_children()
    labels={w.cget('text') for w in widgets if isinstance(w,ttk.Button)}
    assert {'설정 템플릿 생성','템플릿 암호화 변환','설정 파일 불러오기'} <= labels
    selector=next(w for w in widgets if isinstance(w,ttk.Combobox))
    query=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='계좌 조회')
    assert query.cget('style')==button_style('계좌 조회')
    height_checks=[ttk.Button(root,text='height check',style=name)
                   for name in ('TButton','Primary.TButton','Success.TButton',
                                'Danger.TButton','Violet.TButton','Compact.TButton')]
    import tempfile
    from pathlib import Path
    import json
    file_buttons={w.cget('text'):w for w in widgets if isinstance(w,ttk.Button)}
    with tempfile.TemporaryDirectory() as folder:
        source=Path(folder)/'template.json'; sealed=Path(folder)/'template.ksbkey'
        with patch('live_gui.filedialog.asksaveasfilename',return_value=str(source)):
            file_buttons['설정 템플릿 생성'].invoke()
        data=json.loads(source.read_text(encoding='utf-8'))
        data['credentials'].update(TOSS_CLIENT_ID=' test ',TOSS_CLIENT_SECRET=' test ')
        source.write_text(json.dumps(data),encoding='utf-8')
        with patch('live_gui.filedialog.askopenfilename',return_value=str(source)), \
             patch('live_gui.filedialog.asksaveasfilename',return_value=str(sealed)), \
             patch('live_gui.messagebox.askyesno',return_value=False):
            file_buttons['템플릿 암호화 변환'].invoke()
        assert sealed.exists() and source.exists()
        with patch('live_gui.filedialog.askopenfilename',return_value=str(sealed)):
            file_buttons['설정 파일 불러오기'].invoke()
        assert selector.get()==''
    from types import SimpleNamespace
    import json
    def lookup(ids):
        proc=SimpleNamespace(returncode=0,communicate=lambda **kw:(json.dumps([
            {'accountSeq':i,'accountType':'BROKERAGE'} for i in ids]),None))
        with patch.object(panel,'spawn',return_value=proc):
            query.invoke()
            event=panel.events.get(timeout=5)
        panel.querying=False
        event[1](event[2],event[3])
    assert str(selector.cget('state'))=='readonly'
    lookup([101]); assert selector.get()=='101'
    lookup([101,202]); assert selector.get()==''
    assert tuple(selector.cget('values'))==('101','202')
    selector.current(1); assert selector.get()=='202'
    entry=next(w for w in widgets if isinstance(w,ttk.Entry) and not isinstance(w,ttk.Combobox))
    eye=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='👁 보기')
    root.update_idletasks()
    for button in [eye,*height_checks]:
        assert button.winfo_reqheight()==entry.winfo_reqheight(), (
            f"{button.cget('style')} height {button.winfo_reqheight()} "
            f"does not match entry height {entry.winfo_reqheight()}")
    assert entry.cget('show')=='●'
    eye.invoke(); assert entry.cget('show')==''
    eye.invoke(); assert entry.cget('show')=='●'
    entry.insert(0,' \t'); entry.insert('end','\t ')
    assert selector.get()=='202', 'Outer whitespace must not invalidate the selected account'
    entry.insert('end','changed')
    assert selector.get()=='' and not selector.cget('values')
    lookup([]); assert selector.get()==''
    root.destroy()
    print('PASS: single/multiple/empty accounts and credential change; no network/orders.')


if __name__=='__main__': run()
