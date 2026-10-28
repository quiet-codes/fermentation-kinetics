# Pre-Level-3 Project Audit (Task 1)

**Audit date:** 2026-10-27 (UTC)  
**Repository:** `/home/user/fermentation-kinetics`  
**Branch:** `arena/30692720-fermentation-kinetics` at `4877c332a4ec95509c015a753740e50c6b7e7c50`  
**Scope:** read-only audit of the existing Phase 0, Level 1 and Level 2 project. No Level 3 work, no plant optimisation, no raw-data edits, no source/test/frozen-decision/report edits, no final ZIP.  
**Upload caveat:** the only accessible project material is one complete Git checkout with one grafted commit. No separate upload-batch directory exists under `/home/user`. I therefore treated the attached repository as the complete upload for this audit. If more batches are still pending, this audit must be revisited.  
**Machine-readable companion:** `outputs/audits/pre_level3_audit.json` contains all 109 pre-existing files, their SHA-256 hashes, statuses, checks, commands and findings.

---

## 1. Actual project structure and file inventory

### 1.1 Root and structure

```text
fermentation-kinetics/  (project root; single Git checkout)
  .gitignore, AI_USE.md, CLAUDE.md, README.md, requirements.txt, worklog.md
  data/raw/          runs.csv, timecourse.csv, endpoint_hplc.csv, CHECKSUMS.sha256
  docs/              assignment_brief.md, requirements_traceability.csv
  src/               11 .py files; __pycache__/ (7 tracked .pyc files)
  tests/             4 .py files (48 test functions); __pycache__/ (4 tracked .pyc files)
  outputs/tables/    34 .csv + 2 frozen .json; work/ (20 intermediate .json files)
  outputs/figures/   9 .png files
  outputs/audits/    NEW: pre_level3_audit.md, pre_level3_audit.json (this audit)
  reports/           pre_fit_observations.md, level1.md, level2.md
  handoff/           DECISIONS.md, PROJECT_STATE.md, NEXT_ACCOUNT_PROMPT.md
```

Counts (excluding `.git` and the two new audit files): 109 files. 11 Python source files, 4 test source files (48 test functions), 34 top-level generated CSVs, 2 top-level frozen JSON records, 20 work JSON records, 9 PNG figures, 3 reports, 3 handoff files, 2 docs, 3 raw CSVs, 1 checksum file, 12 tracked `.pyc` build artifacts, and project metadata.

### 1.2 Complete path inventory

All paths below are relative to the actual project root. Every path is already in its intended project location; there are no separate upload files to place.

```text
.gitignore
AI_USE.md
CLAUDE.md
README.md
data/raw/CHECKSUMS.sha256
data/raw/endpoint_hplc.csv
data/raw/runs.csv
data/raw/timecourse.csv
docs/assignment_brief.md
docs/requirements_traceability.csv
handoff/DECISIONS.md
handoff/NEXT_ACCOUNT_PROMPT.md
handoff/PROJECT_STATE.md
outputs/figures/carbon_balance_all_runs.png
outputs/figures/ethanol_yield_gap.png
outputs/figures/heldout_prediction.png
outputs/figures/level1_fits.png
outputs/figures/model_comparison_residuals.png
outputs/figures/parameter_profiles_M0.png
outputs/figures/parameter_profiles_M5.png
outputs/figures/plant_uncertainty.png
outputs/figures/raw_curves.png
outputs/tables/candidate_parameters.csv
outputs/tables/carbon_balance_all_runs.csv
outputs/tables/data_quality.csv
outputs/tables/endpoint_diagnostics.csv
outputs/tables/ethanol_yield_pooled.csv
outputs/tables/ethanol_yields.csv
outputs/tables/experiment_design.csv
outputs/tables/experiment_discrimination.csv
outputs/tables/fixed_parameter_sensitivity.csv
outputs/tables/heldout_metrics.csv
outputs/tables/heldout_predictions.csv
outputs/tables/level1_correlations.csv
outputs/tables/level1_fit_diagnostics.csv
outputs/tables/level1_frozen.json
outputs/tables/level1_multistart.csv
outputs/tables/level1_parameters.csv
outputs/tables/level1_sensitivity.csv
outputs/tables/level1_summary_numbers.csv
outputs/tables/level1_t0_diagnostics.csv
outputs/tables/model_comparison.csv
outputs/tables/model_r6_diagnostic.csv
outputs/tables/model_residuals.csv
outputs/tables/model_selection_frozen.json
outputs/tables/parameter_correlations_material.csv
outputs/tables/parameter_profiles.csv
outputs/tables/parameter_uncertainty.csv
outputs/tables/plant_Ks_sensitivity.csv
outputs/tables/plant_linearised_sd.csv
outputs/tables/plant_prediction_uncertainty.csv
outputs/tables/preliminary_carbon_balance.csv
outputs/tables/r7_inclusion_effect.csv
outputs/tables/r7_review.csv
outputs/tables/run_descriptive_summary.csv
outputs/tables/structure_spread.csv
outputs/tables/variance_decomposition.csv
outputs/tables/work/fit_M0.json
outputs/tables/work/fit_M1.json
outputs/tables/work/fit_M2.json
outputs/tables/work/fit_M3.json
outputs/tables/work/fit_M4.json
outputs/tables/work/fit_M5.json
outputs/tables/work/fit_M6.json
outputs/tables/work/fixedgrid_M0.json
outputs/tables/work/fixedgrid_M5.json
outputs/tables/work/loro_M0.json
outputs/tables/work/loro_M1.json
outputs/tables/work/loro_M2.json
outputs/tables/work/loro_M3.json
outputs/tables/work/loro_M4.json
outputs/tables/work/loro_M5.json
outputs/tables/work/loro_M6.json
outputs/tables/work/profile_M0.json
outputs/tables/work/profile_M5.json
outputs/tables/work/r7_M0.json
outputs/tables/work/r7_M5.json
outputs/tables/yield_gap_decomposition.csv
reports/level1.md
reports/level2.md
reports/pre_fit_observations.md
requirements.txt
src/__pycache__/carbon_balance.cpython-314.pyc
src/__pycache__/compare.cpython-314.pyc
src/__pycache__/fit.cpython-314.pyc
src/__pycache__/kinetics.cpython-314.pyc
src/__pycache__/models.cpython-314.pyc
src/__pycache__/plant_uncertainty.cpython-314.pyc
src/__pycache__/uncertainty.cpython-314.pyc
src/carbon_balance.py
src/compare.py
src/fit.py
src/kinetics.py
src/level1_summary.py
src/make_level1_report.py
src/make_level2_report.py
src/models.py
src/phase0_inspect.py
src/plant_uncertainty.py
src/uncertainty.py
tests/__pycache__/test_level2.cpython-314-pytest-9.1.1.pyc
tests/__pycache__/test_model.cpython-314-pytest-9.1.1.pyc
tests/__pycache__/test_phase0.cpython-314-pytest-9.1.1.pyc
tests/__pycache__/test_report_claims.cpython-314-pytest-9.1.1.pyc
tests/test_level2.py
tests/test_model.py
tests/test_phase0.py
tests/test_report_claims.py
worklog.md
```

