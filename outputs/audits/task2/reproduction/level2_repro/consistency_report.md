# Task 2 Level 2 reproduction consistency audit

- Original root: `/home/user/fermentation-kinetics`
- Reproduced root: `/home/user/fermentation-kinetics/outputs/audits/task2/reproduction/level2_repro/root`
- Created: 2026-10-27 14:59:28
- Files compared: 68 (56 CSV/JSON, 9 PNG, 3 Markdown).
- Byte-identical files: 24.
- CSV/JSON outside rtol=1e-6/atol=1e-8: 31 (`outputs/tables/candidate_parameters.csv, outputs/tables/experiment_design.csv, outputs/tables/experiment_discrimination.csv, outputs/tables/fixed_parameter_sensitivity.csv, outputs/tables/level1_correlations.csv, outputs/tables/level1_summary_numbers.csv, outputs/tables/model_comparison.csv, outputs/tables/model_r6_diagnostic.csv, outputs/tables/model_residuals.csv, outputs/tables/parameter_correlations_material.csv, outputs/tables/parameter_profiles.csv, outputs/tables/parameter_uncertainty.csv, outputs/tables/plant_Ks_sensitivity.csv, outputs/tables/plant_linearised_sd.csv, outputs/tables/plant_prediction_uncertainty.csv, outputs/tables/r7_inclusion_effect.csv, outputs/tables/structure_spread.csv, outputs/tables/variance_decomposition.csv, outputs/tables/work/fit_M0.json, outputs/tables/work/fit_M1.json, outputs/tables/work/fit_M2.json, outputs/tables/work/fit_M3.json, outputs/tables/work/fit_M4.json, outputs/tables/work/fit_M5.json, outputs/tables/work/fit_M6.json, outputs/tables/work/fixedgrid_M0.json, outputs/tables/work/fixedgrid_M5.json, outputs/tables/work/loro_M0.json, outputs/tables/work/loro_M5.json, outputs/tables/work/profile_M0.json, outputs/tables/work/profile_M5.json`)
- Files whose bytes differ from copied baseline: 44.

## Decision / arithmetic checks

- D-03 source patterns present: True; original PDF remains unavailable.
- CO2 floor: fitting/frozen = 0.1 g/L; Phase 0/carbon balance = no floor.
- D-24: all stored fits converged = True; recomputed preferred = `M5`; frozen preferred = `M5`.
- D-24 in reproduced root: preferred = `M5`.
- Carbon balance: all eight runs = True; non-closing runs = ['R4'].
- Max residual chi-square difference (original / reproduced): 1.36e-12 / 1.36e-12.
- Unresolved asset references: 0; unnamed figures: 0; unresolved traceability evidence paths: 0.

## Limits

- The original assignment PDF is unavailable; D-03 is verified only against docs/assignment_brief.md.
- Actual Windows execution was not performed in this Linux sandbox; a cp1252 file-encoding simulation is used for the UTF-8 fix.
- Figures are checked for valid PNG signature and byte equality only, not pixel-level equality.
- Numeric reproduction uses Python 3.11.2 / numpy 2.4.6 / pandas 3.1.0; the frozen record used Python 3.12.3 / numpy 2.4.4 / pandas 3.0.2, so bit-exact agreement is not expected.
- Level 1 fit and full Level 1 sensitivity were not refit in the reproduction; the frozen Level 1 outputs were copied as inputs.

See also `reproduction_findings.md` / `reproduction_findings.json`, `key_metrics.json` and `loro_R8_warmstart_check.json` for the targeted explanation of the M5/LORO numerical differences.

Full machine-readable detail: `consistency_report.json`.
