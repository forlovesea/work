"""Back up only SQLite metadata; never walk or copy the content directory."""
import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path


def backup_metadata(source, destination):
    source, destination = Path(source).resolve(), Path(destination).absolute()
    # Refuse overwrites/symlinks, including accidental replacement of the live DB.
    if not source.is_file() or source == destination.resolve():
        raise ValueError("Expected an existing source and a distinct new backup file")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(destination)) as dst:
                src.backup(dst)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    backup_metadata(args.source, args.destination)