### 1.3 Required deliverables

| Required item | Actual path | Status | Evidence / caveat |
|---|---|---|---|
| brief | `docs/assignment_brief.md` | **present, unverified source** | Text extraction is present; original PDF/table image is not. D-03 row-order mapping needs user confirmation. |
| instructions | `CLAUDE.md` | **present** | Objective, rules, handoff rules. |
| raw-1 | `data/raw/runs.csv` | **present** | Matches regenerated CHECKSUMS.sha256; original external checksum file unavailable. |
| raw-2 | `data/raw/timecourse.csv` | **present** | Matches regenerated CHECKSUMS.sha256. |
| raw-3 | `data/raw/endpoint_hplc.csv` | **present** | Matches regenerated CHECKSUMS.sha256. |
| source | `src/*.py` | **present** | 11 scripts; no orchestration/lockfile. |
| tests | `tests/*.py` | **present** | 4 files, 48 test functions; 48 passed in this sandbox. |
| phase0-report | `reports/pre_fit_observations.md` | **present** | Pre-fit observations and hypotheses. |
| level1-report | `reports/level1.md` | **present** | Regenerated byte-for-byte from its generator in sandbox. |
| level2-report | `reports/level2.md` | **present** | Regenerated byte-for-byte from its generator in sandbox. |
| tables | `outputs/tables/` | **present** | 34 CSV, 2 frozen JSON, 20 work JSON; all parse. |
| figures | `outputs/figures/` | **present** | 9 PNG files; all have valid PNG signatures. |
| frozen-l1 | `outputs/tables/level1_frozen.json + level1_parameters.csv` | **present, hash verified** | SHA-256 of parameters file matches frozen record. |
| frozen-l2 | `outputs/tables/model_selection_frozen.json + model_comparison.csv + candidate_parameters.csv` | **present, hashes verified** | M5, rule D-24, r6_used_for_selection=false; both stored hashes match. |
| traceability | `docs/requirements_traceability.csv` | **present** | 64 rows; 124 path-like evidence tokens all resolve. Statuses need updating for this audit and Windows result. |
| decisions | `handoff/DECISIONS.md` | **present** | D-01..D-36, including D-03, D-24, D-29. |
| handoff | `handoff/PROJECT_STATE.md, handoff/NEXT_ACCOUNT_PROMPT.md, worklog.md, AI_USE.md` | **present** | Historical execution claims conflict; see section 2.5. |
| deps | `requirements.txt` | **present** | numpy, scipy, pandas, matplotlib, pytest; no lock file. |
| final-report | `not present` | **missing / not started** | README and traceability mark it not started; component reports exist. |
| level3 | `not present` | **missing / not started** | Correctly not started; must not be started in Task 1. |
| windows-log | `not present` | **missing** | Only the user-supplied one-line error is available; full traceback needed. |
| original-pdf | `not present` | **missing** | Required to confirm D-03 uncertainty table alignment. |
| original-checksum | `not present` | **unverified** | Current file is a sandbox regeneration; cannot prove original raw bytes externally. |

### 1.4 Missing, incomplete or unverified items

| Item | Status | Why it matters |
|---|---|---|
| Original assignment PDF / screenshot of section 3 uncertainty table | **missing** | D-03 row-order mapping cannot be confirmed. |
| Original CHECKSUMS.sha256 from the user | **unverified** | Raw CSVs match the regenerated copy, but not independently tied to original upload. |
| Full Windows pytest log and environment | **missing** | Cannot confirm exact code point, encoding, Python version, or traceback line. |
| Actual Windows rerun of report generators / tests | **not executed in this audit** | Root cause is strongly supported by a Linux cp1252 simulation, not by Windows execution. |
| Full Level 2 numerical reproduction | **not executed in this audit** | Would be destructive to frozen outputs; historical execution is documented but not re-run here. |
| Final consolidated report | **not started** | Brief s7 final deliverable outstanding; component reports are present. |
| Level 3 optimisation and economics recommendation | **not started** | Correctly deferred; must not be done in Task 1. |
| D-03 and CO2 floor user confirmation | **unverified** | Affects scientific interpretation of all fits, QAICc, profiles and carbon-balance intervals. |
| Local Windows test fix verification | **unverified** | The 46 passed / 2 failed result remains unresolved until user reruns after a fix. |
| Git history for Phase 0 / Level 1 preservation claims | **unverified** | Repository has one grafted commit; byte-preservation claims rely on handoff/worklog, not commit history. |

### 1.5 Conflicts and packaging issues

- No duplicate basenames, no case-insensitive path collisions, no untracked or ignored files, and no partial batch directory were found.
- The repository has exactly one grafted commit. It cannot independently prove that Phase 0/Level 1 files were byte-identical to earlier uploads; those claims come from `worklog.md`, `AI_USE.md` and `handoff/PROJECT_STATE.md`.
- 12 `.pyc` files are tracked in Git under `src/__pycache__/` and `tests/__pycache__/`. They are build artifacts, not deliverables. `.gitignore` is empty.
- No `pyproject.toml`, `setup.cfg`, `pytest.ini`, `tox.ini`, `conftest.py`, `.gitattributes`, lock file, or encoding configuration exists.
- All three reports are UTF-8 with LF line endings. Generated tables/JSON are ASCII. `outputs/figures/raw_curves.png` exists and is valid, but its filename is not explicitly written in any report; the Phase 0 report refers only to "raw curves".

---

## 2. Audit of each phase and its evidence

### 2.1 Phase 0

**Present evidence:** `CLAUDE.md`, `docs/assignment_brief.md`, `data/raw/` (3 CSVs + regenerated checksum), `src/phase0_inspect.py`, `tests/test_phase0.py` (6 tests), `reports/pre_fit_observations.md`, `outputs/tables/data_quality.csv`, `endpoint_diagnostics.csv`, `preliminary_carbon_balance.csv`, `run_descriptive_summary.csv`, `outputs/figures/raw_curves.png`, decisions D-01..D-09, and the Phase 0 worklog.

