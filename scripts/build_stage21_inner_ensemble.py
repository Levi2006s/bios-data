"""Compare Stage 21 baseline and parent-delta models on the inner holdout."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

from bioos_benchmark.metrics import regression_metrics


BASE = Path("artifacts/stage21/inner_parent_conditioned_posconv_baseline/predictions.csv")
DELTA = Path("artifacts/stage21/inner_parent_delta_posconv/predictions.csv")
OUTPUT = Path("artifacts/stage21/inner_baseline_delta_ensemble.csv")


def main() -> None:
    base = pd.read_csv(BASE).rename(columns={"prediction": "base_prediction"})
    delta = pd.read_csv(DELTA).rename(columns={"prediction": "delta_prediction"})
    frame = base.merge(delta[["record_id", "delta_prediction"]], on="record_id", validate="one_to_one")
    base_rank = rankdata(frame["base_prediction"], method="average") / len(frame)
    delta_rank = rankdata(frame["delta_prediction"], method="average") / len(frame)
    sweep = []
    candidates = {}
    for weight in np.arange(0.0, 0.5001, 0.025):
        rounded = round(float(weight), 3)
        prediction = (1.0 - weight) * base_rank + weight * delta_rank
        sweep.append({"delta_weight": rounded, "spearman": float(spearmanr(frame["truth"], prediction).statistic)})
        candidates[rounded] = prediction
    best = max(sweep, key=lambda row: row["spearman"])
    frame["prediction"] = candidates[float(best["delta_weight"])]
    report = {
        "model": "stage21_inner_baseline_parent_delta_ensemble",
        "selection_fold": "stage21_inner_family_split",
        "records": len(frame), "best_delta_weight": best["delta_weight"], "sweep": sweep,
        "model_prediction_spearman": float(spearmanr(frame["base_prediction"], frame["delta_prediction"]).statistic),
        "overall": regression_metrics(frame["truth"].to_numpy(), frame["prediction"].to_numpy()),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame[["record_id", "source_file", "truth", "prediction"]].to_csv(OUTPUT, index=False)
    OUTPUT.with_suffix(".metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
