#!/usr/bin/env python3
"""Offline red-team self-test for REUSABLE numeric, CSV, and ID primitives.

Requires numpy and scipy. It does not call a project's actual private grader.
"""
from __future__ import annotations
import csv
import math
import tempfile
from pathlib import Path
import numpy as np
from grader_guards import (
    GraderContractError, canonical_candidate_indices, ieee_float64_native,
    read_csv_strict, stable_gaussian_kl,
)


def expect_reject(f, *a, **kw):
    try:
        f(*a, **kw)
    except (GraderContractError, ValueError):
        return
    raise AssertionError(f"expected reject: {f.__name__}")


def main():
    checks = 0
    z = np.zeros(8, dtype=np.float64)
    e = np.eye(8, dtype=np.float64)
    assert abs(stable_gaussian_kl(z, e, z, e)) <= 1e-12; checks += 1
    assert abs(stable_gaussian_kl(z, e, np.ones(8), e) - 4.) <= 1e-10; checks += 1
    for val in (1e160, 1e200, -1e160, -1e200):
        assert math.isinf(stable_gaussian_kl(z, e, np.full(8, val), e)); checks += 1
    signed = np.array([1e200, -1e200] * 4)
    assert math.isinf(stable_gaussian_kl(z, e, signed, e)); checks += 1
    assert math.isinf(stable_gaussian_kl(np.full(8, -1e308), e, np.full(8, 1e308), e)); checks += 1
    k = stable_gaussian_kl(z, e, z, np.eye(8) * 1e308)
    assert math.isfinite(k) and k > 1000; checks += 1
    assert math.isinf(stable_gaussian_kl(z, np.eye(8) * 1e308, z, e)); checks += 1
    for arr in (np.full(8, np.nan), np.full(8, np.inf), np.full(8, -np.inf)):
        expect_reject(stable_gaussian_kl, z, e, arr, e); checks += 1
    expect_reject(stable_gaussian_kl, z, e, z, e * 0); checks += 1
    expect_reject(stable_gaussian_kl, z, e, z, e.astype('f4')); checks += 1
    assert (ieee_float64_native(e.astype('>f8')) == e).all(); checks += 1
    expect_reject(ieee_float64_native, e.astype('f4')); checks += 1
    candidates = [f"P{i:04d}" for i in range(350)]
    assert canonical_candidate_indices(["P0232", "P0001"], candidates, count=2) == [232,1]; checks += 1
    for aliases in (["P0232", "P０２３２"], ["P0232", "P0232"], ["P0232", "P9999"], ["P0232", "p0001"], ["P0232", "P23"]):
        expect_reject(canonical_candidate_indices, aliases, candidates, count=2); checks += 1

    with tempfile.TemporaryDirectory(prefix='qc-guards-') as tmp:
        f = Path(tmp) / 'data.csv'
        f.write_text('candidate_id\n"P0232"\n"P0001"\n', encoding='utf-8')
        assert [row['candidate_id'] for row in read_csv_strict(f, ['candidate_id'])] == ['P0232','P0001']; checks += 1
        f.write_text('candidate_id\nP0001,unexpected\n', encoding='utf-8')
        expect_reject(read_csv_strict, f, ['candidate_id']); checks += 1
        f.write_text('candidate_id\nP0001\n\n', encoding='utf-8')
        expect_reject(read_csv_strict, f, ['candidate_id']); checks += 1
        f.write_text('candidate_id\ncandidate_id\n', encoding='utf-8')
        expect_reject(read_csv_strict, f, ['candidate_id']); checks += 1
        f.write_text('candidate_id,candidate_id\nP0001,P0002\n', encoding='utf-8')
        expect_reject(read_csv_strict, f, ['candidate_id']); checks += 1
        f.write_text('candidate_id,score\nP0001\n', encoding='utf-8')
        expect_reject(read_csv_strict, f, ['candidate_id', 'score']); checks += 1
        f.write_text('candidate_id,score\nP0001,1.5\nP0002,-3.0\n', encoding='utf-8')
        rows = read_csv_strict(f, ['candidate_id', 'score'])
        assert len(rows)==2 and rows[1]['candidate_id']=='P0002'; checks += 1
        f.write_text('candidate_id,score\n"P0001","1.5"\n', encoding='utf-8')
        assert len(read_csv_strict(f, ['candidate_id','score'])) == 1; checks += 1

    # Valid mathematical equivalence: a declared byte-order change must not
    # change a scientific numeric result.
    x = np.arange(8,dtype='<f8')
    y = ieee_float64_native(x.astype('>f8'))
    assert np.array_equal(x,y); checks += 1
    print(f'PASS: {checks} generic numeric/ID/CSV assertions; actual benchmark grader still requires its own red-team runs')


if __name__ == '__main__':
    main()
