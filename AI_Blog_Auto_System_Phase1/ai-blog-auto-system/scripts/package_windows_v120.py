"""Run after PyInstaller and the frozen --self-test, from any working directory."""
import hashlib
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
release = root / "release/v1.2.0"
app = release / "AI-Blog-Auto"
result = json.loads((root / "build/v1.2.0-self-test/result.json").read_text(encoding="utf-8"))
assert result["passed"] and result["version"] == "1.2.0"
validation = {"version": "1.2.0", "date": "2026-11-23",
              "regression_tests_passed": 129, "final_targeted_tests_passed": 49,
              "frozen_exe_self_test": result, "live_public_oidc_discovery": "HTTP 200",
              "not_tested": ["user ChatGPT Plus OAuth approval", "live ChatGPT plan inference", "real blog publication"]}
(release / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
archive_path = release / "AI-Blog-Auto-Windows-v1.2.0-x64.zip"
with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(app.rglob("*")):
        assert not path.is_symlink()
        if path.is_file():
            archive.write(path, path.relative_to(release))
    archive.write(root / "MANUAL.MD", "MANUAL.MD")
    archive.write(release / "validation.json", "validation.json")
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    assert "AI-Blog-Auto/AI-Blog-Auto.exe" in archive.namelist()
    assert [name for name in archive.namelist() if name.lower().endswith('.md')] == ["MANUAL.MD"]
hashes = []
for path in (archive_path, app / "AI-Blog-Auto.exe"):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    hashes.append({"file": path.relative_to(release).as_posix(), "size": path.stat().st_size, "sha256": digest.hexdigest()})
(release / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
print(json.dumps(hashes, indent=2))
