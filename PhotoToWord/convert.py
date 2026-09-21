"""python convert.py photo1.jpg photo2.png -o output.docx"""
import argparse
from pathlib import Path

from photoword.core import Page, analyze, load_image
from photoword.document import build_docx


def main():
    parser = argparse.ArgumentParser(description="사진을 Word 문서로 변환")
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("output.docx"))
    parser.add_argument("--lang", default="kor+eng")
    parser.add_argument("--psm", type=int, choices=[3, 6, 11], default=3)
    parser.add_argument("--original", action="store_true", help="OCR 없이 원본 이미지를 삽입")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("출력 파일이 이미 존재합니다. 다른 파일 이름을 지정해 주세요.")
    try:
        pages = []
        for path in args.images:
            data = path.read_bytes()
            page = Page(load_image(data)) if args.original else analyze(data, args.lang, args.psm)
            pages.append(page)
            for warning in page.warnings:
                print(f"{path.name}: {warning}")
        result = build_docx(pages, args.original)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            stream.write(result)
        print(f"완료: {args.output.resolve()}")
    except Exception as exc:
        parser.exit(1, f"변환 실패: {exc}\n")


if __name__ == "__main__":
    main()
