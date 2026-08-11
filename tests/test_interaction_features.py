from __future__ import annotations

import numpy as np

from bioos_benchmark.features import InteractionFeaturizer, interaction_text, sampled_kmers


def test_sampled_kmers_are_bounded_and_deterministic() -> None:
    sequence = "ACDEFGHIKLMNPQRSTVWY" * 2
    assert sampled_kmers(sequence, limit=5) == sampled_kmers(sequence, limit=5)
    assert len(sampled_kmers(sequence, limit=5)) == 5


def test_interaction_tokens_require_antigen_and_change_with_antigen() -> None:
    row = {"heavy": "ACDEFGHIKLMN", "light": "PQRSTVWY", "cdrh3": "EFGHIK", "antigen_seq": "ACDEFG"}
    assert interaction_text(row)
    assert interaction_text({**row, "antigen_seq": ""}) == ""
    featurizer = InteractionFeaturizer(n_features=64, interaction_features=128)
    matrix = featurizer.transform([row, {**row, "antigen_seq": "YYYYYY"}])
    cross = matrix[:, -(128):].toarray()
    assert not np.allclose(cross[0], cross[1])
