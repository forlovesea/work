import csv
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from measurement_store import MeasurementStore


class MeasurementStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "measurements.sqlite3"
        self.store = MeasurementStore(self.database_path)
        self.addCleanup(self.store.close)
        self.first_time = datetime(2026, 11, 24, 13, 30, 0)

    def add_samples(self, voltages):
        for index, voltage in enumerate(voltages):
            self.store.append(self.first_time + timedelta(seconds=index), voltage)

    def test_records_are_persistent_and_plot_queries_preserve_extrema(self):
        voltages = [float(index % 5) for index in range(100)]
        voltages[23] = -20.0
        voltages[87] = 50.0
        self.add_samples(voltages)

        plot_data = self.store.plot_range(
            self.first_time,
            self.first_time + timedelta(seconds=99),
            max_points=16,
        )
        self.assertLessEqual(len(plot_data), 16)
        self.assertIn((self.first_time + timedelta(seconds=23), -20.0), plot_data)
        self.assertIn((self.first_time + timedelta(seconds=87), 50.0), plot_data)
        self.assertEqual(self.store.count(), 100)

        self.store.close()
        reopened = MeasurementStore(self.database_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.count(), 100)
        self.assertEqual(reopened.bounds(), (self.first_time, self.first_time + timedelta(seconds=99)))

    def test_long_range_plot_reads_minute_extrema_without_all_raw_rows(self):
        voltages = [float(index % 5) for index in range(120)]
        voltages[23] = -20.0
        voltages[87] = 50.0
        self.add_samples(voltages)

        with patch("measurement_store.RAW_PLOT_LIMIT", 8):
            plot_data = self.store.plot_range(
                self.first_time,
                self.first_time + timedelta(seconds=119),
                max_points=16,
            )

        self.assertLessEqual(len(plot_data), 16)
        self.assertIn((self.first_time + timedelta(seconds=23), -20.0), plot_data)
        self.assertIn((self.first_time + timedelta(seconds=87), 50.0), plot_data)

    def test_csv_export_streams_all_samples(self):
        self.add_samples([1.25, 2.5, 3.75])
        self.store.flush()
        output_path = Path(self.temporary_directory.name) / "result.csv"

        MeasurementStore.export_csv(self.database_path, output_path)

        with output_path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file))
        self.assertEqual(rows[0], ["시간", "전압 (V)"])
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1][1], "3.75")

    def test_excel_export_splits_rows_across_sheets(self):
        self.add_samples([1.25, 2.5, 3.75, 4.0, 5.0])
        self.store.flush()
        output_path = Path(self.temporary_directory.name) / "result.xlsx"

        MeasurementStore.export_excel(
            self.database_path, output_path, max_rows_per_sheet=2
        )

        workbook = load_workbook(output_path, read_only=True)
        self.addCleanup(workbook.close)
        self.assertEqual(workbook.sheetnames, ["전압 측정", "전압 측정 2", "전압 측정 3"])
        row_counts = [sum(1 for _ in sheet.iter_rows()) for sheet in workbook.worksheets]
        self.assertEqual(row_counts, [3, 3, 2])


if __name__ == "__main__":
    unittest.main()
