"""Parent-cluster routed positional model for AlphaSeq landscapes."""

from __future__ import annotations

import argparse,csv,json
from pathlib import Path
import joblib,numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import OneHotEncoder
from .data import normalize_sequence
from .metrics import regression_metrics

def key(h,l,a):return normalize_sequence(h),normalize_sequence(l),normalize_sequence(a)
def matrix(rows,lh,ll):return np.asarray([list(r["heavy"].ljust(lh,"-")[:lh]+r.get("light","").ljust(ll,"-")[:ll]) for r in rows])

def train(input_path:Path,abrank_path:Path,artifact_dir:Path,alpha:float=10.0):
    clusters={}
    with abrank_path.open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("Source","").strip()=="AlphaSeq":clusters[key(r["Ab_heavy_chain_seq"],r["Ab_light_chain_seq"],r["Ag_seq"])]=r["Ab10_cluster"]
    with input_path.open(encoding="utf-8",newline="") as f:rows=[r for r in csv.DictReader(f) if r.get("framework_family_split") in {"train","validation"}]
    for r in rows:r["parent_cluster"]=clusters[key(r["heavy"],r["light"],r["antigen_seq"])]
    lh=max(len(r["heavy"]) for r in rows);ll=max(len(r.get("light","")) for r in rows);models={};outputs=[]
    for cluster in sorted({r["parent_cluster"] for r in rows}):
        tr=[r for r in rows if r["parent_cluster"]==cluster and r["framework_family_split"]=="train"];va=[r for r in rows if r["parent_cluster"]==cluster and r["framework_family_split"]=="validation"]
        encoder=OneHotEncoder(handle_unknown="ignore",sparse_output=True,dtype=np.float32);x=encoder.fit_transform(matrix(tr,lh,ll));v=encoder.transform(matrix(va,lh,ll));model=Ridge(alpha=alpha,solver="lsqr").fit(x,[float(r["score"]) for r in tr]);prediction=model.predict(v);models[cluster]={"encoder":encoder,"model":model};outputs.extend((r,float(r["score"]),float(p)) for r,p in zip(va,prediction))
    truth=np.asarray([x[1] for x in outputs]);prediction=np.asarray([x[2] for x in outputs]);metrics={"model":"parent_cluster_positional_ridge","alpha":alpha,"clusters":len(models),"validation_records":len(outputs),"overall":regression_metrics(truth,prediction),"spearman":float(spearmanr(truth,prediction).statistic)}
    artifact_dir.mkdir(parents=True,exist_ok=True);joblib.dump({"models":models,"heavy_length":lh,"light_length":ll},artifact_dir/"model.joblib");(artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(["record_id","source_file","truth","prediction"])
        for r,y,p in outputs:w.writerow([r["record_id"],r["source_file"],y,p])
    return metrics

def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--abrank",type=Path,required=True);p.add_argument("--artifact-dir",type=Path,required=True);p.add_argument("--alpha",type=float,default=10);a=p.parse_args();print(json.dumps(train(a.input,a.abrank,a.artifact_dir,a.alpha),ensure_ascii=False,indent=2))
if __name__=="__main__":main()
