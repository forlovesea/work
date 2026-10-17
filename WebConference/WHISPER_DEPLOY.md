# 한국어 회의록 정확도 우선 모드

기존 Vosk 대신 다국어 Whisper small을 CPU INT8로 실행합니다. 한국어를 지정하고 최대 약 20초의 음성을 모아 문맥을 처리합니다. 무음 구간은 VAD로 제거합니다. 실제 인식률과 처리 시간은 마이크·발음·전문용어에 따라 달라지므로 기존 회의 음성으로 확인해야 합니다.

i5-3340M의 부담을 줄이도록 인식 작업은 한 번에 하나, 추론 스레드는 하나로 제한합니다. 회의 통신과 별도 스레드에서 처리하지만 CPU·메모리를 공유하므로 기존 서비스에 대한 성능 영향이 없다고 보장할 수는 없습니다. 대기 건수가 계속 늘어나면 자동 기록을 끄고 처리 완료를 기다리세요.

## 기존 Ubuntu 20.04 서버 업데이트

회의가 없는 시간에 실행합니다. 기존 회의가 있다면 자동 기록을 끄고 대기 0건을 확인한 다음 회의록을 저장합니다. 아래 설치는 moa만 재시작하며 Nginx, 인증서, 축전지·원격제어 서비스 설정은 변경하지 않습니다.

1. 기존 Git 다운로드 폴더의 `WebConference/RelayServer`로 이동한 뒤 실행합니다.

```bash
git pull --ff-only
sudo env INSTALL_WHISPER=1 bash deploy/native/install.sh /opt/moa/python/3.12.15/bin/python3.12
```

최초 설치 시 패키지와 모델을 다운로드하므로 시간이 걸립니다. 모델 로딩과 무음 검증에 성공한 뒤 새 릴리스를 활성화합니다. apt 저장소 오류가 있으면 먼저 해당 저장소를 복구해야 합니다.

2. 환경설정을 편집합니다.

```bash
sudo nano /etc/moa/moa.env
```

아래 항목은 중복 없이 추가하거나 교체합니다. 기존 포트·주소·DB·보안 설정을 유지합니다.

```ini
SPEECH_ENGINE=whisper
WHISPER_MODEL_PATH=/var/lib/moa/models/faster-whisper-small
WHISPER_PROMPT="축전지, 정류기, 충전 전압, 방전 전류, 셀 전압, 내부 저항"
```

`WHISPER_PROMPT`는 실제 회의에서 사용하는 용어 목록으로 바꾸거나 비워도 됩니다. 용어 힌트이며 정확성을 보장하는 사전은 아닙니다.

3. 적용하고 확인합니다.

```bash
sudo systemctl restart moa
curl --noproxy '*' -fsS http://127.0.0.1:8000/api/config
sudo journalctl -u moa -n 50 --no-pager
```

응답에서 `"speech_available":true`, `"speech_engine":"faster-whisper"`를 확인합니다. 브라우저에서 `https://61.105.141.21:10443`을 새로고침하고 자동 기록을 켠 회의에서 발언합니다. 표시는 발화 수집 시간과 서버 처리 시간만큼 늦습니다. 이 CPU에서의 지연 시간은 아직 측정하지 않았습니다.

## 회의록 저장과 운영

- 자동 기록을 끈 뒤 **음성 수집·인식 대기 0건**을 확인하고 회의록을 저장합니다. 처리 중에는 다운로드 API가 409로 알려 불완전한 내보내기를 방지합니다.
- 늦게 완료된 문장도 원래 발화 시각으로 정렬하고 발언자 이름을 유지합니다.
- 음성은 서버 메모리에서만 처리합니다. 외부 음성 인식 API로 보내거나 녹음 파일로 저장하지 않습니다. 모델 다운로드에는 인터넷이 필요하고 런타임 모델 로딩은 로컬 파일만 사용합니다.
- 대기열은 서버 전체 60개 구간으로 제한합니다. 초과한 음성은 기록되지 않고 화면에 알립니다. 자동 기록을 끄면 새 음성 수집만 중단하고 대기 중인 작업은 계속 처리합니다.
- 재시작·장애가 발생하면 처리 전 음성은 사라질 수 있습니다. 이미 DB에 저장된 회의록은 유지됩니다.
- 부담이 크거나 문제가 있으면 `/etc/moa/moa.env`의 `SPEECH_ENGINE=vosk`로 되돌리고 `sudo systemctl restart moa`를 실행합니다.

구현 참고: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [CTranslate2 CPU 지원](https://opennmt.net/CTranslate2/hardware_support.html).
