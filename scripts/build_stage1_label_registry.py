#!/usr/bin/env python3
"""Build a conservative, review-required label registry from stage-1 inventory."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


FIELDS = [
    "dataset_id", "path", "sheet", "study_id", "data_role", "assay_type",
    "proposed_label_column", "proposed_direction", "unit", "quality_tier",
    "comparable_group", "censoring", "review_status", "review_notes",
]


def assay_from(path: str, labels: list[str]) -> str:
    text = " ".join([path, *labels]).lower()
    if "binary" in text or "bind/no bind" in text:
        return "binary_binding"
    if "ic50" in text or "neutralization" in text:
        return "ic50"
    if "ec50" in text:
        return "ec50"
    if re.search(r"(^|[^a-z])kd([^a-z]|$)", text) or "affinity" in text:
        return "kd_affinity"
    if "binding" in text:
        return "binding_proxy"
    return "unknown"


def choose_label(labels: list[str], assay: str) -> str:
    if "fitness" in labels:
        return "fitness"
    if assay == "binary_binding":
        return next((label for label in labels if "bind/no bind" in label.lower()), labels[0] if labels else "")
    preferred = ("pred_affinity", "neg_log", "log_aff", "affinity_kd", "kd", "ic50", "ec50")
    for hint in preferred:
        for label in labels:
            if hint in label.lower():
                return label
    return labels[0] if labels else ""


def proposed_direction(label: str, assay: str) -> str:
    value = label.lower()
    if label == "fitness" or "neg_log" in value or "-log" in value or "log_aff" in value:
        return "higher_is_better"
    if assay in {"kd_affinity", "ic50", "ec50"}:
        return "lower_is_better"
    if assay == "binary_binding":
        return "positive_class_is_better"
    return "pending_review"


def registry_row(record: dict, index: int) -> dict[str, str]:
    path = record["path"]
    labels = record["label_candidates"]
    assay = assay_from(path, labels)
    label = choose_label(labels, assay)
    is_structure = record["format"] in {"xlsx", "tsv"}
    is_unlabeled = not labels
    is_prediction = any("pred_affinity" in item.lower() for item in labels)
    is_binary = assay == "binary_binding"
    if is_structure:
        role, tier = "structure_metadata", "pending_review"
    elif is_unlabeled:
        role, tier = "unlabeled_auxiliary", "auxiliary"
    elif is_binary:
        role, tier = "classification_auxiliary", "auxiliary"
    elif is_prediction:
        role, tier = "predicted_label", "weak"
    else:
        role, tier = "ranking_supervision_candidate", "pending_review"
    parts = Path(path).parts
    study_id = parts[1] if len(parts) > 2 and parts[0] == "初赛-序列数据" else Path(path).stem
    notes = []
    if label == "fitness":
        notes.append("fitness_semantics_must_be_verified_against_raw_label")
    if is_structure:
        notes.append("structure_rows_must_be_deduplicated_by_structure_id")
    if is_unlabeled:
        notes.append("no_direct_supervision")
    return {
        "dataset_id": f"ds_{index:03d}", "path": path, "sheet": record["sheet"],
        "study_id": study_id, "data_role": role, "assay_type": assay,
        "proposed_label_column": label, "proposed_direction": proposed_direction(label, assay),
        "unit": "pending_review", "quality_tier": tier,
        "comparable_group": "pending_review", "censoring": "pending_review",
        "review_status": "pending_review", "review_notes": ";".join(notes),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=Path("data/processed/stage1_inventory.json"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/stage1_label_registry_review.csv"))
    args = parser.parse_args()
    payload = json.loads(args.inventory.read_text(encoding="utf-8"))
    rows = [registry_row(record, index) for index, record in enumerate(payload["records"], 1)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"records": len(rows), "pending_review": len(rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
