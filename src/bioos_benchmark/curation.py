"""Human-reviewed label validation, duplicate tracking and leakage-safe split plans."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .audit import sequence_state
from .data import ALIASES, _find_key, _header_and_rows, parse_number
from .split import assign_groups


@dataclass
class UnionFind:
    parent: dict[str, str]

    @classmethod
    def create(cls, groups: list[str]) -> "UnionFind":
        return cls({group: group for group in groups})

    def find(self, item: str) -> str:
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            item, self.parent[item] = self.parent[item], root
        return root

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def load_registry(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    registry = {row["source_file"].replace("\\", "/"): row for row in rows}
    if len(registry) != len(rows):
        raise ValueError("label registry contains duplicate source_file entries")
    return registry


def label_is_valid(value: float | None, entry: dict[str, str]) -> bool:
    if value is None or not math.isfinite(value):
        return False
    policy = entry["censor_policy"]
    minimum = parse_number(entry.get("valid_min", ""))
    maximum = parse_number(entry.get("valid_max", ""))
    if policy in {"require_positive_finite", "require_positive_and_below_max"} and value <= 0:
        return False
    if minimum is not None and value < minimum:
        return False
    if maximum is not None and value > maximum:
        return False
    if entry["metric"] == "binding_class" and value not in {0.0, 1.0}:
        return False
    return True


def digest(*parts: str) -> bytes:
    return hashlib.blake2b("\x1f".join(parts).encode("utf-8"), digest_size=12).digest()


def antibody_family_key(heavy: str, light: str, cdrh3: str) -> bytes:
    """A transparent LSH-like family bucket, not a replacement for MMseqs2 clustering."""
    h_anchor = heavy[:24] + heavy[-18:]
    l_anchor = light[:24] + light[-18:] if light else "VHH"
    cdr_anchor = cdrh3 if cdrh3 else heavy[-28:-8]
    return digest(str(len(heavy) // 5), str(len(light) // 5), h_anchor, l_anchor, cdr_anchor)


def component_assignments(groups: list[str], union: UnionFind) -> tuple[dict[str, str], dict[str, str]]:
    roots = {group: union.find(group) for group in groups}
    components = sorted(set(roots.values()))
    if len(components) >= 3:
        component_split = assign_groups(components, 0.70, 0.15)
    else:
        component_split = {component: "train" for component in components}
    return roots, {group: component_split[roots[group]] for group in groups}


def time_split(year: int) -> str:
    if year <= 2022:
        return "train"
    if year == 2023:
        return "validation"
    return "test"


def curate_audit(
    data_root: Path,
    registry_path: Path,
    audit_csv: Path,
    output_dir: Path,
    imgt_samples_per_file: int = 50,
) -> dict[str, object]:
    registry = load_registry(registry_path)
    with audit_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))
    audited = {row["source_file"].replace("\\", "/") for row in audit_rows}
    missing_registry = sorted(audited - set(registry))
    extra_registry = sorted(set(registry) - audited)
    if missing_registry or extra_registry:
        raise ValueError(f"registry coverage mismatch: missing={missing_registry}, extra={extra_registry}")

    groups = sorted({entry["source_group"] for entry in registry.values()})
    exact_union = UnionFind.create(groups)
    family_union = UnionFind.create(groups)
    antigen_union = UnionFind.create(groups)
    exact_first: dict[bytes, str] = {}
    family_first: dict[bytes, str] = {}
    antigen_first: dict[bytes, str] = {}
    duplicate_keys: set[bytes] = set()
    family_keys: set[bytes] = set()
    valid_antigen_keys: set[bytes] = set()
    stats: list[dict[str, object]] = []
    total = Counter()
    fasta_seen: set[bytes] = set()
    fasta_records: list[tuple[str, str]] = []

    for source, entry in sorted(registry.items()):
        file_stats = Counter()
        path = data_root / Path(source)
        if not path.exists():
            file_stats["missing_file"] += 1
            stats.append({"source_file": source, **file_stats})
            continue
        header, rows = _header_and_rows(path)
        keys = {name: _find_key(header, aliases) for name, aliases in ALIASES.items()}
        index = {name: header.index(key) if key in header else None for name, key in keys.items()}
        group = entry["source_group"]
        sampled = 0
        for values in rows:
            file_stats["raw_rows"] += 1
            if entry["supervised_use"] != "yes" or index["label"] is None:
                file_stats["auxiliary_rows"] += 1
                continue
            label = parse_number(values[index["label"]])
            if label is None or not math.isfinite(label):
                file_stats["missing_or_invalid_label_rows"] += 1
                continue
            if not label_is_valid(label, entry):
                file_stats["out_of_range_label_rows"] += 1
                continue
            heavy, heavy_state = sequence_state(values[index["heavy"]] if index["heavy"] is not None else "")
            if heavy_state != "valid":
                file_stats["quarantined_heavy_rows"] += 1
                continue
            light, light_state = sequence_state(values[index["light"]] if index["light"] is not None else "")
            antigen, antigen_state = sequence_state(values[index["antigen_seq"]] if index["antigen_seq"] is not None else "")
            cdrh3, cdrh3_state = sequence_state(values[index["cdrh3"]] if index["cdrh3"] is not None else "")
            if light_state == "invalid":
                file_stats["ambiguous_light_rows"] += 1
                light = ""
            if cdrh3_state != "valid":
                cdrh3 = ""
            file_stats["curated_supervised_rows"] += 1

            exact = digest(heavy, light)
            if exact in exact_first:
                first_group = exact_first[exact]
                duplicate_keys.add(exact)
                file_stats["repeated_exact_duplicate_rows"] += 1
                if first_group != group:
                    exact_union.union(first_group, group)
                    # The broader family-safe split must preserve every exact
                    # identity constraint even if one file lacks CDRH3.
                    family_union.union(first_group, group)
                    file_stats["cross_group_exact_duplicate_rows"] += 1
            else:
                exact_first[exact] = group

            family = antibody_family_key(heavy, light, cdrh3)
            family_keys.add(family)
            family_group = family_first.setdefault(family, group)
            if family_group != group:
                family_union.union(family_group, group)

            if antigen_state == "valid":
                ag_key = digest(antigen)
                valid_antigen_keys.add(ag_key)
                ag_group = antigen_first.setdefault(ag_key, group)
                if ag_group != group:
                    antigen_union.union(ag_group, group)

            if sampled < imgt_samples_per_file:
                for chain, sequence in (("H", heavy), ("L", light)):
                    if not sequence:
                        continue
                    seq_key = digest(chain, sequence)
                    if seq_key in fasta_seen:
                        continue
                    fasta_seen.add(seq_key)
                    ident = f"{chain}|{seq_key.hex()}|{group.replace('/', '_')}"
                    fasta_records.append((ident, sequence))
                    sampled += 1
                    if sampled >= imgt_samples_per_file:
                        break
        stats.append({"source_file": source, "source_group": group, "tier": entry["tier"], **file_stats})
        total.update(file_stats)

    output_dir.mkdir(parents=True, exist_ok=True)
    stat_fields = [
        "source_file", "source_group", "tier", "raw_rows", "curated_supervised_rows",
        "auxiliary_rows", "missing_or_invalid_label_rows", "out_of_range_label_rows",
        "quarantined_heavy_rows",
        "ambiguous_light_rows", "cross_group_exact_duplicate_rows", "repeated_exact_duplicate_rows",
        "missing_file",
    ]
    with (output_dir / "curation_stats.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=stat_fields)
        writer.writeheader()
        for row in stats:
            writer.writerow({field: row.get(field, 0) for field in stat_fields})

    with (output_dir / "imgt_numbering_input.fasta").open("w", encoding="utf-8", newline="\n") as handle:
        for ident, sequence in fasta_records:
            handle.write(f">{ident}\n{sequence}\n")

    paper_mapping = assign_groups(groups, 0.70, 0.15)
    exact_roots, exact_mapping = component_assignments(groups, exact_union)
    family_roots, family_mapping = component_assignments(groups, family_union)
    antigen_roots, antigen_mapping = component_assignments(groups, antigen_union)
    split_fields = [
        "source_group", "publication_year", "paper_split", "exact_antibody_component",
        "exact_antibody_safe_split", "heuristic_family_component", "heuristic_family_safe_split",
        "exact_antigen_component", "exact_antigen_safe_split", "time_split",
    ]
    group_entry = {entry["source_group"]: entry for entry in registry.values()}
    with (output_dir / "split_group_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=split_fields)
        writer.writeheader()
        for group in groups:
            year = int(group_entry[group]["publication_year"])
            writer.writerow({
                "source_group": group,
                "publication_year": year,
                "paper_split": paper_mapping[group],
                "exact_antibody_component": exact_roots[group],
                "exact_antibody_safe_split": exact_mapping[group],
                "heuristic_family_component": family_roots[group],
                "heuristic_family_safe_split": family_mapping[group],
                "exact_antigen_component": antigen_roots[group],
                "exact_antigen_safe_split": antigen_mapping[group],
                "time_split": time_split(year),
            })

    summary = {
        "registry_files": len(registry),
        "registry_coverage_complete": not missing_registry and not extra_registry,
        "totals": dict(total),
        "unique_exact_antibodies": len(exact_first),
        "exact_antibody_keys_seen_more_than_once": len(duplicate_keys),
        "heuristic_antibody_family_buckets": len(family_keys),
        "unique_valid_antigen_sequences": len(valid_antigen_keys),
        "imgt_numbering_input_sequences": len(fasta_records),
        "imgt_numbering_status": "input_ready; install ANARCII and run IMGT scheme on cloud/CPU",
        "outputs": {
            "file_stats": str(output_dir / "curation_stats.csv"),
            "split_manifest": str(output_dir / "split_group_manifest.csv"),
            "imgt_input": str(output_dir / "imgt_numbering_input.fasta"),
        },
        "limitations": [
            "heuristic_family buckets are deterministic screening groups, not MMseqs2 identity clusters",
            "antigen-safe grouping uses exact valid antigen sequences because most rows lack antigen sequence",
            "IMGT numbering requires the optional ANARCII dependency and is not fabricated heuristically",
        ],
    }
    (output_dir / "curation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate labels and build curation/split artifacts.")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=Path("configs/label_registry.csv"))
    parser.add_argument("--audit", type=Path, default=Path("data/processed/audit.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/curation"))
    parser.add_argument("--imgt-samples-per-file", type=int, default=50)
    args = parser.parse_args()
    result = curate_audit(args.data_root, args.registry, args.audit, args.output_dir, args.imgt_samples_per_file)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
