"""Desktop controller for the existing locked trading subprocess."""
import json
import hashlib
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk, messagebox
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
        self.config_path=ROOT/('etf_config.json' if mode=='etf' else 'live_config.json')
        self.config=json.loads(self.config_path.read_text(encoding='utf-8-sig'))
        self.prefix='etf_' if mode=='etf' else ''
        self.actions=[]
        for label,command in [('인증·계좌 설정',self.settings),('읽기 전용 점검',lambda:self.start(False)),
                              ('실전 시작',lambda:self.start(True)),('중지 요청',self.stop)]:
            b=ttk.Button(buttons,text=label,command=command,style='Primary.TButton' if label=='실전 시작' else 'TButton')
            b.pack(side='left',padx=4)
            self.actions.append(b)
        self.actions[-1].configure(state='disabled')
        ttk.Label(parent,text=f"운용 원금 {self.config['capital']:,}원 · 매수 상한 {self.config['max_order_won']:,}원 · 원화 현금만 사용",style='Muted.TLabel').pack(anchor='w',padx=28)
        self.log=tk.Text(parent,height=7,bg=colors['panel'],fg=colors['text'],insertbackground=colors['text'],font=('맑은 고딕',10),wrap='word',state='disabled')
        self.log.pack(fill='x',padx=28,pady=(6,16))
        self.log_line('대기 중. 인증·계좌 설정 → 읽기 전용 점검 → 실전 시작 순서입니다. 창을 여는 것만으로 주문하지 않습니다.')
        self.root.after(300,self.poll)

    def log_line(self,text):
        self.log.configure(state='normal')
        self.log.insert('end',text+'\n')
        if int(self.log.index('end-1c').split('.')[0])>250: self.log.delete('1.0','50.0')
        self.log.see('end'); self.log.configure(state='disabled')

    def active(self): return self.child is not None and self.child.poll() is None

    def env(self,values=None):
        env=os.environ.copy()
        env.update(load_credentials() if values is None else values)
        env['PYTHONIOENCODING']='utf-8'
        return env

    def spawn(self,args,env):
        executable=ROOT/'.venv'/'Scripts'/'python.exe'
        return subprocess.Popen([str(executable) if executable.exists() else sys.executable,'-u','-X','utf8',str(ROOT/'live.py')]+args,
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)

    def settings(self):
        if self.active() or self.querying: return
        try: values=self.env()
        except Exception:
            messagebox.showerror('인증 확인','저장된 인증정보를 읽지 못했습니다. Windows 사용자와 암호화 파일을 확인하세요.'); return
        window=tk.Toplevel(self.root); window.title('인증·계좌 설정'); window.configure(bg=self.colors['bg'])
        window.transient(self.root); window.grab_set()
        fields={}
        names={'TOSS_CLIENT_ID':'토스 Client ID','TOSS_CLIENT_SECRET':'토스 Client Secret','TOSS_ACCOUNT_SEQ':'계좌 선택값 (accountSeq)',
               'KRX_ID':'KRX 아이디','KRX_PW':'KRX 비밀번호','DART_API_KEY':'DART 인증키',
               'NAVER_CLIENT_ID':'네이버 Client ID','NAVER_CLIENT_SECRET':'네이버 Client Secret'}
        needed=KEYS if self.mode=='etf' else KEYS[:3]
        for row,key in enumerate(needed):
            ttk.Label(window,text=names[key]).grid(row=row,column=0,sticky='w',padx=14,pady=5)
            fields[key]=tk.StringVar(value=values.get(key,''))
            ttk.Entry(window,textvariable=fields[key],show='' if key=='TOSS_ACCOUNT_SEQ' else '●',width=38).grid(row=row,column=1,padx=14,pady=5)
        row=len(needed)
        symbol=tk.StringVar(value=self.config.get('symbol',''))
        if self.mode=='stock':
            ttk.Label(window,text='국내 종목코드 (6자리)').grid(row=row,column=0,padx=14,pady=5)
            ttk.Entry(window,textvariable=symbol).grid(row=row,column=1,padx=14,pady=5); row+=1
        note=tk.StringVar(value='계좌 조회를 누르면 사용 가능한 accountSeq가 표시됩니다.')
        ttk.Label(window,textvariable=note,wraplength=510).grid(row=row,column=0,columnspan=2,padx=14,pady=10)

        def query():
            if self.querying:return
            submitted={k:v.get().strip() for k,v in fields.items()}
            if not submitted.get('TOSS_CLIENT_ID') or not submitted.get('TOSS_CLIENT_SECRET'):
                note.set('토스 Client ID와 Secret을 입력하세요.'); return
            self.querying=True; note.set('계좌 조회 중… 주문은 발생하지 않습니다.')
            def work():
                try:
                    proc=self.spawn(['--accounts'],self.env(submitted))
                    try: out,_=proc.communicate(timeout=90)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.communicate(); raise TimeoutError()
                    accounts=json.loads(out) if proc.returncode==0 else None
                    result=', '.join(str(a['accountSeq']) for a in accounts if a['accountType']=='BROKERAGE') if accounts is not None else ''
                    self.events.put(('accounts',note,'선택 가능한 accountSeq: '+result if result else '조회 실패. API 키·허용 IP·다른 봇 실행 여부를 확인하세요.'))
                except Exception:
                    self.events.put(('accounts',note,'조회 실패. 연결과 인증 설정을 확인하세요.'))
            threading.Thread(target=work,daemon=True).start()

        def save():
            if self.querying:
                note.set('계좌 조회가 끝난 뒤 저장하세요.'); return
            submitted={k:v.get().strip() for k,v in fields.items()}
            if any(not submitted.get(k) for k in needed) or not submitted['TOSS_ACCOUNT_SEQ'].isdigit():
                note.set('모든 인증정보와 숫자로 된 accountSeq를 입력하세요.'); return
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
        ttk.Button(window,text='계좌 조회',command=query).grid(row=row+1,column=0,padx=14,pady=12)
        ttk.Button(window,text='암호화 저장',command=save).grid(row=row+1,column=1,padx=14,pady=12)

    def start(self,live):
        if self.active() or self.querying:return
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
            threading.Thread(target=reader,args=(self.child,),daemon=True).start()
        except Exception as exc:
            messagebox.showerror('시작 실패',str(exc) if isinstance(exc,SafetyStop) else '실행 파일·인증 저장·프로세스 잠금을 확인하세요.')

    def stop(self):
        if self.active():
            try:(ROOT/'STOP').touch()
            except OSError:
                messagebox.showerror('중지 요청 실패','STOP 파일을 생성하지 못했습니다. 토스 앱에서 주문을 확인하세요.');return
            self.status.set('중지 요청 · 미체결 취소 확인 대기 / 보유분은 유지')
            self.log_line(self.status.get())

    def close(self):
        if self.querying:
            messagebox.showinfo('조회 중','계좌 조회가 끝난 뒤 닫아주세요.');return
        if self.active():
            if messagebox.askyesno('중지 후 닫기','미체결 취소를 요청하고 봇 종료를 확인한 뒤 닫습니다.\n보유 종목은 매도하지 않습니다. 진행할까요?'):
                self.closing=True; self.stop()
            return
        self.root.destroy()

    def poll(self):
        while not self.events.empty():
            event=self.events.get_nowait()
            if event[0]=='accounts':
                self.querying=False
                event[1].set(event[2])
            elif event[0]=='log':
                self.log_line(event[1])
                self.status.set(('실전 | ' if self.live else '읽기 전용 | ')+event[1][:170])
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
            if self.child.poll() is not None:
                code=self.child.returncode
                self.log_line(f'프로세스 종료 ({code}). 토스 앱에서 미체결·보유분을 확인하세요.')
                self.status.set('종료 · 토스 주문 내역 확인 필요')
                self.child=None
                for b in self.actions[:-1]:b.configure(state='normal')
                self.actions[-1].configure(state='disabled')
                if self.closing:self.root.destroy();return
        if self.mode=='etf' and self.active():
            try:
                state=Store(ROOT/'research'/'auto_status.json').data
                if state and state.get('updated_at')!=getattr(self,'last_research',None):
                    self.last_research=state.get('updated_at'); self.log_line('자동 분석: '+state['state'])
            except (OSError,ValueError,KeyError):pass
        self.root.after(1000,self.poll)
