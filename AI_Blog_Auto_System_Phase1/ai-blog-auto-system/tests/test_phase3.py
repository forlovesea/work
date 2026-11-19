import base64
import copy
import hashlib
import io
import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PIL import Image
from PySide6.QtCore import QUrl
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication, QFileDialog

from test_phase2 import store, window, click
from blog_gui.exports import Publication, cf_html, import_image, atomic_write
from blog_gui.clipboard import CF_HTML_MIME, mime_data
from blog_gui.services import ServiceError, Services


@pytest.fixture(scope="session", autouse=True)
def release_test_clipboard(qapp):
    # Qt owns QMimeData after setMimeData. Release it while Python and QApplication
    # are alive; retaining a Python-created QMimeData into interpreter teardown can
    # crash PySide's offscreen platform on Windows.
    yield
    qapp.clipboard().clear()
    qapp.processEvents()


class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "img":
            self.sources.append(dict(attrs)["src"])


@pytest.fixture
def article(store, tmp_path):
    result = Services(store).write_article(store.settings(), "", "한글 출력 테스트 🌿")
    result["sections"] = [{"heading": "첫 번째 문단", "body": "첫 번째 본문"}, {"heading": "두 번째 문단", "body": "두 번째 본문"}]
    result["images"] = []
    for index, color in enumerate(["red", "green", "blue", "yellow"]):
        path = tmp_path / f"image-{index}.png"
        Image.new("RGB", (240, 120), color).save(path)
        result["images"].append(import_image(path, store.directory, f"그림 {index} 한글", "테스트 이미지"))
    return result


