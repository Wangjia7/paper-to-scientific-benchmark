#!/usr/bin/env python3
"""Structural (not scientific) preflight for a paper-derived benchmark.

Uses only the Python standard library. A pass cannot establish scientific
identifiability, decision independence, or absence of covert label leakage.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile

SUSPICIOUS_PUBLIC_PATH = re.compile(
    r"(^|[/_\\])(private|hidden|blind_truth|association_truth|instrument_truth|"
    r"grade_v\d*|grade|grader|score_truth|scorer|answer_key|reference_solution|reference_baseline|"
    r"build_data|build_extra|secret_keys)(?=[/_.\\]|$)", re.IGNORECASE
)


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError("manifest must be a JSON object")
    return document


def valid_text(value: object) -> bool:
    return isinstance(value, str) and len(value.strip()) > 0


def is_nonnegative_number(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def safe_relative(root: Path, relative: str) -> bool:
    if not valid_text(relative):
        return False
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        return False
    try:
        (root / rel).resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_manifest(manifest: dict, root: Path, final: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    title = manifest.get("title")
    if not valid_text(title):
        errors.append("missing title")
    if not valid_text(manifest.get("paper")):
        errors.append("missing paper source identifier")
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("missing runtime configuration")
    else:
        cpus, ram, hours = (runtime.get(k) for k in ("cpu_cores", "ram_gb", "max_hours"))
        if any(not is_nonnegative_number(x) or x == 0 for x in (cpus, ram, hours)):
            errors.append("runtime cpu_cores, ram_gb and max_hours must be positive")
        if any(is_nonnegative_number(x) and x > cap for x, cap in ((cpus, 8), (ram, 16), (hours, 5))):
            warnings.append("runtime exceeds the 8 CPU/16 GB/5 h benchmark defaults; check platform")
        if runtime.get("gpu_required") is True:
            warnings.append("GPU marked required; this exceeds the no-GPU benchmark default")
    total_pass_score = manifest.get("pass_score")
    if not is_nonnegative_number(total_pass_score):
        errors.append("pass_score must be finite and nonnegative")
    requirements = manifest.get("requirements", {})
    if not isinstance(requirements, dict):
        errors.append("requirements must be an object")
        requirements = {}
    # The default of 3 matches this user's platform review, NOT a universal benchmark law.
    minimum = requirements.get("min_scientific_judgments", 3)
    if type(minimum) is not int or minimum < 1:
        errors.append("requirements.min_scientific_judgments must be a positive integer")
        minimum = 3
    allow_shared = manifest.get("allow_shared_tables", False)
    if type(allow_shared) is not bool:
        errors.append("allow_shared_tables must be boolean")
        allow_shared = False
    entries = manifest.get("checkpoints")
    if not isinstance(entries, list) or not entries:
        errors.append("checkpoints must be a nonempty list")
        return errors, warnings

    ids, judgment_ids, output_files, truth_files, targets, combined_evidence = (
        set(), set(), {}, {}, set(), []
    )
    all_weight = 0.0
    min_possible_sum = 0.0
    for idx, cp in enumerate(entries):
        prefix = f"checkpoint[{idx}]"
        if not isinstance(cp, dict):
            errors.append(f"{prefix} is not an object")
            continue
        cid = cp.get("id")
        if not valid_text(cid) or cid in ids:
            errors.append(f"{prefix} missing/duplicate id: {cid!r}")
        else:
            ids.add(cid)
        # Several scoring checkpoints may belong to one scientific judgment.
        # Counting file names or checkpoint IDs does NOT establish independence.
        judgment = cp.get("judgment_id", cid)
        if not valid_text(judgment):
            errors.append(f"{prefix} missing judgment_id")
        else:
            judgment_ids.add(judgment)
        for field in ("scientific_question", "scientific_decision", "truth_provenance",
                      "id_column", "value_column", "output_file", "group_column", "truth_file"):
            if not valid_text(cp.get(field)):
                errors.append(f"{prefix} missing {field}")
        target = cp.get("target")
        if not isinstance(target, dict) or not all(valid_text(target.get(k)) for k in ("name", "unit")):
            errors.append(f"{prefix} target must include name and unit")
        else:
            key = target["name"]
            if key in targets:
                warnings.append(f"{prefix} target {key!r} repeats another target; manually prove independence")
            targets.add(key)
        evidence = cp.get("evidence")
        if not isinstance(evidence, list) or len(evidence) < 1 or any(not valid_text(s) for s in evidence):
            errors.append(f"{prefix} evidence must be a nonempty list of descriptions")
        else:
            eset = frozenset(evidence)
            if eset in combined_evidence:
                warnings.append(f"{prefix} shares described evidence; confirm distinct falsifiable conclusions (shared experiments are allowed)")
            combined_evidence.append(eset)
        filename = cp.get("output_file")
        if valid_text(filename):
            prev = output_files.get(filename)
            if prev is not None:
                if not allow_shared:
                    errors.append(f"duplicate output_file {filename!r}; use allow_shared_tables=true for shared CSVs")
                elif (cp.get("id_column") != prev.get("id_column") or
                      cp.get("value_column") == prev.get("value_column")):
                    errors.append(f"{prefix} shared output_file {filename!r} needs a common ID column and distinct scientific value columns")
            else:
                output_files[filename] = cp
            if Path(filename).name != filename or not filename.endswith(".csv"):
                errors.append(f"{prefix} output_file must be a CSV basename")
        if valid_text(cp.get("truth_file")):
            truth_filename = cp["truth_file"]
            prev_truth = truth_files.get(truth_filename)
            if prev_truth is not None:
                if not allow_shared:
                    errors.append(f"duplicate private truth_file {truth_filename!r}; use allow_shared_tables=true for shared CSVs")
                elif (cp.get("id_column") != prev_truth.get("id_column") or
                      cp.get("value_column") == prev_truth.get("value_column")):
                    errors.append(f"{prefix} shared truth_file {truth_filename!r} needs a common ID column and distinct scientific value columns")
            else:
                truth_files[truth_filename] = cp
            if not safe_relative(root, truth_filename):
                errors.append(f"{prefix} truth_file not safely inside project root")
            elif final and not (root / truth_filename).is_file():
                errors.append(f"{prefix} missing truth_file: {truth_filename}")
        groups = cp.get("groups")
        if not isinstance(groups, list) or not groups:
            errors.append(f"{prefix} has no scoring groups")
            continue
        weight = 0.0
        group_ids = set()
        for j, g in enumerate(groups):
            gp = f"{prefix}.groups[{j}]"
            if not isinstance(g, dict):
                errors.append(f"{gp} not object")
                continue
            gid = g.get("id")
            if not valid_text(gid) or gid in group_ids:
                errors.append(f"{gp} missing/duplicate group id")
            group_ids.add(gid)
            for fn in ("count", "min_pass"):
                val = g.get(fn)
                if type(val) is not int or val < (1 if fn == "count" else 0):
                    errors.append(f"{gp} {fn} must be an allowed integer")
            if type(g.get("count")) is int and type(g.get("min_pass")) is int and g["min_pass"] > g["count"]:
                errors.append(f"{gp} min_pass > count")
            for fn in ("abs_tol", "weight"):
                val = g.get(fn)
                if not is_nonnegative_number(val) or (fn == "weight" and val == 0):
                    errors.append(f"{gp} {fn} must be valid nonnegative numeric")
            if is_nonnegative_number(g.get("weight")):
                weight += float(g["weight"])
        all_weight += weight
        min_score = cp.get("min_score")
        if not is_nonnegative_number(min_score) or min_score > weight:
            errors.append(f"{prefix} min_score must be between 0 and {weight}")
        else:
            min_possible_sum += min_score
    if len(judgment_ids) < minimum:
        errors.append(
            f"only {len(judgment_ids)} distinct judgment_id values; platform requires {minimum} "
            "scientific judgments (NOT separate experiments or separate datasets)"
        )
    if abs(all_weight - 100.0) > 1e-8:
        errors.append(f"group weights sum to {all_weight:g}; expected 100")
    if is_nonnegative_number(total_pass_score) and total_pass_score > all_weight:
        errors.append("pass_score exceeds total weight")
    if is_nonnegative_number(total_pass_score) and min_possible_sum > all_weight:
        errors.append("sum(min_score) exceeds total score")
    warnings.append("Manual review REQUIRED: distinct judgment_id values or separate files cannot prove genuinely different scientific interpretations; one shared experiment is allowed")
    return errors, warnings


def scan_public_names(public_dir: Path) -> list[str]:
    errors: list[str] = []
    if not public_dir.is_dir():
        return errors
    for f in public_dir.rglob("*"):
        rel_name = f.relative_to(public_dir).as_posix()
        if SUSPICIOUS_PUBLIC_PATH.search(rel_name):
            errors.append(f"suspicious public path: {rel_name}")
        if f.is_file() and f.suffix.lower() == ".zip":
            try:
                with ZipFile(f) as zf:
                    for member in zf.namelist():
                        if SUSPICIOUS_PUBLIC_PATH.search(member):
                            errors.append(f"suspicious public ZIP member: {rel_name}::{member}")
            except BadZipFile:
                errors.append(f"invalid ZIP: {rel_name}")
    return errors


def public_scorecard(manifest: dict) -> dict:
    """Deliberately omit truth paths, actual values and ID->group mappings."""
    return {
        "title": manifest.get("title"),
        "pass_score": manifest.get("pass_score"),
        "requirements": manifest.get("requirements", {"min_scientific_judgments": 3}),
        "allow_shared_tables": manifest.get("allow_shared_tables", False),
        "scoring": "group_weight * n_with_absolute_error_le_abs_tol / group_count",
        "validity": "per-checkpoint invalid CSV = zero for that checkpoint; total_pass false",
        "checkpoints": [
            {
                "id": cp["id"], "judgment_id": cp.get("judgment_id", cp["id"]), "scientific_question": cp["scientific_question"],
                "target": cp["target"], "output_file": cp["output_file"],
                "id_column": cp["id_column"], "value_column": cp["value_column"],
                "min_score": cp["min_score"],
                "groups": cp["groups"],
                "expected_row_count": sum(g["count"] for g in cp["groups"]),
            }
            for cp in manifest["checkpoints"]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--public-dir", type=Path, default=None)
    parser.add_argument("--final", action="store_true", help="also require private truth files to exist")
    parser.add_argument("--emit-public-scorecard", type=Path, default=None)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        errors, warnings = validate_manifest(manifest, args.root, final=args.final)
        if args.public_dir is not None:
            errors.extend(scan_public_names(args.public_dir))
        for problem in errors:
            print("ERROR:", problem)
        for warning in warnings:
            print("WARN:", warning)
        if args.emit_public_scorecard and not errors:
            args.emit_public_scorecard.parent.mkdir(parents=True, exist_ok=True)
            args.emit_public_scorecard.write_text(
                json.dumps(public_scorecard(manifest), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("WROTE:", args.emit_public_scorecard)
        print(f"PREFLIGHT: {'FAIL' if errors else 'PASS (structural only)'}; {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1 if errors else 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("ERROR:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
