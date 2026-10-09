# 실제 기기 검증 체크리스트

상태: 아직 실제 기기에서 검증하지 않음. 두 대의 Android 기기와 TLS 인증서가 설정된 공인 중계서버가 필요합니다.

- [ ] Target에서 서버 연결을 시작하고 홈으로 이동해도 연결 유지 알림이 남는다.
- [ ] 비행기 모드 켜기/끄기 및 Wi-Fi↔LTE 전환 후 서버에 자동 재접속한다.
- [ ] 화면 공유 중 네트워크 단절 후 Target이 재접속하고 Host 목록에서 해당 기기를 선택해 다시 연결한다.
- [ ] 프로그램 종료 후 연결/공유 알림이 사라지고 네트워크 복구 후에도 재접속하지 않는다.
- [ ] 화면 잠금 및 시스템 공유 중지 후 서버 연결은 유지되고 화면 공유는 다시 승인을 요구한다.

- [ ] Host에 서버 주소와 서버 접속 키를 저장하면 Target 목록을 5초마다 자동으로 갱신한다.
- [ ] 잘못된 접속 키로 목록 조회/기기 등록/원격 연결이 거부된다.
- [ ] Target 이름과 상태(공유 승인 필요/연결 가능/사용 중)가 정확하며 오프라인 기기는 제거된다.
- [ ] 같은 이름의 여러 Target이 ID 뒷표시 없이도 구분 가능한 짧은 ID와 함께 표시되고 선택한 기기로 연결된다.
- [ ] Host/Target 앱 재시작 후 암호화된 서버 설정을 복원한다. 접속 정보 복사/붙여넣기는 필요하지 않다.
- [ ] 전체화면/맞춤/작게 보기 전환과 가로/세로 변경 후 화면 비율 및 터치 좌표가 일치한다.
- [ ] 전체화면에서 보기 옵션, 연결 종료, 기기 뒤로가기로 전체화면 해제가 가능하다.
- [ ] Android 17에서 목록, 키보드 표시, 전체화면 및 원격 화면 조작을 확인한다.

- [ ] LTE↔LTE, LTE↔Wi-Fi, 서로 다른 Wi-Fi 환경에서 각각 접속한다.
- [ ] 기본 포트 55000 및 사용자 지정 포트(예: 58000)에서 서버/방화벽/앱 설정을 맞춰 접속한다.
- [ ] 서버 주소에 범위 밖 포트를 입력하면 거부한다.
- [ ] Host 하단 상태줄이 시스템 내비게이션 영역에 가려지지 않고 색과 설명을 함께 표시한다.
- [ ] 정상 제어 세션은 첫 화면과 상태 응답 확인 후 초록색 및 응답 시간(ms)을 표시한다.
- [ ] 화면 보기 세션은 파랑, 접근성 해제는 노랑으로 표시한다. 접근성 복구 후 다음 응답에 반영된다.
- [ ] 느린 네트워크는 노랑, 5초 무응답은 빨강, 10초 무응답은 연결 종료로 바뀐다.
- [ ] 정지 화면에서도 상태 응답이 오면 정상 상태를 유지한다.
- [ ] 응답 시간 증가 시 10단계 색상/진하기가 구분되며 각 색의 글자가 읽힌다.
- [ ] 빠른 응답과 느린 응답이 반복되면 변동/지연 응답 비율이 올라가고, 최근 한 번의 빠른 응답만으로 초록색이 되지 않는다.
- [ ] 안정된 응답이 이어지면 최근 10회 표본이 갱신되어 정상 색으로 회복한다.
- [ ] 하단 표시줄을 누르면 단계와 측정값의 의미를 확인할 수 있다.
- [ ] 연결을 끊고 새 세션에 접속할 때 이전 상태/응답 시간/늦은 응답이 재사용되지 않는다.
- [ ] 이전 중계서버 연결 시 업데이트 안내가 표시된다.
- [ ] 서버 인증서 불일치/만료/신뢰하지 않는 인증기관인 경우 접속을 거부한다.
- [ ] Target에서 Host 접속 없이 5분 이상 기다려도 대기 연결을 갱신하며 공유 대기를 유지한다.

