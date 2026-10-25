import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_rate_data import parse_line, process_logs


class ParseLineTests(unittest.TestCase):
    def test_parses_single_digit_day_as_utc_and_converts_mega_to_giga(self):
        timestamp, rate = parse_line(
            "[Jan 1 00:15:00 2026 GMT] rate-logger.pl: 3892372.99",
            Path("rc572-rate-2026.log"),
            1,
        )

        self.assertEqual(timestamp, 1767226500)
        self.assertAlmostEqual(rate, 3892.37299)

    def test_rejects_unrecognized_records(self):
        with self.assertRaisesRegex(ValueError, "unrecognized rate record"):
            parse_line("not a rate record", Path("rates.log"), 3)

    def test_preserves_binary_markers_as_missing_rates(self):
        timestamp, rate = parse_line(
            "[Jul 31 17:00:02 2002 GMT] ogr-rate-logger: Binary",
            Path("ogr-rate-2008.log"),
            1,
        )

        self.assertEqual(timestamp, 1028134802)
        self.assertIsNone(rate)


class ProcessLogsTests(unittest.TestCase):
    def test_writes_sorted_project_year_shards_and_skips_mirc_logs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir = root / "logs"
            output_dir = root / "output"
            source_dir.mkdir()
            (source_dir / "rc572-rate-2025.log").write_text(
                "[Jan 1 01:15:00 2026 GMT] rate-logger.pl: 2000\n"
                "[Jan 1 00:15:00 2026 GMT] rate-logger.pl: 1000\n",
                encoding="utf-8",
            )
            (source_dir / "mirc-rates-2026.log").write_text(
                "combined IRC data that is intentionally unsupported",
                encoding="utf-8",
            )

            manifest = process_logs(source_dir, output_dir)

            self.assertEqual([project["id"] for project in manifest["projects"]], ["rc572"])
            project_year = manifest["projects"][0]["years"][0]
            self.assertEqual(project_year["count"], 2)
            self.assertEqual(
                json.loads((output_dir / "rc572-2026.json").read_text(encoding="utf-8")),
                [[1767226500, 1.0], [1767230100, 2.0]],
            )
            self.assertTrue((output_dir / "manifest.json").is_file())

    def test_rejects_unsupported_rate_log_filenames(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "rc572-rate-2026.log").write_text(
                "[Jan 1 00:15:00 2026 GMT] rate-logger.pl: 1000\n",
                encoding="utf-8",
            )
            (root / "rc572-rate-2026-copy.log").write_text(
                "[Jan 1 00:15:00 2026 GMT] rate-logger.pl: 2000\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unsupported rate log filename"):
                process_logs(root, root / "output")

    def test_resolves_duplicate_timestamps_using_last_record(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "rc572-rate-2026.log").write_text(
                "[Jan 1 00:15:00 2026 GMT] rate-logger.pl: 1000\n"
                "[Jan 1 00:15:00 2026 GMT] rate-logger.pl: 2000\n",
                encoding="utf-8",
            )

            manifest = process_logs(root, root / "output")

            self.assertEqual(manifest["projects"][0]["years"][0]["year"], 2026)
            self.assertEqual(
                json.loads((root / "output" / "rc572-2026.json").read_text(encoding="utf-8")),
                [[1767226500, 2.0]],
            )

    def test_preserves_binary_markers_in_generated_data(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "ogr-rate-2008.log").write_text(
                "[Jul 31 17:00:02 2002 GMT] ogr-rate-logger: Binary\n",
                encoding="utf-8",
            )

            process_logs(root, root / "output")

            self.assertEqual(
                json.loads((root / "output" / "ogr-2002.json").read_text(encoding="utf-8")),
                [[1028134802, None]],
            )


if __name__ == "__main__":
    unittest.main()
