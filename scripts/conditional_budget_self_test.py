#!/usr/bin/env python3
"""Synthetic test fixtures for conditional_budget_pilot; NOT real v10 science tests."""
from __future__ import annotations
import copy
import sys
from conditional_budget_pilot import audit

B_GATES=["B_LOW_KL","B_LOW_SOURCE","B_MID_KL","B_MID_SOURCE","B_HIGH_KL","B_HIGH_SOURCE"]

def row(kind, c, js, use_obs, passed):
    a=24.737494;b=29.194558
    return {
        "type":kind,"uses_observation_data":use_obs,"reads_only_public":True,
        "output_valid":True,"scores":{"A":a,"B":b,"C":c},
        "reported_total":round(a+b+c,6),"js_per_observation":list(js),
        "mandatory_gates":{g:True for g in B_GATES},
        "reported_pass":passed,"execution_log":f"synthetic/{kind}.log"
    }

def fixture():
    contract={"min_total":80,"min_subscore":{"A":22,"B":18,"C":27},
              "observations":3,"max_js":0.020,"mandatory_gates":B_GATES}
    cases=[]
    for i in range(3):
        cases.append({"case_id":f"synthetic_{i}","physics_family":f"model_{i%2}",
          "physics_seed":i+1,"split":"dev","strategies":[
            row("old_one_shot",13.385390,[.031,.026,.027],True,False),
            row("geometry_only",25,[.026,.030,.023],False,False),
            row("distance_dedup",25.6,[.024,.028,.022],False,False),
            row("conditional",32,[.007,.008,.008],True,True),
            row("public_only_reference",34.052799,[.003,.004,.005],True,True),
            row("science_ablated",25,[.030,.035,.021],False,False),
        ]})
    return {"_fixture_only":"Illustrative logic test, NOT any real scientific baseline run",
        "release_id":"SYNTHETIC_FIXTURE_ONLY","frozen_before_final_blind":True,
        "new_physics_holdout_untouched":True,"same_unchanged_grader_for_all":True,
        "grader_sha256":"placeholder-for-fixture","contract":contract,"cases":cases}

def main():
    tests=0
    def expect(expr,msg):
        nonlocal tests
        tests+=1
        if not expr:
            raise AssertionError(msg)
    d=fixture()
    expect(audit(d)["status"]=="PILOT_PASS_STRUCTURAL_ONLY","normal fixture")
    bad=copy.deepcopy(d)
    g=bad["cases"][0]["strategies"][1]
    g.update(row("geometry_only",31.002741,[.006496,.005615,.003314],False,True))
    x=audit(bad)
    expect(x["status"]=="PILOT_FAIL_SCIENCE_DECISION_BYPASS","QC v9 farthest point must invalidate pilot")
    expect(any("geometry_only" in s for s in x["bypass"]),"bypass evidence preserved")
    bad=copy.deepcopy(d)
    bad["cases"][1]["physics_family"]="model_0"
    bad["cases"][2]["physics_family"]="model_0"
    expect(audit(bad)["status"]=="PILOT_UNVERIFIED","same physics family not sufficient")
    bad=copy.deepcopy(d)
    bad["cases"][0]["strategies"][0]["reported_total"]+=10
    expect(audit(bad)["status"]=="PILOT_UNVERIFIED","total must be consistent")
    bad=copy.deepcopy(d)
    bad["cases"][0]["strategies"][0]["js_per_observation"]=[.01,float("nan"),.01]
    expect(audit(bad)["status"]=="PILOT_UNVERIFIED","nonfinite JS not accepted")
    bad=copy.deepcopy(d)
    bad["cases"][0]["strategies"][4]["reported_pass"]=False
    expect(audit(bad)["status"]=="PILOT_UNVERIFIED","reported pass must match score")
    bad=copy.deepcopy(d)
    bad["same_unchanged_grader_for_all"]=False
    expect(audit(bad)["status"]=="PILOT_UNVERIFIED","scorer changed across baselines")
    bad=copy.deepcopy(d)
    bad["frozen_before_final_blind"]=False
    expect(audit(bad)["status"]=="PILOT_UNVERIFIED","blind must be pre-frozen")
    bad=copy.deepcopy(d)
    bad["cases"][0]["strategies"][3]["reported_total"]+=1
    expect(audit(bad)["status"]=="PILOT_UNVERIFIED","conditional score must be consistent")
    print(f"conditional_budget_self_test: {tests}/{tests} assertions passed (SYNTHETIC schema/logic only)")
    return 0
if __name__=="__main__":
    sys.exit(main())
