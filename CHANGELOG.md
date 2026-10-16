# Changelog

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
