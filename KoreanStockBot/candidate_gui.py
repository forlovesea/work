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
from etf_scope import candidate_rows,read_symbols,write_symbols
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
    for col,title,width in zip(columns,['선택','순자산 순위','종목명 / 코드','현재가','1주 필요액','예산 내 주수','재무점수','추세','판정 / 제외 사유'],[55,80,220,90,95,85,85,90,290]):
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
            tree.insert('', 'end',iid=symbol,values=('✓' if symbol in state['chosen'] else '□' if good else '—',r['rank'],r['name']+' / '+symbol,
                f"{float(r['price']):,.0f}" if 'price' in r else '미확인',f'{required:,.0f}' if required else '미확인',
                int(budget//required) if required>0 else '—',f"{float(r.get('score',0))*100:.0f}%",
                '상승' if good else '미충족' if r['state']=='TREND' else '미확인',reason))
        info.set(f"분석 시각: {details.get('checked_at','미확인')} / 재무·뉴스 생성: {details.get('generated_at','미확인')}\n"
                 f"계좌 원화 주문 가능액 {float(details.get('power',0)):,.0f}원 · 봇 잔여 현금 {float(details.get('cash',0)):,.0f}원 · 적용 예산 {budget:,.0f}원\n"
                 '예산은 계좌 원화·봇 현금·투자 비중·주문 상한 중 최솟값입니다. 1주 필요액은 현재가 × 1.01 + 10원 추정입니다.')
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
        if panel.active():
            messagebox.showinfo('실행 중','현재 분석 결과는 볼 수 있습니다. 최신 계좌 조회와 적용은 중지 완료 후 진행하세요.',parent=popup);return
        state['busy']=True;panel.querying=True;state['details']=None
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
        except queue.Empty:popup.after(200,poll);return
        state['busy']=False;panel.querying=False
        if report['status']=='CANDIDATE_REPORT':
            details=report['selection_details']
            panel.scope_details=details;panel.binding=binding;render(details)
        else:
            info.set('후보 조회 실패 · '+report['reason'])
            note.set(report['action'])
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
        note.set('실행 중에는 기존 분석 결과만 표시합니다. 봇 중지 완료 후 최신 조회와 종목 선택 적용을 진행하세요.')
    else:refresh()
