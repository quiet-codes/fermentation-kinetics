# Task 2 CO2-floor sensitivity

This is an isolated, additional sensitivity check. The frozen Level 1 parameters and the frozen Level 2 M5/D-24 decision are unchanged.

## Scope

- Existing Level 1 M0 floor cases `CO2_floor_0` and `CO2_floor_0.5` were recomputed from the frozen Level 1 fit.
- All seven Level 2 candidates were refit under floors 0.0 and 0.5 g/L in isolated roots.
- D-24 QAICc selection was recomputed from those fits with the written multistart-convergence condition made explicit.
- No LORO cross-validation, residual table, or full `compare.py --stage select` rerun was performed for the alternative floors; this is not a new frozen selection.

## Level 1 verification

| case | floor (g/L) | original max &#124;change&#124; (%) | recomputed max &#124;change&#124; (%) | exact within 1e-6? |
|---|---:|---:|---:|---|
| CO2_floor_0 | 0.0 | 13.8788 | 13.8879 | no (small numerical difference) |
| CO2_floor_0.5 | 0.5 | 4.3730 | 4.3730 | yes |

## Level 2 additional calculations

| floor (g/L) | preferred (explicit convergence) | best QAICc | c_hat | M5 max &#124;change&#124; (%) | all-model max &#124;change&#124; (%) | runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 0.0 | M5 | M5 | 4.21698 | 2.2299 | 16.3934 | 199.6 |
| 0.5 | M5 | M5 | 3.49552 | 2.9642 | 4.9441 | 180.1 |

Baseline (floor 0.10 g/L, original stored fits): preferred `M5`, best QAICc `M5`, c_hat `3.862912`.

## Interpretation limits

- The original assignment PDF is unavailable; the brief says only 'about ±2%' for CO2 and 'about ±3%' for glycerol/lactic acid. These calculations test sensitivity to the documented 0.10 g/L floor, not the correctness of that interpretation.
- Alternative floors are hypothetical weighting choices. A stable M5 choice under these two alternatives does not prove robustness to every possible weighting or to the missing PDF's exact wording.
- Numeric differences from the stored Level 1 floor-0 case are small but non-zero because this sandbox uses Python 3.11.2 / numpy 2.4.6 / pandas 3.1.0, while the frozen record used Python 3.12.3 / numpy 2.4.4 / pandas 3.0.2.
- Only the fits needed for these conclusions were executed in isolated roots; no original output was overwritten.

Machine-readable evidence: `co2_floor_sensitivity.json`, `level1_verification.json`, `level2_floor_0.json`, `level2_floor_0p5.json`, and per-stage logs in `logs/`.
