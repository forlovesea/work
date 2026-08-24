# Python → C# 동작 대조표

| 영역 | Python 기준 | C# 1차 상태 | 다음 검증 |
|---|---|---|---|
| 프로파일 | `ProfileDialog` | 기존 INI 읽기, 생성·삭제·접속값 저장 | Master/Slave 런타임 등록 |
| 접속 | `SNMPThread` | sysUpTime, GET/BULK, timeout 2.5초·재시도 1회; 실제 장비 577 OID/10모듈 확인 | 장시간 Polling 안정성 시험 |
| Trap | `SNMPTrapThread` | SNMPv2 Trap UDP 수신·community 필터·1000행 UI | 알람별 상세 OID 매핑·재전송 |
| 요약 | `create_summary_section` | Rack/모듈 집계, 충전전류·SOC 제한 GET/SET, 재검증 연결 | 실제 장비 SET 승인 시험 |
| 모듈 | `create_module_table` | Huawei 18.1/18.2 배율 매핑 및 실제 장비 10모듈 확인 | 경보 상태별 장기 대조 |
| 전체 상세 | `AllModuleDetailDialog` | 40열 UI 구현 | 최고/최저 셀 색상·실시간 갱신 |
| 설치 순서 | `ModuleOrderDialog` | UI 구현 | 중복 방지·프로파일 저장 |
| 운전 기록 | `OperationDataRecordThread` | XLSX 컬럼·파일명·날짜 분리·주기 기록 구현 | Excel 실사용 호환성 대조 |
| Active Alarm | `show_alarm_popup` | Polling 활성 경보, 레벨별 색상, Fault 자동 추가·해제 구현 | 실제 경보 발생·해제 시험 |
| EPO | `EpoCutoffThread` | 개별/전체 확인창, prepare→차단·복구 SET, 모듈별 진행창과 응답 검증 | 실제 장비 차단·복구 시험 |
| 종료 | `closeEvent` | 취소 토큰/서비스 종료 | listener와 작업 완전 종료 |
| Master/Slave | 등록·heartbeat·Trap 전달 | UDP 50000, 51000~52000 자동 포트, IP 필터, unregister 구현/시험 | Python↔C# 혼합 실행 시험 |
| 경보음 | `QSoundEffect` | 레벨 선택, 프로파일 저장, WAV 반복 재생·해제 구현 | 시스템별 음량 체감 시험 |
| 설치 순서 | `ModuleOrderDialog` | Qt 빈 위치 호환, 중복 방지, 저장·복원, 메인 반영 구현 | 실제 Barcode 배치 확인 |
| Timeout | 실패 카운터 | 연속 5회 경고, 30회 자동 종료, 누적 표시 구현 | 네트워크 단절 장시간 시험 |
| 제어 | 충전/SOC/재전송 | SET 타입·범위·순서·GET 검증과 GUI 구현 | 실제 장비 쓰기 승인 시험 |
