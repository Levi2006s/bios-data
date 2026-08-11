"""Annotate every curated record with the team consensus label route."""
from __future__ import annotations
import argparse,csv,json
from collections import Counter
from pathlib import Path
from bioos_benchmark.label_policy import load_policies,route_row

def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--policy",type=Path,default=Path("configs/team_label_policy.csv"));p.add_argument("--output",type=Path,required=True);a=p.parse_args();policies=load_policies(a.policy);counts=Counter();grades=Counter()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.input.open(encoding="utf-8",newline="") as source,a.output.open("w",encoding="utf-8",newline="") as target:
        reader=csv.DictReader(source);assert reader.fieldnames;fields=[*reader.fieldnames,"affinity_grade","affinity_weight","task_route","comparison_scope"];writer=csv.DictWriter(target,fieldnames=fields);writer.writeheader()
        for row in reader:
            policy=route_row(row,policies);row.update(affinity_grade=policy.affinity_grade,affinity_weight=f"{policy.affinity_weight:.6g}",task_route=policy.task_route,comparison_scope=policy.comparison_scope);writer.writerow(row);counts[policy.task_route]+=1;grades[policy.affinity_grade]+=1
    report={"input":str(a.input),"output":str(a.output),"records":sum(counts.values()),"task_routes":dict(counts),"affinity_grades":dict(grades)};a.output.with_suffix(".routing.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
