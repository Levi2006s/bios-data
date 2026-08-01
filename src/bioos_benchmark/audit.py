from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .data import AA20, ALIASES, _find_key, _header_and_rows, infer_direction, normalize_sequence, parse_number


AUDIT_FIELDS = [
    "source_group", "source_file", "bytes", "sha256", "raw_rows", "valid_rows",
    "column_count", "columns_json", "numeric_label_rows", "missing_or_invalid_label_rows",
    "valid_heavy_rows", "missing_heavy_rows", "invalid_heavy_rows",
    "heavy_column", "light_column", "antigen_column", "cdrh3_column", "label_column",
    "direction_guess", "with_light", "with_antigen", "with_cdrh3", "status", "note",
    "invalid_light", "invalid_antigen", "invalid_cdrh3",
    "heavy_min_len", "heavy_mean_len", "heavy_max_len",
    "light_min_len", "light_mean_len", "light_max_len",
    "antigen_min_len", "antigen_mean_len", "antigen_max_len",
    "cdrh3_min_len", "cdrh3_mean_len", "cdrh3_max_len",
    "label_min", "label_mean", "label_max",
]


def sequence_state(value: object) -> tuple[str, str]:
    """Return normalized sequence plus missing/valid/invalid state."""
    raw = str(value or "").strip()
    if not raw:
        return "", "missing"
    letters = re.sub(r"[^A-Za-z]", "", raw).upper()
    if not letters or not set(letters) <= AA20:
        return "", "invalid"
    return letters, "valid"


def length_summary(lengths: list[int]) -> tuple[object, object, object]:
    if not lengths:
        return "", "", ""
    return min(lengths), sum(lengths) / len(lengths), max(lengths)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_file(path: Path, data_root: Path, compute_hash: bool) -> dict[str, object]:
    source = path.relative_to(data_root).as_posix()
    parts = source.split("/")
    group = "/".join(parts[:2]) if len(parts) >= 2 else source
    header, rows = _header_and_rows(path)
    keys = {name: _find_key(header, aliases) for name, aliases in ALIASES.items()} if header else {}
    result: dict[str, object] = {
        "source_group": group,
        "source_file": source,
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path) if compute_hash else "",
        "raw_rows": 0,
        "valid_rows": 0,
        "column_count": len(header),
        "columns_json": json.dumps(header, ensure_ascii=False),
        "numeric_label_rows": 0,
        "missing_or_invalid_label_rows": 0,
        "valid_heavy_rows": 0,
        "missing_heavy_rows": 0,
        "invalid_heavy_rows": 0,
        "heavy_column": keys.get("heavy") or "",
        "light_column": keys.get("light") or "",
        "antigen_column": keys.get("antigen_seq") or "",
        "cdrh3_column": keys.get("cdrh3") or "",
        "label_column": keys.get("label") or "",
        "direction_guess": "",
        "with_light": 0,
        "with_antigen": 0,
        "with_cdrh3": 0,
        "status": "unusable",
        "note": "",
        "invalid_light": 0,
        "invalid_antigen": 0,
        "invalid_cdrh3": 0,
        "heavy_min_len": "",
        "heavy_mean_len": "",
        "heavy_max_len": "",
        "light_min_len": "",
        "light_mean_len": "",
        "light_max_len": "",
        "antigen_min_len": "",
        "antigen_mean_len": "",
        "antigen_max_len": "",
        "cdrh3_min_len": "",
        "cdrh3_mean_len": "",
        "cdrh3_max_len": "",
        "label_min": "",
        "label_mean": "",
        "label_max": "",
    }
    if not header:
        result["note"] = "No recognized header in first 80 rows"
        return result
    if not keys.get("heavy"):
        result["note"] = "No recognized heavy-chain column"
    elif not keys.get("label"):
        result["note"] = "No directly numeric supported label column"
    else:
        result["direction_guess"] = infer_direction(header, str(keys["label"]))
    lengths: dict[str, list[int]] = {
        "heavy": [], "light": [], "antigen": [], "cdrh3": [],
    }
    valid_labels: list[float] = []
    for values in rows:
        result["raw_rows"] = int(result["raw_rows"]) + 1
        if len(values) < len(header):
            values += [""] * (len(header) - len(values))
        row = dict(zip(header, values))
        heavy, heavy_state = sequence_state(
            row.get(str(keys["heavy"]), "") if keys.get("heavy") else ""
        )
        label = (
            parse_number(row.get(str(keys["label"]), ""))
            if keys.get("label")
            else None
        )
        if heavy_state == "valid":
            result["valid_heavy_rows"] = int(result["valid_heavy_rows"]) + 1
            lengths["heavy"].append(len(heavy))
        elif heavy_state == "missing":
            result["missing_heavy_rows"] = int(result["missing_heavy_rows"]) + 1
        else:
            result["invalid_heavy_rows"] = int(result["invalid_heavy_rows"]) + 1
        if label is None:
            result["missing_or_invalid_label_rows"] = int(result["missing_or_invalid_label_rows"]) + 1
        else:
            result["numeric_label_rows"] = int(result["numeric_label_rows"]) + 1
        for key_name, result_name, invalid_name, length_name in (
            ("light", "with_light", "invalid_light", "light"),
            ("antigen_seq", "with_antigen", "invalid_antigen", "antigen"),
            ("cdrh3", "with_cdrh3", "invalid_cdrh3", "cdrh3"),
        ):
            if not keys.get(key_name):
                continue
            sequence, state = sequence_state(row.get(str(keys[key_name]), ""))
            if state == "valid":
                result[result_name] = int(result[result_name]) + 1
                lengths[length_name].append(len(sequence))
            elif state == "invalid":
                result[invalid_name] = int(result[invalid_name]) + 1
        if not heavy or label is None:
            continue
        result["valid_rows"] = int(result["valid_rows"]) + 1
        valid_labels.append(label)
    for name in ("heavy", "light", "antigen", "cdrh3"):
        minimum, mean, maximum = length_summary(lengths[name])
        result[f"{name}_min_len"] = minimum
        result[f"{name}_mean_len"] = mean
        result[f"{name}_max_len"] = maximum
    if valid_labels:
        result["label_min"] = min(valid_labels)
        result["label_mean"] = sum(valid_labels) / len(valid_labels)
        result["label_max"] = max(valid_labels)
    if int(result["valid_rows"]) > 0:
        result["status"] = "usable"
        result["note"] = "Direction is heuristic until manually verified from the paper"
    elif not result["note"]:
        result["note"] = "Header recognized but no valid numeric labeled records"
    return result


