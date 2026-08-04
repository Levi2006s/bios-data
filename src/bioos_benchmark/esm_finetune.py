"""Partially fine-tune the last ESM layer for antibody-antigen ranking."""

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
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer

from .esm_head import EsmInteractionHead
from .esm_embeddings import residue_mean_pool
from .metrics import regression_metrics
from .train import load_rows, split_rows


class RowDataset(Dataset):
    def __init__(self, rows: list[dict[str, str]]):
        self.rows=rows;counts=Counter(row["source_file"] for row in rows)
        raw=np.asarray([counts[row["source_file"]]**-0.5 for row in rows]);self.weights=raw/raw.mean()
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):return self.rows[index],float(self.weights[index]),index


def make_collate(tokenizer, max_antigen_length: int = 600, shared_antigen: bool = False):
    def collate(items):
        rows,weights,indices=zip(*items)
        def tokens(key,max_length):
            values=[row.get(key,"") or "X" for row in rows]
            return tokenizer(values,padding=True,truncation=True,max_length=max_length,return_tensors="pt")
        antigen=tokens("antigen_seq",max_antigen_length)
        if shared_antigen:
            antigen={key:value[:1] for key,value in antigen.items()}
        return tokens("heavy",180),tokens("light",160),antigen,torch.tensor([float(row["score"]) for row in rows]),torch.tensor(weights),torch.tensor(indices)
    return collate


class FineTunedEsmRanker(nn.Module):
    def __init__(self, esm: nn.Module, head: EsmInteractionHead, special_token_ids: tuple[int | None, ...]):super().__init__();self.esm=esm;self.head=head;self.special_token_ids=special_token_ids
    def pool(self,batch):
        hidden=self.esm(**batch).last_hidden_state
        return residue_mean_pool(hidden,batch,self.special_token_ids)
    def forward(self,heavy,light,antigen):
        heavy_embedding=self.pool(heavy);antigen_embedding=self.pool(antigen)
        if len(antigen_embedding)==1 and len(heavy_embedding)>1:antigen_embedding=antigen_embedding.expand(len(heavy_embedding),-1)
        return self.head(heavy_embedding,self.pool(light),antigen_embedding)


def to_device(batch,device):return {key:value.to(device,non_blocking=True) for key,value in batch.items()}


def make_grad_scaler():
    """Create a CUDA scaler across both old and new PyTorch AMP APIs."""
    if hasattr(torch.amp, "GradScaler"):
        return torch.amp.GradScaler("cuda")
    return torch.cuda.amp.GradScaler()


@torch.no_grad()
def evaluate(model,loader,device):
    model.eval();truth=[];prediction=[];indices=[]
    for heavy,light,antigen,labels,_,idx in loader:
        with torch.autocast("cuda",dtype=torch.float16):scores=model(to_device(heavy,device),to_device(light,device),to_device(antigen,device))
        truth.extend(labels.numpy());prediction.extend(scores.float().cpu().numpy());indices.extend(idx.numpy())
    return np.asarray(truth),np.asarray(prediction),[int(x) for x in indices]


