"""Windows CF_HTML round-trip plus portable export smoke test.

This intentionally places a generated test article on the system clipboard.
No Naver/browser access or external API requests are made.
"""
import ctypes
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "windows-app"))

from PIL import Image, ImageDraw
from blog_gui.clipboard import copy_windows, windows_api
from blog_gui.exports import Publication, import_image, atomic_write, cf_html


def main():
    directory = ROOT / ".pytest-tmp" / "exports-qa"
    directory.mkdir(parents=True, exist_ok=True)
    article = {"id": "00000000-0000-4000-8000-000000000003", "title": "이미지 순서 검증 문서",
               "created_at": "2026-11-17T00:00:00+00:00", "mock": True,
               "summary": "제목과 본문, 세 장의 이미지가 같은 순서로 출력되는지 확인하는 테스트 문서입니다.",
               "sections": [{"heading": "첫 번째 본문", "body": "빨간 썸네일 다음에는 첫 번째 본문과 초록 이미지가 배치됩니다."},
                            {"heading": "두 번째 본문", "body": "두 번째 본문 다음에는 파란 이미지가 배치됩니다."}],
               "tags": ["출력", "테스트"], "seo_keywords": ["이미지 순서"],
               "sources": [{"title": "테스트용 출처", "url": "https://example.com/"}], "images": []}
    for i, color in enumerate(["#d95656", "#298a61", "#356bb1"]):
        path = directory / f"source-{i}.png"
        image = Image.new("RGB", (800, 240), color)
        ImageDraw.Draw(image).text((30, 70), f"IMAGE {i + 1}", fill="white", font_size=50)
        image.save(path)
        article["images"].append(import_image(path, directory, f"이미지 {i+1}", "검증용 테스트 이미지"))
    publication = Publication(article)
    atomic_write(directory / "sample.html", publication.html().encode("utf-8"))
    atomic_write(directory / "sample.docx", publication.docx())
    atomic_write(directory / "sample.zip", publication.package())
    copy_windows(publication)
    user, kernel = windows_api()
    if not user.OpenClipboard(None):
        raise RuntimeError("Cannot read clipboard after write")
    try:
        def read(fmt):
            handle = user.GetClipboardData(fmt)
            assert handle, "Missing clipboard format"
            pointer = kernel.GlobalLock(handle)
            assert pointer
            try:
                return ctypes.string_at(pointer, kernel.GlobalSize(handle))
            finally:
                kernel.GlobalUnlock(handle)
        raw = read(user.RegisterClipboardFormatW("HTML Format"))
        end = int(re.search(rb"EndHTML:(\d+)", raw)[1])
        assert raw[:end] == cf_html(publication.fragment())
        assert read(13).decode("utf-16-le").rstrip("\0") == publication.text()
        assert read(user.RegisterClipboardFormatW("text/html")).rstrip(b"\0").decode() == publication.html()
        assert read(user.RegisterClipboardFormatW("text/plain")).rstrip(b"\0").decode() == publication.text()
        assert read(user.RegisterClipboardFormatW("PNG"))[:len(publication.assets[0].data)] == publication.assets[0].data
        assert read(8)  # CF_DIB available as a single-image fallback.
    finally:
        user.CloseClipboard()
    with zipfile.ZipFile(directory / "sample.zip") as archive:
        assert len(json.loads(archive.read("manifest.json"))["image_order"]) == 3
    print("PASS: native Windows HTML Format, Unicode text, text/html, text/plain, PNG and CF_DIB")
    print("PASS: standalone HTML, embedded DOCX and ZIP generated for three ordered images")


if __name__ == "__main__":
    main()
