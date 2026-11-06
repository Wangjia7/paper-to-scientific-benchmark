# Skill 2.2.0 update validation (2026-10-21)

## What was actually run

1. `python scripts/self_test.py` → PASS: deterministic and shared-output scoring, science gate matrix positive/negative schema, finite extreme diagnostic JSON handling, row-level CSV, per-judgment independence, reviewer ZIP/evidence presence and stale SHA rejection.
2. `python scripts/qc_guard_self_test.py` → PASS: 32 generic numeric/ID/CSV assertions (NumPy/SciPy installed). Tests ±1e160, ±1e200, signed alternation, huge finite covariance, missing/extra CSV fields, duplicate headers, Unicode aliases, endian float64, NaN/Inf, KL baseline.
3. `python scripts/qc_matrix.py --matrix assets/qc-coverage-matrix.example.json` → PASS (declaration-only). Missing-gate and false-gate audits are asserted to fail in `self_test.py`.
4. `python scripts/preflight.py --manifest assets/benchmark_manifest.example.json --root .` → PASS (structural only; one expected warning that scientific independence cannot be automatically certified).
5. Separately, on the **unchanged existing Günther V2.2 benchmark** in `/mnt/data/gunther_gp_pca_v2_2_work`: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python private/audit_v2.py` → **65 assertions PASS**; `python private/audit_v3.py` → **113 assertions PASS**. Reference score unchanged: A=24.73749372, B=29.194558048, C=35.931670779, total=89.863722546. The Skill update did not modify this benchmark's grader.

## Important limitations

These tests verify **generic safeguards** and show the pre-existing benchmark-specific fixed grader passed its already defined red-team suite. They do **not** certify that an arbitrary future newly generated task has scientific validity or passes platform human QC. New tasks must run their **own** `private/audit_qc.py` against their actual frozen scorer, plus public-only reference and private reviewer release checks. There has been no external GitHub update and no official platform submission in this operation.
