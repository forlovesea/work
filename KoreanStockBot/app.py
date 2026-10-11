"""Offline desktop UI and command-line backtesting (Python 3.10+)."""
import argparse
import calendar
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from engine import Config, PaperEngine, demo_bars, read_bars

from app_paths import ROOT


def return_series(rows, capital, period='전체', start='', end=''):
    """Period-to-date returns based on the observation preceding the interval."""
    if not rows:
        return [], []
    latest=date.fromisoformat(str(rows[-1]['date']))
    finish=latest
    if period=='직접 기간':
        begin,finish=date.fromisoformat(start),date.fromisoformat(end)
        if begin>finish: raise ValueError('시작일은 종료일보다 늦을 수 없습니다.')
    elif period=='일': begin=latest
    elif period=='주': begin=latest-timedelta(days=latest.weekday())
    elif period=='월': begin=latest.replace(day=1)
    elif period=='연': begin=latest.replace(month=1,day=1)
    else: begin=date.fromisoformat(str(rows[0]['date']))
    base=float(capital)
    baseline='시작 원금'
    selected=[]
    for row in rows:
        day=date.fromisoformat(str(row['date']))
        if day<begin:
            base=float(row['equity']); baseline=str(row['date'])
        elif day<=finish: selected.append(row)
    if not selected: return [], []
    if base<=0: raise ValueError('기간 시작 평가자산이 0 이하라 수익률을 계산할 수 없습니다.')
    return ([0.0]+[(float(row['equity'])/base-1)*100 for row in selected],
            [baseline]+[str(row['date']) for row in selected])


