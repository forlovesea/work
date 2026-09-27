"""Before/after review; only an explicit choice commits a correction."""
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from .corrections import CorrectionOptions, correct_image


class CorrectionDialog(tk.Toplevel):
    def __init__(self, parent, source, name, on_select, options=None):
        super().__init__(parent)
        self.title(f"보정 옵션 · {name}")
        self.transient(parent)
        self.geometry(f"{min(1150, self.winfo_screenwidth()-60)}x{min(780, self.winfo_screenheight()-80)}")
        self.minsize(760, 520)
        self.source = source.copy()
        self.result = None
        self.on_select = on_select
        self.results = queue.Queue()
        self.generation = 0
        self.running = False
        self.photos = []
        options = options or CorrectionOptions()
        self.deskew = tk.BooleanVar(value=options.deskew)
        self.shadow = tk.BooleanVar(value=options.shadow)
        self.grayscale = tk.BooleanVar(value=options.grayscale)
        self.binary = tk.BooleanVar(value=options.binary)
        self.contrast = tk.DoubleVar(value=options.contrast)
        self.actual_size = tk.BooleanVar(value=False)
        controls = ttk.Frame(self, padding=12)
        controls.pack(fill="x")
        ttk.Label(controls, text="보정 옵션", style="DialogTitle.TLabel").pack(anchor="w")
        toggles = ttk.Frame(controls)
        toggles.pack(fill="x", pady=6)
        for title, variable in (("자동 기울기 보정", self.deskew), ("그림자 완화", self.shadow),
                                ("회색조", self.grayscale), ("흑백 보정", self.binary)):
            ttk.Checkbutton(toggles, text=title, variable=variable).pack(side="left", padx=(0, 12))
        row = ttk.Frame(controls)
        row.pack(fill="x")
        ttk.Label(row, text="대비 (0.5~2.0)").pack(side="left")
        ttk.Scale(row, from_=0.5, to=2.0, variable=self.contrast, length=220).pack(side="left", padx=8)
        self.refresh_button = ttk.Button(row, text="보정 미리보기", command=self.refresh_preview)
        self.refresh_button.pack(side="left", padx=8)
        ttk.Checkbutton(row, text="실제 크기 (100%)", variable=self.actual_size, command=self.render).pack(side="right")
        ttk.Label(controls, text="선택한 사진 한 장에 적용합니다. 원본 파일은 그대로 보관됩니다.\n보정 사진을 선택하면 분석과 문서의 이미지 출력에 함께 사용됩니다.").pack(anchor="w", pady=(8, 0))
        comparison = ttk.Frame(self, padding=(12, 0))
        comparison.pack(fill="both", expand=True)
        comparison.columnconfigure((0, 1), weight=1, uniform="preview")
        comparison.rowconfigure(0, weight=1)
        self.canvases = []
        for column, title in enumerate(("보정 전 · 원본", "보정 후")):
            frame = ttk.LabelFrame(comparison, text=title, padding=4)
            frame.grid(row=0, column=column, sticky="nsew", padx=4)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            canvas = tk.Canvas(frame, background="#e9eef5", highlightthickness=0)
            canvas.grid(row=0, column=0, sticky="nsew")
            vertical = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
            vertical.grid(row=0, column=1, sticky="ns")
            horizontal = ttk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
            horizontal.grid(row=1, column=0, sticky="ew")
            canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            canvas.bind("<MouseWheel>", lambda event, c=canvas: c.yview_scroll(-int(event.delta/120)*3, "units"))
            canvas.bind("<Configure>", lambda event: self.render())
            self.canvases.append(canvas)
        footer = ttk.Frame(self, padding=12)
        footer.pack(fill="x")
        self.status = tk.StringVar(value="")
        ttk.Label(footer, textvariable=self.status).pack(anchor="w", pady=(0, 8))
        ttk.Button(footer, text="취소", command=self.destroy).pack(side="right")
        self.apply_button = ttk.Button(footer, text="보정 사진 선택", command=lambda: self.choose(True), state="disabled")
        self.apply_button.pack(side="right", padx=8)
        ttk.Button(footer, text="원본 사진 선택", command=lambda: self.choose(False)).pack(side="right")
        for variable in (self.deskew, self.shadow, self.grayscale, self.binary, self.contrast):
            variable.trace_add("write", self.changed)
        self.grab_set()
        self.poll_id = self.after(80, self.poll_result)
        self.refresh_preview()

    def options(self):
        return CorrectionOptions(self.deskew.get(), self.shadow.get(), self.contrast.get(),
                                 self.grayscale.get(), self.binary.get())

    def changed(self, *_):
        self.generation += 1
        self.apply_button.state(["disabled"])
        self.status.set("옵션이 변경되었습니다. [보정 미리보기]를 눌러 갱신하세요.")

    def refresh_preview(self):
        if self.running:
            return
        self.running = True
        self.apply_button.state(["disabled"])
        self.refresh_button.state(["disabled"])
        self.status.set("보정 사진을 준비하고 있습니다…")
        generation, options = self.generation, self.options()
        def work():
            try:
                self.results.put((generation, correct_image(self.source, options), None))
            except Exception as exc:
                self.results.put((generation, None, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll_result(self):
        try:
            generation, result, error = self.results.get_nowait()
            self.running = False
            self.refresh_button.state(["!disabled"])
            if generation == self.generation:
                if error:
                    self.status.set("보정에 실패했습니다. 옵션을 조절해 다시 시도하세요.")
                    messagebox.showerror("사진 보정", error, parent=self)
                else:
                    self.result = result
                    self.apply_button.state(["!disabled"])
                    self.status.set("두 사진의 글자 획을 비교한 뒤 분석에 사용할 사진을 선택하세요.")
                    self.render()
        except queue.Empty:
            pass
        self.poll_id = self.after(80, self.poll_result)

    def destroy(self):
        if hasattr(self, "poll_id"):
            self.after_cancel(self.poll_id)
        super().destroy()

    def render(self):
        self.photos = []
        for canvas, image in zip(self.canvases, (self.source, self.result)):
            canvas.delete("all")
            if image is None:
                continue
            display = image.copy()
            width, height = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
            if not self.actual_size.get():
                display.thumbnail((width, height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(display)
            self.photos.append(photo)
            canvas.create_image(max(0, (width-display.width)//2), max(0, (height-display.height)//2), image=photo, anchor="nw")
            canvas.configure(scrollregion=(0, 0, max(width, display.width), max(height, display.height)))

    def choose(self, corrected):
        if corrected and (self.result is None or self.apply_button.instate(["disabled"])):
            return
        self.on_select(self.result if corrected else None, self.options())
        self.destroy()
