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

        # Structural uniqueness of outputs; cannot prove actual scientific distinction.
        broken = deepcopy(manifest)
        broken["checkpoints"][1]["output_file"] = broken["checkpoints"][0]["output_file"]
        issues, _ = validate_manifest(broken, root, final=False)
        assert any("duplicate output_file" in s for s in issues)
        broken = deepcopy(manifest)
        broken["checkpoints"][1]["truth_file"] = broken["checkpoints"][0]["truth_file"]
        issues, _ = validate_manifest(broken, root, final=False)
        assert any("duplicate private truth_file" in s for s in issues)

    print("PASS: manifest, independent scoring, subgroup gates, boundary, row order, invalid files, ZIP leak detection, duplicate outputs/truth")
    return 0


if __name__ == "__main__":
    sys.exit(main())
