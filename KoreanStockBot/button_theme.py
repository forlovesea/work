"""Rounded, shaded ttk buttons with keyboard, hover, press and disabled states."""
import tkinter as tk


def button_style(label):
    if label in ('중지 요청','재생 중지'): return 'Danger.TButton'
    if label in ('암호화 저장','템플릿 암호화 변환','기간 적용'): return 'Success.TButton'
    if label in ('Manual','수익률 그래프'): return 'Violet.TButton'
    if label in ('실전 시작','백테스트','모의 재생'): return 'Primary.TButton'
    return 'TButton'


def install_buttons(root,style):
    images=[]
    def image(fill,edge,pressed=False):
        size=36; radius=9; top=2 if pressed else 0; bottom=34 if pressed else 31
        photo=tk.PhotoImage(master=root,width=size,height=size)
        def inside(x,y,inset=0):
            left=inset; right=size-1-inset; high=top+inset; low=bottom-inset
            if not left<=x<=right or not high<=y<=low:return False
            r=max(1,radius-inset)
            cx=min(max(x,left+r),right-r); cy=min(max(y,high+r),low-r)
            return (x-cx)**2+(y-cy)**2<=r*r
        for y in range(size):
            for x in range(size):
                if inside(x,y):photo.put(fill if inside(x,y,2) else edge,(x,y))
                elif not pressed and y>bottom and 9<=x<27:photo.put('#080E18',(x,y))
        images.append(photo); return photo
    palettes={
        'TButton':('#2D4260','#6C88AD','#3E5A80','#20324D'),
        'Primary.TButton':('#2862D8','#85B7FF','#397BEF','#1C49AA'),
        'Success.TButton':('#12645C','#53D6B9','#197F72','#0C493F'),
        'Danger.TButton':('#943F56','#FF91AA','#B6506A','#732A40'),
        'Violet.TButton':('#6242AA','#B9A2FF','#7C58C8','#49317F'),
    }
    for number,(name,(fill,edge,hover,pressed)) in enumerate(palettes.items()):
        normal=image(fill,edge); active=image(hover,edge); down=image(pressed,edge,True)
        focus=image(fill,'#FFE19C'); disabled=image('#252E3B','#465162')
        element=f'Action{number}.surface'
        style.element_create(element,'image',normal,('disabled',disabled),('pressed',down),
                             ('active',active),('focus',focus),border=12,sticky='nsew')
        style.layout(name,[(element,{'sticky':'nsew','children':[
            ('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
        style.configure(name,font=('맑은 고딕',10,'bold'),padding=(16,11),foreground='#FFFFFF',anchor='center')
        style.map(name,foreground=[('disabled','#8D9AAD'),('!disabled','#FFFFFF')])
    root._button_images=images
    root.option_add('*TButton.cursor','hand2')
