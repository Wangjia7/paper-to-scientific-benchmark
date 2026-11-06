#!/usr/bin/env python3
"""Executable offline unit tests for benchmark preflight and scoring.

Synthetic fixture only. Does not need the original FP-lensing dataset.
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

from preflight import load_manifest, validate_manifest, scan_public_names, public_scorecard
from score import grade
from qc_matrix import validate_matrix, validate_audit
from qc_release import verify_release, digest

HERE = Path(__file__).resolve().parent
SAMPLE_MANIFEST = HERE.parent / "assets" / "benchmark_manifest.example.json"


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def fixture(tmp):
    manifest = deepcopy(load_manifest(SAMPLE_MANIFEST))
    tmp.joinpath("public").mkdir(exist_ok=True)
    submission = tmp / "submitted"
    submission.mkdir()
    truth_rows = {}
    prediction_rows = {}
    for k, cp in enumerate(manifest["checkpoints"]):
        gt_rows = []
        pred_rows = []
        for g_index, group in enumerate(cp["groups"]):
            for index in range(group["count"]):
                key = 1000 * (k + 1) + 100 * g_index + index
                # A representative zero allows an exact floating boundary test.
                label = 0.0 if k == 0 and g_index == 0 and index == 0 else (
                    (k + 1) * 0.02 + g_index * 0.03 + index * 0.001
                )
                gt_rows.append([key, format(label, ".17g"), group["id"]])
                pred_rows.append([key, format(label, ".17g")])
        write_csv(tmp / cp["truth_file"],
                  [cp["id_column"], cp["value_column"], cp["group_column"]], gt_rows)
        write_csv(submission / cp["output_file"],
                  [cp["id_column"], cp["value_column"]], pred_rows)
        truth_rows[cp["id"]] = gt_rows
        prediction_rows[cp["id"]] = pred_rows
    return manifest, submission, truth_rows, prediction_rows


def main():
    with tempfile.TemporaryDirectory(prefix="benchmark-skill-test-") as td:
        root = Path(td)
        manifest, sub, truth_rows, pred_rows = fixture(root)
        errors, warnings = validate_manifest(manifest, root, final=True)
        assert not errors, errors
        assert warnings, "must still require human review"
        scorecard = public_scorecard(manifest)
        assert "truth_file" not in json.dumps(scorecard)
        assert scorecard["pass_score"] == 80.0

        perfect = grade(manifest, root, sub)
        assert perfect["passed"] and abs(perfect["score"] - 100) < 1e-8
        assert len(perfect["checkpoints"]) == 3

        # Row order is not part of the scientific answer.
        cpa = manifest["checkpoints"][0]
        shuf = pred_rows["A"][:]
        random.Random(20261016).shuffle(shuf)
        write_csv(sub / cpa["output_file"], [cpa["id_column"], cpa["value_column"]], shuf)
        assert grade(manifest, root, sub)["score"] == perfect["score"]

        # Exactly at threshold succeeds, immediately outside fails. Data ID 1000 has truth 0.
        tol = cpa["groups"][0]["abs_tol"]
        changed = pred_rows["A"][:]
        changed[0] = [changed[0][0], repr(tol)]
        write_csv(sub / cpa["output_file"], [cpa["id_column"], cpa["value_column"]], changed)
        assert grade(manifest, root, sub)["checkpoints"]["A"]["groups"]["A1"]["passed"] == 10
        changed[0] = [changed[0][0], repr(tol + 1e-6)]
        write_csv(sub / cpa["output_file"], [cpa["id_column"], cpa["value_column"]], changed)
        partial = grade(manifest, root, sub)
        assert partial["checkpoints"]["A"]["groups"]["A1"]["passed"] == 9
        assert abs(partial["checkpoints"]["B"]["score"] - 30.0) < 1e-8
        assert abs(partial["checkpoints"]["C"]["score"] - 30.0) < 1e-8

        # File invalidity is local; total pass requires every independent task.
        cpb = manifest["checkpoints"][1]
        bad = pred_rows["B"][:]
        bad[0] = [bad[0][0], "NaN"]
        write_csv(sub / cpb["output_file"], [cpb["id_column"], cpb["value_column"]], bad)
        invalid = grade(manifest, root, sub)
        assert not invalid["valid_files"] and not invalid["passed"]
        assert invalid["checkpoints"]["B"]["score"] == 0
        assert invalid["checkpoints"]["A"]["score"] == partial["checkpoints"]["A"]["score"]
        assert invalid["checkpoints"]["C"]["score"] == 30.0

        # One group fails even when global score is >=80; the science gates remain binding.
        write_csv(sub / cpb["output_file"], [cpb["id_column"], cpb["value_column"]], pred_rows["B"])
        broken_a = pred_rows["A"][:]
        broken_a[:10] = [[row[0], "999"] for row in broken_a[:10]]
        write_csv(sub / cpa["output_file"], [cpa["id_column"], cpa["value_column"]], broken_a)
        gate_fail = grade(manifest, root, sub)
        assert gate_fail["score"] >= 80.0 and not gate_fail["passed"]
        assert gate_fail["checkpoints"]["A"]["groups"]["A1"]["passed"] == 0
        write_csv(sub / cpa["output_file"], [cpa["id_column"], cpa["value_column"]], changed)

        # Other malformed cases.
        for corrupt in (pred_rows["B"][:-1], pred_rows["B"] + pred_rows["B"][:1],
                        [[999999, "0.1"]] + pred_rows["B"][1:]):
            write_csv(sub / cpb["output_file"], [cpb["id_column"], cpb["value_column"]], corrupt)
            assert not grade(manifest, root, sub)["checkpoints"]["B"]["valid"]

        # Removing one file fails only that part.
        (sub / cpb["output_file"]).unlink()
        missing = grade(manifest, root, sub)
        assert not missing["passed"] and missing["checkpoints"]["B"]["score"] == 0
        assert missing["checkpoints"]["C"]["score"] == 30

        # Extreme finite numbers can overflow a subtraction or a square;
        # scorer must not produce nonstandard Infinity/NaN JSON or false PASS.
        write_csv(sub / cpb["output_file"], [cpb["id_column"], cpb["value_column"]], pred_rows["B"])
        extreme = [[row[0], "1e308" if j % 2 == 0 else "-1e308"]
                   for j, row in enumerate(pred_rows["B"])]
        write_csv(sub / cpb["output_file"], [cpb["id_column"], cpb["value_column"]], extreme)
        extreme_result = grade(manifest, root, sub)
        assert not extreme_result["passed"]
        assert extreme_result["checkpoints"]["B"]["score"] < 30.0
        json.dumps(extreme_result, allow_nan=False)
        assert extreme_result["checkpoints"]["B"]["rmse_diagnostic_only"] is None
        # Finite +/- 1e308 prediction and truth can overflow subtraction itself.
        huge_truth = [r[:] for r in truth_rows["B"]]
        huge_truth[0][1] = "-1e308"
        huge_pred = [r[:] for r in pred_rows["B"]]
        huge_pred[0][1] = "1e308"
        write_csv(root / cpb["truth_file"], [cpb["id_column"], cpb["value_column"], cpb["group_column"]], huge_truth)
        write_csv(sub / cpb["output_file"], [cpb["id_column"], cpb["value_column"]], huge_pred)
        overflow_result = grade(manifest, root, sub)
        assert overflow_result["checkpoints"]["B"]["score"] < 30.0
        assert overflow_result["checkpoints"]["B"]["rmse_diagnostic_only"] is None
        json.dumps(overflow_result, allow_nan=False)
        write_csv(root / cpb["truth_file"], [cpb["id_column"], cpb["value_column"], cpb["group_column"]], truth_rows["B"])
        write_csv(sub / cpb["output_file"], [cpb["id_column"], cpb["value_column"]], pred_rows["B"])
        # Strict row validation: extra and missing cells cannot be ignored.
        p_b = sub / cpb["output_file"]
        with p_b.open('a', encoding='utf-8') as f:
            f.write('1000,2.0,unexpected\n')
        malformed_result = grade(manifest, root, sub)
        assert malformed_result["checkpoints"]["B"]["score"] == 0.0
        assert not malformed_result["passed"]
        write_csv(p_b, [cpb["id_column"], cpb["value_column"]], pred_rows["B"])

        # Quality necessity gates are not implied by a continuous subscore.
        matrix = json.loads((HERE.parent / 'assets' / 'qc-coverage-matrix.example.json').read_text())
        assert not validate_matrix(matrix)
        missing_gate = deepcopy(matrix)
        missing_gate['gates'] = missing_gate['gates'][:-1]
        assert any('missing mandatory' in x for x in validate_matrix(missing_gate))
        keys = [g['gate_id'] for g in matrix['gates']]
        tests = {name: {'expected_pass': True, 'actual_pass': True} for name in matrix['required_tests']}
        audit = {'gate_results': {name: True for name in keys}, 'science_gate_pass': True,
                 'passed': True, 'test_results': tests, 'grader_sha256': 'example',
                 'run_command': 'python private/grader.py example', 'run_log_path': 'example.log'}
        assert not validate_audit(matrix, audit)
        audit['gate_results'][keys[0]] = False
        assert any('passed=true' in x for x in validate_audit(matrix, audit))
        audit['passed'] = False
        audit['science_gate_pass'] = False
        assert not validate_audit(matrix, audit)

        # Shared scientific experiment: three distinguishable judgments can share
        # one calibration/observation table, one private truth table and one CSV.
        shared = deepcopy(manifest)
        shared["allow_shared_tables"] = True
        shared["requirements"] = {"min_scientific_judgments": 3}
        joint_truth = []
        joint_output = []
        names = ["A", "B", "C"]
        weights = [40.0, 30.0, 30.0]
        truth_cols = ["case_id", "signal_A", "mechanism_B", "propagation_C", "case_group"]
        pred_cols = truth_cols[:-1]
        for cp, ident, weight in zip(shared["checkpoints"], names, weights):
            cp["judgment_id"] = ident
            cp["scientific_question"] = f"Distinct falsifiable claim {ident} in ONE study"
            cp["id_column"] = "case_id"
            cp["value_column"] = {"A": "signal_A", "B": "mechanism_B", "C": "propagation_C"}[ident]
            cp["group_column"] = "case_group"
            cp["truth_file"] = "private/shared_truth.csv"
            cp["output_file"] = "shared_predictions.csv"
            cp["groups"] = [{"id": "G", "count": 5, "abs_tol": 0.01, "weight": weight, "min_pass": 4}]
            cp["min_score"] = weight * 0.7
        for i in range(5):
            vals = [i, 0.1 * i, 1.0 + 0.2 * i, -0.15 + 0.3 * i]
            joint_truth.append([*vals, "G"])
            joint_output.append(vals)
        write_csv(root / "private/shared_truth.csv", truth_cols, joint_truth)
        write_csv(sub / "shared_predictions.csv", pred_cols, joint_output)
        errors, _ = validate_manifest(shared, root, final=True)
        assert not errors, errors
        full_shared = grade(shared, root, sub)
        assert full_shared["passed"] and full_shared["score"] == 100.0
        assert public_scorecard(shared)["allow_shared_tables"] is True
        assert "truth_file" not in json.dumps(public_scorecard(shared))
        damaged = [r[:] for r in joint_output]
        damaged[2][2] = "NaN"  # Only the B scientific conclusion is invalid.
        write_csv(sub / "shared_predictions.csv", pred_cols, damaged)
        invalid_shared = grade(shared, root, sub)
        assert not invalid_shared["passed"]
        assert invalid_shared["checkpoints"]["A"]["score"] == 40.0
        assert invalid_shared["checkpoints"]["B"]["score"] == 0.0
        assert invalid_shared["checkpoints"]["C"]["score"] == 30.0
        write_csv(sub / "shared_predictions.csv", pred_cols, joint_output)

        # Splitting one scientific judgment into three checkpoints must NOT pass
        # the requirement for three scientifically different conclusions.
        disguised = deepcopy(shared)
        for cp in disguised["checkpoints"]:
            cp["judgment_id"] = "SAME_JUDGMENT"
        errors, _ = validate_manifest(disguised, root, final=False)
        assert any("distinct judgment_id" in e for e in errors), errors

        # An explicit different platform may require two judgments rather than
        # three; never hardcode three separate experiments as a global rule.
        two = deepcopy(shared)
        two["checkpoints"] = two["checkpoints"][:2]
        two["requirements"]["min_scientific_judgments"] = 2
        two["checkpoints"][0]["groups"][0]["weight"] = 50.0
        two["checkpoints"][1]["groups"][0]["weight"] = 50.0
        errors, _ = validate_manifest(two, root, final=True)
        assert not errors, errors
        assert grade(two, root, sub)["score"] == 100.0

        # Shared files must be an explicit schema choice, and shared scientific
        # columns must not silently collapse into one target.
        denied = deepcopy(shared)
        denied["allow_shared_tables"] = False
        errors, _ = validate_manifest(denied, root, final=False)
        assert any("duplicate output_file" in e for e in errors)
        collapsed = deepcopy(shared)
        collapsed["checkpoints"][1]["value_column"] = "signal_A"
        errors, _ = validate_manifest(collapsed, root, final=False)
        assert any("distinct scientific value columns" in e for e in errors)

        # Obvious public ZIP/file leak names are flagged, including nested names.
        flagged = root / "public" / "private"
        flagged.mkdir(exist_ok=True)
        (flagged / "blind_truth.csv").write_text("not actually a truth\n", encoding="utf-8")
        assert scan_public_names(root / "public")
        (flagged / "blind_truth.csv").unlink()
        flagged.rmdir()
        assert not scan_public_names(root / "public")
        with ZipFile(root / "public" / "agent.zip", "w") as zf:
            zf.writestr("private/blind_truth.csv", "SECRET")
        assert scan_public_names(root / "public"), "ZIP internal path should be checked"
        (root / "public" / "agent.zip").unlink()

        # Reviewer pack conformance requires all actual artifacts, logs, and
        # archived public/private segregation; tests cannot be just declared.
        import zipfile
        package = deepcopy(json.loads((HERE.parent / 'assets' / 'qc-release-manifest.example.json').read_text()))
        filepaths = package['required_files']
        for role, rel in filepaths.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if role == 'audit_log':
                continue
            path.write_bytes(b'demo content')
        for kind in ('public_zip', 'private_zip'):
            with ZipFile(root / package[kind], 'w') as z:
                if kind=='public_zip':
                    z.writestr('public/README_AGENT.md', 'a public document')
                    z.writestr('public/SCHEMA.json', '{}')
                else:
                    for role in ('generator','grader','reference_solver','hidden_truth','audit_script'):
                        z.writestr(filepaths[role], 'a reviewer-only file')
        audit_checks = {}
        for label in package['required_check_names']:
            logfile = f'private/logs/{label}.log'
            f = root / logfile
            f.parent.mkdir(exist_ok=True)
            f.write_text('DEMO ONLY (unit-test fixture)', encoding='utf-8')
            audit_checks[label] = {'passed': True, 'exit_code': 0, 'log_path': logfile}
        audit = {'checks': audit_checks, 'grader_sha256': digest(root / filepaths['grader']),
                 'commands': {'public_only_reference': 'python reference_solver.py out',
                              'private_grade': 'python private/grader.py out'}}
        (root / filepaths['audit_log']).write_text(json.dumps(audit), encoding='utf-8')
        with ZipFile(root / package['private_zip'], 'a') as z:
            z.writestr(filepaths['audit_log'], json.dumps(audit))
        assert not verify_release(root, package), verify_release(root, package)
        # Even with a passing audit file, a removed log or modified grader
        # must invalidate reviewer release evidence.
        (root / 'private/logs/REFERENCE_PASSES.log').unlink()
        assert any('actual log' in x for x in verify_release(root, package))
        (root / 'private/logs/REFERENCE_PASSES.log').write_text('DEMO ONLY', encoding='utf-8')
        (root / filepaths['grader']).write_text('CHANGED GRADER', encoding='utf-8')
        assert any('stale audit' in x for x in verify_release(root, package))
        # A hidden truth in the Agent ZIP is always a release blocker.
        with ZipFile(root / package['public_zip'], 'w') as z:
            z.writestr('public/data.csv', 'safe')
            z.writestr('private/truth.npz', 'LEAK')
        assert any('private/suspicious' in x for x in verify_release(root, package))

        # Structural uniqueness of outputs; cannot prove actual scientific distinction.
        broken = deepcopy(manifest)
        broken["checkpoints"][1]["output_file"] = broken["checkpoints"][0]["output_file"]
        issues, _ = validate_manifest(broken, root, final=False)
        assert any("duplicate output_file" in s for s in issues)
        broken = deepcopy(manifest)
        broken["checkpoints"][1]["truth_file"] = broken["checkpoints"][0]["truth_file"]
        issues, _ = validate_manifest(broken, root, final=False)
        assert any("duplicate private truth_file" in s for s in issues)

    print("PASS: legacy/shared scientific scoring, anti-compensation matrix, audit gates, float64 extreme loss safety, strict CSV, boundaries, row order, independent invalidity, ZIP leak and reviewer pack checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
