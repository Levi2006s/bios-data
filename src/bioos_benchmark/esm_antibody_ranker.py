"""Memory-efficient ESM antibody-only ranker for fixed-target landscapes."""

from __future__ import annotations

import argparse, csv, json, random
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

from .metrics import regression_metrics


class AntibodyEsmHead(nn.Module):
    def __init__(self, dim: int, dropout: float = 0.15):
        super().__init__()
        self.net=nn.Sequential(nn.Linear(dim,512),nn.LayerNorm(512),nn.GELU(),nn.Dropout(dropout),nn.Linear(512,128),nn.GELU(),nn.Dropout(dropout),nn.Linear(128,1))
    def forward(self,x):return self.net(x).squeeze(1)


def load_route(path:Path,lookup:dict[str,int],zero_index:int,route:str,split_column:str,deduplicate_biological:bool=False):
    rows=[];groups={};sources={};seen=set()
    with path.open(encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("task_route")!=route or r.get(split_column) not in {"train","validation"}:continue
            sequence=r.get("heavy","")
            if sequence not in lookup:continue
            biological_key=(sequence,r.get("light",""),r["score"],r[split_column])
            if deduplicate_biological and biological_key in seen:continue
            seen.add(biological_key)
            group=r.get("comparison_group") or r["source_file"]
            groups.setdefault(group,len(groups));sources.setdefault(r["source_file"],len(sources))
            rows.append((lookup[sequence],lookup.get(r.get("light",""),zero_index),float(r["score"]),float(r.get("affinity_weight","1") or 0),groups[group],sources[r["source_file"]],r[split_column],r["record_id"],r["source_file"]))
    return rows


@torch.no_grad()
def evaluate(model,embeddings,loader,device):
    model.eval();truth=[];pred=[];indices=[]
    for heavy_idx,light_idx,labels,_,_,_,row_idx in loader:
        pair=torch.cat([embeddings[heavy_idx],embeddings[light_idx]],dim=1).to(device,dtype=torch.float32)
        scores=model(pair);truth.extend(labels.numpy());pred.extend(scores.cpu().numpy());indices.extend(row_idx.numpy())
    return np.asarray(truth),np.asarray(pred),[int(x) for x in indices]


def train(input_path:Path,embeddings_path:Path,artifact_dir:Path,*,route="alphaseq_rank",split_column="global_family_v2_split",seed=20260804,epochs=20,batch_size=2048,learning_rate=2e-4,rank_loss_weight=.5,alpha=.4,cap=200000,deduplicate_biological=False):
    if not torch.cuda.is_available():raise RuntimeError("CUDA is required")
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    payload=torch.load(embeddings_path,map_location="cpu");embeddings=payload["embeddings"];lookup={s:i for i,s in enumerate(payload["sequences"])};zero_index=len(embeddings);embeddings=torch.cat([embeddings,torch.zeros((1,embeddings.shape[1]),dtype=embeddings.dtype)])
    rows=load_route(input_path,lookup,zero_index,route,split_column,deduplicate_biological);tr=[r for r in rows if r[6]=="train"];va=[r for r in rows if r[6]=="validation"]
    source_counts=Counter(r[5] for r in tr)
    sample=np.asarray([(min(source_counts[r[5]],cap)**alpha/source_counts[r[5]])*r[3] for r in tr],dtype=np.float64);sample/=sample.mean()
    def dataset(values):
        return TensorDataset(torch.tensor([r[0] for r in values]),torch.tensor([r[1] for r in values]),torch.tensor([r[2] for r in values],dtype=torch.float32),torch.tensor([r[3] for r in values],dtype=torch.float32),torch.tensor([r[4] for r in values]),torch.tensor([r[5] for r in values]),torch.arange(len(values)))
    generator=torch.Generator().manual_seed(seed);sampler=WeightedRandomSampler(torch.tensor(sample),len(tr),replacement=True,generator=generator)
    train_loader=DataLoader(dataset(tr),batch_size=batch_size,sampler=sampler,num_workers=2,pin_memory=True);val_loader=DataLoader(dataset(va),batch_size=batch_size*2,num_workers=2,pin_memory=True)
    device=torch.device("cuda");model=AntibodyEsmHead(embeddings.shape[1]*2).to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=learning_rate,weight_decay=1e-4);scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,max(epochs,1),eta_min=learning_rate*.03)
    best=-float("inf");best_state=None;history=[]
    for epoch in range(1,epochs+1):
        model.train();loss_sum=0.;count=0
        for heavy_idx,light_idx,labels,quality,groups,_,_ in train_loader:
            labels=labels.to(device);quality=quality.to(device);groups=groups.to(device);pair=torch.cat([embeddings[heavy_idx],embeddings[light_idx]],dim=1).to(device,dtype=torch.float32);scores=model(pair);reg=(nn.functional.smooth_l1_loss(scores,labels,reduction="none")*quality).mean()
            permutation=torch.arange(len(labels),device=device)
            for group in groups.unique():
                pos=(groups==group).nonzero(as_tuple=False).flatten()
                if len(pos)>1:permutation[pos]=pos.roll(1)
            delta=labels-labels[permutation];usable=(permutation!=torch.arange(len(labels),device=device))&(delta.abs()>1e-6)
            rank=(nn.functional.softplus(-delta[usable].sign()*(scores[usable]-scores[permutation][usable]))*delta[usable].abs().clamp_max(.5)).mean() if usable.any() else scores.sum()*0
            loss=reg+rank_loss_weight*rank;optimizer.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step();loss_sum+=float(loss)*len(labels);count+=len(labels)
        truth,pred,_=evaluate(model,embeddings,val_loader,device);rho=float(spearmanr(truth,pred).statistic);history.append({"epoch":epoch,"train_loss":loss_sum/count,"validation_spearman":rho,"learning_rate":optimizer.param_groups[0]["lr"]});print(json.dumps(history[-1]),flush=True)
        if rho>best:best=rho;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        scheduler.step()
    model.load_state_dict(best_state);truth,pred,indices=evaluate(model,embeddings,val_loader,device);metrics={"model":"esm150_antibody_only_ranker","route":route,"split_column":split_column,"deduplicate_biological":deduplicate_biological,"seed":seed,"train_records":len(tr),"validation_records":len(va),"best_validation_spearman":best,"overall":regression_metrics(truth,pred),"history":history}
    artifact_dir.mkdir(parents=True,exist_ok=True);torch.save({"state_dict":best_state,"metrics":metrics},artifact_dir/"model.pt");(artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(["record_id","source_file","truth","prediction"])
        for idx,y,p in zip(indices,truth,pred):w.writerow([va[idx][7],va[idx][8],y,p])
    return metrics


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--embeddings",type=Path,required=True);p.add_argument("--artifact-dir",type=Path,required=True);p.add_argument("--route",default="alphaseq_rank");p.add_argument("--split-column",default="global_family_v2_split");p.add_argument("--seed",type=int,default=20260804);p.add_argument("--epochs",type=int,default=20);p.add_argument("--batch-size",type=int,default=2048);p.add_argument("--learning-rate",type=float,default=2e-4);p.add_argument("--rank-loss-weight",type=float,default=.5);p.add_argument("--deduplicate-biological",action="store_true");a=p.parse_args();print(json.dumps(train(a.input,a.embeddings,a.artifact_dir,route=a.route,split_column=a.split_column,seed=a.seed,epochs=a.epochs,batch_size=a.batch_size,learning_rate=a.learning_rate,rank_loss_weight=a.rank_loss_weight,deduplicate_biological=a.deduplicate_biological),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