**Scientifically supported:** the report separates observations, the pre-fit answer to brief Q1, and untested hypotheses. Raw data checks in this audit found 8 runs, 14 time points per run, no duplicates, and all three raw CSVs matching the current checksum file. All 8 runs appear in the Phase 0 carbon-balance table.

**Unverified / incomplete:** D-03 reads the brief's PDF-extracted uncertainty table in row order. The original PDF is missing, so the row alignment cannot be confirmed. The Phase 0 preliminary balance treats `n.d.` lactic acid as 0, while Level 2 later uses a uniform `[0, 0.2)` g/L convention; this is a documented change of convention (D-05 vs D-26). The Phase 0 report does not name `raw_curves.png`.

### 2.2 Level 1

**Present evidence:** `src/kinetics.py`, `src/fit.py`, `src/level1_summary.py`, `src/make_level1_report.py`, `tests/test_model.py` (16 tests), `reports/level1.md`, figures `level1_fits.png` and `heldout_prediction.png`, all `level1_*` and `heldout_*` tables, `level1_frozen.json`, decisions D-10..D-21, and the Level 1 worklog.

**Read-only verification:** `level1_frozen.json` stores `co2_floor=0.1`, `holdout=R6`, training runs `R1,R2,R3,R4,R5,R8`, `biomass_excluded=R3`, and `chi2=3675.254998574371` with `reduced_chi2=12.629742263142`. Its SHA-256 of `level1_parameters.csv` matches the current file. `tests/test_model.py` verifies R6/R7/R3-biomass/t=0 exclusion by perturbation, nominal initial states, measurement SD formulas, and reproduction of stored held-out predictions from frozen parameters. The report states the baseline does not fit within the stated noise and lists the CO2 floor, fixed K_s and R6 limitations.

**Protocol nuance:** `fit.py:stage_fit` calls `read_raw()` before filtering to `policy["train"]`, so the full `timecourse.csv` is technically loaded into memory. The comment "R6 and R7 are never loaded here" is stronger than the literal code. The tests show those rows do not enter the objective. `stage_predict` verifies the frozen hash before constructing R6 records. No leakage into fitting or selection was found, but the documentation should say "only training records are constructed/used", not "R6/R7 are never loaded".

### 2.3 Level 2

**Present evidence:** `src/models.py`, `compare.py`, `uncertainty.py`, `plant_uncertainty.py`, `carbon_balance.py`, `make_level2_report.py`, `tests/test_level2.py` (15 tests), `tests/test_report_claims.py` (11 tests), `reports/level2.md`, 34 top-level CSVs, 20 work JSONs, 9 figures, `model_selection_frozen.json`, decisions D-22..D-36, handoff and worklog.

**Frozen selection:** `model_selection_frozen.json` says `preferred=M5`, `best_QAICc_model=M5`, `rule=D-24`, `c_hat=3.8629121857647286`, `r6_used_for_selection=false`. Its SHA-256 values for `model_comparison.csv` and `candidate_parameters.csv` both match. `model_comparison.csv` has all 7 candidates, `M3` at a bound, all `starts_near_best=8/8`, zero ODE failures, M5 QAICc 309.764 and M6 104.994 units behind. Recomputing chi-square from `model_residuals.z` matches `model_comparison.chi2` for every model to within 4.6e-13.

**Selection-rule gap:** D-24 says "whose multistart converged to one minimum". `compare.py:stage_select` actually filters only `params_at_bound == 0` and `ode_failures == 0`; it records `starts_near_best` but does not use it in the filter. Current work JSONs show all 7 candidates had `n_near_best=8` of `8` and solver status 3, so the outcome is unchanged, but the code does not fully encode the written rule. `model_residuals.csv` is not included in the frozen hash, though its chi-square is internally consistent.

**Uncertainty and identifiability:** `parameter_uncertainty.csv` has 21 rows (M5: 10 fitted + 1 fixed; M0: 8 fitted + 2 fixed). All fitted profile intervals in the current table are closed and contain their estimates. The report discloses the P_max/n ridge, k37 resting on one run, K_s = 1 g/L being disfavoured, and jackknife spread exceeding within-fit intervals.

**Carbon and yield:** `carbon_balance_all_runs.csv` contains all 8 runs. Recovery is 98.247-104.745%, mean 101.036%; only R4 does not close within its MC 95% interval. Pooled yield is 0.459409 g/g TRS consumed (89.828% of 0.5114). `yield_gap_decomposition.csv` is exactly additive (max residual 1.8e-14); mean gap components are biomass 5.702, glycerol 4.546, lactic 0.631, excess CO2 0.465 and unaccounted -1.210 points.

**Plant-relevant work, not optimisation:** `plant_uncertainty.py` evaluates four fixed scenarios only and a test asserts no optimiser names are present. It propagates linearised-Gaussian parameter draws, profile ensembles, structure spread, K_s sensitivity, variance decomposition and experiment-design criteria. `stage_predict` performs a labelled M5+R6 secondary refit but does not save that refit as a work JSON; the plant quantities are in `structure_spread.csv`.

**Level 2 limitations already disclosed:** no candidate fits within noise; residual lag-1 autocorrelation 0.54-0.69; M5 fails leave-out-R8 (chi2/pt 1629); one 37 C run; no 33/36 C runs; run-to-run variability unmeasured; R7 unusual but contamination unproven; R4 carbon imbalance; D-03 and CO2 floor unconfirmed.

### 2.4 Cross-phase integrity and reproducibility

