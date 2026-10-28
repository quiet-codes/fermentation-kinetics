# Fermentation kinetics from batch data (assignment P3)

Python project for the P3 assignment (`docs/assignment_brief.md` is the authoritative specification; working rules are in `CLAUDE.md`).

## Status
| Phase | State |
|---|---|
| Phase 0: raw-data audit and pre-fit observations | complete |
| Level 1: kinetic model, fit, held-out prediction (R6) | complete (provisional baseline; reduced chi-square 12.6) |
| Level 2: model comparison, uncertainty, carbon balance, yield, plant-relevant uncertainty | complete |
| Level 3: plant optimisation (33 C and 36 C scenarios) | complete (`reports/level3.md`) |
| Submission snapshot and final archive | complete (`submission/`, `fermentation_kinetics_final_submission.zip`) |

Start with `reports/level3.md` for the operating recommendation, `reports/level2.md` for the model
evidence, then `handoff/PROJECT_STATE.md` and `handoff/DECISIONS.md`.

**Level 3 headline result.** Normal October constraint (33-37 C): 195 g/L TRS at 33 C, batch complete
(TRS = 5 g/L) in 35.57 h, 86.32 g/L ethanol, 4,858.69 INR/h of cycle time (116,608 INR/day derived) per
170 m3 fermenter. If the cooling water warms by 3 C and 36 C becomes the floor: 175 g/L TRS at 36 C,
39.82 h, 3,710.13 INR/h.

## Layout
```
CLAUDE.md                  project rules
README.md  requirements.txt
worklog.md  AI_USE.md      work log and AI-use note
data/raw/                  runs.csv, timecourse.csv, endpoint_hplc.csv (never modified), CHECKSUMS.sha256
docs/                      assignment_brief.md, requirements_traceability.csv
src/                       phase0_inspect.py                         Phase 0
                           kinetics.py, fit.py, level1_summary.py    Level 1 (unchanged since Level 1)
                           models.py, compare.py, uncertainty.py,
                           plant_uncertainty.py, carbon_balance.py   Level 2
                           make_level1_report.py, make_level2_report.py   regenerate the reports from the tables
tests/                     test_phase0.py, test_model.py, test_level2.py, test_report_claims.py
outputs/tables/            all generated tables; work/ holds per-model fit, LORO, profile, grid and R7 JSON files
outputs/figures/           all generated figures
reports/                   pre_fit_observations.md, level1.md, level2.md, level3.md
src/level3.py              Level 3 policy: model policy, completion rule, steam curve, economics
src/level3_optimize.py     Level 3 workflow: input audit, grid, recommendations, uncertainty, figures, answers
src/make_level3_report.py  regenerates reports/level3.md from the tables
src/level3_consistency_audit.py  report/table/claim consistency audit (31 checks)
scripts/                   reproduce_level3.sh, reproduce_level3.ps1, scripts/build_submission.py,
                           scripts/verify_submission.py, scripts/create_final_zip.py,
                           scripts/run_final_validation.py
submission/                generated snapshot (not a second source of truth)
outputs/audits/level3/     Level 3 audits, preflight CRLF reproduction, validation logs
handoff/                   PROJECT_STATE.md, DECISIONS.md, NEXT_ACCOUNT_PROMPT.md
```

## Install, test and regenerate
```
pip install -r requirements.txt
pytest -q                                   # 81 tests: phases 0-2, Task 2 regression, Level 3
pytest -q tests/test_level3.py              # Level 3 only
```
`pytest.ini` limits collection to `tests/` so the copy of the tests inside `submission/` is not collected
twice. Run all commands from the project root.

## Level 3 (fast path, Linux)
```
python src/level3_optimize.py --stage all --n-draws 200    # full workflow, about 45 s
python src/make_level3_report.py                           # reports/level3.md
python src/level3_consistency_audit.py                     # 31 consistency checks
python scripts/build_submission.py && python scripts/verify_submission.py
python scripts/run_final_validation.py                     # whole chain with logs
```
Windows: `.\scripts\reproduce_level3.ps1`.

## Reproduce (approximate run times on one CPU core)
```
python src/phase0_inspect.py --data-dir data/raw --root .                              # Phase 0 tables and figure (rewrites the Phase 0 outputs; line endings may differ from the supplied copies)
python src/fit.py --data-dir data/raw --root . --stage all                              # Level 1: ~3 min fit + R6 prediction + ~5 min sensitivities
python src/level1_summary.py --data-dir data/raw --root .
python src/compare.py --stage fit  --models M0,M1,M2,M3,M4,M5,M6                        # ~4 min
python src/compare.py --stage loro --models M0,M1,M2,M3,M4,M5,M6                        # ~12 min
python src/compare.py --stage select                                                    # applies the pre-registered rule and freezes it (hash)
python src/compare.py --stage r6diag                                                    # refuses to run if the frozen tables changed
python src/uncertainty.py --stage r7 --models M5,M0
python src/uncertainty.py --stage fixedgrid --models M5,M0
python src/uncertainty.py --stage profile --models M5                                   # ~12 min
python src/uncertainty.py --stage profile --models M0                                   # ~8 min
python src/uncertainty.py --stage assemble --models M5,M0
python src/plant_uncertainty.py --stage predict    # then: design, ksens, discriminate, plot
python src/carbon_balance.py --data-dir data/raw --root .
python src/make_level1_report.py ; python src/make_level2_report.py                     # rebuild the reports from the tables
```
Re-running the fitting stages rewrites the frozen files (`level1_frozen.json`, `model_selection_frozen.json`) and can change the last digits on another platform; if so, rebuild the reports and re-run the tests. Do not hand-edit any file under `outputs/tables/`.

## Integrity and protocol
- Raw CSVs are unchanged; `data/raw/CHECKSUMS.sha256` was **regenerated in the AI sandbox** from the supplied CSVs (your original checksum file was not part of the upload). `sha256sum -c` passes against the supplied bytes.
- Level 1 held out R6 and froze the parameters (SHA-256) before loading it. In Level 2, R6 is no longer blind: it was never used to choose a model; the Level 2 selection was frozen before the R6 diagnostic was computed.
- Decisions, including those made after seeing results, are logged in `handoff/DECISIONS.md` (D-01 to D-36).

## What has and has not been executed
- Executed in the AI sandbox (Python 3.11.2, numpy 2.4.6, scipy 1.17.1, pandas 3.1.0, matplotlib 3.11.2,
  pytest 9.2.0): the whole pipeline including the Level 3 workflow, and the full test suite (81 passed).
  Evidence: `outputs/audits/level3/final_validation.json` and `final_validation_logs/`.
- Windows: the earlier local failure ("59 passed, 1 failed", CRLF in `data_quality.csv`) was reproduced in a
  Linux simulation, traced to `pandas.to_csv` defaulting to `os.linesep`, and fixed by pinning UTF-8 and LF
  in every writer (`outputs/audits/level3/preflight/crlf_repro/`). **Actual Windows execution is still
  pending** and must be done locally.
- The original assignment PDF is unavailable, so `docs/assignment_brief.md` governs and PDF-only
  requirements remain unconfirmed. The D-03 uncertainty mapping and the 0.10 g/L CO2 sd floor remain
  assumptions.

## Main limitations
No candidate model fits within the stated noise; the preferred structure (M5) is not validated at 37 C; one run at 37 C and none at 33 or 36 C; run-to-run variability is unmeasured; R7 is an unusual run, not proven contamination. Details: `reports/level2.md` section 7.
