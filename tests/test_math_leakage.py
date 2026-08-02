from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.ranking.leakage import audit_prediction_shortcuts
from bioos_benchmark.ranking.prepare import activate_split


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_activate_split_and_registry_quality(tmp_path: Path) -> None:
    input_path = tmp_path / "input.csv"
    registry_path = tmp_path / "registry.csv"
    output_path = tmp_path / "output.csv"
    _write(input_path, [{"record_id": "r1", "source_group": "g1", "source_file": "f.csv", "paper_split": "train"}])
    _write(registry_path, [{"source_file": "f.csv", "tier": "Silver", "metric": "KD"}])
    report = activate_split(input_path, output_path, split_column="paper_split", label_registry_path=registry_path)
    assert report["counts"] == {"train": 1}
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["split"] == "train"
    assert row["label_quality"] == "0.75"
    assert row["assay_family"] == "KD"


def test_shortcut_audit_detects_exact_and_source_overlap(tmp_path: Path) -> None:
    truth_path = tmp_path / "truth.csv"
    prediction_path = tmp_path / "prediction.csv"
    rows = [
        {"record_id": "t1", "heavy": "AAAA", "light": "", "source_group": "s1", "source_file": "a.csv", "score": "0.1", "split": "train"},
        {"record_id": "t2", "heavy": "CCCC", "light": "", "source_group": "s2", "source_file": "b.csv", "score": "0.9", "split": "train"},
        {"record_id": "v1", "heavy": "AAAA", "light": "", "source_group": "s1", "source_file": "a.csv", "score": "0.2", "split": "validation"},
        {"record_id": "v2", "heavy": "DDDD", "light": "", "source_group": "s3", "source_file": "c.csv", "score": "0.8", "split": "validation"},
    ]
    _write(truth_path, rows)
    _write(prediction_path, [
        {"record_id": "v1", "split": "validation", "source_group": "s1", "target_id": "", "y_true": "0.2", "score": "0.1", "model_id": "m"},
        {"record_id": "v2", "split": "validation", "source_group": "s3", "target_id": "", "y_true": "0.8", "score": "0.9", "model_id": "m"},
    ])
    report = audit_prediction_shortcuts(truth_path, prediction_path)
    assert report["overlap"]["exact_antibody_rows"] == 1
    assert report["overlap"]["source_group_rows"] == 1
    assert report["feature_contract"]["uses_source_metadata"] is False
