"""Apply Stage 22 inner-selected weights once on the outer validation fold."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from scipy.stats import rankdata, spearmanr

from bioos_benchmark.metrics import regression_metrics


STAGE17 = Path("artifacts/stage17/global_family_v2_final_parent_ensemble.csv")
ABSOLUTE_K8 = Path("artifacts/stage18/global_family_v2_esm_parent_conditioned_posconv/predictions.csv")
CONSENSUS_DELTA = Path("artifacts/stage21/outer_parent_delta_posconv/predictions.csv")
LOCAL_DELTA = Path("artifacts/stage22/outer_local_parent_delta_posconv/predictions.csv")
ABSOLUTE_K16 = Path("artifacts/stage22/outer_parent_conditioned_posconv_k16/predictions.csv")
OUTPUT = Path("artifacts/stage22/preregistered_outer_multiresolution_parent_ensemble.csv")


def rank(values: pd.Series) -> pd.Series:
    return pd.Series(rankdata(values, method="average") / len(values), index=values.index)


def main() -> None:
    components = {
        "stage17": STAGE17,
        "absolute_k8": ABSOLUTE_K8,
        "consensus_delta": CONSENSUS_DELTA,
        "local_delta": LOCAL_DELTA,
        "absolute_k16": ABSOLUTE_K16,
    }
    frame: pd.DataFrame | None = None
    for name, path in components.items():
        current = pd.read_csv(path).rename(columns={"prediction": f"{name}_prediction"})
        keep = ["record_id", f"{name}_prediction"]
        if frame is None:
            frame = current.rename(columns={"truth": "truth", "source_file": "source_file"})
        else:
            frame = frame.merge(current[keep], on="record_id", validate="one_to_one")
    assert frame is not None

    ranked = {name: rank(frame[f"{name}_prediction"]) for name in components}
    stage21_parent = 0.675 * ranked["absolute_k8"] + 0.325 * ranked["consensus_delta"]
    local_augmented = 0.9 * stage21_parent + 0.1 * ranked["local_delta"]
    stage22_parent = 0.725 * local_augmented + 0.275 * ranked["absolute_k16"]
    frame["prediction"] = 0.775 * ranked["stage17"] + 0.225 * stage22_parent

    effective_weights = {
        "stage17": 0.775,
        "absolute_k8": 0.225 * 0.725 * 0.9 * 0.675,
        "consensus_delta": 0.225 * 0.725 * 0.9 * 0.325,
        "local_delta": 0.225 * 0.725 * 0.1,
        "absolute_k16": 0.225 * 0.275,
    }
    by_source = {
        source: regression_metrics(group["truth"].to_numpy(), group["prediction"].to_numpy())
        for source, group in frame.groupby("source_file", sort=True)
    }
    report = {
        "model": "stage22_preregistered_multiresolution_parent_outer_ensemble",
        "selection_fold": "stage21_inner_family_split_only",
        "selection_metrics": {
            "stage21_parent_inner_spearman": 0.6464025801482838,
            "stage22_parent_inner_spearman": 0.6484783355438837,
        },
        "nested_weights": {
            "outer_stage17": 0.775,
            "outer_parent": 0.225,
            "parent_k16": 0.275,
            "parent_local_augmented": 0.725,
            "local_delta_within_local_augmented": 0.1,
            "stage21_parent_within_local_augmented": 0.9,
            "absolute_k8_within_stage21_parent": 0.675,
            "consensus_delta_within_stage21_parent": 0.325,
        },
        "effective_weights": effective_weights,
        "outer_weight_search_performed": False,
        "component_spearman": {
            name: float(spearmanr(frame["truth"], frame[f"{name}_prediction"]).statistic)
            for name in components
        },
        "by_source": by_source,
        "overall": regression_metrics(frame["truth"].to_numpy(), frame["prediction"].to_numpy()),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame[["record_id", "source_file", "truth", "prediction"]].to_csv(OUTPUT, index=False)
    OUTPUT.with_suffix(".metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
