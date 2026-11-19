# Windows·서버·Android 통합 시험 결과

정리일: 2026-11-19 (사용자 시간대 Asia/Seoul).
실행 호스트의 원본 로그에는 2026-11-18이 기록되어 있으며 원본 시각을 변경하지 않았습니다.
**운영 서버 변경·배포·실제 네이버 게시·실제 Firebase 발송은 수행하지 않았습니다.**

## 결과와 실행 범위

| 검사 | 결과 | 실제 실행 범위 |
|---|---|---|
| Python 회귀·통합 | 76 passed, 1 warning, exit 0 | Windows 서비스·GUI, FastAPI/SQLite, 기존 Phase 1~5 |
| Android 단위/Mock | 14개 통과 | Robolectric API 28 |
| Compose 버튼 흐름 | 1개 통과 | Mock 설정 → 다운로드 → 미리보기/복사 → 수동 완료 신고 |
| Android 실제 서버 통신 | 1개 통과, skip 0 | 실제 Kotlin HttpApi/OkHttp/WebSocket와 로컬 Uvicorn 연결 |
| Android 합계 | 16개 통과, 실패/오류 0 | 실제 단말은 사용하지 않음 |
| Android 빌드/Lint | BUILD SUCCESSFUL, 오류 0 / 경고 26 | assembleDebug/testDebugUnitTest/lintDebug |
| APK 서명 | apksigner v2 검증 통과 | 개발용 Debug 서명 |
| Windows EXE | PyInstaller 빌드·자체 실행 시험 통과 | Windows 10 x64, Qt offscreen |
| Ubuntu 실행 환경 | 미실시 | 같은 서버 코드는 Windows에서 실행; Ubuntu 커널/systemd/Nginx는 미검증 |

환경: Windows 10 build 19045, Python 3.10.11, PyInstaller 6.16.0,
JDK 17.0.20.1, Gradle 8.11.1, AGP 8.9.2, Kotlin 2.1.20, Android SDK 35.
[Python 패키지 버전](integration-python-environment.txt).

## 요구 시나리오별 증거

| 시나리오 | 검증 결과 | 근거 및 한계 |
|---|---|---|
| 네트워크 장애 | 통과 | 실제 루프백 TCP 연결 거부 → SQLite 이벤트/ZIP 보존 → Windows 서비스 재생성 → 전송 복구 |
| 업로드 응답 유실 | 통과 | 서버 저장 뒤 응답만 유실시켜 재시도, 동일 SHA/UUID/new=false, 중복 업로드·보존 시간 연장 없음 |
| 로그인 상태 이벤트 | 통과 | 성공/실패/만료 신고를 서버·Android로 전달, 자동 로그인 검증 아님 |
| 발행 실패 | 통과(신고/장애 주입) | PUBLISH_FAILED → MANUAL_PUBLISH_REQUIRED, 실제 네이버 자동 발행을 시도하지 않음 |
| 자동 패키지 생성 | 통과 | 실패 기록·전달 버튼에서 HTML/TXT/DOCX/PNG/manifest ZIP 생성, 고정 파일로 재시도 |
| 서버 업로드 | 통과 | 실제 HTTP 업로드·인증·SHA 검사·중복 처리, GUI 버튼 연결도 별도 검사 |
| Android 이벤트/알림 | 통과(전송 경계 Mock) | 실제 WS 완료 이벤트, 서버 FCM adapter가 만든 데이터 캡처 → 실제 Android 알림 생성/UUID 중복 제거 |
| 콘텐츠 다운로드 | 통과 | 실제 Android HttpApi로 ZIP/Word 다운로드·해시 검증, 3개 이미지 순서·inline HTML·전체 텍스트 확인 |
| 수동 발행 완료 | 통과(사용자 신고) | Compose 명시적 확인 → 서버 API → MANUAL_PUBLISH_COMPLETED → WS/알림, 같은 요청 멱등·다른 URL 409 |
| 6시간·1시간 알림 | 통과 | 주입 시계로 임계점 이동, 중복 정리 실행에도 각 이벤트 1개, FCM 발송 경계 데이터 확인 |
| 정확히 48시간 만료 | 통과 | 만료 1μs 전 200, 만료 순간 파일이 남아 있어도 410 |
| 파일 삭제 | 통과 | 유지관리 실행 후 ZIP 제거, 삭제 이후에도 410, 반복 실행 멱등 |
| 5분 정리·삭제 실패 | 통과(가상 대기) | 300초 재시도 인자 확인, 디스크 오류 후 다음 주기 재실행, 기존 파일 잠금/삭제 재시도 시험 포함 |
| 보안·백업 제외 | 코드 시험 통과 | 인증/만료/권한, 경로 조작, 용량, 무결성, 메타데이터 전용 백업 회귀 시험; 운영 백업 도구 제외 설정은 미적용 |

