from __future__ import annotations

import io
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageDraw, ImageOps

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 24_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
SYMBOL_ONLY = re.compile(r"^(?:\*{2,}|-{3,}|_{3,}|={3,}|\.{3,}|#{2,})$")


def normalize_masked_card_text(text: str) -> str:
    label = re.search(r"카\s*드\s*번\s*호", text)
    if not label:
        return text
    original_tail = text[label.end():]
    tail = re.sub(r"\s+", "", original_tail)
    match = re.search(r"(\d{4})-([^-]{2,})-([^-]{2,})-([^-]{2,})", tail)
    if not match:
        return text
    groups = [match.group(index) for index in range(1, 5)]
    normalized_groups = []
    for group_index, group in enumerate(groups):
        normalized = "".join(character if character.isdigit() else "*" for character in group)
        normalized_groups.append(normalized if group_index == 0 else normalized[:4].ljust(4, "*"))
    masked = "-".join(normalized_groups)
    delimiter = re.match(r"\s*[\]\[:：]*\s*", original_tail).group()
    return text[:label.start()] + "카드번호" + delimiter + masked


@dataclass
class Element:
    kind: str
    box: tuple[int, int, int, int]
    text: str = ""
    confidence: float = 0
    color: str = "000000"
    fill: str | None = None


@dataclass
class Page:
    image: Image.Image
    elements: list[Element] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    words: list[Element] = field(default_factory=list)
    ocr_available: bool = True


def load_image(data: bytes) -> Image.Image:
    if len(data) > MAX_BYTES:
        raise ValueError("사진 한 장은 20MB 이하여야 합니다.")
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > MAX_PIXELS:
            raise ValueError("사진은 2,400만 화소 이하여야 합니다.")
        if getattr(source, "n_frames", 1) != 1:
            raise ValueError("여러 프레임이 있는 파일은 페이지별 사진으로 분리해 주세요.")
        im = ImageOps.exif_transpose(source).convert("RGBA")
        canvas = Image.new("RGBA", im.size, "white")
        canvas.alpha_composite(im)
        im = canvas.convert("RGB")
        im.thumbnail((2400, 3200))
        return im


def check_engine(language: str = "kor+eng") -> list[str]:
    configured = os.environ.get("TESSERACT_CMD")
    executable = configured or shutil.which("tesseract")
    if not executable:
        for root in (os.environ.get("ProgramFiles", "C:/Program Files"),
                     str(Path.home() / "AppData/Local/Programs")):
            candidate = Path(root) / "Tesseract-OCR/tesseract.exe"
            if candidate.is_file():
                executable = str(candidate)
                break
    if not executable:
        raise RuntimeError("Tesseract OCR이 없습니다. README의 설치 절차를 진행해 주세요.")
    pytesseract.pytesseract.tesseract_cmd = executable
    try:
        languages = pytesseract.get_languages(config="")
    except Exception as exc:
        raise RuntimeError("Tesseract 실행 경로 또는 tessdata 설정을 확인해 주세요.") from exc
    missing = set(language.split("+")) - set(languages)
    if missing:
        raise RuntimeError(f"OCR 언어 데이터가 없습니다: {', '.join(sorted(missing))}. README를 확인해 주세요.")
    return languages


def extract_text(im: Image.Image, language: str, psm: int, word_sink=None) -> list[Element]:
    data = pytesseract.image_to_data(im, lang=language, config=f"--psm {psm}",
                                     output_type=pytesseract.Output.DICT, timeout=120)
    groups: dict[tuple, list] = {}
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        confidence = max(0, float(data["conf"][i]))
        if word_sink is not None:
            word_sink.append(Element("word", tuple(int(data[k][i]) for k in
                                     ("left", "top", "width", "height")),
                                     word.strip(), confidence))
        key = tuple(data[k][i] for k in ("block_num", "par_num", "line_num"))
        groups.setdefault(key, []).append(i)
    elements = []
    for indices in groups.values():
        x = min(data["left"][i] for i in indices)
        y = min(data["top"][i] for i in indices)
        right = max(data["left"][i] + data["width"][i] for i in indices)
        bottom = max(data["top"][i] + data["height"][i] for i in indices)
        elements.append(Element("text", (x, y, right-x, bottom-y),
                    normalize_masked_card_text(" ".join(data["text"][i] for i in indices)),
                                sum(max(0, float(data["conf"][i])) for i in indices)/len(indices)))
    # Some Tesseract language models omit masked-card symbols such as ***.
    # A restricted second pass recovers repeated punctuation without changing normal OCR.
    try:
        symbol_data = pytesseract.image_to_data(
            im,
            lang=language,
            config=f"--psm {psm} -c tessedit_char_whitelist=*-_=.#",
            output_type=pytesseract.Output.DICT,
            timeout=120,
        )
    except Exception:
        symbol_data = None
    if symbol_data:
        for i, value in enumerate(symbol_data["text"]):
            symbol = value.strip()
            if not SYMBOL_ONLY.fullmatch(symbol):
                continue
            box = tuple(int(symbol_data[key][i]) for key in ("left", "top", "width", "height"))
            if any(abs(box[0] - item.box[0]) <= 3 and abs(box[1] - item.box[1]) <= 3 for item in elements):
                continue
            confidence = max(0, float(symbol_data["conf"][i]))
            element = Element("text", box, symbol, confidence)
            elements.append(element)
            if word_sink is not None:
                word_sink.append(Element("word", box, symbol, confidence))
    return sorted(elements, key=lambda item: (item.box[1], item.box[0]))


