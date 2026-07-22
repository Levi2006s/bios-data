from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def group_order(group: str) -> bytes:
    return hashlib.sha256(group.encode("utf-8")).digest()


def assign_groups(groups: list[str], train_fraction: float, val_fraction: float) -> dict[str, str]:
    ordered = sorted(set(groups), key=group_order)
    if len(ordered) < 3:
        raise ValueError("At least three source groups are required for train/validation/test splits.")
    train_count = max(1, round(len(ordered) * train_fraction))
    val_count = max(1, round(len(ordered) * val_fraction))
    if train_count + val_count >= len(ordered):
        train_count = len(ordered) - 2
        val_count = 1
    mapping: dict[str, str] = {}
    for index, group in enumerate(ordered):
        if index < train_count:
            split = "train"
        elif index < train_count + val_count:
            split = "validation"
        else:
            split = "test"
        mapping[group] = split
    return mapping


def make_split(input_path: Path, output_path: Path, train_fraction: float, val_fraction: float) -> dict[str, object]:
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "source_group" not in rows[0]:
        raise ValueError("Input must be a non-empty normalized CSV with source_group.")
    mapping = assign_groups([row["source_group"] for row in rows], train_fraction, val_fraction)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) + ["split"]
    counts = {"train": 0, "validation": 0, "test": 0}
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            row["split"] = mapping[row["source_group"]]
            counts[row["split"]] += 1
            writer.writerow(row)
    manifest = {
        "input": str(input_path),
        "output": str(output_path),
        "method": "deterministic SHA-256 ordering of complete literature dataset groups",
        "train_fraction_requested": train_fraction,
        "validation_fraction_requested": val_fraction,
        "record_counts": counts,
        "group_assignments": mapping,
    }
    output_path.with_suffix(".split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Create leakage-aware deterministic splits.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/processed/benchmark_with_split.csv"))
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    args = parser.parse_args()
    if not 0 < args.train_fraction < 1 or not 0 < args.validation_fraction < 1:
        raise ValueError("Fractions must be between 0 and 1.")
    if args.train_fraction + args.validation_fraction >= 1:
        raise ValueError("Train and validation fractions must sum to less than 1.")
    print(
        json.dumps(
            make_split(args.input, args.output, args.train_fraction, args.validation_fraction),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

