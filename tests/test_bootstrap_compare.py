from __future__ import annotations

import numpy as np

from bioos_benchmark.bootstrap_compare import paired_cluster_bootstrap


def test_paired_cluster_bootstrap_detects_better_candidate():
    truth=np.arange(12,dtype=float)
    baseline=np.asarray([0,2,1,4,3,6,5,8,7,10,9,11],dtype=float)
    candidate=truth.copy()
    groups=np.repeat(["a","b","c"],4)
    report=paired_cluster_bootstrap(truth,baseline,candidate,groups,repeats=100,seed=7)
    assert report["point_delta_spearman"]>0
    assert report["probability_candidate_better"]>.9
