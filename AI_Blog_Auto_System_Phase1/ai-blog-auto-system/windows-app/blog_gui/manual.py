"""Manual-only publication handoff; no Naver automation or private API."""
import hashlib
import json
import uuid
from pathlib import Path

from .exports import Publication, atomic_write
from .services import ServiceError
from send_mock_event import validate_url


AUTO_PUBLISH_ENABLED = False


def automatic_publish(*args, **kwargs):
    raise ServiceError("네이버 자동 발행은 비활성화되어 있습니다. 공식 편집기에서 직접 발행하세요.")


class ManualHandoff:
    def __init__(self, services):
        self.services = services
        self.root = services.store.directory / "pending-packages"
        self.root.mkdir(exist_ok=True)

    def prepare(self, config, article, failed=False):
        # Freeze the ZIP once: retries must reuse the exact same bytes and UUID.
        content_id = str(uuid.UUID(article["id"]))
        path = self.root / (content_id + ".zip")
        if not path.exists():
            atomic_write(path, Publication(article).package())
        key = "handoff:" + content_id
        if not self.services.store.get(key):
            if failed:
                self.services.event(config, "PUBLISH_FAILED", {
                    "content_id": content_id, "source": "user_report", "mock": config.mock,
                    "reason": "사용자가 발행 실패를 기록함; 자동 발행 시도 아님"})
            self.services.event(config, "MANUAL_PUBLISH_REQUIRED", {"content_id": content_id, "mock": config.mock})
            self.services.store.put(key, {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        return path

    def upload(self, config, token, path):
        if not token:
            raise ServiceError("서버 토큰을 설정하세요. 생성한 패키지는 로컬에 보존됩니다.")
        path = Path(path)
        content_id = str(uuid.UUID(path.stem))
        if path.resolve() != (self.root / (content_id + ".zip")).resolve():
            raise ServiceError("대기 패키지 경로가 올바르지 않습니다.")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        saved = self.services.store.get("handoff:" + content_id)
        if not saved or saved["sha256"] != digest:
            raise ServiceError("로컬 대기 패키지 무결성 검증에 실패했습니다.")
        with self.services.client_factory() as client:
            response = client.post(validate_url(config.server_url) + "/api/v1/packages", content=data,
                headers={"X-Device-Token": token, "Content-Type": "application/zip", "X-Content-SHA256": digest})
            response.raise_for_status()
            result = response.json()
            if result.get("package_id") != content_id or result.get("sha256") != digest:
                raise ServiceError("업로드 응답 검증 실패; 패키지를 보존했습니다.")
        self.services.store.put("uploaded:" + content_id, result)
        return result

    def retry(self, config, token):
        results = []
        for path in sorted(self.root.glob("*.zip")):
            if not self.services.store.get("uploaded:" + path.stem):
                results.append(self.upload(config, token, path))
        return results
