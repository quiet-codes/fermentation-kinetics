# Level 1 report: kinetic model, fit and held-out prediction

**Scope:** Level 1 only (brief s5, Level 1). No Level 2 uncertainty analysis (no profile likelihood, no Monte Carlo, no model-structure comparison, no final carbon balance) and no Level 3 optimisation was done.
**Spec:** `docs/assignment_brief.md`, `CLAUDE.md`. Decisions are logged in `handoff/DECISIONS.md` (D-10 to D-21) and were recorded **before** any fit.
**What was actually executed (AI sandbox, Python 3.12.3, numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, matplotlib 3.10.8):** `src/fit.py` stages fit, predict and sensitivity; `src/level1_summary.py`; `tests/test_model.py` through a fallback runner (pytest is not installed in the sandbox: **16 passed, 0 failed, 0 skipped**); Phase 0 script re-run (74 PASS / 58 INFO / 5 FLAG, tables identical to the supplied ones apart from CR line endings). **Not executed:** pytest itself, anything on the user's machine. The user did not supply local Phase 0 results in this conversation (the placeholder line was left as template text), so local Phase 0 execution is still unconfirmed.

---

## 1. Run selection (D-10 to D-13)

| Run | Role | Basis (direct evidence) | Remaining uncertainty |
|---|---|---|---|
| R1, R2, R4, R5, R8 | Training | Clean endpoint chemistry (lactic n.d., pH 4.38-4.43), dry-weight biomass | R5 has no usable replicate once R7 is out |
| R3 | Training for TRS, ethanol, CO2; **biomass not in the objective** | `runs.csv` note: biomass by OD600 because the dry-weight oven was under repair; no calibration or uncertainty supplied. The reason is the method, not the residuals. Its carbon balance closes (101.8%) | R3 biomass is simulated from the recorded 2.5 g/L inoculum and is **neither fitted nor validated** |
| R6 | **Held out** | 34 C and 260 g/L is not represented by any training run at that combination. Clean chemistry (lactic n.d., pH 4.46, carbon 100.4%, dry-weight biomass). Shows a late stall | Its raw curve was seen in Phase 0 (permitted by the brief) but was never used for estimation, equation choice or settings |
| R7 | Excluded from the primary fit; sensitivity fit only | Only run with lactic acid (9.00 g/L; detection limit 0.2) and with pH 3.84 (others 4.35-4.46); at 48 h TRS 28.7 vs 6.6 and ethanol 84.2 vs 96.6 g/L against its repeat R5, with the same biomass. The yeast-only model has no lactate sink or acid stress. Lactic carbon (about 4.7% of the sugar carbon) is what closes its carbon balance (101.2%, versus about 96.5% without it) | **A second organism is a hypothesis, not a finding**: no microbiology, lactate measured only at 48 h, and lactate could also follow a stressed run. Excluding R7 removes the only replicate, so run-to-run variability is not measured (see section 7) |

R8 stays in training because it is the only 37 C run.

## 2. Model (explicit ODEs, `src/kinetics.py`)

States (g/L): X biomass, S residual TRS (as glucose), P ethanol, C cumulative CO2. Constant volume; time in h. Initial states are the nominal `runs.csv` values: X(0) = inoculum (2.5), S(0) = nominal TRS (160/220/260), P(0) = C(0) = 0.

```
k(T)  = 1 at 30 C, k34 at 34 C, k37 at 37 C   (piecewise linear between, ValueError outside 30-37 C)
m(S)  = S / (Ks + S)                                       Ks fixed = 1 g/L
mu    = mu_max * k(T) * m(S) * (1 - X / X_max)
q_S   = q_max  * k(T) * m(S) * (1 - P / P_max)^n           n fixed = 1
dX/dt = mu X
dS/dt = -1.2206 mu X  -  q_S X
dP/dt =  Y_P q_S X
dC/dt =  rho_CO2 dP/dt
```
1.2206 g glucose per g biomass = (12.011/24.6)/(72.066/180.16): the glucose carbon needed for CH1.8O0.5N0.2 biomass (brief s3). It is fixed, not fitted. X, S, P are clipped at 0 and the two bracketed saturation factors are clipped at 0 inside the rates. Glycerol, lactic acid and pH are not states (glycerol enters the Level 2 carbon balance).

