#!/usr/bin/env python3
"""Audit the presence of real scientific difficulty pilot evidence (structure only).

The code does not certify scientific difficulty. Human reviewers must inspect
baseline mechanisms, science-gate relevance, and real execution logs.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def audit(p: dict, root: Path) -> dict:
    errors = []
    def need(cond, message):
        if not cond:
            errors.append(message)
    need(bool(p.get("release_id")), "release_id missing")
    need(bool(p.get("unified_science_question")), "unified scientific question missing")
    need(p.get("contract_frozen_before_final_blind") is True,
         "contract was not frozen before final blind generation")
    need(p.get("blind_split_independent_units") is True,
         "no evidence of independent blinding unit (phase/halo/field/seed)")
    gates = p.get("mandatory_science_gates", [])
    need(isinstance(gates, list) and len(gates)>0 and len(gates)==len(set(gates)),
         "missing/duplicate mandatory scientific gates")
    need(int(p.get("development_seed_count", 0)) >= 2,
         "need at least two independent pilot seed runs in this example policy")
    r = p.get("public_only_reference", {})
    need(r.get("reads_only_public") is True, "reference is not public-only")
    need(r.get("passed") is True and r.get("all_mandatory_gates_passed") is True,
         "public-only reference did not pass every mandatory gate")
    if r.get("log_path"):
        need((root / r["log_path"]).is_file(), "reference execution log missing")
    else:
        errors.append("reference execution log path missing")
    baselines = p.get("ordinary_baselines", [])
    need(len(baselines)>=2, "fewer than two scientifically meaningful ordinary baselines")
    observed_failures = set()
    for b in baselines:
        name = b.get("name", "<unnamed>")
        need(bool(b.get("science_assumption")), f"{name}: no science assumption recorded")
        need(b.get("reads_only_public") is True, f"{name}: not public-only")
        failed = set(b.get("failed_mandatory_gates", []))
        need(failed.issubset(set(gates)), f"{name}: unknown failed gate")
        need(bool(failed), f"{name}: ordinary baseline passes all mandatory gates; redesign Gate 1")
        need(b.get("overall_passed") is False,
             f"{name}: ordinary baseline passed benchmark; redesign Gate 1")
        observed_failures |= failed
        if b.get("log_path"):
            need((root / b["log_path"]).is_file(), f"{name}: missing log")
        else:
            errors.append(f"{name}: missing log path")
    need(bool(observed_failures), "no evidence of mandatory scientific failures")
    return {
        "status": "STRUCTURAL_PASS_REQUIRES_EXPERT_REVIEW" if not errors else "FAIL_OR_UNVERIFIED",
        "release_id": p.get("release_id"),
        "baseline_count": len(baselines),
        "mandatory_gates": gates,
        "scientific_failures_exercised": sorted(observed_failures),
        "errors": errors,
        "warning": "This checks recorded logic and log presence, not physical validity or hidden-label leakage.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pilot", required=True, type=Path)
    ap.add_argument("--root", type=Path)
    opt = ap.parse_args()
    try:
        d = json.loads(opt.pilot.read_text(encoding="utf-8"))
        r = audit(d, opt.root or opt.pilot.parent)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r["status"].startswith("STRUCTURAL_PASS") else 1
    except (OSError, ValueError, KeyError, TypeError) as ex:
        print(json.dumps({"status": "FAIL", "error": str(ex)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
