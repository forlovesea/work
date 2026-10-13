"""Sector financial recommendations; explicit single-symbol selection."""
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk,messagebox
from datetime import datetime
from app_paths import ROOT
from live import SafetyStop
from stock_candidates import CATEGORIES,CHECK_NAMES,apply_selection

def preparation_message(env,config):
    """Local prerequisites only; filled credentials do not prove authentication."""
    names={'TOSS_CLIENT_ID':'토스 Client ID','TOSS_CLIENT_SECRET':'토스 Client Secret',
           'TOSS_ACCOUNT_SEQ':'조회 후 선택한 토스 계좌','KRX_ID':'KRX 아이디',
           'KRX_PW':'KRX 비밀번호','DART_API_KEY':'DART 인증키'}
    missing=[name for key,name in names.items() if not str(env.get(key,'')).strip()]
    steps=[]
    if missing:
        steps.append('입력이 필요한 항목\n• '+'\n• '.join(missing))
        steps.append('인증·계좌 설정에서 위 항목을 입력하고, 계좌 조회 후 사용할 계좌를 선택하세요.')
    elif not str(env['TOSS_ACCOUNT_SEQ']).isdigit():
        steps.append('계좌 선택값이 올바르지 않습니다. 인증·계좌 설정에서 계좌를 다시 조회·선택하세요.')
    try:
        from stock_candidates import budget_for
        budget_for(config,config['capital'])
    except Exception:
        steps.append('운용 원금·주문 상한은 양수, 투자 비중은 0 초과 1 이하로 설정해야 합니다. 단일 종목 설정 파일(live_config.json)을 확인하세요.')
    if not steps:return None
    return '\n\n'.join(steps)+'\n\n종목코드 입력이나 ETF 자료 수집은 미리 할 필요가 없습니다. 필요한 업종·재무 자료는 준비 완료 후 자동 조회합니다.'

EXCLUDED={'NO_DART_MAPPING':'DART 기업 연결 없음','MISSING_FINANCIALS':'재무 항목 부족',
 'FINANCIAL_RULES':'재무 조건 미달','STOCK_UNAVAILABLE':'거래 종목 미확인',
 'QUOTE_UNAVAILABLE':'유효 시세 없음','QUOTE_STALE':'시세 시간 초과','BUDGET':'예산 초과','DATA_ERROR':'조회·검증 오류'}

