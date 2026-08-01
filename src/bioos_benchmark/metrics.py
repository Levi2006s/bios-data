from __future__ import annotations

import math

import numpy as np
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error


def safe_correlation(function, truth: np.ndarray, prediction: np.ndarray) -> float:
    if len(truth) < 3 or np.std(truth) == 0 or np.std(prediction) == 0:
        return float("nan")
    return float(function(truth, prediction).statistic)


def top_enrichment(truth: np.ndarray, prediction: np.ndarray, fraction: float = 0.1) -> float:
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
        "top10_enrichment": top_enrichment(truth, prediction, 0.1),
    }

