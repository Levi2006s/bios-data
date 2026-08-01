from __future__ import annotations

from collections import Counter

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import HashingVectorizer


AA = "ACDEFGHIKLMNPQRSTVWY"
HYDROPHOBIC = frozenset("AVILMFWY")
POSITIVE = frozenset("KRH")
NEGATIVE = frozenset("DE")


def sequence_text(row: dict[str, str]) -> str:
    return f"H:{row['heavy']} L:{row.get('light', '')} A:{row.get('antigen_seq', '')}"


def numeric_features(row: dict[str, str]) -> list[float]:
    values: list[float] = []
    for key in ("heavy", "light", "antigen_seq"):
        sequence = row.get(key, "")
        length = max(len(sequence), 1)
        counts = Counter(sequence)
        values.extend(
            [
                len(sequence) / 1000.0,
                sum(counts[x] for x in HYDROPHOBIC) / length,
                (sum(counts[x] for x in POSITIVE) - sum(counts[x] for x in NEGATIVE)) / length,
                counts["C"] / length,
                counts["P"] / length,
            ]
        )
    return values


class AntibodyFeaturizer:
    def __init__(self, n_features: int = 2**16):
        self.n_features = n_features
        self.vectorizer = HashingVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            n_features=n_features,
            alternate_sign=False,
            norm="l2",
            lowercase=False,
        )

    def transform(self, rows: list[dict[str, str]]) -> sparse.csr_matrix:
        text_matrix = self.vectorizer.transform(sequence_text(row) for row in rows)
        numeric = sparse.csr_matrix(np.asarray([numeric_features(row) for row in rows], dtype=np.float32))
        return sparse.hstack([text_matrix, numeric], format="csr")

