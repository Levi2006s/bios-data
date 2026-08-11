import csv
from pathlib import Path

import joblib
import torch

from bioos_benchmark.esm_parent_clusters import build, pair_key


def test_parent_clusters_include_train_only_ood_percentiles(tmp_path: Path) -> None:
    sequences = ["AAAA", "AAAC", "CCCC", "CCCA"]
    embeddings = torch.tensor([[0.0, 0.0], [0.1, 0.0], [1.0, 1.0], [0.9, 1.0]])
    embedding_path = tmp_path / "embeddings.pt"
    torch.save({"sequences": sequences, "embeddings": embeddings}, embedding_path)

    input_path = tmp_path / "rows.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_file", "heavy", "light", "task_route", "fold"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"source_file": "affinity1.csv", "heavy": "AAAA", "light": "CCCC", "task_route": "alphaseq_rank", "fold": "train"},
                {"source_file": "affinity1.csv", "heavy": "AAAC", "light": "CCCA", "task_route": "alphaseq_rank", "fold": "train"},
                {"source_file": "affinity1.csv", "heavy": "AAAA", "light": "CCCA", "task_route": "alphaseq_rank", "fold": "validation"},
            ]
        )

    output = tmp_path / "clusters.joblib"
    build(input_path, embedding_path, output, split_column="fold", clusters_per_group=1)
    payload = joblib.load(output)
    validation_key = pair_key("AAAA", "CCCA")
    assert validation_key in payload["assignments"]
    assert payload["distances"][validation_key] >= 0.0
    assert 0.0 <= payload["ood_percentiles"][validation_key] <= 1.0