def gui(mode='paper'):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root = tk.Tk()
    real=mode!='paper'
    mode_name={'paper':'모의매매','etf':'ETF 자동매매','stock':'단일 종목 자동매매'}[mode]
    from app_version import VERSION
    root.title('투자 전략 스튜디오 v'+VERSION+' | '+mode_name)
    root.geometry(f'{min(1120,root.winfo_screenwidth()-80)}x{min(860,root.winfo_screenheight()-120)}')
    root.minsize(560,400)
    colors = dict(bg='#151618', panel='#202226', text='#F2F4F7', muted='#ABB2BD',
                  accent='#397EF4', border='#383D46', chart='#101214',
                  up='#FF525B', down='#5796FF', grid='#2B3037')
    root.configure(bg=colors['bg'])
    root.option_add('*Font', ('맑은 고딕',10))
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.',font=('맑은 고딕',10),background=colors['bg'],foreground=colors['text'])
    style.configure('TLabel',background=colors['bg'],foreground=colors['text'])
    style.configure('Muted.TLabel',foreground=colors['muted'])
    style.configure('Card.TFrame',background=colors['panel'])
    style.configure('Card.TLabel',background=colors['panel'],foreground=colors['muted'])
    style.configure('Value.TLabel',background=colors['panel'],foreground=colors['text'],font=('맑은 고딕',22,'bold'))
    style.configure('TEntry',fieldbackground=colors['panel'],foreground=colors['text'],insertcolor=colors['text'],padding=7,bordercolor=colors['border'])
    style.configure('TButton',padding=(14,10),background=colors['panel'],bordercolor=colors['border'])
    style.map('TButton',background=[('active','#343A44')],foreground=[('active',colors['text'])])
    style.configure('Primary.TButton',background=colors['accent'],foreground='white',bordercolor=colors['accent'])
    style.map('Primary.TButton',background=[('active','#2865CC')],foreground=[('active','white')])
    from button_theme import install_buttons, button_style
    install_buttons(root,style)
    style.configure('TScrollbar',background='#454C58',troughcolor=colors['bg'],arrowcolor=colors['text'],bordercolor=colors['bg'])
    style.map('TScrollbar',background=[('active','#647085')])
    style.configure('TCombobox',fieldbackground=colors['panel'],foreground=colors['text'],arrowcolor=colors['text'],padding=6)
    style.map('TCombobox',fieldbackground=[('readonly',colors['panel'])],foreground=[('readonly',colors['text'])])
    root.option_add('*TCombobox*Listbox.background',colors['panel'])
    root.option_add('*TCombobox*Listbox.foreground',colors['text'])
    style.configure('Treeview',background=colors['panel'],fieldbackground=colors['panel'],rowheight=32,borderwidth=0)
    style.configure('Treeview.Heading',background='#2A2E35',foreground=colors['muted'],font=('맑은 고딕',10,'bold'),padding=8)
    style.map('Treeview.Heading',background=[('active','#343A44')])
    style.map('Treeview',background=[('selected','#294365')],foreground=[('selected',colors['text'])])
    # Keep scrollbars outside the content so they remain reachable at small sizes.
    root.rowconfigure(0,weight=1)
    root.columnconfigure(0,weight=1)
    viewport=tk.Canvas(root,bg=colors['bg'],highlightthickness=0)
    viewport.grid(row=0,column=0,sticky='nsew')
    vertical=ttk.Scrollbar(root,orient='vertical',command=viewport.yview)
    vertical.grid(row=0,column=1,sticky='ns')
    horizontal=ttk.Scrollbar(root,orient='horizontal',command=viewport.xview)
    horizontal.grid(row=1,column=0,sticky='ew')
    ttk.Frame(root,width=16,height=16).grid(row=1,column=1,sticky='nsew')
    viewport.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
    content=ttk.Frame(viewport)
    content_id=viewport.create_window(0,0,window=content,anchor='nw')

    def resize_content(event=None):
        viewport.itemconfigure(content_id,width=max(content.winfo_reqwidth(),viewport.winfo_width()),
                               height=max(content.winfo_reqheight(),viewport.winfo_height()))
        viewport.configure(scrollregion=viewport.bbox('all'))
    content.bind('<Configure>',resize_content)
    viewport.bind('<Configure>',resize_content)

    def scroll_wheel(event):
        # Do not scroll the main window while interacting with the separate graph.
        if event.widget.winfo_toplevel()!=root: return
        direction=-1 if event.delta>0 else 1
        units=direction*max(1,abs(event.delta)//120)
        if event.state & 0x1: viewport.xview_scroll(units,'units')
        else: viewport.yview_scroll(units,'units')
        return 'break'
    root.bind('<MouseWheel>',scroll_wheel)
    engine, bars, index, running = None, demo_bars(), 0, False
    source = tk.StringVar(value='연결 전 · 인증 설정 후 읽기 전용 점검부터 시작하세요' if real else '합성 데모 데이터 · 실제 종목/시장 수익률이 아닙니다')
    header=ttk.Frame(content)
    header.pack(fill='x',padx=28,pady=(20,10))
    ttk.Label(header,text='투자 전략 스튜디오',font=('맑은 고딕',24,'bold')).pack(side='left')
    from manual_gui import open_manual
    ttk.Button(header,text='Manual',command=lambda:open_manual(root,mode),style='Violet.TButton').pack(side='right',padx=(12,0))
    tk.Label(header,text='●  '+mode_name,bg='#28364C',fg='#9FC3FF',font=('맑은 고딕',10,'bold'),padx=14,pady=8).pack(side='right')
    ttk.Label(content, text='실전 시작 시 실제 주문 발생 · 원화 현금 한도 · 10% 수익 보장 없음' if real else '실제 주문 없음 · 수익 보장 없음 · 10%는 목표 시나리오입니다',style='Muted.TLabel').pack(anchor='w',padx=28)
    ttk.Label(content, textvariable=source,style='Muted.TLabel').pack(anchor='w',padx=28,pady=(5,12))
    metrics=ttk.Frame(content)
    metrics.pack(fill='x',padx=28,pady=(0,14))
    metric_vars={}
    metric_labels={}
    for col,(key,label,value) in enumerate([('equity','평가자산','— 원'),('return','누적 수익률','— %'),('drawdown','관측 최대 낙폭' if real else '최대 낙폭','— %'),('holding','보유 수량','— 주')]):
        metrics.columnconfigure(col,weight=1,uniform='metric')
        card=ttk.Frame(metrics,style='Card.TFrame',padding=14)
        card.grid(row=0,column=col,sticky='ew',padx=(0,10 if col<3 else 0))
        ttk.Label(card,text=label,style='Card.TLabel').pack(anchor='w')
        metric_vars[key]=tk.StringVar(value=value)
        metric_labels[key]=ttk.Label(card,textvariable=metric_vars[key],style='Value.TLabel')
        metric_labels[key].pack(anchor='w',pady=(4,0))
    settings = ttk.Frame(content)
    settings.pack(fill='x', padx=28)
    for col in range(4): settings.columnconfigure(col,weight=1)
    fields = {}
    for i, (key, label, value) in enumerate([('capital', '시작 금액(원)',30000),('allocation','투자 비중(%)',30),('stop_loss','손절 신호(%)',3),('take_profit','익절 신호(%)',6),('max_drawdown','최대 낙폭 중단(%)',10),('fee','편도 수수료 가정(%)',0.015),('sell_tax','매도세 가정(%)',0.2),('slippage','슬리피지 가정(%)',0.1)]):
        r, col = divmod(i, 4)
        ttk.Label(settings, text=label).grid(row=r*2,column=col,padx=10,sticky='w')
        var = tk.StringVar(value=str(value))
        fields[key] = var
        ttk.Entry(settings,textvariable=var,width=20).grid(row=r*2+1,column=col,padx=(0,14),pady=(4,8),sticky='ew')
    if real: settings.pack_forget()
    status = tk.StringVar(value='CSV를 불러오거나 합성 데이터로 시작하세요. 전략: 5일/20일 이동평균 추세')
    if real: status.set('대기 중 · 실제 계좌 조회/체결은 아직 검증되지 않았습니다.')
    ttk.Label(content,textvariable=status,style='Muted.TLabel').pack(anchor='w',padx=28,pady=10)
    period=tk.StringVar(value='전체')
    start_date=tk.StringVar()
    end_date=tk.StringVar()
    applied_dates=['','']
    period_controls=[]
    calendar_mode=tk.BooleanVar(value=False)

    def sync_date_controls():
        custom=period.get()=='직접 기간'
        for first,last,button,check,start_button,end_button in period_controls:
            for entry in (first,last):
                entry.configure(state=('readonly' if calendar_mode.get() else 'normal') if custom else 'disabled')
            for widget in (button,check): widget.configure(state='normal' if custom else 'disabled')
            for widget in (start_button,end_button):
                widget.configure(state='normal' if custom and calendar_mode.get() else 'disabled')

    def pick_date(variable,owner,label):
        popup=tk.Toplevel(owner)
        popup.title(label+' 선택')
        popup.configure(bg=colors['bg'])
        popup.resizable(False,False)
        popup.transient(owner.winfo_toplevel())
        try: chosen=date.fromisoformat(variable.get())
        except ValueError:
            chosen=date.fromisoformat(str(engine.equity[-1]['date'])) if engine and engine.equity else date.today()
        year=tk.IntVar(value=chosen.year)
        month=tk.IntVar(value=chosen.month)
        top=ttk.Frame(popup,padding=12)
        top.pack(fill='x')
        grid=ttk.Frame(popup,padding=(12,0,12,12))
        grid.pack()

        def select(day):
            variable.set(date(year.get(),month.get(),day).isoformat())
            popup.destroy()

        def render(event=None):
            try: y,m=year.get(),month.get()
            except tk.TclError: return
            if not 1<=y<=9999 or not 1<=m<=12: return
            for widget in grid.winfo_children(): widget.destroy()
            for col,name in enumerate(('월','화','수','목','금','토','일')):
                ttk.Label(grid,text=name,anchor='center',foreground=colors['down'] if col==5 else colors['up'] if col==6 else colors['muted']).grid(row=0,column=col,sticky='ew',pady=6)
            for row,week in enumerate(calendar.monthcalendar(y,m),1):
                for col,day in enumerate(week):
                    if day:
                        ttk.Button(grid,text=str(day),width=3,style='Primary.TButton' if (y,m,day)==(chosen.year,chosen.month,chosen.day) else 'TButton',command=lambda d=day:select(d)).grid(row=row,column=col,padx=2,pady=2)

        def shift(delta):
            try: offset=(year.get()-1)*12+month.get()-1+delta
            except tk.TclError: return
            if 0<=offset<9999*12:
                year.set(offset//12+1); month.set(offset%12+1); render()

        ttk.Button(top,text='◀',width=3,command=lambda:shift(-1)).pack(side='left')
        years=ttk.Spinbox(top,from_=1,to=9999,textvariable=year,width=6,command=render)
        years.pack(side='left',padx=(8,2))
        ttk.Label(top,text='년').pack(side='left')
        months=ttk.Combobox(top,values=tuple(range(1,13)),textvariable=month,width=3,state='readonly')
        months.pack(side='left',padx=(8,2))
        ttk.Label(top,text='월').pack(side='left',padx=(0,8))
        ttk.Button(top,text='▶',width=3,command=lambda:shift(1)).pack(side='left')
        years.bind('<Return>',render)
        years.bind('<FocusOut>',render)
        months.bind('<<ComboboxSelected>>',render)
        ttk.Label(popup,text='날짜 선택 후 조회 화면에서 ‘기간 적용’을 누르세요.',style='Muted.TLabel').pack(padx=12,pady=(0,12))
        popup.bind('<Escape>',lambda event:popup.destroy())
        render()
        popup.grab_set()

    def refresh_graphs():
        draw_return(chart)
        if graph_window is not None and graph_window.winfo_exists(): draw_return(graph_canvas)

    def choose_period(event=None):
        custom=period.get()=='직접 기간'
        sync_date_controls()
        if custom and engine and engine.equity and not start_date.get():
            start_date.set(str(engine.equity[0]['date']))
            end_date.set(str(engine.equity[-1]['date']))
            applied_dates[:]=[start_date.get(),end_date.get()]
        refresh_graphs()

    def apply_period():
        try:
            a,b=date.fromisoformat(start_date.get()),date.fromisoformat(end_date.get())
            if a>b: raise ValueError()
        except ValueError:
            messagebox.showerror('기간 확인','날짜를 YYYY-MM-DD 형식으로 입력하고 시작일이 종료일보다 늦지 않은지 확인하세요.')
            return
        applied_dates[:]=[a.isoformat(),b.isoformat()]
        refresh_graphs()

    def add_period_controls(parent):
        toolbar=ttk.Frame(parent)
        toolbar.pack(fill='x',padx=28,pady=(6,8))
        ttk.Label(toolbar,text='조회 기간').pack(side='left',padx=(0,10))
        selector=ttk.Combobox(toolbar,textvariable=period,values=('일','주','월','연','전체','직접 기간'),state='readonly',width=10)
        selector.pack(side='left',padx=(0,12))
        selector.bind('<<ComboboxSelected>>',choose_period)
        check=ttk.Checkbutton(toolbar,text='캘린더로 선택',variable=calendar_mode,command=sync_date_controls)
        check.pack(side='left')
        datebar=ttk.Frame(parent)
        datebar.pack(fill='x',padx=28,pady=(0,8))
        ttk.Label(datebar,text='시작일 ').pack(side='left')
        first=ttk.Entry(datebar,textvariable=start_date,width=12)
        first.pack(side='left')
        start_button=ttk.Button(datebar,text='달력',command=lambda:pick_date(start_date,parent,'시작일'))
        start_button.pack(side='left',padx=4)
        ttk.Label(datebar,text=' ~ 종료일 ').pack(side='left')
        last=ttk.Entry(datebar,textvariable=end_date,width=12)
        last.pack(side='left')
        end_button=ttk.Button(datebar,text='달력',command=lambda:pick_date(end_date,parent,'종료일'))
        end_button.pack(side='left',padx=4)
        button=ttk.Button(datebar,text='기간 적용',command=apply_period,style='Success.TButton')
        button.pack(side='left',padx=8)
        controls=(first,last,button,check,start_button,end_button)
        period_controls.append(controls)
        sync_date_controls()
        return controls

    add_period_controls(content)
    ttk.Label(content,text='일·주·월·연: 마지막 관측일 기준 / 직전 관측 평가액 대비 · 날짜: YYYY-MM-DD',style='Muted.TLabel').pack(anchor='w',padx=28,pady=(0,5))
    chart = tk.Canvas(content,height=280,bg=colors['chart'],highlightthickness=1,highlightbackground=colors['border'])
    chart.pack(fill='x',padx=28)
    ttk.Label(content,text='최근 주문 기록 · 수량은 주문 수량이며 체결 상태는 로그·토스 앱 확인' if real else '최근 가상 체결',font=('맑은 고딕',11,'bold')).pack(anchor='w',padx=28,pady=(12,6))
    output=ttk.Treeview(content,columns=('date','side','qty','price','reason'),show='headings',height=4)
    for key,label,width in [('date','체결일',130),('side','구분',80),('qty','수량',90),('price','체결 가격',130),('reason','매매 사유',300)]:
        output.heading(key,text=label)
        output.column(key,width=width,anchor='w' if key in ('date','reason') else 'e')
    output.tag_configure('alternate',background='#252930')
    output.tag_configure('BUY',foreground=colors['up'])
    output.tag_configure('SELL',foreground=colors['down'])
    output.pack(fill='both',expand=True,padx=28)
    ttk.Label(content,text='봇 관리 자산 기준 · 일별 마지막 관측값 · 과거 미관측 구간은 복원하지 않음' if real else '신호 다음 거래일 시가 + 비용 가정 · 미청산 보유분 포함',style='Muted.TLabel').pack(anchor='w',padx=28,pady=(5,0))

    graph_window, graph_canvas = None, None

    def draw_return(canvas):
        canvas.delete('all')
        if not engine or not engine.equity:
            canvas.create_text(24,70,text='계좌 평가자산 관측 후 그래프가 표시됩니다.' if real else '백테스트 또는 모의 재생을 시작하면 누적 수익률이 표시됩니다.',anchor='w',fill=colors['muted'])
            return
        try:
            values,dates=return_series(engine.equity,engine.cfg.capital,period.get(),*applied_dates)
        except ValueError:
            canvas.create_text(24,70,text='시작일과 종료일을 YYYY-MM-DD로 입력한 뒤 기간 적용을 누르세요.',anchor='w',fill=colors['muted'])
            return
        if not values:
            canvas.create_text(24,70,text='선택한 기간에 재생된 데이터가 없습니다.',anchor='w',fill=colors['muted'])
            return
        w,h=max(canvas.winfo_width(),350),max(canvas.winfo_height(),180)
        left,right,top,bottom=24,w-112,54,h-38
        canvas.create_rectangle(right+8,0,w,h,fill=colors['panel'],outline='')
        lo,hi=min(values+[0]),max(values+[0])
        pad=max((hi-lo)*.15,.5)
        lo,hi=lo-pad,hi+pad
        def xy(i):
            return (left+i*(right-left)/(len(values)-1),bottom-(values[i]-lo)/(hi-lo)*(bottom-top))
        latest_color=colors['up'] if values[-1]>0 else colors['down'] if values[-1]<0 else colors['muted']
        canvas.create_text(20,22,text=f'{period.get()} 누적 수익률   {values[-1]:+.2f}%',anchor='w',fill=latest_color,font=('맑은 고딕',14,'bold'))
        if w>650:
            canvas.create_text(right,22,text=f'{dates[1]} ~ {dates[-1]}  ·  '+('계좌 관측' if real else '모의 결과'),anchor='e',fill=colors['muted'],font=('맑은 고딕',10))
        for k in range(5):
            value=lo+(hi-lo)*k/4
            y=bottom-k*(bottom-top)/4
            canvas.create_line(left,y,right,y,fill=colors['grid'],dash=(4,4))
            canvas.create_text(right+18,y,text=f'{value:+.1f}%',anchor='w',fill=colors['muted'],font=('맑은 고딕',10,'bold'))
        zero=bottom-(0-lo)/(hi-lo)*(bottom-top)
        canvas.create_line(left,zero,right,zero,fill='#8999AC',dash=(4,3))
        for i,anchor in [(0,'w'),((len(values)-1)//2,'center'),(len(values)-1,'e')]:
            x,_=xy(i)
            canvas.create_line(x,top,x,bottom,fill=colors['grid'],dash=(4,4))
            canvas.create_text(x,bottom+18,text=dates[i],anchor=anchor,fill=colors['muted'])
        points=[xy(i) for i in range(len(values))]
        # Split at zero so red and blue denote profit/loss, not daily movement.
        for i in range(1,len(points)):
            a,b=values[i-1],values[i]
            x1,y1=points[i-1]; x2,y2=points[i]
            if a*b<0:
                cross=x1+(x2-x1)*(-a)/(b-a)
                canvas.create_line(x1,y1,cross,zero,fill=colors['up'] if a>0 else colors['down'],width=2.5)
                canvas.create_line(cross,zero,x2,y2,fill=colors['up'] if b>0 else colors['down'],width=2.5)
            else:
                canvas.create_line(x1,y1,x2,y2,fill=colors['up'] if a+b>0 else colors['down'] if a+b<0 else colors['muted'],width=2.5)
        x,y=points[-1]
        canvas.create_oval(x-4,y-4,x+4,y+4,fill=latest_color,outline=colors['text'])
        canvas.create_rectangle(right+9,y-13,w-3,y+13,fill=latest_color,outline='')
        canvas.create_text(right+18,y,text=f'{values[-1]:+.2f}%',anchor='w',fill='#101214',font=('맑은 고딕',11,'bold'))

        def hover(event):
            canvas.delete('hover')
            if not left<=event.x<=right or not top<=event.y<=bottom: return
            i=round((event.x-left)/(right-left)*(len(values)-1))
            x,y=points[i]
            canvas.create_line(x,top,x,bottom,fill='#8999AC',dash=(3,3),tags='hover')
            canvas.create_line(left,y,right,y,fill='#8999AC',dash=(3,3),tags='hover')
            label=f'{dates[i]}  |  {values[i]:+.2f}%'
            tx=min(max(x,left+100),right-100)
            item=canvas.create_text(tx,top+12,text=label,fill=colors['text'],tags='hover')
            box=canvas.bbox(item)
            bg=canvas.create_rectangle(box[0]-6,box[1]-4,box[2]+6,box[3]+4,fill=colors['panel'],outline=colors['border'],tags='hover')
            canvas.tag_raise(item,bg)
        canvas.bind('<Motion>',hover)
        canvas.bind('<Leave>',lambda event:canvas.delete('hover'))

    def open_graph():
        nonlocal graph_window,graph_canvas
        if graph_window is not None and graph_window.winfo_exists():
            graph_window.lift()
            return
        graph_window=tk.Toplevel(root)
        graph_window.title('누적 수익률 그래프 v'+VERSION+' | '+mode_name)
        graph_window.geometry('1000x560')
        graph_window.minsize(780,400)
        graph_window.configure(bg=colors['bg'])
        ttk.Label(graph_window,text='누적 수익률',font=('맑은 고딕',20,'bold')).pack(anchor='w',padx=24,pady=(18,4))
        ttk.Label(graph_window,text='마우스를 올리면 날짜별 수익률을 확인할 수 있습니다. 재생 중 자동 갱신됩니다.',style='Muted.TLabel').pack(anchor='w',padx=24)
        controls=add_period_controls(graph_window)
        def close_graph():
            period_controls.remove(controls)
            graph_window.destroy()
        graph_window.protocol('WM_DELETE_WINDOW',close_graph)
        graph_canvas=tk.Canvas(graph_window,bg=colors['chart'],highlightthickness=0)
        graph_canvas.pack(fill='both',expand=True,padx=24,pady=18)
        graph_canvas.bind('<Configure>',lambda event:draw_return(graph_canvas))

    def show():
        if not engine or not engine.equity:
            return
        r = engine.report()
        status.set(f"{engine.equity[-1]['date']} 기준 · {index:,} / {len(bars):,}개 일봉" + (' · 진입 중단' if engine.halted else ''))
        for key,value in [('equity',f"{r['final']:,.0f} 원"),('return',f"{r['return_pct']:+.2f} %"),('drawdown',f"{r['max_drawdown_pct']:.2f} %"),('holding',f'{engine.qty:,} 주')]:
            metric_vars[key].set(value)
        metric_labels['return'].configure(foreground=colors['up'] if r['return_pct']>0 else colors['down'] if r['return_pct']<0 else colors['text'])
        metric_labels['drawdown'].configure(foreground=colors['down'])
        draw_return(chart)
        if graph_window is not None and graph_window.winfo_exists(): draw_return(graph_canvas)
        output.delete(*output.get_children())
        for n,t in enumerate(engine.trades[-7:]):
            output.insert('','end',values=(t['date'],{'BUY':'매수','SELL':'매도'}.get(t['side'],t['side']),f"{t['quantity']} 주",f"{t['price']:,.0f} 원",t['reason']),tags=(('alternate',) if n%2 else ())+ (t['side'],))

    def start(animated=False):
        nonlocal engine,index,running
        if running:
            return
        try:
            vals = {k:float(v.get())/(1 if k=='capital' else 100) for k,v in fields.items()}
            engine = PaperEngine(Config(**vals))
            if len(bars) < engine.cfg.slow+1:
                raise ValueError('21개 이상의 일봉이 필요합니다.')
        except ValueError as exc:
            messagebox.showerror('설정 확인',str(exc))
            return
        index, running = 0, True
        def tick():
            nonlocal index,running
            if not running:
                return
            for _ in range(1 if animated else 100):
                if index >= len(bars):
                    running = False
                    break
                engine.step(bars[index])
                index += 1
            show()
            if running:
                root.after(100 if animated else 1,tick)
        tick()

    def stop():
        nonlocal running
        running = False

    def load():
        nonlocal bars
        if running:
            return
        path = filedialog.askopenfilename(filetypes=[('일봉 CSV','*.csv')])
        if path:
            try:
                bars = read_bars(path)
                source.set(f'{Path(path).name} · 단일 종목 일봉 {len(bars)}개')
            except (ValueError, OSError) as exc:
                messagebox.showerror('CSV 확인',str(exc))

    def save():
        if engine and engine.equity:
            path = ROOT/'reports'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            engine.export(path)
            (path/'config.json').write_text(json.dumps(vars(engine.cfg),indent=2),encoding='utf-8')
            messagebox.showinfo('저장 완료',str(path))

    def goals():
        try:
            capital=float(fields['capital'].get())
            if not 0 < capital < 1e15:
                raise ValueError()
            messagebox.showinfo('10% 복리 가정 · 예측 아님', '\n'.join(f'{label}: {capital*1.1**n:,.0f}원' for label,n in [('매 거래일 10%, 252회',252),('매주 10%, 52회',52),('매월 10%, 12회',12)])+'\n\n서로 다른 가정입니다. 비용·손실을 제외한 산술 계산이며 달성 확률을 뜻하지 않습니다.')
        except (ValueError, OverflowError):
            messagebox.showerror('입력 확인','시작 금액을 확인하세요.')
    buttons = ttk.Frame(content)
    buttons.pack(pady=14)
    paper_actions=[('CSV 불러오기',load),('백테스트',start),('모의 재생',lambda:start(True)),('재생 중지',stop),('수익률 그래프',open_graph),('결과 저장',save),('10% 복리 계산',goals)]
    if real:
        from live_gui import LivePanel
        def accept_snapshot(snapshot,config,label):
            nonlocal engine
            from live_gui import account_view
            engine=account_view(snapshot,config)
            source.set(label)
            for key,value in [('equity',f"{float(snapshot['last_equity']):,.0f} 원"),('return',f"{engine.report()['return_pct']:+.2f} %"),('drawdown',f"{engine.report()['max_drawdown_pct']:.2f} %"),('holding',f"{snapshot['quantity']} 주")]: metric_vars[key].set(value)
            metric_labels['return'].configure(foreground=colors['up'] if engine.report()['return_pct']>0 else colors['down'])
            output.delete(*output.get_children())
            for order in snapshot.get('orders',[])[-20:]:
                payload=order['payload']
                output.insert('','end',values=(order.get('created','')[:19],payload['side'],payload['quantity'],payload['price'],order.get('status','접수 확인 중')+f" / 체결 {order.get('applied',{}).get('qty',0)}주 / {payload['symbol']}"),tags=(payload['side'],))
            refresh_graphs()
        controller=LivePanel(root,content,buttons,mode,colors,status,accept_snapshot)
        paper_actions=[('수익률 그래프',open_graph)]
        root.protocol('WM_DELETE_WINDOW',controller.close)
    for label,cmd in paper_actions:
        ttk.Button(buttons,text=label,command=cmd,style=button_style(label),cursor='hand2').pack(side='left',padx=4)
    chart.bind('<Configure>',lambda event:draw_return(chart))
    draw_return(chart)
    root.mainloop()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='국내 주식 모의매매 연구 도구')
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--mode',choices=('paper','etf','stock'),default='paper')
    parser.add_argument('--csv',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'reports'/'cli')
    args=parser.parse_args()
    if args.demo or args.csv:
        bot=PaperEngine()
        for bar in read_bars(args.csv) if args.csv else demo_bars():
            bot.step(bar)
        bot.export(args.output)
        print(json.dumps({k:v for k,v in bot.report().items() if k!='periods'},ensure_ascii=False,indent=2))
    else:
        gui(args.mode)