### Term-by-term justification (direct evidence in italics, hypotheses marked)
- **Biomass saturation, (1 - X/X_max).** *In every run biomass is 10.0-11.5 g/L at 24 h and then roughly flat, although R2, R3, R5, R6, R7 and R8 still hold 70-122 g/L TRS at 24 h, so running out of sugar is not what stops growth.* The plateau is also similar at 24 h whether ethanol is about 50 g/L (R8) or about 65-69 g/L (R1, R2). A nutrient limit would fit this (hypothesis, no nutrient data); the data cannot separate it from other causes, so X_max is phenomenological.
- **Sugar and ethanol production continue after growth stops.** *Ethanol rises from about 65 to 100+ g/L between 24 and 48 h at near-constant biomass,* so uptake is written per unit biomass and is not tied to growth.
- **Linear ethanol inhibition of uptake, (1 - P/P_max).** *In R3, R6, R7, R8 (and weaker R5) the sugar uptake over 36-48 h is 30-50% of its early value with sugar still present (Phase 0 O10),* while biomass is flat, so the slowdown is a falling rate per cell. Its form and the fixed exponent n = 1 are the user's simplification, not something the data demonstrated. P_max is the ethanol level at which this form would stop uptake.
- **Temperature multipliers (not a smooth law).** *Early ethanol rates (0-12 h) are equal at 30 and 34 C (2.84 vs 2.88 g/L/h at 160 g/L; 2.53 vs 2.58 at 220 g/L) and about 25% lower at 37 C (1.95),* so neither an Arrhenius law nor a log-linear law fits the raw rates. Three observed levels get one multiplier each (k(30) = 1). The interpolation between levels is an assumption and nothing is extrapolated.
- **Constant yield Y_P and CO2 = rho x ethanol.** *Glycerol per g sugar consumed is a constant 0.045-0.048 g/g and ethanol:CO2 is near 1:1 molar,* so no extra by-product or CO2 kinetics are introduced.
- **Monod term with fixed Ks.** *Sugar is above about 7 g/L at almost every sample; the only low-sugar observations are R1/R4 at 24-30 h,* so Ks cannot be estimated and is fixed a priori.
- **Not included (no supporting evidence in the training curves, or excluded by decision):** substrate inhibition (220 and 260 g/L look alike), Arrhenius temperature dependence, maintenance, cell death, ethanol inhibition of growth, P_max(T), estimated n, lactate or acid effects.

## 3. Estimation method
- **Objective:** weighted nonlinear least squares, residual = (model - observed) / sd, positive-time observations only (t = 0 rows are diagnostics, `level1_t0_diagnostics.csv`; initial states are not re-set to match them). Measured t = 0 values stay in the plots as open diamonds.
- **sd (brief s3):** biomass 0.035 x measured + 0.08; TRS 0.01 x measured + 0.4; ethanol 0.012 x measured + 0.25 g/L; CO2 0.02 x measured **+ 0.10 g/L (my documented floor; the brief gives only "about 2%")**. The smallest positive-time CO2 value is 3 g/L, so no weight is infinite; the floor raises the sd of that point 2.67-fold and the median sd 1.12-fold.
- **Data in the objective:** 299 residuals = 6 training runs x 13 times x (S, P, CO2) + 5 runs x 13 times (biomass; R3 biomass excluded). 8 fitted parameters, 291 degrees of freedom.
- **Solver:** `scipy.integrate.solve_ivp`, LSODA, rtol 1e-9, atol 1e-11. **Optimiser:** `scipy.optimize.least_squares`, trf, bounds, x_scale = jac, diff_step 1e-6, ftol = xtol = gtol = 1e-10, max_nfev 400. **Starts:** the nominal start plus 40 Latin-hypercube starts (seed 20261026), log-sampled for mu_max and q_max.
- **Failures:** solver failures would be replaced by a residual of 1000 and counted. Counted: **0**.
- **Convergence:** all 41 starts ended with status 3 (xtol) and chi-square between 3675.255 and 3675.294; 41 of 41 within 0.1% of the best. That indicates one minimum inside these bounds; it does not show the model is right. No fitted parameter sits at a bound.
- **Protocol for R6:** the fit stage reads only the training runs, writes `level1_parameters.csv` and its SHA-256 (`level1_frozen.json`); the predict stage verifies the hash before it loads R6.

