"""GPU antibody-antigen dual encoder for affinity ranking."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import torch
from scipy.stats import spearmanr
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from .metrics import regression_metrics
from .train import load_rows, split_rows, temperature_sampling_weights


AA_VOCAB = {aa: index + 1 for index, aa in enumerate("ACDEFGHIKLMNPQRSTVWY")}


def encode_sequence(sequence: str, length: int) -> torch.Tensor:
    values = [AA_VOCAB.get(aa, 0) for aa in sequence[:length]]
    values.extend([0] * (length - len(values)))
    return torch.tensor(values, dtype=torch.long)


class SequenceDataset(Dataset):
    def __init__(self, rows: list[dict[str, str]], source_power: float = 0.0):
        self.rows = rows
        counts = Counter(row["source_file"] for row in rows)
        group_names = sorted({row.get("comparison_group") or row["source_file"] for row in rows})
        group_ids = {name: index for index, name in enumerate(group_names)}
        self.group_ids = [group_ids[row.get("comparison_group") or row["source_file"]] for row in rows]
        raw = np.asarray([counts[row["source_file"]] ** (-source_power) for row in rows])
        self.weights = raw / raw.mean()

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        return (
            encode_sequence(row["heavy"], 180),
            encode_sequence(row.get("light", ""), 160),
            encode_sequence(row.get("antigen_seq", ""), 600),
            torch.tensor(float(row["score"]), dtype=torch.float32),
            torch.tensor(float(self.weights[index]), dtype=torch.float32),
            torch.tensor(self.group_ids[index], dtype=torch.long),
            index,
        )


class ChainEncoder(nn.Module):
    def __init__(self, embedding_dim: int = 32, hidden_dim: int = 64):
        super().__init__()
        self.embedding = nn.Embedding(len(AA_VOCAB) + 1, embedding_dim, padding_idx=0)
        self.convs = nn.ModuleList([
            nn.Conv1d(embedding_dim, hidden_dim // 2, kernel_size=3, padding=1),
            nn.Conv1d(embedding_dim, hidden_dim // 2, kernel_size=5, padding=2),
        ])

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        values = self.embedding(tokens).transpose(1, 2)
        encoded = [torch.amax(torch.relu(conv(values)), dim=2) for conv in self.convs]
        return torch.cat(encoded, dim=1)


class DualEncoderRanker(nn.Module):
    def __init__(self, hidden_dim: int = 64, dropout: float = 0.15):
        super().__init__()
        self.heavy_encoder = ChainEncoder(hidden_dim=hidden_dim)
        self.light_encoder = ChainEncoder(hidden_dim=hidden_dim)
        self.antigen_encoder = ChainEncoder(hidden_dim=hidden_dim)
        antibody_dim = hidden_dim * 2
        interaction_dim = antibody_dim * 3 + hidden_dim
        self.antigen_projection = nn.Linear(hidden_dim, antibody_dim)
        self.head = nn.Sequential(
            nn.Linear(interaction_dim, 192), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(192, 64), nn.ReLU(), nn.Dropout(dropout), nn.Linear(64, 1),
        )

    def forward(self, heavy: torch.Tensor, light: torch.Tensor, antigen: torch.Tensor) -> torch.Tensor:
        antibody = torch.cat([self.heavy_encoder(heavy), self.light_encoder(light)], dim=1)
        antigen_small = self.antigen_encoder(antigen)
        antigen_full = self.antigen_projection(antigen_small)
        features = torch.cat([
            antibody, antigen_small,
            torch.abs(antibody - antigen_full), antibody * antigen_full,
        ], dim=1)
        return self.head(features).squeeze(1)


@torch.no_grad()
def predict(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray, list[int]]:
    model.eval(); truth=[]; scores=[]; indices=[]
    for heavy, light, antigen, labels, _, _, batch_indices in loader:
        output = model(heavy.to(device), light.to(device), antigen.to(device))
        truth.extend(labels.numpy().tolist()); scores.extend(output.cpu().numpy().tolist())
        indices.extend(batch_indices.numpy().tolist())
    return np.asarray(truth), np.asarray(scores), indices


def train_neural_ranker(
    input_path: Path, artifact_dir: Path, *, seed: int = 42,
    split_column: str = "framework_family_split", epochs: int = 8,
    batch_size: int = 256, learning_rate: float = 2e-4,
    source_weight_power: float = 0.5, max_rows_per_source: int = 50_000,
    sampling_seed: int | None = None, rank_loss_weight: float = 0.0,
    include_task_routes: set[str] | None = None, sampling_alpha: float | None = None,
    sampling_cap: int = 200_000, allow_missing_antigen: bool = False,
    initialize_from: Path | None = None,
) -> dict[str, object]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for neural ranker training")
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    data_seed = seed if sampling_seed is None else sampling_seed
    # A machine-readable task route supersedes the legacy coarse tier filter.
    tier_filter=None if include_task_routes is not None else {"Gold","Silver"}
    rows = load_rows(input_path, max_rows_per_source, data_seed, tier_filter)
    if include_task_routes is not None:
        rows=[row for row in rows if row.get("task_route") in include_task_routes]
    train_rows, validation_rows = split_rows(rows, 20, split_column, "train", "validation")
    if not allow_missing_antigen:
        train_rows = [row for row in train_rows if row.get("antigen_seq")]
        validation_rows = [row for row in validation_rows if row.get("antigen_seq")]
    if not train_rows or not validation_rows:
        raise ValueError("No train/validation records remain after task and antigen routing")
    train_data = SequenceDataset(train_rows, source_weight_power)
    validation_data = SequenceDataset(validation_rows, 0.0)
    generator = torch.Generator().manual_seed(seed)
    sampler=None
    if sampling_alpha is not None:
        sampling_weights=temperature_sampling_weights(train_rows,sampling_alpha,sampling_cap)
        sampler=WeightedRandomSampler(torch.as_tensor(sampling_weights,dtype=torch.double),len(train_rows),replacement=True,generator=generator)
    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=sampler is None, sampler=sampler, generator=generator if sampler is None else None, num_workers=2, pin_memory=True)
    validation_loader = DataLoader(validation_data, batch_size=batch_size * 2, num_workers=2, pin_memory=True)
    device = torch.device("cuda")
    model = DualEncoderRanker().to(device)
    if initialize_from is not None:
        checkpoint = torch.load(initialize_from, map_location="cpu", weights_only=False)
        model.load_state_dict(checkpoint["state_dict"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max(epochs, 1), eta_min=learning_rate * 0.03,
    )
    history=[]; best_spearman=-float("inf"); best_state=None
    for epoch in range(1, epochs + 1):
        model.train(); loss_sum=0.0; count=0
        for heavy, light, antigen, labels, weights, group_ids, _ in train_loader:
            heavy=heavy.to(device, non_blocking=True); light=light.to(device, non_blocking=True)
            antigen=antigen.to(device, non_blocking=True); labels=labels.to(device); weights=weights.to(device)
            optimizer.zero_grad(set_to_none=True)
            output=model(heavy, light, antigen)
            regression_loss=(nn.functional.smooth_l1_loss(output, labels, reduction="none") * weights).mean()
            if rank_loss_weight > 0:
                # Random in-batch pairs provide an O(B) approximation to the
                # pairwise ranking objective and directly optimize ordering.
                # Only compare records from the same assay/comparison group.
                # Rolling within each group is O(B), deterministic in membership,
                # and avoids physically meaningless cross-assay preferences.
                permutation = torch.arange(len(labels), device=device)
                for group_id in torch.unique(group_ids):
                    positions = torch.nonzero(group_ids.to(device) == group_id, as_tuple=False).flatten()
                    if len(positions) > 1:
                        permutation[positions] = positions.roll(1)
                label_delta = labels - labels[permutation]
                usable = (group_ids.to(device) == group_ids.to(device)[permutation]) & (permutation != torch.arange(len(labels), device=device)) & (label_delta.abs() > 1e-6)
                if usable.any():
                    signed_margin = label_delta[usable].sign() * (output[usable] - output[permutation][usable])
                    pair_weights = label_delta[usable].abs().clamp_max(0.5)
                    ranking_loss = (nn.functional.softplus(-signed_margin) * pair_weights).sum() / pair_weights.sum()
                    loss = regression_loss + rank_loss_weight * ranking_loss
                else:
                    loss = regression_loss
            else:
                loss = regression_loss
            loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); optimizer.step()
            loss_sum += float(loss.item()) * len(labels); count += len(labels)
        truth, scores, _ = predict(model, validation_loader, device)
        correlation=float(spearmanr(truth, scores).statistic)
        history.append({"epoch":epoch,"train_loss":loss_sum/count,"validation_spearman":correlation,"learning_rate":optimizer.param_groups[0]["lr"]})
        print(json.dumps(history[-1]), flush=True)
        if correlation > best_spearman:
            best_spearman=correlation
            best_state={key:value.detach().cpu().clone() for key,value in model.state_dict().items()}
        scheduler.step()
    assert best_state is not None
    model.load_state_dict(best_state); truth, scores, indices = predict(model, validation_loader, device)
    metrics={
        "model":"cnn_antibody_antigen_dual_encoder", "device":torch.cuda.get_device_name(0),
        "seed":seed,"epochs":epochs,"batch_size":batch_size,"learning_rate":learning_rate,
        "sampling_seed":data_seed,
        "include_task_routes":sorted(include_task_routes) if include_task_routes else None,
        "sampling_alpha":sampling_alpha,"sampling_cap":sampling_cap,
        "allow_missing_antigen":allow_missing_antigen,
        "initialize_from":str(initialize_from) if initialize_from else None,
        "rank_loss_weight":rank_loss_weight,
        "source_weight_power":source_weight_power,"train_records":len(train_rows),
        "validation_records":len(validation_rows),"best_validation_spearman":best_spearman,
        "overall":regression_metrics(truth, scores),"history":history,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict":best_state,"metrics":metrics},artifact_dir/"model.pt")
    (artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.writer(handle);writer.writerow(["record_id","source_file","truth","prediction"])
        for idx,y,score in zip(indices,truth,scores):
            row=validation_rows[idx];writer.writerow([row["record_id"],row["source_file"],y,score])
    return metrics


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--artifact-dir",type=Path,required=True);parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--split-column",default="framework_family_split");parser.add_argument("--epochs",type=int,default=8)
    parser.add_argument("--batch-size",type=int,default=256);parser.add_argument("--learning-rate",type=float,default=2e-4)
    parser.add_argument("--source-weight-power",type=float,default=.5);parser.add_argument("--max-rows-per-source",type=int,default=50_000)
    parser.add_argument("--sampling-seed",type=int)
    parser.add_argument("--rank-loss-weight",type=float,default=0.0)
    parser.add_argument("--include-task-routes",nargs="*");parser.add_argument("--sampling-alpha",type=float);parser.add_argument("--sampling-cap",type=int,default=200_000)
    parser.add_argument("--allow-missing-antigen",action="store_true");parser.add_argument("--initialize-from",type=Path)
    args=parser.parse_args();print(json.dumps(train_neural_ranker(args.input,args.artifact_dir,seed=args.seed,split_column=args.split_column,epochs=args.epochs,batch_size=args.batch_size,learning_rate=args.learning_rate,source_weight_power=args.source_weight_power,max_rows_per_source=args.max_rows_per_source,sampling_seed=args.sampling_seed,rank_loss_weight=args.rank_loss_weight,include_task_routes=set(args.include_task_routes) if args.include_task_routes else None,sampling_alpha=args.sampling_alpha,sampling_cap=args.sampling_cap,allow_missing_antigen=args.allow_missing_antigen,initialize_from=args.initialize_from),ensure_ascii=False,indent=2))


if __name__ == "__main__": main()
