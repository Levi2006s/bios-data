import numpy as np
import pytest
from bioos_benchmark.train import temperature_sampling_weights

def test_temperature_sampling_reduces_large_dataset_dominance():
    rows=[{"source_file":"small","affinity_weight":"1"} for _ in range(10)]+[{"source_file":"large","affinity_weight":"1"} for _ in range(1000)]
    weights=temperature_sampling_weights(rows,alpha=.5,cap=200_000)
    small=weights[:10].sum();large=weights[10:].sum()
    assert np.isclose(large/small,10.0)

def test_zero_quality_never_sampled():
    rows=[{"source_file":"a","affinity_weight":"1"},{"source_file":"b","affinity_weight":"0"}]
    weights=temperature_sampling_weights(rows)
    assert weights[0]>0 and weights[1]==0

def test_invalid_temperature_rejected():
    with pytest.raises(ValueError):temperature_sampling_weights([{"source_file":"a"}],alpha=1.1)
