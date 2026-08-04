from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.family_split import (
    assign_family_split, balanced_family_assignment, framework_family_key,
    sequence_framework_family_key,
)


def test_framework_family_groups_matching_anchors() -> None:
    base = "ACDEFGHIKLMNPQRSTVWY" + "A" * 80
    left = {"heavy": base + "A", "light": base, "cdrh3": "ACDEFG"}
    right = {"heavy": base + "C", "light": base, "cdrh3": "YYYYYY"}
    assert framework_family_key(left) == framework_family_key(right)


def test_family_split_keeps_family_together(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"
    fields = ["record_id", "heavy", "light", "cdrh3"]
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"record_id": "a", "heavy": "A" * 100, "light": "C" * 100, "cdrh3": "D" * 10})
        writer.writerow({"record_id": "b", "heavy": "A" * 99 + "E", "light": "C" * 100, "cdrh3": "F" * 10})
    report = assign_family_split(source, output)
    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["framework_family_split"] == rows[1]["framework_family_split"]
    assert sum(report["record_counts"].values()) == 2


def test_balanced_assignment_is_deterministic_and_keeps_keys_whole() -> None:
    sizes = {f"f{index}": index + 1 for index in range(30)}
    first = balanced_family_assignment(sizes, 0.7, 0.15)
    second = balanced_family_assignment(dict(reversed(list(sizes.items()))), 0.7, 0.15)
    assert first == second
    assert set(first) == set(sizes)
    assert set(first.values()) == {"train", "validation", "test"}


def test_v2_key_ignores_inconsistent_cdr_annotation_for_exact_sequence() -> None:
    row = {"heavy": "ACDEFGHIKLMNPQRSTVWY" * 6, "light": "YWVTSRQPNMLKIHGFEDCA" * 5}
    assert sequence_framework_family_key({**row, "cdrh3": "AAAA"}) == sequence_framework_family_key(
        {**row, "cdrh3": ""}
    )


def test_v2_split_keeps_metadata_conflicted_duplicates_together(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"
    fields = ["record_id", "heavy", "light", "cdrh3"]
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        sequence = "ACDEFGHIKLMNPQRSTVWY" * 6
        writer.writerow({"record_id": "a", "heavy": sequence, "light": "", "cdrh3": "AAAA"})
        writer.writerow({"record_id": "b", "heavy": sequence, "light": "", "cdrh3": ""})
    assign_family_split(source, output, column="global_family_v2_split", key_version="v2")
    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["global_family_v2_split"] == rows[1]["global_family_v2_split"]