def show(panel,env_provider=None,on_select=None):
    if panel.active() or panel.querying or panel.closing:
        messagebox.showinfo('중지 후 조회','현재 작업을 중지한 후 업종별 종목 추천을 열어 주세요.');return
    prior=getattr(panel,'stock_window',None)
    if prior is not None and prior.winfo_exists():
        if env_provider is not None:prior.stock_context.update(env_provider=env_provider,on_select=on_select)
        prior.lift();return
    window=tk.Toplevel(panel.root);panel.stock_window=window
    window.stock_context={'env_provider':env_provider or panel.env,'on_select':on_select}
    window.title('내 예산 기준 · 업종별 단일 종목 추천')
    window.geometry('1200x740');window.minsize(800,520);window.transient(panel.root)
    window.columnconfigure(0,weight=1);window.rowconfigure(3,weight=1)
    info=tk.StringVar(value='조회하면 계좌 예산, KRX 업종, DART 재무제표와 종목 시세를 확인합니다.')
    ttk.Label(window,textvariable=info,wraplength=1100,justify='left').grid(row=0,column=0,sticky='ew',padx=16,pady=12)
    ttk.Label(window,text='재무 기준: 매출·영업이익·순이익·영업현금흐름 양수, 자기자본비율 30% 이상 중 4개 이상 충족.\n영업흑자·순이익 흑자·자본 양수는 필수입니다. 공통 지표로 금융업을 정밀 평가하지 않으며, 표준 재무 항목이 없으면 제외합니다.\n업종별 최대 5개 · 검사 통과 수, 시가총액 순. 수익률 예측이 아니며 선택만으로 주문하지 않습니다.',wraplength=1100,justify='left').grid(row=1,column=0,sticky='ew',padx=16)
    controls=ttk.Frame(window);controls.grid(row=2,column=0,sticky='ew',padx=16,pady=10)
    ttk.Label(controls,text='업종별 검사 범위').pack(side='left')
    scope=tk.StringVar(value='시가총액 상위 20개')
    selector=ttk.Combobox(controls,textvariable=scope,values=('시가총액 상위 20개','시가총액 상위 50개','예산 내 전체'),state='readonly',width=22)
    selector.pack(side='left',padx=8)
    ttk.Label(controls,text='전일 종가로 예산 선별 후 검사 · 전체 조회는 오래 걸릴 수 있습니다.').pack(side='left')
    frame=ttk.Frame(window);frame.grid(row=3,column=0,sticky='nsew',padx=16)
    frame.columnconfigure(0,weight=1);frame.rowconfigure(0,weight=1)
    columns=('category','name','symbol','price','required','quantity','score','period','industry')
    tree=ttk.Treeview(frame,columns=columns,show='headings',selectmode='browse')
    for key,title,width in zip(columns,('업종','종목명','코드 (6자리)','조회가 (원)','1주 필요액 (원)','예산 내 주수','재무 검사','보고서 기준일','KRX 업종'),(125,170,95,100,125,100,100,120,150)):
        tree.heading(key,text=title);tree.column(key,width=width,anchor='w' if key in ('category','name','industry') else 'center',stretch=False)
    tree.grid(row=0,column=0,sticky='nsew')
    y=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);y.grid(row=0,column=1,sticky='ns')
    x=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview);x.grid(row=1,column=0,sticky='ew')
    tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
    detail=tk.StringVar(value='조회 후 한 종목을 선택하면 재무 수치·기준시각·공시 출처가 표시됩니다.')
    ttk.Label(window,textvariable=detail,wraplength=1100,justify='left').grid(row=4,column=0,sticky='ew',padx=16,pady=10)
    actions=ttk.Frame(window);actions.grid(row=5,column=0,pady=12)
    state={'busy':False,'proc':None,'result':None,'account':'','cancelled':False,'started':0,'env':None}
    events=queue.Queue()

    def selected(event=None):
        picks=tree.selection();result=state['result']
        if not picks or not result:return
        row=next(r for r in result['rows'] if r['symbol']==picks[0]);report=row['report']
        checks=' / '.join(f'{CHECK_NAMES[k]}: '+('통과' if v else '미달') for k,v in report['checks'].items())
        names={'revenue':'매출','operating_profit':'영업이익','net_profit':'순이익','assets':'자산','equity':'자본','operating_cash':'영업현금흐름'}
        metrics=' / '.join(f'{label} {float(report["metrics"][k])/100000000:,.2f}억원' for k,label in names.items())
        detail.set(f"선택: {row['name']} ({row['symbol']})  |  시세: {row['price_at']}  |  {report.get('fs_div','')}\n"+checks+'\n'+metrics+'\n공시: '+' '.join(report.get('sources',[])))
    tree.bind('<<TreeviewSelect>>',selected)

    def query():
        if state['busy'] or panel.querying or panel.active() or panel.closing:
            messagebox.showinfo('조회 전 확인','진행 중인 조회가 끝날 때까지 기다려 주세요. 자동매매가 실행 중이면 중지 요청 후 정상 중지를 확인하세요.',parent=window);return
        try:
            env=window.stock_context['env_provider']()
            config=json.loads(panel.config_path.read_text(encoding='utf-8-sig'))
            preparation=preparation_message(env,config)
            if preparation:raise SafetyStop(preparation)
            state['account']=env['TOSS_ACCOUNT_SEQ'];state['env']=env
            limit={'시가총액 상위 20개':20,'시가총액 상위 50개':50,'예산 내 전체':0}[scope.get()]
            proc=panel.spawn(['--stock-candidates','--sector-limit',str(limit)],env)
        except Exception as exc:
            explanation=str(exc) if isinstance(exc,SafetyStop) else '조회 준비를 완료하지 못했습니다. 인증 저장정보, live_config.json 및 실행파일 배포 폴더를 확인하세요.'
            info.set(explanation)
            messagebox.showwarning('조회 전 준비가 필요합니다',explanation,parent=window)
            return
        state.update(busy=True,proc=proc,result=None,cancelled=False,error=False,started=time.monotonic())
        panel.querying=True;selector.configure(state='disabled');tree.delete(*tree.get_children())
        detail.set('자료 수집 중 · 결과가 없는 업종은 이유와 함께 표시합니다.')
        info.set('계좌·KRX·DART 조회 준비 중…');panel.diagnostic('STOCK_START')
        def reader():
            try:
                for line in proc.stdout:
                    try:report=json.loads(line)
                    except ValueError:continue
                    if isinstance(report,dict):events.put(report)
                proc.wait()
            finally:
                proc.stdout.close();events.put({'status':'END'})
        threading.Thread(target=reader,daemon=True).start()
        window.after(150,poll)

    def cancel():
        if not state['busy']:return
        state['cancelled']=True
        proc=state['proc']
        if proc is not None and proc.poll() is None:proc.kill()
        info.set('조회 취소 중 · 주문 없는 조회 프로세스 종료 확인 대기')

    def poll():
        if panel.closing and not state['cancelled']:cancel()
        if time.monotonic()-state['started']>1800 and not state['cancelled']:cancel()
        while not events.empty():
            report=events.get_nowait();status=report.get('status')
            if status=='END':
                state['busy']=False;panel.querying=False;selector.configure(state='readonly')
                if state['cancelled']:
                    state['result']=None;tree.delete(*tree.get_children());info.set('조회 취소 · 부분 결과는 추천으로 사용하지 않습니다.')
                elif not state['result'] and not state.get('error'):
                    info.set('조회 실패 · 정상 결과를 받지 못했습니다. 인증·네트워크와 진단 로그를 확인하세요.')
                panel.diagnostic('STOCK_END',candidates=len((state['result'] or {}).get('rows',[])))
                return
            if state['cancelled']:continue
            if status=='STOCK_PROGRESS':
                panel.diagnostic('STOCK_PROGRESS',stage=report.get('stage'),count=report.get('done'),candidates=report.get('total'),symbol=report.get('symbol'))
                label={'ACCOUNT':'계좌 예산 확인','KRX':'KRX 업종 목록 조회','DART':'재무 검사','PRICES':'최신 시세·거래 가능 여부 확인','COMPLETE':'결과 정리'}.get(report.get('stage'),'진행 중')
                info.set(f"{label} · {report.get('done',0)}/{report.get('total',0)}개 · {int(time.monotonic()-state['started'])}초 경과")
            elif status in ('STOCK_ERROR','WORKER_ERROR'):
                state['error']=True
                info.set('조회 실패 · '+report.get('reason','인증·계좌 또는 실행 상태를 확인하세요.'))
                detail.set(report.get('action','다시 조회하기 전 인증 설정과 연결 상태를 확인하세요.'))
                panel.diagnostic('STOCK_ERROR',error_code=report.get('error_code',report.get('code')))
            elif status=='STOCK_CANDIDATES':
                state['result']=report
                for row in report['rows']:
                    tree.insert('','end',iid=row['symbol'],values=(row['category'],row['name'],row['symbol'],
                        f"{float(row['price']):,.0f}",f"{float(row['required']):,.0f}",row['quantity'],
                        f"{sum(row['report']['checks'].values())}/5 통과",row['report']['report_end'],row['industry']))
                summary=' / '.join(f"{group} {sum(r['category']==group for r in report['rows'])}개" for group in CATEGORIES)
                info.set(f"조회 완료 · 적용 예산 {float(report['budget']):,.0f}원 / 계좌 주문 가능액 {float(report['power']):,.0f}원\n"+
                    f"KRX 기준일 {report['as_of']} · {report['screened']}개 검사 · {summary}\n예산 = 계좌 현금·운용 원금·투자 비중·주문 상한 중 제한 적용. 1주 필요액 = 조회가 × 1.01 + 10원 추정.")
                detail.set('제외: '+(' / '.join(f'{EXCLUDED.get(k,k)} {v}개' for k,v in report['excluded'].items()) or '없음')+
                    '\n추천 0개인 업종은 예산·재무·시세 조건을 만족하는 확인된 후보가 없습니다. 장외에는 최신 시세 기준 미충족으로 제외될 수 있습니다.')
                for failure in report.get('errors',[]):panel.diagnostic('STOCK_ERROR',**failure)
        if state['busy']:window.after(150,poll)

    def apply():
        if state['busy'] or panel.active() or panel.querying or panel.closing:return
        picks=tree.selection()
        if not picks or not state['result']:messagebox.showinfo('종목 선택','조회된 후보에서 한 종목을 선택하세요.',parent=window);return
        try:
            current=window.stock_context['env_provider']()
            if any(current.get(k)!=state['env'].get(k) for k in ('TOSS_CLIENT_ID','TOSS_CLIENT_SECRET','TOSS_ACCOUNT_SEQ','KRX_ID','KRX_PW','DART_API_KEY')):
                raise SafetyStop('인증·계좌 정보가 변경되었습니다. 다시 조회하세요.')
            account=current.get('TOSS_ACCOUNT_SEQ','')
            callback=window.stock_context['on_select']
            config=apply_selection(ROOT,panel.config_path,account,state['result'],picks[0],save=callback is None)
            if callback is not None:
                callback(picks[0]);window.destroy();return
            panel.config=config
            panel.log_line('단일 종목 설정 적용: '+picks[0]+' · 읽기 전용 점검 후 실전 시작을 선택하세요.')
            messagebox.showinfo('종목 적용 완료',picks[0]+' 종목을 설정했습니다. 자동 주문은 시작하지 않았습니다.',parent=window)
            window.destroy()
        except Exception as exc:messagebox.showerror('적용 보류',str(exc) if isinstance(exc,SafetyStop) else '설정 저장에 실패했습니다.',parent=window)

    def close():
        if state['busy']:
            cancel();window.after(200,close)
        else:window.destroy()
    ttk.Button(actions,text='예산·재무 기준 조회',command=query,style='Primary.TButton').pack(side='left',padx=6)
    ttk.Button(actions,text='조회 취소',command=cancel).pack(side='left',padx=6)
    ttk.Button(actions,text='선택 종목 적용',command=apply,style='Success.TButton').pack(side='left',padx=6)
    window.protocol('WM_DELETE_WINDOW',close)
