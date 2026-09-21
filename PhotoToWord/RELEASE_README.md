# PhotoToWord — Windows 실행 안내

1. ZIP 파일을 폴더 전체로 압축 해제합니다.
2. `START.bat` 또는 `PhotoToWord\PhotoToWord.exe`를 더블클릭합니다.
3. 사진 추가 → 필요하면 보정 옵션에서 전후 비교·최종 선택 → 분석 및 추천 → 출력 형식 선택 → 저장 순서로 사용합니다.

Windows 10/11 64비트용입니다. Python이나 Microsoft Office 설치는 필요하지 않습니다. 이 배포 ZIP에는 Tesseract OCR과 한국어·영어 모델이 포함되어 있어 별도 OCR 설치 없이 사용할 수 있습니다. 압축 해제 후에는 인터넷 연결 없이 사진을 처리합니다.

`_internal` 및 `tools`를 포함한 **폴더 전체**를 함께 보관하세요. EXE만 옮기면 실행 또는 OCR이 되지 않습니다. 확인용 `sample.png`와 `korean_sample.png`가 앱 폴더에 포함되어 있습니다.

글꼴은 설치된 Noto Sans KR을 우선 사용하고, 없으면 사용 가능한 한글 글꼴로 표시합니다. 원본 사진은 덮어쓰지 않습니다. 보정 선택은 앱 종료 시 초기화됩니다. OCR 결과는 저장 전에 확인하세요.

기존 PC에서 별도 OCR 경로를 저장했다면 해당 설정이 우선합니다. 동봉된 OCR을 사용하려면 앱의 **OCR 설정**에서 `PhotoToWord\tools\Tesseract-OCR\tesseract.exe`를 선택하세요.

GitHub의 **Code → Download ZIP**은 소스 코드입니다. 바로 실행할 파일은 **Releases**에서 `PhotoToWord-버전-windows-x64.zip`을 받으세요. 자세한 기능 설명은 앱의 **매뉴얼 보기** 및 동봉된 README.md에 있습니다.
