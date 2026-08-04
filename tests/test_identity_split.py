from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.identity_split import assign_identity_split, split_for
from bioos_benchmark.validate import validate


def test_exact_identity_never_crosses_record_split(tmp_path: Path) -> None:
    source, output = tmp_path / "input.csv", tmp_path / "output.csv"
    fields = ["record_id", "source_group", "source_file", "heavy", "light", "antigen_seq", "raw_label", "direction", "score"]
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(fields)
        writer.writerow(["a", "g1", "a.csv", "ACDE", "FGHI", "", "1", "1", "0"])
        writer.writerow(["b", "g2", "b.csv", "ACDE", "FGHI", "", "2", "1", "1"])
        writer.writerow(["c", "g1", "a.csv", "KLMN", "PQRS", "", "3", "1", ".5"])
    summary = assign_identity_split(source, output)
    assert sum(summary["record_counts"].values()) == 3
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert rows[0]["exact_antibody_record_split"] == rows[1]["exact_antibody_record_split"]
    report = validate(output)
    assert report["valid"] is True
    assert report["split_diagnostics"]["exact_antibody_record_split"]["exact_antibody_leakage_keys"] == 0


def test_split_for_is_deterministic() -> None:
    assert split_for("same", .7, .15) == split_for("same", .7, .15)
