#!/usr/bin/env bash
# Run from any directory. Re-run after git pull to install a new release.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
    echo 'sudo bash install.sh [/absolute/path/to/python3.12]'
    echo 'Installs and restarts moa.service; existing meetings will end.'
    echo 'Set INSTALL_WHISPER=1 to also install Korean Whisper transcription.'
    exit 0
fi
[[ ${EUID} -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
exec 9>/run/lock/moa-install.lock
flock -n 9 || { echo 'Another Moa installation is running.' >&2; exit 1; }
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 20.04 ]] || { echo 'Expected Ubuntu 20.04.' >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo 'This installer targets x86_64.' >&2; exit 1; }
PYTHON=${1:-/opt/moa/python/3.12.15/bin/python3.12}
[[ ! -e /opt/moa/current.next && ! -L /opt/moa/current.next ]] || { echo 'Resolve stale /opt/moa/current.next before installing.' >&2; exit 1; }
[[ $PYTHON == /* && -x $PYTHON ]] || { echo 'Run build-python.sh first or supply an absolute Python 3.12 path.' >&2; exit 1; }
"$PYTHON" -c 'import sys, ssl, sqlite3; assert sys.version_info[:2] == (3, 12)'
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
apt-get update
apt-get install -y libgomp1 ca-certificates curl
id moa >/dev/null 2>&1 || useradd --system --user-group --home-dir /var/lib/moa --shell /usr/sbin/nologin moa
install -d -m 0755 /opt/moa/releases /etc/moa
install -d -o moa -g moa -m 0750 /var/lib/moa /var/lib/moa/models
if [[ ! -f /etc/moa/moa.env ]]; then
    install -o root -g moa -m 0640 "$SOURCE/deploy/native/moa.env.example" /etc/moa/moa.env
fi
RELEASE=$(mktemp -d /opt/moa/releases/release-XXXXXXXX)
chmod 0755 "$RELEASE"
cp -R "$SOURCE/app" "$SOURCE/static" "$SOURCE/scripts" "$RELEASE/"
cp "$SOURCE/server.py" "$SOURCE/requirements.txt" "$SOURCE/requirements-whisper.txt" "$RELEASE/"
"$PYTHON" -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/python" -m pip install --upgrade pip
# Native media packages must have compatible Linux wheels; avoid surprise source builds.
"$RELEASE/.venv/bin/python" -m pip install --only-binary=av,aiortc,numpy,cryptography,cffi \
    -r "$RELEASE/requirements.txt"
if [[ ${INSTALL_WHISPER:-0} == 1 ]] || grep -q '^SPEECH_ENGINE=whisper$' /etc/moa/moa.env; then
    "$RELEASE/.venv/bin/python" -m pip install -r "$RELEASE/requirements-whisper.txt"
    runuser -u moa -- "$RELEASE/.venv/bin/python" "$RELEASE/scripts/download_whisper.py" \
        --output /var/lib/moa/models/faster-whisper-small
fi
"$RELEASE/.venv/bin/python" -m pip check
runuser -u moa -- "$RELEASE/.venv/bin/python" "$RELEASE/scripts/download_model.py" \
    --models-dir /var/lib/moa/models
runuser -u moa -- "$RELEASE/.venv/bin/python" -c \
    "from vosk import Model; Model('/var/lib/moa/models/vosk-model-small-ko-0.22')"
PREVIOUS=''
if [[ -L /opt/moa/current ]]; then PREVIOUS=$(readlink -f /opt/moa/current); fi
if [[ -e /opt/moa/current && ! -L /opt/moa/current ]]; then
    echo '/opt/moa/current must be a symlink, refusing to replace it.' >&2; exit 1
fi
# Keep the old release and config for manual rollback. Never copy or overwrite the DB.
echo "Activating $RELEASE; previous release: ${PREVIOUS:-none}"
install -m 0644 "$SOURCE/deploy/native/moa.service" /etc/systemd/system/moa.service
systemctl daemon-reload
systemctl stop moa.service
ln -s "$RELEASE" /opt/moa/current.next
mv -Tf /opt/moa/current.next /opt/moa/current
systemctl enable moa.service
systemctl start moa.service
for attempt in $(seq 1 60); do
    if systemctl is-active --quiet moa.service && curl --max-time 5 -fsS http://127.0.0.1:8000/api/config; then
        echo
        echo "Installed: $RELEASE; previous: ${PREVIOUS:-none}"
        echo 'Configure Nginx and HTTPS using UBUNTU_DEPLOY.md.'
        exit 0
    fi
    sleep 2
done
echo "Health check failed. Previous release: ${PREVIOUS:-none}" >&2
journalctl -u moa.service -n 50 --no-pager
exit 1
