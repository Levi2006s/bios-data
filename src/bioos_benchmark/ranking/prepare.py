"""Prepare one reviewed split strategy for the mathematical ranking route."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ALLOWED_SPLITS = {"train", "validation", "test"}
TIER_QUALITY = {"Gold": 1.0, "Silver": 0.75, "Weak": 0.4, "Auxiliary": 0.0}


def activate_split(
    input_path: Path,
    output_path: Path,
    *,
    split_column: str,
    label_registry_path: Path | None = None,
) -> dict[str, object]:
    """Activate a split and keep only labels valid for the primary affinity head.

    Older registries without certification columns retain the legacy tier
    behavior.  Revised registries use ``primary_affinity_weight`` and exclude
    task-specific endpoints (IC50, EC50, binary, OVA risk, and unsplit mixed
    endpoints) from this affinity-only mathematical route.
    """
    registry: dict[str, dict[str, str]] = {}
    if label_registry_path is not None:
        with label_registry_path.open("r", encoding="utf-8-sig", newline="") as handle:
            registry = {row["source_file"]: row for row in csv.DictReader(handle)}

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or split_column not in reader.fieldnames:
            raise ValueError(f"input CSV does not contain split column: {split_column}")
        rows = list(reader)
        fieldnames = list(reader.fieldnames)
    for field in (
        "split", "split_group", "label_quality", "assay_family", "label_tier",
        "affinity_grade", "training_head", "certification_version",
    ):
        if field not in fieldnames:
            fieldnames.append(field)

    counts: Counter[str] = Counter()
    excluded_heads: Counter[str] = Counter()
    missing_registry = 0
    selected_rows: list[dict[str, str]] = []
    for row in rows:
        split = str(row.get(split_column, "")).strip()
        if split not in ALLOWED_SPLITS:
            raise ValueError(f"invalid {split_column} value: {split!r}")
        row["split"] = split
        row["split_group"] = str(row.get("source_group", "")).strip()
        registry_row = registry.get(str(row.get("source_file", "")).strip())
        if registry_row is None:
            missing_registry += 1
            row.setdefault("label_quality", "1")
            row.setdefault("assay_family", "")
            row.setdefault("label_tier", "")
        else:
            tier = registry_row.get("tier", "")
            row["label_tier"] = tier
            certified_weight = registry_row.get("primary_affinity_weight", "").strip()
            if certified_weight:
                weight = float(certified_weight)
                if weight <= 0:
                    excluded_heads[registry_row.get("training_head", "unknown")] += 1
                    continue
                row["label_quality"] = f"{weight:.12g}"
            else:
                row["label_quality"] = f"{TIER_QUALITY.get(tier, 0.5):.12g}"
            row["assay_family"] = registry_row.get("metric", "")
            row["affinity_grade"] = registry_row.get("affinity_grade", "")
            row["training_head"] = registry_row.get("training_head", "")
            row["certification_version"] = registry_row.get("certification_version", "")
        counts[split] += 1
        selected_rows.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected_rows)
    summary = {
        "input": str(input_path),
        "output": str(output_path),
        "split_column": split_column,
        "counts": dict(counts),
        "input_rows": len(rows),
        "rows": len(selected_rows),
        "excluded_non_primary_affinity_rows": sum(excluded_heads.values()),
        "excluded_by_training_head": dict(excluded_heads),
        "registry": str(label_registry_path) if label_registry_path else None,
        "registry_rows_missing": missing_registry,
        "tier_quality": TIER_QUALITY,
        "quality_policy": "certified primary_affinity_weight when present; otherwise legacy tier",
    }
    output_path.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate one leakage-safe split strategy.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-column", required=True)
    parser.add_argument("--label-registry", type=Path)
    args = parser.parse_args()
    report = activate_split(
        args.input,
        args.output,
        split_column=args.split_column,
        label_registry_path=args.label_registry,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
