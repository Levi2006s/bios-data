"""Group-safe pairwise fine-tuning over frozen ESM sequence embeddings."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .esm_head import EsmInteractionHead, evaluate, row_tensors
from .metrics import regression_metrics
from .train import load_rows, split_rows


def build_pairs(rows:list[dict[str,str]],*,minimum_gap:float=.1,offsets:tuple[float,...]=(.05,.25,.5,1.0),max_pairs_per_group:int=4096,seed:int=20260803)->list[tuple[int,int]]:
    grouped=defaultdict(list)
    for index,row in enumerate(rows):grouped[row["comparison_group"]].append(index)
    pairs=[];rng=random.Random(seed)
    for indices in grouped.values():
        group_pairs=set();ordered=sorted(indices,key=lambda index:float(rows[index]["score"]));n=len(ordered)
        for position,left in enumerate(ordered[:-1]):
            for fraction in offsets:
                step=max(1,round((n-1)*fraction));target=min(n-1,position+step)
                right=ordered[target]
                if float(rows[right]["score"])-float(rows[left]["score"])>=minimum_gap:group_pairs.add((right,left))
        group_pairs=sorted(group_pairs)
        if max_pairs_per_group>0 and len(group_pairs)>max_pairs_per_group:group_pairs=rng.sample(group_pairs,max_pairs_per_group)
        pairs.extend(group_pairs)
    return sorted(pairs)


def macro_group_spearman(rows:list[dict[str,str]],truth:np.ndarray,prediction:np.ndarray,minimum_size:int=5)->dict[str,float|int]:
    grouped=defaultdict(list)
    for index,row in enumerate(rows):grouped[row["comparison_group"]].append(index)
    values=[];weighted=[]
    for indices in grouped.values():
        if len(indices)<minimum_size:continue
        idx=np.asarray(indices);rho=float(spearmanr(truth[idx],prediction[idx]).statistic)
        if np.isfinite(rho):values.append(rho);weighted.extend([rho]*len(indices))
    return {"groups":len(values),"macro_spearman":float(np.mean(values)) if values else float("nan"),"median_spearman":float(np.median(values)) if values else float("nan"),"record_weighted_spearman":float(np.mean(weighted)) if weighted else float("nan")}


def train_pairwise(input_path:Path,embeddings_path:Path,checkpoint:Path,artifact_dir:Path,*,seed:int=20260803,epochs:int=20,batch_size:int=1024,learning_rate:float=1e-4,include_metrics:set[str]|None=None,max_pairs_per_group:int=4096,anchor_weight:float=0.0):
    if not torch.cuda.is_available():raise RuntimeError("CUDA is required")
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    payload=torch.load(embeddings_path,map_location="cpu");lookup={s:e for s,e in zip(payload["sequences"],payload["embeddings"])}
    rows=load_rows(input_path,50_000,20260803,{"Gold","Silver"});train_rows,val_rows=split_rows(rows,20,"framework_family_split","train","validation")
    def usable(row):return row.get("antigen_seq") in lookup and row["heavy"] in lookup
    train_rows=[row for row in train_rows if usable(row)];val_rows=[row for row in val_rows if usable(row)]
    if include_metrics:
        train_rows=[row for row in train_rows if row.get("metric") in include_metrics];val_rows=[row for row in val_rows if row.get("metric") in include_metrics]
    train_tensors=row_tensors(train_rows,lookup);val_tensors=row_tensors(val_rows,lookup)
    pairs=build_pairs(train_rows,max_pairs_per_group=max_pairs_per_group,seed=seed);pair_tensor=torch.tensor(pairs,dtype=torch.long)
    loader=DataLoader(TensorDataset(pair_tensor),batch_size=batch_size,shuffle=True,generator=torch.Generator().manual_seed(seed),pin_memory=True)
    val_loader=DataLoader(TensorDataset(*val_tensors,torch.arange(len(val_rows))),batch_size=batch_size*2,pin_memory=True)
    model=EsmInteractionHead(input_dim=train_tensors[0].shape[1]);model.load_state_dict(torch.load(checkpoint,map_location="cpu")["state_dict"]);device=torch.device("cuda");model=model.to(device)
    features=[tensor.to(device) for tensor in train_tensors[:3]];optimizer=torch.optim.AdamW(model.parameters(),lr=learning_rate,weight_decay=1e-4)
    model.eval()
    with torch.no_grad():teacher=model(features[0],features[1],features[2]).detach()
    best=-float("inf");best_state=None;history=[];stale=0
    for epoch in range(1,epochs+1):
        model.train();loss_sum=0.;count=0
        for (indices,) in loader:
            indices=indices.to(device);high=indices[:,0];low=indices[:,1];optimizer.zero_grad(set_to_none=True)
            high_score=model(features[0][high],features[1][high],features[2][high]);low_score=model(features[0][low],features[1][low],features[2][low])
            difference=high_score-low_score;loss=nn.functional.softplus(-difference).mean()
            if anchor_weight>0:loss=loss+anchor_weight*nn.functional.mse_loss(difference,teacher[high]-teacher[low])
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step();loss_sum+=float(loss)*len(indices);count+=len(indices)
        truth,prediction,_=evaluate(model,val_loader,device);macro=macro_group_spearman(val_rows,truth,prediction);selection=float(macro["macro_spearman"])
        item={"epoch":epoch,"pairwise_loss":loss_sum/count,"validation":macro,"global_spearman":float(spearmanr(truth,prediction).statistic)};history.append(item);print(json.dumps(item),flush=True)
        if selection>best:best=selection;best_state={key:value.detach().cpu().clone() for key,value in model.state_dict().items()};stale=0
        else:stale+=1
        if stale>=6:break
    model.load_state_dict(best_state);truth,prediction,indices=evaluate(model,val_loader,device);group_metrics=macro_group_spearman(val_rows,truth,prediction)
    metrics={"model":"frozen_esm_group_pairwise","seed":seed,"pairs":len(pairs),"max_pairs_per_group":max_pairs_per_group,"anchor_weight":anchor_weight,"include_metrics":sorted(include_metrics) if include_metrics else None,"train_records":len(train_rows),"validation_records":len(val_rows),"selection_metric":"macro_comparison_group_spearman_min_n_5","group_metrics":group_metrics,"overall":regression_metrics(truth,prediction),"history":history}
    artifact_dir.mkdir(parents=True,exist_ok=True);torch.save({"state_dict":best_state,"metrics":metrics},artifact_dir/"model.pt");(artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf8",newline="") as handle:
        writer=csv.writer(handle);writer.writerow(["record_id","source_file","comparison_group","truth","prediction"])
        for idx,y,pred in zip(indices,truth,prediction):row=val_rows[idx];writer.writerow([row["record_id"],row["source_file"],row["comparison_group"],y,pred])
    return metrics


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--embeddings",type=Path,required=True);p.add_argument("--checkpoint",type=Path,required=True);p.add_argument("--artifact-dir",type=Path,required=True);p.add_argument("--seed",type=int,default=20260803);p.add_argument("--epochs",type=int,default=20);p.add_argument("--batch-size",type=int,default=1024);p.add_argument("--learning-rate",type=float,default=1e-4);p.add_argument("--include-metrics",nargs="*");p.add_argument("--max-pairs-per-group",type=int,default=4096);p.add_argument("--anchor-weight",type=float,default=0.0);a=p.parse_args();print(json.dumps(train_pairwise(a.input,a.embeddings,a.checkpoint,a.artifact_dir,seed=a.seed,epochs=a.epochs,batch_size=a.batch_size,learning_rate=a.learning_rate,include_metrics=set(a.include_metrics) if a.include_metrics else None,max_pairs_per_group=a.max_pairs_per_group,anchor_weight=a.anchor_weight),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
