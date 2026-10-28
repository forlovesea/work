"""Shared ETF and Advisor desktop palette and widget styles."""
from tkinter import ttk


def install_theme(root):
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
    return colors
