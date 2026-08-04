"""Position-preserving neural ranker for aligned mutational landscapes."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
import joblib
import torch
from scipy.stats import spearmanr
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .metrics import regression_metrics

AA = {aa: i + 1 for i, aa in enumerate("ACDEFGHIKLMNPQRSTVWY")}


class PositionalInteractionNet(nn.Module):
    def __init__(self, length: int, embedding_dim: int = 16, channels: int = 48, dropout: float = .2, num_assays: int = 0, parent_reference_delta: bool = False):
        super().__init__();self.embedding=nn.Embedding(len(AA)+1,embedding_dim,padding_idx=0)
        self.delta_embedding=nn.Embedding((len(AA)+1)**2+1,embedding_dim,padding_idx=0) if parent_reference_delta else None
        self.assay_embedding=nn.Embedding(num_assays,32) if num_assays else None
        self.local=nn.Sequential(
            nn.Conv1d(embedding_dim*(2 if parent_reference_delta else 1),channels,3,padding=1),nn.GELU(),
            nn.Conv1d(channels,channels,5,padding=2),nn.GELU(),
        )
        self.flatten=nn.Flatten();self.head=nn.Sequential(nn.Linear(length*channels+(32 if num_assays else 0),384),nn.GELU(),nn.Dropout(dropout),nn.Linear(384,96),nn.GELU(),nn.Dropout(dropout),nn.Linear(96,1))
    def forward(self,tokens:torch.Tensor,assays:torch.Tensor|None=None,deltas:torch.Tensor|None=None)->torch.Tensor:
        embedded=self.embedding(tokens)
        if self.delta_embedding is not None:
            if deltas is None:raise ValueError("parent-reference delta tokens are required")
            embedded=torch.cat([embedded,self.delta_embedding(deltas)],dim=2)
        features=self.flatten(self.local(embedded.transpose(1,2)))
        if self.assay_embedding is not None:
            if assays is None:raise ValueError("assay ids are required")
            features=torch.cat([features,self.assay_embedding(assays)],dim=1)
        return self.head(features).squeeze(1)


def encode(rows:list[dict[str,str]],heavy_length:int,light_length:int)->torch.Tensor:
    values=[]
    for row in rows:
        sequence=row["heavy"].ljust(heavy_length,"-")[:heavy_length]+row.get("light","").ljust(light_length,"-")[:light_length]
        values.append([AA.get(aa,0) for aa in sequence])
    return torch.tensor(values,dtype=torch.long)


def encode_parent_delta(rows:list[dict[str,str]],heavy_length:int,light_length:int,parent_assignments,references)->torch.Tensor:
    values=[];alphabet=len(AA)+1
    for row in rows:
        key=row["heavy"]+"\x1f"+row.get("light","");reference=references[parent_assignments[key]]
        sequence=row["heavy"].ljust(heavy_length,"-")[:heavy_length]+row.get("light","").ljust(light_length,"-")[:light_length]
        parent=reference["heavy"].ljust(heavy_length,"-")[:heavy_length]+reference["light"].ljust(light_length,"-")[:light_length]
        values.append([0 if current==origin else 1+AA.get(origin,0)*alphabet+AA.get(current,0) for origin,current in zip(parent,sequence)])
    return torch.tensor(values,dtype=torch.long)


@torch.no_grad()
def predict(model,loader,device):
    model.eval();truth=[];scores=[];indices=[]
    for x,deltas,y,_,assays,i in loader:scores.extend(model(x.to(device),assays.to(device),deltas.to(device)).cpu().numpy());truth.extend(y.numpy());indices.extend(i.numpy())
    return np.asarray(truth),np.asarray(scores),np.asarray(indices)


def train(input_path:Path,artifact_dir:Path,*,seed:int=48,epochs:int=100,batch_size:int=512,learning_rate:float=3e-4,rank_weight:float=.04,split_column:str="framework_family_split",task_route:str|None=None,deduplicate_biological:bool=False,aggregate_train_sequences:bool=False,aggregate_repeat_power:float=0.0,condition_on_lengths:bool=False,parent_clusters_path:Path|None=None,heavy_length:int|None=None,light_length:int|None=None,pretrained_checkpoint:Path|None=None,freeze_backbone:bool=False,parent_reference_delta:bool=False)->dict[str,object]:
    if not torch.cuda.is_available():raise RuntimeError("CUDA is required")
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    rows=[];seen=set()
    with input_path.open(encoding="utf-8",newline="") as handle:
        for r in csv.DictReader(handle):
            if r.get(split_column) not in {"train","validation"} or (task_route and r.get("task_route")!=task_route):continue
            if heavy_length is not None and len(r["heavy"]) != heavy_length:continue
            if light_length is not None and len(r.get("light", "")) != light_length:continue
            key=(r["heavy"],r.get("light",""),r["score"],r[split_column])
            if deduplicate_biological and key in seen:continue
            seen.add(key);rows.append(r)
    def assay_name(source):return "alpha_landscape_1" if ("engelhart2022dataset" in source or "affinity1.csv" in source) else ("alpha_landscape_2" if "affinity2.csv" in source else source)
    parent_payload=joblib.load(parent_clusters_path) if parent_clusters_path else None;parent_assignments=parent_payload["assignments"] if parent_payload else None;parent_references=parent_payload.get("references") if parent_payload else None
    if parent_reference_delta and not parent_references:raise ValueError("parent cluster artifact does not contain reference consensuses")
    def parent_name(r):return parent_assignments[r["heavy"]+"\x1f"+r.get("light","")] if parent_assignments is not None else None
    def condition_name(r):
        base=assay_name(r["source_file"])
        if parent_assignments is not None:return parent_name(r)
        return f"{base}|H{len(r['heavy'])}|L{len(r.get('light',''))}" if condition_on_lengths else base
    def comparison_name(r):
        base=r.get("comparison_group") or assay_name(r["source_file"])
        if parent_assignments is not None:return parent_name(r)
        return f"{base}|H{len(r['heavy'])}|L{len(r.get('light',''))}" if condition_on_lengths else base
    tr=[r for r in rows if r[split_column]=="train"];va=[r for r in rows if r[split_column]=="validation"]
    raw_train_records=len(tr)
    if aggregate_train_sequences:
        grouped=defaultdict(list);representatives={}
        for r in tr:
            key=(assay_name(r["source_file"]),r["heavy"],r.get("light",""));grouped[key].append(float(r["score"]));representatives.setdefault(key,r)
        aggregated=[]
        for key,values in grouped.items():
            row=dict(representatives[key]);row["score"]=str(float(np.mean(values)));row["comparison_group"]=key[0]
            repeats=max(1,int(round(len(values)**aggregate_repeat_power)))
            aggregated.extend(dict(row) for _ in range(repeats))
        tr=aggregated
    assay_names=sorted({condition_name(r) for r in rows});assay_ids={name:i for i,name in enumerate(assay_names)};group_names=sorted({comparison_name(r) for r in rows}|set(assay_names));group_ids={name:i for i,name in enumerate(group_names)}
    lh=max(len(r["heavy"]) for r in rows);ll=max(len(r.get("light","")) for r in rows)
    def tensors(values):
        delta=encode_parent_delta(values,lh,ll,parent_assignments,parent_references) if parent_reference_delta else torch.zeros((len(values),lh+ll),dtype=torch.long)
        return TensorDataset(encode(values,lh,ll),delta,torch.tensor([float(r["score"]) for r in values],dtype=torch.float32),torch.tensor([group_ids[comparison_name(r)] for r in values]),torch.tensor([assay_ids[condition_name(r)] for r in values]),torch.arange(len(values)))
    generator=torch.Generator().manual_seed(seed);train_loader=DataLoader(tensors(tr),batch_size=batch_size,shuffle=True,generator=generator,pin_memory=True);val_loader=DataLoader(tensors(va),batch_size=batch_size*2,pin_memory=True)
    device=torch.device("cuda");model=PositionalInteractionNet(lh+ll,num_assays=len(assay_ids),parent_reference_delta=parent_reference_delta).to(device)
    loaded_parameters=[]
    if pretrained_checkpoint is not None:
        checkpoint=torch.load(pretrained_checkpoint,map_location="cpu",weights_only=False);source_state=checkpoint["state_dict"];target_state=model.state_dict()
        for name,value in source_state.items():
            if name=="assay_embedding.weight":continue
            if name in target_state and target_state[name].shape==value.shape:target_state[name]=value;loaded_parameters.append(name)
        source_assays=checkpoint.get("metrics",{}).get("assays",{})
        if "assay_embedding.weight" in source_state:
            for condition,target_id in assay_ids.items():
                if condition in source_assays:target_state["assay_embedding.weight"][target_id]=source_state["assay_embedding.weight"][source_assays[condition]]
            loaded_parameters.append("assay_embedding.weight(mapped)")
        model.load_state_dict(target_state)
    if freeze_backbone:
        for module in (model.embedding,model.local):
            for parameter in module.parameters():parameter.requires_grad=False
    optimizer=torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),lr=learning_rate,weight_decay=2e-4);scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=epochs,eta_min=learning_rate*.02)
    best=-float("inf");best_state=None;history=[];stale=0
    for epoch in range(1,epochs+1):
        model.train();total=0.;count=0
        for x,deltas,y,groups,assays,_ in train_loader:
            x=x.to(device);deltas=deltas.to(device);y=y.to(device);groups=groups.to(device);assays=assays.to(device);optimizer.zero_grad(set_to_none=True);scores=model(x,assays,deltas);reg=nn.functional.smooth_l1_loss(scores,y)
            permutation=torch.arange(len(y),device=device)
            for group in groups.unique():
                positions=(groups==group).nonzero(as_tuple=False).flatten()
                if len(positions)>1:permutation[positions]=positions.roll(1)
            delta=y-y[permutation];usable=(permutation!=torch.arange(len(y),device=device))&(delta.abs()>1e-6);margin=delta[usable].sign()*(scores[usable]-scores[permutation][usable]);rank=nn.functional.softplus(-margin).mean() if usable.any() else scores.sum()*0;loss=reg+rank_weight*rank
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step();total+=float(loss)*len(y);count+=len(y)
        truth,prediction,_=predict(model,val_loader,device);rho=float(spearmanr(truth,prediction).statistic);history.append({"epoch":epoch,"loss":total/count,"validation_spearman":rho,"learning_rate":optimizer.param_groups[0]["lr"]});print(json.dumps(history[-1]),flush=True)
        if rho>best:best=rho;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};stale=0
        else:stale+=1
        scheduler.step()
        if stale>=15:break
    assert best_state is not None;model.load_state_dict(best_state);truth,prediction,indices=predict(model,val_loader,device)
    metrics={"model":"position_preserving_conv_ranker","seed":seed,"epochs_completed":len(history),"rank_weight":rank_weight,"split_column":split_column,"task_route":task_route,"deduplicate_biological":deduplicate_biological,"aggregate_train_sequences":aggregate_train_sequences,"aggregate_repeat_power":aggregate_repeat_power,"condition_on_lengths":condition_on_lengths,"parent_clusters_path":str(parent_clusters_path) if parent_clusters_path else None,"parent_reference_delta":parent_reference_delta,"heavy_length_filter":heavy_length,"light_length_filter":light_length,"pretrained_checkpoint":str(pretrained_checkpoint) if pretrained_checkpoint else None,"freeze_backbone":freeze_backbone,"loaded_parameters":loaded_parameters,"raw_train_records":raw_train_records,"assays":assay_ids,"train_records":len(tr),"validation_records":len(va),"best_validation_spearman":best,"overall":regression_metrics(truth,prediction),"history":history}
    artifact_dir.mkdir(parents=True,exist_ok=True);torch.save({"state_dict":best_state,"heavy_length":lh,"light_length":ll,"metrics":metrics},artifact_dir/"model.pt");(artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.writer(handle);writer.writerow(["record_id","source_file","truth","prediction"])
        for i,y,p in zip(indices,truth,prediction):writer.writerow([va[int(i)]["record_id"],va[int(i)]["source_file"],y,p])
    return metrics


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--artifact-dir",type=Path,required=True);p.add_argument("--seed",type=int,default=48);p.add_argument("--epochs",type=int,default=100);p.add_argument("--batch-size",type=int,default=512);p.add_argument("--learning-rate",type=float,default=3e-4);p.add_argument("--rank-weight",type=float,default=.04);p.add_argument("--split-column",default="framework_family_split");p.add_argument("--task-route");p.add_argument("--deduplicate-biological",action="store_true");p.add_argument("--aggregate-train-sequences",action="store_true");p.add_argument("--aggregate-repeat-power",type=float,default=0.0);p.add_argument("--condition-on-lengths",action="store_true");p.add_argument("--parent-clusters",type=Path);p.add_argument("--parent-reference-delta",action="store_true");p.add_argument("--heavy-length",type=int);p.add_argument("--light-length",type=int);p.add_argument("--pretrained-checkpoint",type=Path);p.add_argument("--freeze-backbone",action="store_true");a=p.parse_args();print(json.dumps(train(a.input,a.artifact_dir,seed=a.seed,epochs=a.epochs,batch_size=a.batch_size,learning_rate=a.learning_rate,rank_weight=a.rank_weight,split_column=a.split_column,task_route=a.task_route,deduplicate_biological=a.deduplicate_biological,aggregate_train_sequences=a.aggregate_train_sequences,aggregate_repeat_power=a.aggregate_repeat_power,condition_on_lengths=a.condition_on_lengths,parent_clusters_path=a.parent_clusters,heavy_length=a.heavy_length,light_length=a.light_length,pretrained_checkpoint=a.pretrained_checkpoint,freeze_backbone=a.freeze_backbone,parent_reference_delta=a.parent_reference_delta),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
