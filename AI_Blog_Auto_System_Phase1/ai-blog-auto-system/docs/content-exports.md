# 콘텐츠 출력 사용법

기존 Phase 1 서버/CLI와 Phase 2 GUI를 유지하고 **콘텐츠 출력** 화면을 추가했습니다.

## 사용 순서

1. **AI 글쓰기**에서 초안을 생성하거나 저장된 초안을 선택합니다.
2. **콘텐츠 출력**에서 **최근 생성 이미지 추가** 또는 **이미지 파일 추가**를 누릅니다.
3. 목록의 **위로/아래로** 버튼으로 순서를 정하고, 설명을 입력한 뒤 **설명 저장**을 누릅니다.
4. **HTML 미리보기**, **서식 포함 전체 복사**, **HTML 저장**, **Word 저장**, **ZIP 패키지 만들기**를 사용합니다.

목록과 설명은 초안별 SQLite JSON에 저장되며 재시작 후에도 유지됩니다.
이미지가 없는 기존 초안도 수정 없이 출력할 수 있습니다.
목록에서 제거해도 원본 이미지 파일은 삭제하지 않습니다.
생성한 이미지가 자동으로 글에 들어가지는 않으므로 원하는 초안에 명시적으로 추가하세요.

## 이미지 배치 규칙

- 첫 이미지: 제목/요약 뒤의 썸네일.
- 두 번째 이미지: 첫 본문 섹션 뒤.
- 세 번째 이미지: 두 번째 본문 섹션 뒤.
- 본문 섹션 수를 초과한 이미지: 마지막 본문 뒤에 목록 순서대로 배치.
- 모든 출력은 같은 배치 모델을 사용합니다. 순서를 바꾸면 썸네일도 함께 바뀝니다.

PNG/JPEG/WebP/BMP 입력을 PNG로 변환하고 EXIF 방향을 반영합니다.
이미지당 20 MiB/2,400만 픽셀, 글당 최대 30장/변환 이미지 합계 80 MiB를 허용합니다.
파일이 없거나 손상된 경우 오류를 표시하며 이미지를 조용히 누락시키지 않습니다.

## HTML

미리보기는 스크립트를 실행하지 않는 Qt 텍스트 브라우저를 사용합니다.
외부 이미지·스타일시트·로컬 파일 요청은 차단하고 생성된 inline PNG만 읽습니다.
텍스트와 설명은 HTML escape 처리하며 출처 링크는 HTTP/HTTPS만 허용합니다.
미리보기의 링크 자동 열기는 비활성화되어 있습니다.

**HTML 저장**은 이미지가 data URI로 내장된 단일 HTML 파일입니다.
다른 PC로 HTML 파일 하나만 옮겨도 원본 이미지 경로에 의존하지 않습니다.
ZIP 안의 `index.html`은 함께 포함된 `images/`의 상대 경로를 사용합니다.
ZIP을 완전히 압축 해제한 뒤 `index.html`을 여세요.
Qt 미리보기와 일반 브라우저의 세부 CSS 표현은 다를 수 있습니다.

## 서식 포함 전체 복사

일반 Windows 실행에서는 다음 클립보드 형식을 한 번의 복사로 제공합니다.

- Unicode 일반 텍스트(`CF_UNICODETEXT`), UTF-8 `text/plain`
- UTF-8 `text/html`
- Windows 등록 형식 `HTML Format` (`CF_HTML`)
- 이미지가 있으면 첫 이미지의 PNG/CF_DIB 보조 형식

전체 이미지의 순서와 본문 내 배치는 CF_HTML/HTML의 inline PNG에 들어갑니다.
PNG/CF_DIB는 단일 이미지용 보조 형식이므로 이를 선택하는 앱은 첫 이미지만 붙여넣을 수 있습니다.
붙여넣기 대상이 data URI 이미지를 제거하거나 HTML 대신 일반 텍스트를 선택할 수도 있습니다.
따라서 복사 성공을 특정 편집기의 붙여넣기 호환성 검증으로 간주하지 않습니다.

CF_HTML의 StartHTML/EndHTML/StartFragment/EndFragment는 문자 수가 아닌 **UTF-8 바이트 위치**입니다.
구현은 [Microsoft HTML Clipboard Format](https://learn.microsoft.com/en-us/windows/win32/dataxchg/html-clipboard-format)을 따릅니다.
자동 GUI 시험의 offscreen 환경은 [Qt QMimeData](https://doc.qt.io/qt-6/qmimedata.html)를 사용하고,
별도 Windows smoke 시험은 실제 Win32 등록 형식을 다시 읽어 확인합니다.

기존 **AI 글쓰기 → 본문 복사**는 일반 텍스트 복사로 유지됩니다.
전체 서식과 이미지를 복사하려면 **콘텐츠 출력 → 서식 포함 전체 복사**를 사용하세요.

## DOCX

python-docx로 A4 문서와 한글 글꼴을 설정하고 제목, 요약, 본문, 이미지, 설명, 태그, SEO, 출처를 기록합니다.
이미지는 외부 링크가 아닌 DOCX 내부 `word/media`에 포함됩니다.
이미지 크기는 비율을 유지하며 페이지 폭과 높이에 맞추고 설명과 함께 배치합니다.
원본 이미지가 없어도 Word 문서 하나만으로 열 수 있습니다.

## ZIP과 manifest

```text
index.html
article.txt
article.docx
images/thumbnail.png
images/body_01.png
images/body_02.png
...
manifest.json
```

이미지가 없는 글은 `images/` 파일 없이 생성됩니다. TXT에는 이미지 파일명·설명·표시 문구가
본문의 같은 위치에 들어갑니다. TXT 자체에 픽셀 데이터는 포함하지 않습니다.

manifest에는 형식 버전, 콘텐츠 ID, 제목, 초안 생성/패키지 생성 시각,
이미지 ID·순서·상대 경로·배치 위치·설명, 파일별 바이트 크기와 SHA-256이 들어갑니다.
manifest 자체의 해시는 자기 참조 문제 때문에 포함하지 않습니다.
ZIP 자체의 해시는 추후 업로드 단계에서 별도로 계산해야 합니다.

내보내기는 허용된 글 필드만 사용합니다. 서버 토큰, OpenAI 키, DB, 로컬 절대 이미지 경로를 포함하지 않습니다.
출력 파일은 같은 디렉터리의 임시 파일을 완성한 뒤 교체하므로 생성 실패로 기존 파일을 덮어쓰지 않습니다.
사용자가 글 본문이나 이미지 설명에 직접 입력한 내용은 그대로 출력됩니다.

## 검증

- 자동 테스트: `python -m pytest -q`
- 실제 Windows 클립보드/출력: `python tests/smoke_exports.py`
- Word 렌더링: `powershell -File tests/render_docx_word.ps1 -InputDocx <DOCX> -OutputPdf <PDF>`

`smoke_exports.py`는 시스템 클립보드를 테스트 콘텐츠로 바꾸며 `.pytest-tmp/exports-qa`에 QA 파일을 만듭니다.
Word 렌더링 도구는 설치된 Word가 필요하며 지정한 테스트 문서만 읽기 전용으로 엽니다.
테스트 파일은 제품 배포 산출물이 아니며 pytest가 다시 실행되면 제거될 수 있습니다.

[검증 결과](phase3-test-results.md) · [스마트에디터 실제 시험](naver-paste-test.md)
