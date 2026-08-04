"""Build Stage 12 parent-cluster and residue-adapted routed ensemble."""
from pathlib import Path
import json,numpy as np,pandas as pd
from scipy.stats import rankdata
from bioos_benchmark.metrics import regression_metrics

root=Path("artifacts")
paths={"ridge":root/"stage11/alphaseq_positional_ridge/predictions.csv","cluster":root/"stage12/alphaseq_cluster_positional_ridge/predictions.csv","conv48":root/"stage12/alphaseq_positional_conv_seed48/predictions.csv","conv51":root/"stage12/alphaseq_positional_conv_seed51/predictions.csv","finetune":root/"stage12/esm150_alphaseq_last_layer_shared/predictions.csv"}
alpha=None
for name,path in paths.items():
    frame=pd.read_csv(path).rename(columns={"prediction":name,"truth":f"truth_{name}"})[["record_id",f"truth_{name}",name]];alpha=frame if alpha is None else alpha.merge(frame,on="record_id")
alpha_weights={"ridge":.0029093361382707306,"cluster":.4271847809350856,"conv48":.28086027541007486,"conv51":.039847602467243184,"finetune":.2491980050493255}
global_model=pd.read_csv(root/"stage11/esm150_conditional_rank/predictions.csv").rename(columns={"prediction":"global_prediction"});cnn_rank=pd.read_csv(root/"stage11/cnn_full_pairrank_seed43/predictions.csv",usecols=["record_id","prediction"]).rename(columns={"prediction":"cnn_rank"});cnn_reg=pd.read_csv(root/"stage11/cnn_full_abrank_seed42/predictions.csv",usecols=["record_id","prediction"]).rename(columns={"prediction":"cnn_reg"});frame=global_model.merge(alpha[["record_id",*alpha_weights]],on="record_id",how="left").merge(cnn_rank,on="record_id").merge(cnn_reg,on="record_id")
mask=frame.cluster.notna();positions=np.flatnonzero(mask);score=sum(weight*rankdata(frame.loc[mask,name]) for name,weight in alpha_weights.items());order=np.argsort(score);mapped=np.empty(len(positions));mapped[order]=np.sort(frame.loc[mask,"global_prediction"]);routed=frame.global_prediction.to_numpy().copy();routed[positions]=mapped
global_weights={"routed":.85861031,"cnn_rank":.09935529,"cnn_reg":.0420344};n=len(frame);prediction=global_weights["routed"]*rankdata(routed)/n+global_weights["cnn_rank"]*rankdata(frame.cnn_rank)/n+global_weights["cnn_reg"]*rankdata(frame.cnn_reg)/n;frame["prediction"]=prediction
metrics={"model":"stage12_parent_cluster_residue_routed_ensemble","alpha_weights":alpha_weights,"global_weights":global_weights,"overall":regression_metrics(frame.truth.to_numpy(),prediction),"records":n};out=root/"stage12";frame[["record_id","source_file","truth","prediction"]].to_csv(out/"final_parent_cluster_routed_ensemble.csv",index=False);(out/"final_parent_cluster_routed_ensemble.metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(metrics,ensure_ascii=False,indent=2))
