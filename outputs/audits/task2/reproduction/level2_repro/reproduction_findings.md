# Task 2 Level 2 reproduction findings

Created: 2026-10-27 15:05:17. Isolated root: `outputs/audits/task2/reproduction/level2_repro/root/`.

## Execution

- 20/20 stages passed in 538.6s; failed=0, skipped=0.
- 68 files compared; 24 byte-identical; 31 CSV/JSON outside rtol=1e-6/atol=1e-8.
- 44 files differ from the copied baseline. Full detail: `consistency_report.json` / `consistency_report.md`.

## Frozen decision and arithmetic

- Preferred / best QAICc / rule unchanged: `M5` / `M5` / `D-24`.
- c_hat original 3.862912186, reproduced 3.862913469, difference 1.28e-06.
- All seven fits still converge 8/8; M3 remains at a bound; R6 was not used for selection.
- Reproduced D-24 preferred: `M5`; all eight carbon-balance runs present; non-closing runs: ['R4'].
- Yield-gap additivity residual 1.78e-14; residual chi-square max difference 1.36e-12; frozen hashes verify: True.

## Why exact numerical reproduction was not achieved

- Sandbox: Python 3.11.2 / numpy 2.4.6 / pandas 3.1.0; frozen record: Python 3.12.3 / numpy 2.4.4 / pandas 3.0.2.
- Six of seven fits reproduced exactly; M5 selected a different near-equivalent minimum: max parameter difference 0.479998 (0.3081%), chi-square difference 0.000371.
- LORO M5 R8 fold 1629.2 originally vs 731.1 reproduced. Targeted recompute from original theta = 1629.1999; from reproduced theta = 731.1355. The difference is warm-start sensitivity on a flat ridge, not a rule change.
- Level 1 report and pre-fit observations are byte-identical; `level2.md` differs because it reports reproduced numbers.

## First attempt

- `outputs/audits/task2/reproduction/failed_attempt_1` failed: Scheduler marked dependent stages skipped immediately after compare_fit finished (deadlock check ran before ready stages were recomputed).
- Fix: Added a progress flag so the scheduler loops again when a dependency has just completed; verified with a small synthetic DAG before rerun. The rerun completed 20/20 stages.

## Limits

- The original assignment PDF is unavailable; D-03 is verified only against docs/assignment_brief.md.
- Actual Windows execution was not performed in this Linux sandbox; a cp1252 file-encoding simulation is used for the UTF-8 fix.
- Figures are checked for valid PNG signature and byte equality only, not pixel-level equality.
- Numeric reproduction uses Python 3.11.2 / numpy 2.4.6 / pandas 3.1.0; the frozen record used Python 3.12.3 / numpy 2.4.4 / pandas 3.0.2, so bit-exact agreement is not expected.
- Level 1 fit and full Level 1 sensitivity were not refit in the reproduction; the frozen Level 1 outputs were copied as inputs.
- The reproduced M5 fit selected a different near-equivalent minimum (P_max lower by 0.48 g/L, chi-square higher by 0.000371). This changes downstream LORO/plant numbers; the frozen original decision is still M5.
- The LORO M5 R8 fold is 731.1 in the reproduction vs 1629.2 originally. A targeted recomputation from the original fit theta gives 1629.1999 and from the reproduced theta gives 731.1355, confirming warm-start sensitivity rather than a code change.
- The reproduced level2.md is not byte-identical because it reports reproduced numbers; level1.md and pre_fit_observations.md are byte-identical.

Machine-readable evidence: `reproduction_findings.json`, `key_metrics.json`, `loro_R8_warmstart_check.json`, `reproduction_log.json`, `consistency_report.json`.
