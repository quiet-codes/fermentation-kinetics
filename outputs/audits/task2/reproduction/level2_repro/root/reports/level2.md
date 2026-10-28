# Level 2 report: model comparison, parameter uncertainty, carbon balance, ethanol yield and plant-relevant uncertainty

**Scope:** Level 2 only. No plant optimisation (Level 3): the brief's margin formula is evaluated at four fixed scenarios purely to propagate uncertainty, and nothing is recommended.
**Preserved:** raw CSVs, Phase 0 files and all Level 1 files (`kinetics.py`, `fit.py`, `level1_*`, `heldout_*`, `reports/level1.md`) are unchanged; the Level 1 baseline is candidate M0 and is reproduced exactly (max difference 0.0 in simulated states).
**Status of R6:** R6 was inspected in Level 1 and its Level 1 prediction is on file, so it is **not blind**. It was never used to develop, choose or tune a model. The selection was frozen (SHA-256 in `model_selection_frozen.json`) before the R6 diagnostic for the candidates was computed (`model_r6_diagnostic.csv`). R6 appears in two places only: (a) that labelled out-of-fit diagnostic and (b) one labelled secondary refit of the chosen model in `structure_spread.csv`.
**What was actually executed (AI sandbox, Python 3.12.3, numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, matplotlib 3.10.8, one CPU core):** `compare.py` (fit, loro, select, r6diag), `uncertainty.py` (r7, fixedgrid, profile, assemble), `plant_uncertainty.py` (predict, design, ksens, discriminate, plot), `carbon_balance.py`; `tests/test_level2.py` 15 passed / 0 failed / 0 skipped, `tests/test_model.py` 16 passed / 0 failed / 0 skipped and `tests/test_report_claims.py` 11 passed / 0 failed (it checks the numbers typed into this report and into the Level 1 report against the raw CSVs and tables, and that each report equals the output of its generator), all through the fallback runner because **pytest is not installed in the sandbox**; the six Phase 0 tests (`tests/test_phase0.py`) also passed (74 PASS / 58 INFO / 5 FLAG) when run through a minimal stand-in for pytest's `fixture` and `approx`. **Not executed:** pytest itself, anything on your machine. Your local Phase 0 and Level 1 results were never supplied.

---

