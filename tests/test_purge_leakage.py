from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.purge_leakage import purge
from bioos_benchmark.validate import validate


def test_purge_prefers_held_out_identity(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"
    fields = ["record_id", "source_group", "source_file", "heavy", "light", "antigen_seq", "raw_label", "direction", "score", "paper_split"]
    rows = [
        ["a", "g1", "train.csv", "ACDE", "FGHI", "", "1", "1", "0", "train"],
        ["b", "g2", "test.csv", "ACDE", "FGHI", "", "2", "1", "1", "test"],
        ["c", "g1", "train.csv", "KLMN", "PQRS", "", "3", "1", ".5", "train"],
    ]
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(fields); writer.writerows(rows)
    summary = purge(source, output, "paper_split")
    assert summary["removed_counts"] == {"train": 1}
    kept = list(csv.DictReader(output.open(encoding="utf-8")))
    assert {row["record_id"] for row in kept} == {"b", "c"}
    report = validate(output)
    assert report["split_diagnostics"]["paper_split"]["exact_antibody_leakage_keys"] == 0
