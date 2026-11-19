# 콘텐츠 출력 검증 결과

검증일: 2026-11-18 (Asia/Seoul).
환경: Windows, Python 3.10.11, PySide6 6.12.0, python-docx 1.2.0.

## 자동 테스트

```text
.venv/Scripts/python -m pytest -q
47 passed, 1 warning
PYTEST_EXIT=0
```

기존 Phase 1/2의 39개 테스트와 출력 관련 8개 테스트가 통과했습니다.
Starlette TestClient의 httpx deprecation 경고 1건은 기존과 동일합니다.
`pip check`도 의존성 문제 없음으로 통과했습니다.
전체 시험 종료 시 Qt offscreen 클립보드 객체 정리에서 발생한 비정상 종료를 발견해,
QApplication 종료 전에 테스트 클립보드를 해제하도록 수정했습니다.
기존 scheduler callback 시험도 일회성 작업의 내부 정리가 끝난 후 종료하도록 보완했습니다.
최종 실행은 모든 테스트 통과 후 종료 코드 0을 확인했습니다.

검증 내용:

- 4개 이미지의 기본 순서와 재정렬 순서를 HTML/CF_HTML/TXT/DOCX/manifest에서 비교.
- 이미지 실데이터 SHA-256을 비교하여 파일명뿐 아니라 실제 이미지 순서가 일치함을 확인.
- DOCX 본문의 drawing 순서와 relationship 대상 이미지 확인. 외부 이미지 링크 없음.
- 원본 이미지를 삭제한 뒤에도 ZIP의 DOCX와 이미지가 독립적으로 유효함을 확인.
- ZIP 포함 파일 목록, 상대 경로, 이미지 순서, 파일 크기, SHA-256 검증.
- manifest/HTML/TXT에 로컬 절대 이미지 경로나 테스트 비밀정보가 포함되지 않음.
- 한글·다중 바이트 문자의 CF_HTML 바이트 오프셋과 fragment 내용 검증.
- HTML의 텍스트/설명 escape, 위험한 URL 제외, 미리보기 외부/로컬 리소스 접근 차단.
- 이미지 없는 글, 손상된 이미지 오류, 실패 시 기존 출력 파일 보존.
- GUI 이미지 추가/최근 이미지 추가/위아래 이동/제거/설명 저장/미리보기/복사/HTML·DOCX·ZIP 저장.
- 이미지 순서를 SQLite에 저장한 뒤 다시 읽어 일치함을 확인.

## 실제 Windows 클립보드

```text
.venv/Scripts/python tests/smoke_exports.py
PASS: native Windows HTML Format, Unicode text, text/html, text/plain, PNG and CF_DIB
PASS: standalone HTML, embedded DOCX and ZIP generated for three ordered images
```

Qt의 offscreen MIME 객체 검증과 별개로, Win32 API를 통해 시스템 클립보드에 쓴 뒤
`HTML Format`, CF_UNICODETEXT, `text/html`, `text/plain`, PNG, CF_DIB를 다시 읽었습니다.
CF_HTML 전체 바이트와 한글 일반 텍스트가 생성 데이터와 일치함을 확인했습니다.
이는 네이버 스마트에디터에서의 붙여넣기 결과를 검증한 것이 아닙니다.

## HTML 및 DOCX 화면 확인

GUI 콘텐츠 출력 화면을 렌더링해 미리보기의 제목·본문·이미지·설명을 확인했습니다.
이미지 선택 행의 낮은 글자 대비를 수정했습니다.

Documents 스킬의 `render_docx.py` 실행은 pdf2image 의존성이 없어 실패했습니다.
대신 설치된 Microsoft Word로 테스트 DOCX를 읽기 전용으로 열어 PDF로 변환하고,
Qt PDF로 2개 페이지를 PNG로 렌더링한 뒤 두 페이지 모두 직접 확인했습니다.
제목 아래 남아 있던 기본 스타일의 파란 테두리를 제거하고 재생성·재렌더링했습니다.
최종 문서에서 한글, 빨강→초록→파랑 이미지 순서, 설명, 태그와 출처를 확인했습니다.
잘림이나 겹침은 발견되지 않았습니다.

재현 도구:

```powershell
.venv/Scripts/python tests/smoke_exports.py
powershell -File tests/render_docx_word.ps1 -InputDocx .pytest-tmp/exports-qa/sample.docx -OutputPdf .pytest-tmp/exports-qa/sample.pdf
.venv/Scripts/python tests/render_pdf_pages.py .pytest-tmp/exports-qa/sample.pdf .pytest-tmp/exports-qa/pages
```

Word 렌더링 도구는 설치된 Word가 필요합니다. QA 파일은 `.pytest-tmp`에 생성하며
자동 테스트가 다시 실행되면 지워질 수 있습니다.

## 별도 실제 시험

**네이버 스마트에디터 ONE 호환성은 미실시**입니다.
[실제 붙여넣기 시험표](naver-paste-test.md)에 Windows/브라우저별 이미지 유지,
순서, 서식, 줄바꿈, 초안 저장 후 다시 열기, 앱 종료 후 붙여넣기 항목을 기록했습니다.
data URI 이미지의 허용 여부는 대상 편집기에 따라 달라질 수 있습니다.

Windows 10/11 각각, Python 3.11, 다양한 Word/브라우저 버전과 대용량 문서의 실제 호환성은
추가 검증 대상입니다. 운영 서버 접속·배포 또는 네이버 게시를 수행하지 않았습니다.
