"""Test whether the Stage 22 local-reference model adds inner-fold rank diversity."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr


BASE = Path("artifacts/stage21/inner_parent_conditioned_posconv_baseline/predictions.csv")
CONSENSUS = Path("artifacts/stage21/inner_parent_delta_posconv/predictions.csv")
LOCAL = Path("artifacts/stage22/inner_local_parent_delta_posconv/predictions.csv")
K16 = Path("artifacts/stage22/inner_parent_conditioned_posconv_k16/predictions.csv")
OUTPUT = Path("artifacts/stage22/inner_local_reference_ensemble_diagnostic.json")


def ranked(values: pd.Series) -> np.ndarray:
    return rankdata(values, method="average") / len(values)


def main() -> None:
    frame = pd.read_csv(BASE).rename(columns={"prediction": "base"})
    consensus = pd.read_csv(CONSENSUS).rename(columns={"prediction": "consensus"})
    local = pd.read_csv(LOCAL).rename(columns={"prediction": "local"})
    k16 = pd.read_csv(K16).rename(columns={"prediction": "k16"})
    frame = frame.merge(consensus[["record_id", "consensus"]], on="record_id", validate="one_to_one")
    frame = frame.merge(local[["record_id", "local"]], on="record_id", validate="one_to_one")
    frame = frame.merge(k16[["record_id", "k16"]], on="record_id", validate="one_to_one")
    base_rank, consensus_rank, local_rank, k16_rank = (ranked(frame[name]) for name in ("base", "consensus", "local", "k16"))
    selected_stage21 = 0.675 * base_rank + 0.325 * consensus_rank
    sweep = []
    for weight in np.arange(0.0, 0.2001, 0.025):
        prediction = (1.0 - weight) * selected_stage21 + weight * local_rank
        sweep.append({"local_weight": round(float(weight), 3), "spearman": float(spearmanr(frame["truth"], prediction).statistic)})
    selected_local = 0.9 * selected_stage21 + 0.1 * local_rank
    k16_sweep = []
    for weight in np.arange(0.0, 0.4001, 0.025):
        prediction = (1.0 - weight) * selected_local + weight * k16_rank
        k16_sweep.append({"k16_weight": round(float(weight), 3), "spearman": float(spearmanr(frame["truth"], prediction).statistic)})
    report = {
        "selection_fold": "stage21_inner_family_split",
        "stage21_fixed_spearman": float(spearmanr(frame["truth"], selected_stage21).statistic),
        "prediction_spearman": {
            "base_local": float(spearmanr(base_rank, local_rank).statistic),
            "consensus_local": float(spearmanr(consensus_rank, local_rank).statistic),
        },
        "sweep": sweep,
        "best": max(sweep, key=lambda row: row["spearman"]),
        "k16_sweep_after_fixed_local_0.1": k16_sweep,
        "k16_best": max(k16_sweep, key=lambda row: row["spearman"]),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
