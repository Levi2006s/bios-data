"""Train an interaction ranking head over frozen ESM embeddings."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .metrics import regression_metrics
from .train import load_rows, split_rows


class EsmInteractionHead(nn.Module):
    def __init__(self, input_dim: int = 320, latent_dim: int = 256, dropout: float = 0.2):
        super().__init__()
        self.antibody = nn.Sequential(nn.Linear(input_dim * 2, latent_dim), nn.LayerNorm(latent_dim), nn.GELU())
        self.antigen = nn.Sequential(nn.Linear(input_dim, latent_dim), nn.LayerNorm(latent_dim), nn.GELU())
        self.head = nn.Sequential(
            nn.Linear(latent_dim * 4, 256), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(256, 64), nn.GELU(), nn.Dropout(dropout), nn.Linear(64, 1),
        )

    def forward(self, heavy: torch.Tensor, light: torch.Tensor, antigen: torch.Tensor) -> torch.Tensor:
        antibody = self.antibody(torch.cat([heavy, light], dim=1))
        target = self.antigen(antigen)
        features = torch.cat([antibody, target, torch.abs(antibody - target), antibody * target], dim=1)
        return self.head(features).squeeze(1)


def row_tensors(rows: list[dict[str, str]], lookup: dict[str, torch.Tensor], source_weight_power: float = 0.5) -> tuple[torch.Tensor, ...]:
    dim = next(iter(lookup.values())).numel()
    zero = torch.zeros(dim, dtype=torch.float32)
    heavy = torch.stack([lookup[row["heavy"]] for row in rows]).float()
    light = torch.stack([lookup.get(row.get("light", ""), zero) for row in rows]).float()
    antigen = torch.stack([lookup[row["antigen_seq"]] for row in rows]).float()
    labels = torch.tensor([float(row["score"]) for row in rows], dtype=torch.float32)
    counts = Counter(row["source_file"] for row in rows)
    weights = torch.tensor([counts[row["source_file"]] ** -source_weight_power for row in rows], dtype=torch.float32)
    weights /= weights.mean()
    antigen_ids={sequence:index for index,sequence in enumerate(sorted({row["antigen_seq"] for row in rows}))}
    groups=torch.tensor([antigen_ids[row["antigen_seq"]] for row in rows],dtype=torch.long)
    return heavy, light, antigen, labels, weights, groups


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray, list[int]]:
    model.eval(); truth=[]; prediction=[]; indices=[]
    for heavy, light, antigen, labels, _, _, idx in loader:
        scores=model(heavy.to(device),light.to(device),antigen.to(device))
        truth.extend(labels.numpy());prediction.extend(scores.cpu().numpy());indices.extend(idx.numpy())
    return np.asarray(truth),np.asarray(prediction),[int(x) for x in indices]


def train_esm_head(
    input_path: Path, embeddings_path: Path, artifact_dir: Path, *,
    seed: int = 42, sampling_seed: int = 20260803, epochs: int = 40,
    batch_size: int = 512, learning_rate: float = 3e-4,
    max_rows_per_source: int = 50_000, source_weight_power: float = 0.5,
    rank_loss_weight: float = 0.0, conditional_rank_loss_weight: float = 0.0,
    initial_model: Path | None = None,
) -> dict[str, object]:
    if not torch.cuda.is_available(): raise RuntimeError("CUDA is required")
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    payload=torch.load(embeddings_path,map_location="cpu")
    lookup={sequence:embedding for sequence,embedding in zip(payload["sequences"],payload["embeddings"])}
    rows=load_rows(input_path,max_rows_per_source,sampling_seed,{"Gold","Silver"})
    train_rows,validation_rows=split_rows(rows,20,"framework_family_split","train","validation")
    train_rows=[row for row in train_rows if row.get("antigen_seq") in lookup and row["heavy"] in lookup]
    validation_rows=[row for row in validation_rows if row.get("antigen_seq") in lookup and row["heavy"] in lookup]
    train=(*row_tensors(train_rows,lookup,source_weight_power),torch.arange(len(train_rows)))
    validation=(*row_tensors(validation_rows,lookup,0.0),torch.arange(len(validation_rows)))
    generator=torch.Generator().manual_seed(seed)
    train_loader=DataLoader(TensorDataset(*train),batch_size=batch_size,shuffle=True,generator=generator,pin_memory=True)
    validation_loader=DataLoader(TensorDataset(*validation),batch_size=batch_size*2,pin_memory=True)
    device=torch.device("cuda");model=EsmInteractionHead(input_dim=train[0].shape[1]).to(device)
    if initial_model is not None:
        checkpoint=torch.load(initial_model,map_location="cpu")
        model.load_state_dict(checkpoint["state_dict"])
    optimizer=torch.optim.AdamW(model.parameters(),lr=learning_rate,weight_decay=1e-4)
    best=-float("inf");best_state=None;history=[];stale=0
    for epoch in range(1,epochs+1):
        model.train();loss_sum=0.;count=0
        for heavy,light,antigen,labels,weights,groups,_ in train_loader:
            heavy=heavy.to(device);light=light.to(device);antigen=antigen.to(device);labels=labels.to(device);weights=weights.to(device);groups=groups.to(device)
            optimizer.zero_grad(set_to_none=True);scores=model(heavy,light,antigen)
            regression_loss=(nn.functional.smooth_l1_loss(scores,labels,reduction="none")*weights).mean()
            if rank_loss_weight > 0:
                permutation=torch.randperm(len(labels),device=device);delta=labels-labels[permutation];usable=delta.abs()>1e-6
                if usable.any():
                    margin=delta[usable].sign()*(scores[usable]-scores[permutation][usable]);pair_weights=delta[usable].abs().clamp_max(.5)
                    rank_loss=(nn.functional.softplus(-margin)*pair_weights).sum()/pair_weights.sum()
                    loss=regression_loss+rank_loss_weight*rank_loss
                else: loss=regression_loss
            else: loss=regression_loss
            if conditional_rank_loss_weight > 0:
                conditional_losses=[]
                for group in groups.unique():
                    positions=(groups==group).nonzero(as_tuple=False).squeeze(1)
                    if len(positions)<2: continue
                    paired=positions.roll(1);delta=labels[positions]-labels[paired];usable=delta.abs()>1e-6
                    if usable.any():
                        margin=delta[usable].sign()*(scores[positions[usable]]-scores[paired[usable]])
                        conditional_losses.append(nn.functional.softplus(-margin).mean())
                if conditional_losses:
                    loss=loss+conditional_rank_loss_weight*torch.stack(conditional_losses).mean()
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step()
            loss_sum+=float(loss)*len(labels);count+=len(labels)
        truth,prediction,_=evaluate(model,validation_loader,device)
        rho=float(spearmanr(truth,prediction).statistic);history.append({"epoch":epoch,"train_loss":loss_sum/count,"validation_spearman":rho})
        print(json.dumps(history[-1]),flush=True)
        if rho>best:
            best=rho;best_state={key:value.detach().cpu().clone() for key,value in model.state_dict().items()};stale=0
        else: stale+=1
        if stale>=8: break
    assert best_state is not None;model.load_state_dict(best_state)
    truth,prediction,indices=evaluate(model,validation_loader,device)
    metrics={"model":"frozen_esm_interaction_head","seed":seed,"sampling_seed":sampling_seed,"epochs_completed":len(history),"train_records":len(train_rows),"validation_records":len(validation_rows),"max_rows_per_source":max_rows_per_source,"source_weight_power":source_weight_power,"rank_loss_weight":rank_loss_weight,"conditional_rank_loss_weight":conditional_rank_loss_weight,"initial_model":str(initial_model) if initial_model else None,"best_validation_spearman":best,"overall":regression_metrics(truth,prediction),"history":history}
    artifact_dir.mkdir(parents=True,exist_ok=True);torch.save({"state_dict":best_state,"metrics":metrics},artifact_dir/"model.pt")
    (artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.writer(handle);writer.writerow(["record_id","source_file","truth","prediction"])
        for idx,y,score in zip(indices,truth,prediction):
            row=validation_rows[idx];writer.writerow([row["record_id"],row["source_file"],y,score])
    return metrics


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--input",type=Path,required=True);parser.add_argument("--embeddings",type=Path,required=True);parser.add_argument("--artifact-dir",type=Path,required=True)
    parser.add_argument("--seed",type=int,default=42);parser.add_argument("--sampling-seed",type=int,default=20260803);parser.add_argument("--epochs",type=int,default=40);parser.add_argument("--batch-size",type=int,default=512);parser.add_argument("--learning-rate",type=float,default=3e-4)
    parser.add_argument("--max-rows-per-source",type=int,default=50_000);parser.add_argument("--source-weight-power",type=float,default=.5);parser.add_argument("--rank-loss-weight",type=float,default=0.0);parser.add_argument("--conditional-rank-loss-weight",type=float,default=0.0)
    parser.add_argument("--initial-model",type=Path)
    args=parser.parse_args();print(json.dumps(train_esm_head(args.input,args.embeddings,args.artifact_dir,seed=args.seed,sampling_seed=args.sampling_seed,epochs=args.epochs,batch_size=args.batch_size,learning_rate=args.learning_rate,max_rows_per_source=args.max_rows_per_source,source_weight_power=args.source_weight_power,rank_loss_weight=args.rank_loss_weight,conditional_rank_loss_weight=args.conditional_rank_loss_weight,initial_model=args.initial_model),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
