from __future__ import annotations

import torch

from bioos_benchmark.esm_head import EsmInteractionHead


def test_esm_head_forward() -> None:
    model=EsmInteractionHead(input_dim=16,latent_dim=8,dropout=0)
    values=[torch.randn(4,16) for _ in range(3)]
    output=model(*values)
    assert output.shape==(4,)
    assert torch.isfinite(output).all()
