"""Local widget smoke check. No credentials, networking or orders are used."""
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from app import gui


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def smoke(mode):
    failures=[]
    def run(root,*args,**kwargs):
        from app_version import VERSION
        assert 'v'+VERSION in root.title()
        root.withdraw()
        def check():
            try:
                widgets=list(descendants(root))
                buttons={str(w.cget('text')):w for w in widgets if isinstance(w,ttk.Button)}
                assert '프로그램 종료' in buttons
                assert buttons['프로그램 종료'].master.master==root
                buttons['Manual'].invoke()
                manual=root._manual_window
                assert manual.winfo_exists() and 'Manual' in manual.title()
                for nav in [w for w in descendants(manual) if isinstance(w,tk.Button)]:
                    nav.invoke(); root.update_idletasks()
                manual.geometry('460x420'); root.update_idletasks()
                buttons['Manual'].invoke(); assert root._manual_window is manual
                manual.destroy()
                if mode!='paper':
                    assert '실전 시작' in buttons and '읽기 전용 점검' in buttons
                    assert '모의 재생' not in buttons
                    assert any(isinstance(w,ttk.Label) and '실행 대기 · 실전 시작 후' in str(w.cget('text')) for w in widgets)
                    log=next(w for w in widgets if isinstance(w,tk.Text))
                    assert log.cget('yscrollcommand') and log.cget('xscrollcommand')
                else:
                    buttons['모의 재생'].invoke(); buttons['재생 중지'].invoke(); root.update_idletasks()
                    plot=next(w for w in widgets if isinstance(w,tk.Canvas) and w.find_withtag('baseline_note'))
                    boxes=[plot.bbox(tick) for tick in plot.find_withtag('date_tick')]
                    for i,box in enumerate(boxes):
                        for other in boxes[i+1:]:assert box[2]<other[0] or other[2]<box[0]
                buttons['수익률 그래프'].invoke()
                root.update_idletasks()
                selector=next(w for w in widgets if isinstance(w,ttk.Combobox) and '직접 기간' in w.cget('values'))
                selector.set('직접 기간'); selector.event_generate('<<ComboboxSelected>>')
                checkbutton=next(w for w in widgets if isinstance(w,ttk.Checkbutton) and w.cget('text')=='캘린더로 선택')
                checkbutton.invoke()
                calendar_button=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='달력')
                calendar_button.invoke()
                root.update_idletasks()
                popup=next(w for w in descendants(root) if isinstance(w,tk.Toplevel) and '선택' in w.title())
                day=next(w for w in descendants(popup) if isinstance(w,ttk.Button) and w.cget('text')=='15')
                day.invoke()
                assert any(isinstance(w,ttk.Entry) and w.get().endswith('-15') for w in widgets)
            except Exception as exc: failures.append(exc)
            finally:
                for pending in root.tk.splitlist(root.tk.call('after','info')):root.after_cancel(pending)
                root.destroy()
        root.after(50,check)
        original(root)
    original=tk.Tk.mainloop
    from engine import demo_bars
    with patch.object(tk.Tk,'mainloop',run), patch('app.demo_bars',return_value=demo_bars()[:21]): gui(mode)
    if failures: raise failures[0]


if __name__=='__main__':
    for mode in ('paper','etf','stock'):smoke(mode)
    print('PASS: 3 GUI modes, graph windows, period selectors, calendar selection. No network/orders.')
