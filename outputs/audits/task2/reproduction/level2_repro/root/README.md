# Fermentation kinetics from batch data (assignment P3)

Python project for the P3 assignment (`docs/assignment_brief.md` is the authoritative specification; working rules are in `CLAUDE.md`).

## Status
| Phase | State |
|---|---|
| Phase 0: raw-data audit and pre-fit observations | complete |
| Level 1: kinetic model, fit, held-out prediction (R6) | complete (provisional baseline; reduced chi-square 12.6) |
| Level 2: model comparison, uncertainty, carbon balance, yield, plant-relevant uncertainty | complete |
| Level 3: plant optimisation (33 C and 36 C scenarios) | **not started** |
| Final consolidated report | **not started** (`reports/level1.md` and `reports/level2.md` are component reports) |

Start with `reports/level2.md`, then `handoff/PROJECT_STATE.md` and `handoff/DECISIONS.md`.

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
reports/                   pre_fit_observations.md, level1.md, level2.md
handoff/                   PROJECT_STATE.md, DECISIONS.md, NEXT_ACCOUNT_PROMPT.md
```

## Install and test
```
pip install -r requirements.txt
pytest -q                                   # all four test files
# without pytest: python tests/test_model.py ; python tests/test_level2.py ; python tests/test_report_claims.py
```
`tests/test_phase0.py` needs pytest (it uses fixtures). Run all commands from the project root.

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
- Executed in the AI sandbox (Python 3.12.3): every stage listed above; `tests/test_model.py` (16), `tests/test_level2.py` (15) and `tests/test_report_claims.py` (11) through fallback runners; the six Phase 0 tests through a minimal stand-in for pytest's `fixture` and `approx`.
- **Not verified:** pytest itself, and any run on your machine. Please run `pytest -q` and compare a few tables.
- The brief's uncertainty-table mapping (D-03) and the 0.10 g/L CO2 sd floor are unconfirmed assumptions.

## Main limitations
No candidate model fits within the stated noise; the preferred structure (M5) is not validated at 37 C; one run at 37 C and none at 33 or 36 C; run-to-run variability is unmeasured; R7 is an unusual run, not proven contamination. Details: `reports/level2.md` section 7.
