"""Audit model reliability by train-only ESM parent-cluster OOD percentile."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr


DATA = Path("data/processed/benchmark_team_routed_v6_global_family.csv")
BASE = Path("artifacts/stage17/global_family_v2_final_parent_ensemble.csv")
PARENT = Path("artifacts/stage18/global_family_v2_esm_parent_conditioned_posconv/predictions.csv")
CLUSTERS = Path("artifacts/stage20/train_only_esm_parent_clusters_with_ood.joblib")
OUTPUT = Path("artifacts/stage20/ood_reliability_audit.json")


def rho(truth: pd.Series, prediction: pd.Series | np.ndarray) -> float:
    return float(spearmanr(truth, prediction).statistic)


def rank(values: pd.Series) -> np.ndarray:
    return rankdata(values.to_numpy(), method="average") / len(values)


def metrics(group: pd.DataFrame) -> dict[str, float | int]:
    return {
        "n": len(group),
        "unique_pairs": int(group["pair_key"].nunique()),
        "base_spearman": rho(group["truth"], group["base_prediction"]),
        "parent_spearman": rho(group["truth"], group["parent_prediction"]),
        "base_mae": float(np.mean(np.abs(group["truth"] - group["base_prediction"]))),
        "parent_mae": float(np.mean(np.abs(group["truth"] - group["parent_prediction"]))),
    }


def main() -> None:
    base = pd.read_csv(BASE).rename(columns={"prediction": "base_prediction"})
    parent = pd.read_csv(PARENT).rename(columns={"prediction": "parent_prediction"})
    frame = base.merge(parent[["record_id", "parent_prediction"]], on="record_id", validate="one_to_one")
    metadata = pd.read_csv(DATA, usecols=["record_id", "heavy", "light"])
    metadata["pair_key"] = metadata["heavy"].fillna("") + "\x1f" + metadata["light"].fillna("")
    frame = frame.merge(metadata[["record_id", "pair_key"]], on="record_id", validate="one_to_one")
    payload = joblib.load(CLUSTERS)
    frame["ood_percentile"] = frame["pair_key"].map(payload["ood_percentiles"])
    if frame["ood_percentile"].isna().any():
        raise ValueError("missing OOD percentile assignments")
    frame["ood_bin"] = pd.cut(
        frame["ood_percentile"], bins=[-np.inf, 0.5, 0.9, np.inf],
        labels=["in_distribution_p00_p50", "intermediate_p50_p90", "ood_p90_p100"],
    )
    frame["base_rank"] = rank(frame["base_prediction"])
    frame["parent_rank"] = rank(frame["parent_prediction"])

    schedules = {
        "fixed_0.225": np.full(len(frame), 0.225),
        "downweight_parent_when_ood": np.where(frame["ood_percentile"] >= 0.9, 0.075, 0.225),
        "upweight_parent_when_ood": np.where(frame["ood_percentile"] >= 0.9, 0.30, 0.225),
    }
    schedule_metrics = {}
    for name, weights in schedules.items():
        prediction = (1.0 - weights) * frame["base_rank"] + weights * frame["parent_rank"]
        schedule_metrics[name] = {"spearman": rho(frame["truth"], prediction)}

    report = {
        "note": "Final-validation diagnostic only; schedules are not eligible for promotion without inner-train confirmation.",
        "records": len(frame),
        "by_ood_bin": {str(name): metrics(group) for name, group in frame.groupby("ood_bin", observed=True)},
        "schedule_diagnostic": schedule_metrics,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