- `cd data/raw && sha256sum -c CHECKSUMS.sha256`: 3 OK. The checksum file is a regeneration, not the user's original.
- `level1_frozen.json` and `model_selection_frozen.json` hashes: all match.
- 22 JSON files parse; 38 CSV files parse; 9 PNG signatures are valid.
- All path-like references in the 3 reports, README, handoff, worklog, AI-use note, decisions and traceability resolve when bare filenames are checked against `outputs/tables/`, `outputs/figures/`, `data/raw/`, `src/`, `tests/`, `reports/`, `handoff/` and `docs/`. Two apparent unresolved strings (`_report.py`, `_1.md`) are regex artifacts from longer names.
- `docs/requirements_traceability.csv` has 64 rows and 124 path-like evidence tokens; all resolve. Its statuses still say pytest/local runs are unverified and mark final report / Level 3 as not started.
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider`: 48 passed in this Linux sandbox. Git status remained clean.

### 2.5 Conflicting historical execution records

- `worklog.md` Phase 0 says `python -m pytest -q` gave 6 passed with pytest 9.1.1.
- `README.md`, `handoff/PROJECT_STATE.md`, `AI_USE.md` and `reports/level2.md` say pytest was not available in the original AI sandbox and that Phase 0 tests ran through a stand-in for `pytest.fixture`/`approx`.
- `reports/level1.md` and `reports/level2.md` say pytest was not run; the user now reports a local Windows run of 46 passed / 2 failed.
- This audit's 48-pass Linux pytest run is a new result. It does not resolve which historical claim about the earlier sandbox is true, and it is not a Windows execution.

---

## 3. Unicode failure diagnosis and evidence required

### 3.1 Code facts

- The two failing tests are `tests/test_report_claims.py::test_level2_report_equals_generator_output` and `::test_level1_report_equals_generator_output` (`tests/test_report_claims.py:32-39`). There are 48 tests in total, so 46 passed / 2 failed matches these two.
- `_regen()` calls `subprocess.run([sys.executable, src/script, out], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)` (`tests/test_report_claims.py:27-29`). It reads the result back with explicit `encoding="utf-8"`.
- Stdout is discarded; `stderr` is not redirected and is captured by pytest. No `encoding` argument is passed to `subprocess.run`, and no decoding of the child's stdout occurs.
- `src/make_level1_report.py:184` uses `open(OUT,'w').write(rep)`. `src/make_level2_report.py:329` uses `open(OUT,'w').write(rep); print(len(rep))`. Neither specifies `encoding`, so Python uses the locale-dependent default text encoding.
- The committed reports are UTF-8 and contain non-ASCII characters. Under cp1252, `reports/level1.md` has only `U+2212 MINUS SIGN` as unencodable; `reports/level2.md` has `U+0394`, `U+20B9`, `U+2192`, `U+2212`, `U+2248`, `U+2264` and `U+2265`. Therefore replacing only U+2212 would not fix Level 2.
- There is no encoding config, `.gitattributes`, `PYTHONUTF8` setting, or `sys.stdout.reconfigure` in the project. `PYTHONIOENCODING` would affect streams but not `open(OUT,'w')`.

### 3.2 Sandbox diagnosis (not Windows)

1. Control: with only `PYTHONIOENCODING=cp1252`, both report tests passed (2 passed). This rules out stdout/stderr stream encoding as the direct cause.
2. Simulation: a temporary `sitecustomize.py` forced `.md` writes from the two generator scripts to use `cp1252`, emulating a Windows ANSI default. Direct runs produced:
   - `make_level1_report.py`: `UnicodeEncodeError: 'charmap' codec can't encode character '\u2212' in position 9745` at `src/make_level1_report.py:184`.
   - `make_level2_report.py`: `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 2358` at `src/make_level2_report.py:329`.
   - Both temporary output files were left at 0 bytes because `open(OUT,'w')` truncates before the failed write.
3. Under that simulation, the two report tests failed with `subprocess.CalledProcessError`; the rest of the suite would give exactly 46 passed / 2 failed.

### 3.3 Most likely root cause

The most likely root cause is locale-dependent implicit text-file encoding in both report generators, not the test's stdout redirection. On a Windows Python whose default locale encoding is cp1252 (or another charmap codec), `open(OUT,'w')` cannot encode the Unicode report text. The user's quoted U+2212 exactly matches the Level 1 first failure. Static inspection predicts the Level 2 first cp1252 failure is U+2192, not U+2212; therefore the full Windows traceback is needed to confirm which character and code page each child process used. The issue is not merely cosmetic: report regeneration fails, the two consistency tests fail, and running a generator with its default output path can truncate an existing report before raising.

### 3.4 Evidence needed to confirm on Windows

Ask the user to supply or run:

```
python -c "import sys,locale,os;print(sys.version);print(locale.getpreferredencoding(False));print(locale.getencoding());print(sys.stdout.encoding);print(os.environ.get('PYTHONUTF8'));print(os.environ.get('PYTHONIOENCODING'))"
chcp
pytest -q tests/test_report_claims.py::test_level1_report_equals_generator_output tests/test_report_claims.py::test_level2_report_equals_generator_output -vv
```

The full traceback for each of the two failures should include the child script path, line number (`make_level1_report.py:184` or `make_level2_report.py:329`), codec name, code point and position. Also record whether UTF-8 mode is enabled and whether any IDE, shell or `sitecustomize` changes the default encoding. No fix was applied in this audit.

---

## 4. D-03 uncertainty mapping and CO2-floor status

### 4.1 Brief and decision

`docs/assignment_brief.md` section 3 is PDF-extracted text. Its method/uncertainty columns are visually scrambled, and the CO2/by-product rows say only "About +/-2%" and "About +/-3%". D-03 reads the table in row order: biomass, TRS, ethanol, CO2, by-products (glycerol/lactic), pH. The original PDF is not in the repository, so this alignment is unconfirmed. No exact formula should be invented for the two approximate rows; the audit reports the implementation's interpretation only.

### 4.2 Implementation map

| Measurement | Brief text | Implemented SD | Where | Status |
|---|---|---|---|---|
| Biomass | +/-(3.5% + 0.08 g/L) | `0.035 * measured + 0.08` g/L | `phase0_inspect.py:54`, `fit.py:45`, `carbon_balance.py:29` | Matches D-03 row-order interpretation; "3.5% of measured value" is the code's reading. |
| TRS | +/-(1% + 0.4 g/L) | `0.01 * measured + 0.4` g/L | `phase0_inspect.py:55`, `fit.py:46`, `carbon_balance.py:30` | Matches D-03 interpretation. |
| Ethanol | +/-(1.2% + 0.25 g/L) | `0.012 * measured + 0.25` g/L | `phase0_inspect.py:56`, `fit.py:47`, `carbon_balance.py:31` | Matches D-03 interpretation. |
| Cumulative CO2 | "About +/-2%" | fitting: `0.02 * measured + 0.10` g/L; Phase 0 / Level 2 carbon MC: `0.02 * measured` | `fit.py:37,48,50-58`; `phase0_inspect.py:57`; `carbon_balance.py:32` | The relative 2% is an interpretation of an approximate statement. The extra 0.10 g/L floor is an analyst assumption, not in the brief. |
| Glycerol / lactic acid | "About +/-3%" | `0.03 * measured` g/L for glycerol and detected lactic; `n.d.` lactic uses uniform `[0, 0.2)` g/L in Level 2 | `phase0_inspect.py:58`; `carbon_balance.py:72-73`; D-26 | The 3%-relative choice is an interpretation of an approximate statement; `n.d.` is censored-data handling, not a 3% formula. |
| pH | +/-0.04 | absolute `0.04` pH units | `phase0_inspect.py:50,234-240`; `carbon_balance.py:157` | Matches brief. |

