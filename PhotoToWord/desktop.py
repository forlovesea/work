"""Windows desktop application. All Tk operations stay on the main thread."""
from __future__ import annotations

import io
import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from photoword.core import Element, Page, analyze, check_engine, load_image, preview
from photoword.exporters import FORMATS, save_export
from photoword.insights import detect_tables, recommend, text_elements
from photoword.correction_dialog import CorrectionDialog
from photoword.typography import configure_typography


class PhotoDocumentApp:
    def __init__(self, root):
        self.root = root
        self.paths = []
        self.corrections = {}
        self.pages = []
        self.tables = []
        self.recommendations = []
        self.busy = False
        self.cancel_event = threading.Event()
        self.events = queue.Queue()
        self.photo = None
        self.analysis_window = None
        self.analysis_progress = None
        self.analysis_status = None
        self.output_folder = None
        self.language = tk.StringVar(value="kor+eng")
        self.ocr_mode = tk.StringVar(value="한국어 본문")
        self.selection_mode = tk.StringVar(value="recommended")
        self.recommended_format = tk.StringVar(value="pdf")
        self.manual_format = tk.StringVar(value=FORMATS["docx"][0])
        self.original = tk.BooleanVar(value=False)
        self.word_layout = tk.StringVar(value="positioned")
        self.font_size_mode = tk.StringVar(value="preserve")
        self.status = tk.StringVar(value="사진을 추가한 다음 [분석 및 추천]을 누르세요.")
        self.format_description = tk.StringVar()
        self.analysis_note = tk.StringVar(value="사진 분석 후 우선순위와 추천 이유가 표시됩니다.")
        self.settings_path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "PhotoToWord" / "settings.json"
        self._load_settings()
        root.title("PhotoToWord · 사진 문서 변환")
        width, height = min(1240, root.winfo_screenwidth()-60), min(820, root.winfo_screenheight()-80)
        root.geometry(f"{width}x{height}")
        root.minsize(960, 620)
        root.configure(bg="#f3f6fb")
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        self.font_family = configure_typography(root)
        style.configure("TLabel", font=(self.font_family, 10))
        style.configure("TButton", background="#e8f1fb", foreground="#234d73", bordercolor="#9ab9d8", lightcolor="#f8fbff", darkcolor="#87a8c8", font=(self.font_family, 10, "bold"), padding=(10, 6), relief="raised")
        style.map("TButton", background=[("active", "#d9eaf8"), ("pressed", "#c6def0"), ("disabled", "#edf1f4")], foreground=[("disabled", "#8a96a3")])
        style.configure("Primary.TButton", background="#159a8a", foreground="#ffffff", bordercolor="#0e7569", lightcolor="#38b6a6", darkcolor="#0e7569", font=(self.font_family, 10, "bold"), padding=(12, 7), relief="raised")
        style.map("Primary.TButton", background=[("active", "#22ad9c"), ("pressed", "#0c7569"), ("disabled", "#a7cbc5")], foreground=[("disabled", "#eef8f6")])
        style.configure("Accent.TButton", background="#f7d9a8", foreground="#704c1d", bordercolor="#d9ae6f", lightcolor="#fff5e5", darkcolor="#c99650", font=(self.font_family, 10, "bold"), padding=(10, 6), relief="raised")
        style.map("Accent.TButton", background=[("active", "#f9e5c2"), ("pressed", "#edc584"), ("disabled", "#f1e7d7")], foreground=[("disabled", "#9a8d79")])
        style.configure("Danger.TButton", background="#f5d5d2", foreground="#8d3430", bordercolor="#d99b96", lightcolor="#fff7f6", darkcolor="#c77f79", font=(self.font_family, 10, "bold"), padding=(10, 6), relief="raised")
        style.map("Danger.TButton", background=[("active", "#f8e2df"), ("pressed", "#eabbb6"), ("disabled", "#f1e7e6")], foreground=[("disabled", "#a18b89")])
        style.configure("Title.TLabel", font=(self.font_family, 20, "bold"))
        style.configure("Heading.TLabel", font=(self.font_family, 11, "bold"))
        style.configure("Guide.TLabelframe", background="#ffffff", bordercolor="#c7d9d5")
        style.configure("Guide.TLabelframe.Label", background="#ffffff", foreground="#0f766e", font=(self.font_family, 10, "bold"))
        style.configure("GuideHint.TLabel", background="#ffffff", foreground="#65748a", font=(self.font_family, 9))
        for step, background, foreground in (
            (1, "#e5f5ec", "#236b3f"),
            (2, "#e8f1fb", "#285a86"),
            (3, "#f1ebfa", "#68428d"),
            (4, "#fff0d9", "#80531f"),
            (5, "#e8f3f4", "#23666b"),
        ):
            style.configure(f"Step{step}.TLabel", background=background, foreground=foreground, font=(self.font_family, 10, "bold"), padding=(10, 5))
        rank_styles = {
            1: ("#e5f5ec", "#78bf91", "#236b3f"),
            2: ("#e8f1fb", "#8cb5df", "#285a86"),
            3: ("#f1ebfa", "#b89bd8", "#68428d"),
        }
        for rank, (background, border, foreground) in rank_styles.items():
            style.configure(f"Rank{rank}.TLabelframe", background=background, bordercolor=border)
            style.configure(f"Rank{rank}.TLabelframe.Label", background=background, foreground=foreground, font=(self.font_family, 9, "bold"))
            style.configure(f"Rank{rank}.TLabel", background=background, foreground="#405064", font=(self.font_family, 9))
            style.configure(f"Rank{rank}.TRadiobutton", background=background, foreground=foreground, font=(self.font_family, 10, "bold"))
        self._build()
        self.selection_mode.trace_add("write", lambda *_: self.update_format())
        self.recommended_format.trace_add("write", lambda *_: self.update_format())
        self.manual_format.trace_add("write", lambda *_: self.update_format())
        self.update_format()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def _load_settings(self):
        try:
            value = json.loads(self.settings_path.read_text(encoding="utf-8"))
            executable = value.get("tesseract", "")
            if executable and Path(executable).is_file():
                os.environ["TESSERACT_CMD"] = executable
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        if not os.environ.get("TESSERACT_CMD"):
            base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
            candidate = base / "tools" / "Tesseract-OCR" / "tesseract.exe"
            if candidate.is_file():
                os.environ["TESSERACT_CMD"] = str(candidate)

    def _build(self):
        header = ttk.Frame(self.root, padding=(18, 12))
        header.pack(fill="x")
        ttk.Label(header, text="사진을 원하는 문서로", style="Title.TLabel").pack(anchor="w")
        guide = ttk.LabelFrame(header, text="빠른 사용 가이드", style="Guide.TLabelframe", padding=(10, 7))
        guide.pack(anchor="w", fill="x", pady=(8, 0))
        ttk.Label(guide, text="보정은 선택 사항입니다. [보정 옵션…]에서 전후 비교 → 원본/보정 사진 선택 → [분석 및 추천]을 누르세요.", style="GuideHint.TLabel", wraplength=850).pack(anchor="w", pady=(0, 5))
        steps = ttk.Frame(guide, style="Guide.TLabelframe")
        steps.pack(anchor="w")
        for index, label in enumerate(("1  사진 추가", "2  보정·사진 선택", "3  분석 및 추천", "4  출력 형식 선택", "5  저장"), 1):
            ttk.Label(steps, text=label, style=f"Step{index}.TLabel").pack(side="left")
            if index < 5:
                ttk.Label(steps, text="  →  ", foreground="#8190a1", font=(self.font_family, 10, "bold")).pack(side="left")
        toolbar = ttk.Frame(self.root, padding=(18, 0, 18, 10))
        toolbar.pack(fill="x")
        self.add_button = ttk.Button(toolbar, text="＋ 사진 추가", style="Accent.TButton", command=self.add_files)
        self.add_button.pack(side="left")
        self.analyze_button = ttk.Button(toolbar, text="분석 및 추천", style="Primary.TButton", command=self.start_analysis)
        self.analyze_button.pack(side="left", padx=7)
        ttk.Label(toolbar, text="OCR 언어").pack(side="left", padx=(12,4))
        self.lang_combo = ttk.Combobox(toolbar, state="readonly", values=["kor+eng", "kor", "eng"], textvariable=self.language, width=10)
        self.lang_combo.pack(side="left")
        self.lang_combo.bind("<<ComboboxSelected>>", lambda _: self.invalidate())
        self.mode_combo = ttk.Combobox(toolbar, state="readonly", values=["한국어 본문", "자동 배치", "흩어진 글자"], textvariable=self.ocr_mode, width=12)
        self.mode_combo.pack(side="left", padx=7)
        self.mode_combo.bind("<<ComboboxSelected>>", lambda _: self.invalidate())
        self.ocr_button = ttk.Button(toolbar, text="OCR 설정", style="Accent.TButton", command=self.ocr_settings)
        self.ocr_button.pack(side="right")
        self.manual_button = ttk.Button(toolbar, text="매뉴얼 보기", command=self.show_manual)
        self.manual_button.pack(side="right", padx=7)
        self.cancel_button = ttk.Button(toolbar, text="분석 취소", style="Danger.TButton", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="right", padx=7)

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=18)
        left = ttk.Frame(body, width=190, padding=8)
        body.add(left, weight=0)
        ttk.Label(left, text="입력 사진 · 페이지 순서", style="Heading.TLabel").pack(anchor="w")
        self.file_list = tk.Listbox(left, width=24, height=15, exportselection=False, font=(self.font_family,10), relief="flat", borderwidth=1)
        self.file_list.pack(fill="both", expand=True, pady=8)
        self.file_list.bind("<<ListboxSelect>>", lambda _: self.select_page())
        self.correction_button = ttk.Button(left, text="보정 옵션…", style="Accent.TButton", command=self.show_corrections)
        self.correction_button.pack(fill="x", pady=(0, 8))
        buttons = ttk.Frame(left)
        buttons.pack(fill="x")
        self.up_button = ttk.Button(buttons, text="↑", width=3, command=lambda: self.move(-1))
        self.up_button.pack(side="left")
        self.down_button = ttk.Button(buttons, text="↓", width=3, command=lambda: self.move(1))
        self.down_button.pack(side="left", padx=3)
        self.remove_button = ttk.Button(buttons, text="삭제", style="Danger.TButton", command=self.remove)
        self.remove_button.pack(side="right")
        ttk.Label(left, text="최대 20장 · 장당 20MB\nJPG / PNG / WEBP / BMP / TIFF", wraplength=185).pack(anchor="w", pady=10)

        middle = ttk.Frame(body, padding=8)
        body.add(middle, weight=1)
        notebook = ttk.Notebook(middle)
        notebook.pack(fill="both", expand=True)
        image_frame = ttk.Frame(notebook)
        notebook.add(image_frame, text="사진 및 검출 영역")
        ttk.Button(image_frame, text="원본 사진 보기", style="Accent.TButton", command=self.show_original).pack(anchor="e", padx=8, pady=(6, 2))
        self.canvas = tk.Canvas(image_frame, bg="#e9eef5", highlightthickness=0, width=360, height=400)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _: self.show_page(update_text=False))
        text_frame = ttk.Frame(notebook)
        notebook.add(text_frame, text="추출 텍스트 · 분석 안내")
        ttk.Button(text_frame, text="원본 사진 보기", style="Accent.TButton", command=self.show_original).pack(anchor="e", padx=8, pady=(6, 2))
        self.text_hint = ttk.Label(text_frame, text="추출 문장을 직접 수정할 수 있습니다. 저장 전에 수정 내용을 반영합니다.", foreground="#536174", wraplength=520)
        self.text_hint.pack(fill="x", padx=10, pady=(10, 4))
        self.text_view = tk.Text(text_frame, wrap="word", width=35, font=(self.font_family,10), bg="#ffffff", fg="#253247", insertbackground="#0f766e", relief="flat", padx=12, pady=10, spacing1=2, spacing3=4)
        self.text_view.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(text_frame, command=self.text_view.yview)
        scroll.pack(side="right", fill="y")
        self.text_view.configure(yscrollcommand=scroll.set)

        right_outer = ttk.Frame(body, width=350)
        body.add(right_outer, weight=0)
        right_canvas = tk.Canvas(right_outer, width=340, highlightthickness=0, yscrollincrement=20)
        right_scroll = ttk.Scrollbar(right_outer, orient="vertical", command=right_canvas.yview)
        right_scroll.pack(side="right", fill="y")
        right_canvas.pack(side="left", fill="both", expand=True)
        right_canvas.configure(yscrollcommand=right_scroll.set)
        right = ttk.Frame(right_canvas, padding=8)
        right_window = right_canvas.create_window((0,0), window=right, anchor="nw")
        right.bind("<Configure>", lambda _: right_canvas.configure(scrollregion=right_canvas.bbox("all")))
        right_canvas.bind("<Configure>", lambda e: right_canvas.itemconfigure(right_window,width=e.width))
        ttk.Label(right, text="출력 형식", style="Heading.TLabel").pack(anchor="w")
        ttk.Radiobutton(right, text="추천 순위에서 선택", value="recommended", variable=self.selection_mode).pack(anchor="w", pady=(10,5))
        self.cards = []
        for rank in range(1,4):
            frame = ttk.LabelFrame(right, text=f"{rank}순위", style=f"Rank{rank}.TLabelframe", padding=8)
            frame.pack(fill="x", pady=3)
            radio = ttk.Radiobutton(frame, text="분석 대기", style=f"Rank{rank}.TRadiobutton", variable=self.recommended_format, value=f"pending{rank}", command=lambda: self.selection_mode.set("recommended"))
            radio.pack(anchor="w")
            radio.state(["disabled"])
            label = ttk.Label(frame, text="사진을 먼저 분석해 주세요.", style=f"Rank{rank}.TLabel", wraplength=280)
            label.pack(anchor="w", pady=(3,0))
            self.cards.append((radio, label))
        ttk.Label(right, textvariable=self.analysis_note, wraplength=300, foreground="#536174").pack(anchor="w", pady=7)
        ttk.Separator(right).pack(fill="x", pady=6)
        ttk.Radiobutton(right, text="직접 선택 (추천과 무관하게 적용)", value="manual", variable=self.selection_mode).pack(anchor="w", pady=5)
        self.manual_combo = ttk.Combobox(right, state="readonly", width=35, textvariable=self.manual_format, values=[v[0] for v in FORMATS.values()])
        self.manual_combo.pack(fill="x")
        self.manual_combo.bind("<<ComboboxSelected>>", lambda _: self.selection_mode.set("manual"))
        ttk.Label(right, textvariable=self.format_description, wraplength=300).pack(anchor="w", pady=9)
        ttk.Label(right, text="Word 저장 방식", style="Heading.TLabel").pack(anchor="w", pady=(3, 2))
        ttk.Radiobutton(right, text="원본 배치 모드 (텍스트 상자)", value="positioned", variable=self.word_layout).pack(anchor="w")
        ttk.Radiobutton(right, text="일반 텍스트 모드 (텍스트 상자 없음)", value="plain_text", variable=self.word_layout).pack(anchor="w")
        ttk.Label(right, text="Word 폰트 크기", style="Heading.TLabel").pack(anchor="w", pady=(5, 2))
        ttk.Radiobutton(right, text="현재 상태 유지 (원본 비율)", value="preserve", variable=self.font_size_mode).pack(anchor="w")
        ttk.Radiobutton(right, text="모든 글자 동일한 크기", value="uniform", variable=self.font_size_mode).pack(anchor="w")
        ttk.Checkbutton(right, text="Word/PPT: 원본 사진으로 보존", variable=self.original).pack(anchor="w")
        ttk.Label(right, text="추천은 규칙 기반이며 정확도를 보장하지 않습니다.\n표 셀·글자·도형은 결과 확인이 필요합니다.", wraplength=300, foreground="#536174").pack(anchor="w", pady=8)
        self._bind_panel_wheel(right_outer, right_canvas)

        footer = ttk.Frame(self.root, padding=(18,10))
        footer.pack(fill="x")
        self.save_button = ttk.Button(footer, text="선택한 형식으로 저장…", style="Primary.TButton", command=self.start_export, state="disabled")
        self.save_button.pack(side="right")
        self.folder_button = ttk.Button(footer, text="저장 폴더 열기", command=self.open_folder, state="disabled")
        self.folder_button.pack(side="right", padx=7)
        self.progress = ttk.Progressbar(footer, mode="determinate", length=130)
        self.progress.pack(side="left", padx=(0,10))
        ttk.Label(footer, textvariable=self.status, wraplength=480).pack(side="left", fill="x", expand=True)

    def _bind_panel_wheel(self, panel, canvas):
        remainder = 0

        def scroll(event):
            nonlocal remainder
            if canvas.yview() == (0.0, 1.0):
                remainder = 0
                return "break"
            delta = event.delta
            if delta * remainder < 0:
                remainder = 0
            remainder += delta
            steps = int(remainder / 120)
            remainder -= steps * 120
            if steps:
                canvas.yview_scroll(-steps * 3, "units")
            return "break"

        def bind_children(widget):
            # Widget bindings run before class bindings, so scrolling over the
            # format combobox moves the panel without changing its selection.
            widget.bind("<MouseWheel>", scroll, add="+")
            for child in widget.winfo_children():
                bind_children(child)

        bind_children(panel)

    def selected_format(self):
        if self.selection_mode.get() == "recommended":
            return self.recommended_format.get()
        return next(key for key, value in FORMATS.items() if value[0] == self.manual_format.get())

    def update_format(self):
        format = self.selected_format()
        self.format_description.set(FORMATS.get(format, ("", "분석 후 형식을 선택하세요."))[1])

    def refresh_files(self, selected=0):
        self.file_list.delete(0, "end")
        for index, path in enumerate(self.paths, 1):
            marker = " [보정]" if path in self.corrections else ""
            self.file_list.insert("end", f"{index}. {path.name}{marker}")
        if self.paths:
            self.file_list.selection_set(min(selected, len(self.paths)-1))
        self.show_page()

    def select_page(self):
        self.apply_text_edits()
        self.show_page()

    def invalidate(self):
        self.pages, self.tables, self.recommendations = [], [], []
        self.save_button.state(["disabled"])
        for radio, label in self.cards:
            radio.configure(text="분석 대기")
            radio.state(["disabled"])
            label.configure(text="사진을 먼저 분석해 주세요.")
        self.analysis_note.set("변경된 사진/언어로 다시 분석해 주세요.")
        self.status.set("사진을 추가한 다음 [분석 및 추천]을 누르세요.")
        self.progress["value"] = 0

    def add_files(self):
        if self.busy:
            return
        filenames = filedialog.askopenfilenames(title="변환할 사진 선택", filetypes=[("사진 파일", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("모든 파일", "*.*")])
        new = [Path(name) for name in filenames if Path(name) not in self.paths]
        if len(self.paths)+len(new) > 20:
            messagebox.showwarning("사진 개수", "최대 20장까지 추가할 수 있습니다.")
            return
        if new:
            self.paths.extend(new)
            self.invalidate()
            self.refresh_files()

    def remove(self):
        if not self.busy and self.file_list.curselection():
            index = self.file_list.curselection()[0]
            self.corrections.pop(self.paths.pop(index), None)
            self.invalidate()
            self.refresh_files(index)

    def move(self, direction):
        if self.busy or not self.file_list.curselection():
            return
        index = self.file_list.curselection()[0]
        new = index+direction
        if 0 <= new < len(self.paths):
            self.paths[index], self.paths[new] = self.paths[new], self.paths[index]
            self.invalidate()
            self.refresh_files(new)

    def show_page(self, update_text=True):
        if not self.file_list.curselection():
            self.canvas.delete("all")
            if update_text:
                self._set_text("")
            return
        index = self.file_list.curselection()[0]
        try:
            if index < len(self.pages):
                page = self.pages[index]
                image = preview(page)
                content = "\n".join(e.text for e in text_elements(page))
                hint = "\n".join(page.warnings) or "분석 안내: 특이사항이 없습니다."
            else:
                path = self.paths[index]
                if path.stat().st_size > 20*1024*1024:
                    raise ValueError("사진 한 장은 20MB 이하여야 합니다.")
                image = self.analysis_image(path)
                content = "분석 전입니다. [분석 및 추천]을 누르세요."
                hint = "사진을 분석하면 추출된 텍스트를 여기서 수정할 수 있습니다."
            if update_text:
                self.text_hint.configure(text=hint)
                self._set_text(content.strip())
            width, height = max(80,self.canvas.winfo_width()-20), max(80,self.canvas.winfo_height()-20)
            image.thumbnail((width,height))
            self.photo = ImageTk.PhotoImage(image)
            self.canvas.delete("all")
            self.canvas.create_image(width/2+10,height/2+10,image=self.photo,anchor="center")
        except Exception as exc:
            self.canvas.delete("all")
            if update_text:
                self.text_hint.configure(text="분석 안내")
                self._set_text(f"사진을 열 수 없습니다: {exc}")

    def show_original(self):
        if not self.file_list.curselection():
            messagebox.showinfo("원본 사진", "먼저 사진을 추가하고 목록에서 사진을 선택해 주세요.")
            return
        index = self.file_list.curselection()[0]
        try:
            image = load_image(self.paths[index].read_bytes())
            window = tk.Toplevel(self.root)
            window.title(f"원본 사진 · {self.paths[index].name}")
            window.transient(self.root)
            max_width = max(480, self.root.winfo_screenwidth() - 180)
            max_height = max(420, self.root.winfo_screenheight() - 180)
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            self.original_photo = ImageTk.PhotoImage(image)
            view = ttk.Label(window, image=self.original_photo)
            view.pack(padx=12, pady=12)
            window.geometry(f"{image.width + 24}x{image.height + 24}")
        except Exception as exc:
            messagebox.showerror("원본 사진", f"사진을 열 수 없습니다: {exc}")

    def analysis_image(self, path, corrections=None):
        selected = self.corrections if corrections is None else corrections
        if path in selected:
            with Image.open(io.BytesIO(selected[path][0])) as image:
                return image.convert("RGB")
        return load_image(path.read_bytes())

    def show_corrections(self):
        if self.busy:
            return
        if not self.file_list.curselection():
            messagebox.showinfo("보정 옵션", "먼저 사진을 추가하고 목록에서 사진을 선택해 주세요.")
            return
        index = self.file_list.curselection()[0]
        path = self.paths[index]
        try:
            if path.stat().st_size > 20*1024*1024:
                raise ValueError("사진 한 장은 20MB 이하여야 합니다.")
            source = load_image(path.read_bytes())
        except Exception as exc:
            messagebox.showerror("보정 옵션", str(exc))
            return
        previous = self.corrections.get(path)
        def select(image, options):
            if image is None:
                self.corrections.pop(path, None)
            else:
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                self.corrections[path] = (buffer.getvalue(), options)
            self.invalidate()
            self.refresh_files(index)
            choice = "보정 사진" if image is not None else "원본 사진"
            self.status.set(f"{path.name}: {choice} 선택 완료. [분석 및 추천]을 누르세요.")
        return CorrectionDialog(self.root, source, path.name, select, previous[1] if previous else None)

    def show_manual(self):
        window = tk.Toplevel(self.root)
        window.title("PhotoToWord 사용 매뉴얼")
        window.transient(self.root)
        window.geometry("700x650")
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="PhotoToWord 사용 매뉴얼", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="사진을 분석해 편집 가능한 문서로 저장하는 방법", style="Muted.TLabel").pack(anchor="w", pady=(2, 10))
        text = tk.Text(frame, wrap="word", font=(self.font_family, 10), bg="#ffffff", fg="#253247", relief="flat", padx=16, pady=14, spacing1=2, spacing3=5)
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        text.tag_configure("section", foreground="#0f766e", font=(self.font_family, 13, "bold"), spacing1=12, spacing3=5)
        text.tag_configure("step1", background="#e5f5ec", foreground="#236b3f", font=(self.font_family, 11, "bold"), spacing1=8)
        text.tag_configure("step2", background="#e8f1fb", foreground="#285a86", font=(self.font_family, 11, "bold"), spacing1=8)
        text.tag_configure("step3", background="#f1ebfa", foreground="#68428d", font=(self.font_family, 11, "bold"), spacing1=8)
        text.tag_configure("step4", background="#fff0d9", foreground="#80531f", font=(self.font_family, 11, "bold"), spacing1=8)
        text.tag_configure("step5", background="#e8f3f4", foreground="#23666b", font=(self.font_family, 11, "bold"), spacing1=8)
        text.tag_configure("body", foreground="#405064", font=(self.font_family, 10), spacing3=5)
        text.tag_configure("note", background="#fff7df", foreground="#765b23", font=(self.font_family, 10, "bold"), spacing1=10, spacing3=8)
        text.insert("end", "사용 순서\n", "section")
        steps = [
            ("step1", "1  사진 추가\n", "사진 추가 버튼으로 JPG, PNG, WEBP, BMP, TIFF 사진을 선택합니다. 최대 20장, 한 장은 20MB 이하입니다.\n\n"),
            ("step2", "2  보정·사진 선택 (선택 사항)\n", "왼쪽 목록에서 사진 한 장을 선택하고 [보정 옵션…]을 누릅니다. 옵션 조절 → [보정 미리보기] → 전후 비교 → [원본 사진 선택] 또는 [보정 사진 선택] 순서로 진행합니다. 보정이 필요 없으면 바로 다음 단계로 진행하세요.\n\n"),
            ("step3", "3  분석 및 추천\n", "OCR 언어와 배치 모드를 고릅니다. 한국어 문서는 kor+eng를 사용하고, 한국어 본문·자동 배치·흩어진 글자 중 문서 형태에 맞게 선택합니다. [분석 및 추천]을 누르면 최종 선택한 사진으로 분석합니다. 보정 창에서 사진을 선택하는 것만으로 분석이 시작되지는 않습니다. 진행 팝업에서 사진별 진행률을 확인하거나 분석을 취소할 수 있습니다.\n\n"),
            ("step4", "4  결과 확인 · 출력 형식 선택\n", "추출 텍스트 · 분석 안내 탭에서 OCR 문장을 수정하고, 원본 사진 보기로 비교합니다. 추천 순위를 선택하거나 직접 선택에서 원하는 출력 형식을 고릅니다.\n\n"),
            ("step5", "5  저장\n", "Word 저장 방식 등 출력 옵션을 확인하고 [선택한 형식으로 저장…]에서 파일 이름과 경로를 지정합니다.\n\n"),
        ]
        for tag, title, body in steps:
            text.insert("end", title, tag)
            text.insert("end", body, "body")
        text.insert("end", "보정 옵션 설명\n", "section")
        text.insert("end", "자동 기울기 보정: 기울어진 글줄이나 수평선을 감지해 회전합니다. 감지되지 않으면 그대로 유지됩니다. 원근 보정 기능은 아닙니다.\n그림자 완화: 배경 밝기의 차이를 줄입니다. 컬러 사진이나 도형의 색도 달라질 수 있습니다.\n대비 (0.5~2.0): 밝고 어두운 부분의 차이를 조절합니다. 1.0은 대비를 추가로 바꾸지 않는 값입니다.\n회색조: 색상을 회색 명암으로 바꿉니다.\n흑백 보정: 글자와 배경을 검정·흰색으로 구분합니다. 가는 획이 사라지지 않는지 비교하세요.\n\n", "body")
        text.insert("end", "전후 비교와 최종 선택\n", "section")
        text.insert("end", "왼쪽은 보정 전 원본, 오른쪽은 보정 후 사진입니다. [실제 크기 (100%)]를 켜고 스크롤하면 작은 글자까지 확인할 수 있습니다. 옵션을 변경할 때마다 [보정 미리보기]를 눌러야 새 결과를 선택할 수 있습니다.\n\n[보정 사진 선택]: 해당 사진에만 적용하고 목록에 [보정]을 표시합니다. 분석과 문서에 포함되는 이미지에 이 사진이 사용됩니다.\n[원본 사진 선택]: 해당 사진의 보정을 해제합니다. 다시 분석하면 원본을 사용합니다.\n[취소] 또는 창 닫기: 이번 변경을 적용하지 않고 기존 선택을 유지합니다.\n\n원본 파일은 수정하지 않습니다. 사진별 보정 선택은 앱 종료 시 초기화됩니다. 분석 후 사진 선택을 바꾸면 기존 분석 결과와 편집 내용이 초기화되므로 다시 [분석 및 추천]을 눌러 주세요. [원본 사진 보기]는 보정 여부와 관계없이 원본을 보여 줍니다.\n\n", "body")
        text.insert("end", "Word 저장 옵션\n", "section")
        text.insert("end", "원본 배치 모드: 사진 속 위치를 유지합니다.\n일반 텍스트 모드: 텍스트 상자 없이 일반 Word 문단으로 저장합니다.\n현재 상태 유지: 글자별 크기를 유지합니다.\n모든 글자 동일한 크기: 전체 글자를 하나의 공통 크기로 저장합니다.\n\n", "body")
        text.insert("end", "OCR 설정\n", "section")
        text.insert("end", "OCR 설정에서 tesseract.exe를 지정할 수 있습니다. 보통 경로는 C:\\Program Files\\Tesseract-OCR\\tesseract.exe입니다. 한국어 인식에는 kor.traineddata가 필요합니다.\n\n", "body")
        text.insert("end", "알아두세요\n", "section")
        text.insert("end", "OCR은 사진 품질과 글꼴에 따라 달라질 수 있습니다. 카드번호 마스킹 기호나 특수기호가 잘못 인식되면 추출 텍스트 탭에서 수정한 뒤 저장하세요. 복잡한 표와 도형은 원본 이미지로 보존될 수 있습니다.\n", "note")
        text.configure(state="disabled")

    def _set_text(self, content):
        self.text_view.delete("1.0", "end")
        self.text_view.insert("1.0", content)

    def apply_text_edits(self):
        if not self.file_list.curselection():
            return
        index = self.file_list.curselection()[0]
        if index >= len(self.pages):
            return
        elements = text_elements(self.pages[index])
        lines = self.text_view.get("1.0", "end-1c").splitlines()
        for element_index, element in enumerate(elements):
            if element_index < len(lines):
                element.text = lines[element_index]
            else:
                element.text = ""

    def set_busy(self, busy, cancellable=False):
        self.busy = busy
        for button in (self.add_button,self.analyze_button,self.ocr_button,self.remove_button,self.up_button,self.down_button,self.correction_button):
            button.state(["disabled" if busy else "!disabled"])
        self.lang_combo.configure(state="disabled" if busy else "readonly")
        self.mode_combo.configure(state="disabled" if busy else "readonly")
        self.save_button.state(["!disabled" if self.pages and not busy else "disabled"])
        self.cancel_button.state(["!disabled" if busy and cancellable else "disabled"])

    def open_analysis_window(self, total):
        self.close_analysis_window()
        window = tk.Toplevel(self.root)
        window.title("분석 진행")
        window.transient(self.root)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", self.cancel)
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="사진을 분석하고 있습니다", style="Heading.TLabel").pack(anchor="w")
        self.analysis_status = tk.StringVar(value=f"준비 중... (0/{total})")
        ttk.Label(frame, textvariable=self.analysis_status, width=34).pack(anchor="w", pady=(8, 10))
        self.analysis_progress = ttk.Progressbar(frame, mode="determinate", maximum=total, length=300)
        self.analysis_progress.pack(fill="x")
        ttk.Button(frame, text="분석 취소", style="Danger.TButton", command=self.cancel).pack(anchor="e", pady=(10, 0))
        window.geometry("340x175")
        window.update_idletasks()
        window.grab_set()
        self.analysis_window = window

    def close_analysis_window(self):
        if self.analysis_window and self.analysis_window.winfo_exists():
            self.analysis_window.grab_release()
            self.analysis_window.destroy()
        self.analysis_window = None
        self.analysis_progress = None
        self.analysis_status = None

    def start_analysis(self):
        if self.busy:
            return
        if not self.paths:
            messagebox.showinfo("사진 추가", "먼저 사진 파일을 추가해 주세요.")
            return
        self.invalidate()
        self.cancel_event.clear()
        self.set_busy(True, True)
        paths, language = list(self.paths), self.language.get()
        psm = {"한국어 본문": 6, "자동 배치": 3, "흩어진 글자": 11}[self.ocr_mode.get()]
        self.status.set("OCR 환경과 사진을 확인하고 있습니다…")
        self.open_analysis_window(len(paths))
        threading.Thread(target=self._analyze_worker, args=(paths,language,psm,dict(self.corrections)), daemon=True).start()

    def _analyze_worker(self, paths, language, psm=6, corrections=None):
        try:
            engine_error = None
            try:
                check_engine(language)
            except RuntimeError as exc:
                engine_error = str(exc)
            pages, tables = [], []
            for index, path in enumerate(paths):
                if self.cancel_event.is_set():
                    self.events.put(("cancelled", None))
                    return
                if path.stat().st_size > 20*1024*1024:
                    raise ValueError(f"{path.name}: 20MB를 초과합니다.")
                data = path.read_bytes()
                selected = self.corrections if corrections is None else corrections
                prepared = self.analysis_image(path, selected) if path in selected else None
                if engine_error:
                    image = prepared if prepared is not None else load_image(data)
                    page = Page(image, [Element("image", (0,0,*image.size))],
                                [engine_error, "OCR 없이 이미지 보존 모드로 분석했습니다. 텍스트/셀 내용은 추출되지 않습니다."], ocr_available=False)
                else:
                    page = analyze(data, language, psm, prepared_image=prepared)
                pages.append(page)
                tables.append(detect_tables(page))
                self.events.put(("progress", (index+1,len(paths))))
            if self.cancel_event.is_set():
                self.events.put(("cancelled", None))
            else:
                self.events.put(("analysis", (pages,tables)))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def accept_analysis(self, pages, tables):
        self.pages, self.tables = pages, tables
        self.recommendations = recommend(pages,tables)
        for (radio,label), item in zip(self.cards,self.recommendations):
            radio.configure(text=FORMATS[item.format][0], value=item.format)
            radio.state(["!disabled"])
            label.configure(text=item.reason)
        self.recommended_format.set(self.recommendations[0].format)
        total = sum(len(group) for group in tables)
        chars = sum(len(e.text) for p in pages for e in text_elements(p))
        limited = not all(p.ocr_available for p in pages)
        self.analysis_note.set(f"{len(pages)}페이지 · 표 {total}개 · 추출 글자 {chars}자" + ("\nOCR 미설치/언어 누락: 이미지 보존 출력만 가능합니다." if limited else ""))
        self.status.set("분석 완료. 추천 순위 또는 원하는 파일 형식을 선택하세요.")
        self.close_analysis_window()
        self.set_busy(False)
        self.show_page()

    def cancel(self):
        self.cancel_event.set()
        self.status.set("현재 사진 처리가 끝나면 취소합니다. OCR은 최대 120초가 걸릴 수 있습니다.")
        self.cancel_button.state(["disabled"])

    def start_export(self):
        if self.busy or not self.pages:
            return
        self.apply_text_edits()
        format = self.selected_format()
        if format in ("txt","csv","xlsx") and not any(text_elements(p) for p in self.pages):
            if not messagebox.askyesno("인식된 글자 없음", "인식된 텍스트가 없어 셀/본문 내용은 비어 있거나 안내 문구로 저장됩니다.\nExcel에는 원본 사진이 포함됩니다. 이 형식으로 저장할까요?"):
                return
        filename = filedialog.asksaveasfilename(title="변환 문서 저장", initialfile=self.paths[0].stem+"_변환."+format,
                                               defaultextension="."+format, filetypes=[(FORMATS[format][0],"*."+format)], confirmoverwrite=True)
        if not filename:
            return
        if Path(filename).suffix.lower() != "."+format:
            messagebox.showerror("파일 확장자", f"선택한 형식에 맞게 .{format} 확장자로 저장해 주세요.")
            return
        self.set_busy(True)
        self.status.set(f"{FORMATS[format][0]} 저장 중…")
        plain_text = self.word_layout.get() == "plain_text" and format == "docx"
        threading.Thread(target=self._export_worker, args=(filename,format,self.original.get(),plain_text,self.font_size_mode.get()), daemon=True).start()

    def _export_worker(self, filename, format, original, plain_text=False, font_size_mode="preserve"):
        try:
            save_export(filename,self.pages,format,original=original,plain_text=plain_text,font_size_mode=font_size_mode,tables=self.tables)
            self.events.put(("saved",filename))
        except Exception as exc:
            self.events.put(("error",str(exc)))

    def poll(self):
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "progress":
                    done,total = payload
                    self.progress["value"] = done/total*100
                    self.status.set(f"사진 분석 중: {done}/{total}")
                    if self.analysis_progress:
                        self.analysis_progress["value"] = done
                    if self.analysis_status:
                        self.analysis_status.set(f"사진 분석 중... {done}/{total}")
                elif event == "analysis":
                    self.accept_analysis(*payload)
                elif event == "cancelled":
                    self.close_analysis_window()
                    self.set_busy(False)
                    self.status.set("분석이 취소되었습니다.")
                elif event == "saved":
                    self.set_busy(False)
                    self.output_folder = str(Path(payload).parent)
                    self.folder_button.state(["!disabled"])
                    self.status.set(f"저장 완료: {Path(payload).name}")
                    messagebox.showinfo("저장 완료", payload)
                elif event == "error":
                    self.close_analysis_window()
                    self.set_busy(False)
                    self.status.set("처리 실패. 파일 또는 OCR 설정을 확인해 주세요.")
                    messagebox.showerror("처리 실패",payload)
        except queue.Empty:
            pass
        self.root.after(100,self.poll)

    def ocr_settings(self):
        if self.busy:
            return
        window = tk.Toplevel(self.root)
        window.title("OCR 설정")
        window.transient(self.root)
        window.grab_set()
        frame = ttk.Frame(window,padding=18)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="Tesseract 실행 파일 경로",style="Heading.TLabel").pack(anchor="w")
        path = tk.StringVar(value=os.environ.get("TESSERACT_CMD", ""))
        ttk.Entry(frame,textvariable=path,width=65).pack(fill="x",pady=8)
        def browse():
            selected = filedialog.askopenfilename(parent=window,title="tesseract.exe 선택",filetypes=[("Tesseract", "tesseract.exe")])
            if selected:
                path.set(selected)
        ttk.Button(frame,text="실행 파일 찾기…",command=browse).pack(anchor="w")
        ttk.Label(frame,text="기본 설치 경로 또는 PATH는 자동 탐색합니다.\n한국어 인식에는 kor.traineddata가 필요합니다.\n미설치 상태에서도 사진 보존 출력은 가능합니다.",wraplength=480).pack(anchor="w",pady=12)
        def save():
            value = path.get().strip().strip('"')
            if value and not Path(value).is_file():
                messagebox.showerror("경로 확인","실행 파일을 찾을 수 없습니다.",parent=window)
                return
            previous = os.environ.get("TESSERACT_CMD")
            if value:
                os.environ["TESSERACT_CMD"] = value
            else:
                os.environ.pop("TESSERACT_CMD",None)
            try:
                languages = check_engine(self.language.get())
                self.settings_path.parent.mkdir(parents=True,exist_ok=True)
                self.settings_path.write_text(json.dumps({"tesseract":value}),encoding="utf-8")
            except Exception as exc:
                if previous:
                    os.environ["TESSERACT_CMD"] = previous
                else:
                    os.environ.pop("TESSERACT_CMD",None)
                messagebox.showerror("OCR 확인",str(exc),parent=window)
                return
            self.invalidate()
            window.destroy()
            messagebox.showinfo("OCR 준비 완료", "설치된 언어: "+", ".join(languages))
        ttk.Button(frame,text="확인 및 저장",command=save).pack(anchor="e")

    def open_folder(self):
        if self.output_folder:
            try:
                os.startfile(self.output_folder)
            except OSError as exc:
                messagebox.showerror("폴더 열기",str(exc))

    def close(self):
        if self.busy:
            messagebox.showinfo("처리 중", "분석은 [분석 취소]를 누른 뒤 종료하세요. 저장 중이면 완료될 때까지 기다려 주세요.")
            return
        self.root.destroy()


