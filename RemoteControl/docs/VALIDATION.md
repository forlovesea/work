# 검증 결과

2026-11-06 · Host 연결 종료 개선

- 연결 상태와 원격 화면을 먼저 정리하고 접속 화면을 복원한 뒤, 캡처한 이전 세션 소켓을 `host-close` 스레드에서 닫도록 변경했습니다. 목록 갱신/앱 종료의 소켓 정리도 메인 스레드 밖으로 이동했습니다.
- `:app:assembleHostDebug :app:testHostDebugUnitTest :app:lintHostDebug` 성공. 기존 JVM 테스트 31개 통과, 실패/오류 0개. Lint 오류 0개, 경고 8개.
- 확인용 APK: `dist/RemoteControl-host-disconnect-fix.apk` (버전 0.4.5 유지).
- 연결된 Android 기기가 없어 실제 연결 종료/즉시 재접속/UI 복귀는 미검증입니다. 기존 JVM 테스트는 이 UI 수명 주기 동작을 직접 검증하지 않습니다. 실기 확인 항목은 `DEVICE_TESTS.md`에 추가했습니다.

2026-10-04 · Windows 개발 환경

| 검사 | 결과 |
| --- | --- |
| Host Debug APK 빌드 | 성공 |
| Target Debug APK 빌드 | 성공 |
| Host JVM 테스트 | 21개 통과 |
| Target JVM 테스트 | 21개 통과 |
| Android Lint | 두 역할 모두 오류 0개, 경고 있음 |
| Python 중계 테스트 | 9개 통과 (포트 범위 검사 포함) |
| Ubuntu 20.04 실제 서비스 실행 | 미검증 |
| 실제 기기 화면 공유 / 접근성 제어 | 미검증 |
| LTE / 서로 다른 Wi-Fi 환경 접속 | 미검증 |

JVM 테스트는 접속 정보 형식·포트·좌표 검증, 올바른 인증서 지문의 TLS 데이터 교환, 잘못된 지문의 TLS 거부를 포함합니다. 중계 테스트는 양방향 바이트 전달, 중복 Target/Host 거부, 알 수 없는 방/프로토콜 거부, 대기 만료, Target 연결 종료 후 방 정리, 접속 수 제한을 포함합니다.

v0.2.0 상태 표시 검사에는 초기 응답/첫 화면 대기, 제어 가능/보기 전용/권한 해제 구분, 지연·무응답·시간 초과 전환, 빠른 응답 복구, 중복/잘못된 상태 응답 거부, 정지 화면 정상 유지, 재접속 시 이전 상태 제거가 포함됩니다. 이전 통신 버전의 접속 정보 거부도 검사했습니다. APK를 양쪽 모두 업데이트해야 합니다. 상태 표시줄의 실제 기기 배치와 LTE 지연 상태는 실기 검증이 남아 있습니다.

APK는 `dist/`에 있으며 같은 폴더의 `SHA256SUMS.txt`에 해시가 기록됩니다. Lint 상세 결과는 `app/build/reports/lint-results-hostDebug.html`과 `lint-results-targetDebug.html`에 생성됩니다. Target의 자체 인증서 고정 검증에는 의도적인 사용자 정의 TrustManager를 사용하며 공인 중계서버 연결에는 Android 기본 인증서 검증과 호스트명 검증을 사용합니다.

v0.3.0에서는 응답 시간별 세분화 경계, 무응답 시 빨강 진하기, 진행 중 응답 대기에 따른 악화, 반복 지연 감지, 최근 10회 표본의 회복 및 재접속 초기화, 10개 색상 구분 테스트를 추가했습니다. 두 APK 빌드와 Lint 오류 0개를 확인했습니다. 실제 기기에서의 색상 가독성과 체감 제어 품질 비교는 미검증입니다.

자동 검사는 Android 시스템 MediaProjection/Accessibility 및 실제 LTE 네트워크의 동작 검증을 대체하지 않습니다. [실기 체크리스트](DEVICE_TESTS.md)에 따라 추가 검증해야 합니다.

## 2026-11-16 장시간 대기 개선 검증

- 변경: 배터리 최적화 제외 안내/상태, 제외 상태의 연결 서비스 CPU 유지(60초 만료, 10초 갱신), 45초 무진행 소켓 감시, 연결 실패 시 절전 상태 진단 로그.
- Host/Target Debug 빌드 및 기존 JVM 테스트 각각 31개 통과. Lint 오류 0개(Host 경고 8개, Target 경고 2개).
- 실제 Android 절전/제조사 제한, 3~4일 대기, 네트워크 정지 후 감시 복구는 실기 미검증. 기존 JVM 테스트가 서비스 및 WakeLock 수명 주기를 검증하는 것은 아님.
- 수정 APK는 dist/RemoteControl-target-debug.apk. 기존 릴리스 APK는 변경하지 않음.
