"""Offline, non-modal visual guide. Opening it never changes trading state."""
import tkinter as tk
from tkinter import ttk
from app_version import VERSION


def sections(mode):
    real=mode!='paper'
    buttons=[
        ('인증·계좌 설정','키와 계좌를 설정하는 창입니다. 계좌 조회 후 하나면 자동 선택되고, 여러 개면 직접 선택합니다.'),
        ('읽기 전용 점검','증권사 연결과 계좌·자료를 확인합니다. 실제 주문은 보내지 않습니다. 확인이 끝나면 중지 요청을 누르세요.'),
        ('실전 시작','확인창 승인 후 실제 매수·매도 주문이 가능한 상태로 전환합니다. 운영시간·현금·분석·위험 조건을 충족해야 주문합니다.'),
        ('중지 요청','미체결 주문 취소를 확인하고 종료합니다. 보유 종목을 자동으로 전부 매도하는 버튼이 아닙니다. 종료 상태를 확인하세요.'),
        ('프로그램 종료','우측 상단 고정 버튼입니다. 계좌·후보 조회가 끝나고 봇의 미체결 정리와 정상 종료를 확인하면 창이 자동으로 닫힙니다. 확인 실패 시 창을 유지합니다. 보유분은 남으며 자동 감시는 종료됩니다. 모의매매는 결과를 reports/paper_exit_시각 폴더에 저장합니다.'),
        ('ETF 후보 제안','중지 완료 후 열면 계좌 원화·시세를 조회해 재무·뉴스·예산·추세 통과 종목을 추천합니다. 종목을 클릭해 선택하고 적용한 뒤 다시 시작하세요. 선택 종목 중 한 번에 한 종목을 운용하며 기존 보유분의 매도 조건은 유지됩니다. 5분이 지난 분석은 재조회가 필요합니다.'),
    ] if real else [
        ('CSV 불러오기','로컬 일봉 CSV를 선택합니다. 불러오기 전에는 합성 데모 데이터를 사용합니다.'),
        ('백테스트','입력한 비용·투자 조건으로 전체 데이터를 계산합니다. 실제 계좌 주문은 없습니다.'),
        ('모의 재생 / 재생 중지','데이터를 순서대로 재생하거나 멈춥니다. 가상 매매 결과와 그래프의 변화를 확인합니다.'),
        ('결과 저장','계산된 결과와 설정을 reports 폴더에 저장합니다. 먼저 백테스트나 모의 재생을 실행하세요.'),
        ('10% 복리 계산','매일·매주·매월 10%라는 서로 다른 가정의 산술 결과입니다. 실제 수익 예측이 아닙니다.'),
    ]
    return [
        ('시작하기','#7C9CFF',[
            ('지금 보고 있는 모드',{'etf':'ETF 자동매매: 코스닥 관련 ETF 순자산 상위 20개를 대상으로 분석·가격·예산 조건을 확인합니다.',
              'stock':'단일 종목 자동매매: 설정한 종목코드 한 개를 대상으로 전략 조건을 확인합니다.',
              'paper':'모의매매: 합성 데모 또는 CSV로 전략을 시험합니다. 실제 주문은 발생하지 않습니다.'}[mode]),
            ('권장 사용 순서','인증·계좌 설정 → 읽기 전용 점검 → 중지 확인 → 실전 시작' if real else '조건 입력 → CSV 선택 또는 데모 사용 → 백테스트 / 모의 재생 → 그래프 확인 → 결과 저장'),
            ('Manual은 안내 전용','이 창을 열거나 닫아도 실행 중인 매매는 계속됩니다. 중지는 본 화면의 중지 요청 버튼을 사용하세요.'),
        ]),
        ('버튼 안내','#57D9CA',buttons+[
            ('수익률 그래프','그래프를 별도 창으로 크게 엽니다. 본 화면과 기간 선택이 연동됩니다.'),
            ('Manual','화면 영역과 사용법을 확인합니다. 인터넷 연결 없이 열 수 있습니다.'),
        ]),
        ('화면 읽기','#FFC66D',[
            ('상단 제목 · 모드 · 데이터 출처','버전과 운용 모드를 먼저 확인하세요. 연결 전·합성 데이터·마지막 관측일 등의 문구로 데이터의 출처와 시점을 구분합니다.'),
            ('평가자산','봇이 관리하는 현금과 보유분의 평가값입니다. 실전에서는 계좌 전체 잔고와 다를 수 있으며 최신 관측 기준입니다.'),
            ('누적 수익률','설정된 운용 원금 대비 관리 평가자산의 변화입니다. 그래프에서 선택한 기간의 수익률과 기준이 다를 수 있습니다.'),
            ('최대 낙폭 · 보유 수량','낙폭은 관측된 고점 대비 하락 정도입니다. 실전의 관측 최대 낙폭은 관측 이력 기준이며, 모든 순간의 하락을 기록한 값은 아닙니다. 보유 수량은 봇 관리 수량입니다.'),
            ('전략 입력 영역' if not real else '운용 원금 · 매수 상한',
             '시작 금액·투자 비중·손절/익절·최대 낙폭과 수수료·세금·슬리피지 가정을 입력합니다. 이 영역은 모의매매 설정입니다.' if not real else '봇의 관리 예산과 주문당 상한입니다. 실제 매수는 사용 가능한 원화 현금과 정수 수량 한도에도 제한됩니다.'),
            ('주문 / 거래 표','날짜·매수/매도·수량·가격을 확인합니다. 실전 주문 수량과 실제 반영된 체결 수량은 다를 수 있으므로 상태도 함께 보세요.'),
            ('상태 영역 · 로그','최근 처리 결과와 대기 이유를 표시합니다. 로그에는 연결·분석·중지 등 처리 이력이 쌓입니다. 아래가 안 보이면 우측 스크롤을 사용하세요.'),
        ]),
        ('그래프 · 기간','#BE9CFF',[
            ('일 / 주 / 월 / 연 / 전체','데이터의 마지막 날짜를 기준으로 해당 일·주·월·연의 누적 수익률을 봅니다. 전체는 기록된 전체 구간입니다. 이전 기간을 지정하려면 직접 기간을 사용하세요.'),
            ('직접 기간 · 기간 적용','시작일과 종료일을 YYYY-MM-DD 형식으로 입력하고 기간 적용을 누릅니다. 선택 구간의 시작 기준에 따라 수익률이 다시 계산됩니다.'),
            ('달력 체크박스','체크하면 달력 버튼으로 날짜를 선택합니다. 체크를 해제하면 직접 입력할 수 있습니다.'),
            ('빨강 / 파랑 · 마우스 확인','기준보다 높은 수익률은 빨강, 낮은 수익률은 파랑입니다. 마우스를 그래프 위에 올려 날짜와 수익률을 확인하세요.'),
            ('그래프가 비어 있을 때','선택 기간에 관측 또는 모의 재생 기록이 있는지 확인하세요. 실전 이력은 일별 관측 기준이며 분·초 단위 실시간 차트가 아닙니다.'),
        ]),
        ('인증 · 설정 파일','#65C5FF',[
            ('계좌 조회 · 암호화 저장','토스 키로 계좌를 조회하고 사용할 계좌를 선택한 뒤 저장합니다. accountSeq는 계좌 선택값이며 계좌 비밀번호가 아닙니다.'),
            ('눈 모양 보기 / 숨기기','해당 입력칸의 내용을 표시하거나 가립니다. 앞뒤 공백·탭은 무시합니다. 창을 다시 열면 숨김 상태입니다.'),
            ('설정 템플릿 생성','저장된 키를 담지 않은 빈 JSON 파일을 만듭니다. 메모장으로 credentials의 빈 값에 키를 입력하세요. 항목 이름은 그대로 두세요.'),
            ('템플릿 암호화 변환','작성한 JSON을 선택해 .ksbkey로 암호화합니다. 검증 후 평문 원본 삭제 여부를 선택할 수 있습니다. 백업·동기화 사본은 따로 관리하세요.'),
            ('설정 파일 불러오기','암호화 파일을 해독해 입력칸에 채웁니다. 계좌 조회 → 선택 → 암호화 저장을 해야 적용됩니다. 파일의 계좌 선택값은 자동 적용하지 않습니다.'),
            ('암호화 범위','같은 PC·동일 Windows 사용자에서 복호화합니다. 같은 사용자 권한의 프로그램까지 차단하지는 않습니다. 타 PC용 휴대 암호화가 아닙니다.'),
            ('모드별 필요한 값','ETF 모드는 토스·KRX·DART·NAVER API HUB 인증을 사용합니다. 단일 종목은 토스 인증과 종목코드를 설정합니다. 모의매매에는 실전 인증 설정이 없습니다.'),
        ]),
        ('상태 이해하기','#FF91AB',[
            ('휴장 대기 / 매매 시작 대기','신규 매수·매도 주문 없이 운영시간을 기다립니다. 다음 개장 시각은 토스 시장 캘린더 응답이며 확인 불가 시 임의로 추정하지 않습니다.'),
            ('마지막 상태를 받은 시각','프로그램이 매매 프로세스의 상태를 마지막으로 전달받은 한국시간입니다. 주문이 체결된 시각이나 시세 시각과 같다는 뜻은 아닙니다.'),
            ('마지막 상태 수신 후 경과: n초','수신 이후 지난 시간이므로 숫자가 커집니다. 새 상태가 오면 0초로 갱신됩니다. 다음 확인까지 남은 시간이 아닙니다.'),
            ('연결 확인 실패 / 응답 지연','정상 휴장 대기와 다른 상태입니다. 네트워크·허용 IP·키를 확인하고 미체결·보유 내역은 토스에서 확인하세요.'),
            ('분석 자료 대기 / 적합한 ETF 없음','후보별 재무점수·확인 비중·뉴스 수와 1주 필요 추정 금액·예산 부족액·이동평균을 확인하세요. 상태 영역은 일부 종목을 요약하고 아래 로그는 최대 20개를 보여줍니다. 실행 중이라고 반드시 매수하지는 않습니다.'),
            ('자료 수집 상태','KRX·DART·NAVER 각각의 API 응답 수신, 캐시 사용, 오류 횟수와 기록 시각을 표시합니다. 캐시는 현재 키의 인증 성공을 의미하지 않습니다. READY는 분석 파일 완성이며 모든 종목이 매수 조건을 통과했다는 뜻이 아닙니다.'),
            ('중지 처리 / 중지 완료','중지 요청 뒤 미체결 취소 확인을 기다릴 수 있습니다. 완료 후에도 보유분은 남습니다. 10%는 목표이며 수익을 보장하지 않습니다.'),
        ]),
    ]


