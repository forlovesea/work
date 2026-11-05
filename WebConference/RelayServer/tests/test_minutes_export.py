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


def test_summary_preserves_late_negation_and_identical_speakers_utterances():
    original = entries(2)
    text = "축전지 교체 조건을 논의했습니다. " * 30 + "그러나 교체하지 않기로 했습니다."
    for e in original:
        e["text"] = text
    blocks = document_blocks("검토", original[0]["at"], original, True)
    summary = blocks[:blocks.index(("h1", "전체 대화 및 기록"))]
    excerpts = [text for kind, text in summary if "출처:" in text]
    assert len(excerpts) == 2
    assert all("그러나 교체하지 않기로 했습니다." in excerpt for excerpt in excerpts)
    assert "[기록 1] 민수" in excerpts[0]
    assert "[기록 2] 지현" in excerpts[1]
    assert all("_reference" not in e for e in original)


def test_summary_includes_latest_topic_update_and_reports_omissions():
    original = entries(7)
    for i, e in enumerate(original):
        e["text"] = f"축전지 전압 점검 발언 {i}"
    original[-1]["text"] = "축전지 전압 점검은 보류합니다."
    blocks = document_blocks("검토", original[0]["at"], original, True)
    summary = blocks[:blocks.index(("h1", "전체 대화 및 기록"))]
    text = "\n".join(text for _, text in summary)
    assert "축전지 전압 점검은 보류합니다." in text
    assert "[기록 7]" in text
    assert "발언 7건 중 3건 발췌" in text
    assert "생략된 발언 4건" in text


def test_summary_without_keywords_keeps_source_and_latest_utterance():
    original = entries(4)
    for e in original:
        e["text"] = "네"
    blocks = document_blocks("검토", original[0]["at"], original, True)
    summary = blocks[:blocks.index(("h1", "전체 대화 및 기록"))]
    excerpts = [text for _, text in summary if "출처:" in text]
    assert len(excerpts) == 3
    assert "[기록 4] 지현" in excerpts[-1]
    assert "2026-10-17 10:03:00 KST" in excerpts[-1]


def test_summary_references_match_chronological_transcript():
    original = entries(2)
    original[1]["kind"] = "action"
    blocks = document_blocks("검토", original[0]["at"], list(reversed(original)), True)
    summary = blocks[:blocks.index(("h1", "전체 대화 및 기록"))]
    assert any("기록: [기록 2] 지현" in text for _, text in summary)
    sources = [text for kind, text in blocks if kind == "speaker"]
    assert "[기록 1]" in sources[0] and "민수" in sources[0]
    assert "[기록 2]" in sources[1] and "지현" in sources[1]


def test_legacy_timestamp_is_utc():
    from app.minutes_export import stamp
    assert stamp("2026-10-17T01:00:00") == "2026-10-17 10:00:00"
    assert stamp("2026-10-17T10:00:00+09:00") == "2026-10-17 10:00:00"


def test_markdown_orders_delayed_transcripts_and_ties():
    from app.domain import Room, minutes_markdown
    original = entries(3)
    original[2]["at"] = original[1]["at"]
    room = Room("r", "CODE", "회의", "meeting", "p", False)
    text = minutes_markdown(room, list(reversed(original))).split("## 시간순 원문")[1]
    assert text.index("기록0000") < text.index("기록0001") < text.index("기록0002")
