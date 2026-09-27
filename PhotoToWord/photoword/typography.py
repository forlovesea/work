"""Shared desktop typography, with Korean-capable system fallbacks."""
from tkinter import font, ttk


def configure_typography(root):
    available = set(font.families(root))
    family = next((name for name in ("Noto Sans KR", "Pretendard", "Malgun Gothic", "맑은 고딕")
                   if name in available), font.nametofont("TkDefaultFont", root=root).actual("family"))
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                 "TkCaptionFont", "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
        font.nametofont(name, root=root).configure(
            family=family, size=9 if name in ("TkSmallCaptionFont", "TkTooltipFont") else 10,
            weight="bold" if name == "TkHeadingFont" else "normal")
    # Limit option defaults to classic widgets so ttk title styles retain
    # their own size and weight.
    for widget in ("Listbox", "Text", "Entry", "Menu", "Message"):
        root.option_add(f"*{widget}.font", "TkTextFont")
    root.option_add("*TCombobox*Listbox.font", "TkTextFont")
    style = ttk.Style(root)
    style.configure(".", font=(family, 10))
    style.configure("TCombobox", font=(family, 10), padding=(5, 3))
    style.configure("TEntry", font=(family, 10))
    style.configure("TNotebook", tabmargins=(0, 0, 0, 0), background="#dce5ee")
    style.configure("TNotebook.Tab", font=(family, 10, "bold"), padding=(12, 8),
                    background="#e8eef5", foreground="#64748b")
    # The clam theme expands selected tabs by default, making adjacent
    # headers appear to have different heights. Keep their geometry fixed.
    style.map("TNotebook.Tab",
              expand=[("selected", (0, 0, 0, 0)), ("!selected", (0, 0, 0, 0))],
              padding=[("selected", (12, 8)), ("!selected", (12, 8))],
              background=[("selected", "#0f766e"), ("active", "#d3e9e6"),
                          ("!selected", "#e8eef5")],
              foreground=[("selected", "#ffffff"), ("active", "#235b57"),
                          ("!selected", "#64748b")],
              lightcolor=[("selected", "#0f766e"), ("!selected", "#e8eef5")],
              darkcolor=[("selected", "#0f766e"), ("!selected", "#e8eef5")])
    style.configure("TLabelframe.Label", font=(family, 10, "bold"))
    style.configure("DialogTitle.TLabel", font=(family, 16, "bold"))
    style.configure("Muted.TLabel", font=(family, 10), foreground="#65748a")
    return family
