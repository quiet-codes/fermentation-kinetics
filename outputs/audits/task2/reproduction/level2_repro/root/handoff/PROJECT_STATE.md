# PROJECT STATE (end of Level 2)

**Completed:** Phase 0; Level 1 (baseline, preserved as candidate M0); Level 2 (model comparison, uncertainty/identifiability, carbon balance, yields, R7 review, plant-relevant uncertainty, proposed experiment). **Not started:** Level 3 optimisation, final report.
**Specification:** `docs/assignment_brief.md` (authoritative), `CLAUDE.md`.

## Files added in Level 2 (Level 1 and Phase 0 files unchanged)
- Code: `src/models.py`, `src/compare.py`, `src/uncertainty.py`, `src/plant_uncertainty.py`, `src/carbon_balance.py`; tests: `tests/test_level2.py`
- Tables (`outputs/tables/`): `model_comparison.csv`, `candidate_parameters.csv`, `model_residuals.csv`, `model_selection_frozen.json`, `model_r6_diagnostic.csv`, `parameter_uncertainty.csv`, `parameter_profiles.csv`, `parameter_correlations_material.csv`, `fixed_parameter_sensitivity.csv`, `r7_inclusion_effect.csv`, `carbon_balance_all_runs.csv`, `ethanol_yields.csv`, `ethanol_yield_pooled.csv`, `yield_gap_decomposition.csv`, `r7_review.csv`, `plant_prediction_uncertainty.csv`, `structure_spread.csv`, `plant_Ks_sensitivity.csv`, `plant_linearised_sd.csv`, `variance_decomposition.csv`, `experiment_design.csv`, `experiment_discrimination.csv`, `work/*.json`
- Figures: `model_comparison_residuals.png`, `parameter_profiles_M5.png`, `parameter_profiles_M0.png`, `carbon_balance_all_runs.png`, `ethanol_yield_gap.png`, `plant_uncertainty.png`
- Report: `reports/level2.md`
- Packaging (added after delivery review): `README.md`, `requirements.txt`, `src/make_level1_report.py`, `src/make_level2_report.py` (rebuild the reports from the tables), `tests/test_report_claims.py`

## Level 2 results (AI sandbox)
- **Selection (D-24, frozen before the R6 diagnostic): M5** = Level 1 baseline + P_max(T) + estimated exponent n. chi-square 3675 (M0) -> 1116 (M5), reduced 12.6 -> 3.9; M3 excluded (n at bound); M6 next at +105 QAICc. Residuals strongly autocorrelated (lag-1 0.54-0.69), QAICc only indicative.
- **Warning:** M5 extrapolates badly when R8 (only 37 C run) is left out (chi2/pt 1629; M2 12, M6 10). M5 does not fit within noise.
- M5 estimates: mu_max=0.1644, X_max=11.11, q_max=1.417, P_max=195, Y_P=0.4806, rho_CO2=0.9783, k34=1.087, k37=0.8049, beta_P=0.04885, n_inh=2.428. P_max and n correlated +0.98 (ridge); P_max extrapolated (about 1.8x observed ethanol). k37 from one run. Profile (scaled) and jackknife intervals in `parameter_uncertainty.csv`; no interval open.
- Fixed parameters: K_s < 0.2 g/L favoured (K_s = 1 costs +36 scaled chi-square units; plant predictions change 1-4%); n = 1 not supported.
- Carbon balance (all 8 runs): recovery 98.2-104.7%, mean 101.0%; only R4 (104.7%) does not close within MC 95%. Unaccounted carbon averages -1.2 points.
- Yield: 0.459 g/g TRS-consumed basis (89.8% of 0.5114); gap = biomass 5.7 + glycerol 4.5 points (+ lactate 4.7 in R7); no unmeasured sink needed.
- R7: lactate 9.0 g/L, pH 3.84; carbon closes only with lactate; including R7 raises M5 reduced chi-square 3.9 -> 12.3 with parameter shifts <= 13%.
- Plant: 37 C/260 g/L -> ethanol 78 g/L and TRS 87 g/L at 48 h, TRS 41 g/L at 96 h, no end of batch within 120 h in M5; structures disagree. 33 C/220 g/L daily margin about Rs 112k (parameter 95% 108-117k; structure spread about +/-5%). 34 C/260: batch end 87 h [81-106], margin Rs 81k [67-86k], ethanol at end 118 g/L (above data and above the 14% v/v steam curve).
- Proposed experiment: 96 h batch at 34 C/260 g/L (alternative 36 C/260).

## Checks
- `python tests/test_report_claims.py`: 11 passed, 0 failed (reports equal their generators; hand-typed numbers checked against raw CSVs and tables). Phase 0: the six tests of `tests/test_phase0.py` passed through a minimal stand-in for pytest's `fixture`/`approx` (74 PASS / 58 INFO / 5 FLAG).
- `python tests/test_level2.py`: 15 passed, 0 failed, 0 skipped; `python tests/test_model.py`: 16 passed, 0 failed, 0 skipped (fallback runner; **pytest not installed in the sandbox, not run**). Phase 0 pytest file not run this session.
- **Nothing has been run on the user's machine.** The user's local Phase 0 and Level 1 results were never supplied.

## Unresolved limitations
- Preferred structure not validated at 37 C; no candidate fits within noise; R3 biomass OD600-based and unvalidated.
- Only one 37 C run and none at 33/36 C (linear interpolation of multipliers); ethanol > 108 g/L and times > 48 h are extrapolations.
- Run-to-run variability unmeasured (only replicate pair is R5/R7, R7 unusual).
- K_s = 1 g/L retained as documented primary though disfavoured (D-31, user decision for Level 3).
- Unmeasured carbon (non-sugar molasses organics, by-products, dissolved CO2) not quantified; CO2 sd floor 0.10 g/L and uncertainty-table mapping (D-03) unconfirmed.
- R6 is no longer blind; any Level 3 refit using R6 must be labelled.
- `requirements.txt` and `README.md` not available to me: add `scipy` (tested 1.17.1).

## Packaging notes
- Raw CSVs, Phase 0 files and Level 1 source/reports are byte-identical to the originals supplied (checked with `cmp`). `data/raw/CHECKSUMS.sha256` was regenerated in the sandbox because the original was not uploaded.
- No analysis was re-run during packaging; the Level 2 frozen selection (M5, rule D-24) is unchanged. Level 3 has not been started.