48시간 실제 대기를 수행한 결과가 아니라 서버의 주입 가능한 시계로 경계를 검증한 결과입니다.
5분 삭제 주기는 실제로 5분 대기하지 않고 scheduler wait 인자와 재시도 동작을 검증했습니다.
서버가 정지해 있거나 디스크 삭제가 실패하면 물리 삭제는 늦어지지만 만료 API 차단은 독립적으로 유지됩니다.

FCM은 실제 Google 네트워크를 통과하지 않았습니다. 가짜 발송기가 캡처한 payload를 Robolectric의
NotificationManager에 전달했고 별도 기존 시험에서 PushHints 처리·중복 제거·커서 보존을 확인했습니다.
실기기 Wi-Fi 단절/복구, 절전/백그라운드 정책, Android 13+ 권한과 실제 푸시 수신은 통과로 표시하지 않습니다.

## 재현과 산출물

```powershell
.venv/Scripts/python -m pytest -q
# JAVA_HOME/ANDROID_HOME 설정 필요
.venv/Scripts/python tests/integration_live.py
.venv/Scripts/python -m PyInstaller --noconfirm windows-app/AI-Blog-Auto.spec
# EXE 자체 실행: build-and-deploy.md 참고
.venv/Scripts/python tests/package_release.py
```

- [실제 통합 실행 요약](../build/integration/result.json)
- [Android 테스트 보고서](../android-app/app/build/reports/tests/testDebugUnitTest/index.html)
- [Android Lint 보고서](../android-app/app/build/reports/lint-results-debug.html)
- [Windows EXE 자체 시험](../build/exe-smoke/result.json)
- [Windows 실행 폴더 ZIP](../build/deliverables/AI-Blog-Auto-Windows-x64.zip)
- [Android 개발용 APK](../build/deliverables/AI-Blog-Monitor-debug.apk)
- [Ubuntu 소스 배포 묶음](../build/deliverables/AI-Blog-Ubuntu-source.tar.gz)
- [산출물 크기·SHA-256](../build/deliverables/SHA256SUMS.json)
- [빌드·Ubuntu 설치·백업·롤백 절차](build-and-deploy.md)

Windows ZIP은 압축 해제 후 `_internal`을 포함한 폴더 전체를 유지해야 합니다.
Ubuntu 묶음은 소스와 템플릿이며 가상환경·비밀정보·운영 DB·콘텐츠 파일이 없습니다.
Windows EXE Authenticode와 Android 정식 배포 키 서명은 포함하지 않았습니다.

## 수정 및 남은 실제 시험

통합 중 Windows 로그인 이벤트 전송, GUI 패키지 업로드/재시도, Android 수동 완료 신고를 연결했습니다.
GUI 종료를 반복할 때 예약 엔진이 이미 종료되었다는 오류도 발견하여 stop을 반복 호출 가능하게 수정했습니다.
Python 경고 1개는 기존 Starlette/httpx 폐기 예정 안내입니다.
Android Lint 26개는 의존성 최신 버전, SharedPreferences, KTX 권고입니다.
SDK XML 버전 안내와 LiveIntegrationTest의 환경변수 nullable 타입 컴파일 경고 2개가 있지만 빌드·검사는 성공했습니다.

다음은 별도 환경에서 확인해야 합니다.

1. Ubuntu 시험 서버의 systemd/Nginx 설정 검사, POSIX 권한, TLS·재시작·실제 백업/스냅샷 제외.
2. Windows 11 새 사용자 계정에서 설치·Credential Manager·실제 화면과 클립보드.
3. 실제 Android 단말의 Wi-Fi/절전/FCM/Keystore/SAF와 대용량 파일·저장 공간 부족.
4. [네이버 스마트에디터 붙여넣기](naver-paste-test.md)와 실제 사용자의 수동 게시 확인.
5. 장시간·부하·최대 용량 환경의 삭제 지연/메모리 사용 측정.

네이버 자동 발행은 비활성화되어 있습니다. 종료된 공식 API/URL Scheme 대신 비공식 기능으로 우회하지 않습니다.
[공식 근거와 발행 정책](naver-publication-policy.md)을 참조하세요.
