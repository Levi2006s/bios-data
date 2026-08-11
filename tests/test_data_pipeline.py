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
    with normalized.open(encoding="utf-8") as handle:
        assert {"tier", "label_origin", "metric", "comparison_group", "label_quality"} <= set(next(csv.reader(handle)))

    split_csv = tmp_path / "split.csv"
    manifest = make_split(normalized, split_csv, 0.6, 0.2)
    assert set(manifest["record_counts"]) == {"train", "validation", "test"}

    report = validate(split_csv)
    assert report["valid"] is True
    assert report["rows"] == 9
    assert report["split_diagnostics"]["split"]["source_group_leakage_count"] == 0


def test_validate_detects_exact_identity_leakage(tmp_path: Path) -> None:
    path = tmp_path / "leak.csv"
    fields = ["record_id", "source_group", "source_file", "heavy", "light", "raw_label", "direction", "score", "exact_antibody_safe_split"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(dict(record_id="a", source_group="g1", source_file="a.csv", heavy="ACDE", light="FGHI", raw_label="1", direction="1", score="0", exact_antibody_safe_split="train"))
        writer.writerow(dict(record_id="b", source_group="g2", source_file="b.csv", heavy="ACDE", light="FGHI", raw_label="2", direction="1", score="1", exact_antibody_safe_split="test"))
    report = validate(path)
    assert report["valid"] is False
    assert report["split_diagnostics"]["exact_antibody_safe_split"]["exact_antibody_leakage_keys"] == 1
