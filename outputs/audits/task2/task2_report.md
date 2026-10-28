# Task 2 report — pre-Level-3 audit follow-up

Created 2026-10-27 15:10:37. Branch `arena/30692720-fermentation-kinetics`. **Stop after Task 2; no Level 3 and no final ZIP.**

## 1. Scope and preservation

- Used the existing project and Task 1 audit files; no restart from scratch.
- Original raw CSVs, reports, diagnostics, tables, figures, frozen JSONs, tests and decisions were not overwritten.
- All reproduction and sensitivity calculations ran in isolated roots under `outputs/audits/task2/`.
- Frozen Level 2 decision remains `M5` under `D-24`; `model_selection_frozen.json` in the original tree is unchanged.
- Level 1 `fit` and full `sensitivity` stages were intentionally not refit; `fit.py --stage predict` and `level1_summary.py` were run as prerequisite verification. Two Level 1 CO2-floor cases were verified separately.

## 2. Exact files changed

Modified tracked files (UTF-8 fix only):

- `src/compare.py`
- `src/fit.py`
- `src/make_level1_report.py`
- `src/make_level2_report.py`
- `src/plant_uncertainty.py`
- `src/uncertainty.py`

New source / test files:

- `src/reproduce_level2.py`
- `src/run_task2_sensitivities.py`
- `src/task2_co2_floor_sensitivity.py`
- `src/task2_consistency_audit.py`
- `tests/test_task2_consistency.py`

New evidence / logs: every file under `outputs/audits/task2/` except the three top-level deliverables themselves (`task2_report.md`, `task2_summary.json`, `task2_file_manifest.json`) is listed with SHA-256 in `outputs/audits/task2/task2_file_manifest.json` (284 files, 5,436,429 bytes). Main evidence roots:
- `outputs/audits/task2/d03_verification.*`
- `outputs/audits/task2/d24_convergence_check.*`
- `outputs/audits/task2/windows_utf8_fix.*`
- `outputs/audits/task2/tests/`
- `outputs/audits/task2/sensitivity/`
- `outputs/audits/task2/reproduction/level2_repro/`
- `outputs/audits/task2/reproduction/failed_attempt_1/` (retained failed first attempt)
- `outputs/audits/task2/final_checks/`
- `outputs/audits/task2/commands_executed.json`, `task2_summary.json`, `task2_file_manifest.json`

## 3. Commands executed

Full list with results: `outputs/audits/task2/commands_executed.json`. Significant commands:

