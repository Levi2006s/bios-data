"""Attach all reviewed split strategies to a normalized Bio-OS CSV."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


SPLIT_COLUMNS = [
    "paper_split",
    "exact_antibody_safe_split",
    "heuristic_family_safe_split",
    "exact_antigen_safe_split",
    "time_split",
]


def apply_split_manifest(input_path: Path, manifest_path: Path, output_path: Path) -> dict[str, object]:
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    mapping = {row["source_group"]: row for row in manifest_rows}
    counts: dict[str, Counter[str]] = {column: Counter() for column in SPLIT_COLUMNS}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8-sig", newline="") as source_handle:
        reader = csv.DictReader(source_handle)
        if not reader.fieldnames or "source_group" not in reader.fieldnames:
            raise ValueError("input CSV must contain source_group")
        with output_path.open("w", encoding="utf-8", newline="") as target_handle:
            writer = csv.DictWriter(target_handle, fieldnames=list(reader.fieldnames) + SPLIT_COLUMNS)
            writer.writeheader()
            rows = 0
            for row in reader:
                group = row["source_group"]
                if group not in mapping:
                    raise ValueError(f"source_group not found in split manifest: {group}")
                for column in SPLIT_COLUMNS:
                    row[column] = mapping[group][column]
                    counts[column][row[column]] += 1
                writer.writerow(row)
                rows += 1
    summary = {
        "input": str(input_path),
        "manifest": str(manifest_path),
        "output": str(output_path),
        "rows": rows,
        "counts": {name: dict(counter) for name, counter in counts.items()},
    }
    output_path.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach leakage-safe split columns to normalized data.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(apply_split_manifest(args.input, args.manifest, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
