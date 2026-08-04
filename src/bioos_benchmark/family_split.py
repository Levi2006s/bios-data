"""Record-level framework-family split for fast homology stress testing."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

def framework_family_key(row: dict[str, str]) -> str:
    """Return a deliberately coarse deterministic family bucket.

    This groups records by N-terminal framework anchors, length buckets, and
    CDR-H3 length. It is stricter than exact-identity splitting but is not a
    substitute for alignment-based MMseqs2/CD-HIT clustering.
    """
    heavy = row.get("heavy", "")
    light = row.get("light", "")
    cdrh3 = row.get("cdrh3", "")
    if not heavy:
        raise ValueError("heavy sequence is required")
    def tail_sketch(sequence: str) -> str:
        tail = sequence[-36:]
        return "".join(tail[index] for index in range(0, len(tail), 6))

    parts = (
        heavy[:20], str(len(heavy) // 5),
        light[:20] if light else "VHH", str(len(light) // 5),
        str(len(cdrh3)) if cdrh3 else "unknown_cdrh3",
        tail_sketch(heavy), tail_sketch(light) if light else "VHH",
    )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]


def sequence_framework_family_key(row: dict[str, str]) -> str:
    """Sequence-only family key that is stable across literature metadata.

    The original stress-test key includes the supplied ``cdrh3`` length.  The
    same antibody can have a missing or differently annotated CDR-H3 in two
    papers, which can put exact duplicates in different folds.  V2 derives
    every component from the actual heavy/light strings, so exact identity is
    guaranteed to imply identical family assignment.
    """
    heavy = row.get("heavy", "")
    light = row.get("light", "")
    if not heavy:
        raise ValueError("heavy sequence is required")

    def tail_sketch(sequence: str) -> str:
        tail = sequence[-36:]
        return "".join(tail[index] for index in range(0, len(tail), 6))

    parts = (
        heavy[:20], str(len(heavy) // 5),
        light[:20] if light else "VHH", str(len(light) // 5),
        tail_sketch(heavy), tail_sketch(light) if light else "VHH",
    )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]


def balanced_family_assignment(
    family_sizes: dict[str, int], train_fraction: float, validation_fraction: float,
) -> dict[str, str]:
    """Greedily balance record load while preserving whole family buckets."""
    fractions = {
        "train": train_fraction,
        "validation": validation_fraction,
        "test": 1.0 - train_fraction - validation_fraction,
    }
    total = sum(family_sizes.values())
    targets = {name: total * fraction for name, fraction in fractions.items()}
    loads = {name: 0 for name in fractions}
    assignment = {}
    ordered = sorted(family_sizes.items(), key=lambda item: (-item[1], item[0]))
    for index, (family, size) in enumerate(ordered):
        if index == 0:
            assignment[family] = "train"
            loads["train"] += size
            continue
        split = min(loads, key=lambda name: (loads[name] / targets[name], name))
        assignment[family] = split
        loads[split] += size
    return assignment


def assign_family_split(
    input_path: Path,
    output_path: Path,
    *,
    column: str = "framework_family_split",
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
    key_version: str = "v1",
) -> dict[str, object]:
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 or train_fraction + validation_fraction >= 1:
        raise ValueError("invalid split fractions")
    key_function = framework_family_key if key_version == "v1" else sequence_framework_family_key
    if key_version not in {"v1", "v2"}:
        raise ValueError(f"unknown family key version: {key_version}")
    family_sizes: Counter[str] = Counter()
    with input_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("input CSV has no header")
        if column in reader.fieldnames:
            raise ValueError(f"split column already exists: {column}")
        fieldnames = reader.fieldnames
        for row in reader:
            family_sizes[key_function(row)] += 1
    assignment = balanced_family_assignment(dict(family_sizes), train_fraction, validation_fraction)
    record_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter(assignment.values())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        with output_path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=[*fieldnames, column])
            writer.writeheader()
            for row in reader:
                family = key_function(row)
                split = assignment[family]
                row[column] = split
                record_counts[split] += 1
                writer.writerow(row)
    summary = {
        "input": str(input_path), "output": str(output_path), "column": column,
        "method": "coarse_framework_anchor_bucket_with_greedy_record_balancing_not_alignment_clustering",
        "key_version": key_version,
        "train_fraction": train_fraction, "validation_fraction": validation_fraction,
        "record_counts": dict(record_counts), "unique_family_counts": dict(family_counts),
    }
    output_path.with_suffix(".family_split_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--column", default="framework_family_split")
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--key-version", choices=("v1", "v2"), default="v1")
    args = parser.parse_args()
    print(json.dumps(assign_family_split(
        args.input, args.output, column=args.column,
        train_fraction=args.train_fraction, validation_fraction=args.validation_fraction,
        key_version=args.key_version,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
