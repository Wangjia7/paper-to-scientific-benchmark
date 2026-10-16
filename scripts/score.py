#!/usr/bin/env python3
"""Reference deterministic CSV score engine for multi-judgment scientific tasks.

The private manifest and private truth must NEVER be shipped to the solver.
Score only solver output CSVs, independent of solution code and prose.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

from preflight import load_manifest, validate_manifest

INTEGER = re.compile(r"[+-]?[0-9]+\Z")


class DataError(ValueError):
    pass


def _parse_id(value: str, label: str) -> int:
    if not isinstance(value, str) or not INTEGER.fullmatch(value):
        raise DataError(f"{label}: invalid integer ID {value!r}")
    return int(value)


def _parse_float(value: str, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise DataError(f"{label}: invalid float {value!r}") from None
    if not math.isfinite(result):
        raise DataError(f"{label}: nonfinite float {value!r}")
    return result


def _read_csv(path: Path, expected_header: list[str], allow_extra: bool = False) -> tuple[list[str], list[list[str]]]:
    """Read a CSV, optionally selecting different target columns from one shared table.

    Multiple scientific judgments may share the same observation and truth file.
    Column validity and numeric scoring remain per judgment; wrong schema is
    still an objective per-judgment failure.
    """
    if not path.is_file():
        raise DataError(f"missing file: {path.name}")
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            if not isinstance(header, list) or not header or any(not name for name in header) or len(set(header)) != len(header):
                raise DataError(f"{path.name}: missing/empty/duplicate header names")
            if (not allow_extra and header != expected_header) or (allow_extra and not set(expected_header).issubset(header)):
                raise DataError(f"{path.name}: header {header!r} incompatible with required columns {expected_header!r}")
            records = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise DataError(f"{path.name}: invalid CSV encoding/quoting: {exc}") from exc
    for line, row in enumerate(records, 2):
        if len(row) != len(header):
            raise DataError(f"{path.name}:{line}: expected {len(header)} columns, got {len(row)}")
    return header, records


def _truth(cp: dict, root: Path, allow_shared: bool = False) -> dict[int, tuple[float, str]]:
    path = root / cp["truth_file"]
    groups = {g["id"]: g for g in cp["groups"]}
    cols = [cp["id_column"], cp["value_column"], cp["group_column"]]
    header, records = _read_csv(path, cols, allow_extra=allow_shared)
    idpos, valuepos, grouppos = (header.index(col) for col in cols)
    out: dict[int, tuple[float, str]] = {}
    group_counts = {g: 0 for g in groups}
    for line, row in enumerate(records, 2):
        key = _parse_id(row[idpos], f"truth:{path.name}:{line}")
        if key in out:
            raise DataError(f"truth:{path.name}:{line}: duplicate ID {key}")
        value = _parse_float(row[valuepos], f"truth:{path.name}:{line}")
        group = row[grouppos]
        if group not in groups:
            raise DataError(f"truth:{path.name}:{line}: unknown group {group}")
        out[key] = (value, group)
        group_counts[group] += 1
    for group, count in group_counts.items():
        if count != groups[group]["count"]:
            raise DataError(f"truth:{path.name}: {group}: count {count} != {groups[group]['count']}")
    return out


def _predictions(cp: dict, submission_dir: Path, expected_ids: set[int], allow_shared: bool = False) -> dict[int, float]:
    filename = cp["output_file"]
    cols = [cp["id_column"], cp["value_column"]]
    header, rows = _read_csv(submission_dir / filename, cols, allow_extra=allow_shared)
    idpos, valuepos = (header.index(col) for col in cols)
    if len(rows) != len(expected_ids):
        raise DataError(f"{filename}: {len(rows)} rows != {len(expected_ids)} expected")
    values: dict[int, float] = {}
    for line, row in enumerate(rows, 2):
        key = _parse_id(row[idpos], f"prediction:{filename}:{line}")
        if key in values:
            raise DataError(f"{filename}:{line}: duplicate ID {key}")
        values[key] = _parse_float(row[valuepos], f"prediction:{filename}:{line}")
    if values.keys() != expected_ids:
        missing = sorted(expected_ids - values.keys())[:5]
        extra = sorted(values.keys() - expected_ids)[:5]
        raise DataError(f"{filename}: mismatched ID set (missing {missing}, extra {extra})")
    return values


def grade(manifest: dict, root: Path, submission: Path) -> dict[str, Any]:
    errors, _warnings = validate_manifest(manifest, root, final=True)
    if errors:
        raise DataError("invalid benchmark manifest: " + "; ".join(errors))
    allow_shared = manifest.get("allow_shared_tables", False)
    total = 0.0
    valid_files = True
    all_checkpoints_ok = True
    checkpoints = {}
    for cp in manifest["checkpoints"]:
        ident = cp["id"]
        truth = _truth(cp, root, allow_shared=allow_shared)
        try:
            pred = _predictions(cp, submission, set(truth), allow_shared=allow_shared)
        except DataError as exc:
            valid_files = False
            all_checkpoints_ok = False
            checkpoints[ident] = {
                "valid": False, "error": str(exc), "score": 0.0,
                "min_score": cp["min_score"], "meets_gate": False, "groups": {}
            }
            continue
        per_group = {}
        score = 0.0
        group_gates_ok = True
        sqerr = 0.0
        for g in cp["groups"]:
            gid = g["id"]
            indices = [key for key, (_value, label) in truth.items() if label == gid]
            passed = 0
            for key in indices:
                err = pred[key] - truth[key][0]
                sqerr += err * err
                if abs(err) <= g["abs_tol"]:
                    passed += 1
            points = g["weight"] * passed / g["count"]
            score += points
            group_ok = passed >= g["min_pass"]
            group_gates_ok &= group_ok
            per_group[gid] = {
                "passed": passed, "total": g["count"], "points": points,
                "weight": g["weight"], "group_min_pass": g["min_pass"],
                "meets_gate": group_ok
            }
        meets_gate = (score >= cp["min_score"] and group_gates_ok)
        all_checkpoints_ok &= meets_gate
        total += score
        checkpoints[ident] = {
            "valid": True, "score": score, "min_score": cp["min_score"],
            "meets_gate": meets_gate, "rmse_diagnostic_only": math.sqrt(sqerr / len(truth)),
            "groups": per_group
        }
    return {
        "score": total, "pass_score": manifest["pass_score"],
        "valid_files": valid_files,
        "passed": valid_files and all_checkpoints_ok and total >= manifest["pass_score"],
        "checkpoints": checkpoints
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    try:
        data = load_manifest(args.manifest)
        report = grade(data, args.root, args.submission)
        output = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output, encoding="utf-8")
        print(output, end="")
        return 0
    except (DataError, ValueError, OSError, KeyError) as exc:
        print("SCORER CONFIGURATION ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