## 0. Findings in brief
1. **Structure matters more than parameter precision.** Adding a temperature-dependent ethanol limit P_max(T) cuts the training chi-square from 3675 (Level 1 baseline) to 1683 (M2, one extra parameter); also estimating the inhibition exponent (M5) gives 1116 (reduced chi-square 12.6 → 3.9). By the rule fixed in advance (D-24) **M5 is preferred**. It still does not fit within the stated noise, and it **fails badly when the only 37 C run is left out** (leave-one-run-out chi-square per point 731), so its 37 C behaviour rests on R8 alone.
2. **The linear ethanol-inhibition form (n = 1) used in Level 1 is not supported**: fixing n = 3 instead lowers the baseline chi-square by 875; M5 estimates n = 2.42 (profile 95% [2.00, 3.12]). **P_max and n are not separable** (linearised correlation +0.98, a ridge); only their combination is determined, and P_max = 194 g/L lies well above any ethanol observed (maximum 107.8 g/L).
3. **K_s = 1 g/L was not harmless:** with the rest re-optimised, chi-square falls monotonically as K_s decreases to 0.05 g/L (scaled change +36 at K_s = 1, +221 at 5 g/L). The data favour a very sharp sugar cutoff (K_s = 0.2 g/L is already above the 95% threshold relative to 0.05 g/L; the lower end is unbounded and sits below the 0.4 g/L TRS measurement floor); the effect on the plant-relevant predictions is small (1-4%) for K_s up to 5 g/L.
4. **Carbon closes for all eight runs within measurement uncertainty except R4** (recovery 104.7%, Monte-Carlo 95% [101.5, 108.3]%). Mean recovery 101.0% (100.5% without R4).
5. **Overall ethanol yield 0.459 g ethanol per g TRS consumed (glucose-equivalent basis; run-bootstrap 95% [0.450, 0.468]) = 89.8% of 0.511.** The 10.2% gap is accounted for by biomass (5.7 points of consumed sugar carbon) and glycerol (4.5), plus lactic acid in R7 (4.7); the residual "unaccounted" term averages -1.2 points, i.e. no unmeasured carbon sink is needed (if anything the output slightly exceeds the measured input).
6. **R7 is an unusual run** (lactic acid 9.0 g/L, pH 3.84 against 4.40 in its repeat R5). Counting lactic acid, its carbon closes (101.0%); leaving it out gives 97.0%. Including R7 raises the reduced chi-square of M5 from 3.9 to 12.3, while no parameter moves by more than 13%.
7. **For the plant, the unresolved quantity is the sugar tail at high ethanol and temperature.** At 37 C / 260 g/L the preferred model predicts 78 g/L ethanol and 87 g/L TRS at 48 h and 41 g/L TRS at 96 h; the 5 g/L end-of-batch condition is not reached within 120 h in M5 (and in most other structures), but one candidate (M3, disqualified) reaches it at 94 h. That is a disagreement between structures, not a parameter interval.
8. **Most useful single additional experiment:** one 96-hour batch at 34 C and 260 g/L TRS (R6's conditions run to 96 h), with dry-weight biomass and endpoint HPLC (section 6.4).

## 1. Task 1: model structures

### 1.1 Candidates and why (training runs only, D-23)
Developed from R1, R2, R3 (no biomass), R4, R5 and R8 only. The training evidence behind the temperature-dependent ethanol limit: early ethanol rates are equal at 30 and 34 C (2.84 vs 2.88 g/L/h at 160 g/L; 2.53 vs 2.58 at 220 g/L) but, at similar ethanol and sugar, R5 (34 C) produces ethanol 22% more slowly than R3 (30 C) over 24-36 h (1.71 vs 2.18 g/L/h), and R8 (37 C) slows at only 66-80 g/L ethanol. M1 tests whether k34 can be dropped (k34 was 0.97 in Level 1). M3 and M5 ask whether the inhibition exponent should be estimated (Level 1 noted a fixed n = 1 was an imposed simplification). M4 and M6 apply the same ethanol factor to growth with no extra parameter. **Nothing was added to repair the Level 1 biomass plateau specifically**, and terms for viability loss, nutrient limitation, substrate inhibition and maintenance were not tested because the data contain no direct observation of them.

| Model | Description | k | chi-square | reduced | QAICc | Δ QAICc | rms z (X / S / P / C) | mean lag-1 residual autocorr. | LORO mean chi2/pt, excl. R8 | LORO chi2/pt, R8 fold |
|---|---|---|---|---|---|---|---|---|---|---|
| M0 | Level 1 baseline (linear inhibition, one P_max, k34 and k37 free) | 8 | 3675 | 12.63 | 967.9 | 658.2 | 2.50 / 4.67 / 3.39 / 2.94 | 0.68 | 22.7 | 28 |
| M1 | M0 with k34 = 1 | 7 | 3803 | 13.03 | 999.0 | 689.2 | 2.59 / 4.93 / 3.27 / 2.86 | 0.69 | 18.0 | 87 |
| M2 | M0 + P_max(T) = P30 exp(-beta (T-30)) | 9 | 1683 | 5.80 | 454.4 | 144.6 | 2.10 / 2.86 / 2.36 / 2.04 | 0.65 | 13.4 | 12 |
| M3 | M0 + estimated exponent n (n at bound 4.0: excluded by D-24) | 9 | 2746 | 9.47 | 729.6 | 419.8 | 1.40 / 4.39 / 2.91 / 2.42 | 0.59 | 19.7 | 19 |
| M4 | M0 with the ethanol factor also on growth | 8 | 3518 | 12.09 | 927.2 | 617.5 | 2.19 / 4.69 / 3.32 / 2.85 | 0.67 | 22.3 | 26 |
| M5 | P_max(T) + estimated n | 10 | 1116 | 3.86 | 309.8 | 0.0 | 1.42 / 2.59 / 1.92 / 1.50 | 0.54 | 9.4 | 731 |
| M6 | P_max(T) + ethanol factor on growth | 9 | 1530 | 5.28 | 414.8 | 105.0 | 1.82 / 2.83 / 2.26 / 1.93 | 0.63 | 12.5 | 10 |

Training data: 299 residuals (R3 biomass excluded). QAICc = chi-square / c_hat + 2k + 2k(k+1)/(N-k-1) with c_hat = 3.86 (reduced chi-square of the most complex candidate, M5; D-24). All seven candidates converged to a single minimum from all 8 starts and had 0 solver failures.

Leave-one-run-out chi-square per point (training runs only; the held-out run is predicted from a refit on the other five):

| Model | R1 | R2 | R3 | R4 | R5 | R8 |
|---|---|---|---|---|---|---|
| M0 | 7.0 | 24.4 | 24.6 | 26.3 | 31.2 | 27.5 |
| M1 | 8.7 | 28.0 | 21.3 | 8.6 | 23.4 | 86.7 |
| M2 | 20.7 | 4.4 | 11.4 | 7.7 | 22.8 | 12.3 |
| M3 | 5.5 | 21.3 | 20.2 | 23.0 | 28.7 | 19.0 |
| M4 | 6.3 | 23.3 | 24.9 | 26.3 | 30.8 | 26.5 |
| M5 | 17.5 | 3.4 | 12.0 | 7.0 | 7.3 | 731.1 |
| M6 | 20.2 | 3.7 | 11.3 | 7.6 | 19.7 | 10.0 |

### 1.2 Selection (rule fixed before computing)
Rule D-24: lowest QAICc among candidates with no parameter at a bound; prefer a simpler candidate within 4 QAICc units. **Result: M5.** M3 has n at its bound of 4.0 and is excluded; the next best, M6, is 105 QAICc units behind, so no simpler model qualified.

### 1.3 What supports it, and how far
- **Fit and residuals:** M5 removes most of the Level 1 structural misfit (chi-square 3675 → 1116); its biomass plateau is 11.1 g/L, matching the data (Level 1: 9.3), and its mean z is between −0.6 and −0.1 in all four variables. It still does not fit within the stated noise (reduced chi-square 3.9; rms z 1.4-2.6).
- **Residuals are strongly autocorrelated** (mean lag-1 coefficient 0.54-0.69 for all candidates), so the chi-square and QAICc assumptions of independent errors with known sds are not met. If the effective sample size were a third of 299, the QAICc gaps would shrink about threefold (M5 vs M2: 144 → about 48), still well above 4. So in-sample, M5 is distinguishable from M2 and M6, and all three from M0/M1/M4. I treat the size of the gaps as indicative only.
- **Out-of-sample within the training runs** the picture is mixed: M5 has the lowest chi2/pt of all seven candidates in 3 of the 5 folds that leave R8 in (R2, R4, R5; R1 is best for M3 and R3 for M6) and the lowest mean (mean 9.4 vs 13.4 for M2 and 12.5 for M6), **but with R8 removed it extrapolates to 37 C catastrophically** (chi2/pt 731; M2 12, M6 10). With three temperature levels and one run at 37 C, the exponent n and the temperature slope of P_max cannot be validated at 37 C. M2 and M6 are the safer alternatives; M2 and M6 cannot be told apart by any plausible experiment (their predictions differ by at most about 56 chi-square units over a 96 h run, section 6.4).
- **Out-of-fit diagnostic on R6 (not used for selection, D-22):** all candidates fail to predict R6 within the noise.

| Model | R6 rms z (X / S / P / C) | TRS at 48 h, predicted (measured 48.7) | Ethanol at 48 h, predicted (measured 100.1) |
|---|---|---|---|
| M0 | 2.06 / 5.61 / 3.06 / 2.69 | 38.7 | 101.8 |
| M1 | 2.24 / 7.00 / 3.74 / 3.37 | 36.1 | 103.1 |
| M2 | 1.63 / 4.06 / 3.90 / 3.27 | 49.5 | 96.7 |
| M3 | 1.22 / 6.75 / 2.83 / 2.67 | 33.7 | 103.6 |
| M4 | 1.61 / 5.61 / 3.00 / 2.63 | 38.9 | 101.5 |
| M5 | 1.63 / 3.82 / 3.78 / 3.47 | 45.3 | 98.2 |
| M6 | 1.38 / 4.01 / 3.91 / 3.31 | 49.4 | 96.5 |

  Compared with M0 (TRS error −10.0 g/L), M5 reduces the 48 h TRS error to -3.4 g/L, but its ethanol and CO2 rms z (3.78, 3.47) are not better than M0's (3.06, 2.69). Nothing here was used to choose; the labelled diagnostic should not be read as confirmation.
- **Are the candidates distinguishable with eight runs?** M0/M1/M4 versus M2/M5/M6, yes (large gaps that survive an autocorrelation discount). M5 versus M2/M6, only at the cost of two extra parameters whose individual values are a ridge and whose 37 C behaviour cannot be validated. M2 versus M6, no.

## 2. Task 2: parameter uncertainty and identifiability (preferred model M5; baseline M0 for comparison)

**Method (D-25).** Point estimates: weighted least squares, multistart, training runs only. Intervals: profile likelihood re-optimising all other parameters, with the 95% threshold at chi-square_min + c_hat × 3.84 (c_hat = 3.86 for M5, 12.63 for M0) because the fits are far from chi-square ≈ dof. The unscaled interval (valid only if the stated sds were exact) is shown for reference. Jackknife = refits with each training run left out in turn (6 refits; run-to-run stability; k37 cannot be estimated when R8 is dropped). Profile intervals that do not close inside the parameter bounds would be reported as open; none was open here.

**Are the Level 1 local (covariance) estimates trustworthy?** Partly. Within M5 the linearised 95% intervals and the profile intervals are close (for example n: linearised [1.90, 2.94], profile [2.00, 3.12]; P_max: [164, 225] vs [170, 235]), so the local approximation is acceptable *given the structure*. They are not trustworthy as statements about the real system, because (i) they are conditional on a structure that still misfits and whose alternatives give non-overlapping intervals (M0 k34 [0.955, 0.989] vs M5 [1.072, 1.102]), (ii) the stated sds understate scatter and the errors are autocorrelated, and (iii) the jackknife range, which reflects run-to-run variation, is wider than the profile interval for several parameters (below). A defensible overall uncertainty is at least the wider of the two.

### 2.1 Fitted parameters of M5 (units in column 2)

| Parameter | Unit | Estimate | Profile 95% (scaled by c_hat) | Profile 95% (sds exact) | Linearised 95% | Jackknife range (leave-one-run-out) | Identifiability | Correlated (|r| ≥ 0.7, linearised) |
|---|---|---|---|---|---|---|---|---|
| mu_max | 1/h | 0.1643 | [0.1552, 0.1741] | [0.1596, 0.1693] | [0.1548, 0.1737] | 0.151 – 0.1686 | partly determined (run-to-run spread exceeds the within-fit interval) | none |r|>=0.7 |
| X_max | g/L | 11.11 | [10.72, 11.5] | [10.91, 11.31] | [10.72, 11.5] | 11.02 – 11.34 | determined (within this model structure) | none |r|>=0.7 |
| q_max | g/g/h | 1.417 | [1.372, 1.463] | [1.394, 1.44] | [1.372, 1.463] | 1.373 – 1.443 | partly determined (run-to-run spread exceeds the within-fit interval) | none |r|>=0.7 |
| P_max | g/L | 194.5 | [170.5, 235.4] | [180.9, 212.6] | [164.4, 224.5] | 184 – 213.4 | determined only jointly (ridge, |r| >= 0.9 with n_inh) | n_inh (+0.98) |
| Y_P | g/g | 0.4806 | [0.476, 0.4853] | [0.4783, 0.483] | [0.476, 0.4853] | 0.4798 – 0.4833 | determined (within this model structure) | none |r|>=0.7 |
| rho_CO2 | g/g | 0.9783 | [0.9652, 0.9915] | [0.9716, 0.985] | [0.9651, 0.9914] | 0.9731 – 0.9833 | determined (within this model structure) | none |r|>=0.7 |
| k34 | - | 1.086 | [1.072, 1.102] | [1.079, 1.094] | [1.071, 1.102] | 1.055 – 1.131 | partly determined (run-to-run spread exceeds the within-fit interval) | beta_P (+0.70) |
| k37 | - | 0.8049 | [0.7867, 0.8238] | [0.7956, 0.8144] | [0.7866, 0.8231] | 0.7889 – 0.8494 | determined by ONE run (R8): precision is conditional, no replication | beta_P (+0.74) |
| beta_P | 1/C | 0.04881 | [0.04421, 0.05365] | [0.04644, 0.05124] | [0.04412, 0.05349] | 0.04381 – 0.05679 | partly determined (run-to-run spread exceeds the within-fit interval) | k34 (+0.70); k37 (+0.74) |
| n_inh | - | 2.421 | [1.999, 3.121] | [2.184, 2.731] | [1.9, 2.941] | 2.232 – 2.726 | determined only jointly (ridge, |r| >= 0.9 with P_max) | P_max (+0.98) |

### 2.2 Level 1 baseline M0 (for comparison)

| Parameter | Unit | Estimate | Profile 95% (scaled by c_hat) | Profile 95% (sds exact) | Linearised 95% | Jackknife range | Identifiability | Correlated |
|---|---|---|---|---|---|---|---|---|
| mu_max | 1/h | 0.2175 | [0.1864, 0.253] | [0.2084, 0.227] | [0.1927, 0.2422] | 0.1985 – 0.2378 | determined (within this model structure) | q_max (-0.73) |
| X_max | g/L | 9.337 | [8.812, 9.908] | [9.187, 9.492] | [8.866, 9.809] | 8.882 – 9.892 | partly determined (run-to-run spread exceeds the within-fit interval) | none |r|>=0.7 |
| q_max | g/g/h | 1.297 | [1.22, 1.381] | [1.275, 1.32] | [1.23, 1.364] | 1.246 – 1.35 | determined (within this model structure) | mu_max (-0.73) |
| P_max | g/L | 118.5 | [113.5, 125.2] | [117.1, 120.2] | [114.1, 123] | 114 – 127.9 | partly determined (run-to-run spread exceeds the within-fit interval) | none |r|>=0.7 |
| Y_P | g/g | 0.478 | [0.4697, 0.4864] | [0.4756, 0.4803] | [0.4697, 0.4863] | 0.4772 – 0.4794 | determined (within this model structure) | none |r|>=0.7 |
| rho_CO2 | g/g | 0.9871 | [0.9634, 1.011] | [0.9804, 0.9938] | [0.9632, 1.011] | 0.9819 – 0.9922 | determined (within this model structure) | none |r|>=0.7 |
| k34 | - | 0.9714 | [0.9547, 0.9887] | [0.9667, 0.9763] | [0.955, 0.9878] | 0.9308 – 1.022 | partly determined (run-to-run spread exceeds the within-fit interval) | none |r|>=0.7 |
| k37 | - | 0.6687 | [0.6526, 0.6852] | [0.6642, 0.6733] | [0.6527, 0.6847] | 0.6595 – 0.6773 | determined by ONE run (R8): precision is conditional, no replication | none |r|>=0.7 |

Identifiability labels are rule-based (`uncertainty.py: classify`): "determined" = closed interval, relative width ≤ 40%, run-to-run (jackknife) spread no larger than the interval; "partly determined" = closed but the leave-one-run-out spread exceeds the within-fit interval; "determined only jointly" = |r| ≥ 0.9 with another parameter; k37 is flagged separately because it rests on one run.

### 2.3 Reading the table honestly
- **Best determined (within this structure):** X_max, Y_P and rho_CO2 (relative profile half-widths ≈ 4%, 1.0% and 1.3%).
- **rho_CO2** is 0.978 [0.965, 0.992]; the stoichiometric 0.955 is **outside** the interval, about 2.4% higher. The carbon balance gives a compatible amount of CO2 beyond the 1:1 pairing with ethanol (+0.5 points of consumed carbon on average, with intervals that include zero for six runs). Extra CO2 from biomass synthesis is a plausible explanation but is not tested.
- **P_max and n (ethanol-inhibition shape):** correlation +0.98; the profile intervals are closed but P_max and n trade off along a ridge. The data determine the *combination* of inhibition strength over the observed ethanol range (up to 108 g/L). P_max is an extrapolated scale (≈ 1.8 × the highest observed ethanol) and should not be quoted as a physical ethanol tolerance.
- **Temperature parameters (k34, k37, beta_P):** within-fit intervals are narrow, but the jackknife spreads (k34 1.055–1.131; beta_P 0.0438–0.0568) are several times wider than the profile half-widths. k37 comes from one run, and beta_P correlates with both multipliers (+0.70, +0.75). A temperature of 33 or 36 C is reached only by linear interpolation of the multipliers (an assumption).
- **mu_max and q_max** are "partly determined": within-fit intervals ±6% and ±3%, but the jackknife range is wider (mu_max 0.151–0.169).
- **What I do about the weakly determined ones:** report jackknife ranges beside the profile intervals; carry the structural alternatives (M2, M6, M0) into the plant-relevant predictions rather than a single parameter set; flag everything that depends on P_max, n, beta_P and k37 as extrapolation (section 6); and recommend the experiment in section 6.4.

### 2.4 Fixed parameters K_s and the exponent n
Re-optimising the other parameters at each fixed value (D-25):

| Model | Fixed value | chi-square | Δ chi-square / c_hat vs best grid point | P_max | k37 |
|---|---|---|---|---|---|
| M5 | K_s = 0.05 g/L | 977 | +0.0 | 193 | 0.807 |
| M5 | K_s = 0.2 g/L | 997 | +5.3 | 193 | 0.806 |
| M5 | K_s = 1 g/L | 1116 | +36.1 | 194 | 0.805 |
| M5 | K_s = 5 g/L | 1832 | +221.2 | 194 | 0.796 |
| M5 | K_s = 20 g/L | 5194 | +1091.8 | 153 | 0.767 |
| M0 | n = 0.5 (fixed) | 4864 | +163.3 | 108 | 0.670 |
| M0 | n = 1 (fixed) | 3675 | +69.3 | 119 | 0.669 |
| M0 | n = 1.5 (fixed) | 3174 | +29.6 | 136 | 0.668 |
| M0 | n = 2 (fixed) | 2960 | +12.6 | 160 | 0.669 |
| M0 | n = 3 (fixed) | 2801 | +0.0 | 212 | 0.670 |

- **K_s:** the best grid point is the smallest (0.05 g/L). Relative to it, K_s = 0.2 is already +5.3 scaled units (above the 3.84 threshold), K_s = 1 is +36 and K_s = 5 is +221. So the data put the upper limit of K_s between 0.05 and 0.2 g/L, with the lower end unbounded; sampling at 24 and 30 h cannot resolve K_s below the 0.4 g/L TRS floor. The a-priori K_s = 1 g/L therefore costs fit but changes the plant-relevant predictions little (section 6.3). K_s is **not estimated**; I keep 1 g/L as the documented primary value (D-16) and report this sensitivity.
- **n (baseline M0, grid):** chi-square falls monotonically as n rises from 0.5 to 3, so n = 1 is not supported; in M5 n is estimated at 2.42 (profile [2.00, 3.12]), but only jointly with P_max.

## 3. Task 3: carbon balance for all eight runs

Inputs: measured t = 0 TRS (as glucose equivalent; 6 C per 180.16 g) and the inoculum biomass from `runs.csv` (24.6 g per C-mol). Outputs: 48 h TRS, biomass, ethanol (2 C per 46.07 g), cumulative CO2 (44.01 g per C-mol), glycerol (3 C per 92.09 g) and lactic acid (3 C per 90.08 g). **n.d. lactic acid is uniform on [0, 0.2) g/L (central 0.1), not zero.** 95% intervals are Monte-Carlo (20,000 draws) from the brief's measurement sds (including the t = 0 TRS and the inoculum). All eight runs are included regardless of the fitting decisions.

| Run | Carbon in (C-mol/L) | Carbon out (C-mol/L) | Unaccounted (C-mol/L) | Recovery % of input | MC 95% | Recovery % of consumed-sugar carbon (Phase 0 basis) | Closes within 95%? | Role in fits |
|---|---|---|---|---|---|---|---|---|
| R1 | 5.533 | 5.500 | +0.034 (+0.6%) | 99.4 | [96.2, 102.8] | 99.4 | yes | yes |
| R2 | 7.508 | 7.377 | +0.132 (+1.8%) | 98.2 | [95.2, 101.4] | 98.2 | yes | yes |
| R3 | 8.744 | 8.892 | -0.148 (-1.7%) | 101.7 | [98.8, 104.8] | 101.9 | yes | yes |
| R4 | 5.294 | 5.545 | -0.251 (-4.7%) | 104.7 | [101.5, 108.3] | 104.8 | NO | yes |
| R5 | 7.362 | 7.372 | -0.011 (-0.1%) | 100.1 | [97.0, 103.3] | 100.2 | yes | yes |
| R6 | 8.827 | 8.863 | -0.036 (-0.4%) | 100.4 | [97.5, 103.4] | 100.5 | yes | held out |
| R7 | 7.458 | 7.533 | -0.074 (-1.0%) | 101.0 | [98.0, 104.0] | 101.2 | yes | excluded |
| R8 | 7.355 | 7.551 | -0.196 (-2.7%) | 102.7 | [99.7, 105.7] | 103.5 | yes | yes |

Components (C-mol/L):

| Run | In: sugar | In: inoculum | Out: residual sugar | Biomass | Ethanol | CO2 | Glycerol | Lactic acid |
|---|---|---|---|---|---|---|---|---|
| R1 | 5.432 | 0.102 | 0.010 | 0.454 | 3.117 | 1.668 | 0.247 | 0.0033 |
| R2 | 7.407 | 0.102 | 0.000 | 0.469 | 4.363 | 2.213 | 0.329 | 0.0033 |
| R3 | 8.642 | 0.102 | 0.952 | 0.501 | 4.680 | 2.397 | 0.358 | 0.0033 |
| R4 | 5.192 | 0.102 | 0.010 | 0.463 | 3.239 | 1.591 | 0.239 | 0.0033 |
| R5 | 7.260 | 0.102 | 0.220 | 0.459 | 4.194 | 2.170 | 0.327 | 0.0033 |
| R6 | 8.726 | 0.102 | 1.622 | 0.442 | 4.346 | 2.138 | 0.312 | 0.0033 |
| R7 | 7.357 | 0.102 | 0.956 | 0.471 | 3.655 | 1.865 | 0.285 | 0.2997 |
| R8 | 7.254 | 0.102 | 1.645 | 0.457 | 3.460 | 1.727 | 0.258 | 0.0033 |

Sensitivity of the recovery % (central values):

| Run | Primary | Nominal t = 0 TRS | Measured t = 0 biomass | n.d. lactic = 0 / = 0.2 g/L |
|---|---|---|---|---|
| R1 | 99.4 | 101.3 | 99.1 | 99.3 / 99.4 |
| R2 | 98.2 | 99.3 | 98.3 | 98.2 / 98.3 |
| R3 | 101.7 | 101.5 | 101.6 | 101.7 / 101.7 |
| R4 | 104.7 | 102.1 | 104.8 | 104.7 / 104.8 |
| R5 | 100.1 | 99.2 | 100.2 | 100.1 / 100.2 |
| R6 | 100.4 | 101.2 | 100.3 | 100.4 / 100.4 |
| R7 | 101.0 | 101.4 | 101.0 | 101.0 / 101.0 |
| R8 | 102.7 | 101.7 | 102.8 | 102.6 / 102.7 |

**Reading.**
- All runs recover 98.2-104.7% of the carbon; the Monte-Carlo sd is 1.5-1.8 points, so seven of eight close within 95% uncertainty. **R4 does not** (104.7%, interval [101.5, 108.3]); R4's measured t = 0 TRS (155.9 g/L) is 4.1 g/L below nominal (z = −2.09 in Phase 0), and with the nominal 160 g/L the recovery is 102.1%. R4's catabolic yield is also above the stoichiometric 0.511 (section 4), which points to a measurement bias in this run, not a real source of carbon. It was not excluded (nothing independent says it is unfit for the yeast model).
- **Mean recovery 101.0%** (100.5% without R4); total unaccounted carbon over the eight runs is -0.55 C-mol/L, i.e. output slightly *exceeds* input. A missing carbon sink therefore is not indicated.
- On the Phase 0 consumed-sugar basis (column 7) the recoveries agree with the Phase 0 table within 0.4 points for every run (differences arise from the nominal vs measured inoculum); the total-input basis in column 5 puts the same carbon over a larger denominator, so it sits closer to 100%.
- **Limitations that move the balance but were not corrected:** (i) the TRS assay is a reducing-sugar measurement, so non-sugar organic carbon in molasses (organic acids, amino acids, betaine) is not in the input; it would push recovery above 100%, which is the sign of the average residual; (ii) unmeasured by-products (acetate, succinate, 2,3-butanediol, higher alcohols) and dissolved CO2/bicarbonate are not in the output and would push recovery below 100%; (iii) biomass is converted with the brief's fixed 24.6 g/C-mol, and R3's biomass is OD600-based with no calibration uncertainty; (iv) the inoculum is the recorded charge, not a measurement. The sizes of (i) and (ii) are unknown from these data: they probably partly cancel, so a recovery near 100% does not prove the absence of either.

## 4. Task 4: ethanol yield and the questionable-run analysis

Yield = ethanol at 48 h / (TRS(0) − TRS(48 h)), with the measured t = 0 TRS; theoretical = 2 × 46.07 / 180.16 = **0.5114 g/g**. The last column removes the sugar used to build the biomass increase (1.2206 g/g, carbon equivalent), i.e. the catabolic yield (Level 1's Y_P is defined this way).

| Run | TRS consumed (g/L) | Ethanol (g/L) | Yield (g/g) | MC 95% (measurement only) | % of theory | Yield with nominal t = 0 TRS | Catabolic yield |
|---|---|---|---|---|---|---|---|
| R1 | 162.8 | 71.8 | 0.4410 | [0.424, 0.459] | 86.2 | 0.4496 | 0.472 |
| R2 | 222.4 | 100.5 | 0.4519 | [0.436, 0.469] | 88.4 | 0.4568 | 0.475 |
| R3 | 230.9 | 107.8 | 0.4669 | [0.449, 0.485] | 91.3 | 0.4659 | 0.492 |
| R4 | 155.6 | 74.6 | 0.4794 | [0.462, 0.498] | 93.7 | 0.4671 | 0.515 |
| R5 | 211.4 | 96.6 | 0.4570 | [0.440, 0.475] | 89.3 | 0.4527 | 0.481 |
| R6 | 213.3 | 100.1 | 0.4693 | [0.451, 0.489] | 91.8 | 0.4737 | 0.493 |
| R7 | 192.2 | 84.2 | 0.4381 | [0.420, 0.456] | 85.7 | 0.4401 | 0.465 |
| R8 | 168.4 | 79.7 | 0.4733 | [0.453, 0.494] | 92.5 | 0.4672 | 0.505 |

| Pooled set | Sum ethanol / sum TRS consumed | % of 0.5114 | Run-bootstrap 95% (10,000) |
|---|---|---|---|
| all 8 runs | 0.4594 | 89.8 | [0.450, 0.468] |
| 7 runs (R7 excluded) | 0.4624 | 90.4 | [0.454, 0.471] |
| 6 Level-1 training runs | 0.4611 | 90.2 | [0.452, 0.471] |
| R7 alone | 0.4381 | 85.7 | n/a (one run) |
| R5 alone | 0.4570 | 89.3 | n/a (one run) |

**Overall yield: 0.4594 g/g on the consumed-TRS (glucose-equivalent, after inversion) basis, 89.8% of theoretical; 0.4624 g/g (90.4%) without R7.** On the basis of sugar as charged (sucrose plus reducing sugars by mass before inversion, which exceeds the TRS figure by the inversion factor 1.0368 seen in all runs), the same ethanol is about 0.476 g per g of sugar charged and consumed; the basis must always be stated.

**Where the gap goes** (exact decomposition, as points of the consumed sugar carbon not routed to ethanol plus its paired CO2; each row sums to the total gap, and the bracketed intervals are Monte-Carlo):

| Run | Total gap | Biomass | Glycerol | Lactic acid | CO2 beyond 1:1 with ethanol | Unaccounted |
|---|---|---|---|---|---|---|
| R1 | 13.8 | 6.5 [5.8, 7.3] | 4.6 | 0.06 | +2.0 [+0.5, +3.5] | +0.6 [-2.9, +3.9] |
| R2 | 11.6 | 5.0 [4.4, 5.5] | 4.4 | 0.04 | +0.4 [-1.0, +1.9] | +1.8 [-1.5, +4.8] |
| R3 | 8.7 | 5.2 [4.6, 5.8] | 4.7 | 0.04 | +0.7 [-0.8, +2.2] | -1.9 [-5.4, +1.4] |
| R4 | 6.3 | 7.0 [6.2, 7.8] | 4.6 | 0.06 | -0.6 [-2.1, +1.0] | -4.8 [-8.5, -1.5] |
| R5 | 10.7 | 5.1 [4.5, 5.6] | 4.6 | 0.05 | +1.0 [-0.4, +2.5] | -0.2 [-3.5, +3.1] |
| R6 | 8.2 | 4.8 [4.2, 5.4] | 4.4 | 0.05 | -0.5 [-1.9, +1.0] | -0.5 [-4.3, +3.0] |
| R7 | 14.3 | 5.8 [5.1, 6.4] | 4.5 | 4.68 | +0.6 [-0.8, +2.0] | -1.2 [-4.7, +2.4] |
| R8 | 7.5 | 6.3 [5.6, 7.1] | 4.6 | 0.06 | -0.1 [-1.5, +1.5] | -3.5 [-7.6, +0.4] |

Averages over the eight runs: biomass 5.7, glycerol 4.5, lactic acid 0.63, CO2 beyond pairing +0.5, unaccounted -1.2; total 10.1. **Biomass and glycerol (about 101% of the average gap) are measured and are sufficient to explain it;** the unaccounted term is negative on average and its interval includes zero in seven runs (R4 is the exception, −4.9 [−8.5, −1.5]). I do not attribute any of the gap to an unmeasured pathway. The per-run yields differ by more than the measurement sd would allow (R1 0.441 vs R4 0.479 at the same exhausted-sugar endpoint), so some yield variation between runs is outside the stated measurement noise.

### 4.1 R7 review (independent chemistry and carbon, not fit residuals)

| Quantity | R7 | R5 (repeat) | z of difference | Unit |
|---|---|---|---|---|
| final TRS | 28.7 | 6.6 | +26.6 | g/L |
| ethanol 48 h | 84.2 | 96.6 | -6.6 | g/L |
| CO2 48 h | 82.1 | 95.5 | -5.3 | g/L |
| biomass 48 h | 11.6 | 11.3 | +0.4 | g/L |
| glycerol | 8.76 | 10 | -3.2 | g/L |
| final pH | 3.84 | 4.4 | -9.9 | - |
| lactic acid (n.d. = 0.1 +/- 0.058) | 9 | 0.1 | +32.2 | g/L |
| lactic acid carbon | 0.3 | nan |  | C-mol/L |
| lactic acid as glucose equivalent (1 glucose -> 2 lactic acid) | 9 | nan |  | g/L |
| TRS consumed | 192 | 211 |  | g/L |
| share of the R5-R7 TRS-consumption gap that lactic acid carbon could account for | 0.469 | nan |  | fraction |
| ethanol per TRS consumed, as measured | 0.438 | 0.457 |  | g/g |
| ethanol per TRS consumed after removing lactic-acid glucose equivalent | 0.46 | 0.457 |  | g/g |
| carbon recovery, lactate counted (total-input basis) | 101 | 100 |  | % |
| carbon recovery, lactate omitted | 97 | 100 |  | % |
| carbon recovery, consumed basis, lactate counted | 101 | 100 |  | % |

- **Direct observations:** R7 is the only run with detectable lactic acid and the only low pH; at the same nominal conditions it ends with 22.1 g/L more TRS and 12.4 g/L less ethanol than R5 with the same biomass. Counting the lactic acid, its carbon closes at 101.0%; leaving it out gives 97.0% (about 1.9 Monte-Carlo sd below 100%). Lactic acid carbon is 4.7% of the carbon consumed. Its glucose equivalent (1 glucose → 2 lactic acid) is about 9.0 g/L, which is 47% of the 19.2 g/L difference in TRS consumed relative to R5. After removing that sugar, R7's ethanol per sugar consumed is 0.460 g/g against R5's 0.457.
- **Interpretation:** this is evidence of an *unusual* run: it contains a carbon sink and an acid stress that the yeast-only model lacks. It is **not proof of contamination**: no microbiology exists, lactic acid is measured at 48 h only, and the other roughly half of the slower sugar uptake is unexplained. That is why R7 is excluded from the primary fits, kept in every diagnostic table, and tested as a sensitivity case.
- **Effect of including R7 on the fits** (refit with R7 added, warm start, R6 not used; `r7_inclusion_effect.csv`):

| Model | Reduced chi-square | Parameters changing by ≥ 10% or ≥ 1 profile half-width | Parameters shifting by ≥ 2 profile half-widths (value in half-widths) |
|---|---|---|---|
| M5 | 3.86 → 12.32 | P_max -10.1%; Y_P -1.5%; k34 -2.9%; k37 +3.3%; beta_P +13.3%; n_inh -10.3% | k34 (-2.1) |
| M0 | 12.63 → 24.07 | mu_max +10.1%; k34 -5.6% | k34 (-3.1) |

  R7 adds 3083 chi-square units for its 52 residuals in M5 (an average |z| of about 7.7), so the yeast-only model cannot describe it, but the parameter estimates move modestly. The shifts that matter most for a 33-36 C question are k34 (down) and the temperature slope beta_P (up).

## 5. Level 2 questions of the brief

**Q2. Which parameters can these data pin down, and what do you do about the others?** Evidence in section 2. Within the preferred structure: Y_P, rho_CO2 and X_max are well determined; mu_max, q_max, k34 and beta_P are determined within-fit but not robustly across runs (jackknife wider); P_max and n are determined only jointly (ridge, P_max extrapolated); k37 rests on one run; K_s and n = 1 (Level 1) are not supported as fixed values (K_s < 0.2 g/L; n clearly above 1). Actions: report both profile and jackknife ranges; propagate structural alternatives; flag extrapolation; the experiment in 6.4.

**Q3. Is any run unfit for fitting the yeast model?** R7, on independent grounds (section 4.1): lactic acid 9.0 g/L (≥ 45 times the 0.2 g/L detection limit), pH 3.84 (-9.9 sd below R5), a lactate carbon sink of 4.7% of consumed carbon that a yeast-only model has no term for, and a carbon balance that closes only if lactate is counted. R4 is a measurement-quality case (recovery 104.7%, catabolic yield above stoichiometric) but is not unfit. R3 is fit for sugar, ethanol and CO2 (carbon closes at 101.7%); only its OD600 biomass is treated separately. Contamination is a hypothesis, not a finding.

**Q4. Overall ethanol yield, basis, and the gap to the maximum?** 0.459 g/g on consumed TRS (glucose equivalent), 89.8% of 0.511; about 0.476 g per g sugar charged and consumed. The gap (≈10% of the theoretical yield) is accounted for by biomass formation (5.7 points) and glycerol (4.5 points) with lactic acid in R7; the unaccounted carbon averages -1.2 points.

**Q5. What does the model predict at 37 C and 260 g/L, and how far to trust it?** Section 6.1 gives the numbers. Trust is low for anything beyond the first ~48 h: 37 C is supported by one run (R8, 220 g/L), 260 g/L in the training set by R3 only (30 C; R6 at 34 C was not used), and the combination is not observed; ethanol above 108 g/L, the TRS tail below 50 g/L and any end time beyond 48 h are extrapolations; candidate structures disagree on the 96 h TRS by tens of g/L.

**Q6. Which single experiment?** Section 6.4.

## 6. Task 5: plant-relevant uncertainty (fixed scenarios only; not an optimisation)

The brief's margin formula was applied exactly as stated in section 4 of the brief (170 m3, 8 h turnaround, ₹60/L, ₹25/kg TRS for all sugar charged, steam from the design curve, batch ended when TRS ≤ 5 g/L). The batch end is searched to 120 h, but the data stop at 48 h. Where the wash strength leaves the 7-14% v/v design curve the steam value is clipped and flagged.

### 6.1 Preferred model M5: parameter uncertainty (150 draws from the linearised covariance; profile-ensemble range in `plant_prediction_uncertainty.csv`)

| Scenario (T / TRS g/L) | Ethanol at 48 h (g/L) | TRS at 48 h (g/L) | TRS at 96 h (g/L) | Time to ≤ 5 g/L and daily margin per fermenter |
|---|---|---|---|---|
| 33 C / 220 | 99.6 [98.5, 100.4] | 2.4 [1.4, 3.5] | 0.0 [0.0, 0.0] | 46 h [46, 47]; margin 112.5k [107.6k, 116.7k] |
| 34 C / 260 | 98.2 [96.9, 99.1] | 45.3 [43.7, 47.1] | 1.1 [0.0, 9.1] | 88 h [81, 106]; margin 80.7k [66.3k, 85.9k] |
| 36 C / 260 | 85.0 [83.8, 85.8] | 72.6 [71.2, 74.3] | 27.4 [22.6, 34.3] | not reached in 120 h; no margin |
| 37 C / 260 | 78.3 [77.1, 79.1] | 86.6 [85.0, 88.5] | 41.3 [36.9, 47.1] | not reached in 120 h; no margin |

Flags: the 33 C and 36 C scenarios use the interpolated multipliers; the 34 C / 260 g/L batch ends at an ethanol level of about 118 g/L (above the observed maximum of 107.8 g/L and at 14.9% v/v, above the 14% limit of the steam curve) and later than the 48 h data. For the 37 C / 260 g/L case the brief asks about, the preferred model gives ethanol 78 g/L and TRS 87 g/L at 48 h; 41 g/L TRS at 96 h; **no end of batch within 120 h**.

### 6.2 Structure uncertainty: each candidate at its own optimum (TRS at 96 h g/L / time to ≤ 5 g/L / margin, ₹ per day)

| Model | 33 C / 220 | 34 C / 260 | 36 C / 260 | 37 C / 260 |
|---|---|---|---|---|
| M0 | 0 / 45 h / 118k | 8 / never / – | 13 / never / – | 19 / never / – |
| M1 | 0 / 44 h / 121k | 5 / 94 h / 77k | 11 / 120 h / 61k | 17 / never / – |
| M2 | 0 / 48 h / 112k | 32 / never / – | 50 / never / – | 60 / never / – |
| M3 | 0 / 43 h / 118k | 0 / 64 h / 106k | 0 / 81 h / 86k | 3 / 94 h / 75k |
| M4 | 0 / 45 h / 117k | 11 / never / – | 16 / never / – | 21 / never / – |
| M5 | 0 / 46 h / 112k | 1 / 88 h / 81k | 27 / never / – | 41 / never / – |
| M6 | 0 / 48 h / 110k | 33 / never / – | 51 / never / – | 59 / never / – |

At 33 C / 220 g/L the structures agree on the batch time (43-48 h) and the daily margin varies by ±4% about its mean, comparable to the parameter-only interval (108k-117k). At 34-37 C / 260 g/L the structures disagree on whether the batch can finish within 96 h at all, and by tens of g/L in TRS: that disagreement, not the parameter interval, dominates. Refitting M5 with R6 added (labelled secondary, R6 used as training) moves the 34 C / 260 g/L batch time from 88 h to 88 h and the margin from ₹80.7k to ₹79.4k per day.

### 6.3 Which parameters drive the uncertainty (linearised, additive shares of the predictive variance; grouped because the P_max–n ridge makes single-parameter shares meaningless)

| Quantity | Ethanol-inhibition shape (P_max, n) | Temperature (beta_P, k34, k37) | Yield (Y_P, rho_CO2) | Growth and uptake (mu_max, X_max, q_max) |
|---|---|---|---|---|
| margin 33 C/220 | 44% | -2% | 70% | -11% |
| margin 34 C/260 | 109% | -12% | 5% | -2% |
| TRS(96 h) 36 C/260 | 93% | 3% | 1% | 3% |
| TRS(96 h) 37 C/260 | 72% | 21% | 1% | 5% |

Linearised 1-sd uncertainty of the daily margin: ₹2.6k (2.3%) at 33 C / 220 and ₹4.2k (5.2%) at 34 C / 260. At 33 C / 220 the yield (Y_P) and the inhibition shape dominate; at the 260 g/L scenarios the ethanol-inhibition shape and the temperature slope dominate. K_s: re-optimised M5 predictions at 33 C / 220 are insensitive to the primary K_s = 1 g/L (K_s 0.05 → 5: batch time 46.0 → 47.6 h; margin ₹113.7k → ₹107.6k), and only a K_s of 20 g/L, which the data reject, gives a large change.

| K_s (g/L) | chi-square | Time to ≤ 5 g/L and margin at 33 C / 220 | TRS at 96 h |
|---|---|---|---|
| 0.05 | 977 | 46.0 h / 113.7k | 0.0 |
| 0.2 | 997 | 46.0 h / 113.6k | 0.0 |
| 1 | 1116 | 46.3 h / 112.5k | 0.0 |
| 5 | 1832 | 47.6 h / 107.6k | 0.0 |
| 20 | 5194 | 52.5 h / 93.0k | 0.0 |

### 6.4 The single most useful additional experiment
**One 96-hour batch at 34 C and 260 g/L TRS (the conditions of R6, extended to 96 h), sampled as before to 48 h and every 12 h to 96 h for biomass (dry weight, not OD600), TRS, ethanol and CO2, with endpoint and 48 h glycerol, lactic acid and pH. If a duplicate is possible it also measures run-to-run reproducibility, which the data lack.**
Why this one:
- **Model sensitivity:** the prediction uncertainty at the high-sugar scenarios is dominated by the shape and temperature dependence of ethanol inhibition at ethanol levels above 100 g/L and by the TRS tail after 48 h (section 6.3). No run contains data past 48 h or ethanol above 108 g/L at 34 C.
- **Coverage:** the run sits on the one cell (34 C, 260 g/L) already bracketed by R6 at 48 h and by R3 at 30 C, and extends it in time; the 33 and 36 C interpolations and the 37 C extrapolation stay unobserved, but the structures that disagree most there are the ones this run discriminates.
- **Linearised design criterion** (preferred model; extra data weighted by the stated sds; reduction in the predictive sd of the daily margin, of TRS at 96 h, and the chi-square distance between preferred model and M2 along the new run; `experiment_design.csv`, `experiment_discrimination.csv`):

| Candidate run (T / TRS / duration) | Mean reduction in margin sd (33/220 and 34/260 scenarios) | Margin sd reduction at 34/260 | TRS(96 h) sd reduction at 36/260 | TRS(96 h) sd reduction at 37/260 | Separation M5 vs M2 (chi-square units) |
|---|---|---|---|---|---|
| 34 C / 260 / 96 h | 36% | 59% | 66% | 53% | 10228 |
| 33 C / 260 / 96 h | 33% | 52% | 51% | 39% | 8280 |
| 36 C / 260 / 96 h | 28% | 45% | 65% | 65% | 2195 |
| 37 C / 220 / 96 h | 25% | 40% | 63% | 69% | 2593 |
| 37 C / 260 / 96 h | 22% | 34% | 52% | 57% | 1023 |
| 34 C / 260 / 48 h | 9% | 10% | 10% | 10% | 120 |

  The best 96 h run reduces the predicted margin sd by about 36% on average, against 9% for repeating the same condition to 48 h only: the added duration, not the condition, carries most of the information. A 36 C / 260 g/L run to 96 h is the alternative if the warm-water scenario matters most: it reduces the TRS(96 h) sd at the 37 C scenario more (64% vs 52%) and equals the 34 C run at the 36 C scenario (65%), but it separates the competing structures about 4.7 times less strongly and reduces the margin sd less. A 37 C / 260 g/L run to 96 h separates them about 10 times less strongly.
- **Caveats:** the design criterion is linearised around the preferred model, uses only that model's parameter uncertainty (structural uncertainty enters only through the separation column), and assumes the new run behaves like the training runs (no contamination, which the proposed lactate/pH check would reveal).

## 7. Limitations and unresolved issues
1. **Preferred structure is not validated at 37 C.** With R8 left out M5 extrapolates badly (chi2/pt 731); M2/M6 behave better there (≈ 12-10). M5 was chosen by the pre-registered rule; I did not change the rule after seeing this.
2. **No candidate fits within noise** (reduced chi-square ≥ 3.9); residuals are autocorrelated; the biomass of R3 remains OD600-based and unvalidated.
3. **P_max and n form a ridge; P_max is extrapolated** well above observed ethanol; all high-ethanol predictions (≥ 100 g/L, the 14% v/v steam-curve limit) are extrapolations.
4. **Only one run at 37 C and none at 33 or 36 C**; k33/k36 are linear interpolations; the code refuses temperatures outside 30-37 C.
5. **Run-to-run variability is not measured**: only replicate pair R5/R7 exists and R7 is unusual. Profile intervals use measurement sds scaled by the fit's c_hat, not replicate variance.
6. **K_s = 1 g/L (fixed) is disfavoured by the data** (K_s < 0.2 g/L); it is retained as the documented primary value, with sensitivity.
7. **Carbon balance:** unmeasured organic carbon, by-products and dissolved CO2 are not quantified; R4 does not close within 95%.
8. **R7 remains a hypothesis-level exclusion** (no microbiology).
9. **R6 is not blind** for any Level 2 conclusion; its only uses are the labelled diagnostic and the labelled secondary refit.
10. **The brief's uncertainty table mapping (D-03) is still unconfirmed**, and the CO2 sd floor (0.10 g/L) is my assumption.
11. **pytest and local runs are still to be done by you.**

## 8. Reproduce
```
pip install numpy scipy pandas matplotlib pytest
python src/compare.py --stage fit  --models M0,M1,M2,M3,M4,M5,M6      # ~4 min total
python src/compare.py --stage loro --models M0,M1,M2,M3,M4,M5,M6      # ~12 min
python src/compare.py --stage select                                   # freezes the selection (hash)
python src/compare.py --stage r6diag                                   # refuses to run if the tables changed
python src/uncertainty.py --stage r7 --models M5,M0 ; python src/uncertainty.py --stage fixedgrid --models M5,M0
python src/uncertainty.py --stage profile --models M5 ; python src/uncertainty.py --stage profile --models M0   # ~25 min
python src/uncertainty.py --stage assemble --models M5,M0
python src/plant_uncertainty.py --stage predict ; ... --stage design ; ... --stage ksens ; ... --stage discriminate ; ... --stage plot
python src/carbon_balance.py --data-dir data/raw --root .
pytest -q
```
(`uncertainty.py` stages `profile` and later use the preferred model named in `model_selection_frozen.json`: here M5.)

## 9. Files
Code: `src/models.py`, `src/compare.py`, `src/uncertainty.py`, `src/plant_uncertainty.py`, `src/carbon_balance.py`; tests: `tests/test_level2.py`.
Tables: `model_comparison.csv`, `candidate_parameters.csv`, `model_residuals.csv`, `model_selection_frozen.json`, `model_r6_diagnostic.csv`, `parameter_uncertainty.csv`, `parameter_profiles.csv`, `parameter_correlations_material.csv`, `fixed_parameter_sensitivity.csv`, `r7_inclusion_effect.csv`, `carbon_balance_all_runs.csv`, `ethanol_yields.csv`, `ethanol_yield_pooled.csv`, `yield_gap_decomposition.csv`, `r7_review.csv`, `plant_prediction_uncertainty.csv`, `structure_spread.csv`, `plant_Ks_sensitivity.csv`, `plant_linearised_sd.csv`, `variance_decomposition.csv`, `experiment_design.csv`, `experiment_discrimination.csv`, and `work/` (per-model fit, LORO, profile JSON).
Figures: `model_comparison_residuals.png`, `parameter_profiles_M5.png`, `parameter_profiles_M0.png`, `carbon_balance_all_runs.png`, `ethanol_yield_gap.png`, `plant_uncertainty.png`.
