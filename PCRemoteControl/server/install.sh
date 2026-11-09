#!/bin/sh
# Ubuntu 20.04+; changes only the PCRemoteControl service.
set -eu
if [ "$(id -u)" -ne 0 ]; then echo 'Run with sudo.' >&2; exit 1; fi
if [ "$#" -ne 2 ]; then echo 'Usage: sudo sh server/install.sh /path/fullchain.pem /path/privkey.pem' >&2; exit 1; fi
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CERT=$(readlink -f -- "$1")
KEY=$(readlink -f -- "$2")
test -r "$CERT" && test -r "$KEY"
python3 - "$CERT" "$KEY" <<'PY'
import ssl, sys
assert sys.version_info >= (3, 8), 'Python 3.8 or newer required'
ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(sys.argv[1], sys.argv[2])
PY
if ! systemctl is-active --quiet pcremote-relay; then
    if ss -ltnH 'sport = :61000' | grep -q .; then
        echo 'TCP 61000 is already in use. No service was changed.' >&2; exit 1
    fi
fi
getent group pcremote >/dev/null || groupadd --system pcremote
getent passwd pcremote >/dev/null || useradd --system --gid pcremote --no-create-home --shell /usr/sbin/nologin pcremote
install -d -o root -g root -m 755 /opt/pcremote
install -d -o root -g pcremote -m 750 /etc/pcremote
if [ -f /opt/pcremote/relay.py ]; then cp -p /opt/pcremote/relay.py /opt/pcremote/relay.py.previous; fi
install -m 644 "$SOURCE/relay.py" /opt/pcremote/relay.py
if [ "$CERT" != /etc/pcremote/fullchain.pem ]; then install -o root -g pcremote -m 640 "$CERT" /etc/pcremote/fullchain.pem; fi
if [ "$KEY" != /etc/pcremote/privkey.pem ]; then install -o root -g pcremote -m 640 "$KEY" /etc/pcremote/privkey.pem; fi
if [ ! -f /etc/pcremote/relay.env ]; then
    (umask 077; printf 'PCREMOTE_PASSWORD=jjh1234\n' > /etc/pcremote/relay.env)
fi
chown root:pcremote /etc/pcremote/relay.env /etc/pcremote/fullchain.pem /etc/pcremote/privkey.pem
chmod 640 /etc/pcremote/relay.env /etc/pcremote/fullchain.pem /etc/pcremote/privkey.pem
install -m 644 "$SOURCE/pcremote-relay.service" /etc/systemd/system/pcremote-relay.service
systemctl daemon-reload
systemctl enable pcremote-relay
systemctl restart pcremote-relay
systemctl --no-pager --full status pcremote-relay
echo 'Allow TCP 61000 in the server firewall and cloud security group. Existing RemoteControl is unchanged.'
echo 'Email verification is required. Configure PCREMOTE_SMTP_HOST/PORT/USER/PASSWORD (optional FROM) in /etc/pcremote/relay.env, then restart pcremote-relay. See README.md.'
