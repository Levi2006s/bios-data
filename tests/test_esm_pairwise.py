from __future__ import annotations

import numpy as np

from bioos_benchmark.esm_pairwise import build_pairs, macro_group_spearman


def test_build_pairs_never_crosses_comparison_groups():
    rows=[{"comparison_group":"a","score":"0"},{"comparison_group":"a","score":"1"},{"comparison_group":"b","score":"0"},{"comparison_group":"b","score":"1"}]
    pairs=build_pairs(rows,minimum_gap=.1,offsets=(1.0,))
    assert pairs==[(1,0),(3,2)]


def test_macro_group_spearman_is_group_equal_weighted():
    rows=[{"comparison_group":"a"}]*5+[{"comparison_group":"b"}]*5
    truth=np.tile(np.arange(5),2);prediction=np.r_[np.arange(5),np.arange(4,-1,-1)]
    result=macro_group_spearman(rows,truth,prediction)
    assert result["groups"]==2 and abs(result["macro_spearman"])<1e-12
