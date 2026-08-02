from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from ..metrics import regression_metrics
from .preferences import oriented_label


def _clean(value: object) -> str:
    return str(value or "").strip()


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _read_unique_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "record_id" not in rows[0]:
        raise ValueError(f"{path} must be a non-empty CSV with record_id.")
    ids = [_clean(row.get("record_id")) for row in rows]
    if any(not record_id for record_id in ids):
        raise ValueError(f"{path} contains an empty record_id.")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path} contains duplicate record_id values.")
    return rows


def _prediction_score(row: Mapping[str, object]) -> float:
    text = _clean(row.get("score", row.get("prediction")))
    try:
        score = float(text)
    except ValueError as error:
        raise ValueError(f"Invalid score for record {_clean(row.get('record_id'))}") from error
    if not math.isfinite(score):
        raise ValueError(f"Non-finite score for record {_clean(row.get('record_id'))}")
    return score


def _aligned_rows(
    truth_rows: Sequence[dict[str, str]],
    prediction_rows: Sequence[dict[str, str]],
) -> list[tuple[dict[str, str], dict[str, str]]]:
    prediction_lookup = {_clean(row["record_id"]): row for row in prediction_rows}
    truth_ids = {_clean(row["record_id"]) for row in truth_rows}
    prediction_ids = set(prediction_lookup)
    missing = sorted(truth_ids - prediction_ids)
    extra = sorted(prediction_ids - truth_ids)
    if missing or extra:
        raise ValueError(f"record_id mismatch: missing={missing[:5]}, extra={extra[:5]}")
    return [
        (row, prediction_lookup[_clean(row["record_id"])])
        for row in sorted(truth_rows, key=lambda item: _clean(item["record_id"]))
    ]


def _group_metrics(
    truth: np.ndarray,
    prediction: np.ndarray,
    groups: Sequence[str],
) -> tuple[dict[str, dict[str, float]], float | None, float | None]:
    positions: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        positions[group or "<missing>"].append(index)
    by_group: dict[str, dict[str, float]] = {}
    correlations: list[float] = []
    weighted_values: list[tuple[float, int]] = []
    for group, indices in sorted(positions.items()):
        idx = np.asarray(indices, dtype=np.int64)
        metrics = regression_metrics(truth[idx], prediction[idx])
        by_group[group] = metrics
        correlation = metrics["spearman"]
        if math.isfinite(correlation):
            correlations.append(correlation)
            weighted_values.append((correlation, len(indices)))
    macro = float(np.mean(correlations)) if correlations else None
    denominator = sum(size for _, size in weighted_values)
    weighted = (
        sum(value * size for value, size in weighted_values) / denominator
        if denominator
        else None
    )
    return by_group, macro, weighted


def _cluster_bootstrap_spearman(
    truth: np.ndarray,
    prediction: np.ndarray,
    clusters: Sequence[str],
    rounds: int,
    seed: int,
) -> dict[str, object]:
    if rounds <= 0:
        return {"rounds_requested": rounds, "rounds_valid": 0, "low": None, "high": None}
    cluster_positions: dict[str, list[int]] = defaultdict(list)
    for index, cluster in enumerate(clusters):
        cluster_positions[cluster or f"row_{index}"].append(index)
    names = sorted(cluster_positions)
    if len(names) < 2:
        return {"rounds_requested": rounds, "rounds_valid": 0, "low": None, "high": None}
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(rounds):
        sampled = rng.choice(names, size=len(names), replace=True)
        indices = [
            position
            for cluster in sampled
            for position in cluster_positions[str(cluster)]
        ]
        correlation = regression_metrics(truth[indices], prediction[indices])["spearman"]
        if math.isfinite(correlation):
            values.append(correlation)
    if not values:
        return {"rounds_requested": rounds, "rounds_valid": 0, "low": None, "high": None}
    return {
        "rounds_requested": rounds,
        "rounds_valid": len(values),
        "low": float(np.quantile(values, 0.025)),
        "median": float(np.quantile(values, 0.5)),
        "high": float(np.quantile(values, 0.975)),
    }


def _cluster_bootstrap_top10(
    truth: np.ndarray,
    prediction: np.ndarray,
    clusters: Sequence[str],
    rounds: int,
    seed: int,
) -> dict[str, object]:
    """Cluster bootstrap interval for the Top-10% enrichment statistic."""
    if rounds <= 0:
        return {"rounds_requested": rounds, "rounds_valid": 0, "low": None, "high": None}
    cluster_positions: dict[str, list[int]] = defaultdict(list)
    for index, cluster in enumerate(clusters):
        cluster_positions[cluster or f"row_{index}"].append(index)
    names = sorted(cluster_positions)
    if len(names) < 2:
        return {"rounds_requested": rounds, "rounds_valid": 0, "low": None, "high": None}
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(rounds):
        sampled = rng.choice(names, size=len(names), replace=True)
        indices = [
            position
            for cluster in sampled
            for position in cluster_positions[str(cluster)]
        ]
        value = regression_metrics(truth[indices], prediction[indices])["top10_enrichment"]
        if math.isfinite(value):
            values.append(value)
    if not values:
        return {"rounds_requested": rounds, "rounds_valid": 0, "low": None, "high": None}
    return {
        "rounds_requested": rounds,
        "rounds_valid": len(values),
        "low": float(np.quantile(values, 0.025)),
        "median": float(np.quantile(values, 0.5)),
        "high": float(np.quantile(values, 0.975)),
    }


