# TCP 업로드 프로토콜 v1

monitoring-client → 서버 수집 연결은 TCP/TLS입니다. Android 조회 API는 HTTPS 설계를 유지합니다.

## 프레이밍

- 기본 포트 9443 (변경 가능), 운영 기본 TLS + 인증서/호스트 검증
- `4바이트 unsigned big-endian 본문 길이` + `UTF-8 JSON 본문`
- 본문 최대 16 MiB, NaN/Infinity 불허
- TCP 수신은 분할될 수 있으므로 헤더/본문 모두 지정 길이만큼 반복 수신
- 같은 연결에서 업로드 → ACK 반복, 동시에 ACK 대기하는 메시지는 한 건
- 클라이언트 연결/소켓 I/O 타임아웃 4초, 실패 시 동일 sample_id로 재전송

## 메시지

```json
{
  "type": "upload",
  "token": "collector-issued-token",
  "payload": {
    "schema_version": 1,
    "sample_id": "uuid-generated-once",
    "captured_at": "2026-09-28T00:00:00+00:00",
    "site_id": "site-01",
    "device_id": "battery-01",
    "kind": "snapshot",
    "data": {}
  }
}
```

kind는 snapshot 또는 trap입니다. captured_at은 큐 저장용 데이터를 만든 시각입니다. SNMP 마지막 성공 수신 시각은 data.last_poll_at이며 재전송 시 sample_id와 시각을 바꾸지 않습니다. 서버는 received_at을 별도로 기록합니다.

snapshot data 필드: source_version, mode, site_name, system_name, equipment_ip, connected, last_poll_ok, last_poll_at, last_poll_error, last_trap_at, snmp_fail_count, snmp_total_fail_count, raw_oids, module_map, module_data, row_to_module, equip_to_module, module_order, module_barcodes, active_alarms, faults, active_fault_keys, total_capacity, group_soh, summary_table, module_tables, fault_table, epo_status.

원본 데이터 키와 배열을 보존하며 딕셔너리 키는 JSON 문자열로 변환합니다. module_data의 cells는 V, temps는 ℃, volt는 V, current는 A, soc/soh는 %입니다. 수집 불가 값은 null입니다. 원본이 표현한 상태/센티널 값은 raw_oids에 그대로 유지됩니다.

trap data 필드: received_at, raw_trap, monitored_ip. raw_trap의 `_source_ip`가 실제 발신 장비이며 현재 프로필과 다를 수 있습니다. 발생/복구 Trap OID를 그대로 보존합니다.

## ACK

```json
{"type":"ack","sample_id":"uuid-generated-once","ok":true}
```

ACK도 같은 길이 헤더를 사용합니다. **DB 트랜잭션 커밋 후** 반환해야 합니다. 운영 서버는 인증된 수집기 ID + sample_id로 중복 제거하고 이미 저장된 메시지에도 성공 ACK를 반환해야 합니다.

ok:false, 잘못된 ID 또는 연결 종료 시 클라이언트는 큐를 삭제하지 않습니다. 영구적인 인증/스키마 오류가 계속되면 후속 전송도 대기하므로 운영자가 원인을 수정해야 합니다.

## 서버 구현 상태

`server/`에 TCP/TLS 수신, 토큰/현장/장비 검증, 크기/연결 제한, JSON/시각 검증, 중복 제거, 이력/최신 snapshot 저장, ACK와 DB 백업을 구현했습니다. 서버의 생성된 클라이언트 설정을 수집기에 입력해 연결합니다. 최신 snapshot은 captured_at으로 선택하므로 측정 데이터의 신선도는 last_poll_at과 연결 상태를 별도로 확인해야 합니다.

알람 판정/발송과 독립적인 수집 중단 감시는 구현했습니다. [알람·푸시 안내](alarms-and-push.md)를 참고하세요. 세밀한 요청 빈도 제한은 후속 범위입니다.

## 전체 운영 설계 항목

- 토큰별 현장/장비 권한, 요청 크기/빈도 제한, 필드/시각 검증
- 중복 알림 억제, 과거 재전송과 최신 상태 구분
- last_poll_at이 오래되거나 비정상 미래 시각이면 정상 최신 데이터로 표시하지 않음
- TLS 인증서, 토큰 발급/폐기, DB 백업, 별도 작업의 수집 중단 감지
- 별도 알람 판정 및 푸시 발송 큐

test_receiver.py는 로컬 프레이밍·저장·ACK 시험 도구이며 운영 기능은 제공하지 않습니다. 기존 telemetry.example.json은 초기 정규화 형식 초안이고 현재 수집기 wire 형식은 이 문서를 따릅니다.
