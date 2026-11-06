# Changelog

## 2.4.0 — 2026-11-05

- Incorporate newly reported **Günther v9 / B05** rejection: a science-blind sequential farthest-point design legitimately scores A=24.737494, B=29.194558, C=31.002741, total **84.934793**, with three JS values below 0.020 and all B gates satisfied. Retain distinction from previous B01–B04 grader/contract failures.
- Add required **Gate 1c Scientific Decision Bypass**: test whether claimed indispensable scientific observations can be removed and a legal geometry-only/one-shot strategy still passes. Do not discriminate by algorithm name, add post-hoc gates, or raise score thresholds.
- Add **Gate 4c Scientific Budget Conflict** for C-style multi-observable active sampling: physically motivated differences in posterior location, response/constraint scale and conditional GP gains; independent physics families/seeds beyond candidate-layout variants.
- Add reference `13-observation-conditioned-budget-b05.md`, logic audit `scripts/conditional_budget_pilot.py` and 10/10 synthetic logic regressions. Audit of provided records is **not** execution of v2.3 generator/grader or v10 science proof.
- Preserve earlier B01–B04 grader protections and V4 release identity; ensure reviewer and public materials remain separate.

## 2.3.0 — 2026-11-05 (prior local development snapshot)

- Add cross-case failure taxonomy (BAO V2, FP V4, Günther, Simba), user-reported acceptance semantics, scientific difficulty/identifiability pilot and actual release-lock architecture.
- Add `references/10-12`, `scripts/difficulty_pilot.py`, `scripts/release_lock.py`, their example data and synthetic self-tests. Historical acceptance does not establish universal scientific validity.

## 2.2.0 — 2026-10-21

- Based on two Günther GP/PCA QC returns, add **QC scientific necessity / anti-compensation gates**: region × mandatory target AND criteria, no compensation by total/subscore, independent scoring retained.
- Require **complete private reviewer proof pack**: generator, truth, grader, public-only reference solver, independent re-generation/sampling, CLI, logs and reproducibility hashes, with no leakage to Agent.
- Require **fail-closed numerical scoring** even with finite extreme inputs (`1e160`, `1e200`, sign-alternating extremes, large covariance); never map NaN to zero KL; evaluate and audit intermediate operations.
- Require **canonical public candidate IDs**, uniqueness of physical index after mapping and strict CSV row cardinality/headers, while preserving legitimate scientific-equivalent formats.
- New references `08-gunther-qc-lessons.md` and `09-grader-quality-assurance.md`; updated Skill, scoring-contract, task template, review playbook, acceptance tests, README and summary.
- Add executable generic guard tests, science necessity matrix preflight and reviewer-pack release preflight; these verify generic invariants but do **not** certify arbitrary benchmark-specific graders.
- Fix sample score engine to handle extreme finite prediction differences without nonstandard JSON diagnostics. Keep existing v2.1 shared-table and platform judgment rules.

## 2.1.0 — 2026-10-16

- **Scientific decision count ≠ experimental data count ≠ checkpoint count.** Three independent *controlled experiments* are no longer required; one study with shared simulations/observations may support multiple separately falsifiable claims.
- Require **coherence** of judgments under one scientific question, rather than unrelated tasks stitched together to reach a number.
- Clarify that the particular platform review asks for three different scientific judgments; the original general platform rule demands multiple objective checkpoints, not universally three experiments. Other platforms may configure the count.
- Preserve mandatory pre-engineering `GO / REJECT / INSUFFICIENT_EVIDENCE` screening and explicit refusal for low-value conversion.
- Add Elbers LPT failure analysis and prevent fixed-function regression / nine-option fixed objective / mass inversion from being mistaken for scientifically interpretive judgments solely because of separate datasets.
- `scripts/preflight.py`: count distinct `judgment_id` (platform-configurable minimum), not checkpoints or experiments; opt-in `allow_shared_tables` for a common truth/output CSV with distinct target columns.
- `scripts/score.py`: support column-wise scoring from shared CSVs, including localized invalid numeric values.
- Add shared-table structural manifest and self-tests showing independent per-judgment scores even when all data are in one table.
- Keep original non-shared scoring behavior compatible with historical FP lensing V4 (`38.2 + 27 + 30 = 95.2`).

Scientific independence and identifiability still require expert review; structural validation is not scientific certification. This revision does not include any new benchmark submission or GitHub push.
