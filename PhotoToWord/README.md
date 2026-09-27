# PhotoToWord Desktop — 사진을 원하는 문서로

Windows 10·11 **64비트**용 데스크톱 GUI입니다. 사진을 추가하면 내용을 분석하여 출력 형식을 **1·2·3순위로 추천**합니다. 추천과 관계없이 **Word / Excel / PowerPoint / TXT / PDF / CSV**를 직접 선택할 수도 있습니다.

로컬에서 처리하며 API 키가 필요 없습니다. 사진을 외부 OCR 서버에 보내지 않습니다. 최초 개발환경/패키지 설치에는 인터넷이 필요합니다.

## 실행

**GitHub에서 받아 바로 실행:** [PhotoToWord v1.0.0 다운로드](https://github.com/forlovesea/work/releases/tag/phototoword-v1.0.0)에서 `PhotoToWord-1.0.0-windows-x64.zip`을 받아 폴더 전체를 압축 해제하고 `START.bat`를 실행하세요. 이 배포 ZIP에는 Python 실행 환경, Tesseract OCR, 한국어·영어 모델이 포함됩니다. 별도 Python/OCR 설치나 인터넷 연결 없이 실행할 수 있습니다. 저장소가 비공개이므로 GitHub 접근 권한이 있는 계정으로 로그인해야 합니다.

**Code → Download ZIP으로 받은 소스:** 압축 해제 후 `PhotoToWord` 폴더에서 Python 3.10~3.13 64비트를 설치하고 `run.bat`를 실행하세요. 가상환경이 없으면 최초 실행 시 필요한 패키지를 설치합니다(인터넷 필요). 소스로 OCR을 실행하려면 아래 OCR 설정에 따라 Tesseract와 언어 데이터를 설치하세요. 가장 간단한 실행 방법은 위 Releases ZIP입니다.

**Python 없이 실행:** `dist\PhotoToWord\PhotoToWord.exe`를 더블클릭하세요. 다른 PC에는 **dist\PhotoToWord 폴더 전체**를 복사해야 합니다. `_internal` 폴더도 필수입니다. Word/Excel/PowerPoint를 설치하지 않아도 출력 파일을 생성할 수 있습니다.

**소스에서 실행:** 현재 프로젝트에는 가상환경이 구성되어 있습니다. `run.bat`를 더블클릭하면 GUI가 열립니다. 새 PC 또는 프로젝트 경로 변경 후에는 Python 3.10 이상(64비트)을 설치하고 실행하세요.

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\run.bat
```

이전 Word 전용 브라우저 화면은 `run_web.bat`로 실행합니다. 새 추천/다중 형식 선택 기능은 **데스크톱 GUI**에 구현되어 있습니다.

## 사용 순서

1. **사진 추가**: JPG, PNG, WEBP, BMP, 단일 페이지 TIFF를 선택합니다. 최대 20장, 장당 20MB/2,400만 화소입니다.
2. 왼쪽 목록의 **↑ / ↓ / 삭제**로 페이지 순서를 정합니다.
   필요하면 사진을 선택하고 **보정 옵션…**을 누릅니다. 기울기·그림자·대비·회색조·흑백 옵션을 조절한 뒤 **보정 미리보기**로 전후 사진을 비교합니다. **실제 크기 (100%)**에서는 스크롤로 글자 획을 확인할 수 있습니다. **원본 사진 선택 / 보정 사진 선택** 중 하나를 누르면 그 사진으로 분석합니다. 보정 선택은 사진마다 적용되고 목록에 **[보정]**으로 표시됩니다. 원본 파일은 수정하지 않으며, 보정 사진을 선택하면 문서에 포함되는 이미지에도 적용됩니다. 다시 보정 창에서 원본을 선택하면 되돌릴 수 있습니다. 선택은 앱을 종료하면 초기화됩니다.
3. OCR 언어와 배치 모드를 고르고 **분석 및 추천**을 누릅니다. 한국어가 많은 사진은 기본값 **kor+eng / 한국어 본문**을 사용하세요. 여러 단/복잡한 배치는 **자동 배치**, 흩어진 짧은 글자는 **흩어진 글자**도 비교할 수 있습니다. 분석은 백그라운드에서 실행됩니다.
4. 오른쪽 **1·2·3순위**와 추천 이유를 확인합니다. 기본은 1순위이며 2·3순위도 선택할 수 있습니다.
5. 다른 형식을 원하면 **직접 선택** 목록에서 고릅니다. 수동 선택은 추천보다 우선합니다.
6. **선택한 형식으로 저장…**에서 파일 이름과 경로를 지정합니다.

가운데에서 사진/검출 영역과 추출 텍스트를 확인합니다. 추출 텍스트 탭에서 문장을 수정한 뒤 저장할 수 있습니다. 사진 목록/언어/보정 선택을 변경하면 다시 분석하도록 이전 결과와 편집 내용을 초기화합니다. 여러 사진은 하나의 출력 파일로 저장됩니다.

오른쪽 내용이 화면에 모두 들어오지 않으면 마우스 휠 또는 세로 스크롤바를 사용하세요. 분석 취소는 현재 사진 처리 후 반영되며 OCR 한 장의 제한 시간은 120초입니다.

## 보정 옵션 사용법

1. 왼쪽 목록에서 사진 한 장을 선택하고 **보정 옵션…**을 누릅니다. 보정은 선택 사항입니다.
2. 아래 옵션을 조절하고 **보정 미리보기**를 누릅니다. 옵션을 바꾼 뒤에는 미리보기를 다시 갱신해야 보정 사진을 선택할 수 있습니다.
3. 왼쪽 원본과 오른쪽 보정 사진을 비교합니다. **실제 크기 (100%)**를 켜고 스크롤하여 작은 글자의 획이 유지되는지 확인하세요.
4. **원본 사진 선택** 또는 **보정 사진 선택**으로 확정합니다. **취소**나 창 닫기는 기존 선택을 유지합니다.
5. 메인 화면에서 **분석 및 추천**을 누릅니다. 사진 선택만으로 분석이 시작되지는 않습니다.

| 옵션 | 설명 |
|---|---|
| 자동 기울기 보정 | 글줄이나 수평선의 기울기를 감지해 회전합니다. 감지되지 않으면 유지하며, 원근 왜곡은 보정하지 않습니다. |
| 그림자 완화 | 배경 밝기의 차이를 줄입니다. 컬러 이미지의 색도 달라질 수 있습니다. |
| 대비 (0.5~2.0) | 밝고 어두운 부분의 차이를 조절합니다. 1.0은 대비를 추가로 바꾸지 않는 값입니다. |
| 회색조 | 색상을 회색 명암으로 바꿉니다. |
| 흑백 보정 | 검정과 흰색으로 구분합니다. 가는 글자 획이 사라지지 않는지 확인하세요. |

보정은 사진별로 적용되며 목록에 **[보정]**으로 표시됩니다. 보정 창을 다시 열고 **원본 사진 선택**을 누르면 되돌릴 수 있습니다. 원본 파일은 수정하지 않습니다. **원본 사진 보기**는 항상 원본을 보여 주며, 보정 사진을 선택했다면 분석과 문서에 포함되는 이미지에는 보정 사진을 사용합니다. 선택은 앱 종료 시 초기화됩니다. 분석 후 선택을 바꾸면 다시 분석해야 합니다.

보정이 항상 인식률을 높이지는 않습니다. 전후 사진에서 글자 획을 비교하고 분석 결과도 확인하세요.

## 추천 기준

전체 사진의 텍스트 양, 표 구분선, 도형 수, 가로/세로 배치를 집계하는 **규칙 기반 추천**입니다. 정확도 확률이나 AI 신뢰도 점수가 아닙니다.

| 주된 특징 | 1순위 | 2순위 | 3순위 |
|---|---|---|---|
| 구분선이 있는 표가 일정 면적 이상 | Excel | Word | PDF |
| 텍스트와 여러 도형 또는 가로 배치 | PowerPoint | Word | PDF |
| 본문 텍스트 중심 | Word | TXT | PDF |
| 사진/이미지 중심 | PDF | PowerPoint | Word |
| OCR 엔진/선택 언어를 사용할 수 없음 | PDF | PowerPoint | Word |

여러 장을 선택하면 전체 묶음에 대한 추천입니다. 사진마다 다른 형식으로 저장하려면 개별 분석/저장하세요. OCR이 없으면 텍스트 기반 추천 대신 이미지 보존을 우선합니다.

## 형식별 저장 내용

| 형식 | 실제 저장 내용 | 범위 |
|---|---|---|
| Word `.docx` | 페이지별 텍스트 상자, 사진 조각, 사각형/타원 | 복잡한 그림/표 내부는 이미지로 남을 수 있음 |
| Excel `.xlsx` | 표별 셀 시트 + 페이지별 원본 사진/전체 OCR 텍스트 시트 | 직선 구분선이 있는 단순 표만 셀로 복원 |
| PowerPoint `.pptx` | 사진별 슬라이드, 편집 가능한 글자·단순 도형·이미지 | 슬라이드 크기는 동일, 원래 글꼴/연결 관계 미복원 |
| TXT `.txt` | 페이지 구분을 포함한 OCR 글자 | 사진·도형·배치 제외, UTF-8 BOM |
| PDF `.pdf` | 사진을 페이지로 보존 | 이미지 PDF, 글자 검색·수정 불가 |
| CSV `.csv` | 페이지/표/행 번호와 각 열의 값 | 표가 없으면 OCR 줄 목록, 그림 제외, UTF-8 BOM |

**Word/PPT: 원본 사진으로 보존**은 두 형식에 한해 전체 사진을 삽입합니다. 글자/도형은 편집되지 않습니다. PDF는 항상 이미지 보존 방식입니다.

Excel은 선행 0과 OCR 원문을 보존하기 위해 수치/수식처럼 보이는 값도 문자열로 저장합니다. CSV에서 수식처럼 해석될 수 있는 값은 작은따옴표를 앞에 붙입니다. 계산하려면 결과를 검토한 뒤 Excel에서 숫자 형식으로 바꾸세요.

## OCR 설정

GitHub Releases ZIP에는 Tesseract OCR 엔진과 한국어·영어 데이터가 함께 들어 있습니다. **소스 실행 또는 build.ps1만으로 만든 EXE**에는 OCR 엔진이 포함되지 않으므로 별도 설치가 필요합니다. 미설치 상태에서도 GUI, 추천, 사진 기반 DOCX/PPTX/PDF와 이미지가 포함된 XLSX 출력은 가능합니다. TXT/CSV에는 인식할 글자가 없어 안내 문구만 저장됩니다. GUI는 이 상태를 알리고 텍스트 없는 출력 전에 확인합니다.

1. [Tesseract 공식 설치 안내](https://tesseract-ocr.github.io/tessdoc/Installation.html)에서 UB Mannheim Windows 설치 파일을 찾습니다.
2. English와 Korean 언어 데이터를 포함하여 설치합니다.
3. GUI의 **OCR 설정**에서 `tesseract.exe`를 선택하고 **확인 및 저장**을 누릅니다.
4. `kor+eng`로 다시 분석합니다. 한국어 데이터가 없다면 `eng`만 선택하거나 한국어 데이터를 추가하세요.

GUI에 저장한 실행 경로, `TESSERACT_CMD` 환경변수, PATH, 기본 설치 위치를 사용합니다. EXE/소스 옆 `tools\Tesseract-OCR\tesseract.exe`도 인식합니다. 설정은 `%LOCALAPPDATA%\PhotoToWord\settings.json`에 저장합니다. GUI가 외부 프로그램을 자동 다운로드/설치하지는 않습니다.

한국어가 누락되었으면 [공식 kor.traineddata](https://github.com/tesseract-ocr/tessdata_fast/raw/main/kor.traineddata)를 설치 경로의 `tessdata` 폴더에 넣으세요. 별도 폴더를 사용하려면 [eng.traineddata](https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata)도 함께 넣고 실행 전 `TESSDATA_PREFIX` 환경변수를 지정하세요.

## 인식 범위와 한계

- 선명한 정면 문서 사진에 적합합니다. EXIF 방향을 반영하고, 보정 옵션에서 자동 기울기 보정을 선택할 수 있습니다. 원근 왜곡은 보정하지 않습니다.
- OCR 오류, 요소 누락, 도형 오분류가 발생할 수 있습니다. 결과를 검토해야 합니다.
- 구분선 없는 표, 병합 셀, 복잡한 표, 손글씨, 수식, 차트 데이터/연결 관계의 구조 복원은 보장하지 않습니다.
- 사진은 최대 2400×3200으로 축소됩니다. 원본 보존 옵션도 축소된 작업 이미지를 사용합니다.
- Word는 VML 도형/텍스트 상자를 사용하며 데스크톱 Microsoft Word를 기준으로 합니다. 다른 뷰어에서 배치가 달라질 수 있습니다.
- 구형 `.doc/.xls/.ppt` 대신 `.docx/.xlsx/.pptx`를 지원합니다. HWP/HWPX는 지원하지 않습니다.

## 빌드와 검증

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe desktop.py --smoke-test smoke-output
.\.venv\Scripts\python.exe tests/gui_flow.py
```

Windows에서 PyInstaller로 64비트 폴더형 EXE를 만듭니다. `build.ps1`은 `dist\PhotoToWord` 결과를 갱신하므로 배포 폴더 안에 사용자 사진/결과 파일을 보관하지 마세요.

검증은 추천 규칙, 표 좌표/셀 배정, 6개 출력 형식, 저장 실패 시 기존 파일 보존, GUI 초기화/수동 선택/백그라운드 흐름을 포함합니다. 합성 요소와 모의 OCR은 실제 인식률 검증을 대신하지 않습니다. Windows 10에서 실행 검증했으며 Windows 11과 실제 Office 화면은 별도 장비에서 아직 확인하지 않았습니다.

## 주요 코드

```text
desktop.py                 GUI / 추천·수동 선택 / 백그라운드 처리
photoword/core.py          이미지 / OCR / 이미지·도형 검출
photoword/insights.py      표 검출·셀 배정 / 형식 추천
photoword/exporters.py     다중 출력 형식 / 파일 저장
photoword/document.py      Word 문서 생성
PhotoToWord.spec           Windows EXE 빌드 설정
build.ps1 / run.bat        빌드 / 데스크톱 실행
run_web.bat / app.py       기존 Word 전용 웹 UI
tests/                    회귀 테스트
samples/sample.png        테스트용 사진
```

참고: [python-pptx](https://python-pptx.readthedocs.io/en/latest/), [openpyxl](https://openpyxl.readthedocs.io/en/stable/), [PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html).
