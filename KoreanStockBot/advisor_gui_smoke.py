"""Offline UI smoke check; never reads credentials or connects to a broker."""
import json
import tempfile
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from advisor import DEFAULTS
from advisor_gui import AdvisorWindow
from live import now_kst
from credentials import KEYS


def check_credentials(app, root, directory):
    synthetic={key:'synthetic' for key in KEYS}
    synthetic['TOSS_ACCOUNT_SEQ']='999'
    with patch('advisor_gui.load_credentials',return_value=synthetic):
        app.credentials()
        window=app.settings_window
        app.credentials()
        assert app.settings_window is window
    widgets=window.winfo_children()
    buttons={w.cget('text'):w for w in widgets if isinstance(w,ttk.Button)}
    assert {'설정 템플릿 생성','템플릿 암호화 변환','설정 파일 불러오기','👁 보기'} <= buttons.keys()
    selector=next(w for w in widgets if isinstance(w,ttk.Combobox))
    entries=[w for w in widgets if isinstance(w,ttk.Entry) and not isinstance(w,ttk.Combobox)]
    assert selector.get()=='' and all(w.cget('show')=='●' for w in entries)
    toggle=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='👁 보기')
    toggle.invoke();assert entries[0].cget('show')==''
    template=Path(directory)/'template.json'
    with patch('advisor_gui.filedialog.asksaveasfilename',return_value=str(template)):
        buttons['설정 템플릿 생성'].invoke()
    assert template.exists()
    with patch('advisor_gui.filedialog.askopenfilename',return_value='synthetic.ksbkey'), patch('settings_file.load_settings',return_value={'credentials':synthetic,'symbol':''}):
        buttons['설정 파일 불러오기'].invoke()
    assert all(w.cget('show')=='●' for w in entries) and selector.get()==''
    def query(accounts):
        with patch('advisor_gui.TossBroker') as broker:
            broker.return_value.get.return_value=[{'accountSeq':n,'accountType':'BROKERAGE'} for n in accounts]
            buttons['계좌 조회'].invoke()
            root.after(250,root.quit);root.mainloop()
    with patch('advisor_gui.save_credentials') as save:
        buttons['암호화 저장'].invoke();save.assert_not_called()
        query(['123']);assert selector.get()=='123'
        entries[0].insert('end','changed');assert selector.get()==''
        buttons['암호화 저장'].invoke();save.assert_not_called()
        query(['123','456']);assert selector.get()==''
        selector.set('456');buttons['암호화 저장'].invoke()
        assert save.call_args.args[0]['TOSS_ACCOUNT_SEQ']=='456'
        assert save.call_args.args[1]==Path(directory)/'advisor/credentials.dpapi'


def run():
    with tempfile.TemporaryDirectory() as directory:
        root=tk.Tk();root.withdraw()
        try:
            app=AdvisorWindow(root,Path(directory));root.update_idletasks()
            assert len(app.book.tabs())==4
            assert str(app.approve_button.cget('state'))=='disabled'
            check_credentials(app,root,directory)
            report=dict(checked_at=now_kst().isoformat(),scope='테스트',rows=[dict(symbol='123456',name='테스트 종목',score=100,
                reason='검증 예시',eligible=True,news={'count':1,'risk':False,'articles':[]},
                report={'report_end':'2026-06-30','checks':{},'sources':[]})])
            app.render_report(report);assert app.tree.exists('123456')
            app.render_paper(dict(settings=DEFAULTS,equity='31000',drawdown='.01',symbol='',quantity=0,trades=[],
                                 history=[{'equity':'30000'},{'equity':'31000'}]))
            assert '+3.33%' in app.metrics.get()
            assert app.chart.find_all()
            calls=[];app.service=SimpleNamespace(c=DEFAULTS,approve=lambda value:calls.append(value))
            app.offer=dict(id='approval-test',symbol='123456',side='BUY',quantity=2,price='3000',reason='TEST',created=now_kst().isoformat())
            text=app.offer_text(app.offer)
            assert '6,000원' in text and '120초' in text
            with patch('advisor_gui.messagebox.askyesno',return_value=False):app.approve()
            assert calls==[] and app.offer is not None
            def execute(kind,fn):fn()
            app.task=execute
            with patch('advisor_gui.messagebox.askyesno',return_value=True):app.approve()
            assert calls==['approval-test'] and app.offer is None
            app.approve();assert calls==['approval-test']
        finally:root.destroy()
    print('PASS: advisor tabs, recommendation, paper chart, explicit single approval; no broker access')


if __name__=='__main__':run()
