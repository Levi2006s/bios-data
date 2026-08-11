import csv
from pathlib import Path

import joblib
import torch

from bioos_benchmark.esm_local_references import build_local_references
from bioos_benchmark.esm_parent_clusters import pair_key


def test_local_reference_excludes_train_self_and_uses_only_train_for_validation(tmp_path: Path) -> None:
    sequences = ["AAAA", "AAAC", "AACC", "CCCC"]
    embeddings = torch.tensor([[1.0, 0.0], [0.9, 0.1], [0.8, 0.2], [0.0, 1.0]])
    embedding_path = tmp_path / "embeddings.pt"
    torch.save({"sequences": sequences, "embeddings": embeddings}, embedding_path)
    rows = [
        {"heavy": "AAAA", "light": "CCCC", "task_route": "alphaseq_rank", "fold": "train"},
        {"heavy": "AAAC", "light": "CCCC", "task_route": "alphaseq_rank", "fold": "train"},
        {"heavy": "AACC", "light": "CCCC", "task_route": "alphaseq_rank", "fold": "validation"},
    ]
    input_path = tmp_path / "rows.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    keys = [pair_key(row["heavy"], row["light"]) for row in rows]
    cluster_path = tmp_path / "clusters.joblib"
    joblib.dump({"assignments": {key: "group|C0" for key in keys}}, cluster_path)
    output_path = tmp_path / "local.joblib"
    build_local_references(input_path, embedding_path, cluster_path, output_path, split_column="fold", device="cpu", batch_size=2)
    references = joblib.load(output_path)["pair_references"]
    assert references[keys[0]]["reference_key"] == keys[1]
    assert references[keys[1]]["reference_key"] == keys[0]
    assert references[keys[2]]["reference_key"] in {keys[0], keys[1]}