def smoke_test(root, app, output):
    """Exercise the packaged GUI + every exporter using synthetic elements, not OCR."""
    output = Path(output)
    output.mkdir(parents=True,exist_ok=True)
    page = Page(Image.new("RGB",(600,800),"white"),[
        Element("text",(40,40,420,30),"GUI smoke test 한글",95),
        Element("rect",(40,150,180,100)),
        Element("oval",(320,150,180,100)),
        Element("image",(40,400,300,200)),
    ])
    app.paths = [output/"synthetic.png"]
    page.image.save(app.paths[0])
    app.accept_analysis([page],[[]])
    app.refresh_files()
    root.update()
    assert len(app.recommendations) == 3
    for format in FORMATS:
        app.selection_mode.set("manual")
        app.manual_format.set(FORMATS[format][0])
        assert app.selected_format() == format
        save_export(output/f"smoke.{format}",app.pages,format,tables=app.tables)
    (output/"smoke-result.json").write_text(json.dumps({"gui": "ok", "formats":list(FORMATS),"ocr_tested":False}),encoding="utf-8")
    root.destroy()


def verify_release(root, app, output):
    """Verify the packaged application's actual OCR path and all exporters."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    sample = base / "korean_sample.png"
    if not sample.exists():
        sample = base / "samples/korean_ocr_verified/korean_sample.png"
    app.paths = [sample]
    app._analyze_worker(app.paths, "kor+eng", 6)
    while True:
        event, payload = app.events.get_nowait()
        if event == "error":
            raise RuntimeError(payload)
        if event == "analysis":
            app.accept_analysis(*payload)
            break
    assert all(page.ocr_available for page in app.pages), "OCR unavailable"
    recognized = "\n".join(item.text for page in app.pages for item in text_elements(page))
    assert "12345" in recognized and "홍길동" in recognized, recognized
    for format in FORMATS:
        save_export(output / f"verified.{format}", app.pages, format, tables=app.tables)
    (output / "verification.json").write_text(json.dumps({
        "gui": "ok", "ocr": "ok", "formats": list(FORMATS),
        "ocr_executable": os.environ.get("TESSERACT_CMD"), "recognized": recognized,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    root.destroy()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError,OSError):
        pass
    root = tk.Tk()
    if len(sys.argv) == 3 and sys.argv[1] in ("--smoke-test", "--verify-release"):
        root.withdraw()
        app = PhotoDocumentApp(root)
        if sys.argv[1] == "--verify-release":
            verify_release(root, app, sys.argv[2])
        else:
            smoke_test(root,app,sys.argv[2])
    else:
        PhotoDocumentApp(root)
        root.mainloop()


if __name__ == "__main__":
    main()
