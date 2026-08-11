"""Create an experimental benchmark with assay-safe AbRank percentile labels."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from bioos_benchmark.data import iter_csv_records, stable_record_id


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--input",type=Path,required=True);parser.add_argument("--abrank",type=Path,required=True);parser.add_argument("--data-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);args=parser.parse_args()
    group_by_id={stable_record_id(record):record.comparison_group for record in iter_csv_records(args.abrank,args.data_root,-1)}
    grouped=defaultdict(list);abrank_rows=[]
    with args.input.open(encoding="utf8",newline="") as handle:
        for row in csv.DictReader(handle):
            if not row["source_file"].endswith("AbRank_dataset.csv"):continue
            group=group_by_id.get(row["record_id"])
            if not group:raise ValueError(f"AbRank record not resolved: {row['record_id']}")
            index=len(abrank_rows);abrank_rows.append((row["record_id"],float(row["raw_label"]),int(row["direction"]),group));grouped[group].append(index)
    scores=[.5]*len(abrank_rows)
    for indices in grouped.values():
        ordered=sorted(indices,key=lambda i:abrank_rows[i][1]*abrank_rows[i][2]);start=0
        while start<len(ordered):
            end=start+1;value=abrank_rows[ordered[start]][1]*abrank_rows[ordered[start]][2]
            while end<len(ordered) and abrank_rows[ordered[end]][1]*abrank_rows[ordered[end]][2]==value:end+=1
            score=.5 if len(ordered)==1 else ((start+end-1)/2)/(len(ordered)-1)
            for position in range(start,end):scores[ordered[position]]=score
            start=end
    replacement={record_id:(group,score) for (record_id,_,_,group),score in zip(abrank_rows,scores)}
    args.output.parent.mkdir(parents=True,exist_ok=True);rows_written=0
    with args.input.open(encoding="utf8",newline="") as source,args.output.open("w",encoding="utf8",newline="") as target:
        reader=csv.DictReader(source);writer=csv.DictWriter(target,fieldnames=reader.fieldnames);writer.writeheader()
        for row in reader:
            if row["record_id"] in replacement:
                group,score=replacement[row["record_id"]];row["comparison_group"]=group;row["score"]=f"{score:.12g}"
                endpoint=group.split("::")[-2];row["metric"]="AbRank_KD" if endpoint=="KD" else "AbRank_IC50" if endpoint=="IC50" else "AbRank_other"
            writer.writerow(row);rows_written+=1
    sizes=Counter(len(indices) for indices in grouped.values());endpoint_counts=Counter(group.split("::")[-2] for _,_,_,group in abrank_rows)
    report={"input":str(args.input),"output":str(args.output),"rows":rows_written,"abrank_rows":len(abrank_rows),"comparison_groups":len(grouped),"endpoint_counts":dict(endpoint_counts),"group_size_histogram":dict(sorted(sizes.items())),"singleton_groups":sizes[1]}
    args.output.with_suffix(".summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8");print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