def open_manual(root,mode):
    existing=getattr(root,'_manual_window',None)
    if existing is not None and existing.winfo_exists():
        existing.deiconify(); existing.lift(); existing.focus_set(); return existing
    window=tk.Toplevel(root); root._manual_window=window
    window.title(f'Manual · 투자 전략 스튜디오 v{VERSION}')
    window.geometry(f'{min(900,root.winfo_screenwidth()-70)}x{min(780,root.winfo_screenheight()-100)}')
    window.minsize(420,360); window.configure(bg='#101620')
    hero=tk.Frame(window,bg='#1B2945'); hero.pack(fill='x')
    tk.Label(hero,text=f'USER GUIDE   /   v{VERSION}',bg='#1B2945',fg='#9CB8FF',font=('맑은 고딕',10,'bold')).pack(anchor='w',padx=24,pady=(20,4))
    tk.Label(hero,text='투자를 시작하기 전, 한눈에.',bg='#1B2945',fg='#F3F7FF',font=('맑은 고딕',22,'bold')).pack(anchor='w',padx=24)
    tk.Label(hero,text='버튼의 역할부터 화면의 숫자까지 · 오프라인 가이드',bg='#1B2945',fg='#C1CEE4',font=('맑은 고딕',10)).pack(anchor='w',padx=24,pady=(8,18))
    nav=tk.Frame(window,bg='#101620'); nav.pack(fill='x',padx=16,pady=12)
    body=tk.Frame(window,bg='#101620'); body.pack(fill='both',expand=True,padx=16)
    canvas=tk.Canvas(body,bg='#101620',highlightthickness=0)
    scroll=ttk.Scrollbar(body,orient='vertical',command=canvas.yview)
    scroll.pack(side='right',fill='y'); canvas.pack(side='left',fill='both',expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    page=tk.Frame(canvas,bg='#101620'); item=canvas.create_window(0,0,window=page,anchor='nw')
    labels=[]; navigation=[]
    data=sections(mode)
    def fit(event=None):
        width=max(240,canvas.winfo_width())
        canvas.itemconfigure(item,width=width)
        for label in labels: label.configure(wraplength=max(180,width-70))
        canvas.configure(scrollregion=canvas.bbox('all'))
    page.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',fit)
    def select(index):
        for child in page.winfo_children():child.destroy()
        labels.clear()
        title,accent,cards=data[index]
        for i,button in enumerate(navigation):button.configure(bg=accent if i==index else '#202C3E',fg='#101620' if i==index else '#D5DEEF')
        heading=tk.Label(page,text=title,bg='#101620',fg=accent,font=('맑은 고딕',18,'bold'),anchor='w')
        heading.pack(fill='x',padx=8,pady=(4,12)); labels.append(heading)
        for n,(title,text) in enumerate(cards,1):
            card=tk.Frame(page,bg='#1B2534',highlightbackground='#304058',highlightthickness=1)
            card.pack(fill='x',padx=6,pady=(0,10))
            tk.Frame(card,bg=accent,width=4).pack(side='left',fill='y')
            inner=tk.Frame(card,bg='#1B2534'); inner.pack(fill='both',expand=True,padx=18,pady=14)
            for value,color,font in [(f'{n:02d}  {title}',accent,('맑은 고딕',12,'bold')),(text,'#D6DFEF',('맑은 고딕',11))]:
                label=tk.Label(inner,text=value,bg='#1B2534',fg=color,font=font,justify='left',anchor='w')
                label.pack(fill='x',pady=(0,6)); labels.append(label)
        fit(); canvas.yview_moveto(0)
    for i,(title,accent,cards) in enumerate(data):
        button=tk.Button(nav,text=title,command=lambda index=i:select(index),relief='raised',bd=2,
                         activebackground=accent,activeforeground='#101620',cursor='hand2',font=('맑은 고딕',10,'bold'),pady=9)
        button.grid(row=i//3,column=i%3,sticky='ew',padx=4,pady=4); navigation.append(button)
    for i in range(3):nav.columnconfigure(i,weight=1)
    def wheel(event):
        canvas.yview_scroll(-int(event.delta/120) if abs(event.delta)>=120 else (-1 if event.delta>0 else 1),'units')
        return 'break'
    window.bind('<MouseWheel>',wheel)
    window.bind('<Escape>',lambda e:window.destroy())
    footer=tk.Frame(window,bg='#101620'); footer.pack(fill='x',padx=22,pady=10)
    tk.Label(footer,text='안내 창을 닫아도 매매 상태는 유지됩니다.',bg='#101620',fg='#A8B5CB',font=('맑은 고딕',9)).pack(side='left')
    ttk.Button(footer,text='닫기',command=window.destroy).pack(side='right')
    select(0)
    return window