| category | command | result |
|---|---|---|
| status/capacity | `git status --short --branch; nproc; grep -c ^processor /proc/cpuinfo; free -h; git branch --show-current` | Only outputs/audits/ untracked before Task 2 edits; 2 CPUs; 3.8 GiB RAM; branch correct. |
| static inspection | `grep -RIn 'open(' src/*.py; grep -RIn 'D-24\\|multistart converged' --include='*.md' --include='*.csv' .; sed -n '70,90p' docs/assignment_brief.md; grep -RIn '^def sd_' src/*.py; grep -RIn '0.04\\|0.03 \*' src/*.py` | Identified implicit text open() calls, D-24 wording/filter, brief uncertainty strings and implemented sd formulas. |
| UTF-8 fix | `PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python - <<'PY'  # AST rewrite adding encoding='utf-8' and newline='\n' to text open() calls` | 35 text open() calls updated in src/compare.py, src/fit.py, src/make_level1_report.py, src/make_level2_report.py, src/plant_uncertainty.py, src/uncertainty.py. |
| UTF-8 fix check | `PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m compileall -q src tests; /tmp/fk-audit-venv/bin/python src/make_level1_report.py /tmp/fk-utf8-check/level1.md; /tmp/fk-audit-venv/bin/python src/make_level2_report.py /tmp/fk-utf8-check/level2.md; cmp reports/level1.md /tmp/fk-utf8-check/level1.md; cmp reports/level2.md /tmp/fk-utf8-check/level2.md` | Compile OK; both generated reports byte-identical on Linux. compileall created untracked cpython-311 .pyc files which were subsequently deleted. |
| UTF-8 simulation | `PYTHONPATH=/tmp/fk-cp1252-sim PYTHONUTF8=0 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python src/make_level1_report.py /tmp/fk-utf8-check/level1_cp.md; PYTHONPATH=/tmp/fk-cp1252-sim PYTHONUTF8=0 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python src/make_level2_report.py /tmp/fk-utf8-check/level2_cp.md; cmp reports/level1.md /tmp/fk-utf8-check/level1_cp.md; cmp reports/level2.md /tmp/fk-utf8-check/level2_cp.md` | Both byte-identical under the Linux cp1252 file-write simulation. |
| tests | `PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider` | 60 passed (48 original + 12 new Task 2 tests). |
| tests | `PYTHONPATH=/tmp/fk-cp1252-sim PYTHONUTF8=0 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider` | 60 passed under cp1252 simulation. |
| tests | `PYTHONPATH=/tmp/fk-cp1252-sim PYTHONUTF8=0 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider tests/test_report_claims.py::test_level1_report_equals_generator_output tests/test_report_claims.py::test_level2_report_equals_generator_output` | 2 passed; original report-equality tests unmodified. |
| CO2 sensitivity | `PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONIOENCODING=utf-8 /tmp/fk-audit-venv/bin/python src/task2_co2_floor_sensitivity.py --mode level1 --output outputs/audits/task2/sensitivity/level1_verification.json` | Recomputed CO2_floor_0 and CO2_floor_0.5; floor 0.5 exact, floor 0 differs slightly (max \|change\| 13.8879% vs 13.8788%). |
| CO2 sensitivity | `PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python src/run_task2_sensitivities.py` | Level 2 floors 0.0 and 0.5 refit in parallel; both select M5 with explicit convergence; total 200.73 s. |
| Level 2 reproduction attempt 1 (failed) | `PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python src/reproduce_level2.py --mode all --run-id level2_repro --max-workers 2` | compare_fit passed (163.6 s) but the scheduler marked 14 dependent stages skipped; retained as outputs/audits/task2/reproduction/failed_attempt_1. |
| scheduler regression check | `PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python - <<'PY'  # synthetic 5-stage DAG through reproduce_level2.run_stages` | All 5 synthetic stages passed after adding a progress flag. |
| Level 2 reproduction rerun | `PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python src/reproduce_level2.py --mode all --run-id level2_repro --max-workers 2` | 20/20 stages passed; consistency audit completed; D-24 preferred M5 in isolated root. |
| targeted numerical check | `PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /tmp/fk-audit-venv/bin/python - <<'PY'  # recompute LORO M5 R8 fold from original and reproduced fit thetas` | Original theta gives 1629.1999; reproduced theta gives 731.1355, confirming warm-start sensitivity. |
| evidence generation | `PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python - <<'PY'  # generate D-03, D-24 and Windows UTF-8 JSON/Markdown evidence` | Created d03_verification.*, d24_convergence_check.*, windows_utf8_fix.*. |
| evidence generation | `PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python - <<'PY'  # generate key_metrics.json, reproduction_findings.*` | Created targeted reproduction metrics and findings. |
| final checks | `git status --short; git diff --name-only; git diff --stat; (cd data/raw && sha256sum -c CHECKSUMS.sha256); find outputs/audits/task2 \( -name '*.pyc' -o -name '__pycache__' \) -print; find outputs/audits/task2 -name 'test_*.py' -print; PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider; PYTHONPATH=/tmp/fk-cp1252-sim PYTHONUTF8=0 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider` | Only 6 tracked source files modified; raw checksums OK; no nested test modules or pyc artifacts; final pytest 60 passed in both environments. |

Static inspection additionally used `grep`/`sed`/`nl` on `CLAUDE.md`, `docs/assignment_brief.md`, `docs/requirements_traceability.csv`, `handoff/*.md`, `reports/*.md`, all `src/*.py` and all `tests/*.py`.

## 4. Test results

- Linux sandbox default: **60 passed** (48 original + 12 new Task 2 tests).
- Linux sandbox under cp1252 file-write simulation: **60 passed**.
- Original two report-equality tests under simulation: **2 passed**; they were not weakened.
- Direct generator outputs under simulation are byte-identical to `reports/level1.md` and `reports/level2.md`.
- Final verification: 60 passed in 4.81s (default) and 60 passed in 4.15s (cp1252 simulation).
- Raw CSV checksums: `runs.csv`, `timecourse.csv`, `endpoint_hplc.csv` all OK.
- No nested `test_*.py` modules or `.pyc` artifacts remain under `outputs/audits/task2/`.

## 5. Calculations reproduced and checks

### 5.1 D-03 against the available brief

- Verified the extracted brief’s six uncertainty strings and the implemented row-order mapping across `phase0_inspect.py`, `fit.py` and `carbon_balance.py`.
- The 0.10 g/L CO2 floor is used in fitting/frozen records but not in Phase 0/carbon balance.
- Limits: Original assignment PDF is unavailable. The extracted brief's uncertainty table is unlabelled and read in row order; the exact meaning of 'about ±2%' / 'about ±3%' and row alignment cannot be definitively verified. Do not infer additional requirements.

### 5.2 CO2-floor sensitivity (isolated roots only)

| calculation | result |
|---|---|
| Level 1 CO2_floor_0 verification | recomputed max &#124;change&#124; = 13.8879% (floor 0.5 exact; floor 0 differs slightly) |
| Level 1 CO2_floor_0.5 verification | recomputed max &#124;change&#124; = 4.3730% (floor 0.5 exact; floor 0 differs slightly) |
| Level 2 floor 0.0 | preferred M5; M5 max &#124;change&#124; 2.2299%; convergence condition changes selection = False |
| Level 2 floor 0.5 | preferred M5; M5 max &#124;change&#124; 2.9642%; convergence condition changes selection = False |

