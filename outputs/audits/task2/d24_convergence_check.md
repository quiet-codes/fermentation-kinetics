# D-24 multistart-convergence check

Created: 2026-10-27 14:55:50. **Frozen decision unchanged.**

## Discrepancy

- Written rule (`handoff/DECISIONS.md line 28 (D-24)`): “Preferred = lowest QAICc among candidates whose fitted parameters are not at a bound and whose multistart converged to one minimum; if a candidate with fewer parameters is within 4 QAICc units of the best, take the simpler.”
- Code (`src/compare.py:195 (stage_select)`): `ok = cmp[(cmp.params_at_bound == 0) & (cmp.ode_failures == 0)]`
- stage_select filters only params_at_bound and ode_failures; it records starts_near_best but does not use n_near_best/status in the eligibility filter.

## Current stored results

- All seven stored Level 2 fits converged from every start: True (`n_near_best/n_starts = 8/8`, solver status 3).
- M3 alone has a parameter at a bound (1) and remains ineligible under both filters.
- Eligible with explicit convergence: ['M0', 'M1', 'M2', 'M4', 'M5', 'M6'].
- Recomputed preferred / best QAICc: `M5` / `M5`.
- Frozen preferred / rule / c_hat / R6-used: `M5` / `D-24` / 3.862912 / False.

Conclusion: the current results satisfy the written multistart-convergence condition, and adding that condition explicitly does not change M5. The code still does not enforce it explicitly; this report does not silently alter the pre-registered rule or the frozen decision.

## Additional floor sensitivity

| floor (g/L) | preferred with explicit convergence | convergence condition changes selection? |
|---:|---|---|
| 0.0 | M5 | False |
| 0.5 | M5 | False |

Machine-readable evidence: `d24_convergence_check.json`, `sensitivity/co2_floor_sensitivity.json`.
