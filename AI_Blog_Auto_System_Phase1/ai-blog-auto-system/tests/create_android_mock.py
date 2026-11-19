"""Rebuild the small, portable Android fixture with the Windows export contract."""
import sys
import tempfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "windows-app"))
from blog_gui.exports import Publication

with tempfile.TemporaryDirectory(dir=ROOT / ".pytest-tmp") as temporary:
    images = []
    for i, color in enumerate(("#244E72", "#36A391", "#F1B35C")):
        path = Path(temporary) / f"image{i}.png"
        Image.new("RGB", (640, 320), color).save(path)
        images.append({"id": f"mock-{i}", "path": str(path), "caption": f"순서 {i + 1}: Mock 이미지", "disclosure": "Mock"})
    article = {"id": "99f7d610-d944-4011-a8da-9dcdd88f1120", "created_at": "2026-11-18T00:00:00+00:00",
               "title": "AI 블로그 수동 발행 예제", "summary": "실제 서버 없이 다운로드와 복사를 시험하세요.",
               "sections": [{"heading": "안전한 콘텐츠 확인", "body": "출처와 내용을 검토한 뒤 직접 발행하세요."},
                            {"heading": "이미지 순서", "body": "썸네일, 본문 첫 이미지, 본문 두 번째 이미지 순서입니다."}],
               "images": images, "sources": [], "tags": ["Mock", "테스트"], "seo_keywords": []}
    target = ROOT / "android-app/app/src/main/assets/mock-package.zip"
    target.write_bytes(Publication(article).package())
    print(f"Generated {target.name}: {target.stat().st_size} bytes")
