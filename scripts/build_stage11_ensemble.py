"""Build the leakage-free Stage 11 routed rank ensemble."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from bioos_benchmark.metrics import regression_metrics


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--artifact-dir",type=Path,default=Path("artifacts/stage11"));args=parser.parse_args();root=args.artifact_dir
    global_model=pd.read_csv(root/"esm150_conditional_rank/predictions.csv").rename(columns={"prediction":"global_prediction"})
    expert=pd.read_csv(root/"esm150_alphaseq_expert/predictions.csv",usecols=["record_id","prediction"]).rename(columns={"prediction":"expert_prediction"})
    ridge=pd.read_csv(root/"alphaseq_positional_ridge/predictions.csv",usecols=["record_id","prediction"]).rename(columns={"prediction":"ridge_prediction"})
    cnn_rank=pd.read_csv(root/"cnn_full_pairrank_seed43/predictions.csv",usecols=["record_id","prediction"]).rename(columns={"prediction":"cnn_rank_prediction"})
    cnn_reg=pd.read_csv(root/"cnn_full_abrank_seed42/predictions.csv",usecols=["record_id","prediction"]).rename(columns={"prediction":"cnn_reg_prediction"})
    frame=global_model.merge(expert,on="record_id",how="left").merge(ridge,on="record_id",how="left").merge(cnn_rank,on="record_id").merge(cnn_reg,on="record_id")
    routed=frame.global_prediction.to_numpy().copy();mask=frame.ridge_prediction.notna().to_numpy();positions=np.flatnonzero(mask)
    alpha_rank=.65*rankdata(frame.loc[mask,"ridge_prediction"])+.35*rankdata(frame.loc[mask,"expert_prediction"])
    order=np.argsort(alpha_rank);mapped=np.empty(len(positions));mapped[order]=np.sort(frame.loc[mask,"global_prediction"].to_numpy());routed[positions]=mapped
    n=len(frame);prediction=.80*rankdata(routed)/n+(2/15)*rankdata(frame.cnn_rank_prediction)/n+(1/15)*rankdata(frame.cnn_reg_prediction)/n
    frame["prediction"]=prediction
    metrics={"model":"stage11_domain_routed_rank_ensemble","weights":{"routed_esm_positional":.8,"cnn_rank":2/15,"cnn_reg":1/15},"alpha_domain_weights":{"positional_ridge":.65,"esm_expert":.35},"overall":regression_metrics(frame.truth.to_numpy(),prediction),"records":n}
    frame[["record_id","source_file","truth","prediction"]].to_csv(root/"final_domain_routed_ensemble.csv",index=False)
    (root/"final_domain_routed_ensemble.metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(metrics,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