def train_finetune(input_path:Path,model_path:Path,head_checkpoint:Path,artifact_dir:Path,*,seed:int=42,epochs:int=4,batch_size:int=16,head_lr:float=1e-4,esm_lr:float=1e-5,pooling:str="attention_mean",max_rows_per_source:int=50_000,rank_loss_weight:float=0.0,shared_antigen:bool=False):
    if not torch.cuda.is_available():raise RuntimeError("CUDA is required")
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    rows=load_rows(input_path,max_rows_per_source,20260803,{"Gold","Silver"});train_rows,val_rows=split_rows(rows,20,"framework_family_split","train","validation")
    train_rows=[r for r in train_rows if r.get("antigen_seq")];val_rows=[r for r in val_rows if r.get("antigen_seq")]
    tokenizer=AutoTokenizer.from_pretrained(model_path,local_files_only=True);esm=AutoModel.from_pretrained(model_path,local_files_only=True,use_safetensors=True)
    for parameter in esm.parameters():parameter.requires_grad=False
    for parameter in esm.encoder.layer[-1].parameters():parameter.requires_grad=True
    head=EsmInteractionHead(input_dim=esm.config.hidden_size);head.load_state_dict(torch.load(head_checkpoint,map_location="cpu")["state_dict"])
    if pooling=="residue_mean":special_ids=(tokenizer.cls_token_id,tokenizer.eos_token_id,tokenizer.pad_token_id)
    elif pooling=="attention_mean":special_ids=()
    else:raise ValueError(f"unknown pooling mode: {pooling}")
    device=torch.device("cuda");model=FineTunedEsmRanker(esm,head,special_ids).to(device)
    if shared_antigen and len({row["antigen_seq"] for row in train_rows+val_rows})!=1:raise ValueError("shared_antigen requires exactly one antigen sequence")
    collate=make_collate(tokenizer,shared_antigen=shared_antigen);generator=torch.Generator().manual_seed(seed)
    train_loader=DataLoader(RowDataset(train_rows),batch_size=batch_size,shuffle=True,generator=generator,collate_fn=collate,num_workers=2,pin_memory=True)
    val_loader=DataLoader(RowDataset(val_rows),batch_size=batch_size*2,collate_fn=collate,num_workers=2,pin_memory=True)
    optimizer=torch.optim.AdamW([{"params":head.parameters(),"lr":head_lr},{"params":esm.encoder.layer[-1].parameters(),"lr":esm_lr}],weight_decay=1e-4)
    scaler=make_grad_scaler();best=-float("inf");best_state=None;history=[]
    for epoch in range(1,epochs+1):
        model.train();loss_sum=0.;count=0
        for heavy,light,antigen,labels,weights,_ in train_loader:
            optimizer.zero_grad(set_to_none=True);labels=labels.to(device);weights=weights.to(device)
            with torch.autocast("cuda",dtype=torch.float16):
                scores=model(to_device(heavy,device),to_device(light,device),to_device(antigen,device));regression_loss=(nn.functional.smooth_l1_loss(scores,labels,reduction="none")*weights).mean()
                if rank_loss_weight>0:
                    permutation=torch.randperm(len(labels),device=device);delta=labels-labels[permutation];usable=delta.abs()>1e-6
                    margin=delta[usable].sign()*(scores[usable]-scores[permutation][usable]);loss=regression_loss+rank_loss_weight*nn.functional.softplus(-margin).mean()
                else:loss=regression_loss
            scaler.scale(loss).backward();scaler.unscale_(optimizer);nn.utils.clip_grad_norm_(model.parameters(),1.0);scaler.step(optimizer);scaler.update()
            loss_sum+=float(loss)*len(labels);count+=len(labels)
        truth,prediction,_=evaluate(model,val_loader,device);rho=float(spearmanr(truth,prediction).statistic)
        history.append({"epoch":epoch,"train_loss":loss_sum/count,"validation_spearman":rho});print(json.dumps(history[-1]),flush=True)
        if rho>best:best=rho;best_state={key:value.detach().cpu().clone() for key,value in model.state_dict().items()}
    model.load_state_dict(best_state);truth,prediction,indices=evaluate(model,val_loader,device)
    metrics={"model":"esm_last_layer_finetune","seed":seed,"epochs":epochs,"head_lr":head_lr,"esm_lr":esm_lr,"pooling":pooling,"max_rows_per_source":max_rows_per_source,"rank_loss_weight":rank_loss_weight,"shared_antigen":shared_antigen,"train_records":len(train_rows),"validation_records":len(val_rows),"best_validation_spearman":best,"overall":regression_metrics(truth,prediction),"history":history}
    artifact_dir.mkdir(parents=True,exist_ok=True);torch.save({"state_dict":best_state,"metrics":metrics},artifact_dir/"model.pt");(artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf8",newline="") as handle:
        writer=csv.writer(handle);writer.writerow(["record_id","source_file","truth","prediction"])
        for idx,y,score in zip(indices,truth,prediction):row=val_rows[idx];writer.writerow([row["record_id"],row["source_file"],y,score])
    return metrics


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--model",type=Path,required=True);p.add_argument("--head-checkpoint",type=Path,required=True);p.add_argument("--artifact-dir",type=Path,required=True);p.add_argument("--seed",type=int,default=42);p.add_argument("--epochs",type=int,default=4);p.add_argument("--batch-size",type=int,default=16);p.add_argument("--head-lr",type=float,default=1e-4);p.add_argument("--esm-lr",type=float,default=1e-5);p.add_argument("--pooling",choices=("attention_mean","residue_mean"),default="attention_mean");p.add_argument("--max-rows-per-source",type=int,default=50_000);p.add_argument("--rank-loss-weight",type=float,default=0.0);p.add_argument("--shared-antigen",action="store_true");a=p.parse_args();print(json.dumps(train_finetune(a.input,a.model,a.head_checkpoint,a.artifact_dir,seed=a.seed,epochs=a.epochs,batch_size=a.batch_size,head_lr=a.head_lr,esm_lr=a.esm_lr,pooling=a.pooling,max_rows_per_source=a.max_rows_per_source,rank_loss_weight=a.rank_loss_weight,shared_antigen=a.shared_antigen),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