def visual_elements(im: Image.Image, texts: list[Element]) -> list[Element]:
    rgb = np.array(im)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # Mask only OCR lines; retain surrounding diagram outlines.
    mask = cv2.threshold(gray, 235, 255, cv2.THRESH_BINARY_INV)[1]
    for element in texts:
        x, y, w, h = element.box
        mask[max(0, y-2):y+h+2, max(0, x-2):x+w+2] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    result = []
    total = im.width * im.height
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if w*h < max(100, total*0.00015) or (w < 5 and h < 5):
            continue
        # Avoid converting an entire page border into a photo covering all text.
        if w*h > total*0.95 and np.count_nonzero(mask[y:y+h, x:x+w])/(w*h) < 0.05:
            continue
        approx = cv2.approxPolyDP(contour, 0.015*cv2.arcLength(contour, True), True)
        inner = rgb[y+max(1,h//5):y+max(2,4*h//5), x+max(1,w//5):x+max(2,4*w//5)]
        spread = float(np.std(inner.reshape(-1, 3), axis=0).max()) if inner.size else 255
        # Exclude OCR pixels when determining if a shape has a uniform fill.
        patch = rgb[y:y+h, x:x+w]
        inner_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(inner_mask, [contour - np.array([[[x, y]]])], -1, 255, -1)
        inset = max(5, round(min(w, h)*0.06))
        inner_mask = cv2.erode(inner_mask, np.ones((2*inset+1, 2*inset+1), np.uint8),
                               borderType=cv2.BORDER_CONSTANT, borderValue=0)
        for t in texts:
            tx, ty, tw, th = t.box
            x0, y0 = max(0, tx-x-2), max(0, ty-y-2)
            x1, y1 = min(w, tx+tw-x+2), min(h, ty+th-y+2)
            if x1 > x0 and y1 > y0:
                inner_mask[y0:y1, x0:x1] = 0
        samples = patch[inner_mask > 0]
        if len(samples):
            spread = float(np.std(samples, axis=0).max())
        kind = "image"
        if spread < 18 and w > 15 and h > 15:
            if len(approx) == 4 and area/(w*h) > 0.87:
                kind = "rect"
            elif len(contour) >= 5:
                (_, _), (ew, eh), _ = cv2.fitEllipse(contour)
                if ew*eh > 0 and abs(area/(np.pi*ew*eh/4)-1) < 0.12 and 0.65 < area/(w*h) < 0.86:
                    kind = "oval"
        border = patch[mask[y:y+h, x:x+w] > 0]
        color = "000000" if not len(border) else "%02X%02X%02X" % tuple(np.percentile(border, 20, axis=0).astype(int))
        fill = None if not len(samples) else "%02X%02X%02X" % tuple(np.median(samples, axis=0).astype(int))
        result.append(Element(kind, (x, y, w, h), color=color, fill=fill))
    # For complex diagrams/photos containing text, preserve the crop and suppress
    # overlapping OCR later, preventing doubled text in the reconstructed page.
    return sorted(result, key=lambda e: (e.box[1], e.box[0]))


def analyze(data: bytes, language: str = "kor+eng", psm: int = 3, *, prepared_image: Image.Image | None = None) -> Page:
    check_engine(language)
    im = prepared_image.copy() if prepared_image is not None else load_image(data)
    words = []
    texts = extract_text(im, language, psm, word_sink=words)
    visuals = visual_elements(im, texts)
    warnings = []
    if not texts:
        warnings.append("텍스트가 검출되지 않았습니다. 언어 또는 OCR 모드를 확인해 주세요.")
        if not visuals:
            visuals = [Element("image", (0, 0, *im.size))]
    for text in texts:
        x, y, w, h = text.box
        for visual in visuals:
            vx, vy, vw, vh = visual.box
            if visual.kind == "image" and vx <= x and vy <= y and vx+vw >= x+w and vy+vh >= y+h:
                text.kind = "embedded_text"
                break
    if any(t.kind == "embedded_text" for t in texts):
        warnings.append("복잡한 이미지 내부의 글자는 이미지로 보존됩니다. 추출 JSON에는 텍스트가 포함됩니다.")
    if any(t.confidence < 65 for t in texts):
        warnings.append("신뢰도가 낮은 텍스트가 있습니다. 변환 전에 교정해 주세요.")
    return Page(im, visuals + texts, warnings, words)


def preview(page: Page) -> Image.Image:
    im = page.image.copy()
    draw = ImageDraw.Draw(im)
    colors = {"text": "blue", "embedded_text": "purple", "image": "green", "rect": "red", "oval": "orange"}
    for i, e in enumerate(page.elements):
        x, y, w, h = e.box
        draw.rectangle((x, y, x+w, y+h), outline=colors[e.kind], width=2)
        draw.text((x, max(0, y-12)), f"{i}: {e.kind}", fill=colors[e.kind])
    return im
