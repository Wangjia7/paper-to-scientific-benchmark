#!/usr/bin/env python3
"""Pre-upload immutable release identity check. Python stdlib only.

Check a matching public/private ZIP pair against a previously frozen release
contract. This script does NOT run a private grader, judge scientific difficulty,
confirm uploads to a platform, or grant claim of external approval.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from zipfile import ZipFile, BadZipFile


class ReleaseError(ValueError):
    pass


def insist(predicate: bool, detail: str) -> None:
    if not predicate:
        raise ReleaseError(detail)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_zip(z: ZipFile, label: str) -> list[str]:
    # ZIP has no reliable path-level access control; reject directories except
    # for benign explicit entries, and any entry that could escape extraction.
    infos = [x for x in z.infolist() if not x.is_dir()]
    paths = [x.filename for x in infos]
    insist(len(paths) == len(set(paths)), f"{label}: duplicate ZIP member")
    for info in infos:
        p = PurePosixPath(info.filename)
        insist(not p.is_absolute() and ".." not in p.parts and "\\" not in info.filename,
               f"{label}: unsafe ZIP member {info.filename!r}")
        insist((info.external_attr >> 16) & stat.S_IFMT(0o777777) != stat.S_IFLNK,
               f"{label}: symlink ZIP member {info.filename!r}")
    # An intentional full CRC run; archive sizes are constrained by task budget.
    insist(z.testzip() is None, f"{label}: corrupt ZIP member/CRC")
    return paths


def public_manifest_artifacts(m: dict) -> dict[str, dict]:
    if isinstance(m.get("public_artifacts"), list):
        a = m["public_artifacts"]
        insist(all(isinstance(x, dict) and isinstance(x.get("filename"), str) for x in a),
               "public manifest: invalid public_artifacts")
        names = [x["filename"] for x in a]
        insist(len(names) == len(set(names)), "public manifest: duplicate filename")
        return {x["filename"]: x for x in a}
    if isinstance(m.get("artifacts"), dict):
        return m["artifacts"]
    raise ReleaseError("public manifest: expected public_artifacts list or artifacts mapping")


def check_csv_template(z: ZipFile, spec: dict) -> None:
    name = spec["member"]
    key = spec["id_column"]
    try:
        raw = z.read(name).decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ReleaseError(f"{name}: not UTF-8") from e
    # csv.reader(strict=True) by itself does NOT validate row widths.
    rows = list(csv.reader(io.StringIO(raw, newline=""), strict=True))
    insist(bool(rows), f"{name}: empty CSV")
    header = rows.pop(0)
    insist(len(set(header)) == len(header), f"{name}: duplicate header fields")
    if "header" in spec:
        insist(header == spec["header"], f"{name}: incorrect header {header!r}")
    insist(key in header, f"{name}: ID column {key} absent")
    insist(all(len(r) == len(header) for r in rows), f"{name}: malformed physical column count")
    insist(len(rows) == spec["rows"],
           f"{name}: expected {spec['rows']} rows, got {len(rows)}")
    idx = header.index(key)
    ids = [r[idx] for r in rows]
    insist(all(ids), f"{name}: empty ID")
    insist(len(ids) == len(set(ids)), f"{name}: duplicate ID")
    if "id_regex" in spec:
        pattern = re.compile(spec["id_regex"], re.ASCII)
        insist(all(pattern.fullmatch(s) for s in ids), f"{name}: non-canonical ID")


def check(contract: dict, public: Path, private: Path, task_text: Path | None = None) -> dict:
    rid = contract["release_id"]
    schema = str(contract["schema_version"])
    pubspec = contract["public"]
    privspec = contract["private"]
    insist(bool(rid), "empty release_id")
    with ZipFile(public) as p, ZipFile(private) as q:
        a, b = inspect_zip(p, "public"), inspect_zip(q, "private")
        pubset, privset = set(a), set(b)
        insist(len(a) == pubspec["file_count"],
               f"public file count mismatch: expected {pubspec['file_count']}, got {len(a)}")
        insist(set(pubspec.get("required_members", [])).issubset(pubset),
               f"public missing required members {sorted(set(pubspec.get('required_members', []))-pubset)}")
        insist(set(privspec.get("required_members", [])).issubset(privset),
               f"private missing required members {sorted(set(privspec.get('required_members', []))-privset)}")
        if "min_file_count" in privspec:
            insist(len(b) >= privspec["min_file_count"], "private incomplete file count")
        insist(not any(x.startswith("private/") or any(part in {"truth", "oracle", "hidden_scoring"}
                   for part in re.split(r"[/_.-]", x.lower())) or
                   x.lower().endswith(("/grader.py", "/grade_v4.py", "/reference_solver.py"))
                   for x in a), "public contains private-only material")
        manifest_name = pubspec.get("manifest", "benchmark_manifest.json")
        insist(manifest_name in pubset, f"missing public manifest {manifest_name}")
        m = json.loads(p.read(manifest_name))
        insist(m.get("bundle_id") == rid,
               f"public bundle_id mismatch: {m.get('bundle_id')} != {rid}")
        actual_schema = str(m.get("schema_version", m.get("schema")))
        insist(actual_schema == schema,
               f"public schema mismatch: {actual_schema} != {schema}")
        listed = public_manifest_artifacts(m)
        insist(set(listed) == pubset - {manifest_name},
               "public manifest does not match exact archive member set")
        for filename, info in listed.items():
            data = p.read(filename)
            insist(info.get("bytes") == len(data), f"{filename}: size mismatch")
            insist(info.get("sha256") == hashlib.sha256(data).hexdigest(),
                   f"{filename}: SHA-256 mismatch")
        for spec in pubspec.get("csv_templates", []):
            check_csv_template(p, spec)
        if "readme" in pubspec:
            rtext = p.read(pubspec["readme"]).decode("utf-8")
            insist(rid in rtext, "public README does not carry release_id")
        if "reviewer_readme" in privspec:
            rtext = q.read(privspec["reviewer_readme"]).decode("utf-8")
            insist(rid in rtext, "private README does not carry release_id")
        if "scoring_contract" in pubspec:
            c = json.loads(p.read(pubspec["scoring_contract"]))
            insist(c.get("bundle_id") == rid, "scoring contract release_id mismatch")
    if task_text is not None:
        text = task_text.read_text(encoding="utf-8")
        for token in [rid] + contract.get("task_text_required_tokens", []):
            insist(token in text, f"task text missing required token: {token}")
    return {
        "status": "STRUCTURAL_PASS_NOT_SCIENCE_CERTIFICATION",
        "release_id": rid,
        "schema_version": schema,
        "public_file_count": len(a),
        "private_file_count": len(b),
        "public_sha256": file_sha256(public),
        "private_sha256": file_sha256(private),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--public", required=True, type=Path)
    ap.add_argument("--private", required=True, type=Path)
    ap.add_argument("--task", type=Path, default=None)
    opt = ap.parse_args()
    try:
        contract = json.loads(opt.contract.read_text(encoding="utf-8"))
        result = check(contract, opt.public, opt.private, opt.task)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, BadZipFile, KeyError, TypeError, ValueError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