The fitting path is `fit.residual_fn` -> `fit.sd_of` -> `fit.sd_C`; `compare.py` uses the same `fit.default_policy()` for all 7 fits, LORO, residual z-scores and the R6 diagnostic; `uncertainty.py` profiles/grids/R7 refits inherit it through `compare.resid_fun`; `plant_uncertainty.py` design/discrimination also use `fit.sd_of` for synthetic measurement noise. Therefore the 0.10 g/L floor is embedded in Level 1 estimates, all Level 2 candidate fits, QAICc, the frozen M5 selection, profile intervals and design calculations. It is not used in `phase0_inspect.py` or `carbon_balance.py` carbon-balance uncertainty.

### 4.3 CO2 floor: where, effect, and alternatives

- `CO2_FLOOR = 0.10` g/L is defined at `src/fit.py:37`, stored in `level1_frozen.json`, and applied by `fit.sd_C(c, floor)` and `default_policy()`.
- `sd_C(0) = 0.10`, so the floor prevents zero uncertainty and division by zero. In the training objective t=0 rows are excluded and the smallest positive-time CO2 is 3.0 g/L, so pure 2% would give 0.06 g/L; with the floor it is 0.16 g/L, a 2.67-fold increase. The stored median ratio is 1.118.
- D-18/D-20 predeclared two alternatives: floor 0 and floor 0.5 g/L. `fit.py:stage_sensitivity` implements them as `CO2_floor_0` and `CO2_floor_0.5`.
- `outputs/tables/level1_sensitivity.csv` contains 8 parameter rows for each alternative. Floor 0 changes `mu_max` by -13.9% and `q_max` by +7.1% (max absolute parameter change 13.88%); floor 0.5 changes parameters by at most 4.37%. `worklog.md` says the sensitivity stage was executed in the original AI sandbox. This audit did **not** re-run it; no per-case JSON or independent execution log exists, only the aggregate CSV, report text and worklog.
- These alternatives are Level 1 baseline M0 sensitivities. There is no executed seven-candidate Level 2 sensitivity for other CO2 floors and no CLI option in `compare.py` to change the floor. Re-running `compare.py --stage select` with a different floor would change the frozen decision and is prohibited.

### 4.4 Evidence needed if a new sensitivity is required

First obtain user confirmation of D-03 from the original PDF and an explicit decision on whether the floor remains an assumption or is replaced. If a new calculation is requested, pre-register the alternative floor value(s), use an isolated `--root` or copied sandbox so no frozen file is overwritten, keep the same seed/starts/solver settings, record package versions, and save new audit-only outputs. Compare training-only chi-square and parameter changes; do not compute R6 metrics for the sensitivity (D-20), do not re-run `--stage select` against the frozen decision, and do not use the result to choose a model. If Level 2 sensitivity is required, source changes would be needed to pass a custom policy to `compare.py`; that is a later task, not this audit.

### 4.5 Four distinct uncertainty concepts

- **Measurement uncertainty:** the brief's 1-sd values, used for residual weights, z-scores, endpoint diagnostics and carbon-balance Monte Carlo draws.
- **Model inadequacy:** systematic misfit not described by those sds: reduced chi-square 12.6 (M0) to 3.9 (M5), autocorrelated residuals, biomass plateau/shape errors, structure disagreement and M5's leave-out-R8 failure. `c_hat` scaling acknowledges but does not fully model this.
- **Parameter uncertainty:** profile-likelihood intervals, linearised covariance and Gaussian draws, conditional on one structure, fixed K_s/n, the weighting (including CO2 floor), and the training runs. It does not include structure error or unknown systematic bias.
- **Run-to-run variability:** LORO jackknife, R1/R4 and R5/R7 comparisons, and the pooled-yield bootstrap. It is largely unmeasured because R7 is unusual and is the only replicate. Carbon-balance MC intervals use measurement sds, not run-to-run variance.

---

## 5. Existing Level 2 execution commands in correct order

The following are the commands that actually exist in `README.md`, `worklog.md`, `reports/level2.md` and the argparse choices in the source. Phase 0 / Level 1 commands are included because the Level 2 chain starts from their outputs. The `...` form in `reports/level2.md:355` is not a literal command; the exact chained form from `worklog.md:112` is used below.

```text
pip install -r requirements.txt
python src/phase0_inspect.py --data-dir data/raw --root .
python src/fit.py --data-dir data/raw --root . --stage all
python src/level1_summary.py --data-dir data/raw --root .
python src/compare.py --stage fit  --models M0,M1,M2,M3,M4,M5,M6
python src/compare.py --stage loro --models M0,M1,M2,M3,M4,M5,M6
python src/compare.py --stage select
python src/compare.py --stage r6diag
python src/uncertainty.py --stage r7 --models M5,M0
python src/uncertainty.py --stage fixedgrid --models M5,M0
python src/uncertainty.py --stage profile --models M5
python src/uncertainty.py --stage profile --models M0
python src/uncertainty.py --stage assemble --models M5,M0
python src/plant_uncertainty.py --stage predict && python src/plant_uncertainty.py --stage design && python src/plant_uncertainty.py --stage ksens && python src/plant_uncertainty.py --stage discriminate && python src/plant_uncertainty.py --stage plot
python src/carbon_balance.py --data-dir data/raw --root .
python src/make_level1_report.py ; python src/make_level2_report.py
pytest -q
```

`compare.py` stages accept `--data-dir`, `--root`, `--n-lhs` and `--seed`, but `select` always loads all 7 `M.VARIANTS` fit JSONs and ignores `--models`. `uncertainty.py` defaults `--models M5,M0`; `profile`, `fixedgrid` and `r7` do not themselves choose the model from the frozen JSON. `plant_uncertainty.py` stages use `model_selection_frozen.json` for the preferred model. `reports/level2.md:359` says "uncertainty.py stages profile and later use the preferred model named in model_selection_frozen.json"; that is inaccurate for `uncertainty.py` and more applicable to `plant_uncertainty.py`. `plant_uncertainty.py`'s docstring also incorrectly attributes `plant_uncertainty.png` to `design`; `plot` writes it.

### 5.1 Stage dependencies, outputs and destructive side effects

