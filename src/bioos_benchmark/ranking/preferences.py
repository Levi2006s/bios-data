from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


PAIR_FIELDS = [
    "left_record_id",
    "right_record_id",
    "preference",
    "pair_weight",
    "comparison_group",
    "reason",
]


@dataclass(frozen=True)
class PreferencePair:
    """A quality-weighted statement about the relative order of two records."""

    left_record_id: str
    right_record_id: str
    preference: int
    pair_weight: float
    comparison_group: str
    reason: str


@dataclass(frozen=True)
class _ComparableRecord:
    record_id: str
    label: float
    quality: float
    is_censored: bool
    conflict: float
    split: str
    comparison_group: str


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _finite_float(value: object, default: float | None = None) -> float | None:
    text = _clean_text(value)
    if not text:
        return default
    try:
        number = float(text)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _bounded_float(value: object, default: float) -> float:
    number = _finite_float(value, default)
    assert number is not None
    return min(1.0, max(0.0, number))


def _as_bool(value: object) -> bool:
    return _clean_text(value).casefold() in {"1", "true", "yes", "y", "censored"}


def oriented_label(row: Mapping[str, object]) -> float | None:
    """Return a label where larger values always mean better affinity."""
    for key in ("canonical_label", "within_group_rank", "score"):
        number = _finite_float(row.get(key))
        if number is not None:
            return number
    raw = _finite_float(row.get("raw_label"))
    if raw is None:
        return None
    direction = _finite_float(row.get("direction"), 1.0)
    return raw * (direction if direction in {-1.0, 1.0} else 1.0)


def infer_comparison_group(
    row: Mapping[str, object],
    group_fields: Sequence[str] | None = None,
) -> str:
    """Build a conservative group in which labels are safe to compare."""
    explicit = _clean_text(row.get("comparison_group"))
    if explicit:
        return explicit
    if group_fields:
        fields = tuple(group_fields)
    else:
        fields = (
            "paper_group",
            "source_file",
            "target_id",
            "antigen_id",
            "assay_family",
            "assay_format",
        )
    parts = []
    for field in fields:
        value = _clean_text(row.get(field))
        if value:
            parts.append(f"{field}={value}")
    if not parts:
        source_group = _clean_text(row.get("source_group"))
        if source_group:
            parts.append(f"source_group={source_group}")
    return "\x1f".join(parts)


def _to_comparable(
    row: Mapping[str, object],
    group_fields: Sequence[str] | None,
) -> _ComparableRecord | None:
    record_id = _clean_text(row.get("record_id"))
    label = oriented_label(row)
    comparison_group = infer_comparison_group(row, group_fields)
    if not record_id or label is None or not comparison_group:
        return None
    quality = _bounded_float(row.get("label_quality"), 1.0)
    conflict = _bounded_float(
        row.get("replicate_conflict", row.get("label_conflict")),
        0.0,
    )
    return _ComparableRecord(
        record_id=record_id,
        label=label,
        quality=quality,
        is_censored=_as_bool(row.get("is_censored")),
        conflict=conflict,
        split=_clean_text(row.get("split")),
        comparison_group=comparison_group,
    )


