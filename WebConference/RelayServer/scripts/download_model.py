"""Download the official Korean Vosk model into this project (Python 3.8+)."""
import argparse
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "vosk-model-small-ko-0.22"
URL = "https://alphacephei.com/vosk/models/" + NAME + ".zip"
REQUIRED = ("am/final.mdl", "conf/model.conf", "conf/mfcc.conf", "graph/HCLr.fst",
            "graph/Gr.fst", "graph/phones/word_boundary.int", "ivector/final.ie")


def complete_model(target):
    return all((target / name).is_file() and (target / name).stat().st_size > 0 for name in REQUIRED)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=ROOT / "models")
    args = parser.parse_args()
    models = args.models_dir.resolve()
    target = models / NAME
    if complete_model(target):
        print("Model already installed:", target)
        return
    models.mkdir(parents=True, exist_ok=True)
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
    if not complete_model(target):
        raise RuntimeError("Model extraction did not produce expected files")
    print("Model ready:", target)


if __name__ == "__main__":
    main()
