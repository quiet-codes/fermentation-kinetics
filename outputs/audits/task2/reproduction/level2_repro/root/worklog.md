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

