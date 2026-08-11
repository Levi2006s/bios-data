"""Aligned percentile-rank ensemble for neural validation predictions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from .metrics import regression_metrics


def ensemble_predictions(inputs: list[Path], output: Path, weights: list[float] | None = None) -> dict[str, object]:
    if len(inputs) < 2:
        raise ValueError("at least two prediction files are required")
    tables=[]
    for path in inputs:
        with path.open(encoding="utf-8",newline="") as handle:
            rows=list(csv.DictReader(handle))
        lookup={row["record_id"]:row for row in rows}
        if len(lookup)!=len(rows): raise ValueError(f"duplicate record_id in {path}")
        tables.append(lookup)
    ids=sorted(tables[0])
    if any(set(table)!=set(ids) for table in tables[1:]):
        raise ValueError("prediction record_id sets must match exactly")
    truth=np.asarray([float(tables[0][record_id]["truth"]) for record_id in ids])
    for table in tables[1:]:
        other=np.asarray([float(table[record_id]["truth"]) for record_id in ids])
        if not np.allclose(truth,other): raise ValueError("truth values disagree")
    if weights is None: weights=[1/len(inputs)]*len(inputs)
    if len(weights)!=len(inputs) or any(weight<0 for weight in weights) or sum(weights)<=0:
        raise ValueError("weights must match inputs and be non-negative with positive sum")
    normalized=np.asarray(weights,dtype=float)/sum(weights)
    ranks=np.vstack([rankdata([float(table[record_id]["prediction"]) for record_id in ids]) for table in tables])
    score=np.average(ranks,axis=0,weights=normalized)/(len(ids)+1)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.writer(handle);writer.writerow(["record_id","source_file","truth","prediction"])
        for record_id,y,value in zip(ids,truth,score):
            writer.writerow([record_id,tables[0][record_id].get("source_file",""),y,value])
    report={"inputs":[str(path) for path in inputs],"weights":normalized.tolist(),"output":str(output),"records":len(ids),"method":"weighted_global_percentile_rank","overall":regression_metrics(truth,score)}
    output.with_suffix(".summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--inputs",type=Path,nargs="+",required=True)
    parser.add_argument("--weights",type=float,nargs="+");parser.add_argument("--output",type=Path,required=True);args=parser.parse_args()
    print(json.dumps(ensemble_predictions(args.inputs,args.output,args.weights),ensure_ascii=False,indent=2))


if __name__ == "__main__": main()