def _candidate_indices(
    count: int,
    limit: int,
    seed: int,
    group: str,
) -> list[tuple[int, int]]:
    total = count * (count - 1) // 2
    if total <= limit:
        return [(left, right) for left in range(count) for right in range(left + 1, count)]
    digest = hashlib.sha256(f"{seed}\x1f{group}".encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    indices: set[tuple[int, int]] = set()
    attempts = 0
    max_attempts = max(limit * 30, 1000)
    while len(indices) < limit and attempts < max_attempts:
        left = rng.randrange(count)
        right = rng.randrange(count - 1)
        if right >= left:
            right += 1
        if left > right:
            left, right = right, left
        indices.add((left, right))
        attempts += 1
    return sorted(indices)


def _pair_weight(
    better: _ComparableRecord,
    worse: _ComparableRecord,
    gap: float,
    gap_scale: float,
) -> tuple[float, str]:
    gap_weight = min(1.0, gap / gap_scale) if gap_scale > 0 else 1.0
    censor_weight = 0.5 if better.is_censored or worse.is_censored else 1.0
    conflict_weight = 1.0 - max(better.conflict, worse.conflict)
    weight = better.quality * worse.quality * gap_weight * censor_weight * conflict_weight
    reasons = ["ordered_label"]
    if censor_weight < 1:
        reasons.append("censored_downweighted")
    if conflict_weight < 1:
        reasons.append("conflict_downweighted")
    return min(1.0, max(0.0, weight)), "+".join(reasons)


def build_preference_pairs(
    records: Sequence[Mapping[str, object]],
    *,
    min_gap: float = 0.0,
    max_pairs_per_group: int = 100_000,
    max_pairs_total: int = 1_000_000,
    seed: int = 42,
    group_fields: Sequence[str] | None = None,
) -> list[PreferencePair]:
    """Construct reproducible pairs only within compatible comparison groups."""
    if min_gap < 0:
        raise ValueError("min_gap must be non-negative.")
    if max_pairs_per_group <= 0:
        raise ValueError("max_pairs_per_group must be positive.")
    if max_pairs_total <= 0:
        raise ValueError("max_pairs_total must be positive.")
    grouped: dict[str, list[_ComparableRecord]] = defaultdict(list)
    seen_ids: set[str] = set()
    for row in records:
        record = _to_comparable(row, group_fields)
        if record is None:
            continue
        if record.record_id in seen_ids:
            raise ValueError(f"Duplicate record_id: {record.record_id}")
        seen_ids.add(record.record_id)
        grouped[record.comparison_group].append(record)

    pairs: list[PreferencePair] = []
    group_limit = max(
        1,
        min(max_pairs_per_group, max_pairs_total // max(1, len(grouped))),
    )
    for group in sorted(grouped):
        members = sorted(grouped[group], key=lambda item: (item.label, item.record_id))
        if len(members) < 2:
            continue
        labels = [member.label for member in members]
        label_range = max(labels) - min(labels)
        gap_scale = label_range if label_range > 0 else 1.0
        group_pairs: list[PreferencePair] = []
        for left_index, right_index in _candidate_indices(
            len(members), group_limit * 3, seed, group
        ):
            left = members[left_index]
            right = members[right_index]
            if left.split and right.split and left.split != right.split:
                continue
            gap = right.label - left.label
            if gap <= min_gap:
                continue
            if left.is_censored and right.is_censored:
                continue
            weight, reason = _pair_weight(right, left, gap, gap_scale)
            if weight <= 0:
                continue
            group_pairs.append(
                PreferencePair(
                    left_record_id=right.record_id,
                    right_record_id=left.record_id,
                    preference=1,
                    pair_weight=weight,
                    comparison_group=group,
                    reason=reason,
                )
            )
        if len(group_pairs) > group_limit:
            group_pairs.sort(
                key=lambda pair: hashlib.sha256(
                    f"{seed}\x1f{pair.left_record_id}\x1f{pair.right_record_id}".encode("utf-8")
                ).digest()
            )
            group_pairs = group_pairs[:group_limit]
        pairs.extend(group_pairs)
    return pairs


def validate_preference_pairs(
    pairs: Sequence[PreferencePair],
    records: Sequence[Mapping[str, object]],
    *,
    group_fields: Sequence[str] | None = None,
) -> dict[str, object]:
    """Validate pair integrity and return an auditable summary."""
    lookup: dict[str, _ComparableRecord] = {}
    duplicate_record_ids: list[str] = []
    for row in records:
        record = _to_comparable(row, group_fields)
        if record is None:
            continue
        if record.record_id in lookup:
            duplicate_record_ids.append(record.record_id)
        lookup[record.record_id] = record

    errors: list[str] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    reason_counts: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    weights: list[float] = []
    for pair in pairs:
        key = (pair.left_record_id, pair.right_record_id, pair.comparison_group)
        if key in seen_pairs:
            errors.append(f"duplicate pair: {key}")
        seen_pairs.add(key)
        left = lookup.get(pair.left_record_id)
        right = lookup.get(pair.right_record_id)
        if left is None or right is None:
            errors.append(f"unknown record in pair: {key}")
            continue
        if pair.preference not in {-1, 1}:
            errors.append(f"invalid preference: {key}")
        if not 0 < pair.pair_weight <= 1:
            errors.append(f"invalid weight: {key}")
        if left.comparison_group != right.comparison_group:
            errors.append(f"cross-group pair: {key}")
        if pair.comparison_group != left.comparison_group:
            errors.append(f"incorrect comparison_group: {key}")
        if left.split and right.split and left.split != right.split:
            errors.append(f"cross-split pair: {key}")
        oriented_gap = (left.label - right.label) * pair.preference
        if oriented_gap <= 0:
            errors.append(f"wrong or tied direction: {key}")
        if left.is_censored and right.is_censored:
            errors.append(f"double-censored pair: {key}")
        weights.append(pair.pair_weight)
        reason_counts[pair.reason] += 1
        group_counts[pair.comparison_group] += 1

    if duplicate_record_ids:
        errors.append(f"duplicate record_ids: {sorted(set(duplicate_record_ids))[:10]}")
    return {
        "valid": not errors,
        "pairs": len(pairs),
        "comparison_groups": len(group_counts),
        "weight_min": min(weights) if weights else None,
        "weight_mean": sum(weights) / len(weights) if weights else None,
        "weight_max": max(weights) if weights else None,
        "counts_by_group": dict(group_counts),
        "counts_by_reason": dict(reason_counts),
        "errors": errors[:100],
    }


def read_csv_rows(
    path: Path, split: str | None = None, include_tiers: set[str] | None = None,
) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if split is not None:
        rows = [row for row in rows if _clean_text(row.get("split")) == split]
    if include_tiers:
        rows = [row for row in rows if _clean_text(row.get("tier")) in include_tiers]
    return rows


def write_pairs(path: Path, pairs: Iterable[PreferencePair]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAIR_FIELDS)
        writer.writeheader()
        for pair in pairs:
            row = asdict(pair)
            row["pair_weight"] = f"{pair.pair_weight:.12g}"
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build quality-weighted preference pairs for affinity ranking."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--min-gap", type=float, default=0.0)
    parser.add_argument("--max-pairs-per-group", type=int, default=100_000)
    parser.add_argument("--max-pairs-total", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--group-fields", nargs="*")
    parser.add_argument("--include-tiers", nargs="*")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = read_csv_rows(
        args.input, args.split or None,
        set(args.include_tiers) if args.include_tiers else None,
    )
    pairs = build_preference_pairs(
        rows,
        min_gap=args.min_gap,
        max_pairs_per_group=args.max_pairs_per_group,
        max_pairs_total=args.max_pairs_total,
        seed=args.seed,
        group_fields=args.group_fields,
    )
    report = validate_preference_pairs(pairs, rows, group_fields=args.group_fields)
    if not report["valid"]:
        raise ValueError(f"Preference validation failed: {report['errors'][:5]}")
    write_pairs(args.output, pairs)
    report.update(
        {
            "input": str(args.input),
            "output": str(args.output),
            "split": args.split,
            "min_gap": args.min_gap,
            "max_pairs_per_group": args.max_pairs_per_group,
            "max_pairs_total": args.max_pairs_total,
            "seed": args.seed,
            "include_tiers": sorted(args.include_tiers) if args.include_tiers else None,
        }
    )
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
