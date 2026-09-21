# 현재 PC의 OCR 설치 및 검증

- 설치일: 2026-09-18
- 엔진: Tesseract 5.5.3.20260724, Windows 64비트
- 위치: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- 언어: `kor`, `eng`, `osd`
- 한국어/영어 모델: 공식 `tessdata_best`
- 프로그램 기본값: `kor+eng` + `한국어 본문` (PSM 6)

자동 배치(PSM 3)가 한국어 샘플의 줄을 잘못 분할하는 현상을 확인하여 데스크톱에 배치 모드 선택을 추가했습니다. 다른 배치에는 자동 배치(3) 또는 흩어진 글자(11)를 선택하고 다시 분석할 수 있습니다.

실제 GUI 분석 경로에서 한국어/영어 샘플을 OCR로 읽고 DOCX, XLSX, PPTX, TXT, PDF, CSV를 생성했습니다. 결과는 `samples/korean_ocr_verified`에 있습니다.

정확도는 완벽하지 않습니다. 샘플에서 `한국어 문서 변환 테스트`, `홍길동`, `12345`는 인식했으나 `추출합니다`는 `추줄합니다`로 읽었고 한국어 띄어쓰기도 달라졌습니다. `verification.json`에 원문과 결과를 함께 기록했습니다. 이 검증은 깨끗한 합성 사진의 설치/연결 확인이며 사용자의 실제 사진 인식률을 보장하지 않습니다.

이 PC에서는 엔진 경로를 자동 탐색합니다. 기존 프로그램 창을 닫고 최신 EXE를 다시 실행하세요. 다른 PC에서는 Tesseract 및 언어 데이터 설치가 별도로 필요합니다.

설치 파일 출처: [공식 Tesseract 릴리스](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.3). 다운로드 SHA256을 공식 릴리스의 digest와 대조했습니다.

```text
bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4
```
