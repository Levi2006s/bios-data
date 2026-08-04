"""Aligned positional mutation-effect baseline for fixed-family landscapes."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import joblib
import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import OneHotEncoder

from .metrics import regression_metrics


def sequence_matrix(rows: list[dict[str, str]], heavy_length: int, light_length: int) -> np.ndarray:
    return np.asarray([
        list(row["heavy"].ljust(heavy_length, "-")[:heavy_length] + row.get("light", "").ljust(light_length, "-")[:light_length])
        for row in rows
    ])


def train(input_path: Path, artifact_dir: Path, alpha: float = 10.0, *,
          split_column: str = "framework_family_split", task_route: str | None = None) -> dict[str, object]:
    with input_path.open(encoding="utf-8", newline="") as handle:
        rows=[row for row in csv.DictReader(handle) if row.get(split_column) in {"train","validation"} and (task_route is None or row.get("task_route")==task_route)]
    train_rows=[row for row in rows if row[split_column]=="train"]
    validation_rows=[row for row in rows if row[split_column]=="validation"]
    heavy_length=max(len(row["heavy"]) for row in rows);light_length=max(len(row.get("light","")) for row in rows)
    encoder=OneHotEncoder(handle_unknown="ignore",sparse_output=True,dtype=np.float32)
    x_train=encoder.fit_transform(sequence_matrix(train_rows,heavy_length,light_length))
    x_validation=encoder.transform(sequence_matrix(validation_rows,heavy_length,light_length))
    y_train=np.asarray([float(row["score"]) for row in train_rows]);truth=np.asarray([float(row["score"]) for row in validation_rows])
    model=Ridge(alpha=alpha,solver="lsqr").fit(x_train,y_train);prediction=model.predict(x_validation)
    metrics={"model":"aligned_positional_ridge","alpha":alpha,"split_column":split_column,"task_route":task_route,"train_records":len(train_rows),"validation_records":len(validation_rows),"heavy_length":heavy_length,"light_length":light_length,"overall":regression_metrics(truth,prediction),"spearman":float(spearmanr(truth,prediction).statistic)}
    artifact_dir.mkdir(parents=True,exist_ok=True);joblib.dump({"encoder":encoder,"model":model,"heavy_length":heavy_length,"light_length":light_length},artifact_dir/"model.joblib")
    (artifact_dir/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    with (artifact_dir/"predictions.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.writer(handle);writer.writerow(["record_id","source_file","truth","prediction"])
        for row,y,pred in zip(validation_rows,truth,prediction):writer.writerow([row["record_id"],row["source_file"],y,pred])
    return metrics


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--input",type=Path,required=True);parser.add_argument("--artifact-dir",type=Path,required=True);parser.add_argument("--alpha",type=float,default=10.0);parser.add_argument("--split-column",default="framework_family_split");parser.add_argument("--task-route")
    args=parser.parse_args();print(json.dumps(train(args.input,args.artifact_dir,args.alpha,split_column=args.split_column,task_route=args.task_route),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
