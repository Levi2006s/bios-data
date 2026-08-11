"""Train-only ESM heavy/light clustering for parent-proxy assignment."""

from __future__ import annotations

import argparse,csv,json
from collections import Counter,defaultdict
from pathlib import Path

import joblib,numpy as np,torch
from sklearn.cluster import MiniBatchKMeans


def assay_name(source:str)->str:
    if "engelhart2022dataset" in source or "affinity1.csv" in source:return "alpha_landscape_1"
    if "affinity2.csv" in source:return "alpha_landscape_2"
    return source


def pair_key(heavy:str,light:str)->str:return heavy+"\x1f"+light


def build(input_path:Path,embeddings_path:Path,output:Path,*,split_column="global_family_v2_split",route="alphaseq_rank",clusters_per_group=8,seed=20260812):
    payload=torch.load(embeddings_path,map_location="cpu");emb=payload["embeddings"].float().numpy();lookup={s:i for i,s in enumerate(payload["sequences"])};zero=np.zeros(emb.shape[1],dtype=np.float32)
    groups=defaultdict(lambda:{"train":{},"validation":{}})
    with input_path.open(encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            split=r.get(split_column)
            if r.get("task_route")!=route or split not in {"train","validation"}:continue
            group=f"{assay_name(r['source_file'])}|H{len(r['heavy'])}|L{len(r.get('light',''))}"
            groups[group][split].setdefault(pair_key(r["heavy"],r.get("light","")),(r["heavy"],r.get("light","")))
    assignments={};distances={};ood_percentiles={};references={};report={}
    def vectors(pairs):
        return np.stack([np.concatenate((emb[lookup[h]],emb[lookup[l]] if l in lookup else zero)) for h,l in pairs]).astype(np.float32)
    for group,parts in sorted(groups.items()):
        train_keys=sorted(parts["train"]);validation_keys=sorted(parts["validation"]);train_pairs=[parts["train"][k] for k in train_keys];validation_pairs=[parts["validation"][k] for k in validation_keys];n_clusters=min(clusters_per_group,len(train_pairs))
        model=MiniBatchKMeans(n_clusters=n_clusters,random_state=seed,n_init=3,batch_size=4096,max_iter=100,reassignment_ratio=.01).fit(vectors(train_pairs))
        train_vectors=vectors(train_pairs);validation_vectors=vectors(validation_pairs) if validation_pairs else np.empty((0,train_vectors.shape[1]),dtype=np.float32)
        train_labels=model.labels_;validation_labels=model.predict(validation_vectors) if validation_pairs else np.empty(0,dtype=int)
        train_distances=np.linalg.norm(train_vectors-model.cluster_centers_[train_labels],axis=1)
        validation_distances=np.linalg.norm(validation_vectors-model.cluster_centers_[validation_labels],axis=1) if validation_pairs else np.empty(0,dtype=np.float32)
        cluster_reference={cluster:np.sort(train_distances[train_labels==cluster]) for cluster in range(n_clusters)}
        def consensus(sequences):
            return "".join(sorted(Counter(sequence[position] for sequence in sequences).items(),key=lambda item:(-item[1],item[0]))[0][0] for position in range(len(sequences[0])))
        for cluster in range(n_clusters):
            members=[train_pairs[index] for index in np.flatnonzero(train_labels==cluster)]
            references[f"{group}|C{cluster}"]={"heavy":consensus([pair[0] for pair in members]),"light":consensus([pair[1] for pair in members]) if members[0][1] else ""}
        def record(key,label,distance):
            assignments[key]=f"{group}|C{int(label)}";distances[key]=float(distance);reference=cluster_reference[int(label)];ood_percentiles[key]=float(np.searchsorted(reference,distance,side="right")/len(reference))
        for key,label,distance in zip(train_keys,train_labels,train_distances):record(key,label,distance)
        for key,label,distance in zip(validation_keys,validation_labels,validation_distances):record(key,label,distance)
        report[group]={"train_unique":len(train_keys),"validation_unique":len(validation_keys),"clusters":n_clusters,"train_cluster_counts":np.bincount(train_labels,minlength=n_clusters).tolist(),"validation_cluster_counts":np.bincount(validation_labels,minlength=n_clusters).tolist(),"train_distance_median":float(np.median(train_distances)),"validation_distance_median":float(np.median(validation_distances)) if len(validation_distances) else None,"validation_ood_p90_fraction":float(np.mean([ood_percentiles[key]>=.9 for key in validation_keys])) if validation_keys else None}
    output.parent.mkdir(parents=True,exist_ok=True);joblib.dump({"assignments":assignments,"distances":distances,"ood_percentiles":ood_percentiles,"references":references,"split_column":split_column,"route":route,"groups":report},output);summary={"output":str(output),"pairs":len(assignments),"reference_consensuses":len(references),"clusters_per_group":clusters_per_group,"seed":seed,"groups":report};output.with_suffix(".json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--embeddings",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--split-column",default="global_family_v2_split");p.add_argument("--clusters-per-group",type=int,default=8);p.add_argument("--seed",type=int,default=20260812);a=p.parse_args();print(json.dumps(build(a.input,a.embeddings,a.output,split_column=a.split_column,clusters_per_group=a.clusters_per_group,seed=a.seed),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
