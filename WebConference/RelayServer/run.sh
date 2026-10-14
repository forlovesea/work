#!/usr/bin/env bash
set -euo pipefail
SERVER_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SERVER_DIR"
if [[ -x "$SERVER_DIR/.venv/bin/python" ]]; then
    SERVER_PYTHON="$SERVER_DIR/.venv/bin/python"
else
    SERVER_PYTHON="${MOA_PYTHON:-python3.12}"
fi
if ! command -v "$SERVER_PYTHON" >/dev/null 2>&1; then
    echo 'Python 3.12 is required. See ../UBUNTU_DEPLOY.md for native installation.' >&2
    exit 1
fi
"$SERVER_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 is required"'
exec "$SERVER_PYTHON" "$SERVER_DIR/server.py" "$@"