## 4. Fitted parameters (training runs R1, R2, R3*, R4, R5, R8)

| Parameter | Meaning | Estimate | Unit | Approx. SE (scaled) | Bounds | Start | At bound |
|---|---|---|---|---|---|---|---|
| mu_max | max specific growth rate, 30 C | 0.2175 | 1/h | 0.013 (5.8%) | 0.05 – 1.5 | 0.3 | no |
| X_max | biomass saturation | 9.337 | g/L | 0.24 (2.6%) | 8 – 20 | 11.5 | no |
| q_max | max specific catabolic uptake, 30 C | 1.297 | g/g/h | 0.034 (2.6%) | 0.2 – 5 | 1 | no |
| P_max | ethanol at which uptake would stop (linear inhibition) | 118.5 | g/L | 2.3 (1.9%) | 108 – 500 | 150 | no |
| Y_P | ethanol per g catabolised sugar | 0.478 | g/g | 0.0042 (0.9%) | 0.3 – 0.511 | 0.47 | no |
| rho_CO2 | CO2 per g ethanol | 0.9871 | g/g | 0.012 (1.2%) | 0.8 – 1.2 | 0.96 | no |
| k34 | rate multiplier 34 C vs 30 C | 0.9714 | - | 0.0084 (0.9%) | 0.2 – 1.5 | 1 | no |
| k37 | rate multiplier 37 C vs 30 C | 0.6687 | - | 0.0082 (1.2%) | 0.2 – 1.5 | 0.8 | no |

Fixed: K_s = 1 g/L, n = 1. Derived effective maxima (delta method):

| Quantity | Value | Approx. SE |
|---|---|---|
| mu_max*k34 | 0.2112 1/h | 0.012 (5.8%) |
| mu_max*k37 | 0.1454 1/h | 0.0086 (5.9%) |
| q_max*k34 | 1.26 g/g/h | 0.033 (2.7%) |
| q_max*k37 | 0.8675 g/g/h | 0.024 (2.8%) |

### Uncertainty and identifiability: what can be said and what cannot
- The SEs are **linearised Gauss-Newton** values at the optimum, scaled by sqrt(chi2/dof) = 3.55 because the reduced chi-square is 12.6 (chi-square 3675 for 291 dof). They measure how tightly the data pin each number **if this structure were correct**; they are **not credible intervals**, they do not include model-structure error, and measurement sds alone clearly understate the real scatter. Profile-likelihood intervals are Level 2 work and were not attempted.
- Numerically the problem is well-conditioned: the relative Jacobian's condition number is 21 and the largest correlations are mu_max–q_max −0.73, mu_max–P_max +0.64, q_max–P_max −0.58. No parameter is at a bound.
- **Weakly supported in substance despite small SEs:** k37 (one run, R8); k34 (R4 and R5 only, since R6 is held out and R7 is excluded); P_max (above the highest ethanol observed in training, 107.8 g/L, so it is partly extrapolated; its value of 118.5 g/L depends on the imposed linear form); X_max (the model plateau is below the data, see section 5); mu_max (growth sampled every 2 h with a large biomass sd). K_s and n are not estimated.
- **CO2 ratio:** rho_CO2 = 0.987 +/- 0.012 against the stoichiometric 0.955, i.e. +3.3% and 2.6 approximate SE above it. Observed 48 h CO2:ethanol ratios of individual runs span 0.938 (R4) to 1.022 (R1). The excess over 0.955 is not explained here (CO2 also arises from biomass formation; dissolved CO2 and by-products are not modelled; the fit is a compromise across runs). Y_P = 0.478 g/g is 93.5% of 0.511; the gap is a Level 2 (carbon balance) question.

