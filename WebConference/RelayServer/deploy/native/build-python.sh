#!/usr/bin/env bash
# Install a private CPython without replacing Ubuntu's /usr/bin/python3.
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 20.04 ]] || { echo 'Expected Ubuntu 20.04.' >&2; exit 1; }
VERSION=3.12.15
SHA256=c2c4321961fab0fb999d66e0cecf521c2ab3994c7992873ea99e306c1094fd5a
PREFIX=/opt/moa/python/$VERSION
if [[ -x $PREFIX/bin/python3.12 ]]; then
    "$PREFIX/bin/python3.12" -c 'import ssl, sqlite3, bz2, lzma, ctypes, venv'
    echo "$PREFIX/bin/python3.12"
    exit 0
fi
apt-get update
apt-get install -y build-essential curl ca-certificates xz-utils libssl-dev \
    zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev uuid-dev
BUILD=$(mktemp -d /var/tmp/moa-python.XXXXXXXX)
trap 'rm -rf -- "$BUILD"' EXIT
cd "$BUILD"
curl --fail --location --retry 3 --proto '=https' \
    "https://www.python.org/ftp/python/$VERSION/Python-$VERSION.tar.xz" -o python.tar.xz
echo "$SHA256  python.tar.xz" | sha256sum --check --strict
tar -xf python.tar.xz
cd "Python-$VERSION"
./configure --prefix="$PREFIX" --with-ensurepip=install
# A conservative default for small hosts; override with JOBS=4 if desired.
make -j "${JOBS:-2}"
make altinstall
"$PREFIX/bin/python3.12" -c 'import ssl, sqlite3, bz2, lzma, ctypes, venv'
echo "Python ready: $PREFIX/bin/python3.12"
