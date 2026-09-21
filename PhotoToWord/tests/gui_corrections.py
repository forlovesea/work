"""Run on an interactive Windows desktop."""
import ctypes
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from PIL import ImageGrab
from desktop import PhotoDocumentApp


ctypes.windll.shcore.SetProcessDpiAwareness(1)
root = tk.Tk()
app = PhotoDocumentApp(root)
path = Path(__file__).resolve().parents[1] / "samples/sample.png"
original_bytes = path.read_bytes()
app.paths = [path]
app.refresh_files()
root.update()


def wait_preview(dialog):
    deadline = time.monotonic() + 20
    while dialog.running and time.monotonic() < deadline:
        root.update()
        time.sleep(0.02)
    assert not dialog.running, "Correction preview timed out"
    assert not dialog.apply_button.instate(["disabled"])


dialog = app.show_corrections()
wait_preview(dialog)
dialog.binary.set(True)
assert dialog.apply_button.instate(["disabled"])
dialog.refresh_preview()
wait_preview(dialog)
selected = dialog.result.copy()
dialog.actual_size.set(True)
dialog.render()
dialog.actual_size.set(False)
dialog.render()
root.update()
output = Path("smoke-output/corrections")
output.mkdir(parents=True, exist_ok=True)
dialog.attributes("-topmost", True)
dialog.lift()
root.update()
time.sleep(0.3)
ImageGrab.grab(bbox=(dialog.winfo_rootx(), dialog.winfo_rooty(),
                     dialog.winfo_rootx()+dialog.winfo_width(), dialog.winfo_rooty()+dialog.winfo_height())).save(output / "comparison.png")
dialog.choose(True)
assert path in app.corrections
assert app.analysis_image(path).tobytes() == selected.tobytes()
assert not app.pages and app.save_button.instate(["disabled"])
with patch("desktop.check_engine", side_effect=RuntimeError("OCR unavailable")):
    app._analyze_worker([path], "eng")
assert app.events.get_nowait()[0] == "progress"
event, payload = app.events.get_nowait()
assert event == "analysis"
assert payload[0][0].image.tobytes() == selected.tobytes()
with patch("desktop.check_engine"), patch("desktop.analyze", return_value=payload[0][0]) as analyze:
    app._analyze_worker([path], "eng")
    assert analyze.call_args.kwargs["prepared_image"].tobytes() == selected.tobytes()
dialog = app.show_corrections()
dialog.destroy()
assert path in app.corrections, "Cancel must preserve previous choice"
dialog = app.show_corrections()
dialog.choose(False)
assert path not in app.corrections
assert path.read_bytes() == original_bytes
root.destroy()
print("Correction preview, stale-option protection, selection, OCR/fallback input, cancel, restore: OK")
