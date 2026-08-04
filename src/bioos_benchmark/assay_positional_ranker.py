"""Per-assay aligned positional experts on a shared leakage-safe split."""

from __future__ import annotations

import argparse, csv, json
from pathlib import Path

import joblib
import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import OneHotEncoder

from .metrics import regression_metrics
from .positional_ranker import sequence_matrix


def train(input_path:Path,artifact_dir:Path,*,split_column="global_family_v2_split",task_route="alphaseq_rank",alpha=10.0):
    by_source={}
    with input_path.open(encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            if row.get("task_route")==task_route and row.get(split_column) in {"train","validation"}:
                by_source.setdefault(row["source_file"],[]).append(row)
    models={};outputs=[];source_metrics={}
    for source,rows in sorted(by_source.items()):
        tr=[r for r in rows if r[split_column]=="train"];va=[r for r in rows if r[split_column]=="validation"]
        if not tr or not va:continue
        lh=max(len(r["heavy"]) for r in rows);ll=max(len(r.get("light","")) for r in rows)
        encoder=OneHotEncoder(handle_unknown="ignore",sparse_output=True,dtype=np.float32)
        x=encoder.fit_transform(sequence_matrix(tr,lh,ll));v=encoder.transform(sequence_matrix(va,lh,ll))
        model=Ridge(alpha=alpha,solver="lsqr").fit(x,np.asarray([float(r["score"]) for r in tr]));pred=model.predict(v);truth=np.asarray([float(r["score"]) for r in va])
        source_metrics[source]={"train_records":len(tr),"validation_records":len(va),"spearman":float(spearmanr(truth,pred).statistic),"overall":regression_metrics(truth,pred)}
        models[source]={"encoder":encoder,"model":model,"heavy_length":lh,"light_length":ll}
        outputs.extend((r,float(y),float(p)) for r,y,p in zip(va,truth,pred))
    truth=np.asarray([o[1] for o in outputs]);pred=np.asarray([o[2] for o in outputs]);metrics={"model":"per_assay_positional_ridge","split_column":split_column,"task_route":task_route,"alpha":alpha,"sources":source_metrics,"overall":regression_metrics(truth,pred),"spearman":float(spearmanr(truth,pred).statistic)}
    artifact_dir.mkdir(parents=True,exist_ok=True);joblib.dump(models,artifact_dir/"model.joblib");(artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(["record_id","source_file","truth","prediction"])
        for r,y,p in outputs:w.writerow([r["record_id"],r["source_file"],y,p])
    return metrics


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--artifact-dir",type=Path,required=True);p.add_argument("--split-column",default="global_family_v2_split");p.add_argument("--task-route",default="alphaseq_rank");p.add_argument("--alpha",type=float,default=10.0);a=p.parse_args();print(json.dumps(train(a.input,a.artifact_dir,split_column=a.split_column,task_route=a.task_route,alpha=a.alpha),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
