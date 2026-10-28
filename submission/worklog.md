# Worklog

## Phase 0 – Raw-data audit and pre-fit observations (2026-10-26)

**Scope (CLAUDE.md):** audit and observations only. No kinetic fitting, no optimisation, no run excluded.

### Sequence
1. **First pass** (earlier in the conversation): `CLAUDE.md` and `assignment_brief.md` arrived as 0-byte files. CSVs were inspected and a first set of outputs was built using my own assumptions (biomass carbon 0.48 g/g, analyst-chosen tolerances, ethanol-evaporation caveat, a provisional handoff).
2. **Second pass (this version):** the real `CLAUDE.md` and brief were uploaded (`*_1.md`). The three CSVs were byte-identical to the first upload (`cmp`), so the data inspection stands. Everything was redone against the brief:
   - measurement sds from brief s3 replace my tolerances (z-scores in `data_quality.csv`, `endpoint_diagnostics.csv`; sd propagation in the carbon balance);
   - biomass carbon fraction 0.4883 g/g (24.6 g per C-mol), n.d. = below 0.2 g/L, constant volume and returned off-gas ethanol, all from the brief;
   - the first pass's "HPLC at 48 h", "TRS after inversion" and "biomass by dry weight" assumptions are now confirmed by the brief and no longer assumptions;
   - the earlier reading of the two metadata sugar columns as "derived" was replaced by the chemically consistent explanation (~70% sucrose, inversion gain);
   - the R1/R4 constant CO2 was downgraded from a flag to an observation (plausible zero off-gas flow after sugar exhaustion);
   - the provisional handoff file was deleted and replaced by the three files CLAUDE.md specifies.
3. Added `tests/test_phase0.py` (6 tests) and `data/raw/CHECKSUMS.sha256`.
4. Copied the raw CSVs unchanged into `data/raw/`, the brief to `docs/assignment_brief.md`, and CLAUDE.md to the project root.

### What was actually executed (AI sandbox, Python 3.12.3, pandas 3.0.2, matplotlib 3.10.8, pytest 9.1.1)
- `python src/phase0_inspect.py --data-dir data/raw --root .` ran without errors (137 data-quality checks: 74 PASS, 58 INFO, 5 FLAG).
- `python -m pytest -q`: **6 passed**.
- `raw_curves.png` viewed (4 panels, 8 runs).
- Numbers quoted in the report were compared against the generated tables; three wording errors found and fixed (R8 biomass z, biomass share of carbon, count of expected exceedances).
- **Not yet run on the user's machine.**

### Local re-run
```
pip install pandas numpy matplotlib pytest
python src/phase0_inspect.py --data-dir data/raw --root .
pytest -q
```
Outputs should match the supplied tables (compare, e.g., `outputs/tables/preliminary_carbon_balance.csv`).

### Failed checks / unresolved limitations
- No failed tests. Open data questions are in `reports/pre_fit_observations.md` section E and `handoff/PROJECT_STATE.md`.
- The brief's uncertainty table was PDF-extracted text; I read it in row order (needs your confirmation against the PDF).

### Next step
Stop. Level 1 starts only after the user reviews outputs and confirms local files are saved.

---

## Level 1 – Model, fit and held-out prediction (2026-10-26)

**Scope:** Level 1 only. No Level 2 uncertainty analysis, no Level 3 optimisation.

### Sequence
1. The user's message contained unfilled template placeholders (including the local Phase 0 result line). I treated the proposal in my previous response as approved, and said so. The user then sent explicit approvals and safeguards.
2. **Decisions recorded before any fit** in `handoff/DECISIONS.md` (D-10 to D-21): R6 held out; R3 biomass excluded from the objective; R7 excluded from the primary fit; nominal initial states; sds; protocol.
3. My first draft of `kinetics.py` (logistic thermal factor, P_max(T), estimated exponent) was **replaced before any fit** to follow the user's simplifications (fixed n = 1, no P_max(T), per-level temperature multipliers, Ks fixed). The earlier draft was never run on data.
4. Fit stage: training runs only; R6 and R7 were not loaded. A 10-start trial run (to time the fit) and then the official 40-start run; only the second one's outputs are kept. 41/41 starts reached one minimum.
5. I inspected training residuals and the training figure. I did **not** change the model after seeing them; the misfit is reported.
6. Predict stage: verified the SHA-256 of `level1_parameters.csv`, then loaded R6 for the first time and predicted it. No refit. No model change after seeing R6.
7. Predeclared sensitivities ran after the prediction (R6 never evaluated in them).
8. `src/level1_summary.py` computed post-hoc numbers for the report; `reports/level1.md` was generated from the tables; five wording errors in my first draft of the report were found by checking against `heldout_predictions.csv` and fixed (e.g. TRS bias starts at 8 h not 10 h; CO2 error grows from +2.1 to +6.4 g/L; the R1/R4 difference is about 1.7 sd of a difference, not 2.5 sd).

