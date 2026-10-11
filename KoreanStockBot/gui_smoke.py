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
        root.withdraw()
        def check():
            try:
                widgets=list(descendants(root))
                buttons={str(w.cget('text')):w for w in widgets if isinstance(w,ttk.Button)}
                if mode!='paper':
                    assert '실전 시작' in buttons and '읽기 전용 점검' in buttons
                    assert '모의 재생' not in buttons
                buttons['수익률 그래프'].invoke()
                root.update_idletasks()
                selector=next(w for w in widgets if isinstance(w,ttk.Combobox) and '직접 기간' in w.cget('values'))
                selector.set('직접 기간'); selector.event_generate('<<ComboboxSelected>>')
                checkbutton=next(w for w in widgets if isinstance(w,ttk.Checkbutton))
                checkbutton.invoke()
                calendar_button=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='달력')
                calendar_button.invoke()
                root.update_idletasks()
                popup=next(w for w in descendants(root) if isinstance(w,tk.Toplevel) and '선택' in w.title())
                day=next(w for w in descendants(popup) if isinstance(w,ttk.Button) and w.cget('text')=='15')
                day.invoke()
                assert any(isinstance(w,ttk.Entry) and w.get().endswith('-15') for w in widgets)
            except Exception as exc: failures.append(exc)
            finally:root.destroy()
        root.after(50,check)
        original(root)
    original=tk.Tk.mainloop
    with patch.object(tk.Tk,'mainloop',run): gui(mode)
    if failures: raise failures[0]


if __name__=='__main__':
    for mode in ('paper','etf','stock'):smoke(mode)
    print('PASS: 3 GUI modes, graph windows, period selectors, calendar selection. No network/orders.')
