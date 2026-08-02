from __future__ import annotations

import math

import numpy as np
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error


def safe_correlation(function, truth: np.ndarray, prediction: np.ndarray) -> float:
    if (
        len(truth) < 3
        or np.isclose(np.std(truth), 0.0, atol=1e-12)
        or np.isclose(np.std(prediction), 0.0, atol=1e-12)
    ):
        return float("nan")
    return float(function(truth, prediction).statistic)


def top_enrichment(truth: np.ndarray, prediction: np.ndarray, fraction: float = 0.1) -> float:
    if (
        len(truth) < 2
        or np.isclose(np.std(truth), 0.0, atol=1e-12)
        or np.isclose(np.std(prediction), 0.0, atol=1e-12)
    ):
        return float("nan")
    count = max(1, math.ceil(len(truth) * fraction))
    predicted_top = set(np.argsort(prediction)[-count:])
    true_top = set(np.argsort(truth)[-count:])
    overlap = len(predicted_top & true_top)
    expected = count * count / len(truth)
    return float(overlap / expected) if expected else float("nan")


def regression_metrics(truth: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    return {
        "n": int(len(truth)),
        "rmse": float(mean_squared_error(truth, prediction) ** 0.5),
        "mae": float(mean_absolute_error(truth, prediction)),
        "pearson": safe_correlation(pearsonr, truth, prediction),
        "spearman": safe_correlation(spearmanr, truth, prediction),
        "top1_enrichment": top_enrichment(truth, prediction, 0.01),
        "top5_enrichment": top_enrichment(truth, prediction, 0.05),
        "top10_enrichment": top_enrichment(truth, prediction, 0.1),
    }
