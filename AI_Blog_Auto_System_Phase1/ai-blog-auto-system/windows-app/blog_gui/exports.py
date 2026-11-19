"""One ordered content model for HTML, CF_HTML, TXT, DOCX and ZIP."""
import base64
import hashlib
import html
import io
import json
import os
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

from .services import ServiceError, web_url
from .storage import utcnow

MAX_IMAGES = 30
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 80 * 1024 * 1024
MAX_PIXELS = 24_000_000


def png_bytes(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
        raise ServiceError("이미지 파일이 없거나 20 MiB 제한을 초과합니다.")
    try:
        with Image.open(path) as image:
            if image.format not in {"PNG", "JPEG", "WEBP", "BMP"}:
                raise ServiceError("PNG/JPEG/WebP/BMP 이미지만 사용할 수 있습니다.")
            if image.width * image.height > MAX_PIXELS:
                raise ServiceError("이미지는 2,400만 픽셀 이하여야 합니다.")
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            output = io.BytesIO()
            image.save(output, "PNG")  # Strip EXIF and other unrelated metadata.
            data = output.getvalue()
            if len(data) > MAX_IMAGE_BYTES:
                raise ServiceError("변환된 이미지가 20 MiB 제한을 초과합니다.")
            return data, image.size
    except ServiceError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ServiceError("지원되는 이미지 파일을 읽을 수 없습니다.") from None


def import_image(path, directory, caption="", disclosure="사용자 제공 이미지"):
    data, _ = png_bytes(path)
    directory = Path(directory) / "images"
    directory.mkdir(parents=True, exist_ok=True)
    image_id = str(uuid.uuid4())
    target = directory / f"{image_id}.png"
    target.write_bytes(data)
    return {"id": image_id, "path": str(target), "caption": caption or Path(path).stem,
            "disclosure": disclosure}


@dataclass(frozen=True)
class Asset:
    image_id: str
    name: str
    caption: str
    disclosure: str
    data: bytes
    width: int
    height: int


class Publication:
    def __init__(self, article):
        # Snapshot only public content; no store settings, tokens, or absolute paths in exports.
        self.article = article
        entries = article.get("images", [])
        if len(entries) > MAX_IMAGES:
            raise ServiceError("글 하나에 이미지는 최대 30개입니다.")
        self.assets = []
        size = 0
        for i, entry in enumerate(entries):
            data, dimensions = png_bytes(entry["path"])
            size += len(data)
            if size > MAX_TOTAL_BYTES:
                raise ServiceError("이미지 합계가 80 MiB 제한을 초과합니다.")
            name = "images/thumbnail.png" if i == 0 else f"images/body_{i:02d}.png"
            self.assets.append(Asset(entry["id"], name, entry.get("caption", ""), entry.get("disclosure", ""), data, *dimensions))
        if len({a.image_id for a in self.assets}) != len(self.assets):
            raise ServiceError("이미지 ID가 중복되었습니다.")

    def blocks(self):
        a = self.article
        yield "title", a["title"]
        yield "paragraph", "MOCK 테스트 초안" if a.get("mock") else "AI 작성 초안 · 검토 필요"
        yield "paragraph", a["summary"]
        if self.assets:
            yield "image", self.assets[0]
        sections = a["sections"]
        for i, section in enumerate(sections):
            yield "heading", section["heading"]
            yield "paragraph", section["body"]
            if i + 1 < len(self.assets):
                yield "image", self.assets[i+1]
        for asset in self.assets[len(sections)+1:]:
            yield "image", asset
        yield "paragraph", "태그: " + ", ".join(a.get("tags", []))
        yield "paragraph", "SEO: " + ", ".join(a.get("seo_keywords", []))
        yield "heading", "출처"
        for source in a.get("sources", []):
            yield "source", source
        yield "paragraph", "작성 시각: " + a["created_at"]

    def text(self):
        result = []
        for kind, value in self.blocks():
            if kind == "image":
                result.append(f"[이미지 {value.name}] {value.caption}\n{value.disclosure}")
            elif kind == "source":
                result.append(value["title"] + " — " + (value["url"] if web_url(value["url"]) else "유효하지 않은 출처 URL"))
            else:
                result.append(value)
        return "\n\n".join(result)

    def fragment(self, embed_images=True):
        parts = ['<div style="font-family:Malgun Gothic,sans-serif;color:#17283f;line-height:1.65;">']
        for kind, value in self.blocks():
            if kind == "image":
                src = "data:image/png;base64," + base64.b64encode(value.data).decode("ascii") if embed_images else value.name
                width = min(value.width, 680)
                height = max(1, round(value.height * width / value.width))
                parts.append(f'<p data-image-id="{html.escape(value.image_id, quote=True)}"><img src="{src}" '
                             f'width="{width}" height="{height}" alt="{html.escape(value.caption, quote=True)}" '
                             'style="max-width:100%;height:auto;"></p>')
                parts.append('<p style="font-size:10pt;color:#526170;">' + html.escape(value.caption) + '<br>' + html.escape(value.disclosure) + '</p>')
            elif kind == "source":
                title = html.escape(value["title"])
                url = value["url"]
                parts.append(f'<p><a href="{html.escape(url, quote=True)}">{title}</a></p>' if web_url(url) else f'<p>{title} (URL 제외)</p>')
            else:
                tag = {"title": "h1", "heading": "h2"}.get(kind, "p")
                parts.append(f'<{tag}>' + html.escape(value).replace("\n", "<br>") + f'</{tag}>')
        parts.append("</div>")
        return "\n".join(parts)

    def html(self, embed_images=True):
        return ('<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' data:; style-src \'unsafe-inline\';">'
                '<title>' + html.escape(self.article["title"]) + '</title>'
                '<style>body{max-width:760px;margin:32px auto;padding:0 20px;background:white}h1,h2{color:black}</style>'
                '</head><body>' + self.fragment(embed_images) + '</body></html>')

    def docx(self):
        doc = Document()
        section = doc.sections[0]
        section.page_width, section.page_height = Cm(21), Cm(29.7)
        section.top_margin = section.bottom_margin = Cm(2)
        section.left_margin = section.right_margin = Cm(2.2)
        for border in list(doc.styles.element.iter(qn("w:pBdr"))):
            border.getparent().remove(border)
        for name in ("Normal", "Title", "Heading 1", "Caption"):
            style = doc.styles[name]
            style.font.name = "Malgun Gothic"
            style.font.color.rgb = RGBColor(0, 0, 0)
            style._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "맑은 고딕")
        doc.styles["Normal"].font.size = Pt(11)
        doc.styles["Normal"].paragraph_format.space_after = Pt(8)
        doc.styles["Normal"].paragraph_format.line_spacing = 1.15
        doc.styles["Title"].font.size = Pt(23)
        doc.styles["Heading 1"].font.size = Pt(15)
        doc.styles["Caption"].font.size = Pt(9)
        doc.core_properties.author = "AI Blog Auto System"
        doc.core_properties.title = self.article["title"]
        for kind, value in self.blocks():
            if kind == "title":
                doc.add_paragraph(value, "Title")
            elif kind == "heading":
                doc.add_paragraph(value, "Heading 1")
            elif kind == "image":
                width = min(6.0, value.width / 110, 3.8 * value.width / value.height)
                p = doc.add_paragraph()
                p.paragraph_format.keep_with_next = True
                shape = p.add_run().add_picture(io.BytesIO(value.data), width=Inches(width))
                shape._inline.docPr.set("descr", value.caption)
                shape._inline.docPr.set("name", value.name)
                doc.add_paragraph(value.caption + ("\n" + value.disclosure if value.disclosure else ""), "Caption")
            elif kind == "source":
                doc.add_paragraph(value["title"] + " — " + (value["url"] if web_url(value["url"]) else "URL 제외"))
            else:
                doc.add_paragraph(value)
        output = io.BytesIO()
        doc.save(output)
        return output.getvalue()

    def package(self):
        files = {"index.html": self.html(False).encode("utf-8"), "article.txt": self.text().encode("utf-8"), "article.docx": self.docx()}
        files.update({a.name: a.data for a in self.assets})
        manifest = {
            "format_version": "1.0", "content_id": self.article["id"], "title": self.article["title"],
            "created_at": self.article["created_at"], "packaged_at": utcnow(),
            "image_order": [a.name for a in self.assets],
            "images": [{"id": a.image_id, "path": a.name, "caption": a.caption, "disclosure": a.disclosure,
                        "position": "thumbnail" if i == 0 else f"after_section_{min(i, len(self.article['sections']))}",
                        "sha256": hashlib.sha256(a.data).hexdigest()} for i, a in enumerate(self.assets)],
            "files": [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in files.items()],
        }
        # manifest cannot hash itself; ZIP checksum belongs to a future upload envelope.
        files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        return output.getvalue()


def atomic_write(path, data):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".blog-export-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def cf_html(fragment):
    """Offsets count UTF-8 bytes from the beginning of the CF_HTML buffer."""
    template = "Version:1.0\r\nStartHTML:{:010d}\r\nEndHTML:{:010d}\r\nStartFragment:{:010d}\r\nEndFragment:{:010d}\r\n"
    placeholder = template.format(0, 0, 0, 0).encode("ascii")
    prefix = '<html><head><meta charset="utf-8"></head><body><!--StartFragment-->'.encode("utf-8")
    content = fragment.encode("utf-8")
    suffix = b"<!--EndFragment--></body></html>"
    start = len(placeholder)
    fragment_start = start + len(prefix)
    fragment_end = fragment_start + len(content)
    end = fragment_end + len(suffix)
    return template.format(start, end, fragment_start, fragment_end).encode("ascii") + prefix + content + suffix
