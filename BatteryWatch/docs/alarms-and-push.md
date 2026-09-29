# 서버 알람과 푸시

알람 평가는 수집 요청과 독립적으로 기본 5초마다 실행됩니다. SQLite에 활성 상태·발생/복구 이벤트·사용자 확인·발송 큐를 저장합니다. 재시작 후에도 상태를 보존합니다.

## 기본값

- 측정 통신 중단: `last_poll_at`이 없거나 미래이거나 60초보다 오래된 경우. `connected=false`나 `last_poll_ok=false`이면 즉시 불량으로 처리합니다.
- 한 번도 수신하지 못한 등록 장비: 서버 시작 후 60초부터 통신 중단으로 판단합니다.
- 장비 자체 알람: `active_alarms` 집합이 비어 있는지에 따라 발생/복구를 기록합니다.
- SOC·셀 온도·전압·편차 규칙은 운영 기준 미확정으로 기본 비활성입니다.

## 임계값 설정

아래 값은 형식 예시이며 운영 권장값이 아닙니다. 장비 사양을 확인한 후 설정하세요. 현재 규칙은 모든 등록 장비에 공통 적용됩니다.

```json
"alarms": {
  "scan_seconds": 5,
  "stale_seconds": 60,
  "rules": [
    {"id":"soc_low","enabled":false,"metric":"soc","direction":"low","threshold":20,"hysteresis":5,"duration_seconds":30},
    {"id":"temperature_high","enabled":false,"metric":"temps","direction":"high","threshold":50,"hysteresis":3,"duration_seconds":30},
    {"id":"cell_voltage_high","enabled":false,"metric":"cells","direction":"high","threshold":3.6,"hysteresis":0.1,"duration_seconds":30},
    {"id":"cell_imbalance","enabled":false,"metric":"cell_delta","direction":"high","threshold":0.2,"hysteresis":0.05,"duration_seconds":30}
  ]
}
```

단위: SOC %, 온도 ℃, 전압/편차 V. low는 미만, high는 초과가 발생 조건입니다. 복구 경계에는 low의 경우 hysteresis를 더하고 high에서는 뺍니다. 경계에 도달하면 복구합니다.
지속시간은 서로 다른 성공 측정의 시각으로 계산합니다. 같은 데이터 재전송은 누적되지 않습니다. 결측과 오래된 데이터는 발생 대기를 중단하지만 활성 수치 알람을 복구하지 않습니다.
활성 규칙을 비활성화/삭제해도 기존 알람은 자동 복구되지 않습니다. 재활성화 후 정상 측정으로 복구할 수 있습니다.
최신 snapshot을 평가하므로 평가 사이에 사라진 짧은 상태를 모두 검출하지는 않습니다. Trap 원문은 별도 수신 이력에 보존합니다.
업로드 간격에 맞게 `stale_seconds`를 조정하세요.

## API

`Authorization: Bearer <조회 토큰>`이 필요합니다. 업로드 토큰과는 별개입니다.

| 메서드 | 경로 | 내용 |
|---|---|---|
| GET | `/api/v1/devices` | 허용 장비 목록 |
| GET | `/api/v1/snapshot?site_id=…&device_id=…` | 최신 원본 측정·신선도 |
| GET | `/api/v1/history?site_id=…&device_id=…&limit=20` | 최근 업로드/Trap 이력, 최대 100개 |
| GET | `/api/v1/alarms?site_id=…&device_id=…` | 활성 알람·최근 발생/복구 100개 |
| POST | `/api/v1/acknowledgements` | `{"event_id":"…"}` 사용자 확인 |
| PUT | `/api/v1/push-devices/{UUID}` | `{"token":"FCM 토큰"}` 기기 등록/갱신 |
| DELETE | `/api/v1/push-devices/{UUID}` | 기기와 대기 발송 해제 |

사용자 확인은 알람 복구가 아닙니다. 조회/확인/등록에 계정별 권한을 검사합니다. 변경 본문은 8 KiB로 제한합니다.

## Firebase 서버 설정

```powershell
python -m pip install -r requirements-push.txt
```

서버 설정 파일에 다음을 추가하고 재시작합니다. 상대 경로는 서버 설정 파일 기준입니다.

```json
"push": {"enabled":true,"service_account":"secrets/firebase-service-account.json"}
```

서비스 계정은 앱의 `google-services.json`과 별개이며 APK에 포함하지 않습니다. 경로를 생략하면 Application Default Credentials를 사용합니다.
푸시가 비활성일 때도 등록된 기기별 큐는 유지됩니다. 활성화하면 대기 이벤트가 발송될 수 있습니다.
실패 시 5초부터 최대 1시간 간격으로 재시도합니다. 폐기된 토큰은 제거하고 권한이 없어진 수신자는 발송하지 않습니다.
전송 성공과 DB 기록 사이의 중단으로 중복될 수 있어 event_id를 알림 태그로 사용합니다. 전송 성공은 휴대폰 표시/사용자 확인과 다릅니다.
기기 등록 이전의 이벤트는 소급 발송하지 않습니다. 앱의 알람 이력에서 확인합니다.

운영 인증서·Firebase 자격증명·임계값을 준비한 후 실제 장비와 휴대폰에서 검증해야 합니다.
참고: [Android FCM](https://firebase.google.com/docs/cloud-messaging/android/get-started), [Admin SDK 발송](https://firebase.google.com/docs/cloud-messaging/send/admin-sdk).
