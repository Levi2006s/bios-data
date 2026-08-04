"""Extract one AbRank provenance domain while preserving benchmark splits."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from bioos_benchmark.data import normalize_sequence


def key(heavy: str, light: str, antigen: str) -> tuple[str, str, str]:
    return normalize_sequence(heavy), normalize_sequence(light), normalize_sequence(antigen)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--abrank", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    domain_keys: set[tuple[str, str, str]] = set()
    with args.abrank.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("Source", "").strip() == args.domain:
                domain_keys.add(key(row["Ab_heavy_chain_seq"], row["Ab_light_chain_seq"], row["Ag_seq"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with args.input.open(encoding="utf-8", newline="") as source, args.output.open("w", encoding="utf-8", newline="") as target:
        reader = csv.DictReader(source)
        assert reader.fieldnames
        writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            if key(row["heavy"], row["light"], row["antigen_seq"]) not in domain_keys:
                continue
            writer.writerow(row)
            split = row.get("framework_family_split", "")
            counts[split] = counts.get(split, 0) + 1
    print({"domain": args.domain, "keys": len(domain_keys), "split_counts": counts, "output": str(args.output)})


if __name__ == "__main__":
    main()
