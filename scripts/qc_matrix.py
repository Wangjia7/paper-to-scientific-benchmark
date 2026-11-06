#!/usr/bin/env python3
"""Check SCIENCE NECESSITY gate coverage; optionally check an audit-status JSON.

This is a contract preflight, NOT a scientific proof and NOT a replacement
for executing the benchmark-specific grader and keeping original logs.

Usage:
  python scripts/qc_matrix.py --matrix assets/qc-coverage-matrix.example.json
  python scripts/qc_matrix.py --matrix private/quality_gates.json --audit private/QC_STATUS.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


class ContractError(ValueError):
    pass


def _nonempty_string(s):
    return isinstance(s, str) and bool(s.strip())


def validate_matrix(m):
    errors = []
    if not isinstance(m, dict):
        return ["QC matrix must be an object"]
    domains = m.get("mandatory_domains")
    targets = m.get("mandatory_targets")
    gates = m.get("gates")
    if not isinstance(domains, list) or not domains or any(not _nonempty_string(x) for x in domains):
        errors.append("mandatory_domains: nonempty string list required")
        domains = []
    if len(set(domains)) != len(domains):
        errors.append("mandatory_domains has duplicates")
    if not isinstance(targets, list) or not targets or any(not _nonempty_string(x) for x in targets):
        errors.append("mandatory_targets: nonempty string list required")
        targets = []
    if len(set(targets)) != len(targets):
        errors.append("mandatory_targets has duplicates")
    if not isinstance(gates, list) or not gates:
        errors.append("gates: nonempty list required")
        gates = []
    ids = set()
    cells = set()
    for j, gate in enumerate(gates):
        if not isinstance(gate, dict):
            errors.append(f"gate[{j}] must be an object")
            continue
        ident = gate.get("gate_id")
        domain = gate.get("domain")
        target = gate.get("target")
        if not _nonempty_string(ident) or ident in ids:
            errors.append(f"gate[{j}]: missing/duplicate gate_id")
        ids.add(ident)
        if domain not in domains or target not in targets:
            errors.append(f"gate[{j}]: unknown domain/target")
        pair = (domain, target)
        if pair in cells:
            errors.append(f"gate[{j}]: duplicate mandatory cell {pair}")
        cells.add(pair)
        if gate.get("operator") not in ("<=", "<", ">=", ">", "=="):
            errors.append(f"gate[{j}]: public comparison operator missing")
        t = gate.get("threshold")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            errors.append(f"gate[{j}]: threshold must be finite numeric")
        if not _nonempty_string(gate.get("threshold_provenance")):
            errors.append(f"gate[{j}]: threshold provenance required")
        if gate.get("public") is not True:
            errors.append(f"gate[{j}]: scientific hard gate must be public")
    expected = {(d, t) for d in domains for t in targets}
    missing = sorted(expected - cells)
    if missing:
        errors.append(f"missing mandatory domain×target cells: {missing}")
    if cells - expected:
        errors.append(f"unexpected gate cells: {sorted(cells - expected)}")
    logic = m.get("final_pass_logic", "")
    if not _nonempty_string(logic) or "all(mandatory_gates)" not in logic:
        errors.append("final_pass_logic must explicitly AND all(mandatory_gates)")
    tests = m.get("required_tests")
    if not isinstance(tests, list) or not tests or any(not _nonempty_string(x) for x in tests):
        errors.append("required_tests: nonempty string list required")
    elif len(set(tests)) != len(tests):
        errors.append("required_tests contains duplicates")
    return errors


def validate_audit(matrix, audit):
    errors = []
    if not isinstance(audit, dict):
        return ["QC audit must be an object"]
    names = [gate["gate_id"] for gate in matrix["gates"]]
    gate_state = audit.get("gate_results")
    if not isinstance(gate_state, dict) or set(gate_state) != set(names):
        errors.append("audit.gate_results missing/extra gate IDs")
    elif any(type(gate_state[x]) is not bool for x in names):
        errors.append("audit.gate_results must be booleans")
    else:
        science_ok = all(gate_state.values())
        if audit.get("science_gate_pass") is not science_ok:
            errors.append("audit.science_gate_pass inconsistent with logical AND of all gates")
        if audit.get("passed") is True and not science_ok:
            errors.append("audit.passed=true even though a mandatory gate failed")
    required = set(matrix["required_tests"])
    tests = audit.get("test_results")
    if not isinstance(tests, dict):
        errors.append("audit.test_results missing")
    else:
        missing = required - set(tests)
        if missing:
            errors.append(f"audit missing required executed tests: {sorted(missing)}")
        for name, item in tests.items():
            if not isinstance(item, dict) or type(item.get("expected_pass")) is not bool or type(item.get("actual_pass")) is not bool:
                errors.append(f"audit test {name}: expected_pass and actual_pass booleans required")
            elif item["expected_pass"] != item["actual_pass"]:
                errors.append(f"audit test {name}: actual result disagrees with expectation")
    for field in ("grader_sha256", "run_command", "run_log_path"):
        if not _nonempty_string(audit.get(field)):
            errors.append(f"audit missing provenance: {field}")
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix", required=True, type=Path)
    p.add_argument("--audit", type=Path)
    ns = p.parse_args()
    try:
        matrix = json.loads(ns.matrix.read_text(encoding="utf-8"))
        errors = validate_matrix(matrix)
        if not errors and ns.audit:
            audit = json.loads(ns.audit.read_text(encoding="utf-8"))
            errors.extend(validate_audit(matrix, audit))
    except (OSError, ValueError, json.JSONDecodeError) as e:
        errors = [str(e)]
    for err in errors:
        print("ERROR:", err)
    print("QC_MATRIX:", "FAIL" if errors else "PASS (declaration/audit logic only)")
    if not ns.audit and not errors:
        print("NOTE: No grader was run. Provide --audit and original test logs before claiming actual QC completion.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
