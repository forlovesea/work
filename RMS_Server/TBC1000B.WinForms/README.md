# TBC1000B WinForms 포팅

`TBC1000B_감시프로그램_V3.2.3.py`와 `Main_GUI_캡처/Lastest`를 기준으로 진행하는 병렬 포팅 프로젝트입니다. Python 원본은 변경하지 않습니다.

## 현재 구현 범위

- 프로파일 선택 화면
- 메인 화면의 접속 설정, 현장 정보, 시스템 요약, Trap, 모듈 상태, 설치 순서, 고장 정보 영역
- 운전 데이터 기록 설정 화면
- 전체 모듈 상세정보 화면
- Active Alarm List
- 모듈 설치 순서 설정 화면
- 외부 패키지 없는 SNMPv2c GET/GETBULK/SET BER 코덱과 UDP 클라이언트
- Trap UDP 수신 및 community 필터
- Huawei TBC1000B MIB의 모듈·셀 데이터 매핑
- EPO 준비/차단 SET와 응답값 검증
- 기존 `profiles/*.ini` 읽기, 생성, 삭제 및 접속정보 저장
- 외부 패키지 없는 XLSX 운전 데이터 주기 기록과 날짜별 파일 분리
- 전체 모듈 순차 차단·복구와 모듈별 진행상태
- 충전전류 제한과 SOC 충전 제한 SET 후 GET 검증
- 누락 Trap 재전송 요청
- 활성 경보/Fault 자동 반영과 레벨별 경보음
- 모듈 설치 순서 중복 방지 및 프로파일 저장
- 연속 timeout 5회 경고 및 30회 자동 종료

## 빌드

.NET 8 SDK 이상이 설치된 Windows에서:

```powershell
dotnet build .\TBC1000B.WinForms\TBC1000B.WinForms.csproj
dotnet run --project .\TBC1000B.WinForms\TBC1000B.WinForms.csproj
```

저장소 루트에서 빌드 스크립트를 실행할 수도 있습니다. 로컬 `.dotnet` SDK가 있으면 우선 사용하고, 없으면 시스템에 설치된 .NET 8 SDK를 사용합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\TBC1000B.WinForms\build.ps1
```

현재 접속 버튼은 입력된 장비로 실제 SNMP 패킷을 전송합니다. EPO는 개별 또는 전체 확인창에서 실행한 경우에만 전송됩니다. 운전 데이터 기록은 `Operation data record` 폴더에 날짜별 XLSX로 저장됩니다.

## 로컬 통합 시험

```powershell
dotnet run --project .\TBC1000B.WinForms.SmokeTests\TBC1000B.WinForms.SmokeTests.csproj
```

가짜 UDP 장비를 이용해 GET/SET, Trap 및 Huawei MIB 데이터 배율을 검증합니다.

## 릴리스

- `publish/framework-dependent/TBC1000B_Monitor.exe`: 약 0.50MB. 대상 PC에 .NET 8 Desktop Runtime 설치 필요
- `publish/self-contained/TBC1000B_Monitor.exe`: 약 64.9MB. 별도 .NET 설치 없이 실행 가능하며 함께 게시된 네이티브 DLL/Assets 필요

실제 장비 `10.0.0.3:161`에서 읽기 전용 시험으로 sysUpTime, 577개 Huawei OID와 모듈 10개의 전압·전류·상태·SOC·SOH 매핑을 확인했습니다. GETBULK는 응답 유실을 피하기 위해 요청당 10개로 운용합니다.

Master/Slave는 Python 원본과 동일하게 UDP 50000 등록, 5초 heartbeat, 12초 생존 판정, 51000~52000 로컬 Trap 포트 및 장비 IP별 Trap 전달을 사용합니다.
