# Phase 4 검증 결과

검증일: 2026-11-18. 로컬 Windows / Python 3.10.11 가상환경.
운영 서버 접속·설정 변경·배포는 하지 않았습니다.

## 실행 결과

```text
.venv\Scripts\python.exe -m pytest -q
68 passed, 1 warning in 12.50s
exit code: 0

.venv\Scripts\python.exe tests/smoke_local.py
Acknowledged events: 1
Acknowledged events: 0
PASS: real HTTP server + CLI + persisted event + empty retry
PASS: real HTTP ZIP upload/download + auth + duplicate + immediate expiry denial
exit code: 0
```

기존 Phase 1~3 47개와 Phase 4 21개 테스트가 통과했습니다.
경고 1개는 설치된 Starlette TestClient의 httpx 사용에 대한 의존성 폐기 예정 안내입니다.
실패한 테스트는 없습니다. 실제 HTTP 시험에서 발견한 테스트 SQLite 연결 미종료를
수정한 후 재실행하여 임시 폴더 정리까지 정상 종료한 것을 확인했습니다.

## 검증 범위

| 항목 | 결과 |
|---|---|
| 기존 이벤트 API·GUI·출력 회귀 | 통과 |
| 실제 Publication ZIP 업로드·원본 다운로드 | 바이트 일치 |
| HTML/TXT/DOCX/manifest/PNG 개별 다운로드 | 원본 ZIP 내부 파일과 일치 |
| PNG 순서 | manifest.image_order 순서의 3개 이미지 바이트 일치 |
| 인증 누락/오류, UUID/인덱스 검증 | 거부 확인 |
| Content-Length 및 길이 없는 청크 업로드 한도 | 모두 413 |
| ZIP SHA-256/내부 해시/manifest/형식 불일치 | 422 |
| 경로 조작 6종, 중복 ZIP 항목, ZIP 심볼릭 링크 | 모두 거부 |
| 확장 크기 제한 | 테스트 한도를 낮춰 거부 확인 |
| 동일 UUID 4개 동시 업로드 | 한 파일·새 업로드 1개·이벤트 1개 |
| 같은 UUID 다른 내용 | 409 |
| 재업로드 보존 시간 | 연장 없음 |
| 기록 지연 시 업로드 완료 시각 | fsync 후 테스트 시각을 기준으로 +48시간 |
| 만료 1μs 전 / 만료 정각 | 200 / 410 |
| 미삭제 파일 다운로드 | 만료 정각 410, 개별 파일도 차단 |
| 6시간·1시간 임계 이벤트 | 중복 실행·저장소 재생성 후에도 각각 1개 |
| 중지 후 알림 따라잡기 | 유효 기간 안에서만 각 임계 이벤트 1개 |
| 만료 후 사전 알림 | 생략 |
| 파일 삭제 실패 | 이벤트/삭제 완료 상태 없음, 다운로드는 계속 차단 |
| 삭제 재시도·이미 없는 파일 | 정상 완료, 삭제 이벤트 1개 |
| 실제 주기 작업 | 테스트에서 30ms 주기로 동작시켜 삭제 확인 |
| 재시작 후 만료 상태 | 계속 410, 이벤트 중복 없음 |
| 디스크 기록 실패 | 파일과 메타데이터 남지 않음 |
| 저장 파일 변조/유실 | 503, 다운로드 이력 추가 안 됨 |
| DB 경로 변조/저장 링크 | 외부 파일을 읽거나 삭제하지 않음 |
| 커밋 전 중단 흔적 | 메타데이터 없는 서버 생성 ZIP 정리, 무관 파일 유지 |
| SQLite 전용 백업 | 메타데이터만 생성, ZIP/이미지 복사 없음, 기존 백업 덮어쓰기 거부 |

시간 경계는 주입한 UTC 시계로 검증했습니다. 실제 48시간을 기다리지 않았습니다.
정리 작업 기본값은 300초이며 주기 실행 테스트만 짧게 설정했습니다.
저장 링크 검사는 Windows 심볼릭 링크 생성 권한 없이 링크 판정을 모의하여 확인했습니다.
ZIP 심볼릭 링크 메타데이터 거부는 실제 ZIP 파일로 확인했습니다.

## 남은 실제 환경 시험

- Ubuntu/Python 3.11 서비스 실행, POSIX 권한, 프로세스 강제 중단/정전 복구.
- HTTPS 리버스 프록시의 디스크 버퍼·캐시 비활성화와 업로드 한도.
- 100 MiB 최대 용량 및 동시 요청 부하/메모리 측정.
- 운영 백업·VM 스냅샷에서 콘텐츠 볼륨 제외 여부. 외부 백업 설정은 이 작업에서 변경하지 않았습니다.
- 기기별 인증/권한 격리, PostgreSQL, FCM/Android 및 GUI 업로드 연결.
- 네이버 스마트에디터 붙여넣기는 기존 [별도 실제 시험](naver-paste-test.md) 상태를 유지합니다.
