"""Desktop research + paper automation + per-order approval workbench."""
import json
import os
import queue
import threading
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime

from app_paths import ROOT
from app_version import VERSION
from advisor import Advisor, DEFAULTS, settings, fresh_report
from broker import TossBroker, StopRequested
from credentials import KEYS, load_credentials, save_credentials
from live import Store, SafetyStop, MarketDataWait, now_kst, process_lock, dec
from runtime_status import describe_status
from desktop_theme import install_theme
from button_theme import button_style


def error_text(exc):
    if isinstance(exc,MarketDataWait):return '시세·호가 확인 대기 · 주문하지 않았습니다. 다음 주기에 다시 조회합니다.'
    if isinstance(exc,StopRequested):return '현재 조회 중지됨 · 실제 주문 자동 실행 없음'
    from candidate_feedback import failure
    report=failure(exc)
    if report['code']!='UNVERIFIED':return report['reason']+' '+report['action']
    # All Korean SafetyStop messages in this app are application-owned, not API text.
    if isinstance(exc,SafetyStop):return str(exc)
    return '자료/설정 확인 실패 ('+type(exc).__name__+') · 인증 설정과 저장 폴더를 확인하세요.'


class AdvisorWindow:
    def __init__(self,root,path=ROOT):
        self.root=root;self.path=Path(path);self.events=queue.Queue()
        self.busy=False;self.automatic=False;self.closing=False;self.cancel_event=threading.Event()
        self.service=None;self.offer=None;self.buttons=[];self.timer=None
        self.watch_symbol=None;self.watch_timer=None;self.watch_seen=None
        asset_root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
        root._chart_icon=tk.PhotoImage(file=str(asset_root/'assets'/'stock_chart.png'))
        root.iconphoto(True,root._chart_icon)
        if sys.platform=='win32':root.iconbitmap(default=str(asset_root/'assets'/'stock_chart.ico'))
        root.title('추천종목자동매매 프로그램 v'+VERSION+' | 모의 자동매매 · 실제 주문 개별 승인')
        root.geometry('1180x820');root.minsize(950,700)
        self.colors=install_theme(root)
        style=ttk.Style(root)
        style.configure('Title.TLabel',font=('맑은 고딕',24,'bold'))
        style.configure('Advisor.Card.TLabel',background=self.colors['panel'],font=('맑은 고딕',13,'bold'),padding=14)
        style.configure('TNotebook',borderwidth=0)
        style.configure('TNotebook.Tab',padding=(18,10),background=self.colors['panel'],foreground=self.colors['muted'])
        style.map('TNotebook.Tab',background=[('selected','#294365'),('active','#343A44')],foreground=[('selected',self.colors['text'])])
        root.option_add('*Text.background',self.colors['panel'])
        root.option_add('*Text.foreground',self.colors['text'])
        root.option_add('*Text.insertBackground',self.colors['text'])
        root.option_add('*Text.selectBackground','#294365')
        root.option_add('*Text.relief','flat')
        root.option_add('*Text.padX',12)
        root.option_add('*Text.padY',10)
        shell=ttk.Frame(root,padding=18);shell.pack(fill='both',expand=True)
        ttk.Label(shell,text='추천종목자동매매',style='Title.TLabel').pack(anchor='w')
        ttk.Label(shell,text='뉴스·재무 분석 → 모의 복리 운용 → 실제 주문은 매번 확인·승인',style='Muted.TLabel').pack(anchor='w',pady=(4,10))
        ttk.Label(shell,text='10%는 비교 목표이며 수익 예측·보장이 아닙니다. 뉴스 평가는 키워드 규칙이며, 전 종목·전 기사 분석이 아닙니다.',wraplength=1080).pack(anchor='w')
        self.status=tk.StringVar(value='인증 설정 → 예산 확인 → 뉴스·재무 분석 순서로 시작하세요.')
        ttk.Label(shell,textvariable=self.status,wraplength=1080,foreground='#9FC3FF').pack(fill='x',pady=12)
        actions=ttk.Frame(shell);actions.pack(fill='x')
        self.button(actions,'인증·계좌 설정',self.credentials)
        self.button(actions,'뉴스·재무 분석',self.analyze)
        self.button(actions,'모의 자동매매 시작',self.start_paper)
        ttk.Button(actions,text='모의 감시 중지',command=self.stop_paper,style='Danger.TButton').pack(side='left',padx=3)
        self.book=ttk.Notebook(shell);self.book.pack(fill='both',expand=True,pady=12)
        self.tabs={}
        for title in ('추천과 근거','모의 성과','실제 주문 승인','예산·비용'):
            tab=ttk.Frame(self.book,padding=12);self.book.add(tab,text=title);self.tabs[title]=tab
        tab=self.tabs['추천과 근거']
        self.scope=tk.StringVar(value='분석 전 · 업종별 시가총액 상위 20개에서 재무를 검사한 후 상위 12개 뉴스 검토')
        ttk.Label(tab,textvariable=self.scope,wraplength=1030).pack(anchor='w',pady=(0,8))
        columns=('name','symbol','score','news','state')
        self.tree=ttk.Treeview(tab,columns=columns,show='headings',height=8,selectmode='browse')
        for key,label,width in zip(columns,('종목','코드','규칙 점수','관련 기사','판단 근거'),(160,80,80,80,470)):
            self.tree.heading(key,text=label);self.tree.column(key,width=width,stretch=key in ('name','state'))
        self.tree.pack(fill='x');self.tree.bind('<<TreeviewSelect>>',self.selected)
        ttk.Label(tab,text='추천은 주문 지시가 아닙니다. 매매안 생성 시 최신 시세·호가·시장 운영시간을 다시 검사합니다.').pack(anchor='w',pady=8)
        self.details=tk.Text(tab,height=12,wrap='word',font=('맑은 고딕',10));self.details.pack(fill='both',expand=True)
        self.details.configure(state='disabled')
        tab=self.tabs['모의 성과']
        self.metrics=tk.StringVar(value='모의 거래 전 · 실제 계좌 주문 없음')
        ttk.Label(tab,textvariable=self.metrics,style='Advisor.Card.TLabel',wraplength=1020).pack(fill='x')
        ttk.Label(tab,text='평가액은 예상 청산 비용을 차감합니다. 체결은 호가+슬리피지 가정이며 실제 유동성·체결을 재현하지 않습니다.\n실현 손익은 다음 매수 예산에 반영됩니다. 한 번에 1종목, 하루 신규 매수 1회, 기본 감시 간격 30초.',wraplength=1020).pack(anchor='w',pady=8)
        self.chart=tk.Canvas(tab,height=180,bg=self.colors['chart'],highlightthickness=0);self.chart.pack(fill='x')
        bar=ttk.Frame(tab);bar.pack(fill='x',pady=8)
        self.button(bar,'모의 거래 CSV 저장',self.export)
        self.button(bar,'모의 기록 보관 후 새로 시작',self.archive_paper)
        self.history=tk.Text(tab,height=7,wrap='word');self.history.pack(fill='both',expand=True)
        self.history.configure(state='disabled')
        tab=self.tabs['실제 주문 승인']
        ttk.Label(tab,text='주문안을 확인한 뒤 한 건씩 승인합니다. 모의 자동매매에서는 실제 주문을 보내지 않습니다.\n최초 사용은 보유분·미체결이 없는 계좌가 필요합니다. 종목 변경은 기존 보유분·미체결 정산 후 가능하며 예산·위험 설정은 유지합니다.',wraplength=1020).pack(anchor='w')
        bar=ttk.Frame(tab);bar.pack(fill='x',pady=12)
        self.button(bar,'선택 종목 주문안 / 체결 확인',self.preview)
        self.approve_button=self.button(bar,'표시된 실제 주문 승인',self.approve)
        self.button(bar,'미체결 취소 승인',self.cancel_order)
        watchbar=ttk.Frame(tab);watchbar.pack(fill='x',pady=4)
        self.button(watchbar,'선택 종목 승인 알림 시작',self.start_watch)
        ttk.Button(watchbar,text='승인 알림 중지',command=self.stop_watch).pack(side='left',padx=3)
        ttk.Label(tab,text='5초마다 선택 종목 확인 · 조건 감지 시 승인 팝업 · 거절한 동일 방향·사유는 조건 해제 전 재알림하지 않습니다.',wraplength=1020).pack(anchor='w')
        self.order_text=tk.Text(tab,height=18,wrap='word',font=('맑은 고딕',11));self.order_text.pack(fill='both',expand=True)
        self.set_text(self.order_text,'주문안 없음 · 실제 주문 미승인\n추천 목록에서 종목을 선택한 뒤 주문안을 생성하세요.')
        ttk.Label(tab,text='승인 후 가격·수량·조건이 달라지거나 120초가 지나면 전송하지 않습니다. 미체결·체결은 별도로 확인하세요.',wraplength=1020).pack(anchor='w',pady=8)
        self.entries={};self.vars={};tab=self.tabs['예산·비용']
        saved=Store(self.path/'advisor/settings.json').data or DEFAULTS
        labels={'capital':'운용 예산 (원)','allocation':'1회 투자 비중 (%)','max_order_won':'1회 매수 상한 (원)',
                'fee':'모의 수수료 가정 (%)','sell_reserve':'매도 세금·기타 비용 예비율 (%)','slippage':'모의 슬리피지 (%)',
                'stop_loss':'비용 반영 손절 (%)','take_profit':'비용 반영 익절 목표 (%)','max_drawdown':'최대 낙폭 제한 (%)'}
        for i,(key,label) in enumerate(labels.items()):
            ttk.Label(tab,text=label).grid(row=i,column=0,sticky='w',padx=8,pady=5)
            val=saved.get(key,DEFAULTS[key]);value=val if key in ('capital','max_order_won') else round(val*100,6)
            var=tk.StringVar(value=str(value));self.vars[key]=var
            entry=ttk.Entry(tab,textvariable=var,width=18);entry.grid(row=i,column=1,padx=12,pady=5);self.entries[key]=entry
        ttk.Label(tab,text='비용 값은 가정이며 법정 세율을 뜻하지 않습니다. 실제 주문 수량은 증권사 수수료 조회를 반영합니다.\n실제 비용은 체결 정산의 수수료·세금으로 기록합니다. 모의 기록이 있으면 설정 변경 전 기록을 보관하세요.',wraplength=730).grid(row=10,column=0,columnspan=3,sticky='w',padx=8,pady=15)
        self.log=tk.Text(shell,height=4,wrap='word',font=('맑은 고딕',9));self.log.pack(fill='x');self.log.configure(state='disabled')
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.approve_button.configure(state='disabled')
        self.render_report(Store(self.path/'advisor/recommendations.json').data)
        self.render_paper(Store(self.path/'advisor/paper.json').data)
        root.after(100,self.poll)

    def button(self,parent,text,command):
        style={'뉴스·재무 분석':'Primary.TButton','모의 자동매매 시작':'Primary.TButton','표시된 실제 주문 승인':'Success.TButton','미체결 취소 승인':'Danger.TButton'}.get(text,button_style(text))
        button=ttk.Button(parent,text=text,command=command,style=style);button.pack(side='left',padx=3)
        self.buttons.append(button);return button

    @staticmethod
    def set_text(widget,text):
        widget.configure(state='normal');widget.delete('1.0','end');widget.insert('end',text);widget.configure(state='disabled')

    def note(self,text):
        self.status.set(text)
        self.log.configure(state='normal');self.log.insert('end',now_kst().strftime('%H:%M:%S')+' · '+text+'\n');self.log.see('end');self.log.configure(state='disabled')

    def config(self):
        values={k:float(v.get())/(1 if k in ('capital','max_order_won') else 100) for k,v in self.vars.items()}
        return settings(values)

    def connect(self):
        c=self.config()
        if self.service and self.service.c==c:return self.service
        path=self.path/'advisor/credentials.dpapi'
        values=load_credentials(path if path.exists() else self.path/'runtime/credentials.dpapi')
        for key in KEYS:
            os.environ.pop(key,None)
            if values.get(key):os.environ[key]=values[key]
        if any(not values.get(k) for k in KEYS[:3]):raise SafetyStop('인증·계좌 설정에서 토스 인증과 계좌 선택을 저장하세요.')
        base=json.loads((self.path/'live_config.json').read_text(encoding='utf-8-sig'))
        self.service=Advisor(self.path,TossBroker(account=values['TOSS_ACCOUNT_SEQ'],live=False),base,c)
        self.service.b.stop_requested=self.cancel_event.is_set
        saved=Store(self.path/'advisor/settings.json');saved.data=c;saved.save()
        return self.service

    def task(self,kind,fn):
        if self.busy or self.closing:return
        self.busy=True;self.active_kind=kind;self.cancel_event.clear()
        for b in self.buttons:b.configure(state='disabled')
        for entry in self.entries.values():entry.configure(state='disabled')
        self.note('처리 중 · '+kind)
        def run():
            try:self.events.put(('done',kind,fn()))
            except Exception as exc:self.events.put(('error',kind,error_text(exc)))
        threading.Thread(target=run,daemon=True).start()

    def analyze(self):
        self.stop_watch()
        try:
            service=self.connect()
            missing=[k for k in KEYS[3:] if not os.environ.get(k)]
            if missing:raise SafetyStop('뉴스·재무 분석용 KRX·DART·NAVER 인증을 저장하세요.')
            self.offer=None
            self.task('분석',lambda:service.analyze(self.progress))
        except Exception as exc:messagebox.showerror('분석 준비',error_text(exc),parent=self.root)

    def progress(self,text):
        if self.cancel_event.is_set():raise StopRequested()
        self.events.put(('progress',text))

    def start_paper(self):
        self.stop_watch()
        try:self.connect()
        except Exception as exc:messagebox.showerror('모의매매 준비',error_text(exc),parent=self.root);return
        self.automatic=True;self.book.select(self.tabs['모의 성과']);self.paper_tick()

    def paper_tick(self):
        self.timer=None
        if not self.automatic or self.closing:return
        if self.busy:self.timer=self.root.after(1000,self.paper_tick);return
        service=self.service
        def work():
            if not fresh_report(service.report,now_kst()):
                if service.paper.s['quantity']:
                    # Check price-based exits before potentially slow research calls.
                    service.paper.tick(service.b,service.base,service.report)
                    if service.paper.s['quantity']:service.refresh_holding(self.progress)
                    else:service.analyze(self.progress)
                else:service.analyze(self.progress)
            result=service.paper.tick(service.b,service.base,service.report)
            return result
        self.task('모의 감시',work)

    def stop_paper(self):
        self.automatic=False
        # Only interrupt analysis/paper reads; an approved mutation must finish recording.
        if getattr(self,'active_kind','') not in ('실제 승인','취소 승인'):self.cancel_event.set()
        if self.timer:self.root.after_cancel(self.timer);self.timer=None
        if not self.busy:
            for entry in self.entries.values():entry.configure(state='normal')
        self.note('모의 감시 중지 요청 · 보유 모의 포지션은 유지 · 실제 미체결 주문은 취소하지 않음')

    def render_report(self,report):
        self.report=report
        self.tree.delete(*self.tree.get_children())
        if not report:return
        self.scope.set(report.get('scope','')+' · 분석 시각 '+report['checked_at'][:19]+' · 점수는 수익 확률이 아닙니다.')
        for row in report['rows']:
            self.tree.insert('','end',iid=row['symbol'],values=(row['name'],row['symbol'],row['score'],row['news']['count'],row['reason']))

    def selected(self,event=None):
        picks=self.tree.selection()
        if not picks or not self.report:return
        row=next(r for r in self.report['rows'] if r['symbol']==picks[0])
        from stock_candidates import CHECK_NAMES
        lines=[row['name']+' ('+row['symbol']+')',row['reason'],'재무 기준: '+row['report']['report_end'],
               ' / '.join(label+(': 통과' if row['report']['checks'][k] else ': 미달') for k,label in CHECK_NAMES.items())]
        lines.extend('공시: '+url for url in row['report'].get('sources',[]))
        for article in row['news'].get('articles',[])[:10]:lines.extend((article['published_at'][:10]+' · '+article['title'],article['url']))
        self.set_text(self.details,'\n'.join(lines))

    def render_paper(self,s):
        if not s:return
        initial=float(s['settings']['capital']);equity=float(s['equity']);rate=(equity/initial-1)*100
        self.metrics.set(f"모의 평가액 {equity:,.0f}원   |   누적 {rate:+.2f}%   |   비교 목표 +10% ({initial*1.1:,.0f}원)\n최대 낙폭 {float(s['drawdown'])*100:.2f}%   |   보유 {s['symbol'] or '-'} {s['quantity']}주   |   거래 {len(s['trades'])}건")
        self.set_text(self.history,'\n'.join(f"{r['time'][:19]} {r['side']} {r['symbol']} {r['quantity']}주 · {r['reason']}" for r in s['trades'][-30:]))
        self.chart.delete('all');points=[float(r['equity']) for r in s['history']]
        if len(points)<2:
            self.chart.create_text(20,30,anchor='w',fill=self.colors['muted'],text='관측이 2회 이상 쌓이면 비용 반영 모의 평가액을 표시합니다.');return
        width=max(700,self.chart.winfo_width());low=min(points);high=max(points)
        coords=[]
        for i,value in enumerate(points):coords.extend((20+i*(width-40)/(len(points)-1),150-(value-low)/max(1,high-low)*110))
        self.chart.create_line(*coords,fill=self.colors['accent'],width=2)
        self.chart.create_text(20,12,anchor='w',fill=self.colors['muted'],text=f'관측 구간 모의 평가액 · 최저 {low:,.0f}원 / 최고 {high:,.0f}원')

    def preview(self):
        self.stop_watch()
        self.stop_paper()
        try:
            service=self.connect();saved=(Store(service.data/'approved_state.json').data or {}).get('advisor_config') or Store(service.data/'approved_config.json').data
            picks=self.tree.selection()
            symbol=picks[0] if picks else (saved['symbol'] if saved else '')
            if not symbol:raise SafetyStop('추천 목록에서 검토할 종목을 선택하세요.')
            self.offer=None;self.book.select(self.tabs['실제 주문 승인'])
            self.task('주문안',lambda:service.prepare(symbol))
        except Exception as exc:messagebox.showerror('주문안 준비',error_text(exc),parent=self.root)

    def start_watch(self):
        if self.busy or self.closing:return
        self.stop_watch();self.stop_paper()
        try:
            self.connect()
            picks=self.tree.selection()
            saved=(Store(self.service.data/'approved_state.json').data or {}).get('advisor_config') or Store(self.service.data/'approved_config.json').data
            symbol=picks[0] if picks else (saved['symbol'] if saved else '')
            if not symbol:raise SafetyStop('추천 목록에서 감시할 종목을 선택하세요.')
            self.watch_symbol=symbol;self.watch_seen=None;self.offer=None
            self.book.select(self.tabs['실제 주문 승인']);self.watch_tick()
        except Exception as exc:
            self.stop_watch();messagebox.showerror('승인 알림 준비',error_text(exc),parent=self.root)

    def stop_watch(self):
        self.watch_symbol=None;self.watch_seen=None
        if self.watch_timer:self.root.after_cancel(self.watch_timer);self.watch_timer=None
        self.offer=None
        if hasattr(self,'approve_button'):self.approve_button.configure(state='disabled')
        if not self.busy and not self.automatic:
            for entry in getattr(self,'entries',{}).values():entry.configure(state='normal')

    def watch_tick(self):
        self.watch_timer=None
        if not self.watch_symbol or self.closing:return
        if self.busy:
            self.watch_timer=self.root.after(1000,self.watch_tick);return
        service=self.service;symbol=self.watch_symbol
        self.offer=None
        self.task('승인 알림',lambda:service.prepare(symbol))

    def watch_result(self,result):
        if not self.watch_symbol or self.closing:return
        if result.get('status')!='APPROVAL_REQUIRED':
            self.watch_seen=None;self.offer=None
            self.set_text(self.order_text,describe_status(json.dumps(result)));return
        self.offer=result;self.set_text(self.order_text,self.offer_text(result))
        key=(result['symbol'],result['side'],result['reason'])
        if key!=self.watch_seen:
            self.watch_seen=key
            self.book.select(self.tabs['실제 주문 승인'])
            self.approve()

    def offer_text(self,offer):
        action='매수' if offer['side']=='BUY' else '매도'
        amount=float(offer['price'])*offer['quantity'];c=self.service.c
        estimated=amount*(c['fee']+(c['sell_reserve'] if offer['side']=='SELL' else 0))
        return (f"실제 {action} 주문안 · 아직 전송하지 않음\n\n종목: {offer['symbol']}\n수량: {offer['quantity']}주\n지정가: {float(offer['price']):,.0f}원\n주문 금액: {amount:,.0f}원\n비용 예비 추정: {estimated:,.0f}원 (설정 가정, 실제 정산과 다를 수 있음)\n판단: {offer['reason']}\n생성 시각: {offer['created'][:19]} · 유효 120초\n\n승인 시 최신 계좌·호가·수수료·조건을 다시 확인합니다.\n확인된 주문도 체결을 보장하지 않습니다. 토스 앱에서 주문을 확인하세요.")

    def approve(self):
        if not self.offer or self.busy:return
        offer=self.offer
        if not messagebox.askyesno('이 주문 한 건을 실제 전송',self.offer_text(offer)+'\n\n위 주문 한 건을 승인하시겠습니까?',parent=self.root,default=messagebox.NO):return
        if self.closing or self.offer is not offer:return
        self.offer=None;self.task('실제 승인',lambda:self.service.approve(offer['id']))

    def cancel_order(self):
        if self.busy or not self.service:return
        if not messagebox.askyesno('미체결 취소 승인','이 프로그램이 기록한 미체결 주문의 잔여 수량 취소를 요청할까요?\n취소 결과는 별도 확인하며 자동 재주문하지 않습니다.',parent=self.root):return
        self.offer=None;self.task('취소 승인',self.service.cancel)

    def export(self):
        try:
            service=self.connect()
            path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.csv',initialfile='추천매매_모의거래.csv')
            if path:service.paper.export(path);self.note('모의 거래 CSV 저장 완료')
        except Exception as exc:messagebox.showerror('저장',error_text(exc),parent=self.root)

    def archive_paper(self):
        if self.busy:return
        self.stop_watch()
        if not messagebox.askyesno('모의 기록 보관','현재 모의 기록을 보관하고 새 예산으로 모의매매를 시작할까요?\n실제 주문 기록은 바꾸지 않습니다.',parent=self.root):return
        self.stop_paper();path=self.path/'advisor/paper.json'
        if path.exists():path.rename(path.with_name('paper_'+now_kst().strftime('%Y%m%d_%H%M%S_%f')+'.json'))
        self.service=None;self.offer=None;self.metrics.set('새 모의매매 준비 · 예산을 확인하세요.');self.chart.delete('all')

    def credentials(self):
        if self.busy:return
        self.stop_watch()
        self.stop_paper()
        prior=getattr(self,'settings_window',None)
        if prior is not None and prior.winfo_exists():prior.lift();return
        path=self.path/'advisor/credentials.dpapi'
        try:saved=load_credentials(path if path.exists() else self.path/'runtime/credentials.dpapi')
        except Exception:
            messagebox.showerror('인증 확인','저장된 인증정보를 읽지 못했습니다. Windows 사용자와 암호화 파일을 확인하세요.',parent=self.root);return
        window=tk.Toplevel(self.root);window.title('인증·계좌 설정');window.transient(self.root)
        window.configure(bg=self.colors['bg']);self.settings_window=window
        fields={};verified=[]
        names={'TOSS_CLIENT_ID':'토스 Client ID','TOSS_CLIENT_SECRET':'토스 Client Secret','TOSS_ACCOUNT_SEQ':'계좌 선택값 (accountSeq)',
               'KRX_ID':'KRX 아이디','KRX_PW':'KRX 비밀번호','DART_API_KEY':'DART 인증키',
               'NAVER_CLIENT_ID':'API HUB Client ID','NAVER_CLIENT_SECRET':'API HUB Client Secret'}
        for i,key in enumerate(KEYS):
            ttk.Label(window,text=names[key]).grid(row=i,column=0,padx=12,pady=6,sticky='w')
            fields[key]=tk.StringVar(value=saved.get(key,''))
            if key=='TOSS_ACCOUNT_SEQ':
                fields[key].set('')
                selector=ttk.Combobox(window,textvariable=fields[key],state='readonly',width=38)
                selector.grid(row=i,column=1,padx=12,pady=6)
            else:
                entry=ttk.Entry(window,textvariable=fields[key],show='●',width=38)
                entry.grid(row=i,column=1,padx=14,pady=5)
                toggle=ttk.Button(window,text='👁 보기',width=10,style='Compact.TButton')
                def reveal(target=entry,button=toggle):
                    visible=bool(target.cget('show'))
                    target.configure(show='' if visible else '●')
                    button.configure(text='👁 숨기기' if visible else '👁 보기')
                toggle.configure(command=reveal);toggle.grid(row=i,column=2,padx=(0,14),pady=5)
        note=tk.StringVar(value='토스 계좌 조회 후 선택하세요. KRX·DART·NAVER 키는 뉴스·재무 분석에 사용합니다.')
        ttk.Label(window,textvariable=note,wraplength=580).grid(row=9,column=0,columnspan=2,padx=12,pady=8)
        account_queue=queue.Queue();pending=[False];identity=[None]
        def invalidate(*args):
            verified.clear();identity[0]=None
            fields['TOSS_ACCOUNT_SEQ'].set('');selector.configure(values=())
            note.set('토스 인증정보가 변경되었습니다. 계좌를 다시 조회하세요.')
        for key in KEYS[:2]:fields[key].trace_add('write',invalidate)
        def lookup():
            if pending[0]:return
            values={k:v.get().strip() for k,v in fields.items()}
            if not values['TOSS_CLIENT_ID'] or not values['TOSS_CLIENT_SECRET']:note.set('토스 인증키를 입력하세요.');return
            invalidate();pending[0]=True;note.set('계좌 조회 중… 주문은 발생하지 않습니다.')
            def worker():
                try:
                    broker=TossBroker(live=False)
                    broker.credentials=(values['TOSS_CLIENT_ID'],values['TOSS_CLIENT_SECRET'])
                    accounts=list(dict.fromkeys(str(r['accountSeq']) for r in broker.get('accounts') if r['accountType']=='BROKERAGE' and str(r['accountSeq']).isdigit()))
                    account_queue.put((True,accounts,values))
                except Exception as exc:account_queue.put((False,error_text(exc),values))
            threading.Thread(target=worker,daemon=True).start()
        def poll_accounts():
            if not window.winfo_exists():return
            try:
                ok,data,values=account_queue.get_nowait();pending[0]=False
                if ok and all(fields[k].get().strip()==values[k] for k in KEYS[:2]):
                    verified[:]=data;identity[0]=(values[KEYS[0]],values[KEYS[1]])
                    selector.configure(values=data);fields['TOSS_ACCOUNT_SEQ'].set(data[0] if len(data)==1 else '')
                    note.set('계좌가 하나여서 자동 선택했습니다.' if len(data)==1 else '사용할 계좌를 선택 목록에서 선택하세요.' if data else '선택 가능한 계좌가 없습니다. API 키·허용 IP·계좌 상태를 확인하고 다시 조회하세요.')
                else:note.set(data if not ok else '인증이 변경됐습니다. 다시 조회하세요.')
            except queue.Empty:pass
            window.after(150,poll_accounts)
        def save():
            if pending[0]:note.set('계좌 조회가 끝난 뒤 저장하세요.');return
            values={k:v.get().strip() for k,v in fields.items()}
            if values['TOSS_ACCOUNT_SEQ'] not in verified or identity[0]!=(values[KEYS[0]],values[KEYS[1]]):note.set('현재 인증으로 계좌를 조회하고 선택하세요.');return
            if any(not values.get(k) for k in KEYS):note.set('모든 인증정보를 입력하세요.');return
            try:
                save_credentials(values,path);self.service=None;self.offer=None
                self.approve_button.configure(state='disabled')
                self.note('추천매매 전용 인증 저장 완료');window.destroy()
            except Exception as exc:note.set(error_text(exc))
        ttk.Button(window,text='계좌 조회',command=lookup).grid(row=10,column=0,padx=12,pady=12)
        ttk.Button(window,text='암호화 저장',command=save,style='Success.TButton').grid(row=10,column=1,padx=12,pady=12)
        def template():
            from settings_file import create_template
            path=filedialog.asksaveasfilename(parent=window,title='빈 설정 템플릿 저장',
                initialfile='KoreanStockBot_settings.json',defaultextension='.json',filetypes=[('설정 템플릿','*.json')])
            if not path:return
            try:
                create_template(path)
                note.set('빈 템플릿을 만들었습니다. 메모장으로 값을 입력하고 저장한 뒤 암호화 변환하세요. 계좌 선택값은 비워 두고 조회해도 됩니다.')
            except Exception: note.set('템플릿 저장 실패. 저장 위치와 파일 권한을 확인하세요.')

        def encrypt_file():
            from settings_file import encrypt_template
            source=filedialog.askopenfilename(parent=window,title='작성한 JSON 템플릿 선택',filetypes=[('설정 템플릿','*.json')])
            if not source:return
            destination=filedialog.asksaveasfilename(parent=window,title='암호화 설정 파일 저장',
                initialfile=Path(source).stem+'.ksbkey',defaultextension='.ksbkey',filetypes=[('암호화 설정','*.ksbkey')])
            if not destination:return
            try: encrypt_template(source,destination)
            except Exception:
                note.set('암호화 실패. 템플릿 형식, 토스 ID·Secret 입력, 저장 위치를 확인하세요.');return
            note.set('암호화 저장 완료. 같은 PC의 동일 Windows 사용자로 불러올 수 있습니다. 설정 파일 불러오기를 누르세요.')
            if messagebox.askyesno('평문 원본 정리','암호화 파일을 저장하고 복호화 검증을 마쳤습니다.\n키가 그대로 보이는 원본 JSON 파일을 삭제할까요?\n동기화·백업 사본까지 지우는 것은 아닙니다.',parent=window):
                try: Path(source).unlink()
                except OSError: note.set('암호화 파일은 저장됐지만 평문 원본 삭제에 실패했습니다. 원본을 직접 정리하세요.')
            else: note.set('암호화 완료. 평문 원본 JSON은 남아 있으므로 안전하게 보관하거나 삭제하세요.')

        def import_file():
            if pending[0]:
                note.set('계좌 조회가 끝난 뒤 파일을 불러오세요.');return
            from settings_file import load_settings
            path=filedialog.askopenfilename(parent=window,title='암호화 설정 파일 불러오기',filetypes=[('암호화 설정','*.ksbkey')])
            if not path:return
            try: imported=load_settings(path)
            except Exception:
                note.set('파일을 해독하지 못했습니다. 정상 암호화 파일인지, 같은 PC·Windows 사용자인지 확인하세요.');return
            for key,var in fields.items():
                if key!='TOSS_ACCOUNT_SEQ':var.set(imported['credentials'].get(key,''))
            # Imported identity must still be verified by a fresh broker lookup.
            invalidate()
            for widget in window.winfo_children():
                if isinstance(widget,ttk.Entry) and not isinstance(widget,ttk.Combobox):
                    widget.configure(show='●')
                if isinstance(widget,ttk.Button) and str(widget.cget('text')).startswith('👁'):widget.configure(text='👁 보기')
            note.set('암호화 설정을 불러왔습니다. 계좌 조회 → 사용할 계좌 선택 → 암호화 저장을 눌러 적용하세요.')

        for column,(label,command) in enumerate([('설정 템플릿 생성',template),('템플릿 암호화 변환',encrypt_file),('설정 파일 불러오기',import_file)]):
            ttk.Button(window,text=label,command=command,style=button_style(label),cursor='hand2').grid(row=11,column=column,padx=8,pady=(0,12))

        window.after(150,poll_accounts)
        window.grab_set()

    def poll(self):
        try:
            while True:
                event=self.events.get_nowait()
                if event[0]=='progress':self.status.set(event[1]);continue
                self.busy=False
                for b in self.buttons:b.configure(state='normal')
                for entry in self.entries.values():entry.configure(state='disabled' if self.automatic or self.watch_symbol else 'normal')
                kind=event[1]
                if event[0]=='error':
                    if self.watch_symbol:self.stop_watch()
                    self.offer=None;self.note(event[2])
                    if kind in ('실제 승인','취소 승인'):self.set_text(self.order_text,event[2]+'\n주문 전송 결과가 불명확하면 토스 앱에서 확인하세요. 자동 재전송하지 않습니다.')
                elif kind=='분석':
                    self.render_report(event[2]);self.note(f"분석 완료 · 뉴스 검토 {len(event[2]['rows'])}개 · 모의매매 또는 주문안 검토 가능")
                elif kind=='모의 감시':
                    self.render_report(self.service.report);self.render_paper(self.service.paper.s);self.note(event[2])
                elif kind=='승인 알림':self.watch_result(event[2])
                elif kind=='주문안':
                    result=event[2]
                    if result.get('status')=='APPROVAL_REQUIRED':self.offer=result;self.set_text(self.order_text,self.offer_text(result));self.note('새 실제 주문안 · 검토 후 승인 대기')
                    else:self.offer=None;self.set_text(self.order_text,describe_status(json.dumps(result)));self.note('주문안 없음 · 계좌/매매 조건 확인 완료')
                elif kind=='실제 승인':
                    self.set_text(self.order_text,'주문 접수 응답 확인 · 체결 확정 아님\n'+describe_status(json.dumps(event[2]))+'\n주문안 / 체결 확인으로 후속 상태를 조회하세요.');self.note('승인 주문 1건 전송 · 추가 주문은 다시 승인해야 합니다.')
                elif kind=='취소 승인':self.set_text(self.order_text,event[2]);self.note(event[2])
                self.approve_button.configure(state='normal' if self.offer and not self.busy else 'disabled')
                if self.watch_symbol and not self.closing and self.watch_timer is None:
                    self.watch_timer=self.root.after(5000,self.watch_tick)
                if self.automatic and not self.closing and self.timer is None:self.timer=self.root.after(30000,self.paper_tick)
        except queue.Empty:pass
        if self.closing and not self.busy:self.root.destroy();return
        self.root.after(100,self.poll)

    def close(self):
        self.stop_watch()
        self.automatic=False;self.closing=True
        if getattr(self,'active_kind','') not in ('실제 승인','취소 승인'):self.cancel_event.set()
        if self.busy:self.note('진행 작업의 결과 기록 후 종료합니다. 실제 미체결은 토스 앱에서 확인하세요.')
        else:self.root.destroy()


def main():
    with process_lock(ROOT/'advisor/window.lock'):
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('KoreanStockBot.Desktop.advisor')
        root=tk.Tk();AdvisorWindow(root);root.mainloop()


if __name__=='__main__':main()
