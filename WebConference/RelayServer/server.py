"""Run the standalone meeting relay from any working directory."""
import argparse
import os
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Moa Python WebRTC meeting relay")
    parser.add_argument("--host", default="127.0.0.1", help="Listening address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP/WebSocket port (default: 8000)")
    parser.add_argument("--env-file", help="Optional environment file, relative to the server directory")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    # The native Windows Vosk loader needs an ASCII relative model path.
    # Keeping the working directory here also makes local scripts predictable.
    os.chdir(ROOT)
    uvicorn.run("app.main:app", host=args.host, port=args.port,
                workers=1, ws_max_size=100000, env_file=args.env_file)


if __name__ == "__main__":
    main()
