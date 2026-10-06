#!/bin/sh
# Run on the Ubuntu relay: sudo sh update-server.sh
set -eu
if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo sh update-server.sh" >&2
    exit 1
fi
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
getent group remotecontrol >/dev/null
test -s /etc/remotecontrol/fullchain.pem
test -s /etc/remotecontrol/privkey.pem
python3 -m py_compile "$SOURCE_DIR/relay.py"
install -d -o root -g remotecontrol -m 750 /etc/remotecontrol
if [ ! -f /etc/remotecontrol/access.key ]; then
    (umask 077; python3 -c 'import secrets; print(secrets.token_hex(32))' > /etc/remotecontrol/access.key)
fi
chown root:remotecontrol /etc/remotecontrol/access.key
chmod 640 /etc/remotecontrol/access.key
python3 -c 'import pathlib,re; assert re.fullmatch(r"[0-9a-fA-F]{64}", pathlib.Path("/etc/remotecontrol/access.key").read_text().strip()), "Invalid access.key"'
install -d -o root -g root -m 755 /opt/remotecontrol
if [ -f /opt/remotecontrol/relay.py ]; then
    cp -p /opt/remotecontrol/relay.py "/opt/remotecontrol/relay.py.backup.$(date +%Y%m%d%H%M%S)"
fi
install -o root -g root -m 644 "$SOURCE_DIR/relay.py" /opt/remotecontrol/relay.py.new
mv /opt/remotecontrol/relay.py.new /opt/remotecontrol/relay.py
# Existing service arguments, certificate paths, and port are preserved.
systemctl restart remotecontrol-relay
systemctl --no-pager --full status remotecontrol-relay
echo 'Server updated. Use sudo cat /etc/remotecontrol/access.key to read the shared key for your Host and Target apps.'
