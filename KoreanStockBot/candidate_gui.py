"""Measured ETF suggestions with explicit user selection; read-only refresh."""
import hashlib
import json
import queue
import threading
import subprocess
import time
import tkinter as tk
from tkinter import ttk,messagebox
from datetime import datetime
from app_paths import ROOT
from live import process_lock,stamp
from etf_scope import candidate_rows,candidate_cells,read_symbols,write_symbols
from diagnostics import STATES,REASONS
from candidate_feedback import unavailable_message


def show(panel):
    if panel.querying:return
    try:
        env=panel.env();account=env.get('TOSS_ACCOUNT_SEQ','')
        if not account.isdigit():raise ValueError()
        config=json.loads(panel.config_path.read_text(encoding='utf-8-sig'))
        binding=hashlib.sha256((account+'|'+json.dumps(config,sort_keys=True)).encode()).hexdigest()
        path=ROOT/'runtime'/'etf_scope.json'
        saved=read_symbols(path,binding)
    except Exception:
        messagebox.showerror('설정 확인','인증·계좌 설정과 후보 설정 파일을 확인하세요.');return
    popup=tk.Toplevel(panel.root);popup.title('내 자산 기준 ETF 후보 제안')
    popup.geometry('1050x640');popup.minsize(620,440);popup.transient(panel.root)
    popup.configure(bg=panel.colors['bg'])
    popup.columnconfigure(0,weight=1);popup.rowconfigure(2,weight=1)
    info=tk.StringVar(value='최신 계좌·시세와 자동 수집된 재무·뉴스를 기준으로 후보를 분석합니다.')
    ttk.Label(popup,textvariable=info,wraplength=950,justify='left').grid(row=0,column=0,sticky='ew',padx=16,pady=12)
    ttk.Label(popup,text='종목을 클릭해 선택/해제하세요. 추천은 조건 통과 순서이며 예상 수익률이 아닙니다.\n선택한 종목 안에서 한 번에 한 종목을 운용하고, 실제 주문 전 호가·위험 한도 등을 다시 검사합니다.',wraplength=950).grid(row=1,column=0,sticky='ew',padx=16)
    frame=ttk.Frame(popup);frame.grid(row=2,column=0,sticky='nsew',padx=16,pady=10)
    frame.columnconfigure(0,weight=1);frame.rowconfigure(0,weight=1)
    columns=('pick','rank','name','price','required','quantity','score','trend','reason')
    tree=ttk.Treeview(frame,columns=columns,show='headings',selectmode='browse')
    for col,title,width in zip(columns,['선택','순자산 순위','종목명 / 코드','현재가 (원)','1주 필요액 (원)','예산 내 주수','재무점수','추세 / 검사 상태','판정 / 제외 사유'],[55,80,220,125,130,85,85,195,310]):
        tree.heading(col,text=title);tree.column(col,width=width,minwidth=width,stretch=False)
    tree.grid(row=0,column=0,sticky='nsew')
    for orient,row,col,command in [('vertical',0,1,tree.yview),('horizontal',1,0,tree.xview)]:
        scroll=ttk.Scrollbar(frame,orient=orient,command=command);scroll.grid(row=row,column=col,sticky='ns' if col else 'ew')
        tree.configure(**{('yscrollcommand' if col else 'xscrollcommand'):scroll.set})
    note=tk.StringVar(value='')
    ttk.Label(popup,textvariable=note,wraplength=950).grid(row=3,column=0,sticky='ew',padx=16,pady=8)
    controls=ttk.Frame(popup);controls.grid(row=4,column=0,pady=12)
    state={'details':None,'chosen':set(),'eligible':set(),'busy':False}
    results=queue.Queue()
    progress_window=None
    progress_text=tk.StringVar()
    started=0

    def dismiss_progress():
        nonlocal progress_window
        if progress_window is not None and progress_window.winfo_exists():progress_window.destroy()
        progress_window=None

    def open_progress():
        nonlocal progress_window,started
        dismiss_progress();started=time.monotonic()
        progress_window=tk.Toplevel(popup)
        progress_window.title('최신 계좌·시세 조회 진행 상황')
        progress_window.transient(popup);progress_window.resizable(False,False)
        ttk.Label(progress_window,textvariable=progress_text,wraplength=460,justify='left',padding=18).pack(fill='x')
        bar=ttk.Progressbar(progress_window,mode='indeterminate',length=420)
        bar.pack(padx=18,pady=6);bar.start(15)
        ttk.Label(progress_window,text='결과가 화면에 반영되면 자동으로 닫힙니다.\n확인을 누르면 이 안내창만 닫히며 작업은 계속됩니다.',padding=18).pack()
        ttk.Button(progress_window,text='확인',command=dismiss_progress).pack(pady=(0,14))
        progress_window.protocol('WM_DELETE_WINDOW',dismiss_progress)

    def progress(message):
        progress_text.set(message+f'\n경과: {int(time.monotonic()-started)}초')

    def render(details):
        state['details']=details;state['eligible']=set();state['chosen']=set()
        tree.delete(*tree.get_children())
        budget=float(details.get('budget',0))
        rows=candidate_rows(details)
        for r in rows:
            symbol=r['symbol'];good=r['state'] in ('ELIGIBLE','SELECTED')
            if good:state['eligible'].add(symbol)
            if good and saved and symbol in saved:state['chosen'].add(symbol)
            required=float(r.get('required',0))
            reason='추천 · 재무·뉴스·예산·추세 통과' if good else STATES.get(r['state'],r['state'])
            if r.get('reasons'):reason+=' / '+', '.join(REASONS.get(v,v) for v in r['reasons'])
            if r.get('shortfall') and float(r['shortfall'])>0:reason+=f" / {float(r['shortfall']):,.0f}원 부족"
            price_cell,required_cell,trend_cell=candidate_cells(r)
            if r['state'] in ('STRUCTURE','RESEARCH'):reason+=' / 앞 조건 미통과로 시세·추세 조회 생략'
            if r['state']=='CANDLES':reason+=f" / 일봉 {r.get('candles',0)}개, 필요 {details.get('slow','미확인')}개 / 마지막 {r.get('last_day') or '없음'}"
            tree.insert('', 'end',iid=symbol,values=('✓' if symbol in state['chosen'] else '□' if good else '—',r['rank'],r['name']+' / '+symbol,
                price_cell,required_cell,
                int(budget//required) if required>0 else '—',f"{float(r.get('score',0))*100:.0f}%",
                trend_cell,reason))
        info.set(f"분석 시각: {details.get('checked_at','미확인')} / 재무·뉴스 생성: {details.get('generated_at','미확인')}\n"
                 f"계좌 원화 주문 가능액 {float(details.get('power',0)):,.0f}원 · 봇 잔여 현금 {float(details.get('cash',0)):,.0f}원 · 적용 예산 {budget:,.0f}원\n"
                 '예산은 계좌 원화·봇 현금·투자 비중·주문 상한 중 최솟값입니다. 1주 필요액은 현재가 × 1.01 + 10원 추정입니다.\n'
                 '조회 생략: 앞 조건 미통과로 요청하지 않음 / 유효 시세 없음: 응답·통화 확인 필요 / 시세 시간 초과: 최신성 기준 미충족')
        note.set(f"중복 제거 후 {len(rows)}종목 중 추천 {len(state['eligible'])}개. 선택 {len(state['chosen'])}개. " +
                 ('통과 후보가 없어 현재는 매수 대기를 제안합니다. 한도와 분석 조건을 자동 완화하지 않습니다.' if not state['eligible'] else '적용 후 실전 시작 시 선택 종목만 신규 매수 후보로 검사합니다.'))

    def toggle(event):
        symbol=tree.identify_row(event.y)
        if symbol not in state['eligible']:return
        chosen=state['chosen']
        chosen.remove(symbol) if symbol in chosen else chosen.add(symbol)
        tree.set(symbol,'pick','✓' if symbol in chosen else '□')
        note.set(f'선택 {len(chosen)}개 · 적용은 봇 중지 후 가능합니다. 기존 보유분의 매도 관리는 유지됩니다.')
    tree.bind('<ButtonRelease-1>',toggle)

    def refresh():
        if state['busy'] or panel.querying or getattr(panel,'closing',False):return
        state['busy']=True;panel.querying=True;state['details']=None
        open_progress()
        if panel.active():
            progress('1/3 · 실행 중인 작업에 중지를 요청합니다.\n보유 종목은 유지하며 정상 중지 확인 후 조회합니다.')
            info.set('최신 조회 준비 · 실행 중인 작업의 정상 중지 확인 대기')
            if panel.stop() is False:
                finish_error('중지 요청을 전달하지 못해 조회를 시작하지 않았습니다.');return
            popup.after(200,wait_stopped)
        elif getattr(panel,'child',None) is not None:
            popup.after(200,wait_stopped)
        else:begin_query()

    def finish_error(reason):
        state['busy']=False;panel.querying=False
        info.set('조회 시작 보류 · '+reason)
        note.set('현재 작업 상태와 토스 앱의 미체결·보유분을 확인하세요. 정상 중지 확인 전에는 자동 조회하지 않습니다.')
        panel.log_line(info.get());dismiss_progress()

    def wait_stopped():
        if getattr(panel,'closing',False):
            finish_error('프로그램 종료 요청으로 대기 중인 조회를 취소했습니다.');return
        progress('1/3 · 정상 중지 확인 대기\n주문 정리와 작업 종료를 확인하고 있습니다.')
        if getattr(panel,'child',None) is None:
            if not getattr(panel,'stop_confirmed',False) or getattr(panel,'exit_unverified',False):
                finish_error('정상 중지가 확인되지 않았습니다.');return
            begin_query();return
        if time.monotonic()-started>=120:
            finish_error('중지 확인이 120초 안에 끝나지 않았습니다.');return
        popup.after(200,wait_stopped)

    def begin_query():
        if getattr(panel,'closing',False):
            finish_error('프로그램 종료 요청으로 조회를 취소했습니다.');return
        progress('2/3 · 계좌·시세 및 후보 조건 조회 중\n결과를 기다리고 있습니다. 조회 중에는 주문하지 않습니다.')
        panel.diagnostic('CANDIDATE_START')
        state['eligible']=set();state['chosen']=set();tree.delete(*tree.get_children())
        info.set('읽기 전용 조회 중 · 계좌 원화, 순자산 상위 20개 ETF, 재무·뉴스, 시세와 추세 확인 · 주문 없음')
        def work():
            proc=None
            try:
                proc=panel.spawn(['--etf','--candidate-report'],env)
                output,_=proc.communicate(timeout=180)
                report=None
                for line in output.splitlines():
                    try:value=json.loads(line)
                    except ValueError:continue
                    if isinstance(value,dict) and value.get('status') in ('CANDIDATE_REPORT','CANDIDATE_ERROR'):report=value
                if report is None or (proc.returncode and report['status']!='CANDIDATE_ERROR'):raise ValueError()
                results.put(report)
            except Exception as exc:
                if proc is not None and proc.poll() is None:proc.kill();proc.communicate()
                timeout=isinstance(exc,subprocess.TimeoutExpired)
                results.put(dict(status='CANDIDATE_ERROR',reason='계좌·시세 조회가 180초 안에 완료되지 않았습니다.' if timeout else '조회 프로그램을 실행하지 못했거나 정상 결과를 받지 못했습니다.',
                    action='인터넷 연결과 실행파일 배포 폴더를 확인하고 읽기 전용 점검의 상태를 확인하세요.'))
        threading.Thread(target=work,daemon=True).start()
        popup.after(200,poll)

    def poll():
        try:report=results.get_nowait()
        except queue.Empty:
            progress('2/3 · 계좌·시세 및 후보 조건 조회 중\n결과 대기 · 조회 제한 시간은 최대 180초입니다.')
            popup.after(200,poll);return
        progress('3/3 · 조회 결과를 화면에 반영 중')
        state['busy']=False;panel.querying=False
        details=report.get('selection_details',{})
        panel.diagnostic(report['status'],error_code=report.get('code'),
            candidates=len(details.get('rows',[])),eligible=sum(r.get('state') in ('ELIGIBLE','SELECTED') for r in details.get('rows',[])))
        if report['status']=='CANDIDATE_REPORT':
            details=report['selection_details']
            panel.scope_details=details;panel.binding=binding;render(details)
        else:
            info.set('후보 조회 실패 · '+report['reason'])
            note.set(report['action'])
        popup.update_idletasks()
        dismiss_progress()
        explanation=unavailable_message(report)
        if explanation:
            panel.log_line(explanation)
            if not getattr(panel,'closing',False):
                show_message=messagebox.showwarning if report['status']=='CANDIDATE_ERROR' else messagebox.showinfo
                show_message('후보 제안 불가 사유',explanation,parent=popup)

    def apply():
        if state['busy'] or panel.active() or panel.querying or getattr(panel,'closing',False):
            messagebox.showinfo('대기 필요','조회와 봇 중지가 완료된 뒤 적용하세요.',parent=popup);return
        details=state['details']
        if not details or not state['chosen']:
            messagebox.showinfo('종목 선택','추천된 종목을 한 개 이상 선택하세요.',parent=popup);return
        age=(datetime.now().astimezone()-stamp(details['checked_at'])).total_seconds()
        if not details.get('complete') or not 0<=age<=300:
            messagebox.showinfo('다시 조회','분석 후 5분이 지났거나 검사가 미완료입니다. 최신 계좌·시세 조회를 누르세요.',parent=popup);return
        try:
            with process_lock(ROOT/'runtime'/'bot.lock'):write_symbols(path,binding,state['chosen'])
            panel.log_line('사용자 선택 ETF: '+', '.join(sorted(state['chosen']))+' · 다음 시작부터 신규 매수 후보에 적용')
            popup.destroy()
        except Exception:messagebox.showerror('적용 실패','다른 봇의 실행 여부와 파일 권한을 확인하세요.',parent=popup)

    def close():
        if state['busy']:messagebox.showinfo('조회 중','읽기 전용 조회가 끝난 뒤 닫아주세요.',parent=popup)
        else:popup.destroy()
    popup.protocol('WM_DELETE_WINDOW',close)
    ttk.Button(controls,text='최신 계좌·시세 조회',command=refresh,style='Primary.TButton').pack(side='left',padx=6)
    ttk.Button(controls,text='선택한 종목 적용',command=apply,style='Success.TButton').pack(side='left',padx=6)
    if panel.active():
        details=getattr(panel,'scope_details',None) if getattr(panel,'binding',None)==binding else None
        if details:render(details)
        note.set('최신 계좌·시세 조회를 누르면 자동으로 중지를 요청하고 정상 중지 확인 후 조회합니다. 실전은 자동 재시작하지 않습니다.')
    else:refresh()
