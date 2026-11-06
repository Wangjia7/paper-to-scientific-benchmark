#!/usr/bin/env python3
"""Reusable *examples* of defensive grader primitives.

Only the CSV/ID helpers are standard-library. Gaussian KL and IEEE float64
helpers require numpy/scipy. Integrate according to the task's public scoring
contract; these are NOT universal scientific scoring rules.
"""
from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Iterable


class GraderContractError(ValueError):
    """Invalid submission, math domain or numerics: never treat as zero loss."""


def read_csv_strict(path: str | Path, expected_header: list[str]) -> list[dict[str, str]]:
    """Read RFC-style CSV while refusing ragged rows and duplicate/missing columns.

    This intentionally requires EXACT column order as the supplied public
    contract; row order is not constrained. Quoted fields are fully supported.
    """
    if not expected_header or len(set(expected_header)) != len(expected_header):
        raise GraderContractError("grader configuration: invalid expected CSV header")
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f, strict=True)
            header = next(reader, None)
            if header != expected_header:
                raise GraderContractError(f"{path.name}: CSV header mismatch: {header!r}")
            rows = []
            for line, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    raise GraderContractError(f"{path.name}:{line}: expected {len(header)} columns, got {len(row)}")
                if any(field == "" for field in row):
                    raise GraderContractError(f"{path.name}:{line}: empty required CSV field")
                if row == header:
                    raise GraderContractError(f"{path.name}:{line}: repeated header as data")
                rows.append(dict(zip(header, row)))
            return rows
    except (csv.Error, UnicodeError) as exc:
        raise GraderContractError(f"{path.name}: invalid CSV syntax/encoding: {exc}") from exc


def canonical_candidate_indices(
    submitted_ids: Iterable[str], canonical_ids: Iterable[str], *,
    pattern: str = r"P[0-9]{4}", count: int | None = None
) -> list[int]:
    """Exact public ID membership + index-level uniqueness; no Unicode aliases.

    Case IDs can be other structured tokens: change pattern only if the PUBLIC
    contract says so. Do not normalize/casefold/parse digits before membership.
    """
    candidates = list(canonical_ids)
    values = list(submitted_ids)
    regex = re.compile(pattern, re.ASCII)
    if len(candidates) != len(set(candidates)) or any(
        not isinstance(x, str) or regex.fullmatch(x) is None for x in candidates
    ):
        raise GraderContractError("public canonical candidate catalogue is invalid")
    if count is not None and len(values) != count:
        raise GraderContractError(f"expected exactly {count} chosen candidates")
    lookup = {value: i for i, value in enumerate(candidates)}
    resolved: list[int] = []
    for value in values:
        if not isinstance(value, str) or regex.fullmatch(value) is None or value not in lookup:
            raise GraderContractError(f"noncanonical or unavailable candidate ID: {value!r}")
        resolved.append(lookup[value])
    if len(set(resolved)) != len(resolved):
        raise GraderContractError("duplicate scientific candidates after canonical lookup")
    return resolved


def ieee_float64_native(array, *, shape: tuple[int, ...] | None = None):
    """Reject float32 / non-floating dtypes; accept big/little-endian IEEE f8.

    Only use when the PUBLIC contract explicitly allows both endian orders.
    """
    import numpy as np
    a = np.asarray(array)
    if a.dtype.kind != "f" or a.dtype.itemsize != 8:
        raise GraderContractError("IEEE binary64 floating-point array required")
    if shape is not None and a.shape != shape:
        raise GraderContractError(f"unexpected shape {a.shape}, expected {shape}")
    b = a.astype(np.float64, copy=False)
    if not np.isfinite(b).all():
        raise GraderContractError("input array has NaN/Inf")
    return b


def _finite_log_norm(values):
    """log(||values||_2) calculated without squaring huge finite entries."""
    import numpy as np
    a = np.asarray(values, dtype=np.float64)
    if not np.isfinite(a).all():
        raise GraderContractError("nonfinite intermediate in norm")
    scale = float(np.max(np.abs(a)))
    if scale == 0.0:
        return -math.inf
    norm_unit = float(np.sum(np.square(a / scale)))
    if not math.isfinite(norm_unit) or norm_unit <= 0.0:
        raise GraderContractError("invalid scaled squared norm")
    return math.log(scale) + 0.5 * math.log(norm_unit)