def audit(data_root: Path, output: Path, compute_hash: bool) -> dict[str, object]:
    files = sorted((data_root / "初赛-序列数据").rglob("*.csv"))
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = [audit_file(path, data_root, compute_hash) for path in files]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    status = Counter(str(row["status"]) for row in rows)
    summary = {
        "data_root": str(data_root),
        "csv_files": len(rows),
        "status": dict(status),
        "raw_rows": sum(int(row["raw_rows"]) for row in rows),
        "valid_rows": sum(int(row["valid_rows"]) for row in rows),
        "numeric_label_rows": sum(int(row["numeric_label_rows"]) for row in rows),
        "missing_or_invalid_label_rows": sum(int(row["missing_or_invalid_label_rows"]) for row in rows),
        "valid_heavy_rows": sum(int(row["valid_heavy_rows"]) for row in rows),
        "missing_heavy_rows": sum(int(row["missing_heavy_rows"]) for row in rows),
        "invalid_heavy_rows": sum(int(row["invalid_heavy_rows"]) for row in rows),
        "rows_with_light": sum(int(row["with_light"]) for row in rows),
        "rows_with_antigen_sequence": sum(int(row["with_antigen"]) for row in rows),
        "rows_with_cdrh3": sum(int(row["with_cdrh3"]) for row in rows),
        "invalid_light_rows": sum(int(row["invalid_light"]) for row in rows),
        "invalid_antigen_rows": sum(int(row["invalid_antigen"]) for row in rows),
        "invalid_cdrh3_rows": sum(int(row["invalid_cdrh3"]) for row in rows),
        "files_with_light": sum(int(row["with_light"]) > 0 for row in rows),
        "files_with_antigen_sequence": sum(int(row["with_antigen"]) > 0 for row in rows),
        "files_with_cdrh3": sum(int(row["with_cdrh3"]) > 0 for row in rows),
        "hash_inputs": compute_hash,
        "audit_csv": str(output),
    }
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit all Bio-OS sequence CSV files.")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/processed/audit.csv"))
    parser.add_argument("--hash-inputs", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.data_root, args.output, args.hash_inputs), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
