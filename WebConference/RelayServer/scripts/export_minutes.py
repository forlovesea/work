"""Export a closed or live meeting from the administrator's local SQLite copy."""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.domain import Room, minutes_markdown

parser = argparse.ArgumentParser()
parser.add_argument("--db", default="data/meetings.db")
parser.add_argument("--list", action="store_true")
parser.add_argument("--room-id")
parser.add_argument("--output", default="minutes.md")


def main():
    args = parser.parse_args()
    db = sqlite3.connect(Path(args.db).resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        if args.list:
            for row in db.execute("SELECT id,title,created_at,closed_at FROM rooms ORDER BY created_at DESC"):
                print(dict(row))
            return
        if not args.room_id:
            parser.error("Provide --room-id or --list")
        row = db.execute("SELECT * FROM rooms WHERE id=?", (args.room_id,)).fetchone()
        if not row:
            parser.error("Room not found")
        room = Room(row["id"], row["code"], row["title"], row["mode"], "", False, created_at=row["created_at"])
        entries = [dict(row) for row in db.execute("SELECT * FROM entries WHERE room_id=? ORDER BY id", (args.room_id,))]
        Path(args.output).write_text(minutes_markdown(room, entries), encoding="utf-8")
        print("Exported:", args.output)
    finally:
        db.close()


if __name__ == "__main__":
    main()
