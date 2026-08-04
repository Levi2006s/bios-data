"""Apply Stage 21 inner-selected weights once on the outer validation fold."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from scipy.stats import rankdata, spearmanr

from bioos_benchmark.metrics import regression_metrics


STAGE17 = Path("artifacts/stage17/global_family_v2_final_parent_ensemble.csv")
ABSOLUTE = Path("artifacts/stage18/global_family_v2_esm_parent_conditioned_posconv/predictions.csv")
DELTA = Path("artifacts/stage21/outer_parent_delta_posconv/predictions.csv")
OUTPUT = Path("artifacts/stage21/preregistered_outer_parent_delta_ensemble.csv")


def rank(values: pd.Series) -> pd.Series:
    return pd.Series(rankdata(values, method="average") / len(values), index=values.index)


def main() -> None:
    stage17 = pd.read_csv(STAGE17).rename(columns={"prediction": "stage17_prediction"})
    absolute = pd.read_csv(ABSOLUTE).rename(columns={"prediction": "absolute_prediction"})
    delta = pd.read_csv(DELTA).rename(columns={"prediction": "delta_prediction"})
    frame = stage17.merge(absolute[["record_id", "absolute_prediction"]], on="record_id", validate="one_to_one")
    frame = frame.merge(delta[["record_id", "delta_prediction"]], on="record_id", validate="one_to_one")
    stage17_rank = rank(frame["stage17_prediction"])
    absolute_rank = rank(frame["absolute_prediction"])
    delta_rank = rank(frame["delta_prediction"])
    parent_subensemble = 0.675 * absolute_rank + 0.325 * delta_rank
    frame["prediction"] = 0.775 * stage17_rank + 0.225 * parent_subensemble
    by_source = {
        source: regression_metrics(group["truth"].to_numpy(), group["prediction"].to_numpy())
        for source, group in frame.groupby("source_file", sort=True)
    }
    report = {
        "model": "stage21_preregistered_parent_delta_outer_ensemble",
        "weight_selection": "stage21_inner_family_split_only",
        "weights": {"stage17": 0.775, "absolute_parent": 0.151875, "parent_delta": 0.073125},
        "outer_weight_search_performed": False,
        "component_spearman": {
            "stage17": float(spearmanr(frame["truth"], frame["stage17_prediction"]).statistic),
            "absolute_parent": float(spearmanr(frame["truth"], frame["absolute_prediction"]).statistic),
            "parent_delta": float(spearmanr(frame["truth"], frame["delta_prediction"]).statistic),
        },
        "by_source": by_source,
        "overall": regression_metrics(frame["truth"].to_numpy(), frame["prediction"].to_numpy()),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame[["record_id", "source_file", "truth", "prediction"]].to_csv(OUTPUT, index=False)
    OUTPUT.with_suffix(".metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
