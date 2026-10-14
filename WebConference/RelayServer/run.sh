#!/usr/bin/env bash
set -euo pipefail
SERVER_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SERVER_DIR"
if [[ -x "$SERVER_DIR/.venv/bin/python" ]]; then
    SERVER_PYTHON="$SERVER_DIR/.venv/bin/python"
else
    SERVER_PYTHON="python3"
fi
exec "$SERVER_PYTHON" "$SERVER_DIR/server.py" "$@"
