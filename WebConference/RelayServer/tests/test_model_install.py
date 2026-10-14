import io
import sys
import zipfile

import pytest

from scripts import download_model as download


def archive(traversal=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as zf:
        for name in download.REQUIRED:
            zf.writestr(download.NAME + "/" + name, b"model-test")
        if traversal:
            zf.writestr("../outside.txt", b"unsafe")
    return stream.getvalue()


def test_custom_model_directory_repairs_partial_install(monkeypatch, tmp_path):
    destination = tmp_path / "state" / "models"
    partial = destination / download.NAME / "am" / "final.mdl"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"partial")
    monkeypatch.setattr(sys, "argv", ["download_model", "--models-dir", str(destination)])
    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(archive()))
    download.main()
    assert download.complete_model(destination / download.NAME)
    assert partial.read_bytes() == b"model-test"
    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *a, **k: pytest.fail("Already installed"))
    download.main()


def test_model_archive_cannot_escape_destination(monkeypatch, tmp_path):
    destination = tmp_path / "models"
    monkeypatch.setattr(sys, "argv", ["download_model", "--models-dir", str(destination)])
    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(archive(True)))
    with pytest.raises(ValueError, match="Unsafe archive path"):
        download.main()
    assert not (tmp_path / "outside.txt").exists()
