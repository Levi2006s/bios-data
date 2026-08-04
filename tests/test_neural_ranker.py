from __future__ import annotations

import torch

from bioos_benchmark.neural_ranker import DualEncoderRanker, encode_sequence


def test_neural_ranker_forward_shape() -> None:
    model = DualEncoderRanker(hidden_dim=16, dropout=0.0)
    heavy = torch.stack([encode_sequence("ACDEFG", 12), encode_sequence("YYYY", 12)])
    light = torch.stack([encode_sequence("HIK", 10), encode_sequence("", 10)])
    antigen = torch.stack([encode_sequence("LMNPQ", 16), encode_sequence("RST", 16)])
    output = model(heavy, light, antigen)
    assert output.shape == (2,)
    assert torch.isfinite(output).all()
