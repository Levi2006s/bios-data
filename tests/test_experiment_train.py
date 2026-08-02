from __future__ import annotations

import numpy as np

from bioos_benchmark.experiment_train import quality_weights, safe_metric_key


def test_quality_weights_are_bounded() -> None:
    weights = quality_weights([
        {"label_quality": "1"}, {"label_quality": "0.65"},
        {"label_quality": "0"}, {"label_quality": "bad"},
    ])
    assert np.allclose(weights, [1.0, 0.65, 0.05, 1.0])


def test_missing_metric_uses_explicit_fallback() -> None:
    assert safe_metric_key({}, "metric") == "unknown"
    assert safe_metric_key({"metric": "KD"}, "metric") == "KD"
