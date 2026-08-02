from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from .data import AA20


REQUIRED = {
    "record_id", "source_group", "source_file", "heavy", "raw_label",
    "direction", "score",
}

KNOWN_SPLIT_COLUMNS = (
    "split", "paper_split", "exact_antibody_safe_split",
    "heuristic_family_safe_split", "exact_antigen_safe_split", "time_split",
    "exact_antibody_record_split",
)


def identity_digest(*values: str) -> bytes:
    return hashlib.blake2b("\x1f".join(values).encode("utf-8"), digest_size=12).digest()


def validate(path: Path) -> dict[str, object]:
    errors: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    group_splits: dict[str, defaultdict[str, set[str]]] = {}
    first_antibody_split: dict[str, dict[bytes, str]] = {}
    first_antigen_split: dict[str, dict[bytes, str]] = {}
    antibody_leak_keys: dict[str, set[bytes]] = {}
    antigen_leak_keys: dict[str, set[bytes]] = {}
    split_counts: dict[str, Counter[str]] = {}
    row_count = 0

    def add_error(row: int, code: str, detail: str) -> None:
        if len(errors) < 50:
            errors.append({"row": row, "code": code, "detail": detail})

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            return {"path": str(path), "valid": False, "rows": 0, "errors": [{"row": 1, "code": "missing_columns", "detail": sorted(missing)}]}
        split_columns = [name for name in KNOWN_SPLIT_COLUMNS if name in (reader.fieldnames or [])]
        for name in split_columns:
            group_splits[name] = defaultdict(set)
            first_antibody_split[name] = {}
            first_antigen_split[name] = {}
            antibody_leak_keys[name] = set()
            antigen_leak_keys[name] = set()
            split_counts[name] = Counter()
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
            antibody_key = identity_digest(row.get("heavy", ""), row.get("light", ""))
            antigen = row.get("antigen_seq", "")
            antigen_key = identity_digest(antigen) if antigen else None
            for name in split_columns:
                split = row.get(name, "")
                if not split:
                    add_error(line_number, "missing_split", name)
                    continue
                split_counts[name][split] += 1
                group_splits[name][row["source_group"]].add(split)
                prior = first_antibody_split[name].setdefault(antibody_key, split)
                if prior != split:
                    antibody_leak_keys[name].add(antibody_key)
                if antigen_key is not None:
                    prior_antigen = first_antigen_split[name].setdefault(antigen_key, split)
                    if prior_antigen != split:
                        antigen_leak_keys[name].add(antigen_key)
    split_diagnostics = {}
    for name in split_columns:
        leaking_groups = {group: sorted(splits) for group, splits in group_splits[name].items() if len(splits) > 1}
        split_diagnostics[name] = {
            "record_counts": dict(split_counts[name]),
            "source_groups": len(group_splits[name]),
            "source_group_leakage_count": len(leaking_groups),
            "source_group_leakage_examples": dict(list(sorted(leaking_groups.items()))[:10]),
            "exact_antibody_leakage_keys": len(antibody_leak_keys[name]),
            "exact_antigen_leakage_keys": len(antigen_leak_keys[name]),
        }
        if name in {"split", "paper_split", "exact_antibody_safe_split", "heuristic_family_safe_split", "exact_antigen_safe_split", "time_split"} and leaking_groups:
            add_error(0, "source_group_split_leakage", f"{name}: {len(leaking_groups)} groups")
        if name in {"exact_antibody_safe_split", "heuristic_family_safe_split", "exact_antibody_record_split"} and antibody_leak_keys[name]:
            add_error(0, "exact_antibody_split_leakage", f"{name}: {len(antibody_leak_keys[name])} keys")
        if name == "exact_antigen_safe_split" and antigen_leak_keys[name]:
            add_error(0, "exact_antigen_split_leakage", f"{name}: {len(antigen_leak_keys[name])} keys")
    return {
        "path": str(path),
        "valid": not errors,
        "rows": row_count,
        "unique_record_ids": len(seen_ids),
        "source_groups": len(next(iter(group_splits.values()))) if group_splits else None,
        "split_diagnostics": split_diagnostics,
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