| Order | Stage / command | Expected outputs | Side effect / warning |
|---|---|---|---|
| 0 | `pip install -r requirements.txt` | `installed dependencies` | no project files |
| 1 | `python src/phase0_inspect.py --data-dir data/raw --root .` | `Phase 0 tables and raw_curves.png` | rewrites those Phase 0 outputs |
| 2 | `python src/fit.py --data-dir data/raw --root . --stage all` | `Level 1 tables, frozen JSON, held-out tables and 2 figures` | rewrites Level 1 tables/figures and refreezes level1_frozen.json |
| 3 | `python src/level1_summary.py --data-dir data/raw --root .` | `level1_correlations.csv, level1_summary_numbers.csv` | rewrites those two tables |
| 4 | `python src/compare.py --stage fit  --models M0,M1,M2,M3,M4,M5,M6` | `work/fit_M0.json .. fit_M6.json` | overwrites those 7 work JSONs |
| 5 | `python src/compare.py --stage loro --models M0,M1,M2,M3,M4,M5,M6` | `work/loro_M0.json .. loro_M6.json` | overwrites those 7 work JSONs |
| 6 | `python src/compare.py --stage select` | `model_comparison.csv, candidate_parameters.csv, model_residuals.csv, model_selection_frozen.json, model_comparison_residuals.png` | rewrites and re-freezes Level 2 selection; can invalidate a later r6diag hash |
| 7 | `python src/compare.py --stage r6diag` | `model_r6_diagnostic.csv` | overwrites diagnostic; refuses if frozen comparison/parameter hashes changed |
| 8 | `python src/uncertainty.py --stage r7 --models M5,M0` | `work/r7_M5.json, work/r7_M0.json` | overwrites those 2 work JSONs |
| 9 | `python src/uncertainty.py --stage fixedgrid --models M5,M0` | `work/fixedgrid_M5.json, work/fixedgrid_M0.json` | overwrites those 2 work JSONs |
| 10 | `python src/uncertainty.py --stage profile --models M5` | `work/profile_M5.json` | overwrites that work JSON |
| 11 | `python src/uncertainty.py --stage profile --models M0` | `work/profile_M0.json` | overwrites that work JSON |
| 12 | `python src/uncertainty.py --stage assemble --models M5,M0` | `5 parameter/R7 tables and 2 profile figures` | rewrites those tables and figures |
| 13 | `python src/plant_uncertainty.py --stage predict && python src/plant_uncertainty.py --stage design && python src/plant_uncertainty.py --stage ksens && python src/plant_uncertainty.py --stage discriminate && python src/plant_uncertainty.py --stage plot` | `8 plant/design tables and plant_uncertainty.png` | rewrites those outputs; predict refits M5 with R6 as a labelled secondary result but does not save that refit as work JSON |
| 14 | `python src/carbon_balance.py --data-dir data/raw --root .` | `5 carbon/yield tables and 2 figures` | rewrites those outputs; raw CSVs are read-only |
| 15 | `python src/make_level1_report.py ; python src/make_level2_report.py` | `reports/level1.md, reports/level2.md by default` | overwrites both reports; on a non-UTF-8 Windows locale the unencoded write can truncate output before failing |
| 16 | `pytest -q` | `test results only; Phase 0 fixture uses a temporary root` | no project files when run as in this audit with bytecode/cache disabled |

`carbon_balance.py` uses raw CSVs only and can be run independently of the model chain, but `make_level2_report.py` must run after it. `make_level1_report.py` / `make_level2_report.py` accept an optional output path; with no argument they overwrite `reports/level1.md` / `reports/level2.md`. There is no single orchestration script. Most stage dependencies are enforced only by missing-file errors. `README.md` warns that re-running fitting stages rewrites frozen files and can change last digits across platforms; this audit did not run any of those destructive stages.

---

## 6. Test coverage and missing consistency checks

### 6.1 Sandbox result

`PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider` returned **48 passed in 3.70s** on Linux with Python 3.11.2, numpy 2.4.6, scipy 1.17.1, pandas 3.1.0, matplotlib 3.11.2 and pytest 9.1.1. Git status was clean before and after. This is a Linux sandbox result, not a Windows rerun and not a full numerical reproduction.

### 6.2 Coverage matrix

| Area | Existing checks | Gap | Smallest reliable addition |
|---|---|---|---|
| report text vs generated tables | test_report_claims.py: 2 equality tests plus 9 selected numeric-claim tests | No systematic check of every prose number or report asset reference; the 2 equality tests are exactly the Windows failures. | Keep equality tests and add one regression test forcing a cp1252-like default file encoding. |
| model-selection decision consistency | test_selection_rule_reproduces_and_is_frozen_before_r6; test_model_comparison_claims; test_plant_and_design_claims | Code and test reapply the simplified D-24 filter but do not programmatically enforce the written multistart convergence clause. model_residuals.csv is not hashed by the frozen record. | Add a test recomputing chi-square from model_residuals.z for all 7 models, checking starts_near_best/status and reapplying full D-24 wording without editing frozen JSON. |
| parameter estimates and uncertainty intervals | test_parameter_uncertainty_table_consistency; test_uncertainty_claims; test_fitted_parameters_inside_bounds_and_flags_consistent; test_frozen_optimum_is_a_stationary_point_of_the_training_objective | No all-parameter reconciliation from work/profile_*.json to parameter_profiles.csv and parameter_uncertainty.csv; no D-03 formula test across modules. | Add one test recomputing closed interval endpoints from profile JSON for M5/M0 and checking all fitted values lie within them. |
| all eight carbon balances | test_carbon_balance_arithmetic_and_all_runs_present checks all 8 IDs but only R2 arithmetic; test_carbon_and_yield_claims checks summary claims. | No all-eight recomputation of C_in, C_out, recovery and MC interval consistency from the three raw CSVs. | Add one all-eight raw-to-table arithmetic test using the documented n.d. central 0.1 g/L convention. |
| yield and yield-gap claims | test_yield_and_gap_decomposition_are_exact; test_carbon_and_yield_claims; test_level1_report_hand_typed_numbers | Pooled bootstrap interval and report phrase about biomass + glycerol are not reproduced from raw data for all runs. | Extend the all-eight carbon/yield test to recompute pooled yield, check_sum_minus_gap and mean gap components. |
| report references and figures | Only existence checks for a few Phase 0/Level 1 files; report generators are compared as strings. | No test resolves every report path reference or verifies every generated figure is referenced. Static scan resolved all references but raw_curves.png is not named explicitly in reports. | Add one asset-reference test for reports and traceability evidence fields. |
| raw-data integrity | test_raw_files_unchanged in test_phase0.py and test_model.py | Both compare against a regenerated CHECKSUMS.sha256; no external original hash. | Ask user for original checksum or trusted source hash; add it as a separate frozen audit record, not by editing raw data. |
| requirements traceability | No automated test; static scan in this audit resolved 124 path-like evidence tokens. | Statuses can drift and evidence paths can break without failing pytest. | Add one test parsing evidence paths and checking existence; update statuses only in a later task. |

