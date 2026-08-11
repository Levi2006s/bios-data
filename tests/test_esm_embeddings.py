from __future__ import annotations

import torch

from bioos_benchmark.esm_embeddings import residue_mean_pool


def test_residue_mean_pool_excludes_boundary_and_padding_tokens():
    hidden=torch.tensor([[[100.0],[2.0],[4.0],[200.0],[300.0]]])
    batch={
        "input_ids":torch.tensor([[0,5,6,2,1]]),
        "attention_mask":torch.tensor([[1,1,1,1,0]]),
    }
    pooled=residue_mean_pool(hidden,batch,(0,2,1))
    assert pooled.tolist()==[[3.0]]
