"""Assign balanced deterministic splits while keeping exact identities intact."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def identity_key(row: dict[str, str], entity: str) -> str:
    if entity == "antibody":
        return "\x1f".join((row.get("heavy", ""), row.get("light", "")))
    antigen = row.get("antigen_seq", "")
    if not antigen:
        raise ValueError("antigen identity split requires non-empty antigen_seq")
    return antigen


def split_for(key: str, train_fraction: float, validation_fraction: float) -> str:
    bucket = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big") / 2**64
    if bucket < train_fraction:
        return "train"
    if bucket < train_fraction + validation_fraction:
        return "validation"
    return "test"


def assign_identity_split(
    input_path: Path,
    output_path: Path,
    entity: str = "antibody",
    column: str = "exact_antibody_record_split",
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> dict[str, object]:
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 or train_fraction + validation_fraction >= 1:
        raise ValueError("invalid split fractions")
    counts: Counter[str] = Counter()
    keys_by_split: dict[str, set[str]] = {"train": set(), "validation": set(), "test": set()}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("input CSV has no header")
        if column in reader.fieldnames:
            raise ValueError(f"split column already exists: {column}")
        with output_path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=[*reader.fieldnames, column])
            writer.writeheader()
            for row in reader:
                key = identity_key(row, entity)
                split = split_for(key, train_fraction, validation_fraction)
                row[column] = split
                counts[split] += 1
                keys_by_split[split].add(key)
                writer.writerow(row)
    summary = {
        "input": str(input_path), "output": str(output_path), "entity": entity,
        "column": column, "train_fraction": train_fraction,
        "validation_fraction": validation_fraction, "record_counts": dict(counts),
        "unique_identity_counts": {name: len(keys) for name, keys in keys_by_split.items()},
    }
    output_path.with_suffix(".identity_split_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--entity", choices=("antibody", "antigen"), default="antibody")
    parser.add_argument("--column", default="exact_antibody_record_split")
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    args = parser.parse_args()
    result = assign_identity_split(
        args.input, args.output, args.entity, args.column,
        args.train_fraction, args.validation_fraction,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
