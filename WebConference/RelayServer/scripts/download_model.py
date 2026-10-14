"""Download the official Korean Vosk model into this project (Python 3.8+)."""
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "vosk-model-small-ko-0.22"
URL = "https://alphacephei.com/vosk/models/" + NAME + ".zip"


def main():
    models = ROOT / "models"
    target = models / NAME
    if (target / "am" / "final.mdl").is_file():
        print("Model already installed:", target)
        return
    models.mkdir(exist_ok=True)
    archive = models / (NAME + ".zip.part")
    print("Downloading official Korean speech model:", URL, flush=True)
    with urllib.request.urlopen(URL, timeout=60) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            resolved = (models / member.filename).resolve()
            if os.path.commonpath([str(models.resolve()), str(resolved)]) != str(models.resolve()):
                raise ValueError("Unsafe archive path")
        zf.extractall(models)
    archive.unlink()
    if not (target / "am" / "final.mdl").is_file():
        raise RuntimeError("Model extraction did not produce expected files")
    print("Model ready:", target)


if __name__ == "__main__":
    main()
