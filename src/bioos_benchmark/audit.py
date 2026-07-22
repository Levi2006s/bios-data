from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from .data import ALIASES, _find_key, _header_and_rows, infer_direction, normalize_sequence, parse_number


AUDIT_FIELDS = [
    "source_group", "source_file", "bytes", "sha256", "raw_rows", "valid_rows",
    "heavy_column", "light_column", "antigen_column", "cdrh3_column", "label_column",
    "direction_guess", "with_light", "with_antigen", "with_cdrh3", "status", "note",
]


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
    }
    if not header:
        result["note"] = "No recognized header in first 80 rows"
        return result
    if not keys.get("heavy"):
        result["note"] = "No recognized heavy-chain column"
        return result
    if not keys.get("label"):
        result["note"] = "No directly numeric supported label column"
        return result
    result["direction_guess"] = infer_direction(header, str(keys["label"]))
    for values in rows:
        result["raw_rows"] = int(result["raw_rows"]) + 1
        if len(values) < len(header):
            values += [""] * (len(header) - len(values))
        row = dict(zip(header, values))
        heavy = normalize_sequence(row.get(str(keys["heavy"]), ""))
        label = parse_number(row.get(str(keys["label"]), ""))
        if not heavy or label is None:
            continue
        result["valid_rows"] = int(result["valid_rows"]) + 1
        if keys.get("light") and normalize_sequence(row.get(str(keys["light"]), "")):
            result["with_light"] = int(result["with_light"]) + 1
        if keys.get("antigen_seq") and normalize_sequence(row.get(str(keys["antigen_seq"]), "")):
            result["with_antigen"] = int(result["with_antigen"]) + 1
        if keys.get("cdrh3") and normalize_sequence(row.get(str(keys["cdrh3"]), "")):
            result["with_cdrh3"] = int(result["with_cdrh3"]) + 1
    if int(result["valid_rows"]) > 0:
        result["status"] = "usable"
        result["note"] = "Direction is heuristic until manually verified from the paper"
    else:
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

