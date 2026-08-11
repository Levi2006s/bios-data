"""Reconcile the teammate DOCX certification table with BioOS label metadata."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from extract_docx_tables import extract_tables


def key(value:str)->str:
    return re.sub(r"[^a-z0-9]","",Path(value).name.casefold())


def expected_direction(text:str)->str:
    compact="".join(text.split())
    if "越小" in compact:return "-1"
    if "越大" in compact or compact.startswith("1="):return "1"
    return ""


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--docx",type=Path,required=True);parser.add_argument("--registry",type=Path,required=True);parser.add_argument("--benchmark",type=Path,required=True);parser.add_argument("--output-dir",type=Path,required=True);args=parser.parse_args()
    certified=[]
    for table in extract_tables(args.docx)[1:]:
        header=table[0]
        for values in table[1:]:
            row=dict(zip(header,values))
            if row.get("文件名"):certified.append(row)
    with args.registry.open(encoding="utf8",newline="") as handle:registry=list(csv.DictReader(handle))
    registry_by_key={key(row["source_file"]):row for row in registry}
    counts=Counter();tiers={};metrics={};directions={};splits=Counter()
    with args.benchmark.open(encoding="utf8",newline="") as handle:
        for row in csv.DictReader(handle):
            source=row["source_file"];counts[source]+=1;tiers[source]=row.get("tier","");metrics[source]=row.get("metric","");directions[source]=row.get("direction","");splits[(source,row.get("framework_family_split",""))]+=1
    details=[];matched_registry=set()
    for row in certified:
        doc_key=key(row["文件名"]);match_key=doc_key;match_type="exact"
        if doc_key not in registry_by_key:
            scored=sorted(((SequenceMatcher(None,doc_key,candidate).ratio(),candidate) for candidate in registry_by_key),reverse=True)
            score,match_key=scored[0];match_type=f"fuzzy:{score:.3f}"
            if score<.88:match_key=""
        reg=registry_by_key.get(match_key);source=reg["source_file"] if reg else "";matched_registry.add(match_key)
        suggested=expected_direction(row.get("开发价值方向","") or row.get("原始数值方向",""));issues=[]
        grade=row.get("亲和力等级","")
        endpoint=row.get("终点/标签定义","")
        if reg:
            if suggested and suggested!=reg["direction"]:issues.append("direction_conflict")
            if (grade in {"D","NA"} or "C/D" in grade) and reg["supervised_use"]=="yes":issues.append("not_affinity_but_supervised")
            if ("EC50" in endpoint or "IC50" in endpoint) and reg["tier"]=="Gold":issues.append("functional_endpoint_is_gold")
            if "B/C" in grade and reg["tier"]=="Gold":issues.append("quality_overstated")
        details.append({
            "doc_filename":row["文件名"],"registry_source_file":source,"match_type":match_type if reg else "unmatched",
            "endpoint":endpoint,"affinity_grade":grade,"doc_direction":suggested,
            "registry_metric":reg["metric"] if reg else "","registry_direction":reg["direction"] if reg else "",
            "registry_tier":reg["tier"] if reg else "","registry_supervised_use":reg["supervised_use"] if reg else "",
            "benchmark_rows":counts[source],"train_rows":splits[(source,"train")],"validation_rows":splits[(source,"validation")],"test_rows":splits[(source,"test")],
            "issues":";".join(issues),"certification_note":row.get("认证意见/处理",""),
        })
    output=args.output_dir;output.mkdir(parents=True,exist_ok=True)
    fields=list(details[0]);
    with (output/"reconciliation.csv").open("w",encoding="utf8",newline="") as handle:writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(details)
    issue_counts=Counter(issue for row in details for issue in row["issues"].split(";") if issue)
    issue_rows=Counter()
    for row in details:
        for issue in row["issues"].split(";"):
            if issue:issue_rows[issue]+=row["benchmark_rows"]
    benchmark_sources=set(counts);registry_sources={row["source_file"] for row in registry}
    summary={
        "certified_files":len(certified),"registry_files":len(registry),"benchmark_sources":len(benchmark_sources),"benchmark_rows":sum(counts.values()),
        "certification_matched":sum(bool(row["registry_source_file"]) for row in details),
        "certification_unmatched":[row["doc_filename"] for row in details if not row["registry_source_file"]],
        "registry_not_certified":sorted(row["source_file"] for token,row in registry_by_key.items() if token not in matched_registry),
        "issue_file_counts":dict(issue_counts),"issue_benchmark_row_counts":dict(issue_rows),
        "rows_in_any_flagged_source":sum(row["benchmark_rows"] for row in details if row["issues"]),
        "output_csv":str(output/"reconciliation.csv"),
    }
    (output/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8");print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