def _regime_metrics(
    truth: np.ndarray,
    prediction: np.ndarray,
    regimes: Sequence[str],
) -> dict[str, dict[str, float]]:
    positions: dict[str, list[int]] = defaultdict(list)
    for index, regime in enumerate(regimes):
        if regime:
            positions[regime].append(index)
    return {
        regime: regression_metrics(
            truth[np.asarray(indices, dtype=np.int64)],
            prediction[np.asarray(indices, dtype=np.int64)],
        )
        for regime, indices in sorted(positions.items())
    }


def evaluate_predictions(
    truth_path: str | Path,
    prediction_path: str | Path,
    *,
    bootstrap_rounds: int = 1000,
    seed: int = 42,
    split: str | None = None,
) -> dict[str, object]:
    """Evaluate predictions after strict one-to-one record_id alignment."""
    truth_path = Path(truth_path)
    prediction_path = Path(prediction_path)
    truth_rows = _read_unique_csv(truth_path)
    prediction_rows = _read_unique_csv(prediction_path)
    if split:
        truth_rows = [row for row in truth_rows if _clean(row.get("split")) == split]
        prediction_rows = [
            row for row in prediction_rows if not _clean(row.get("split"))
            or _clean(row.get("split")) == split
        ]
        if not truth_rows:
            raise ValueError(f"No truth rows found for split: {split}")
    aligned = _aligned_rows(truth_rows, prediction_rows)

    usable: list[tuple[dict[str, str], float, float]] = []
    for truth_row, prediction_row in aligned:
        label = oriented_label(truth_row)
        score = _prediction_score(prediction_row)
        if label is not None:
            usable.append((truth_row, label, score))
    if len(usable) < 2:
        raise ValueError("At least two labeled aligned records are required.")

    rows = [item[0] for item in usable]
    truth = np.asarray([item[1] for item in usable], dtype=np.float64)
    prediction = np.asarray([item[2] for item in usable], dtype=np.float64)
    source_groups = [_clean(row.get("source_group", row.get("source_file"))) for row in rows]
    target_groups = [_clean(row.get("target_id", row.get("antigen_id"))) for row in rows]
    split_groups = [
        _clean(row.get("split_group")) or source_groups[index] or _clean(row.get("record_id"))
        for index, row in enumerate(rows)
    ]
    by_source, macro_source, weighted_source = _group_metrics(
        truth, prediction, source_groups
    )
    by_target, macro_target, weighted_target = _group_metrics(
        truth, prediction, target_groups
    )
    by_split = _regime_metrics(
        truth, prediction, [_clean(row.get("split")) for row in rows]
    )
    by_evaluation_regime = _regime_metrics(
        truth,
        prediction,
        [_clean(row.get("evaluation_regime")) for row in rows],
    )
    antibody_types = [
        _clean(row.get("antibody_type"))
        or ("VHH" if not _clean(row.get("light")) else "Fv")
        for row in rows
    ]
    censoring = [
        "censored"
        if _clean(row.get("is_censored")).casefold() in {"1", "true", "yes", "y"}
        else "uncensored"
        for row in rows
    ]

    rng = np.random.default_rng(seed)
    shuffled_truth = truth[rng.permutation(len(truth))]
    permutation_spearman = regression_metrics(shuffled_truth, prediction)["spearman"]
    source_held_out = by_evaluation_regime.get("source-held-out")
    antigen_cold = by_evaluation_regime.get("antigen-cold")
    composite = None
    if (
        macro_source is not None
        and source_held_out is not None
        and antigen_cold is not None
        and math.isfinite(source_held_out["spearman"])
        and math.isfinite(antigen_cold["spearman"])
    ):
        composite = (
            0.50 * macro_source
            + 0.25 * source_held_out["spearman"]
            + 0.25 * antigen_cold["spearman"]
        )

    report: dict[str, object] = {
        "truth": str(truth_path),
        "predictions": str(prediction_path),
        "records_total": len(truth_rows),
        "records_labeled": len(usable),
        "split_filter": split,
        "global": regression_metrics(truth, prediction),
        "macro_source_spearman": macro_source,
        "size_weighted_source_spearman": weighted_source,
        "macro_target_spearman": macro_target,
        "size_weighted_target_spearman": weighted_target,
        "by_source": by_source,
        "by_target": by_target,
        "by_split": by_split,
        "by_evaluation_regime": by_evaluation_regime,
        "by_antibody_type": _regime_metrics(truth, prediction, antibody_types),
        "by_censoring": _regime_metrics(truth, prediction, censoring),
        "bootstrap_spearman_95ci": _cluster_bootstrap_spearman(
            truth, prediction, split_groups, bootstrap_rounds, seed
        ),
        "bootstrap_top10_enrichment_95ci": _cluster_bootstrap_top10(
            truth, prediction, split_groups, bootstrap_rounds, seed + 1
        ),
        "label_permutation_spearman": permutation_spearman,
        "model_selection_composite": composite,
        "seed": seed,
    }
    return _json_safe(report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strictly evaluate affinity ranking predictions.")
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-rounds", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = evaluate_predictions(
        args.truth,
        args.predictions,
        bootstrap_rounds=args.bootstrap_rounds,
        seed=args.seed,
        split=args.split,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
