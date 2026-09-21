"""Run separately on an interactive Windows desktop: python tests/gui_flow.py."""
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from desktop import PhotoDocumentApp
from photoword.exporters import FORMATS

root = tk.Tk()
root.withdraw()
app = PhotoDocumentApp(root)
app.paths = [Path(__file__).resolve().parents[1]/"samples/sample.png"]
app.refresh_files()
app.selection_mode.set("manual")
app.manual_format.set(FORMATS["xlsx"][0])
errors = []
with patch("desktop.check_engine",side_effect=RuntimeError("Test: OCR unavailable")), patch("desktop.messagebox.showerror",side_effect=lambda *args: errors.append(args)):
    app.start_analysis()
    deadline = time.monotonic()+15
    while app.busy and time.monotonic()<deadline:
        root.update()
        time.sleep(0.02)
assert not app.busy and not errors, errors
assert app.pages and not app.pages[0].ocr_available
assert app.recommendations[0].format == "pdf"
assert app.selected_format() == "xlsx", "Manual selection must survive recommendation updates"
app.language.set("eng")
app.invalidate()
assert not app.pages and app.save_button.instate(["disabled"])
app.cancel_event.set()
with patch("desktop.check_engine",side_effect=RuntimeError("Test: OCR unavailable")):
    app._analyze_worker(app.paths,"eng")
assert app.events.get_nowait()[0] == "cancelled"
root.destroy()
print("GUI worker, fallback, manual override, invalidation and cancellation: OK")