def _exp_twice(log_norm):
    """Square a scaled norm; mathematically enormous result is +inf, never 0."""
    if log_norm == -math.inf:
        return 0.0
    val_log = 2.0 * log_norm
    if not math.isfinite(val_log):
        raise GraderContractError("nonfinite log quadratic form")
    if val_log > math.log(__import__("sys").float_info.max):
        return math.inf
    # Underflow of a very small NONNEGATIVE square is harmless for KL bounds.
    return math.exp(val_log)


def stable_gaussian_kl(
    reference_mean, reference_cov, predicted_mean, predicted_cov,
    *, negative_roundoff: float = 1e-10
) -> float:
    """KL(N(reference) || N(predicted)) with robust Mahalanobis calculation.

    Covariances should already contain ONLY the stabilizer made PUBLIC in the
    scoring contract. Returns +inf when the true KL exceeds float64 range;
    malformed inputs/intermediates raise GraderContractError. A real grader
    must turn +inf into a scientific quality-gate FAILURE and JSON `null` plus
    a diagnostic flag; never serialize bare NaN/Infinity into strict JSON.
    """
    import numpy as np
    from scipy.linalg import cholesky, solve_triangular

    m0 = ieee_float64_native(reference_mean)
    m1 = ieee_float64_native(predicted_mean)
    c0 = ieee_float64_native(reference_cov)
    c1 = ieee_float64_native(predicted_cov)
    if m0.ndim != 1 or m1.shape != m0.shape or c0.shape != (len(m0), len(m0)) or c1.shape != c0.shape:
        raise GraderContractError("KL input dimensions mismatch")
    if not np.allclose(c0, c0.T, rtol=0, atol=1e-8) or not np.allclose(c1, c1.T, rtol=0, atol=1e-8):
        raise GraderContractError("KL covariances must be symmetric")
    try:
        l0 = cholesky(c0, lower=True, check_finite=True)
        l1 = cholesky(c1, lower=True, check_finite=True)
        w = solve_triangular(l1, l0, lower=True, check_finite=True)
    except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
        raise GraderContractError(f"invalid KL covariance whitening: {exc}") from exc
    if not np.isfinite(w).all():
        raise GraderContractError("KL covariance whitening returned non-finite")
    trace_term = _exp_twice(_finite_log_norm(w))

    # Subtract means only after scaling: direct subtraction can overflow even
    # when BOTH submitted numbers are finite float64 values.
    scale = max(1.0, float(np.max(np.abs(m0))), float(np.max(np.abs(m1))))
    delta_scaled = (m1 / scale) - (m0 / scale)
    try:
        z = solve_triangular(l1, delta_scaled, lower=True, check_finite=True)
    except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
        raise GraderContractError(f"invalid KL mean whitening: {exc}") from exc
    norm_log = _finite_log_norm(z)
    quadratic = _exp_twice((math.log(scale) + norm_log) if norm_log != -math.inf else -math.inf)

    diag0, diag1 = np.diag(l0), np.diag(l1)
    if not np.all(np.isfinite(diag0)) or not np.all(np.isfinite(diag1)) or np.any(diag0 <= 0) or np.any(diag1 <= 0):
        raise GraderContractError("invalid KL Cholesky factors")
    logdet0 = 2.0 * float(np.log(diag0).sum())
    logdet1 = 2.0 * float(np.log(diag1).sum())
    if not all(math.isfinite(x) for x in (logdet0, logdet1)):
        raise GraderContractError("invalid KL logdet")
    if math.isinf(quadratic) or math.isinf(trace_term):
        return math.inf
    # Python float addition can overflow without raising.
    k = 0.5 * (trace_term + quadratic - len(m0) + logdet1 - logdet0)
    if math.isinf(k) and k > 0:
        return math.inf
    if not math.isfinite(k):
        raise GraderContractError("nonfinite KL intermediate/final value")
    if k < 0.0:
        if k >= -negative_roundoff:
            return 0.0
        raise GraderContractError(f"significantly negative KL: {k}")
    return k
