"""Explainable, deterministic format recommendations and ruled-table extraction."""
from dataclasses import dataclass

import cv2
import numpy as np

from .core import Page


@dataclass
class Table:
    box: tuple[int, int, int, int]
    cells: list[list[str]]


@dataclass
class Recommendation:
    format: str
    reason: str


def text_elements(page):
    return sorted((e for e in page.elements if e.kind in ("text", "embedded_text")),
                  key=lambda e: (e.box[1], e.box[0]))


def _centers(indices):
    groups = []
    for value in indices:
        if not groups or value > groups[-1][-1]+2:
            groups.append([int(value)])
        else:
            groups[-1].append(int(value))
    return [round(sum(g)/len(g)) for g in groups]


def detect_tables(page: Page) -> list[Table]:
    gray = cv2.cvtColor(np.array(page.image), cv2.COLOR_RGB2GRAY)
    ink = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)[1]
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                  np.ones((1, max(30, page.image.width//25)), np.uint8))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                np.ones((max(30, page.image.height//35), 1), np.uint8))
    grid = cv2.bitwise_or(horizontal, vertical)
    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tables = []
    for contour in sorted(contours, key=lambda c: cv2.boundingRect(c)[1]):
        x, y, w, h = cv2.boundingRect(contour)
        if w < 80 or h < 60:
            continue
        xs = _centers(np.where(np.count_nonzero(vertical[y:y+h, x:x+w], axis=0) > h*0.75)[0])
        ys = _centers(np.where(np.count_nonzero(horizontal[y:y+h, x:x+w], axis=1) > w*0.75)[0])
        if not (3 <= len(xs) <= 31 and 3 <= len(ys) <= 61):
            continue
        # Only fully ruled rectangular grids; merged/broken cells are not inferred.
        intersections = sum(bool(grid[max(y+yy-2,0):y+yy+3, max(x+xx-2,0):x+xx+3].any())
                            for yy in ys for xx in xs)
        if intersections < len(xs)*len(ys)*0.9:
            continue
        buckets = [[[] for _ in xs[:-1]] for _ in ys[:-1]]
        for word in page.words or text_elements(page):
            wx, wy, ww, wh = word.box
            cx, cy = wx+ww/2-x, wy+wh/2-y
            col, row = int(np.searchsorted(xs, cx)-1), int(np.searchsorted(ys, cy)-1)
            if xs[0] < cx < xs[-1] and ys[0] < cy < ys[-1]:
                buckets[row][col].append(word)
        cells = [[" ".join(e.text for e in sorted(cell, key=lambda e: (round(e.box[1]/10), e.box[0])))
                  for cell in row] for row in buckets]
        tables.append(Table((x,y,w,h), cells))
    return tables


def recommend(pages: list[Page], tables=None) -> list[Recommendation]:
    if not pages:
        return []
    tables = tables if tables is not None else [detect_tables(p) for p in pages]
    if not all(page.ocr_available for page in pages):
        return [Recommendation("pdf", "OCR을 사용할 수 없어 사진 모양을 보존하는 PDF가 가장 적합합니다."),
                Recommendation("pptx", "사진을 슬라이드별로 배치해 설명이나 발표 자료를 만들 수 있습니다."),
                Recommendation("docx", "사진을 페이지별로 담고 Word에서 설명을 추가할 수 있습니다.")]
    texts = [e for p in pages for e in text_elements(p)]
    chars = sum(len(e.text) for e in texts)
    area = sum(p.image.width*p.image.height for p in pages)
    table_area = sum(t.box[2]*t.box[3] for group in tables for t in group)
    shapes = sum(e.kind in ("rect", "oval") for p in pages for e in p.elements)
    landscape = sum(p.image.width > p.image.height*1.15 for p in pages) > len(pages)/2
    if any(tables) and table_area/area > 0.12:
        return [Recommendation("xlsx", "행·열 구분선이 있는 표가 검출되어 셀 단위 검토에 적합합니다."),
                Recommendation("docx", "표와 주변 설명을 문서 형태로 함께 정리할 수 있습니다."),
                Recommendation("pdf", "표의 원래 배치를 그대로 보존해 공유할 수 있습니다.")]
    if chars > 0 and (shapes >= 2*len(pages) or landscape):
        return [Recommendation("pptx", "가로 배치 또는 여러 도형이 있어 슬라이드 편집에 적합합니다."),
                Recommendation("docx", "텍스트와 그림을 페이지에 재배치하여 문서로 편집할 수 있습니다."),
                Recommendation("pdf", "사진의 원래 모양을 유지해 공유할 수 있습니다.")]
    if chars >= 60:
        return [Recommendation("docx", "읽을 수 있는 본문 텍스트가 많아 문서 편집에 적합합니다."),
                Recommendation("txt", "인식한 글자만 추출하여 검색하거나 다른 프로그램에 붙여 넣을 수 있습니다."),
                Recommendation("pdf", "원본 모양을 보존한 배포용 문서로 적합합니다.")]
    return [Recommendation("pdf", "글자보다 시각 자료 중심이므로 원본 모습 보존을 우선합니다."),
            Recommendation("pptx", "이미지를 슬라이드에 배치하여 발표 자료로 사용할 수 있습니다."),
            Recommendation("docx", "이미지와 추출된 텍스트를 문서에 넣어 편집할 수 있습니다.")]
