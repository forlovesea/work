"""Consistent compact ttk buttons with clear action colors and states."""
import tkinter as tk


def button_style(label):
    if label in ('중지 요청','재생 중지'): return 'Danger.TButton'
    if label in ('암호화 저장','템플릿 암호화 변환','기간 적용'): return 'Success.TButton'
    if label in ('Manual','수익률 그래프'): return 'Violet.TButton'
    if label in ('실전 시작','백테스트','모의 재생'): return 'Primary.TButton'
    return 'TButton'


def install_buttons(root,style):
    palettes={
        'TButton':('#293B55','#6684AA','#344C6D','#1E2E45'),
        'Primary.TButton':('#245BC7','#79A9F5','#316DDF','#193F8F'),
        'Success.TButton':('#176B59','#66C9AA','#21836C','#104B3F'),
        'Danger.TButton':('#A33F52','#F28B9A','#BD4D61','#762B3B'),
        'Violet.TButton':('#6347A8','#B6A2EA','#795AC2','#47327D'),
    }
    for name,(fill,edge,hover,pressed) in palettes.items():
        style.configure(name,font=('맑은 고딕',10,'bold'),padding=(14,5),
                        foreground='#FFFFFF',background=fill,bordercolor=edge,
                        lightcolor=edge,darkcolor=pressed,anchor='center')
        style.map(name,
                  background=[('disabled','#343A44'),('pressed',pressed),('active',hover),('!disabled',fill)],
                  foreground=[('disabled','#98A2B2'),('!disabled','#FFFFFF')],
                  bordercolor=[('focus','#FFE19C'),('!focus',edge)])
    style.configure('Compact.TButton',font=('맑은 고딕',10,'bold'),padding=(14,5),
                    foreground='#FFFFFF',background=palettes['TButton'][0],
                    bordercolor=palettes['TButton'][1],anchor='center')
    style.map('Compact.TButton',
              background=[('disabled','#343A44'),('pressed',palettes['TButton'][3]),
                          ('active',palettes['TButton'][2]),('!disabled',palettes['TButton'][0])],
              foreground=[('disabled','#98A2B2'),('!disabled','#FFFFFF')],
              bordercolor=[('focus','#FFE19C'),('!focus',palettes['TButton'][1])])
    root.option_add('*TButton.cursor','hand2')
