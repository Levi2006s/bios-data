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


def sampled_kmers(sequence: str, k: int = 3, limit: int = 16) -> list[str]:
    """Return a deterministic, position-covering subset of unique k-mers."""
    kmers = list(dict.fromkeys(sequence[index:index + k] for index in range(max(0, len(sequence) - k + 1))))
    if len(kmers) <= limit:
        return kmers
    positions = np.linspace(0, len(kmers) - 1, num=limit, dtype=int)
    return [kmers[index] for index in positions]


def interaction_text(row: dict[str, str], limit: int = 16) -> str:
    """Explicit antibody-kmer by antigen-kmer tokens for a linear interaction head."""
    antigen = row.get("antigen_seq", "")
    if not antigen:
        return ""
    antibody_region = row.get("cdrh3", "") or row.get("heavy", "")[-36:]
    antibody_region += row.get("light", "")[-24:]
    antibody_kmers = sampled_kmers(antibody_region, limit=limit)
    antigen_kmers = sampled_kmers(antigen, limit=limit)
    return " ".join(f"X_{left}_{right}" for left in antibody_kmers for right in antigen_kmers)


class InteractionFeaturizer:
    """Add sparse antibody-antigen cross features to the sequence baseline."""

    def __init__(self, n_features: int = 2**16, interaction_features: int = 2**17):
        self.n_features = n_features
        self.interaction_features = interaction_features
        self.base = AntibodyFeaturizer(n_features=n_features)
        self.interactions = HashingVectorizer(
            analyzer="word",
            token_pattern=r"[^ ]+",
            n_features=interaction_features,
            alternate_sign=True,
            norm="l2",
            lowercase=False,
        )

    def transform(self, rows: list[dict[str, str]]) -> sparse.csr_matrix:
        base = self.base.transform(rows)
        cross = self.interactions.transform(interaction_text(row) for row in rows)
        return sparse.hstack([base, cross], format="csr")
