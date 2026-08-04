"""Machine-readable team consensus for label grading and task routing."""
from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class LabelPolicy:
    affinity_grade:str
    affinity_weight:float
    task_route:str
    comparison_scope:str
    notes:str=""

def load_policies(path:Path)->list[tuple[str,str,LabelPolicy]]:
    with path.open(encoding="utf-8",newline="") as handle:
        return [(r["rule_type"],r["rule_value"],LabelPolicy(r["affinity_grade"],float(r["affinity_weight"]),r["task_route"],r["comparison_scope"],r.get("notes",""))) for r in csv.DictReader(handle)]

def route_row(row:dict[str,str],policies:list[tuple[str,str,LabelPolicy]])->LabelPolicy:
    source=row.get("source_file","");metric=row.get("metric","")
    # Source-specific safety corrections override broad metric defaults.
    for kind,value,policy in policies:
        if kind=="source_contains" and value in source:
            if policy.task_route=="route_by_metric":break
            return policy
    for kind,value,policy in policies:
        if kind=="metric" and value==metric:return policy
    return LabelPolicy("NA",0.0,"unsupervised","none","unresolved label policy")
