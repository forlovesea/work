import json
import sys
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

project = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(project))
from desktop import PhotoDocumentApp
from photoword.core import check_engine
from photoword.exporters import FORMATS, save_export
from photoword.insights import text_elements

output = project / 'samples' / 'korean_ocr_verified'
output.mkdir(parents=True, exist_ok=True)
lines = ['한국어 문서 변환 테스트', '사진에서 글자를 추출합니다.', '이름: 홍길동   수량: 12개', 'English OCR Test 12345']
image = Image.new('RGB', (1200, 430), 'white')
draw = ImageDraw.Draw(image)
font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 42)
for index, line in enumerate(lines):
    draw.text((70, 50+index*80), line, fill='black', font=font)
image_path = output/'korean_sample.png'
image.save(image_path)

root = tk.Tk()
root.withdraw()
app = PhotoDocumentApp(root)
languages = check_engine('kor+eng')
app.paths = [image_path]
app.refresh_files()
errors = []
with patch('desktop.messagebox.showerror', side_effect=lambda *args: errors.append(args)):
    app.start_analysis()
    deadline = time.monotonic()+150
    while app.busy and time.monotonic() < deadline:
        root.update()
        time.sleep(0.05)
assert not app.busy and not errors, errors
assert app.pages and all(page.ocr_available for page in app.pages)
recognized = '\n'.join(e.text for page in app.pages for e in text_elements(page))
compact = ''.join(recognized.split())
for phrase in ('한국어 문서 변환 테스트', '사진에서 글자를', '홍길동', '12345'):
    assert ''.join(phrase.split()) in compact, (phrase, recognized)
for format in FORMATS:
    save_export(output/f'korean_result.{format}', app.pages, format, tables=app.tables)
report = {
    'status': 'passed', 'languages': languages, 'expected': lines,
    'recognized': recognized, 'formats': list(FORMATS),
    'recommendations': [item.format for item in app.recommendations],
    'note': 'Actual Tesseract Korean/English OCR through desktop analysis worker; clean synthetic sample only. Compare expected and recognized text for recognition errors.'
}
(output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
root.destroy()
