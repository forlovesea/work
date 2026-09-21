import hashlib
import json
from dataclasses import asdict

import streamlit as st

from photoword.core import analyze, check_engine, load_image, Page, preview
from photoword.document import build_docx

st.set_page_config(page_title="사진 → Word", page_icon="📄", layout="wide")
st.title("사진을 편집 가능한 Word 문서로")
st.caption("1 사진 추가  →  2 내용 분석  →  3 추천 형식 또는 직접 선택  →  4 저장")
with st.sidebar:
    st.header("변환 설정")
    language = st.selectbox("인식 언어", ["kor+eng", "eng", "kor"])
    mode = st.selectbox("OCR 배치", [3, 6, 11], format_func=lambda x: {3: "자동 문서 분석", 6: "한 덩어리의 텍스트", 11: "흩어진 텍스트"}[x])
    original = st.checkbox("원본 보존 모드 (페이지 전체를 이미지로 삽입)")
    word_layout = st.radio("Word 저장 방식", ["원본 배치 모드 (텍스트 상자)", "일반 텍스트 모드 (텍스트 상자 없음)"])
    font_size_mode = st.radio("Word 폰트 크기", ["현재 상태 유지 (원본 비율)", "모든 글자 동일한 크기"])
    st.caption("원본 보존 모드는 OCR 엔진 없이도 실행됩니다. 글자와 도형은 편집되지 않습니다.")
    if st.button("OCR 설치 확인"):
        try:
            st.success("설치된 언어: " + ", ".join(check_engine(language)))
        except Exception as exc:
            st.error(str(exc))
    st.info("정면에서 촬영한 밝고 선명한 문서가 좋습니다. 복잡한 그림과 표는 이미지로 보존될 수 있습니다.")

uploads = st.file_uploader("사진 선택 · 선택 목록 순서대로 한 장씩 Word 페이지에 배치됩니다", type=["png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp"], accept_multiple_files=True)
signature = hashlib.sha256()
signature.update(f"{language}:{mode}:{original}".encode())
for upload in uploads:
    signature.update(upload.name.encode())
    signature.update(upload.getvalue())
token = signature.hexdigest()
if st.session_state.get("token") != token:
    for key in list(st.session_state):
        if key.startswith("edit_") or key in ("pages", "document"):
            del st.session_state[key]
    st.session_state.token = token

if len(uploads) > 20:
    st.error("한 번에 20장까지 변환할 수 있습니다.")
if st.button("사진 분석", type="primary", disabled=not uploads or len(uploads) > 20):
    st.session_state.pop("pages", None)
    st.session_state.pop("document", None)
    for key in list(st.session_state):
        if key.startswith("edit_"):
            del st.session_state[key]
    try:
        pages = []
        with st.spinner("사진을 분석하고 있습니다…"):
            progress = st.progress(0)
            for i, upload in enumerate(uploads):
                data = upload.getvalue()
                pages.append(Page(load_image(data)) if original else analyze(data, language, mode))
                progress.progress((i+1)/len(uploads))
        st.session_state.pages = pages
    except Exception as exc:
        st.error(f"분석하지 못했습니다: {exc}")

pages = st.session_state.get("pages", [])
if pages:
    for i, page in enumerate(pages):
        with st.expander(f"{i+1}페이지 · {uploads[i].name}", expanded=i == 0):
            left, right = st.columns(2)
            left.image(page.image if original else preview(page), caption="파랑: 텍스트 · 초록: 이미지 · 빨강/주황: 도형 · 보라: 이미지 안의 텍스트")
            for warning in page.warnings:
                right.warning(warning)
            for j, element in enumerate(page.elements):
                if element.kind == "text":
                    value = right.text_input(f"텍스트 {j} · 신뢰도 {element.confidence:.0f}%", value=element.text, key=f"edit_{i}_{j}")
                    if value != element.text:
                        element.text = value
                        st.session_state.pop("document", None)
            if not original:
                right.caption(f"추출 영역: {len(page.elements)}개. 배치는 Word에서 조정할 수 있습니다.")
    if st.button("Word 파일 생성", type="primary"):
        try:
            st.session_state.document = build_docx(
                pages,
                original=original,
                plain_text=word_layout.startswith("일반 텍스트"),
                font_size_mode="uniform" if font_size_mode.startswith("모든") else "preserve",
            )
        except Exception as exc:
            st.error(f"Word 생성 실패: {exc}")
    if "document" in st.session_state:
        st.download_button("📥 Word 다운로드", st.session_state.document, "converted.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    data = [{"page": i+1, "size": list(page.image.size), "warnings": page.warnings, "elements": [asdict(e) for e in page.elements]} for i, page in enumerate(pages)]
    st.download_button("추출 결과 JSON 다운로드", json.dumps(data, ensure_ascii=False, indent=2), "extracted.json", "application/json")