## 5. Training fit quality (`level1_fits.png`, `level1_fit_diagnostics.csv`)
rms z / mean z per run (z = (model - data)/sd; |z| around 1 would be consistent with the stated noise):

| Run | Biomass | TRS | Ethanol | CO2 |
|---|---|---|---|---|
| R1 | 2.56 / -1.64 | 1.73 / 0.23 | 1.47 / -0.86 | 1.95 / -1.8 |
| R2 | 2.76 / -0.94 | 5.76 / -0.03 | 2.55 / 0.95 | 1.9 / 1.49 |
| R3 | 4.66 (not fitted) / 0.38 | 5.15 / -1.74 | 3.55 / 1.65 | 2.86 / 1.76 |
| R4 | 2.84 / -2.32 | 2.67 / 1.73 | 3.96 / -3.16 | 2.78 / -1.51 |
| R5 | 2.48 / -1.37 | 5.01 / -3.25 | 2.1 / 0.46 | 1.86 / 0.13 |
| R8 | 1.74 / -0.92 | 5.97 / -0.7 | 5.25 / -2.99 | 5.0 / -2.76 |

- Pooled rms z of the training fit: biomass 2.50, TRS 4.67, ethanol 3.39, CO2 2.94; overall 3.51. **The model does not fit within the stated measurement noise.** It reproduces the broad shape of every run (160 g/L runs exhaust sugar near 30 h and plateau near 72 g/L ethanol; the 220-260 g/L runs and R8 slow with sugar left) but with systematic deviations.
- **Biomass plateau is too low:** the model saturates at X_max = 9.34 g/L whereas the data reach 10-11.5 g/L by 24 h and 10.9-12.3 g/L at 48 h; pooled mean z -1.44. I did not add terms to fix this (instruction D-17). The biomass state therefore works as a catalyst for the fermentation rate rather than as a faithful biomass prediction. I did not test why it settles below the data.
- **TRS** residuals keep one sign for 6-10 consecutive samples in R2, R3, R5 and R8 (late-phase curvature not captured).
- R1 and R4 are near-replicates in kinetics yet end at 71.8 and 74.6 g/L ethanol (both with TRS about 0), a difference of 2.8 g/L, about 1.7 sd of the difference of two measurements with the stated noise. That points to run-to-run yield variation outside the model and the sds (hypothesis).
- R3 biomass (OD600, not fitted) lies above the model in the late phase; no validity is claimed for it either way.

## 6. Held-out prediction of R6 (34 C, 260 g/L), parameters frozen, no refitting (`heldout_prediction.png`, `heldout_metrics.csv`, `heldout_predictions.csv`)

Time-course errors at the 13 positive-time samples (error = prediction - measurement; z uses the measurement sd):

| Variable | RMSE | Bias | RMSE as % of mean | Mean z | rms z | Within 2 sd | Longest same-sign run |
|---|---|---|---|---|---|---|---|
| Biomass (g/L) | 0.80 | -0.26 | 10.2 | -0.30 | 2.06 | 54% | 7 of 13 |
| TRS (g/L) | 7.51 | -4.98 | 4.8 | -3.89 | 5.61 | 31% | 10 of 13 |
| Ethanol (g/L) | 2.73 | +1.76 | 5.8 | +1.61 | 3.06 | 46% | 9 of 13 |
| CO2 (g/L) | 3.80 | +2.97 | 8.4 | +2.19 | 2.69 | 31% | 11 of 13 |

At 48 h:

| Variable | Measured | Predicted | Error | z |
|---|---|---|---|---|
| Biomass (g/L) | 10.87 | 9.34 | -1.53 | -3.3 |
| TRS (g/L) | 48.70 | 38.69 | -10.01 | -11.3 |
| Ethanol (g/L) | 100.10 | 101.79 | +1.69 | +1.2 |
| CO2 (g/L) | 94.10 | 100.48 | +6.38 | +3.2 |

