# 구현 및 검증 기록 — 2026-09-29

## 후속 완료 사항

- 별도 데이터 폴더와 루프백 포트를 사용하는 실행형 데모 추가 (`server/demo.bat`)
- 실제 TCP → DB → 알람 → Android HTTP API의 12단계 전체 연동 검증 추가 (`server.py self-test`)
- 비밀 값을 출력하지 않는 운영 설정 점검 추가 (`server.py doctor`)
- 서버 자동 테스트 22개 통과. Android 소스와 APK는 이번 후속 변경에서 수정하지 않았습니다.
- 실행형 데모를 64초 구동하여 snapshot 32건 저장과 저 SOC 발생/복구, 통신 실패 발생/복구 이벤트 4건을 확인했습니다.
- [실행 안내](local-demo.md)에 USB 휴대폰 및 에뮬레이터 연결 절차 정리

## 이번 변경

- Android 장비 목록·현재 모듈/셀 상태·측정/Trap 이력·활성 알람/발생/복구 이력·사용자 확인·설정 화면
- 화면을 벗어나면 조회 중단, 조회 실패/오래된 측정 구분, 조회 토큰 암호화 저장
- 서버 독립 알람 평가, 수치 규칙의 지속시간/복구 폭, 결측 시 잘못된 복구 방지
- 알람 상태·이벤트·사용자 확인·기기 등록·발송 큐의 SQLite 영속 저장
- 권한 검사된 알람/기기등록 API, FCM 재시도·폐기 토큰 제거
- Firebase 없는 조회 빌드와 Firebase 푸시 빌드 분리

## 자동 검증

- 서버: `python -m unittest discover -s server/tests` — 18개 통과
- 수집기: `python -m unittest discover -s monitoring-client/tests` — 6개 통과
- Android: `assembleOfflineDebug`, `testOfflineDebugUnitTest` 통과 (단위 테스트 2개)
- Android: `assemblePushDebug`, `testPushDebugUnitTest` 통과 (같은 단위 테스트 2개)
- 푸시 빌드는 명시적인 시험용 Firebase 설정으로 컴파일만 검증했습니다. 해당 설정과 시험용 푸시 APK는 배포하지 않습니다.
- 설치용 조회 APK: `dist/BatteryWatch-viewer-debug.apk`

Windows의 긴 Gradle 경로를 피하기 위해 빌드 때만 임시 드라이브를 사용했고 종료 후 해제했습니다.

## 아직 현장 확인이 필요한 항목

- 실제 장비 → 운영 서버 → 휴대폰의 측정 데이터 연결
- 운영 HTTPS 인증서와 Firebase 프로젝트/서비스 계정 적용
- 실제 FCM 발송·수신, 화면 꺼짐/재부팅/강제 종료/알림 권한 거부/네트워크 복구
- 장비 사양에 맞춘 수치 임계값, 지속시간과 복구 폭 승인/설정 (기본 수치 규칙 없음)

운영 서버 배포나 자격증명 생성은 수행하지 않았습니다. 조회 전용 APK에는 백그라운드 푸시 기능이 없습니다.
