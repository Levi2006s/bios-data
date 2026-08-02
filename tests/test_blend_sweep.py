from __future__ import annotations

import numpy as np

from bioos_benchmark.blend_sweep import evaluate_blends


def test_evaluate_blends_reports_endpoints() -> None:
    rows = [{"source_file": "a"} for _ in range(4)]
    truth = np.asarray([0.0, 0.25, 0.75, 1.0])
    global_prediction = truth.copy()
    expert_prediction = truth[::-1]
    results = evaluate_blends(rows, truth, global_prediction, expert_prediction, [0.0, 1.0])
    assert results[0]["overall"]["spearman"] == 1.0
    assert results[1]["overall"]["spearman"] == -1.0