**Reading of the result (observations first, then hypotheses):**
- *Ethanol* is predicted to within 1.7 g/L (1.7%) at 48 h, but is over-predicted at 12-30 h by up to 5.6 g/L and the ethanol errors exceed 2 sd at 7 of 13 samples (TRS 9 of 13, CO2 9 of 13, biomass 6 of 13).
- *TRS is the poorest-predicted variable:* the model predicts less residual sugar than measured at every sample from 8 h onward (48 h: 38.7 vs 48.7 g/L, an error of -10.0 g/L). Relative to the plant's 5 g/L end-of-batch limit this is a large error, although it does not by itself say anything about 33-36 C.
- *CO2* is over-predicted from 12 h onward by an amount that grows from +2.1 to +6.4 g/L (2.96-3.7 sd at every sample from 12 h); R6's measured CO2:ethanol ratio is 0.940 against the fitted rho_CO2 of 0.987.
- *Biomass* plateau is under-predicted (-1.53 g/L at 48 h), as in training.
- **Comparison with training:** the R6 rms z (2.06 biomass, 5.61 TRS, 3.06 ethanol, 2.69 CO2) is similar to the in-sample misfit (2.50, 4.67, 3.39, 2.94), so structural misfit rather than overfitting dominates. The exception is the TRS bias (mean z -3.9 for R6 against -0.6 pooled in training), which is a systematic prediction error.
- **Sugar-error arithmetic (hand calculation from the tables):** R6's measured ethanol per g TRS dropped (nominal S0) is 0.474, above every training run (0.450-0.467); the model's value is 0.460. At R6's own yield the predicted ethanol would need about 214.9 g/L of sugar rather than 221.3, so roughly 6 of the 10 g/L TRS error comes from yield and about 4 g/L from the 1.7 g/L ethanol over-prediction.
- **Hypotheses (not tested, R6 not used to choose among them):** (i) ethanol tolerance falls with temperature, i.e. the P_max(T) the user excluded from this model; the Phase 0 raw data (stronger stall in R6 than in R3) pointed this way, and the sign of the R6 error is compatible with it; (ii) run-to-run yield variation of the kind seen between R1 and R4; (iii) a different yield at 260 g/L. One held-out run cannot separate these.
- **Limits of this test:** it is one run, at one condition, with the model structure chosen before R6 was predicted and the large in-sample misfit shown above. **It does not show that the model generalises across operating conditions**, and the 33 and 36 C scenarios and 37 C with 260 g/L would need interpolation or extrapolation that the fitted multipliers do not support (k is defined only at 30, 34 and 37 C).

## 7. Sensitivity analyses (predeclared, run only after the primary fit and the R6 prediction; R6 not used; no R6 metrics computed for them; nothing selected from them)
Change in the fitted value relative to the primary fit, in % (and in primary linearised SE units):

| Parameter | R7 included | R3 biomass incl. (sd x2) | K_s = 0.2 | K_s = 5 | CO2 floor 0 | CO2 floor 0.5 |
|---|---|---|---|---|---|---|
| mu_max | +10.1% (+1.7) | -3.3% (-0.6) | +6.1% (+1.0) | -0.5% (-0.1) | -13.9% (-2.4) | +4.4% (+0.8) |
| X_max | -2.6% (-1.0) | +1.0% (+0.4) | -2.5% (-1.0) | +1.6% (+0.6) | +0.4% (+0.1) | +1.8% (+0.7) |
| q_max | +1.8% (+0.7) | +1.0% (+0.4) | -2.8% (-1.1) | +3.1% (+1.2) | +7.1% (+2.7) | -3.3% (-1.3) |
| P_max | -4.1% (-2.1) | -0.8% (-0.4) | +2.7% (+1.4) | +1.5% (+0.8) | -3.3% (-1.7) | +1.4% (+0.7) |
| Y_P | -1.7% (-1.9) | +0.1% (+0.1) | -0.1% (-0.1) | -0.3% (-0.4) | -0.3% (-0.3) | +0.4% (+0.5) |
| rho_CO2 | -0.2% (-0.2) | +0.0% (+0.0) | +0.1% (+0.1) | -0.1% (-0.1) | +0.7% (+0.6) | -0.9% (-0.7) |
| k34 | -5.6% (-6.5) | +0.0% (+0.0) | +0.3% (+0.4) | +0.9% (+1.0) | +0.6% (+0.7) | -0.5% (-0.6) |
| k37 | -0.4% (-0.3) | -0.0% (-0.0) | +0.3% (+0.2) | -0.5% (-0.4) | +1.4% (+1.2) | -1.3% (-1.1) |
| reduced chi-square | 24.07 | 12.31 | 12.49 | 14.06 | 14.61 | 10.92 |

