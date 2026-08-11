from __future__ import annotations

from bioos_benchmark.ranking.validation_ensemble import sweep_validation_ensemble


def test_validation_ensemble_aligns_intersection() -> None:
    pointwise = [
        {"record_id": "a", "source_file": "s", "truth": "0", "prediction": "0"},
        {"record_id": "b", "source_file": "s", "truth": "1", "prediction": "1"},
    ]
    pairwise = [
        {"record_id": "a", "target_id": "t", "y_true": "0", "score": "1"},
        {"record_id": "b", "target_id": "t", "y_true": "1", "score": "0"},
        {"record_id": "c", "target_id": "t", "y_true": ".5", "score": ".5"},
    ]
    result = sweep_validation_ensemble(pointwise, pairwise, [0.0, 1.0])
    assert result["intersection_records"] == 2
    assert result["results"][0]["overall"]["rmse"] == 0.0
    assert result["results"][1]["overall"]["rmse"] == 1.0
