"""Purge exact identities from lower-priority splits without moving source groups."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def digest(*values: str) -> bytes:
    return hashlib.blake2b("\x1f".join(values).encode("utf-8"), digest_size=12).digest()


def record_key(row: dict[str, str], entity: str) -> bytes | None:
    if entity == "antibody":
        return digest(row.get("heavy", ""), row.get("light", ""))
    antigen = row.get("antigen_seq", "")
    return digest(antigen) if antigen else None


def purge(
    input_path: Path,
    output_path: Path,
    split_column: str,
    entity: str = "antibody",
    priority: tuple[str, ...] = ("test", "validation", "train"),
) -> dict[str, object]:
    rank = {name: index for index, name in enumerate(priority)}
    selected: dict[bytes, str] = {}
    observed: dict[bytes, set[str]] = {}
    input_counts: Counter[str] = Counter()
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or split_column not in reader.fieldnames:
            raise ValueError(f"missing split column: {split_column}")
        for row in reader:
            split = row[split_column]
            if split not in rank:
                raise ValueError(f"unexpected split value in {split_column}: {split}")
            input_counts[split] += 1
            key = record_key(row, entity)
            if key is None:
                continue
            observed.setdefault(key, set()).add(split)
            previous = selected.get(key)
            if previous is None or rank[split] < rank[previous]:
                selected[key] = split

    output_path.parent.mkdir(parents=True, exist_ok=True)
    kept: Counter[str] = Counter()
    removed: Counter[str] = Counter()
    removed_by_source: Counter[str] = Counter()
    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        with output_path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                split = row[split_column]
                key = record_key(row, entity)
                if key is not None and selected[key] != split:
                    removed[split] += 1
                    removed_by_source[row.get("source_file", "")] += 1
                    continue
                writer.writerow(row)
                kept[split] += 1
    leaking_keys = sum(len(splits) > 1 for splits in observed.values())
    summary = {
        "input": str(input_path), "output": str(output_path), "split_column": split_column,
        "entity": entity, "priority": list(priority), "input_counts": dict(input_counts),
        "kept_counts": dict(kept), "removed_counts": dict(removed),
        "removed_rows": sum(removed.values()), "identity_keys": len(observed),
        "cross_split_identity_keys_before_purge": leaking_keys,
        "largest_removed_sources": removed_by_source.most_common(20),
    }
    output_path.with_suffix(".purge_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-column", required=True)
    parser.add_argument("--entity", choices=("antibody", "antigen"), default="antibody")
    args = parser.parse_args()
    print(json.dumps(purge(args.input, args.output, args.split_column, args.entity), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
