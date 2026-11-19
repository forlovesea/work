# Phase 1 검증 결과

검증일: 2026-11-17 (Asia/Seoul). 환경: Windows, Python 3.10.11, 프로젝트 .venv.

## 완료

- `.venv/Scripts/python -m pytest -q`: **17 passed**, 1 warning.
- `.venv/Scripts/python tests/smoke_local.py`: **PASS**.
  실제 loopback Uvicorn 서버와 별도 CLI 프로세스 실행, 1건 저장,
  flush-only에서 0건 재전송 및 서버 조회 확인. 프로세스와 임시 DB 정리 완료.
- 인증 누락/오류/토큰 미설정 차단, 이벤트 검증, UUID 중복/충돌,
  동시 중복 전송, DB 재개방 후 영속성, 커서 페이지 조회,
  네트워크 장애 및 응답 유실 후 outbox 재전송, 잘못된 인증 후 이벤트 보존 검증.
- JSON Schema 예제 및 서버 이벤트 타입 목록 일치 검증.

Starlette TestClient가 httpx 사용에 대해 deprecation 경고를 출력합니다.
현재 테스트는 통과했으며 향후 테스트 클라이언트 의존성 업데이트 시 호환성을 확인해야 합니다.
설치 버전은 `docs/tested-environment-windows-py310.txt`에 기록했습니다.
이는 Ubuntu/Python 3.11용 공통 lock 파일이 아닙니다.

최초 pytest 실행은 테스트 통과 후 시스템 임시 디렉터리 정리 권한 오류가 발생했습니다.
pytest.ini에서 전용 `.pytest-tmp` 디렉터리를 사용하도록 수정한 최종 실행은 해당 오류 없이 종료했습니다.
이 디렉터리는 pytest가 재생성하므로 사용자 파일을 보관하지 마세요.

## 검증 필요 / 미구현

Python 3.11 및 Ubuntu 20.04 실환경은 아직 검증하지 않았습니다.
PostgreSQL/SQLAlchemy/Alembic, WebSocket/FCM, Android 실제 수신, GUI/AI,
파일 출력/업로드/48시간 만료, 네이버 발행, EXE/APK는 후속 단계입니다.
공인 서버 접속/배포, 운영 DB 및 방화벽 변경을 수행하지 않았습니다.

Git 상태 조회는 상위 저장소의 dubious ownership 경고로 실패했습니다.
전역 Git 설정을 변경하거나 커밋/푸시하지 않았습니다.