### 6.3 Recommended smallest set

A single new test file in the next task (not created here) could add these six checks:

1. Encoding regression: run both generators into temp files under a simulated cp1252 default text encoding; assert UTF-8 bytes, exact equality to committed reports, and no truncation.
2. Asset/reference check: resolve every *.csv, *.json, *.png and *.py reference in the three reports and in requirements_traceability.csv; assert all 9 figures are accounted for.
3. Frozen-selection consistency: recompute chi-square from model_residuals.z, reapply the full D-24 wording including convergence, and verify M5 / r6_used_for_selection=false without editing model_selection_frozen.json.
4. D-03 and CO2-floor mapping: assert the six brief uncertainty formulas where implemented, record that approximate 2% and 3% have no exact brief formula, and assert the documented difference between fit.sd_C (with floor) and carbon_balance.sd_C (without floor).
5. All-eight carbon/yield recomputation: verify C_in, C_out, recovery, pooled yield and gap decomposition from raw CSVs for R1..R8 with the D-26 n.d. convention.
6. Traceability check: verify all evidence paths resolve and flag statuses that still say pytest/local runs unverified after this audit.

---

## 7. Missing, incomplete, or unverified assignment deliverables

- **Present and verified in this checkout:** assignment brief text, all 3 raw CSVs, source code, tests, Phase 0 / Level 1 / Level 2 reports, generated tables, figures, frozen Level 1 and Level 2 records, requirements traceability, decision log, handoff documents, work log, AI-use note and dependency file.
- **Missing:** original assignment PDF, original checksum file, full Windows test log/traceback, final consolidated report, Level 3 code/results.
- **Incomplete:** requirements traceability statuses (pytest/local runs now need reconciliation; final report and Level 3 correctly still open), report/figure reference test coverage, D-03 confirmation, CO2-floor decision.
- **Unverified:** actual Windows execution, original sandbox pytest claim, byte-preservation claims against earlier uploads (single grafted commit), and full Level 2 numerical reproducibility in this environment.
- **Not started by design:** Level 3 plant optimisation, final report, final ZIP.

---

## 8. Minimal, ordered implementation plan for the next task

1. **Collect evidence before editing:** obtain the original PDF/table image for D-03, the full Windows pytest traceback, and the Windows environment output listed in section 3.4. Confirm whether all upload batches are complete.
2. **Fix only the encoding defect:** in a separate task, make report file writes explicitly UTF-8 (and consider `newline="\n"`), keep report content unchanged, and add the cp1252 regression test. Re-run `pytest -q` in the Linux sandbox; ask the user to rerun on Windows and report the actual result. Do not normalize away meaningful scientific symbols unless the user requests it.
3. **Add the six consistency checks** from section 6.3 in one new test file. Do not edit the four existing test files or frozen outputs in Task 1.
4. **Reconcile records:** after the fix and Windows rerun, update `worklog.md`, `AI_USE.md`, traceability, `PROJECT_STATE.md`, `DECISIONS.md` and `NEXT_ACCOUNT_PROMPT.md` with what was actually executed, the Windows failure status, and this audit's findings. Do not retroactively claim Windows success.
5. **Resolve D-03 and the CO2 floor scientifically:** if the user confirms the current mapping and floor, record that confirmation and leave all frozen fits unchanged. If not, pre-register a sensitivity in an isolated output root, execute it with recorded settings, and label it as sensitivity only; never rerun `--stage select` over the frozen Level 2 decision.
6. **Only after user approval**, consider a separate task for Level 3 using the frozen M5 decision and an explicit user choice about M2/M6 structure band and K_s (D-31). Task 1 does not start Task 2 or Level 3.

---

## 9. Items that must remain frozen

1. docs/assignment_brief.md text as the currently authoritative specification, until the user supplies the original PDF and confirms D-03.
2. The three raw CSV files under data/raw/ and their current bytes; no raw data edits in this audit.
3. CLAUDE.md rules, especially rule 7 (held-out protocol) and rule 12 (report/table consistency).
4. D-24 pre-registered selection rule wording and D-29 frozen result: M5 is the Level 2 preferred model.
5. outputs/tables/model_selection_frozen.json, model_comparison.csv and candidate_parameters.csv; their stored SHA-256 values currently match.
6. outputs/tables/level1_frozen.json and level1_parameters.csv; their stored SHA-256 currently matches.
7. Phase 0, Level 1 and Level 2 reports, generated tables, work JSONs and figures as historical evidence; do not overwrite during Task 1.
8. R6 protocol: R6 was held out in Level 1, is not blind in Level 2, and was never used to choose the Level 2 model.
9. Primary Level 2 fixed K_s = 1 g/L and baseline n = 1 for M0; D-31 remains a user decision for Level 3, not a retroactive Level 2 change.
10. CO2 sd floor = 0.10 g/L as a documented assumption in the existing fits; any new floor value must be a separately labelled sensitivity in an isolated output root.
11. D-03 itself is unconfirmed, not frozen as scientific truth; it must not be silently replaced or assumed correct.

---

## 10. Execution provenance for this audit

### 10.1 Commands executed

All commands were run from `/home/user/fermentation-kinetics` unless a `cd data/raw` is shown. Read-only `nl`, `sed`, `grep`, `find`, `cat`, `head`, `wc` and Python heredocs inspected files; they did not run the production fitting pipeline.

- `pwd && git status --short --branch && ls -la && git ls-files`  
  read-only git/filesystem inspection; result: clean working tree on arena/30692720-fermentation-kinetics; 1 grafted commit
- `find /home/user -maxdepth 2 ... ; find . -path ./.git -prune -o -printf ... ; git status --porcelain=v1 --ignored ; git log --oneline --decorate -10`  
  read-only filesystem inspection; result: no separate upload batches; 109 files excluding .git; no untracked/ignored files
- `nl -ba CLAUDE.md README.md docs/assignment_brief.md requirements.txt`  
  static inspection; result: brief, rules, layout, reproduction commands, limitations read
- `nl -ba handoff/PROJECT_STATE.md handoff/NEXT_ACCOUNT_PROMPT.md AI_USE.md handoff/DECISIONS.md worklog.md docs/requirements_traceability.csv`  
  static inspection; result: decision log D-01..D-36, handoff, worklog, AI-use note and 64 traceability rows read
