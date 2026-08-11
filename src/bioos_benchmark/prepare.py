from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from .data import (
    iter_csv_records,
    grouped_percentile_scores,
    reservoir_sample,
    source_group,
    stable_record_id,
)
from .curation import label_is_valid, load_registry


FIELDS = [
    "record_id", "source_group", "source_file", "antigen_id", "antigen_seq", "heavy", "light",
    "cdrh3", "raw_label", "direction", "score", "tier", "label_origin", "metric",
    "comparison_group", "label_quality",
]

TIER_QUALITY = {"Gold": 1.0, "Silver": 0.65, "Weak": 0.25, "Auxiliary": 0.0}


def load_overrides(path: Path | None) -> dict[str, int]:
    if path is None:
        return {}
    overrides: dict[str, int] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            source = str(row.get("source_file", "")).strip().replace("\\", "/")
            direction = int(str(row.get("direction", "0")).strip() or 0)
            if source and direction in {-1, 1}:
                overrides[source] = direction
    return overrides


def prepare(
    data_root: Path,
    output: Path,
    max_rows_per_file: int | None,
    seed: int,
    overrides_path: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, object]:
    # Recursive discovery avoids depending on a locale-sensitive directory
    # name; files without supported antibody/label fields are skipped below.
    csv_files = sorted(data_root.rglob("*.csv"))
    output.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    skipped: list[str] = []
    record_count = 0
    duplicate_count = 0
    seen_record_ids: set[str] = set()
    overrides = load_overrides(overrides_path)
    registry = load_registry(registry_path) if registry_path else {}
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for file_index, path in enumerate(csv_files):
            source = path.relative_to(data_root).as_posix()
            entry = registry.get(source)
            if registry and (entry is None or entry["supervised_use"] != "yes"):
                skipped.append(source)
                continue
            direction = overrides.get(source)
            if direction not in {-1, 1} and entry is not None:
                direction = int(entry["direction"])
            record_stream = iter_csv_records(path, data_root, direction)
            if entry is not None:
                record_stream = (
                    record for record in record_stream if label_is_valid(record.raw_label, entry)
                )
            records = reservoir_sample(
                record_stream,
                max_rows_per_file,
                seed + file_index,
            )
            if not records:
                skipped.append(path.relative_to(data_root).as_posix())
                continue
            scores = grouped_percentile_scores(records)
            for record, score in zip(records, scores):
                record_id = stable_record_id(record)
                if record_id in seen_record_ids:
                    duplicate_count += 1
                    continue
                seen_record_ids.add(record_id)
                record_count += 1
                writer.writerow(
                    {
                        "record_id": record_id,
                        "source_group": source_group(record.source_file),
                        "source_file": record.source_file,
                        "antigen_id": record.antigen_id,
                        "antigen_seq": record.antigen_seq,
                        "heavy": record.heavy,
                        "light": record.light,
                        "cdrh3": record.cdrh3,
                        "raw_label": f"{record.raw_label:.12g}",
                        "direction": record.direction,
                        "score": f"{score:.12g}",
                        "tier": entry.get("tier", "") if entry else "",
                        "label_origin": entry.get("label_origin", "") if entry else "",
                        "metric": entry.get("metric", "") if entry else "",
                        "comparison_group": record.comparison_group or record.source_file,
                        "label_quality": f"{TIER_QUALITY.get(entry.get('tier', ''), 1.0):.12g}" if entry else "1",
                    }
                )
                counts[record.source_file] += 1
    summary = {
        "data_root": str(data_root),
        "output": str(output),
        "records": record_count,
        "duplicate_records_removed": duplicate_count,
        "included_files": len(counts),
        "skipped_files": skipped,
        "max_rows_per_file": max_rows_per_file,
        "seed": seed,
        "direction_overrides": str(overrides_path) if overrides_path else None,
        "override_count": len(overrides),
        "label_registry": str(registry_path) if registry_path else None,
        "registry_count": len(registry),
        "counts_by_source": dict(counts),
        "label_definition": "source-wise percentile; 1 is better",
    }
    summary_path = output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unify Bio-OS sequence datasets.")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/processed/benchmark.csv"))
    parser.add_argument("--max-rows-per-file", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--direction-overrides", type=Path)
    parser.add_argument("--label-registry", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = prepare(
        args.data_root,
        args.output,
        args.max_rows_per_file,
        args.seed,
        args.direction_overrides,
        args.label_registry,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
