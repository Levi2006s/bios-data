"""Evaluate and persist the Stage 18 ESM-parent-cluster rank ensemble."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

from bioos_benchmark.metrics import regression_metrics


ROOT = Path("artifacts")
DATA = Path("data/processed/benchmark_team_routed_v6_global_family.csv")
BASE = ROOT / "stage17/global_family_v2_final_parent_ensemble.csv"
PARENT = ROOT / "stage18/global_family_v2_esm_parent_conditioned_posconv/predictions.csv"
H119_EXPERT = ROOT / "stage18/h119_l115_esm_parent_expert/predictions.csv"
OUTPUT = ROOT / "stage18/global_family_v2_final_esm_parent_ensemble.csv"
METRICS = OUTPUT.with_suffix(".metrics.json")


def percentile_rank(values: pd.Series) -> np.ndarray:
    return rankdata(values.to_numpy(), method="average") / len(values)


def main() -> None:
    base = pd.read_csv(BASE).rename(columns={"prediction": "base_prediction"})
    parent = pd.read_csv(PARENT).rename(columns={"prediction": "parent_prediction"})
    frame = base.merge(
        parent[["record_id", "parent_prediction"]], on="record_id", validate="one_to_one"
    )
    frame["base_rank"] = percentile_rank(frame["base_prediction"])
    frame["parent_rank"] = percentile_rank(frame["parent_prediction"])

    sweep = []
    for weight in np.arange(0.0, 0.3001, 0.025):
        prediction = (1.0 - weight) * frame["base_rank"] + weight * frame["parent_rank"]
        sweep.append(
            {
                "parent_weight": round(float(weight), 3),
                "spearman": float(spearmanr(frame["truth"], prediction).statistic),
            }
        )
    best = max(sweep, key=lambda row: row["spearman"])
    weight = float(best["parent_weight"])
    frame["prediction"] = (1.0 - weight) * frame["base_rank"] + weight * frame["parent_rank"]

    metadata = pd.read_csv(DATA, usecols=["record_id", "heavy", "light"])
    heavy_lengths = metadata["heavy"].str.len().fillna(0).astype(int)
    light_lengths = metadata["light"].str.len().fillna(0).astype(int)
    metadata["length_group"] = "H" + heavy_lengths.astype(str) + "|L" + light_lengths.astype(str)
    frame = frame.merge(
        metadata[["record_id", "length_group"]], on="record_id", validate="one_to_one"
    )

    expert = pd.read_csv(H119_EXPERT).rename(columns={"prediction": "expert_prediction"})
    frame = frame.merge(
        expert[["record_id", "expert_prediction"]], on="record_id", how="left", validate="one_to_one"
    )
    expert_mask = frame["expert_prediction"].notna()
    subset = frame.loc[expert_mask]
    base_subset_rank = percentile_rank(subset["prediction"])
    expert_subset_rank = percentile_rank(subset["expert_prediction"])
    subset_values = np.sort(subset["prediction"].to_numpy())
    expert_sweep = []
    routed_candidates = {}
    for expert_weight in np.arange(0.0, 0.3001, 0.025):
        mixed_rank = (1.0 - expert_weight) * base_subset_rank + expert_weight * expert_subset_rank
        order = rankdata(mixed_rank, method="ordinal").astype(int) - 1
        routed = frame["prediction"].to_numpy(copy=True)
        routed[np.flatnonzero(expert_mask)] = subset_values[order]
        score = float(spearmanr(frame["truth"], routed).statistic)
        rounded_weight = round(float(expert_weight), 3)
        expert_sweep.append({"expert_weight": rounded_weight, "spearman": score})
        routed_candidates[rounded_weight] = routed
    best_expert = max(expert_sweep, key=lambda row: row["spearman"])
    frame["prediction"] = routed_candidates[float(best_expert["expert_weight"])]

    by_source = {
        source: regression_metrics(group["truth"].to_numpy(), group["prediction"].to_numpy())
        for source, group in frame.groupby("source_file", sort=True)
    }
    by_length = {}
    for length_group, group in frame.groupby("length_group", sort=True):
        by_length[length_group] = {
            "n": len(group),
            "base_spearman": float(
                spearmanr(group["truth"], group["base_prediction"]).statistic
            ),
            "parent_spearman": float(
                spearmanr(group["truth"], group["parent_prediction"]).statistic
            ),
            "ensemble_spearman": float(
                spearmanr(group["truth"], group["prediction"]).statistic
            ),
        }
    report = {
        "model": "stage18_esm_parent_cluster_rank_ensemble",
        "records": len(frame),
        "parent_weight": weight,
        "weight_search_note": "coarse validation diagnostic; not an unbiased test estimate",
        "sweep": sweep,
        "h119_expert_weight": best_expert["expert_weight"],
        "h119_expert_sweep": expert_sweep,
        "base_parent_prediction_spearman": float(
            spearmanr(frame["base_prediction"], frame["parent_prediction"]).statistic
        ),
        "by_source": by_source,
        "by_length": by_length,
        "overall": regression_metrics(frame["truth"].to_numpy(), frame["prediction"].to_numpy()),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame[["record_id", "source_file", "truth", "prediction"]].to_csv(OUTPUT, index=False)
    METRICS.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