def docx_image_hashes(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
              "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
        rels = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
        image_rels = {r.attrib["Id"]: r.attrib for r in rels if r.attrib["Type"].endswith("/image")}
        assert all(r.get("TargetMode") != "External" for r in image_rels.values())
        root = ET.fromstring(archive.read("word/document.xml"))
        styles = ET.fromstring(archive.read("word/styles.xml"))
        assert not list(styles.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pBdr"))
        ids = [node.attrib["{" + ns["r"] + "}embed"] for node in root.findall(".//a:blip", ns)]
        return [hashlib.sha256(archive.read("word/" + image_rels[rid]["Target"])).hexdigest() for rid in ids]


@pytest.mark.parametrize("order", [[0, 1, 2, 3], [3, 1, 0, 2]])
def test_image_order_shared_across_html_cfhtml_docx_txt_and_manifest(article, order):
    article["images"] = [article["images"][i] for i in order]
    output = Publication(article)
    expected = [hashlib.sha256(asset.data).hexdigest() for asset in output.assets]
    parser = ImageParser()
    parser.feed(output.html())
    assert [hashlib.sha256(base64.b64decode(src.split(",", 1)[1])).hexdigest() for src in parser.sources] == expected
    raw = cf_html(output.fragment())
    header = dict((key.decode(), int(value)) for key, value in re.findall(rb"(StartHTML|EndHTML|StartFragment|EndFragment):(\d+)", raw))
    assert raw[header["StartFragment"]:header["EndFragment"]].decode("utf-8") == output.fragment()
    assert raw[header["StartHTML"]:header["EndHTML"]].startswith(b"<html>")
    assert header["EndHTML"] == len(raw)
    assert docx_image_hashes(output.docx()) == expected
    text = output.text()
    positions = [text.index("[이미지 " + asset.name + "]") for asset in output.assets]
    assert positions == sorted(positions)
    with zipfile.ZipFile(io.BytesIO(output.package())) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["image_order"] == [a.name for a in output.assets]
        assert [m["id"] for m in manifest["images"]] == [a["id"] for a in article["images"]]
        assert [m["sha256"] for m in manifest["images"]] == expected
        assert docx_image_hashes(archive.read("article.docx")) == expected
        parser = ImageParser()
        parser.feed(archive.read("index.html").decode("utf-8"))
        assert parser.sources == manifest["image_order"]


def test_zip_integrity_portability_and_no_local_paths(article, tmp_path):
    article["api_key"] = "DO-NOT-EXPORT"
    output = Publication(article)
    package = output.package()
    # Export snapshot remains self-contained even after the original image files disappear.
    for entry in article["images"]:
        Path(entry["path"]).unlink()
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        assert set(archive.namelist()) == {"index.html", "article.txt", "article.docx", "manifest.json", *manifest["image_order"]}
        for file in manifest["files"]:
            data = archive.read(file["path"])
            assert len(data) == file["size"] and hashlib.sha256(data).hexdigest() == file["sha256"]
        for name in ("manifest.json", "index.html", "article.txt"):
            data = archive.read(name)
            assert b"DO-NOT-EXPORT" not in data and str(tmp_path).encode() not in data
        assert len(docx_image_hashes(archive.read("article.docx"))) == 4


def test_escape_scripts_urls_and_captions(article):
    article["title"] = '<script>alert("bad")</script>'
    article["sections"][0]["body"] = '<img src="https://evil.test/image" onerror="alert(1)">'
    article["images"][0]["caption"] = '\"><script>bad</script>'
    article["sources"] = [{"title": "bad", "url": "javascript:alert(1)"}]
    content = Publication(article).html()
    parser = ImageParser()
    parser.feed(content)
    assert "script" not in parser.tags
    assert all(src.startswith("data:image/png;base64,") for src in parser.sources)
    assert 'href="javascript:' not in content
    assert "&lt;script&gt;" in content


def test_missing_or_invalid_images_fail_without_partial_output(article, tmp_path):
    Path(article["images"][0]["path"]).write_bytes(b"not an image")
    with pytest.raises(ServiceError):
        Publication(article)
    target = tmp_path / "existing.zip"
    target.write_bytes(b"old")
    with pytest.raises(ServiceError):
        atomic_write(target, Publication(article).package())
    assert target.read_bytes() == b"old"


def test_text_only_exports(article):
    article["images"] = []
    output = Publication(article)
    assert docx_image_hashes(output.docx()) == []
    with zipfile.ZipFile(io.BytesIO(output.package())) as archive:
        assert json.loads(archive.read("manifest.json"))["image_order"] == []


def test_qt_mime_formats_and_preview_blocks_external_resources(qtbot, article, window):
    output = Publication(article)
    mime = mime_data(output)
    assert mime.hasHtml() and mime.hasText() and mime.hasImage()
    assert bytes(mime.data(CF_HTML_MIME)) == cf_html(output.fragment())
    assert bytes(mime.data("image/png")) == output.assets[0].data
    assert window.output_preview.loadResource(QTextDocument.ResourceType.ImageResource, QUrl("https://evil.test/test.png")) is None
    assert window.output_preview.loadResource(QTextDocument.ResourceType.ImageResource, QUrl("file:///C:/secret.png")) is None


def test_output_buttons_persist_order_and_export(qtbot, window, article, tmp_path, monkeypatch):
    window.store.save_article(article)
    window.display_article(article)
    window.nav.setCurrentRow(9)
    window.output_images.setCurrentRow(1)
    original_ids = [i["id"] for i in article["images"]]
    click(qtbot, window, "image_up")
    assert window.article["images"][0]["id"] == original_ids[1]
    click(qtbot, window, "image_down")
    assert [i["id"] for i in window.article["images"]] == original_ids
    window.image_caption.setText("수정된 그림 설명")
    click(qtbot, window, "save_caption")
    assert window.article["images"][1]["caption"] == "수정된 그림 설명"
    click(qtbot, window, "preview_html")
    assert "수정된 그림 설명" in window.output_preview.toPlainText()
    click(qtbot, window, "copy_rich")
    assert QApplication.clipboard().mimeData().hasHtml()
    for kind in ("html", "docx", "zip"):
        path = tmp_path / ("export." + kind)
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, p=path: (str(p), ""))
        click(qtbot, window, "export_package" if kind == "zip" else "export_" + kind)
        assert path.stat().st_size > 0
    click(qtbot, window, "remove_image")
    assert len(window.article["images"]) == 3
    selected_path = article["images"][0]["path"]
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a: ([selected_path], ""))
    click(qtbot, window, "add_image_files")
    assert len(window.article["images"]) == 4
    window.image = {"path": selected_path, "disclosure": "Mock 테스트 이미지", "prompt": "최신 이미지"}
    click(qtbot, window, "add_latest_image")
    assert len(window.article["images"]) == 5
    saved = window.store.articles()[0]
    assert [a["id"] for a in saved["images"]] == [a["id"] for a in window.article["images"]]
    click(qtbot, window, "preview_html")
    qtbot.wait(100)
    screenshot = Path(__file__).resolve().parents[1] / ".pytest-tmp" / "gui-output.png"
    assert window.grab().save(str(screenshot))
