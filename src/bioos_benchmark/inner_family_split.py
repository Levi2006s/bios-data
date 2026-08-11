"""Create a train-only inner family holdout without touching outer validation."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from .family_split import sequence_framework_family_key


def build_inner_split(
    input_path: Path,
    output_path: Path,
    *,
    outer_column: str = "global_family_v2_split",
    inner_column: str = "stage21_inner_family_split",
    route: str = "alphaseq_rank",
    train_fraction: float = 0.8,
) -> dict[str, object]:
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be between zero and one")
    family_sizes: Counter[str] = Counter()
    with input_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("input CSV has no header")
        if inner_column in reader.fieldnames:
            raise ValueError(f"split column already exists: {inner_column}")
        fieldnames = reader.fieldnames
        for row in reader:
            if row.get(outer_column) == "train" and row.get("task_route") == route:
                family_sizes[sequence_framework_family_key(row)] += 1

    targets = {"train": sum(family_sizes.values()) * train_fraction, "validation": sum(family_sizes.values()) * (1.0 - train_fraction)}
    loads = {"train": 0, "validation": 0}
    assignments: dict[str, str] = {}
    for index, (family, size) in enumerate(sorted(family_sizes.items(), key=lambda item: (-item[1], item[0]))):
        split = "train" if index == 0 else min(loads, key=lambda name: (loads[name] / targets[name], name))
        assignments[family] = split
        loads[split] += size

    record_counts: Counter[str] = Counter()
    family_counts = Counter(assignments.values())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open(encoding="utf-8", newline="") as source, output_path.open("w", encoding="utf-8", newline="") as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=[*fieldnames, inner_column])
        writer.writeheader()
        for row in reader:
            if row.get(outer_column) == "train" and row.get("task_route") == route:
                split = assignments[sequence_framework_family_key(row)]
            else:
                split = "excluded"
            row[inner_column] = split
            record_counts[split] += 1
            writer.writerow(row)

    report = {
        "input": str(input_path), "output": str(output_path),
        "outer_column": outer_column, "inner_column": inner_column, "route": route,
        "train_fraction": train_fraction, "record_counts": dict(record_counts),
        "family_counts": dict(family_counts), "assigned_loads": loads,
        "outer_validation_policy": "excluded_from_inner_model_development",
    }
    output_path.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--outer-column", default="global_family_v2_split")
    parser.add_argument("--inner-column", default="stage21_inner_family_split")
    parser.add_argument("--route", default="alphaseq_rank")
    parser.add_argument("--train-fraction", type=float, default=0.8)
    args = parser.parse_args()
    print(json.dumps(build_inner_split(args.input, args.output, outer_column=args.outer_column, inner_column=args.inner_column, route=args.route, train_fraction=args.train_fraction), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