Both alternative Level 2 floors select `M5` when the written multistart-convergence clause is made explicit. These are additional sensitivity calculations, not a frozen decision change.

### 5.3 D-24 multistart convergence

- Written rule requires multistart convergence; `compare.py:stage_select` filters only `params_at_bound == 0` and `ode_failures == 0`.
- Current stored results satisfy the written clause: all seven fits `8/8`, solver status 3, zero failures; only M3 is at a bound.
- Recomputed preferred with explicit convergence = `M5`; frozen preferred = `M5`; `r6_used_for_selection = false`. No rule or decision was changed.

### 5.4 Windows UTF-8 fix

- Added explicit `encoding="utf-8"` to 35 text `open()` calls in six existing source files and `newline="\n"` for text writes.
- On Windows the previous default cp1252 could not encode U+2212 (Level 1) or seven character classes in Level 2 (U+0394, U+20B9, U+2192, U+2212, U+2248, U+2264, U+2265).
- Evidence: `windows_utf8_fix.md/json`, `tests/test_results.md/json`, `tests/*.log`.

### 5.5 Level 2 reproduction and consistency audit

- Reproduction script: `src/reproduce_level2.py`; isolated root: `outputs/audits/task2/reproduction/level2_repro/root`.
- 20/20 stages passed in 538.6s after one retained failed scheduler attempt (fixed with a progress flag).
- 68 files compared: 24 byte-identical, 31 CSV/JSON outside rtol=1e-6/atol=1e-8, 44 hash-changed vs copied baseline.
- Frozen hashes in the reproduced root verify: True; reproduced D-24 preferred = `M5`.
- All eight carbon-balance runs reproduce; non-closing runs = ['R4']; yield-gap additivity residual 1.78e-14; residual chi-square max difference 1.36e-12.
- Asset references unresolved = 0; unnamed figures = 0; traceability evidence paths unresolved = 0.
- `level1.md` and `pre_fit_observations.md` are byte-identical in the reproduced root; `level2.md` differs because it reports reproduced numbers.
- Key numerical non-reproducibility: M5 selected a different near-equivalent minimum (P_max lower by 0.48 g/L, chi-square higher by 0.000371). LORO M5 R8 = 1629.2 originally vs 731.1 reproduced; targeted recomputation from the original fit theta gives 1629.1999 and from the reproduced theta gives 731.1355. See `reproduction_findings.md`, `key_metrics.json`, `loro_R8_warmstart_check.json`.

## 6. Unresolved issues

- Original assignment PDF unavailable; D-03 row alignment and exact meaning of “about ±2%” / “about ±3%” cannot be definitively verified.
- Actual Windows pytest run and full Windows traceback are still missing; only Linux cp1252 simulation was executed.
- Full Level 2 numerical reproduction is not bit-exact under Python 3.11.2/numpy 2.4.6/pandas 3.1.0 vs frozen Python 3.12.3/numpy 2.4.4/pandas 3.0.2.
- M5 selected a different near-equivalent minimum in the reproduction (P_max -0.48 g/L, chi-square +0.000371), causing large LORO-R8 (1629.2 -> 731.1) and downstream plant differences.
- Historical execution-claim conflict from the Task 1 audit (real pytest vs fallback runners) remains unresolved; Task 2 did not assume either claim.

## 7. Windows commands the user should run locally

From the project root, in a normal Windows shell (do not rely on `PYTHONUTF8=1` as the fix):

```bat
python -m pip install -r requirements.txt
python -c "import sys,locale; print(sys.version); print(locale.getpreferredencoding(False)); print(sys.stdout.encoding)"
chcp
python -m pytest -q
python -m pytest -q tests/test_report_claims.py::test_level1_report_equals_generator_output tests/test_report_claims.py::test_level2_report_equals_generator_output -vv
python -m pytest -q tests/test_task2_consistency.py -vv
python src/make_level1_report.py "%TEMP%\fk_level1.md"
python src/make_level2_report.py "%TEMP%\fk_level2.md"
fc /B reports\level1.md "%TEMP%\fk_level1.md"
fc /B reports\level2.md "%TEMP%\fk_level2.md"
git status --short
```

Expected: `python -m pytest -q` reports 60 passed; the two report-equality tests pass; `fc /B` reports no differences for both generated reports; `git status --short` shows no modifications to original outputs.
Please paste the full Windows output if any test fails; actual Windows execution was not performed in this Linux sandbox.

## 8. Stop condition

Task 2 is complete and awaits user review. Level 3 was not started, plant economics were not optimized, and no final ZIP was built.