- **R7 included:** reduced chi-square rises from 12.6 to 24.1. The estimates move by at most about 10% (mu_max +10.1%, k34 -5.6%, Y_P -1.7%). In SE units k34 (-6.5), P_max (-2.1) and Y_P (-1.9) move most, but because the SEs are small relative to the misfit, SE units overstate the importance; I regard the k34 shift (the 34 C multiplier falls from 0.971 to about 0.917) as the one change that could matter for a 33-36 C recommendation. This is consistent with R7 being slower than R5, but that is not evidence about why.
- **R3 biomass included:** no material change (largest shift 3.3%).
- **K_s:** shifts of at most about 6% (mu_max) over 0.2-5 g/L; K_s does not change the picture.
- **CO2 floor:** removing the floor shifts mu_max by -13.9% and q_max by +7.1% (about 2.4-2.7 SE); a floor of 0.5 g/L shifts them by at most 4.4%. The early, small CO2 values therefore carry some weight in the growth-rate estimate, and the floor is a real, documented assumption.

## 8. Limitations and unresolved issues
1. The model does not reproduce the data within the stated noise (reduced chi-square 12.6); the biomass plateau is too low and late-phase TRS curvature is systematically mismatched. Structure changes were not made after seeing the training fit (instructions) and none were made after seeing R6.
2. R6 prediction errors typically 2-6 sd in all variables, with TRS biased low by about 10 g/L at 48 h.
3. k37 rests on one run; k34 on R4 and R5; interpolation to 33 and 36 C is an assumption; the model refuses temperatures outside 30-37 C.
4. P_max is only partly constrained by training data (training ethanol is at most 107.8 g/L) and depends on the linear inhibition form.
5. With R7 excluded and R6 held out, run-to-run variability cannot be measured from replicates; measurement-only sds understate it (reduced chi-square above 12; R1 vs R4; R5 vs R7).
6. The R7 explanation (second organism) is untested. The CO2 floor (0.10 g/L), K_s (1 g/L) and the biomass sugar term (carbon-closure value 1.2206 g/g) are my documented assumptions.
7. Carbon balance, parameter profile intervals, model comparison and the plant optimisation were not done (Levels 2-3).
8. The brief's uncertainty table is still read in row order from PDF-extracted text (D-03) and the user has not confirmed it.
9. pytest itself has not been run; the model tests were run with a fallback runner in the sandbox, and nothing was run locally.

## 9. Reproduce
```
pip install numpy scipy pandas matplotlib pytest      # tested with numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, matplotlib 3.10.8
python src/fit.py --data-dir data/raw --root . --stage all     # fit (~3 min), R6 prediction, sensitivity (~5 min)
python src/level1_summary.py --data-dir data/raw --root .
pytest -q
```
Re-running `--stage all` refits and refreezes the parameters before R6 is read, so the protocol is preserved. Small last-digit differences across platforms are possible.

## 10. Files
Code: `src/kinetics.py`, `src/fit.py`, `src/level1_summary.py`, `tests/test_model.py`. Tables: `level1_parameters.csv`, `heldout_metrics.csv`, `heldout_predictions.csv`, `level1_fit_diagnostics.csv`, `level1_t0_diagnostics.csv`, `level1_multistart.csv`, `level1_sensitivity.csv`, `level1_correlations.csv`, `level1_summary_numbers.csv`, `level1_frozen.json`. Figures: `level1_fits.png`, `heldout_prediction.png`.
