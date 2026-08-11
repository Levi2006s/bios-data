"""Build leakage-safe local parent references from frozen ESM embeddings."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import torch

from .esm_parent_clusters import pair_key


def build_local_references(
    input_path: Path,
    embeddings_path: Path,
    clusters_path: Path,
    output_path: Path,
    *,
    split_column: str,
    route: str = "alphaseq_rank",
    batch_size: int = 1024,
    device: str = "cuda",
) -> dict[str, object]:
    embedding_payload = torch.load(embeddings_path, map_location="cpu", weights_only=False)
    embeddings = embedding_payload["embeddings"].float()
    lookup = {sequence: index for index, sequence in enumerate(embedding_payload["sequences"])}
    zero = torch.zeros(embeddings.shape[1], dtype=torch.float32)
    cluster_payload = joblib.load(clusters_path)
    assignments = cluster_payload["assignments"]

    pairs: dict[str, tuple[str, str]] = {}
    splits: dict[str, str] = {}
    with input_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            split = row.get(split_column)
            if row.get("task_route") != route or split not in {"train", "validation"}:
                continue
            key = pair_key(row["heavy"], row.get("light", ""))
            pairs.setdefault(key, (row["heavy"], row.get("light", "")))
            splits[key] = split

    by_condition: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"train": [], "validation": []})
    for key, split in splits.items():
        by_condition[assignments[key]][split].append(key)

    def vectors(keys: list[str]) -> torch.Tensor:
        values = []
        for key in keys:
            heavy, light = pairs[key]
            light_embedding = embeddings[lookup[light]] if light in lookup else zero
            values.append(torch.cat((embeddings[lookup[heavy]], light_embedding)))
        tensor = torch.stack(values)
        return torch.nn.functional.normalize(tensor, dim=1)

    target_device = torch.device(device)
    pair_references: dict[str, dict[str, object]] = {}
    report: dict[str, object] = {}
    for condition, parts in sorted(by_condition.items()):
        train_keys = sorted(parts["train"])
        validation_keys = sorted(parts["validation"])
        if len(train_keys) < 2:
            raise ValueError(f"condition needs at least two training pairs: {condition}")
        candidates = vectors(train_keys).to(target_device)
        candidate_position = {key: index for index, key in enumerate(train_keys)}

        def assign(query_keys: list[str], exclude_self: bool) -> list[float]:
            similarities: list[float] = []
            for start in range(0, len(query_keys), batch_size):
                keys = query_keys[start : start + batch_size]
                query = vectors(keys).to(target_device)
                scores = query @ candidates.T
                if exclude_self:
                    rows = torch.arange(len(keys), device=target_device)
                    columns = torch.tensor([candidate_position[key] for key in keys], device=target_device)
                    scores[rows, columns] = -torch.inf
                best_scores, best_indices = scores.max(dim=1)
                for key, score, index in zip(keys, best_scores.cpu().tolist(), best_indices.cpu().tolist()):
                    reference_key = train_keys[int(index)]
                    heavy, light = pairs[reference_key]
                    pair_references[key] = {
                        "heavy": heavy,
                        "light": light,
                        "reference_key": reference_key,
                        "cosine_similarity": float(score),
                    }
                    similarities.append(float(score))
            return similarities

        train_similarities = assign(train_keys, exclude_self=True)
        validation_similarities = assign(validation_keys, exclude_self=False)
        report[condition] = {
            "train_unique": len(train_keys),
            "validation_unique": len(validation_keys),
            "train_similarity_median": float(np.median(train_similarities)),
            "validation_similarity_median": float(np.median(validation_similarities)) if validation_similarities else None,
        }
        del candidates
        if target_device.type == "cuda":
            torch.cuda.empty_cache()

    output_payload = dict(cluster_payload)
    output_payload["pair_references"] = pair_references
    output_payload["local_reference_method"] = "same_train_cluster_cosine_nearest_neighbor_excluding_train_self"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(output_payload, output_path)
    summary = {
        "output": str(output_path),
        "pairs": len(pair_references),
        "split_column": split_column,
        "route": route,
        "method": output_payload["local_reference_method"],
        "groups": report,
    }
    output_path.with_suffix(".json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--clusters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-column", required=True)
    parser.add_argument("--route", default="alphaseq_rank")
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    print(json.dumps(build_local_references(args.input, args.embeddings, args.clusters, args.output, split_column=args.split_column, route=args.route, batch_size=args.batch_size, device=args.device), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
