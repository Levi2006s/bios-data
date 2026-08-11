from pathlib import Path
from bioos_benchmark.label_policy import load_policies,route_row

POLICIES=load_policies(Path("configs/team_label_policy.csv"))

def test_adcc_never_routes_to_affinity():
    policy=route_row({"source_file":"初赛-序列数据/2/shanehsazzadeh2023unlocking_adcc_ec50.csv","metric":"EC50"},POLICIES)
    assert policy.task_route=="adcc_aux" and policy.affinity_weight==0

def test_ova_is_polyreactivity_risk():
    policy=route_row({"source_file":"初赛-序列数据/12/makowski2022cooptimization_igg_ova.csv","metric":"binding_signal"},POLICIES)
    assert policy.task_route=="polyreactivity_risk" and policy.affinity_grade=="D"

def test_spr_routes_to_affinity():
    policy=route_row({"source_file":"x_spr.csv","metric":"negative_log10_KD"},POLICIES)
    assert policy.task_route=="affinity_rank" and policy.affinity_weight==1
