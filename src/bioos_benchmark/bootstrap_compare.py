"""Paired bootstrap uncertainty for competing ranking prediction files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr


def paired_cluster_bootstrap(
    truth: np.ndarray,
    baseline: np.ndarray,
    candidate: np.ndarray,
    groups: np.ndarray,
    *,
    repeats: int = 2000,
    seed: int = 20260803,
) -> dict[str, object]:
    unique=np.unique(groups);members=[np.flatnonzero(groups==group) for group in unique]
    rng=np.random.default_rng(seed);deltas=[]
    for _ in range(repeats):
        chosen=rng.integers(0,len(unique),size=len(unique))
        index=np.concatenate([members[position] for position in chosen])
        base=float(spearmanr(truth[index],baseline[index]).statistic)
        cand=float(spearmanr(truth[index],candidate[index]).statistic)
        if np.isfinite(base) and np.isfinite(cand):deltas.append(cand-base)
    values=np.asarray(deltas)
    if not len(values):raise ValueError("no finite bootstrap replicates")
    point=float(spearmanr(truth,candidate).statistic-spearmanr(truth,baseline).statistic)
    return {
        "method":"paired_source_cluster_bootstrap",
        "groups":int(len(unique)),"repeats_requested":repeats,"repeats_valid":int(len(values)),
        "seed":seed,"point_delta_spearman":point,
        "delta_mean":float(values.mean()),"delta_std":float(values.std(ddof=1)),
        "ci95":[float(x) for x in np.quantile(values,[.025,.975])],
        "probability_candidate_better":float(np.mean(values>0)),
    }


def compare_prediction_files(baseline_path:Path,candidate_path:Path,output:Path,*,repeats:int=2000,seed:int=20260803,metadata_path:Path|None=None,group_by_antibody_pair:bool=False):
    def read(path):
        with path.open(encoding="utf8",newline="") as handle:rows=list(csv.DictReader(handle))
        return {row["record_id"]:row for row in rows}
    baseline=read(baseline_path);candidate=read(candidate_path);ids=sorted(baseline)
    if set(ids)!=set(candidate):raise ValueError("prediction record_id sets must match")
    truth=np.asarray([float(baseline[x]["truth"]) for x in ids])
    other_truth=np.asarray([float(candidate[x]["truth"]) for x in ids])
    if not np.allclose(truth,other_truth):raise ValueError("truth values disagree")
    groups=np.asarray([baseline[x]["source_file"] for x in ids])
    if group_by_antibody_pair:
        if metadata_path is None:raise ValueError("metadata_path is required for antibody-pair grouping")
        with metadata_path.open(encoding="utf8",newline="") as handle:
            metadata={row["record_id"]:row["heavy"]+"\x1f"+row.get("light","") for row in csv.DictReader(handle)}
        groups=np.asarray([metadata[x] for x in ids])
    report=paired_cluster_bootstrap(
        truth,np.asarray([float(baseline[x]["prediction"]) for x in ids]),
        np.asarray([float(candidate[x]["prediction"]) for x in ids]),
        groups,repeats=repeats,seed=seed,
    )
    if group_by_antibody_pair:report["method"]="paired_exact_antibody_cluster_bootstrap"
    report.update({"baseline":str(baseline_path),"candidate":str(candidate_path),"records":len(ids),"grouping":"exact_antibody_pair" if group_by_antibody_pair else "source_file"})
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--baseline",type=Path,required=True);parser.add_argument("--candidate",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);parser.add_argument("--repeats",type=int,default=2000);parser.add_argument("--seed",type=int,default=20260803);parser.add_argument("--metadata",type=Path);parser.add_argument("--group-by-antibody-pair",action="store_true");args=parser.parse_args()
    print(json.dumps(compare_prediction_files(args.baseline,args.candidate,args.output,repeats=args.repeats,seed=args.seed,metadata_path=args.metadata,group_by_antibody_pair=args.group_by_antibody_pair),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