### Executed (AI sandbox, Python 3.12.3, numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, matplotlib 3.10.8)
- `python src/fit.py --stage fit --n-starts 40` (185 s), `--stage predict`, `--stage sensitivity` (6 cases), `python src/level1_summary.py`.
- `python tests/test_model.py` (fallback runner): 16 passed, 0 failed, 0 skipped. pytest is not installed in this sandbox and there is no network, so **pytest has not been run**.
- Phase 0 script re-run to a temporary root: 74 PASS / 58 INFO / 5 FLAG; the four tables are identical to the supplied ones apart from CR line endings.
- `data/raw/CHECKSUMS.sha256` was regenerated in the sandbox for testing and is not shipped (the user's local file is the reference).

### Failed checks / problems
- A first attempt to build the folder tree with brace expansion under `sh` created a stray literal directory; it was removed.
- A background launch of the fit stage did not survive the tool call and was re-run in the foreground.
- A report-patch script failed on an invalid replacement string and changed nothing; it was corrected and re-run.
- No test failures.

### Local commands (not yet run by the user)
```
pip install numpy scipy pandas matplotlib pytest
python src/fit.py --data-dir data/raw --root . --stage all
python src/level1_summary.py --data-dir data/raw --root .
pytest -q
```

### Next step
Stop. Level 2 starts only after the user reviews the Level 1 outputs.

---

## Level 2 – Model comparison, uncertainty, carbon balance, yield, plant-relevant uncertainty (2026-10-26)

**Scope:** Level 2 only. No Level 3 optimisation (margin evaluated at four fixed scenarios).

### Sequence
1. Inspected current files and tables: Level 1 state intact (frozen hash matched; M0 refit reproduces chi-square 3675.26).
2. **Registered before any Level 2 computation** (`DECISIONS.md` D-22 to D-28): R6 not blind and never used for selection; seven candidates (D-23) developed from training-run descriptive evidence only (R5 vs R3 late rates, R8); selection rule (QAICc with c_hat from the most complex candidate, parameters-at-bound disqualify, 4-unit simplicity tie-break, leave-one-run-out as tie-break); uncertainty method; carbon-balance and yield conventions; plant protocol.
3. Fitted all candidates (training runs only), leave-one-run-out, applied the rule, **froze** the selection with SHA-256, and only then ran the R6 out-of-fit diagnostic for all candidates.
4. Profile likelihood, jackknife (from the leave-one-run-out fits), K_s and n grids, R7-inclusion refits; carbon balance and yields from the raw CSVs (Monte-Carlo, fixed seed); plant-relevant propagation, linearised design and structure-discrimination criteria; figures; tests; report generated from the tables.
5. **Disclosed changes made after seeing results:** identifiability labels refined (ridge and single-run flags; labelling only, D-30); carbon-balance and profile figures corrected (axis range; c_hat in the profile figure title, which first showed M0's value on the M5 panel); report wording corrected after checking hand-typed claims against the tables (K_s upper limit, fold winners, Phase 0 agreement, alternative-experiment statement).

### Executed (AI sandbox, Python 3.12.3, numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, matplotlib 3.10.8; one CPU core)
- `compare.py` stages fit (7 candidates, 8 starts each), loro, select, r6diag; `uncertainty.py` stages r7, fixedgrid, profile (M5, M0), assemble; `plant_uncertainty.py` stages predict (150 draws), design, ksens, discriminate, plot; `carbon_balance.py`.
- `python tests/test_level2.py`: 15 passed, 0 failed, 0 skipped. `python tests/test_model.py`: 16 passed, 0 failed, 0 skipped. Both through the fallback runner; **pytest is not installed in this sandbox and has not been run**.

### Failed checks / problems
- First draft of the M5 identifiability labels called P_max "determined" despite r = 0.98 with n (fixed, see above).
- A report-patch script failed once on a replacement string that no longer existed and changed nothing; re-applied.
- No test failures. The Phase 0 pytest file was not run this session.
- M5's leave-out-R8 cross-validation failed badly (chi2/pt 1629); recorded as a limitation, selection rule not altered.

### Local commands (not yet run by the user)
```
pip install numpy scipy pandas matplotlib pytest
python src/compare.py --stage fit  --models M0,M1,M2,M3,M4,M5,M6
python src/compare.py --stage loro --models M0,M1,M2,M3,M4,M5,M6
python src/compare.py --stage select && python src/compare.py --stage r6diag
python src/uncertainty.py --stage r7 --models M5,M0 && python src/uncertainty.py --stage fixedgrid --models M5,M0
python src/uncertainty.py --stage profile --models M5 && python src/uncertainty.py --stage profile --models M0
python src/uncertainty.py --stage assemble --models M5,M0
python src/plant_uncertainty.py --stage predict && python src/plant_uncertainty.py --stage design && python src/plant_uncertainty.py --stage ksens && python src/plant_uncertainty.py --stage discriminate && python src/plant_uncertainty.py --stage plot
python src/carbon_balance.py --data-dir data/raw --root .
pytest -q
```

### Next step
Stop. Level 3 starts only after the user reviews the Level 2 outputs and decides which structure(s) and K_s value to carry forward.

---

## Level 2 packaging repair (2026-10-27)

**Trigger:** the user reported an incomplete, flattened ZIP. **No analysis was re-run.**

- Inventoried the workspace: every table, work JSON and figure referenced in `reports/level2.md` exists (including `parameter_profiles_M0.png`). The only missing items were `README.md` and `requirements.txt`, and the report generators, which had been kept outside the project in `/tmp`; all three groups were added.
- Byte-compared the raw CSVs, `phase0_inspect.py`, `test_phase0.py`, `CLAUDE.md`, the brief, `pre_fit_observations.md`, the Phase 0 tables and `raw_curves.png` with the uploads: all identical. `kinetics.py`, `fit.py` and `level1_parameters.csv` still match the delivered Level 1 copy and the frozen hash.
- `data/raw/CHECKSUMS.sha256` is unavailable from the upload; it was regenerated from the supplied CSVs in the sandbox (`sha256sum -c` passes).
- Added `tests/test_report_claims.py` (11 tests). It found no numerical error; one inconsistency of rounding was fixed (R2 rate 2.525 g/L/h: Level 1 said 2.53, Level 2 said 2.52; Level 2 now says 2.53) and the Level 2 report was regenerated.
- Reconciled `docs/requirements_traceability.csv` with the evidence on disk (all evidence paths exist); statuses changed: CL-11 (pytest/local unverified), CL-12 (checked by test), B-D2 (final report not written), B-P1 (partial), U0-06/07/09 (Phase 0 tests re-run via a pytest stand-in); five packaging rows added (P-01 to P-05).
- Executed this session: `tests/test_model.py` 16 passed; `tests/test_level2.py` 15 passed; `tests/test_report_claims.py` 11 passed (fallback runners); Phase 0 six tests passed through a stand-in for `pytest.fixture`/`approx`. **Not executed:** pytest itself; anything on the user's machine.


---

## Level 3 - optimisation, engineering interpretation and final submission (2026-10-28)

**Trigger.** User master task: complete Level 3, produce the technical report, the traceability matrix, the
`submission/` snapshot and the final archive, without changing the frozen Level 2 selection or using R6.

**Workspace state found at the start of this session (preflight).** Canonical root
`/home/user/fermentation-kinetics`, branch `arena/b48e5f7c-fermentation-kinetics` at commit `ed55eda`
(the merge of the Task 2 pull request). Present: Phase 0, Level 1 and Level 2 sources, reports, tables,
figures, frozen records, Task 2 evidence under `outputs/audits/task2/`, and the 60-test suite. Absent:
`src/level3*.py`, `scripts/`, `submission/`, `reports/level3.md` and the final archive. Every earlier run of
these was in a workspace that no longer exists; they were **not** present in this checkout and were rebuilt
here. Interpreters: sandbox `python3` 3.11.2 with no scientific stack, so a virtual environment was created
at `/tmp/fk-venv` (numpy 2.4.6, scipy 1.17.1, pandas 3.1.0, matplotlib 3.11.2, pytest 9.2.0) - matching the
environment recorded for the earlier sessions.

**Baseline test run before any change:** `python -m pytest -q` -> `60 passed in 4.74s`.

### Preflight gate 1 - the reported Windows CRLF failure
- Reproduced in the sandbox with a `sitecustomize.py` shim that makes `pandas.DataFrame.to_csv` default to
  `lineterminator="\r\n"`, i.e. the documented Windows default (`os.linesep`). Ran
  `python src/phase0_inspect.py` under the shim: `outputs/tables/data_quality.csv` came out with 138 CRLF
  line endings and 0 bare LF. The targeted test then failed with exactly the reported message:
  `AssertionError: outputs/tables/data_quality.csv contains CRLF`. Log:
  `outputs/audits/level3/preflight/crlf_repro/before_fix_windows_default_pytest.log`.
- **Actual cause:** `pandas.DataFrame.to_csv` defaults its line terminator to `os.linesep`, so on Windows
  every generated table is CRLF regardless of encoding. Task 2 had fixed the *encoding* of text `open()`
  calls but not the pandas line terminator. Raw data and tests were not touched.
- **Fix:** all 35 `to_csv` call sites across the 8 writer modules now pass `encoding="utf-8"` and
  `lineterminator="\n"`. After the fix the same simulated-Windows run produces 0 CRLF and the test passes
  (`after_fix_windows_default_pytest.log`). Added
  `tests/test_task2_consistency.py::test_all_csv_writers_pin_utf8_and_lf_line_terminator`, an AST guard that
  fails if any future writer omits either argument.

### Preflight gate 2 - frozen model policy
`src/level3.py::verify_model_policy` re-derives, and the audit records in
`outputs/audits/level3/model_policy.json`: frozen preferred model M5, rule D-24,
`r6_used_for_selection = false`, Level 1 holdout R6 not in the training set, `model_comparison.csv` and
`candidate_parameters.csv` SHA-256 both matching the frozen record, `level1_parameters.csv` matching its
frozen hash, and `fit_M5.json` reproducing `candidate_parameters.csv` to 1e-12 (status 3, 0 solver failures,
0 parameters at a bound, 8/8 multistarts near-best). All 12 checks pass.

### Preflight gate 3 - economics and the steam curve
Constants and the eight-point steam curve were transcribed from `docs/assignment_brief.md` section 4 into
`src/level3.py` and cross-checked against the existing `src/plant_uncertainty.py`. The curve is interpolated
only inside 7-14 % v/v; outside it the intensity is NaN and no margin is assigned. Recorded as unresolved:
the original PDF is unavailable, so PDF-only wording and the curve's provenance beyond its eight points
cannot be confirmed.

### Work performed (commands actually executed, in order)
```
python -m pytest -q                                             # 60 passed (baseline)
# preflight CRLF reproduction and fix (see above)
python src/level3_optimize.py --stage input_audit                # 18 inputs, checksums OK, policy OK
python src/level3_optimize.py --stage grid                       # 1,572 rows in 11.6 s
python src/level3_optimize.py --stage recommend                  # 16 recommendation rows, 17 economics rows
python src/level3_optimize.py --stage uncertainty --n-draws 200   # 100 rows, 19.4 s
python src/level3_optimize.py --stage model_comparison           # 12 rows
python src/level3_optimize.py --stage horizon                    # 27 unfinished, 26 complete by 240 h
python src/level3_optimize.py --stage figures                    # 4 figures
python src/level3_optimize.py --stage answers                    # 12 answered questions
python src/make_level3_report.py                                 # reports/level3.md, 21 tracked claims
python src/level3_consistency_audit.py                           # 31/31 checks passed
python -m pytest -q                                              # 81 passed (60 pre-existing + 21 new)
python scripts/build_submission.py ; python scripts/verify_submission.py
python scripts/run_final_validation.py                           # full chain, see outputs/audits/level3/final_validation.json
```

### Results (from the generated tables, not from expectation)
- Normal 33-37 C: **195 g/L TRS at 33 C**, complete in 35.571 h, 86.32 g/L ethanol, wash 10.94 % v/v,
  211,696 INR per batch, cycle 43.571 h, **4,858.69 INR/h** (116,608 INR/day derived).
- Minimum 36 C: **175 g/L TRS at 36 C**, complete in 39.817 h, 76.73 g/L ethanol, **3,710.13 INR/h**;
  1,148.56 INR/h (23.6 %) below the normal scenario.
- Status counts on the primary horizon for M5: 443 completed feasible, 31 completed outside the steam curve,
  27 unfinished, 0 simulation failures. The highest-ethanol completed candidates all lie above 14 % v/v and
  are therefore never priced.
- Brief Q5 (37 C, 260 g/L): does not complete within 120 h; 105.37 g/L ethanol and 30.26 g/L TRS at 120 h.
  Reported as a low-trust extrapolation.
- Uncertainty (200 Gaussian parameter draws per model): margin 4,641.97-5,038.55 INR/h at the normal optimum
  and 3,538.06-3,858.37 INR/h at the warm optimum; every draw completes. Discrete CO2-floor alternatives
  move the normal optimum only between 4,842.97 and 4,873.75 INR/h.

### Scientific decisions taken while doing this, and why
- **No local optimiser.** The objective is flat within about 10 INR/h over 187.5-200 g/L, so a deterministic
  coarse/dense/refinement grid is more informative than a gradient search, and it exposes the infeasible
  region instead of hiding it. The refinement confirmed the optima are not grid artefacts.
- **120 h primary horizon, 240 h diagnostic.** The 240 h run is reported but never used for ranking, to show
  that the horizon is not concealing a better candidate (26 of the 27 unfinished cases eventually complete;
  none would outrank the recommendation).
- **Completed-but-out-of-curve is its own status.** Those batches are real completions, but the supplied
  steam curve does not cover them, so they get no steam cost and no margin rather than an extrapolated one.
- **M2 and M6 are comparisons, never substitutions.** They are 4.0-4.8 % higher in margin at their own
  optima and shift the sugar charge by one grid step; the recommendation stays M5 because D-24 selected it.

### Failures and corrections during this session (kept, not hidden)
- Test bugs found while writing `tests/test_level3.py`: an incorrect hand-computed expectation for the
  interpolated crossing time (1.5 h instead of 1.667 h) and a `DataFrame.median` name clash. Both were test
  errors, corrected in the test; the production code was not changed to make them pass.
- Report-generator defects found by reading the generated output and corrected: a duplicated "INR/h per
  hour" phrase, a negative-signed penalty presented as a cost, a parameter table with an empty unit column,
  `../outputs/...` figure links (which the existing reference test rejects), and - most importantly - a
  sentence claiming both fitted temperature multipliers were below 1. That claim was **wrong**: k34 = 1.0865
  is above 1. The section now states the correct mechanism (ethanol tolerance falling with temperature,
  with the simulated completion times at 195 g/L quoted for each temperature).
- `scripts/build_submission.py` initially failed its own required-item check because
  `requirements_traceability.csv`, `pytest.ini` and the validation record did not exist yet. The matrix and
  `pytest.ini` were created; the validation record is now treated as an optional source that is reported as
  pending on the provisional build.

### Not done / still open
- **Actual Windows execution** of the test suite and `scripts/reproduce_level3.ps1` - not performed here;
  only a Linux simulation of the Windows line-terminator default. The simulated failure also printed pytest's
  older-style one-line assertion detail, so the exact rendering on the user's machine may differ.
- The original assignment PDF is unavailable; the extracted brief governs.
- The recommendations are model optima, not plant-validated optima; predictive uncertainty is not quantified.
- `AI_USE.md` personal-contribution section is deliberately left for the student.
