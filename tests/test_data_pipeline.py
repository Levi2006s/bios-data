from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.audit import audit
from bioos_benchmark.prepare import prepare
from bioos_benchmark.split import make_split
from bioos_benchmark.validate import validate


def write_source(root: Path, group: int, name: str, values: list[float]) -> None:
    folder = root / "初赛-序列数据" / str(group)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["heavy", "light", "KD (nM)", "fitness"])
        for index, value in enumerate(values):
            suffix = "Y" if index % 2 else "A"
            writer.writerow([f"ACDEFGHIKLMNPQRSTVW{suffix}", "ACDEFGHIK", value, value])


def test_complete_data_pipeline(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    write_source(raw, 1, "one.csv", [1, 2, 3])
    write_source(raw, 2, "two.csv", [2, 3, 4])
    write_source(raw, 3, "three.csv", [3, 4, 5])

    audit_csv = tmp_path / "audit.csv"
    audit_summary = audit(raw, audit_csv, compute_hash=True)
    assert audit_summary["csv_files"] == 3
    assert audit_summary["valid_rows"] == 9

    normalized = tmp_path / "normalized.csv"
    summary = prepare(raw, normalized, max_rows_per_file=0, seed=7)
    assert summary["records"] == 9

    split_csv = tmp_path / "split.csv"
    manifest = make_split(normalized, split_csv, 0.6, 0.2)
    assert set(manifest["record_counts"]) == {"train", "validation", "test"}

    report = validate(split_csv)
    assert report["valid"] is True
    assert report["rows"] == 9
