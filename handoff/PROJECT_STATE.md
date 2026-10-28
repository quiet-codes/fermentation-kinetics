# PROJECT STATE (end of Level 3 and final packaging)

**Completed:** Phase 0; Level 1; Level 2; Task 2 audit follow-up; Level 3 optimisation, uncertainty and
reporting; submission snapshot; final archive.
**Specification:** `docs/assignment_brief.md` (authoritative; the original PDF is unavailable), `CLAUDE.md`.

## Level 3 result

| scenario | initial TRS | temperature | completion | final TRS | ethanol | wash | margin/cycle | 24 h equivalent |
|---|---|---|---|---|---|---|---|---|
| normal 33-37 C | 195.0 g/L | 33.0 C | 35.571 h | 5.000 g/L | 86.32 g/L | 10.94 % v/v | **4,858.69 INR/h** | 116,608 INR/day (derived) |
| minimum 36 C | 175.0 g/L | 36.0 C | 39.817 h | 5.000 g/L | 76.73 g/L | 9.72 % v/v | **3,710.13 INR/h** | 89,043 INR/day (derived) |

Model: frozen M5, parameter set `M5_a29043ff3379ad5d`, source `outputs/tables/work/fit_M5.json`.
Warming costs 1,148.56 INR/h (23.6 %). Uncertainty on the margin (200 parameter draws): 4,641.97-5,038.55
INR/h normal, 3,538.06-3,858.37 INR/h warm; every draw completes. M2/M6 own optima are 4.0-4.8 % higher and
prefer one grid step less sugar; they remain comparisons, not the recommendation.

Feasibility bookkeeping on the 120 h horizon (M5): 443 completed feasible, 31 completed outside the 7-14 %
v/v steam curve (no margin), 27 unfinished (no margin, no completion time), 0 simulation failures.
Brief Q5 (37 C, 260 g/L): does not complete; 105.37 g/L ethanol and 30.26 g/L TRS at 120 h, low trust.

## Files added in Level 3
- Code: `src/level3.py` (policy, completion rule, economics, steam curve), `src/level3_optimize.py`
  (workflow), `src/make_level3_report.py`, `src/level3_consistency_audit.py`; tests: `tests/test_level3.py`
- Scripts: `scripts/reproduce_level3.sh`, `scripts/reproduce_level3.ps1`, `scripts/build_submission.py`,
  `scripts/verify_submission.py`, `scripts/create_final_zip.py`, `scripts/run_final_validation.py`
- Tables: `outputs/tables/optimization_grid.csv`, `optimization_recommendations.csv`, `plant_economics.csv`,
  `optimization_uncertainty.csv`, `optimization_model_comparison.csv`, `optimization_input_audit.csv`,
  `optimization_horizon_sensitivity.csv`
- Figures: `outputs/figures/level3_feasible_region.png`, `level3_economics.png`,
  `level3_completion_time.png`, `level3_uncertainty.png`
- Report: `reports/level3.md` (generated from the tables by `src/make_level3_report.py`)
- Audits: `outputs/audits/level3/` (model policy, input audit, grid and horizon summaries, uncertainty draws,
  answers, report claims, consistency report, submission build and verification, final validation and logs,
  final ZIP validation and listing), plus `outputs/audits/level3/preflight/crlf_repro/` (the reproduced and
  fixed Windows CRLF failure)
- Packaging: `submission/` snapshot, `requirements_traceability.csv` (root, full matrix),
  `pytest.ini`, `fermentation_kinetics_final_submission.zip`

## Checks performed in this environment
- Full test suite: 81 passed (60 pre-existing + 21 Level 3). `pytest.ini` limits collection to `tests/`.
- Consistency audit: 31/31 checks passed (`outputs/audits/level3/consistency_report.md`).
- Submission verification: 14/14 checks passed; manifest hashes, required structure, figure links, no
  caches or secrets, raw checksums, frozen selection, frozen Level 1 hash, eight carbon balances.
- Final validation chain: recorded stage by stage with exit codes in
  `outputs/audits/level3/final_validation.json`; archive validated in `outputs/audits/level3/final_zip_validation.json`.
- **Linux/sandbox only. Actual Windows execution has not been performed and is still pending.**

## Unresolved limitations (unchanged from earlier phases unless noted)
- The preferred structure is not validated at 37 C; only one run (R8) exists there, and there is no data at
  33 or 36 C, so those temperatures are interpolations of the fitted multipliers.
- No candidate model fits within the stated noise; residuals are strongly autocorrelated, so QAICc is
  indicative rather than definitive.
- M5's P_max and n_inh are strongly associated; the ethanol-tolerance extrapolation is the weakest part of
  any high-sugar prediction.
- The leave-one-out R8 result is sensitive to the fitted minimum and the numerical environment (the Task 2
  isolated refit moved it from 1629.2 to 731.1).
- The CO2 standard-deviation floor of 0.10 g/L is an assumption; its discrete alternatives were quantified
  and matter far less than the parameter ensemble.
- R7 excluded from primary fits, R3 biomass is OD600-based, R4 does not close its carbon balance within 95 %.
- The original assignment PDF is unavailable; PDF-only requirements cannot be confirmed.
- Parameter uncertainty is quantified; predictive uncertainty is not. The recommendations are model optima,
  not plant-validated optima.
- Windows verification outstanding (only a Linux simulation of the Windows line terminator was done).

## Next actions for the user
1. `python -m pip install -r requirements.txt` then `python -m pytest -q` on Windows and record the result.
2. Run `.\scripts\reproduce_level3.ps1` on Windows and compare `git status --short`.
3. Complete the editable personal-contribution section in `AI_USE.md`.
4. Confirm any requirement that exists only in the original assignment PDF.
