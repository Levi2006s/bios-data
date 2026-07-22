from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from .data import AA20


REQUIRED = {
    "record_id", "source_group", "source_file", "heavy", "raw_label",
    "direction", "score",
}


def validate(path: Path) -> dict[str, object]:
    errors: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    group_splits: defaultdict[str, set[str]] = defaultdict(set)
    row_count = 0

    def add_error(row: int, code: str, detail: str) -> None:
        if len(errors) < 50:
            errors.append({"row": row, "code": code, "detail": detail})

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            return {"path": str(path), "valid": False, "rows": 0, "errors": [{"row": 1, "code": "missing_columns", "detail": sorted(missing)}]}
        for line_number, row in enumerate(reader, start=2):
            row_count += 1
            record_id = row["record_id"]
            if record_id in seen_ids:
                add_error(line_number, "duplicate_record_id", record_id)
            seen_ids.add(record_id)
            for key in ("heavy", "light", "antigen_seq", "cdrh3"):
                sequence = row.get(key, "")
                if sequence and not set(sequence) <= AA20:
                    add_error(line_number, "invalid_amino_acid", key)
            try:
                score = float(row["score"])
                if not 0 <= score <= 1:
                    add_error(line_number, "score_out_of_range", row["score"])
            except ValueError:
                add_error(line_number, "non_numeric_score", row["score"])
            if row["direction"] not in {"-1", "1"}:
                add_error(line_number, "invalid_direction", row["direction"])
            if row.get("split"):
                group_splits[row["source_group"]].add(row["split"])
    for group, splits in group_splits.items():
        if len(splits) > 1:
            add_error(0, "split_leakage", f"{group}: {sorted(splits)}")
    return {
        "path": str(path),
        "valid": not errors,
        "rows": row_count,
        "unique_record_ids": len(seen_ids),
        "source_groups": len(group_splits) if group_splits else None,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate normalized Bio-OS data.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate(args.input)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

