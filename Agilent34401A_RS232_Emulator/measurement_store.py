import csv
import math
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook


EXCEL_MAX_DATA_ROWS = 1_048_575
PLOT_MAX_POINTS = 2_000
RAW_PLOT_LIMIT = 50_000
COMMIT_INTERVAL_SECONDS = 5
COMMIT_BATCH_SIZE = 1_000


class MeasurementStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS measurements ("
            "id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, voltage REAL NOT NULL)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS measurements_timestamp "
            "ON measurements(timestamp)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS measurement_minutes ("
            "bucket TEXT PRIMARY KEY, "
            "first_id INTEGER NOT NULL, first_timestamp TEXT NOT NULL, first_voltage REAL NOT NULL, "
            "minimum_id INTEGER NOT NULL, minimum_timestamp TEXT NOT NULL, minimum_voltage REAL NOT NULL, "
            "maximum_id INTEGER NOT NULL, maximum_timestamp TEXT NOT NULL, maximum_voltage REAL NOT NULL, "
            "last_id INTEGER NOT NULL, last_timestamp TEXT NOT NULL, last_voltage REAL NOT NULL)"
        )
        self.connection.commit()
        self.pending = 0
        self.last_commit = time.monotonic()

    def append(self, timestamp, voltage):
        cursor = self.connection.execute(
            "INSERT INTO measurements(timestamp, voltage) VALUES (?, ?)",
            (timestamp.isoformat(timespec="microseconds"), voltage),
        )
        sample_id = cursor.lastrowid
        timestamp_text = timestamp.isoformat(timespec="microseconds")
        bucket = timestamp.replace(second=0, microsecond=0).isoformat(
            timespec="microseconds"
        )
        self.connection.execute(
            "INSERT INTO measurement_minutes("
            "bucket, first_id, first_timestamp, first_voltage, "
            "minimum_id, minimum_timestamp, minimum_voltage, "
            "maximum_id, maximum_timestamp, maximum_voltage, "
            "last_id, last_timestamp, last_voltage) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(bucket) DO UPDATE SET "
            "first_id = CASE WHEN excluded.first_id < first_id THEN excluded.first_id ELSE first_id END, "
            "first_timestamp = CASE WHEN excluded.first_id < first_id THEN excluded.first_timestamp ELSE first_timestamp END, "
            "first_voltage = CASE WHEN excluded.first_id < first_id THEN excluded.first_voltage ELSE first_voltage END, "
            "minimum_id = CASE WHEN excluded.minimum_voltage < minimum_voltage THEN excluded.minimum_id ELSE minimum_id END, "
            "minimum_timestamp = CASE WHEN excluded.minimum_voltage < minimum_voltage THEN excluded.minimum_timestamp ELSE minimum_timestamp END, "
            "minimum_voltage = MIN(minimum_voltage, excluded.minimum_voltage), "
            "maximum_id = CASE WHEN excluded.maximum_voltage > maximum_voltage THEN excluded.maximum_id ELSE maximum_id END, "
            "maximum_timestamp = CASE WHEN excluded.maximum_voltage > maximum_voltage THEN excluded.maximum_timestamp ELSE maximum_timestamp END, "
            "maximum_voltage = MAX(maximum_voltage, excluded.maximum_voltage), "
            "last_id = CASE WHEN excluded.last_id > last_id THEN excluded.last_id ELSE last_id END, "
            "last_timestamp = CASE WHEN excluded.last_id > last_id THEN excluded.last_timestamp ELSE last_timestamp END, "
            "last_voltage = CASE WHEN excluded.last_id > last_id THEN excluded.last_voltage ELSE last_voltage END",
            (
                bucket,
                sample_id,
                timestamp_text,
                voltage,
                sample_id,
                timestamp_text,
                voltage,
                sample_id,
                timestamp_text,
                voltage,
                sample_id,
                timestamp_text,
                voltage,
            ),
        )
        self.pending += 1
        now = time.monotonic()
        if (
            self.pending >= COMMIT_BATCH_SIZE
            or now - self.last_commit >= COMMIT_INTERVAL_SECONDS
        ):
            self.flush()

    def flush(self):
        if self.pending:
            self.connection.commit()
            self.pending = 0
            self.last_commit = time.monotonic()

    def close(self):
        if self.connection is None:
            return
        self.flush()
        self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.connection.close()
        self.connection = None

    def count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM measurements"
        ).fetchone()[0]

    def bounds(self):
        row = self.connection.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM measurements"
        ).fetchone()
        if row[0] is None:
            return None
        return datetime.fromisoformat(row[0]), datetime.fromisoformat(row[1])

    def recent(self, limit):
        rows = self.connection.execute(
            "SELECT timestamp, voltage FROM measurements "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        rows.reverse()
        return [(datetime.fromisoformat(timestamp), voltage) for timestamp, voltage in rows]

    def plot_range(self, start, end, max_points=PLOT_MAX_POINTS):
        start_text = start.isoformat(timespec="microseconds")
        end_text = end.isoformat(timespec="microseconds")
        count = self.connection.execute(
            "SELECT COUNT(*) FROM measurements WHERE timestamp BETWEEN ? AND ?",
            (start_text, end_text),
        ).fetchone()[0]
        if count == 0:
            return []

        if count <= max_points:
            cursor = self.connection.execute(
                "SELECT id, timestamp, voltage FROM measurements "
                "WHERE timestamp BETWEEN ? AND ? ORDER BY id",
                (start_text, end_text),
            )
            return [
                (datetime.fromisoformat(timestamp), voltage)
                for _, timestamp, voltage in cursor
            ]

        if count > RAW_PLOT_LIMIT:
            start_bucket = start.replace(second=0, microsecond=0).isoformat(
                timespec="microseconds"
            )
            end_bucket = end.replace(second=0, microsecond=0).isoformat(
                timespec="microseconds"
            )
            rollups = self.connection.execute(
                "SELECT first_id, first_timestamp, first_voltage, "
                "minimum_id, minimum_timestamp, minimum_voltage, "
                "maximum_id, maximum_timestamp, maximum_voltage, "
                "last_id, last_timestamp, last_voltage "
                "FROM measurement_minutes WHERE bucket BETWEEN ? AND ? ORDER BY bucket",
                (start_bucket, end_bucket),
            )
            candidates = {}
            for row in rollups:
                for offset in range(0, len(row), 3):
                    sample_id, timestamp, voltage = row[offset : offset + 3]
                    if start_text <= timestamp <= end_text:
                        candidates[sample_id] = (sample_id, timestamp, voltage)
            rows = [candidates[key] for key in sorted(candidates)]
            return self._downsample(rows, len(rows), max_points)

        cursor = self.connection.execute(
            "SELECT id, timestamp, voltage FROM measurements "
            "WHERE timestamp BETWEEN ? AND ? ORDER BY id",
            (start_text, end_text),
        )
        return self._downsample(cursor, count, max_points)

    @staticmethod
    def _downsample(rows, count, max_points):
        if count <= max_points:
            return [
                (datetime.fromisoformat(timestamp), voltage)
                for _, timestamp, voltage in rows
            ]
        bucket_count = max(1, max_points // 4)
        bucket_size = math.ceil(count / bucket_count)
        plotted = []
        current_bucket = None
        first = last = minimum = maximum = None

        def finish_bucket():
            rows = {row[0]: row for row in (first, minimum, maximum, last)}
            plotted.extend(
                (datetime.fromisoformat(row[1]), row[2])
                for row in sorted(rows.values())
            )

        for index, row in enumerate(rows):
            bucket = index // bucket_size
            if bucket != current_bucket:
                if current_bucket is not None:
                    finish_bucket()
                current_bucket = bucket
                first = last = minimum = maximum = row
            else:
                last = row
                if row[2] < minimum[2]:
                    minimum = row
                if row[2] > maximum[2]:
                    maximum = row
        finish_bucket()
        return plotted

    @staticmethod
    def _reader(database_path):
        uri = f"{Path(database_path).resolve().as_uri()}?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=30)

    @classmethod
    def export_csv(cls, database_path, output_path):
        output_path = Path(output_path)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                newline="",
                encoding="utf-8-sig",
                suffix=".tmp",
                prefix=f"{output_path.stem}_",
                dir=output_path.parent,
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                writer = csv.writer(file)
                writer.writerow(("시간", "전압 (V)"))
                with closing(cls._reader(database_path)) as connection:
                    cursor = connection.execute(
                        "SELECT timestamp, voltage FROM measurements ORDER BY id"
                    )
                    while True:
                        rows = cursor.fetchmany(10_000)
                        if not rows:
                            break
                        writer.writerows(
                            (
                                datetime.fromisoformat(timestamp).strftime(
                                    "%Y-%m-%d %H:%M:%S.%f"
                                )[:-3],
                                voltage,
                            )
                            for timestamp, voltage in rows
                        )
            os.replace(temporary_path, output_path)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()

    @classmethod
    def export_excel(
        cls, database_path, output_path, max_rows_per_sheet=EXCEL_MAX_DATA_ROWS
    ):
        output_path = Path(output_path)
        temporary_path = None
        workbook = Workbook(write_only=True)
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".xlsx",
                prefix=f"{output_path.stem}_",
                dir=output_path.parent,
                delete=False,
            ) as file:
                temporary_path = Path(file.name)

            sheet_number = 0
            sheet = cls._new_sheet(workbook, sheet_number)
            rows_in_sheet = 0
            with closing(cls._reader(database_path)) as connection:
                cursor = connection.execute(
                    "SELECT timestamp, voltage FROM measurements ORDER BY id"
                )
                while True:
                    rows = cursor.fetchmany(10_000)
                    if not rows:
                        break
                    for timestamp, voltage in rows:
                        if rows_in_sheet >= max_rows_per_sheet:
                            sheet_number += 1
                            sheet = cls._new_sheet(workbook, sheet_number)
                            rows_in_sheet = 0
                        sheet.append((datetime.fromisoformat(timestamp), voltage))
                        rows_in_sheet += 1
            workbook.save(temporary_path)
            os.replace(temporary_path, output_path)
        finally:
            workbook.close()
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _new_sheet(workbook, sheet_number):
        name = "전압 측정" if sheet_number == 0 else f"전압 측정 {sheet_number + 1}"
        sheet = workbook.create_sheet(name)
        sheet.append(("시간", "전압 (V)"))
        return sheet
