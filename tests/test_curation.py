from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.apply_splits import apply_split_manifest
from bioos_benchmark.curation import label_is_valid


def test_label_range_and_binary_validation() -> None:
    kd = {"censor_policy": "require_positive_and_below_max", "valid_min": "0", "valid_max": "1", "metric": "KD"}
    assert label_is_valid(1e-9, kd)
    assert not label_is_valid(0.0, kd)
    assert not label_is_valid(7.64e19, kd)

    binary = {"censor_policy": "reject_outside_range", "valid_min": "0", "valid_max": "1", "metric": "binding_class"}
    assert label_is_valid(1.0, binary)
    assert label_is_valid(0.0, binary)
    assert not label_is_valid(0.5, binary)


def test_apply_split_manifest(tmp_path: Path) -> None:
    input_path = tmp_path / "input.csv"
    manifest_path = tmp_path / "manifest.csv"
    output_path = tmp_path / "output.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["record_id", "source_group"])
        writer.writeheader()
        writer.writerow({"record_id": "r1", "source_group": "g1"})
    split_columns = [
        "paper_split", "exact_antibody_safe_split", "heuristic_family_safe_split",
        "exact_antigen_safe_split", "time_split",
    ]
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_group", *split_columns])
        writer.writeheader()
        writer.writerow({"source_group": "g1", **{name: "test" for name in split_columns}})

    summary = apply_split_manifest(input_path, manifest_path, output_path)
    assert summary["rows"] == 1
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["paper_split"] == "test"
    assert row["time_split"] == "test"
