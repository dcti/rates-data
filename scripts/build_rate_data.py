#!/usr/bin/env python3
"""Convert project rate logs into static, year-partitioned chart data."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECTS = {
    "ogr": {"label": "OGR", "unit": "Gnodes/sec"},
    "ogrng": {"label": "OGR-NG", "unit": "Gnodes/sec"},
    "ogrp2": {"label": "OGR-P2", "unit": "Gnodes/sec"},
    "rc564": {"label": "RC5-64", "unit": "Gkeys/sec"},
    "rc572": {"label": "RC5-72", "unit": "Gkeys/sec"},
}
PROJECT_RE = re.compile(
    r"^(?P<project>ogrng|ogrp2|rc564|rc572|ogr)-rate(?:-(?P<year>\d{4}))?\.log$"
)
MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
LINE_RE = re.compile(
    r"^\[(?P<month>[A-Z][a-z]{2}) (?P<day>\d{1,2}) "
    r"(?P<time>\d{2}:\d{2}:\d{2}) (?P<year>\d{4}) GMT\] "
    r"[^:]+: (?P<rate>\d+(?:\.\d+)?|Binary)$"
)
GENERATED_FILE_RE = re.compile(
    r"^(?:manifest|(?:ogrng|ogrp2|rc564|rc572|ogr)-\d{4})\.json$"
)


def parse_line(line: str, source: Path, line_number: int) -> tuple[int, float | None]:
    match = LINE_RE.fullmatch(line)
    if match is None:
        raise ValueError(f"{source}:{line_number}: unrecognized rate record")

    try:
        hour, minute, second = (int(part) for part in match["time"].split(":"))
        timestamp = datetime(
            int(match["year"]),
            MONTHS[match["month"]],
            int(match["day"]),
            hour,
            minute,
            second,
            tzinfo=timezone.utc,
        )
    except (KeyError, ValueError) as error:
        raise ValueError(f"{source}:{line_number}: invalid timestamp: {error}") from error

    rate = match["rate"]
    return int(timestamp.timestamp()), None if rate == "Binary" else float(rate) / 1000


def process_logs(source_dir: Path, output_dir: Path) -> dict:
    records: dict[str, dict[int, dict[int, float | None]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    sources = sorted(source_dir.glob("*-rate*.log"))
    included_files = 0
    duplicate_count = 0
    conflicting_duplicate_count = 0

    for source in sources:
        match = PROJECT_RE.fullmatch(source.name)
        if match is None:
            raise ValueError(f"{source}: unsupported rate log filename")

        included_files += 1
        project = match["project"]
        with source.open(encoding="utf-8") as log:
            for line_number, raw_line in enumerate(log, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                timestamp, rate = parse_line(line, source, line_number)
                year = datetime.fromtimestamp(timestamp, timezone.utc).year
                year_records = records[project][year]
                if timestamp in year_records:
                    duplicate_count += 1
                    if year_records[timestamp] != rate:
                        conflicting_duplicate_count += 1
                year_records[timestamp] = rate

    if not included_files:
        raise ValueError(f"No supported rate logs found in {source_dir}")
    if duplicate_count:
        print(
            f"Collapsed {duplicate_count} duplicate timestamps "
            f"({conflicting_duplicate_count} with differing rates); the last record "
            "in sorted file and line order was kept.",
            file=sys.stderr,
        )

    projects = []
    expected_files = set()
    for project, metadata in PROJECTS.items():
        if project not in records:
            continue
        years = []
        for year, values in sorted(records[project].items()):
            filename = f"{project}-{year}.json"
            expected_files.add(filename)
            points = [[timestamp, values[timestamp]] for timestamp in sorted(values)]
            output_file = output_dir / filename
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(
                json.dumps(points, separators=(",", ":"), allow_nan=False) + "\n",
                encoding="utf-8",
            )
            years.append(
                {
                    "year": year,
                    "count": len(points),
                    "first": points[0][0],
                    "last": points[-1][0],
                    "file": f"data/{filename}",
                }
            )
        projects.append(
            {
                "id": project,
                "label": metadata["label"],
                "unit": metadata["unit"],
                "years": years,
            }
        )

    for existing in output_dir.glob("*.json"):
        if GENERATED_FILE_RE.fullmatch(existing.name) and existing.name not in expected_files:
            existing.unlink()

    manifest = {"version": 1, "projects": projects}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    repository = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=repository)
    parser.add_argument("--output-dir", type=Path, default=repository / "docs" / "data")
    args = parser.parse_args()

    try:
        manifest = process_logs(args.source_dir, args.output_dir)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    project_count = len(manifest["projects"])
    record_count = sum(
        year["count"] for project in manifest["projects"] for year in project["years"]
    )
    print(f"Generated {record_count:,} records for {project_count} projects.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