- `python - <<PY (non-ASCII character scan) ; grep -RInE "print\(|subprocess|encoding|open\(|..." src tests`  
  read-only computed + static inspection; result: identified U+2212 and other non-ASCII chars; found open(OUT,"w") in both generators
- `sed -n ... src/make_level1_report.py src/make_level2_report.py tests/test_report_claims.py tests/test_phase0.py`  
  static inspection; result: located failing tests and subprocess stdout=DEVNULL
- `grep -RInE "0\.035|0\.08|0\.012|0\.25|0\.02|0\.10|sd_|..." src tests ; grep -RInE "add_argument|--stage|choices=" src`  
  static inspection; result: mapped uncertainty formulas and all real CLI stages
- `sed -n ... src/fit.py src/compare.py src/uncertainty.py src/plant_uncertainty.py src/carbon_balance.py src/phase0_inspect.py`  
  static inspection; result: traced fitting, weighting, selection, profiles, plant design, carbon balance and report generation
- `sed -n ... tests/test_level2.py tests/test_model.py tests/test_report_claims.py tests/test_phase0.py`  
  static inspection; result: mapped 48 test functions and coverage gaps
- `python - <<PY (encode reports as cp1252, cp437, cp850, cp1250, cp1251)`  
  read-only computed diagnosis; result: Level 1 first cp1252 failure U+2212; Level 2 first cp1252 failure U+2192; Level 2 has 7 unencodable character classes
- `python --version ; python -c "locale/stdout/PYTHONUTF8/PYTHONIOENCODING" ; python -m pip --version ; importlib.metadata versions`  
  sandbox environment inspection; result: system Python 3.11.2, UTF-8, no scientific packages or pytest
- `sha256sum -c data/raw/CHECKSUMS.sha256 (from repo root)`  
  read-only check; incorrect working directory; result: FAILED open or read for 3 bare filenames; corrected in next command
- `cd data/raw && sha256sum -c CHECKSUMS.sha256`  
  read-only checksum verification; result: runs.csv OK; timecourse.csv OK; endpoint_hplc.csv OK
- `python - <<PY (verify level1_frozen.json and model_selection_frozen.json SHA-256 fields)`  
  read-only computed verification; result: all 3 stored hashes match current files
- `python -m venv /tmp/fk-audit-venv && /tmp/fk-audit-venv/bin/python -m pip install --upgrade pip -q && /tmp/fk-audit-venv/bin/python -m pip install -r requirements.txt -q`  
  sandbox dependency installation outside repo; result: numpy 2.4.6, scipy 1.17.1, pandas 3.1.0, matplotlib 3.11.2, pytest 9.1.1
- `PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider`  
  sandbox test execution; result: 48 passed in 3.70s; git status clean before and after
- `mkdir -p /tmp/fk-cp1252-sim ; cat > /tmp/fk-cp1252-sim/sitecustomize.py <<PY ... PY ; PYTHONPATH=/tmp/fk-cp1252-sim ... python src/make_level1_report.py /tmp/... ; ... python src/make_level2_report.py /tmp/...`  
  sandbox cp1252 simulation; NOT a Windows run; result: Level 1 UnicodeEncodeError U+2212 at position 9745; Level 2 U+2192 at position 2358; both temp outputs left 0 bytes
- `PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=cp1252 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider tests/test_report_claims.py::test_level1_report_equals_generator_output tests/test_report_claims.py::test_level2_report_equals_generator_output`  
  sandbox control test; result: 2 passed; stdout/stderr encoding alone does not cause the failure
- `PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONPATH=/tmp/fk-cp1252-sim /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider tests/test_report_claims.py::test_level1_report_equals_generator_output tests/test_report_claims.py::test_level2_report_equals_generator_output`  
  sandbox simulated-encoding test execution; result: 2 failed, matching the user-reported 46 passed / 2 failed pattern
- `python - <<PY (parse all JSON/CSV; verify PNG signatures; resolve report/traceability references; check line endings; check duplicate basenames)`  
  read-only computed checks; result: 22 JSON parse, 38 CSV parse, 9 valid PNG, no duplicate basenames or case collisions, reports UTF-8 with LF
- `python - <<PY (summary of model_comparison, frozen selection, candidate parameters, parameter_uncertainty, carbon balances, yields, CO2 floor sensitivity, residual chi-square)`  
  read-only numerical consistency checks; result: frozen M5 hashes match; residual chi-square matches model_comparison to <=4.6e-13; all 8 carbon balances present; floor alternatives present in level1_sensitivity.csv
- `git rev-list --count HEAD ; git log --format=... ; git remote -v ; git branch --show-current ; git status --short --branch`  
  read-only git inspection; result: 1 grafted commit, branch arena/30692720-fermentation-kinetics, clean tree

A few diagnostic commands failed without changing project files and were corrected: `sha256sum -c data/raw/CHECKSUMS.sha256` from the repo root (bare filenames), two Python heredocs using system Python without pandas, one malformed reference-extraction regex, and `file -bi` (the `file` utility is absent). The corrected checks passed.

### 10.2 Sandbox execution vs static inspection

- **Sandbox execution:** dependency installation into `/tmp/fk-audit-venv`; `pytest -q`; `phase0_inspect.py` invoked by the Phase 0 pytest fixture into a temporary root; both report generators invoked by `_regen()` into temporary files; both generators invoked directly under the cp1252 simulation into temporary files; the two report tests under `PYTHONIOENCODING=cp1252` and under simulated cp1252 file encoding.
- **Read-only computed checks (not project code execution):** SHA-256 of files, frozen-hash comparisons, checksum verification, JSON/CSV parsing, PNG signature checks, duplicate/case-collision checks, Unicode/code-page character scans, report/traceability reference resolution, line-ending checks, table summaries, model-selection arithmetic, residual chi-square consistency, carbon/yield summaries and test-function counts.
- **Static inspections:** reading the brief, `CLAUDE.md`, README, source code, tests, reports, decisions, worklog, AI-use note, traceability and handoff; tracing stage dependencies and side effects from code; coverage mapping.
- **Not executed:** the full Phase 0/Level 1/Level 2 production pipeline commands from section 5; any command with default report output paths; full Level 2 numerical reproduction; Level 3 optimisation; any plant economics optimisation; any code on Windows; any final ZIP creation.
- **No project source file, test, raw CSV, frozen record, generated table, figure, existing report or handoff document was modified by this audit.** The only new files are the two audit deliverables.
