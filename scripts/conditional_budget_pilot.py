#!/usr/bin/env python3
"""Audit *reported* scientific-information-necessity pilots (B05).

Only checks numerical consistency, coverage, and pre-registered contrast logic.
Does NOT execute a simulator or establish independent physics validity.
The benchmark-specific grader remains authoritative.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path

REQUIRED = (
    "old_one_shot", "geometry_only", "distance_dedup",
    "conditional", "public_only_reference", "science_ablated",
)

def finite_num(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)

def is_pass(row, contract):
    errors = []
    scores = row.get("scores")
    js = row.get("js_per_observation")
    gates = row.get("mandatory_gates")
    names = list(contract["min_subscore"])
    if not isinstance(scores, dict) or not all(finite_num(scores.get(k)) for k in names):
        errors.append("missing/nonfinite subscore")
    if not isinstance(js, list) or len(js) != contract["observations"] or not all(finite_num(x) and x>=0 for x in js):
        errors.append("missing/nonfinite per-observation JS")
    if not isinstance(gates, dict) or any(gates.get(g) is not True and gates.get(g) is not False for g in contract["mandatory_gates"]):
        errors.append("missing/nonboolean mandatory science gate")
    if row.get("output_valid") is not True and row.get("output_valid") is not False:
        errors.append("missing output_valid boolean")
    if errors:
        return None, errors
    total = sum(scores[k] for k in names)
    if not finite_num(row.get("reported_total")) or abs(row["reported_total"] - total)>1e-4:
        errors.append("reported total does not equal sum of subscores")
    if not isinstance(row.get("reads_only_public"), bool) or row["reads_only_public"] is not True:
        errors.append("not public-only")
    if not isinstance(row.get("execution_log"), str) or not row["execution_log"]:
        errors.append("execution log path missing")
    passed = (row["output_valid"] and total >= contract["min_total"]
              and all(scores[k] >= v for k,v in contract["min_subscore"].items())
              and all(v <= contract["max_js"] for v in js)
              and all(gates[g] for g in contract["mandatory_gates"]))
    if not isinstance(row.get("reported_pass"), bool) or row["reported_pass"] != passed:
        errors.append("reported_pass disagrees with frozen scoring contract")
    return passed, errors

def audit(obj, root=None, require_logs=False):
    errors=[]
    bypass=[]
    unverified=[]
    def need(cond,message):
        if not cond: errors.append(message)
    contract=obj.get("contract",{})
    need(isinstance(obj.get("release_id"),str) and bool(obj["release_id"]),"release_id missing")
    need(obj.get("frozen_before_final_blind") is True, "scoring contract not frozen before final blind")
    need(obj.get("new_physics_holdout_untouched") is True, "physics holdout not isolated")
    need(obj.get("same_unchanged_grader_for_all") is True, "not the same unchanged grader")
    need(obj.get("grader_sha256") and isinstance(obj.get("grader_sha256"),str),"grader SHA missing")
    need(finite_num(contract.get("min_total")) and contract.get("min_total",-1)>=0,"min_total missing")
    need(isinstance(contract.get("min_subscore"),dict) and all(finite_num(v) for v in contract.get("min_subscore",{}).values()),"min_subscore invalid")
    need(isinstance(contract.get("observations"),int) and contract.get("observations",0)>0,"observations invalid")
    need(finite_num(contract.get("max_js")) and contract.get("max_js",-1)>0,"max_js invalid")
    need(isinstance(contract.get("mandatory_gates"),list) and len(contract.get("mandatory_gates",[]))==len(set(contract.get("mandatory_gates",[]))),"mandatory_gates invalid")
    cases=obj.get("cases")
    if not isinstance(cases,list) or not cases:
        return {"status":"PILOT_UNVERIFIED","errors":errors+["cases missing"],"bypass":[],"unverified":[]}
    family=set();seed=set()
    for ca in cases:
        cid=ca.get("case_id","<unnamed>")
        if ca.get("split") not in ("dev","independent_pilot","final_holdout"):
            errors.append(f"{cid}: unknown data split")
        family.add(ca.get("physics_family"))
        seed.add((ca.get("physics_family"),ca.get("physics_seed")))
        strategies=ca.get("strategies",[])
        if not isinstance(strategies,list):
            errors.append(f"{cid}: strategies not a list"); continue
        names=[s.get("type") for s in strategies]
        need(set(REQUIRED).issubset(names),f"{cid}: missing strategy types {sorted(set(REQUIRED)-set(names))}")
        need(len(names)==len(set(names)),f"{cid}: duplicate strategy types")
        seen={}
        for row in strategies:
            typ=row.get("type","<none>")
            if typ in ("geometry_only","distance_dedup","science_ablated") and row.get("uses_observation_data") is not False:
                errors.append(f"{cid}/{typ}: data-ablation route must not use observations")
            if typ in ("conditional","public_only_reference") and row.get("uses_observation_data") is not True:
                errors.append(f"{cid}/{typ}: science reference must use observable evidence")
            if not row.get("execution_log"):
                errors.append(f"{cid}/{typ}: missing log")
            elif require_logs and root and not (root/row["execution_log"]).is_file():
                errors.append(f"{cid}/{typ}: log not found")
            if (not isinstance(contract.get("min_subscore"),dict) or not isinstance(contract.get("observations"),int)
                or not finite_num(contract.get("max_js")) or not isinstance(contract.get("mandatory_gates"),list)):
                errors.append("contract invalid; cannot score");continue
            result,diag=is_pass(row,contract)
            errors.extend([f"{cid}/{typ}: {x}" for x in diag])
            seen[typ]=result
            if typ in ("geometry_only","distance_dedup","science_ablated") and result is True:
                bypass.append(f"{cid}/{typ}: observation-free route legitimately passes all science gates")
            if typ=="old_one_shot" and result is True:
                unverified.append(f"{cid}: one-shot route passes; show conditional benefit in another prespecified physics case")
            if typ in ("conditional","public_only_reference") and result is False:
                unverified.append(f"{cid}/{typ}: science-informed reference fails")
        if (seen.get("public_only_reference") is None or seen.get("conditional") is None):
            unverified.append(f"{cid}: reference/conditional route missing or invalid")
    need(len([x for x in family if isinstance(x,str) and x])>=2,
         "only one physics family; layouts with same likelihood do not establish physics generalization")
    need(len(seed)>=3,"need >=3 independent physics realizations in this example release policy")
    # Do not reject simple scientifically informed routes *by their names*.
    # The audit only requires the targeted ablation counterexamples to fail.
    if errors or unverified:
        status="PILOT_UNVERIFIED"
    elif bypass:
        status="PILOT_FAIL_SCIENCE_DECISION_BYPASS"
    else:
        status="PILOT_PASS_STRUCTURAL_ONLY"
    # Bypass is a valid, decisive finding even if scenario completeness is deficient.
    if bypass:
        status="PILOT_FAIL_SCIENCE_DECISION_BYPASS"
    return {"status":status,"cases":len(cases),"physics_families":len(family),
            "distinct_family_seed_pairs":len(seed),"bypass":bypass,"unverified":unverified,
            "errors":errors,"warning":"Audit of reported runs only. Does not execute simulator/grader or prove causal identifiability."}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pilot",type=Path,required=True)
    ap.add_argument("--root",type=Path)
    ap.add_argument("--require-logs",action="store_true")
    opt=ap.parse_args()
    try:
        obj=json.loads(opt.pilot.read_text(encoding="utf-8"))
        status=audit(obj,opt.root or opt.pilot.parent,opt.require_logs)
        print(json.dumps(status,ensure_ascii=False,indent=2,allow_nan=False))
        return 0 if status["status"]=="PILOT_PASS_STRUCTURAL_ONLY" else 1
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(json.dumps({"status":"PILOT_UNVERIFIED","error":str(exc)}))
        return 1
if __name__ == "__main__":
    sys.exit(main())
