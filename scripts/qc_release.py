#!/usr/bin/env python3
"""Check that the private REVIEWER package is present, separated and audited.

Usage: python scripts/qc_release.py --root actual_benchmark_dir \
          --manifest actual_benchmark_dir/private/qc_release_manifest.json
This checks file existence, archive segregation, grader SHA and evidence shape.
It CANNOT prove log authenticity, scientific correctness or future platform pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile
from preflight import SUSPICIOUS_PUBLIC_PATH


class ReleaseError(ValueError):
    pass


def _within(root: Path, path: str) -> Path:
    p = PurePosixPath(path)
    if not path or p.is_absolute() or '..' in p.parts or p.parts[0] == '.':
        raise ReleaseError(f"unsafe relative path: {path!r}")
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ReleaseError(f"path escapes root: {path!r}")
    return candidate


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_release(root: Path, manifest: dict) -> list[str]:
    errors = []
    files = manifest.get('required_files')
    roles = ('generator', 'grader', 'reference_solver', 'hidden_truth',
             'audit_script', 'public_readme', 'public_scoring_schema', 'audit_log')
    if not isinstance(files, dict) or any(not isinstance(files.get(x), str) for x in roles):
        return ['required_files missing one or more required private/public reviewer artifacts']
    resolved = {}
    for name in roles:
        try:
            p = _within(root, files[name]); resolved[name] = p
            if not p.is_file():
                errors.append(f"missing reviewer artifact ({name}): {files[name]}")
        except ReleaseError as e:
            errors.append(str(e))
    for name in ('grader','reference_solver','hidden_truth','audit_script','audit_log'):
        if not PurePosixPath(files[name]).parts[0] in ('private','reports'):
            errors.append(f"{name} must not be in public/")
    for name in ('public_readme','public_scoring_schema'):
        if PurePosixPath(files[name]).parts[0] != 'public':
            errors.append(f"{name} must be inside public/")
    for kind in ('public_zip', 'private_zip'):
        try:
            p = _within(root, manifest.get(kind))
            if not p.is_file():
                errors.append(f"missing archive: {kind}={manifest.get(kind)}")
                continue
            with ZipFile(p) as z:
                if z.testzip() is not None:
                    errors.append(f"corrupt ZIP entry in {kind}")
                names = z.namelist()
                if not names:
                    errors.append(f"empty archive: {kind}")
                if kind == 'public_zip':
                    blocked = [n for n in names if (
                        SUSPICIOUS_PUBLIC_PATH.search(n)
                        or any(x in PurePosixPath(n).parts for x in ('private','generate.py','reference_solver.py'))
                        or PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts
                    )]
                    if blocked:
                        errors.append(f"private/suspicious members in public ZIP: {blocked[:5]}")
                    for role in ('public_readme','public_scoring_schema'):
                        if files[role] not in names:
                            errors.append(f"public ZIP missing declared reviewer artifact: {role}")
                else:
                    for role in ('generator','grader','reference_solver','hidden_truth','audit_script','audit_log'):
                        if files[role] not in names:
                            errors.append(f"private ZIP missing declared reviewer artifact: {role}")
        except (OSError, BadZipFile, ReleaseError, TypeError) as e:
            errors.append(f"invalid {kind}: {e}")
    if 'audit_log' in resolved and resolved['audit_log'].is_file():
        try:
            audit = json.loads(resolved['audit_log'].read_text(encoding='utf-8'))
            checks = audit.get('checks', {})
            for name in manifest.get('required_check_names', []):
                obj = checks.get(name)
                if not isinstance(obj, dict) or obj.get('passed') is not True or obj.get('exit_code') != 0:
                    errors.append(f"QC status missing/not passed/exit!=0: {name}")
                else:
                    log = obj.get('log_path')
                    if not isinstance(log, str) or not _within(root, log).is_file():
                        errors.append(f"QC actual log is missing for {name}: {log}")
            recorded = audit.get('grader_sha256')
            if 'grader' in resolved and resolved['grader'].is_file() and recorded != digest(resolved['grader']):
                errors.append("audit grader_sha256 does not match current grader (stale audit)")
            commands = audit.get('commands', {})
            for required in ('public_only_reference', 'private_grade'):
                if not isinstance(commands.get(required), str) or not commands[required].strip():
                    errors.append(f"missing actual command declaration: {required}")
        except (OSError, ValueError, ReleaseError, AttributeError) as exc:
            errors.append(f"invalid audit_log: {exc}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        errs = verify_release(args.root, manifest)
    except (OSError, ValueError, TypeError) as e:
        errs = [str(e)]
    for e in errs:
        print('ERROR:', e)
    print('QC_RELEASE:', 'FAIL' if errs else 'PASS (artifact/log presence, not independent scientific verification)')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