- [ ] Host APK에는 화면 캡처 서비스/접근성 서비스가 없고, Target APK에만 존재한다.
- [ ] Target의 시스템 화면 공유 요청을 취소하면 포트가 열리지 않는다.
- [ ] 화면 보기 전용 연결에서는 화면만 보이고 모든 제어가 거부된다.
- [ ] 접근성 활성화 + 제어 허용 세션에서 탭/스와이프/홈/뒤로가 실행된다.
- [ ] Host 화면의 상하/좌우 여백을 누르면 제어가 발생하지 않는다.
- [ ] 서버가 제공하는 지문을 잘못 바꾸면 TLS 인증이 실패한다.
- [ ] 일회용 키를 바꾸면 인증이 거부되며 Target에서 새 세션을 시작해야 한다.
- [ ] 첫 Host 접속 후 두 번째 Host는 접속하지 못한다.
- [ ] Target 앱/알림에서 중지하면 화면 전송과 제어가 종료된다.
- [ ] Target 화면 잠금/회전/시스템 공유 종료 시 세션이 종료된다.
- [ ] Host 홈 이동, 종료, Wi-Fi 단절 시 상태와 정리가 확인된다. Host는 10초 무응답 시 종료하며 Target의 단절 감지는 OS TCP 타임아웃에 따라 지연될 수 있다.
- [ ] 새 세션에서 이전 접속 키가 거부된다.
- [ ] Target의 접근성을 꺼도 화면 보기 연결은 유지되지만 터치 실행은 중단된다.
- [ ] Android 8, 13, 14, 15 이상에서 각 권한/알림/화면 공유 수명 주기를 확인한다.
- [ ] 30분 제한과 연속 재접속에서 메모리/소켓/화면 공유 리소스가 정리된다.

검증 시 OS/제조사/기기명/결과를 기록합니다. 접속 키나 개인 화면은 로그에 넣지 않습니다.


## v0.4.3 TLS Keystore regression (device verification pending)

- [ ] Upgrade an existing Target installation with a v3 identity. Restart sharing and confirm `TLS identity=v4 authorizedDigests=` includes `NONE` and `SHA-256`.
- [ ] Confirm `TLS signing self-check algorithm=NONEwithECDSA verified=true` before SHARE registration.
- [ ] On SM-F711N / Android 15 and SM-A235N / Android 14, confirm both handshake-completed events, session token acceptance, and first frame receipt.
- [ ] Restart sharing and reconnect twice; confirm the v4 identity remains usable.
- [ ] Check a fresh Target installation as well as an upgrade.

The previous SHA256withECDSA self-check did not exercise Conscrypt's prehashed NONEwithECDSA signing path. v4 authorizes DIGEST_NONE and retains SHA-256 for certificate signing. Old TLS aliases are retired only after the new signing check succeeds. Private keys remain in AndroidKeyStore and certificate pinning remains enabled.

References: [Android key digest authorizations](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec.Builder#setDigests(java.lang.String...)), [Android 35 Conscrypt signing callback](https://android.googlesource.com/platform/prebuilts/fullsdk/sources/+/refs/heads/androidx-constraintlayout-release/android-35/com/android/org/conscrypt/CryptoUpcalls.java).

## v0.4.4 원격 화면 깨우기 (실기기 검증 대기)

- [ ] Target 서버 연결 후 공유를 시작하지 않고 화면을 끈다. Host의 화면 깨우기로 화면 켜짐 확인을 받는다.
- [ ] 화면이 이미 켜진 경우에도 정상 응답하며 잠금 해제/공유 승인이 자동 실행되지 않는다.
- [ ] PIN 잠금 상태에서 화면만 켜지고 잠금이 유지된다.
- [ ] 공유 중 화면을 끈 뒤 깨운다. OS가 공유를 종료했다면 Target에서 재승인이 필요하다.
- [ ] 깊은 절전/네트워크 차단 시 성공으로 표시하지 않는다. 만료된 미전달 요청은 재접속 후 실행되지 않는다.
- [ ] 연결 종료/앱 종료 후 원격 깨우기가 불가능하다.
- [ ] 구버전 Target 또는 서버에서는 미지원 안내가 표시된다.
- [ ] 두 Host의 동시 요청, 화면 켜기 권한 제한, Samsung Android 15 및 지원 OS별 동작을 확인한다.

## v0.4.5 화면 켜짐 유지 (실기기 검증 대기)

- [ ] 양쪽 앱 업데이트 후 옵션 기본 꺼짐 및 선택 저장을 확인한다.
- [ ] Target 화면 자동 꺼짐 시간을 짧게 설정하고 Host 옵션을 켠 채 공유하여 설정 시간을 지나도 켜져 있는지 확인한다.
- [ ] 보기 전용 연결 및 전체화면에서도 옵션 변경이 가능하다.
- [ ] 옵션 해제/연결 종료/공유 중지 후 정상 자동 화면 꺼짐이 복원된다.
- [ ] 네트워크 차단 시 마지막 신호로부터 15초 안에 화면 유지 잠금이 만료된다.
- [ ] 전원 버튼 잠금을 강제로 해제하거나 화면을 다시 깨우지 않는다.
- [ ] 재연결 시 이전 연결의 유지 잠금이 남지 않는다.
