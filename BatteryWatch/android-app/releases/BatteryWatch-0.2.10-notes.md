# BatteryWatch 0.2.10

- versionCode: 12
- APK: BatteryWatch-0.2.10-offline-debug.apk
- Application ID: com.batterywatch.monitor.offline.debug
- 알람(n): 현재 발생 중인 총 알람 개수. 복구 이력 제외, 장비 알람 요약 중복 제외.
- 활성 알람이 있으면 깜박이며 최고 심각도에 따라 Critical 빨강, Major 주황, Minor 파스텔 노랑, Warning 파스텔 하늘색으로 표시.
- 모두 해제되면 기본 버튼으로 복귀.
- APK 빌드 성공, 기존 단위 테스트 16개 통과, APK 서명 검증 완료. 실제 휴대폰 UI 검증은 별도 필요.
- 로컬 0.2.9 배포 APK와 서명이 같아 업데이트 설치 가능. 0.2.8-alarms-20261006 APK와는 서명이 다름. 해당 구버전에서 설치가 거부되면 서버 연결 설정을 별도 기록한 뒤 기존 앱 제거 및 재설치 필요.
- Firebase 백그라운드 푸시가 없는 offline debug 빌드이며 서버 네트워크 조회는 지원.
