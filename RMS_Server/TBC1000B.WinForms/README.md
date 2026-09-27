# TBC1000B WinForms v3.2.6

`TBC1000B_감시프로그램_V3.2.3.py`와 `Main_GUI_캡처/Lastest`를 기준으로 진행하는 병렬 포팅 프로젝트입니다. Python 원본은 변경하지 않습니다.

## v3.2.6 변경 사항

- Python v3.2.6의 모듈 갱신 시간, SOC 표시, 모듈/셀팩 전압 및 접속 시스템 타입 표시 반영
- 모듈 테이블의 제목과 값에 맞춘 열 너비 조정 및 경보 영역 확보
- 접속 설정 영역을 창 너비에 따라 한 줄 또는 두 줄로 배치
- 접속 입력칸에서 Enter로 접속 시작, 누락된 입력칸으로 자동 이동
- 기록 기간 입력칸에 `30일` 형식으로 단위 표시
- Timeout 자동 종료 시 접속 버튼, 상태 표시 및 시스템 타입 초기화
- VS Code에서 F5로 Debug 빌드 및 실행 (`TBC1000B.WinForms` 폴더를 열어 사용)

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

## 최종 고객 배포: 단일 EXE (v3.2.6)

`powershell -NoProfile -ExecutionPolicy Bypass -File .\package-final.ps1`

- 전달 파일: `Final/TBC1000B_Monitor_v3.2.6.exe` 하나만 복사합니다.
- Windows x64용이며 이미지와 경보음을 포함합니다. .NET 런타임은 제외한 경량 배포본입니다. 고객 PC에 .NET 8 Desktop Runtime(x64)이 설치되어 있어야 합니다.
- 실행 시 내장 구성 요소를 사용자 임시 캐시에 자동으로 풉니다.
- 설정과 기록은 원본 EXE 옆에 생성되므로 쓰기 가능한 로컬 폴더에 두십시오.
- 이전 Final은 새 빌드 성공 후 `artifacts/single-exe-*/previous-Final`에 보관됩니다.
- 단일 EXE의 리소스는 추출된 어셈블리 옆 Assets에서 읽고, 사용자 데이터는 원본 프로세스 경로를 기준으로 저장합니다.