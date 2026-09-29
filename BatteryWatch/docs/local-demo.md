# 로컬 실행 및 전체 연동 검증

## 장비 없이 앱 화면 확인

`server/demo.bat`을 실행합니다. 별도 패키지 설치 없이 Python 3.10 이상에서 동작합니다.

```powershell
cd BatteryWatch\server
demo.bat
```

- 수집 TCP: `127.0.0.1:19443`
- 앱 조회 API: `127.0.0.1:18443`
- 앱 설정값: `server/demo-data/android-connection.local.json`
- 데모 DB와 토큰: `server/demo-data/`에만 저장하며 기존 운영 설정을 읽지 않습니다.
- 장비 이름: `demo-site / DEMO-simulated-battery`

기존 [조회용 APK](../dist/BatteryWatch-viewer-debug.apk)를 설치한 뒤 앱 설정에 조회 주소와 위 파일의 토큰을 입력합니다.
에뮬레이터에서는 주소를 `http://10.0.2.2:18443`으로 지정합니다.

USB로 연결한 Android 휴대폰은 USB 디버깅을 허용하고 Android SDK의 adb로 포트를 연결합니다.

```powershell
adb reverse tcp:18443 tcp:18443
```

이 경우 앱 주소는 `http://127.0.0.1:18443`입니다. 시험 종료 시 `adb reverse --remove tcp:18443`으로 해제합니다.
제공된 debug APK만 이 로컬 HTTP 경로를 허용합니다. 서버를 LAN에 평문으로 노출하는 방식은 사용하지 않습니다.

정상 → 저 SOC → 복구 → 통신 실패를 각 15초씩 반복합니다. 화면에서 SOC와 활성 알람/발생·복구 이력이 바뀌는 것을 확인할 수 있습니다.
모든 값과 임계값은 **시뮬레이션 전용**입니다. FCM이나 실제 배터리에 연결하지 않습니다. 푸시 수신 검증을 대신하지 않습니다.
종료는 Ctrl+C이며 같은 폴더로 다시 실행하면 데모 토큰과 이력을 유지합니다.
포트 충돌 시 `demo.bat --api-port 18444 --upload-port 19444`처럼 변경합니다.

## 한 번에 자동 검증

```powershell
python server.py self-test
```

임시 DB와 임의의 루프백 포트를 사용하므로 설정 파일 없이 실행할 수 있습니다. 실행 후 임시 데이터는 정리됩니다.
실제 TCP 업로드/ACK, 중복 제거, Android HTTP 조회, 알람 발생/복구, 확인 기록, 발송 재시도(가짜 발송기), 통신 중단, 권한과 저장 지속성을 검증합니다.
성공하면 JSON의 `ok`가 `true`이고 12개 검사 항목을 출력합니다. 실패하면 종료 코드가 0이 아닙니다.

## 운영 설정 점검

```powershell
python server.py doctor
python server.py --config server.local.json doctor --android-config ..\android-app\app\google-services.json
```

토큰이나 개인 키를 출력하지 않고 설정·포트·인증서/키 로드·API 활성화·임계값·Firebase 라이브러리/프로젝트 일치 여부를 확인합니다.
`ok=true`는 설정 검사 통과이며 실제 통신/푸시 성공을 의미하지 않습니다. `warning`에는 비활성인 기능과 추가 현장 확인 항목이 표시됩니다.

## 실제 운영으로 전환할 때 필요한 값

1. 운영 서버 주소와 일치하는 HTTPS 인증서, 수집 및 조회 포트
2. 실제 현장/장비 ID와 업로드·조회용 별도 토큰
3. Firebase 프로젝트의 Android 설정과 서버 서비스 계정
4. 해당 축전지의 운영 임계값·지속시간·복구 폭

실제 값은 데모 설정과 분리해서 구성합니다. [알람 및 푸시 설정](alarms-and-push.md)을 참고하세요.
