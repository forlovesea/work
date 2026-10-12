"""Desktop controller for the existing locked trading subprocess."""
import json
import hashlib
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from runtime_status import describe_status, exit_status, KST
from button_theme import button_style
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from live import ROOT, Store, process_lock, SafetyStop
from credentials import KEYS, load_credentials, save_credentials


def account_view(snapshot,config):
    capital=float(config['capital'])
    equity=float(snapshot['last_equity'])
    # Initial baseline is the managed capital, not the whole account balance.
    report={'return_pct':(equity/capital-1)*100,
            'max_drawdown_pct':float(snapshot.get('observed_max_drawdown',0))*100}
    return SimpleNamespace(cfg=SimpleNamespace(capital=float(snapshot.get('equity_history_base',capital))),
        equity=snapshot.get('equity_history',[]),report=lambda:report)


class LivePanel:
    def __init__(self,root,parent,buttons,mode,colors,status,on_snapshot):
        self.root,self.mode,self.colors,self.status=root,mode,colors,status
        self.on_snapshot=on_snapshot
        self.child=None
        self.querying=False
        self.events=queue.Queue()
        self.live=False
        self.closing=False
        self.exit_unverified=False
        self.last_received=None
        self.stop_started=None
        self.stop_confirmed=False
        self.runtime_text=tk.StringVar(value='실행 대기 · 실전 시작 후 연결 및 시장 상태를 표시합니다.')
        self.config_path=ROOT/('etf_config.json' if mode=='etf' else 'live_config.json')
        self.config=json.loads(self.config_path.read_text(encoding='utf-8-sig'))
        self.prefix='etf_' if mode=='etf' else ''
        self.actions=[]
        for label,command in [('인증·계좌 설정',self.settings),('읽기 전용 점검',lambda:self.start(False)),
                              ('실전 시작',lambda:self.start(True)),('중지 요청',self.stop)]:
            b=ttk.Button(buttons,text=label,command=command,style=button_style(label),cursor='hand2')
            b.pack(side='left',padx=4)
            self.actions.append(b)
        self.actions[-1].configure(state='disabled')
        if mode=='etf':
            ttk.Button(buttons,text='ETF 후보 제안',command=self.scope_settings,style='Violet.TButton').pack(side='left',padx=4)
        ttk.Label(parent,text=f"운용 원금 {self.config['capital']:,}원 · 매수 상한 {self.config['max_order_won']:,}원 · 원화 현금만 사용",style='Muted.TLabel').pack(anchor='w',padx=28)
        ttk.Label(parent,textvariable=self.runtime_text,wraplength=760,justify='left',
                  font=('맑은 고딕',11,'bold')).pack(fill='x',padx=28,pady=(8,4))
        self.data_text=tk.StringVar(value='자료 수집 상태: 아직 확인하지 않았습니다.')
        if mode=='etf':
            ttk.Label(parent,textvariable=self.data_text,wraplength=760,justify='left',style='Muted.TLabel').pack(fill='x',padx=28,pady=6)
        log_frame=ttk.Frame(parent)
        log_frame.pack(fill='x',padx=28,pady=(6,16))
        log_frame.columnconfigure(0,weight=1)
        self.log=tk.Text(log_frame,height=7,bg=colors['panel'],fg=colors['text'],insertbackground=colors['text'],font=('맑은 고딕',10),wrap='none',state='disabled')
        self.log.grid(row=0,column=0,sticky='nsew')
        log_y=ttk.Scrollbar(log_frame,orient='vertical',command=self.log.yview)
        log_y.grid(row=0,column=1,sticky='ns')
        log_x=ttk.Scrollbar(log_frame,orient='horizontal',command=self.log.xview)
        log_x.grid(row=1,column=0,sticky='ew')
        self.log.configure(yscrollcommand=log_y.set,xscrollcommand=log_x.set)
        def log_wheel(event):
            units=-1 if event.delta>0 else 1
            if event.state & 0x1:self.log.xview_scroll(units,'units')
            else:self.log.yview_scroll(units,'units')
            return 'break'
        self.log.bind('<MouseWheel>',log_wheel)
        self.log_line('대기 중. 인증·계좌 설정 → 읽기 전용 점검 → 실전 시작 순서입니다. 창을 여는 것만으로 주문하지 않습니다.')
        self.root.after(300,self.poll)

    def log_line(self,text):
        follow=self.log.yview()[1]>=.99
        self.log.configure(state='normal')
        self.log.insert('end',text+'\n')
        if int(self.log.index('end-1c').split('.')[0])>250: self.log.delete('1.0','50.0')
        if follow:self.log.see('end')
        self.log.configure(state='disabled')

    def active(self): return self.child is not None and self.child.poll() is None

    def scope_settings(self):
        if self.closing:return
        from candidate_gui import show
        show(self)

    def env(self,values=None):
        env=os.environ.copy()
        env.update(load_credentials() if values is None else values)
        for key in KEYS:
            if key in env: env[key]=env[key].strip()
        env['PYTHONIOENCODING']='utf-8'
        return env

    def spawn(self,args,env):
        from app_paths import worker_command
        return subprocess.Popen(worker_command('live')+args,
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)

    def settings(self):
        if self.active() or self.querying or self.closing: return
        try: values=self.env()
        except Exception:
            messagebox.showerror('인증 확인','저장된 인증정보를 읽지 못했습니다. Windows 사용자와 암호화 파일을 확인하세요.'); return
        window=tk.Toplevel(self.root); window.title('인증·계좌 설정'); window.configure(bg=self.colors['bg'])
        window.transient(self.root); window.grab_set()
        fields={}
        verified_accounts=[]
        names={'TOSS_CLIENT_ID':'토스 Client ID','TOSS_CLIENT_SECRET':'토스 Client Secret','TOSS_ACCOUNT_SEQ':'계좌 선택값 (accountSeq)',
               'KRX_ID':'KRX 아이디','KRX_PW':'KRX 비밀번호','DART_API_KEY':'DART 인증키',
               'NAVER_CLIENT_ID':'API HUB Client ID','NAVER_CLIENT_SECRET':'API HUB Client Secret'}
        needed=KEYS if self.mode=='etf' else KEYS[:3]
        for row,key in enumerate(needed):
            ttk.Label(window,text=names[key]).grid(row=row,column=0,sticky='w',padx=14,pady=5)
            fields[key]=tk.StringVar(value=values.get(key,'').strip())
            if key=='TOSS_ACCOUNT_SEQ':
                fields[key].set('')
                account_selector=ttk.Combobox(window,textvariable=fields[key],state='readonly',width=36)
                account_selector.grid(row=row,column=1,padx=14,pady=5)
            else:
                entry=ttk.Entry(window,textvariable=fields[key],show='●',width=38)
                entry.grid(row=row,column=1,padx=14,pady=5)
                toggle=ttk.Button(window,text='👁 보기',width=10,style='Compact.TButton')
                def reveal(target=entry,button=toggle):
                    visible=bool(target.cget('show'))
                    target.configure(show='' if visible else '●')
                    button.configure(text='👁 숨기기' if visible else '👁 보기')
                toggle.configure(command=reveal)
                toggle.grid(row=row,column=2,padx=(0,14),pady=5)
        row=len(needed)
        symbol=tk.StringVar(value=self.config.get('symbol',''))
        if self.mode=='stock':
            ttk.Label(window,text='국내 종목코드 (6자리)').grid(row=row,column=0,padx=14,pady=5)
            ttk.Entry(window,textvariable=symbol).grid(row=row,column=1,padx=14,pady=5); row+=1
        note=tk.StringVar(value='계좌 조회 후 사용할 계좌를 목록에서 선택하세요. 계좌가 하나면 자동 선택됩니다.')
        ttk.Label(window,textvariable=note,wraplength=510).grid(row=row,column=0,columnspan=2,padx=14,pady=10)

        last_auth=[tuple(fields[k].get().strip() for k in ('TOSS_CLIENT_ID','TOSS_CLIENT_SECRET'))]
        def invalidate(*args):
            verified_accounts.clear()
            fields['TOSS_ACCOUNT_SEQ'].set('')
            account_selector.configure(values=())
            note.set('토스 인증정보가 변경되었습니다. 계좌를 다시 조회하세요.')
        def auth_changed(*args):
            current=tuple(fields[k].get().strip() for k in ('TOSS_CLIENT_ID','TOSS_CLIENT_SECRET'))
            if current!=last_auth[0]:
                last_auth[0]=current
                invalidate()
        for key in ('TOSS_CLIENT_ID','TOSS_CLIENT_SECRET'):
            fields[key].trace_add('write',auth_changed)

        def receive(accounts,submitted):
            if not window.winfo_exists(): return
            if any(fields[k].get().strip()!=submitted[k] for k in ('TOSS_CLIENT_ID','TOSS_CLIENT_SECRET')):
                invalidate(); return
            verified_accounts[:]=accounts
            account_selector.configure(values=accounts)
            fields['TOSS_ACCOUNT_SEQ'].set(accounts[0] if len(accounts)==1 else '')
            note.set('계좌가 하나여서 자동 선택했습니다.' if len(accounts)==1 else
                     '사용할 계좌를 선택 목록에서 선택하세요.' if accounts else
                     '선택 가능한 계좌가 없습니다. API 키·허용 IP·계좌 상태를 확인하고 다시 조회하세요.')

        def query():
            if self.querying or self.closing:return
            submitted={k:v.get().strip() for k,v in fields.items()}
            if not submitted.get('TOSS_CLIENT_ID') or not submitted.get('TOSS_CLIENT_SECRET'):
                note.set('토스 Client ID와 Secret을 입력하세요.'); return
            verified_accounts.clear()
            account_selector.configure(values=())
            fields['TOSS_ACCOUNT_SEQ'].set('')
            self.querying=True; note.set('계좌 조회 중… 주문은 발생하지 않습니다.')
            def work():
                try:
                    proc=self.spawn(['--accounts'],self.env(submitted))
                    try: out,_=proc.communicate(timeout=90)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.communicate(); raise TimeoutError()
                    accounts=json.loads(out) if proc.returncode==0 else None
                    result=list(dict.fromkeys(str(a['accountSeq']) for a in accounts
                        if a['accountType']=='BROKERAGE' and str(a['accountSeq']).isdigit())) if accounts is not None else []
                    self.events.put(('accounts',receive,result,submitted))
                except Exception:
                    self.events.put(('accounts',receive,[],submitted))
            threading.Thread(target=work,daemon=True).start()

        def save():
            if self.querying:
                note.set('계좌 조회가 끝난 뒤 저장하세요.'); return
            submitted={k:v.get().strip() for k,v in fields.items()}
            if submitted['TOSS_ACCOUNT_SEQ'] not in verified_accounts:
                note.set('계좌 조회 후 사용할 계좌를 선택하세요.'); return
            if any(not submitted.get(k) for k in needed):
                note.set('모든 인증정보를 입력하세요.'); return
            if self.mode=='stock' and not re.fullmatch('[0-9A-Z]{6}',symbol.get().strip().upper()):
                note.set('유효한 국내 종목코드 6자리를 입력하세요.'); return
            try:
                with process_lock(ROOT/'runtime'/'bot.lock'):
                    config=json.loads(self.config_path.read_text(encoding='utf-8-sig'))
                    if self.mode=='stock' and config['symbol']!=symbol.get().strip().upper():
                        if (ROOT/'runtime'/'live_state.json').exists(): raise SafetyStop('실전 기록이 있어 종목을 바꿀 수 없습니다. 기존 주문·보유 상태를 먼저 정산하세요.')
                        config['symbol']=symbol.get().strip().upper()
                        config_store=Store(self.config_path); config_store.data=config; config_store.save()
                    saved=load_credentials(); saved.update(submitted); save_credentials(saved)
                    self.config=config
                window.destroy(); self.log_line('인증정보를 Windows 암호화 저장했습니다. 읽기 전용 점검으로 연결을 확인하세요.')
            except Exception as exc:
                note.set(str(exc) if isinstance(exc,SafetyStop) else '설정 저장 실패. 다른 봇 실행 여부와 파일 권한을 확인하세요.')
        ttk.Button(window,text='계좌 조회',command=query,style=button_style('계좌 조회')).grid(row=row+1,column=0,padx=14,pady=12)
        ttk.Button(window,text='암호화 저장',command=save,style='Success.TButton').grid(row=row+1,column=1,padx=14,pady=12)

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
            if self.querying:
                note.set('계좌 조회가 끝난 뒤 파일을 불러오세요.');return
            from settings_file import load_settings
            path=filedialog.askopenfilename(parent=window,title='암호화 설정 파일 불러오기',filetypes=[('암호화 설정','*.ksbkey')])
            if not path:return
            try: imported=load_settings(path)
            except Exception:
                note.set('파일을 해독하지 못했습니다. 정상 암호화 파일인지, 같은 PC·Windows 사용자인지 확인하세요.');return
            for key,var in fields.items():
                if key!='TOSS_ACCOUNT_SEQ':var.set(imported['credentials'].get(key,''))
            if self.mode=='stock' and imported['symbol']:symbol.set(imported['symbol'])
            # Imported identity must still be verified by a fresh broker lookup.
            invalidate()
            for widget in window.winfo_children():
                if isinstance(widget,ttk.Entry) and not isinstance(widget,ttk.Combobox):
                    if str(widget.cget('textvariable'))!=str(symbol):widget.configure(show='●')
                if isinstance(widget,ttk.Button) and str(widget.cget('text')).startswith('👁'):widget.configure(text='👁 보기')
            note.set('암호화 설정을 불러왔습니다. 계좌 조회 → 사용할 계좌 선택 → 암호화 저장을 눌러 적용하세요.')

        for column,(label,command) in enumerate([('설정 템플릿 생성',template),('템플릿 암호화 변환',encrypt_file),('설정 파일 불러오기',import_file)]):
            ttk.Button(window,text=label,command=command,style=button_style(label),cursor='hand2').grid(row=row+2,column=column,padx=8,pady=(0,12))

    def start(self,live):
        if self.active() or self.querying or self.closing:return
        self.exit_unverified=False
        try:
            env=self.env()
            self.config=json.loads(self.config_path.read_text(encoding='utf-8-sig'))
            self.binding=hashlib.sha256((env.get('TOSS_ACCOUNT_SEQ','')+'|'+json.dumps(self.config,sort_keys=True)).encode()).hexdigest()
            needed=KEYS if self.mode=='etf' else KEYS[:3]
            if any(not env.get(k) for k in needed):
                messagebox.showerror('인증 필요','인증·계좌 설정을 먼저 완료하세요.');return
            if live and not messagebox.askyesno('실제 주문 시작',f"{self.mode.upper()} 모드에서 실제 매수·매도가 발생합니다.\n원금 {self.config['capital']:,}원 / 매수 상한 {self.config['max_order_won']:,}원\n실전 체결은 아직 검증되지 않았습니다. 시작할까요?"): return
            with process_lock(ROOT/'runtime'/'bot.lock'):
                if (ROOT/'STOP').exists():
                    if not messagebox.askyesno('중지 상태 해제','토스의 기존 주문·보유분을 확인했나요?\nSTOP 파일만 제거하고 같은 계좌·설정으로 시작합니다.'):return
                    (ROOT/'STOP').unlink()
            self.live=live
            self.last_received=time.monotonic()
            self.received_status=False
            self.stop_started=None
            self.stop_confirmed=False
            self.reader_done=False
            self.runtime_base='연결 중 · 계좌 및 시장 상태를 아직 확인하지 못했습니다.'
            self.runtime_text.set(self.runtime_base)
            args=(['--etf'] if self.mode=='etf' else [])+(['--live'] if live else [])
            self.child=self.spawn(args,env)
            for b in self.actions[:-1]:b.configure(state='disabled')
            self.actions[-1].configure(state='normal')
            self.status.set('실전 연결 중' if live else '읽기 전용 연결 중 · 주문 없음')
            self.log_line(self.status.get())
            self.last_stamp=None
            def reader(proc):
                for line in proc.stdout:
                    # live.py emits safe status only; never echo child environment.
                    self.events.put(('log',line.strip()))
                proc.stdout.close()
                self.events.put(('reader_done',))
            threading.Thread(target=reader,args=(self.child,),daemon=True).start()
        except Exception as exc:
            messagebox.showerror('시작 실패',str(exc) if isinstance(exc,SafetyStop) else '실행 파일·인증 저장·프로세스 잠금을 확인하세요.')

    def stop(self):
        if self.active():
            try:(ROOT/'STOP').touch()
            except OSError:
                messagebox.showerror('중지 요청 실패','STOP 파일을 생성하지 못했습니다. 토스 앱에서 주문을 확인하세요.');return False
            if self.stop_started is None:self.stop_started=time.monotonic()
            self.status.set('중지 요청 접수 · 진행 중인 작업 응답 후 주문 정리 확인 · 보유분 유지')
            self.runtime_base=self.status.get()
            self.runtime_text.set(self.runtime_base)
            self.log_line(self.status.get())
        return True

    def close(self):
        if self.closing:return
        if self.exit_unverified:
            if messagebox.askyesno('주문 확인 필요','정상 중지를 확인하지 못했습니다. 토스 앱에서 미체결·보유분을 직접 확인해야 합니다.\n이 상태를 확인하고 창을 닫으시겠습니까?'):
                self.root.destroy()
            return
        self.closing=True
        if self.active() and self.stop() is False:
            self.closing=False;return
        self.status.set('프로그램 종료 준비 · 조회 및 주문 정리 완료 대기 · 보유분 유지')
        self.runtime_text.set(self.status.get())
        if self.child is None and not self.querying:self.root.destroy()

    def finish_exit(self,code):
        self.exit_unverified=not (code==0 and self.stop_confirmed)
        if self.closing and self.exit_unverified:
            self.closing=False
            messagebox.showerror('자동 종료 보류','미체결 정리를 포함한 정상 중지를 확인하지 못했습니다. 창을 유지합니다.\n토스 앱에서 주문·보유분을 확인하세요.')

    def poll(self):
        while not self.events.empty():
            event=self.events.get_nowait()
            if event[0]=='reader_done':
                self.reader_done=True
            elif event[0]=='accounts':
                self.querying=False
                event[1](event[2],event[3])
            elif event[0]=='log':
                self.last_received=time.monotonic()
                self.received_status=True
                readable=describe_status(event[1])
                try:
                    report=json.loads(event[1]); details=report.get('selection_details')
                    if report.get('status')=='STOPPED':self.stop_confirmed=True
                    if details:
                        self.scope_details=details
                        from diagnostics import selection_text
                        detail_text=selection_text(details,limit=20)
                        if detail_text!=getattr(self,'last_details',None):
                            self.log_line(detail_text);self.last_details=detail_text
                except (ValueError,TypeError,AttributeError,KeyError):pass
                self.log_line(readable)
                self.runtime_base=('실전 | ' if self.live else '읽기 전용 | ')+readable
                self.runtime_base+='\n마지막 상태를 받은 시각: '+datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')+' (한국시간)'
                self.runtime_text.set(self.runtime_base)
                self.status.set(readable.split('\n')[0])
        if self.active() and self.last_received is not None:
            age=int(time.monotonic()-self.last_received)
            warning='\n응답 지연 · 현재 연결·주문 상태 확인 필요' if age>max(90,self.config['poll_seconds']*3) else ''
            elapsed=(f'마지막 상태 수신 후 경과: {age}초 (새 상태를 받으면 0초로 갱신)'
                     if self.received_status else f'첫 상태 수신 대기: {age}초 경과')
            self.runtime_text.set(self.runtime_base+'\n'+elapsed+warning)
            if self.stop_started is not None:
                stop_age=int(time.monotonic()-self.stop_started)
                stop_note=f'중지 요청 후 {stop_age}초 경과 · 종료 확인 전입니다. 보유분은 자동 매도하지 않습니다.'
                if stop_age>=60:
                    stop_note+='\n중지 처리 지연 · 통신 응답 또는 주문 정리 대기 중입니다. 토스 앱에서 미체결을 확인하세요.'
                self.runtime_text.set(self.runtime_text.get()+'\n'+stop_note)
        if self.child is not None:
            path=ROOT/'runtime'/(self.prefix+('live_state.json' if self.live else 'dry_state.json'))
            try:
                snapshot=Store(path).data
                if snapshot and snapshot.get('binding')==getattr(self,'binding',None):
                    history=snapshot.get('equity_history',[])
                    observed=history[-1].get('timestamp','') if history else '관측 대기'
                    symbol=snapshot.get('managed_symbol') or self.config.get('symbol') or 'ETF 후보 검색'
                    label=('실전 관측' if self.live else '읽기 전용 관측 · 실제 주문 없음')+f' / {symbol} / 마지막 관측: {observed}'
                    self.on_snapshot(snapshot,self.config,label)
            except (OSError,ValueError,KeyError,TypeError):
                self.status.set('상태 파일 확인 중 · 최신 값 표시 보류')
            if self.child.poll() is not None and getattr(self,'reader_done',False):
                code=self.child.returncode
                self.log_line(f'프로세스 종료 ({code}). 토스 앱에서 미체결·보유분을 확인하세요.')
                final_status=exit_status(code,self.stop_confirmed)
                self.status.set(final_status)
                self.runtime_text.set(final_status)
                self.log_line(final_status)
                self.child=None
                for b in self.actions[:-1]:b.configure(state='normal')
                self.actions[-1].configure(state='disabled')
                self.finish_exit(code)
        if self.mode=='etf' and self.active():
            try:
                state=Store(ROOT/'research'/'auto_status.json').data
                if state and state.get('updated_at')!=getattr(self,'last_research',None):
                    from diagnostics import source_text
                    self.last_research=state.get('updated_at')
                    description=source_text(state)
                    self.data_text.set(description)
                    self.log_line(description)
            except (OSError,ValueError,KeyError):pass
        if self.closing and self.child is None and not self.querying:
            self.root.destroy();return
        self.root.after(1000,self.poll)
