"""Package local build outputs and a source-only Ubuntu release; never deploy."""
import hashlib
import json
import shutil
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "build" / "deliverables"
    output.mkdir(parents=True, exist_ok=True)
    desktop = ROOT / "dist" / "AI-Blog-Auto"
    if not (desktop / "AI-Blog-Auto.exe").is_file():
        raise RuntimeError("Build the Windows EXE first")
    with zipfile.ZipFile(output / "AI-Blog-Auto-Windows-x64.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(desktop.rglob("*")):
            if path.is_symlink():
                raise ValueError("Unexpected symlink in build output")
            if path.is_file():
                archive.write(path, path.relative_to(desktop.parent))
    shutil.copyfile(ROOT / "android-app/app/build/outputs/apk/debug/app-debug.apk", output / "AI-Blog-Monitor-debug.apk")
    sources = list((ROOT / "ubuntu-server/app").glob("*.py"))
    sources += list((ROOT / "ubuntu-server/deploy").glob("*"))
    sources += list((ROOT / "shared").glob("*.json"))
    sources += list((ROOT / "docs").glob("*.md"))
    sources += [ROOT / name for name in ("README.md", "ubuntu-server/requirements.txt", "ubuntu-server/requirements-fcm.txt",
                "ubuntu-server/backup_metadata.py", "ubuntu-server/backup-excludes.txt", "ubuntu-server/.env.example")]
    with tarfile.open(output / "AI-Blog-Ubuntu-source.tar.gz", "w:gz") as archive:
        for path in sorted(sources):
            if not path.is_file() or path.is_symlink():
                raise ValueError("Unexpected source entry")
            archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
    artifacts = []
    for path in sorted(output.iterdir()):
        if path.suffix not in {".zip", ".apk", ".gz"}:
            continue
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        artifacts.append({"file": path.name, "size": path.stat().st_size, "sha256": digest.hexdigest()})
    (output / "SHA256SUMS.json").write_text(json.dumps(artifacts, indent=2), encoding="utf-8")
    print(json.dumps(artifacts, indent=2))


if __name__ == "__main__":
    main()
