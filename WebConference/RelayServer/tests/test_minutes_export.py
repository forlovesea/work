from io import BytesIO
import pytest
from docx import Document
from pypdf import PdfReader
from fastapi.testclient import TestClient
from app.main import create_app
from app.media import SpeechService
from app.minutes_export import export_minutes, document_blocks


def entries(count=5):
    return [{"id": i, "at": f"2026-10-17T01:{i % 60:02}:00+00:00", "speaker": "지현" if i % 2 else "민수",
             "kind": "speech", "text": f"기록{i:04d} 축전지 전압은 48V입니다. 교체는 아직 결정하지 않았습니다. <보류> & 재검토"} for i in range(count)]


def extract(data, fmt):
    if fmt == "txt":
        return data.decode("utf-8-sig")
    if fmt == "docx":
        return "\n".join(p.text for p in Document(BytesIO(data)).paragraphs)
    return "\n".join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)


@pytest.mark.parametrize("fmt", ["txt", "docx", "pdf"])
@pytest.mark.parametrize("summary", [False, True])
def test_export_keeps_every_record_and_summary_is_optional(fmt, summary):
    original = entries(205)  # More than the UI's 200-entry cache.
    data, mime = export_minutes("축전지 점검", original[0]["at"], original, fmt, summary)
    text = extract(data, fmt)
    assert ("회의록 요약" in text) == summary
    assert "전체 대화 및 기록" in text
    for e in original:
        assert "".join(e["text"].split()) in "".join(text.split())
    if summary:
        decision = text.split("확정 결정")[1].split("실행 항목")[0]
        assert "교체" not in decision
        assert "방장이 확정하여 기록한 항목 없음" in decision


@pytest.mark.parametrize("fmt", ["txt", "docx", "pdf"])
def test_empty_and_long_records(fmt):
    data, _ = export_minutes("빈 회의", "2026-10-17T00:00:00+00:00", [], fmt, True)
    assert "저장된 대화 및 기록이 없습니다" in extract(data, fmt)
    original = entries(1)
    original[0]["text"] = "한글과 긴 내용 " * 600 + "끝표식"
    data, _ = export_minutes("긴 회의", original[0]["at"], original, fmt)
    assert "끝표식" in extract(data, fmt)


def test_api_formats_authorization_and_default(tmp_path):
    with TestClient(create_app(str(tmp_path / "export.db"), SpeechService(""), approval_required=False)) as client:
        host = client.post("/api/rooms", json={"title": "테스트", "name": "방장"}).json()
        other = client.post("/api/rooms", json={"title": "다른 방", "name": "손님"}).json()
        url = f"/api/rooms/{host['room_id']}/minutes"
        headers = {"Authorization": "Bearer " + host["token"]}
        for fmt in ("txt", "docx", "pdf"):
            assert client.get(url, params={"format": fmt}).status_code == 403
            assert client.get(url, params={"format": fmt}, headers={"Authorization": "Bearer " + other["token"]}).status_code == 403
            response = client.get(url, params={"format": fmt, "summary": True}, headers=headers)
            assert response.status_code == 200
            assert f".{fmt}" in response.headers["content-disposition"]
            assert response.headers["cache-control"] == "no-store"
            assert "회의록 요약" in extract(response.content, fmt)
        response = client.get(url, headers=headers)
        assert "text/plain" in response.headers["content-type"]
        assert "회의록 요약" not in response.text
        assert client.get(url, params={"format": "exe"}, headers=headers).status_code == 422
        assert client.get(url, params={"summary": "invalid"}, headers=headers).status_code == 422
