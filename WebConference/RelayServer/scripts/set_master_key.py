"""Set/reset the Master key interactively. Never accepts passwords as arguments."""
import argparse
import getpass
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.master_auth import default_key_path, write_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=default_key_path())
    args = parser.parse_args()
    if os.name == "posix" and os.geteuid() != 0:
        parser.error("Run with sudo so only the administrator can replace the Master key.")
    password = getpass.getpass("New Master key (12-256 characters): ")
    if password != getpass.getpass("Confirm Master key: "):
        parser.error("Keys do not match; nothing was changed.")
    try:
        write_key(args.path, password, service_owner=os.name == "posix")
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    print(f"Master key updated: {args.path}")
    print("No service restart needed. Existing Master sessions are now revoked.")


if __name__ == "__main__":
    main()
