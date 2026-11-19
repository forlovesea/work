# 2026-11-19 개발용 배포 파일

| 파일 | 용도 | 설치 안내 |
|---|---|---|
| [AI-Blog-Auto-Windows-x64.zip](AI-Blog-Auto-Windows-x64.zip) | EXE와 필수 `_internal` 폴더 전체 | [Windows 설치·사용](../../docs/windows-install-use.md) |
| [AI-Blog-Monitor-debug.apk](AI-Blog-Monitor-debug.apk) | Android 개발용 Debug APK | [Android 설치·사용](../../docs/android-install-use.md) |
| [AI-Blog-Ubuntu-source.tar.gz](AI-Blog-Ubuntu-source.tar.gz) | 서버 소스와 설치 템플릿 | [Ubuntu 설치·사용](../../docs/ubuntu-install-use.md) |
| [SHA256SUMS.json](SHA256SUMS.json) | 파일 크기와 SHA-256 | 내려받은 파일의 무결성 비교 |

GitHub의 파일 화면에서 **Download raw file**로 내려받거나 저장소를 clone하세요.
Windows ZIP은 전체 압축 해제 후 `AI-Blog-Auto/AI-Blog-Auto.exe`를 실행합니다.
Android는 API 26 이상이며 실제 배포 키가 아닌 Debug 키로 서명되어 있습니다.
Windows EXE에는 Authenticode 서명이 없습니다.

```powershell
Get-FileHash .\AI-Blog-Auto-Windows-x64.zip -Algorithm SHA256
Get-FileHash .\AI-Blog-Monitor-debug.apk -Algorithm SHA256
```

[개발 상세서](../../docs/development-guide.md) · [통합 시험 결과](../../docs/integration-test-results.md) · [빌드·배포·롤백](../../docs/build-and-deploy.md)

Windows/Android 실행 코드는 통합 시험에서 검증한 빌드입니다. 서버 묶음에는 최신 문서를 함께 포함했습니다.
키·실제 설정·운영 DB·사용자 콘텐츠는 포함하지 않습니다. 서버 묶음은 설치 파일이며 운영 서버에 배포한 결과가 아닙니다.
자동 네이버 발행은 비활성화되어 있고 실제 FCM·Ubuntu OS·단말 시험의 남은 범위는 시험 결과 문서에 표시했습니다.
