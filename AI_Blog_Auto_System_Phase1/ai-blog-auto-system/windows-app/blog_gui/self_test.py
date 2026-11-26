"""Offline frozen-EXE smoke; writes only below an explicitly provided directory."""
import json
import zipfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from .storage import Store, Settings
from .services import Services
from .manual import ManualHandoff, AUTO_PUBLISH_ENABLED
from .window import MainWindow
from .workflow import VERSION, author_locally
from .chatgpt import ChatGPT


def run(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    class EmptyVault:
        def __init__(self):
            self.values = {}
        def get(self, name):
            return self.values.get(name, "")
        def set(self, name, value):
            self.values[name] = value
    app = QApplication.instance() or QApplication([])
    store = Store(directory / "desktop")
    config = Settings(initialized=True)
    store.save_settings(config)
    service = Services(store)
    session = ChatGPT(Store(directory / "credential-smoke"), EmptyVault())
    session.save({"accounts": {}, "active": "", "test": "frozen-encryption-check"})
    assert session.records()["test"] == "frozen-encryption-check"
    assert b"frozen-encryption-check" not in session.path.read_bytes()
    automatic = author_locally(service, Settings(scheduled_image=True), "")
    assert Path(automatic["path"]).is_file()
    assert len(automatic["article"]["images"]) == 1
    article = service.write_article(config, "", "EXE 통합 시험")
    image = service.generate_image(config, "", "EXE image")
    article["images"] = [{**image, "id": "test", "caption": "EXE image"}]
    store.save_article(article)
    path = ManualHandoff(service).prepare(config, article, failed=True)
    with zipfile.ZipFile(path) as archive:
        assert {"index.html", "article.docx", "article.txt", "manifest.json"} <= set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        assert len(manifest["image_order"]) == 1
    window = MainWindow(store, EmptyVault())
    window.nav.setCurrentRow(1)
    window.show()
    app.processEvents()
    window.grab().save(str(directory / "settings.png"))
    window.display_article(article)
    window.login_state.setCurrentText("만료")
    window.record_login()
    assert store.get("naver_status")["state"] == "만료"
    window.close()
    app.processEvents()
    assert not AUTO_PUBLISH_ENABLED
    (directory / "result.json").write_text(json.dumps({"passed": True, "version": VERSION,
        "checks": ["encrypted ChatGPT credential roundtrip (test-only vault)", "local automatic authoring without server", "automatic image attachment and ZIP", "Qt GUI initialization", "Mock article/image", "DOCX/ZIP/manifest", "login recording", "auto publish disabled"]}, indent=2), encoding="utf-8")
    return 0
