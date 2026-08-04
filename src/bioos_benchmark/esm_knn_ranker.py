"""Exact GPU cosine-kNN over frozen ESM embeddings, with train-only indices."""

from __future__ import annotations

import argparse,csv,json
from collections import defaultdict
from pathlib import Path
import numpy as np,torch
from scipy.stats import spearmanr
from .metrics import regression_metrics


def canonical_source(source:str)->str:
    if "engelhart2022dataset" in source:return "alpha_landscape_1"
    if "affinity1.csv" in source:return "alpha_landscape_1"
    if "affinity2.csv" in source:return "alpha_landscape_2"
    return source


def train(input_path:Path,embeddings_path:Path,artifact_dir:Path,*,split_column="global_family_v2_split",route="alphaseq_rank",neighbors=32,batch_size=512,temperature=.05):
    if not torch.cuda.is_available():raise RuntimeError("CUDA is required")
    payload=torch.load(embeddings_path,map_location="cpu");embeddings=payload["embeddings"].float();lookup={s:i for i,s in enumerate(payload["sequences"])}
    train_scores=defaultdict(lambda:defaultdict(list));validation={}
    with input_path.open(encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("task_route")!=route:continue
            source=canonical_source(r["source_file"]);sequence=r["heavy"]
            if r.get(split_column)=="train":train_scores[source][sequence].append(float(r["score"]))
            elif r.get(split_column)=="validation":
                key=(source,sequence,r["score"]);validation.setdefault(key,r)
    device=torch.device("cuda");outputs=[];source_metrics={}
    for source in sorted({k[0] for k in validation}):
        train_sequences=sorted(train_scores[source]);labels=torch.tensor([np.mean(train_scores[source][s]) for s in train_sequences],device=device)
        train_vectors=torch.nn.functional.normalize(embeddings[[lookup[s] for s in train_sequences]].to(device),dim=1)
        values=[(k,r) for k,r in validation.items() if k[0]==source];truth=[];prediction=[]
        for start in range(0,len(values),batch_size):
            chunk=values[start:start+batch_size];query=torch.nn.functional.normalize(embeddings[[lookup[k[1]] for k,_ in chunk]].to(device),dim=1);similarity=query@train_vectors.T;top=similarity.topk(min(neighbors,len(train_sequences)),dim=1);weights=torch.softmax(top.values/temperature,dim=1);pred=(weights*labels[top.indices]).sum(1).cpu().numpy()
            for (key,row),score in zip(chunk,pred):truth.append(float(key[2]));prediction.append(float(score));outputs.append((row,float(key[2]),float(score)))
        source_metrics[source]={"train_unique":len(train_sequences),"validation_unique":len(values),"spearman":float(spearmanr(truth,prediction).statistic),"overall":regression_metrics(np.asarray(truth),np.asarray(prediction))}
        del train_vectors;torch.cuda.empty_cache()
    truth=np.asarray([x[1] for x in outputs]);prediction=np.asarray([x[2] for x in outputs]);metrics={"model":"esm150_exact_cosine_knn","split_column":split_column,"route":route,"neighbors":neighbors,"temperature":temperature,"sources":source_metrics,"overall":regression_metrics(truth,prediction),"spearman":float(spearmanr(truth,prediction).statistic)}
    artifact_dir.mkdir(parents=True,exist_ok=True);(artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(["record_id","source_file","truth","prediction"])
        for r,y,p in outputs:w.writerow([r["record_id"],r["source_file"],y,p])
    return metrics


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--embeddings",type=Path,required=True);p.add_argument("--artifact-dir",type=Path,required=True);p.add_argument("--split-column",default="global_family_v2_split");p.add_argument("--neighbors",type=int,default=32);p.add_argument("--batch-size",type=int,default=512);p.add_argument("--temperature",type=float,default=.05);a=p.parse_args();print(json.dumps(train(a.input,a.embeddings,a.artifact_dir,split_column=a.split_column,neighbors=a.neighbors,batch_size=a.batch_size,temperature=a.temperature),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
