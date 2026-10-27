"""Generates reports/level1.md from the output tables (run from the project root after the Level 1 stages have produced them).
Usage: python src/make_level1_report.py [output_path]   (default: reports/level1.md)
Every number in the report is read from outputs/tables/*.csv or *.json; hand-typed numbers in the text are checked by tests/test_report_claims.py."""
import sys
OUT = sys.argv[1] if len(sys.argv) > 1 else 'reports/level1.md'
import json, pandas as pd, numpy as np
T='outputs/tables/'
P=pd.read_csv(T+'level1_parameters.csv'); fr=json.load(open(T+'level1_frozen.json'))
D=pd.read_csv(T+'level1_fit_diagnostics.csv'); H=pd.read_csv(T+'heldout_metrics.csv')
S=pd.read_csv(T+'level1_sensitivity.csv'); N=pd.read_csv(T+'level1_summary_numbers.csv').set_index('name').value
MS=pd.read_csv(T+'level1_multistart.csv'); HP=pd.read_csv(T+'heldout_predictions.csv')
f=lambda x,n=4: f"{x:.{n}g}"
fit=P[P.status=='fitted'].set_index('parameter'); fx=P[P.status=='fixed'].set_index('parameter'); dv=P[P.status=='derived'].set_index('parameter')
# parameter table
rows=[]
meaning={'mu_max':'max specific growth rate, 30 C','X_max':'biomass saturation','q_max':'max specific catabolic uptake, 30 C','P_max':'ethanol at which uptake would stop (linear inhibition)','Y_P':'ethanol per g catabolised sugar','rho_CO2':'CO2 per g ethanol','k34':'rate multiplier 34 C vs 30 C','k37':'rate multiplier 37 C vs 30 C'}
for n,r in fit.iterrows():
    rows.append(f"| {n} | {meaning[n]} | {f(r.value)} | {r.unit} | {f(r.se_linear_scaled,2)} ({r.rel_se_pct:.1f}%) | {r.lower:g} – {r.upper:g} | {r.start:g} | {r.at_bound} |")
ptab="\n".join(rows)
drow="\n".join(f"| {n} | {f(r.value)} {r.unit} | {f(r.se_linear_scaled,2)} ({r.rel_se_pct:.1f}%) |" for n,r in dv.iterrows())
# per-run diagnostics rms_z
pv=D.pivot(index='run',columns='variable',values='rms_z').round(2)[['X','S','P','C']]
pm=D.pivot(index='run',columns='variable',values='mean_z').round(2)[['X','S','P','C']]
drows="\n".join(f"| {r} | {pv.loc[r,'X']}{' (not fitted)' if r=='R3' else ''} / {pm.loc[r,'X']} | {pv.loc[r,'S']} / {pm.loc[r,'S']} | {pv.loc[r,'P']} / {pm.loc[r,'P']} | {pv.loc[r,'C']} / {pm.loc[r,'C']} |" for r in pv.index)
# heldout
h=H[H.scope=='timecourse_t>0'].set_index('variable'); e=H[H.scope=='endpoint_48h'].set_index('variable')
name={'X':'Biomass (g/L)','S':'TRS (g/L)','P':'Ethanol (g/L)','C':'CO2 (g/L)'}
hrows="\n".join(f"| {name[v]} | {h.loc[v,'rmse']:.2f} | {h.loc[v,'bias']:+.2f} | {h.loc[v,'rel_rmse_pct']:.1f} | {h.loc[v,'mean_z']:+.2f} | {h.loc[v,'rms_z']:.2f} | {h.loc[v,'frac_abs_z_le_2']*100:.0f}% | {int(h.loc[v,'longest_same_sign_run'])} of 13 |" for v in 'XSPC')
erows="\n".join(f"| {name[v]} | {e.loc[v,'observed']:.2f} | {e.loc[v,'predicted']:.2f} | {e.loc[v,'bias']:+.2f} | {e.loc[v,'mean_z']:+.1f} |" for v in 'XSPC')
# sensitivity
order=['mu_max','X_max','q_max','P_max','Y_P','rho_CO2','k34','k37']
cases=['R7_included','R3_biomass_included_sd_x2','Ks_0.2','Ks_5','CO2_floor_0','CO2_floor_0.5']
pc=S.pivot(index='parameter',columns='case',values='change_pct').loc[order,cases]
ps=S.pivot(index='parameter',columns='case',values='change_in_primary_se').loc[order,cases]
srows="\n".join("| "+n+" | "+" | ".join(f"{pc.loc[n,c]:+.1f}% ({ps.loc[n,c]:+.1f})" for c in cases)+" |" for n in order)
sc=S.groupby('case').agg(chi2=('chi2','first'),N=('n_residuals','first'),red=('reduced_chi2','first')).loc[cases]
scrow=" | ".join(f"{sc.loc[c,'red']:.2f}" for c in cases)
# R7 / floor / yields
corr_top="mu_max–q_max −0.73, mu_max–P_max +0.64, q_max–P_max −0.58"
rep=f"""# Level 1 report: kinetic model, fit and held-out prediction

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
m(S)  = S / (Ks + S)                                       Ks fixed = {fx.loc['K_s','value']:g} g/L
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
- **sd (brief s3):** biomass 0.035 x measured + 0.08; TRS 0.01 x measured + 0.4; ethanol 0.012 x measured + 0.25 g/L; CO2 0.02 x measured **+ 0.10 g/L (my documented floor; the brief gives only "about 2%")**. The smallest positive-time CO2 value is {N['min_positive_time_CO2_g_per_L']:.0f} g/L, so no weight is infinite; the floor raises the sd of that point {N['CO2_sd_floor_vs_pure2pct_ratio_at_min_CO2']:.2f}-fold and the median sd {N['CO2_sd_floor_vs_pure2pct_ratio_median']:.2f}-fold.
- **Data in the objective:** {fr['n_residuals']} residuals = 6 training runs x 13 times x (S, P, CO2) + 5 runs x 13 times (biomass; R3 biomass excluded). {fr['n_fitted_params']} fitted parameters, {fr['dof']} degrees of freedom.
- **Solver:** `scipy.integrate.solve_ivp`, LSODA, rtol 1e-9, atol 1e-11. **Optimiser:** `scipy.optimize.least_squares`, trf, bounds, x_scale = jac, diff_step 1e-6, ftol = xtol = gtol = 1e-10, max_nfev 400. **Starts:** the nominal start plus {fr['n_starts']-1} Latin-hypercube starts (seed {fr['seed']}), log-sampled for mu_max and q_max.
- **Failures:** solver failures would be replaced by a residual of 1000 and counted. Counted: **{fr['ode_failures_counted']}**.
- **Convergence:** all {fr['n_starts']} starts ended with status 3 (xtol) and chi-square between {MS.chi2.min():.3f} and {MS.chi2.max():.3f}; {fr['starts_within_0p1pct_of_best']} of {fr['n_starts']} within 0.1% of the best. That indicates one minimum inside these bounds; it does not show the model is right. No fitted parameter sits at a bound.
- **Protocol for R6:** the fit stage reads only the training runs, writes `level1_parameters.csv` and its SHA-256 (`level1_frozen.json`); the predict stage verifies the hash before it loads R6.

## 4. Fitted parameters (training runs R1, R2, R3*, R4, R5, R8)

| Parameter | Meaning | Estimate | Unit | Approx. SE (scaled) | Bounds | Start | At bound |
|---|---|---|---|---|---|---|---|
{ptab}

Fixed: K_s = {fx.loc['K_s','value']:g} g/L, n = {fx.loc['n_inh','value']:g}. Derived effective maxima (delta method):

| Quantity | Value | Approx. SE |
|---|---|---|
{drow}

### Uncertainty and identifiability: what can be said and what cannot
- The SEs are **linearised Gauss-Newton** values at the optimum, scaled by sqrt(chi2/dof) = {np.sqrt(fr['reduced_chi2']):.2f} because the reduced chi-square is {fr['reduced_chi2']:.1f} (chi-square {fr['chi2']:.0f} for {fr['dof']} dof). They measure how tightly the data pin each number **if this structure were correct**; they are **not credible intervals**, they do not include model-structure error, and measurement sds alone clearly understate the real scatter. Profile-likelihood intervals are Level 2 work and were not attempted.
- Numerically the problem is well-conditioned: the relative Jacobian's condition number is {N['relative_jacobian_condition_number']:.0f} and the largest correlations are {corr_top}. No parameter is at a bound.
- **Weakly supported in substance despite small SEs:** k37 (one run, R8); k34 (R4 and R5 only, since R6 is held out and R7 is excluded); P_max (above the highest ethanol observed in training, 107.8 g/L, so it is partly extrapolated; its value of {fit.loc['P_max','value']:.1f} g/L depends on the imposed linear form); X_max (the model plateau is below the data, see section 5); mu_max (growth sampled every 2 h with a large biomass sd). K_s and n are not estimated.
- **CO2 ratio:** rho_CO2 = {fit.loc['rho_CO2','value']:.3f} +/- {fit.loc['rho_CO2','se_linear_scaled']:.3f} against the stoichiometric 0.955, i.e. +3.3% and {N['rho_minus_stoich_in_SE']:.1f} approximate SE above it. Observed 48 h CO2:ethanol ratios of individual runs span 0.938 (R4) to 1.022 (R1). The excess over 0.955 is not explained here (CO2 also arises from biomass formation; dissolved CO2 and by-products are not modelled; the fit is a compromise across runs). Y_P = {fit.loc['Y_P','value']:.3f} g/g is {100*fit.loc['Y_P','value']/0.5114:.1f}% of 0.511; the gap is a Level 2 (carbon balance) question.

## 5. Training fit quality (`level1_fits.png`, `level1_fit_diagnostics.csv`)
rms z / mean z per run (z = (model - data)/sd; |z| around 1 would be consistent with the stated noise):

| Run | Biomass | TRS | Ethanol | CO2 |
|---|---|---|---|---|
{drows}

- Pooled rms z of the training fit: biomass {N['train_pooled_rms_z[X]']:.2f}, TRS {N['train_pooled_rms_z[S]']:.2f}, ethanol {N['train_pooled_rms_z[P]']:.2f}, CO2 {N['train_pooled_rms_z[C]']:.2f}; overall {N['train_overall_rms_z']:.2f}. **The model does not fit within the stated measurement noise.** It reproduces the broad shape of every run (160 g/L runs exhaust sugar near 30 h and plateau near 72 g/L ethanol; the 220-260 g/L runs and R8 slow with sugar left) but with systematic deviations.
- **Biomass plateau is too low:** the model saturates at X_max = {fit.loc['X_max','value']:.2f} g/L whereas the data reach 10-11.5 g/L by 24 h and 10.9-12.3 g/L at 48 h; pooled mean z {N['train_pooled_mean_z[X]']:.2f}. I did not add terms to fix this (instruction D-17). The biomass state therefore works as a catalyst for the fermentation rate rather than as a faithful biomass prediction. I did not test why it settles below the data.
- **TRS** residuals keep one sign for 6-10 consecutive samples in R2, R3, R5 and R8 (late-phase curvature not captured).
- R1 and R4 are near-replicates in kinetics yet end at 71.8 and 74.6 g/L ethanol (both with TRS about 0), a difference of 2.8 g/L, about 1.7 sd of the difference of two measurements with the stated noise. That points to run-to-run yield variation outside the model and the sds (hypothesis).
- R3 biomass (OD600, not fitted) lies above the model in the late phase; no validity is claimed for it either way.

## 6. Held-out prediction of R6 (34 C, 260 g/L), parameters frozen, no refitting (`heldout_prediction.png`, `heldout_metrics.csv`, `heldout_predictions.csv`)

Time-course errors at the 13 positive-time samples (error = prediction - measurement; z uses the measurement sd):

| Variable | RMSE | Bias | RMSE as % of mean | Mean z | rms z | Within 2 sd | Longest same-sign run |
|---|---|---|---|---|---|---|---|
{hrows}

At 48 h:

| Variable | Measured | Predicted | Error | z |
|---|---|---|---|---|
{erows}

**Reading of the result (observations first, then hypotheses):**
- *Ethanol* is predicted to within 1.7 g/L (1.7%) at 48 h, but is over-predicted at 12-30 h by up to {HP[(HP.variable=='P')].error.max():.1f} g/L and the ethanol errors exceed 2 sd at 7 of 13 samples (TRS 9 of 13, CO2 9 of 13, biomass 6 of 13).
- *TRS is the poorest-predicted variable:* the model predicts less residual sugar than measured at every sample from 8 h onward (48 h: {e.loc['S','predicted']:.1f} vs {e.loc['S','observed']:.1f} g/L, an error of {e.loc['S','bias']:+.1f} g/L). Relative to the plant's 5 g/L end-of-batch limit this is a large error, although it does not by itself say anything about 33-36 C.
- *CO2* is over-predicted from 12 h onward by an amount that grows from +2.1 to +6.4 g/L (2.96-3.7 sd at every sample from 12 h); R6's measured CO2:ethanol ratio is {N['obs_CO2_over_ethanol_48h[R6]']:.3f} against the fitted rho_CO2 of {fit.loc['rho_CO2','value']:.3f}.
- *Biomass* plateau is under-predicted ({e.loc['X','bias']:+.2f} g/L at 48 h), as in training.
- **Comparison with training:** the R6 rms z ({N['R6_rms_z[X]']:.2f} biomass, {N['R6_rms_z[S]']:.2f} TRS, {N['R6_rms_z[P]']:.2f} ethanol, {N['R6_rms_z[C]']:.2f} CO2) is similar to the in-sample misfit ({N['train_pooled_rms_z[X]']:.2f}, {N['train_pooled_rms_z[S]']:.2f}, {N['train_pooled_rms_z[P]']:.2f}, {N['train_pooled_rms_z[C]']:.2f}), so structural misfit rather than overfitting dominates. The exception is the TRS bias (mean z {N['R6_mean_z[S]']:.1f} for R6 against {N['train_pooled_mean_z[S]']:.1f} pooled in training), which is a systematic prediction error.
- **Sugar-error arithmetic (hand calculation from the tables):** R6's measured ethanol per g TRS dropped (nominal S0) is {N['obs_ethanol_per_TRS_dropped_nominalS0[R6]']:.3f}, above every training run ({min(N[f'obs_ethanol_per_TRS_dropped_nominalS0[{r}]'] for r in ['R1','R2','R3','R4','R5','R8']):.3f}-{max(N[f'obs_ethanol_per_TRS_dropped_nominalS0[{r}]'] for r in ['R1','R2','R3','R4','R5','R8']):.3f}); the model's value is {N['pred_R6_ethanol_per_TRS_dropped']:.3f}. At R6's own yield the predicted ethanol would need about 214.9 g/L of sugar rather than 221.3, so roughly 6 of the 10 g/L TRS error comes from yield and about 4 g/L from the 1.7 g/L ethanol over-prediction.
- **Hypotheses (not tested, R6 not used to choose among them):** (i) ethanol tolerance falls with temperature, i.e. the P_max(T) the user excluded from this model; the Phase 0 raw data (stronger stall in R6 than in R3) pointed this way, and the sign of the R6 error is compatible with it; (ii) run-to-run yield variation of the kind seen between R1 and R4; (iii) a different yield at 260 g/L. One held-out run cannot separate these.
- **Limits of this test:** it is one run, at one condition, with the model structure chosen before R6 was predicted and the large in-sample misfit shown above. **It does not show that the model generalises across operating conditions**, and the 33 and 36 C scenarios and 37 C with 260 g/L would need interpolation or extrapolation that the fitted multipliers do not support (k is defined only at 30, 34 and 37 C).

## 7. Sensitivity analyses (predeclared, run only after the primary fit and the R6 prediction; R6 not used; no R6 metrics computed for them; nothing selected from them)
Change in the fitted value relative to the primary fit, in % (and in primary linearised SE units):

| Parameter | R7 included | R3 biomass incl. (sd x2) | K_s = 0.2 | K_s = 5 | CO2 floor 0 | CO2 floor 0.5 |
|---|---|---|---|---|---|---|
{srows}
| reduced chi-square | {scrow} |

- **R7 included:** reduced chi-square rises from {fr['reduced_chi2']:.1f} to {sc.loc['R7_included','red']:.1f}. The estimates move by at most about 10% (mu_max +10.1%, k34 -5.6%, Y_P -1.7%). In SE units k34 (-6.5), P_max (-2.1) and Y_P (-1.9) move most, but because the SEs are small relative to the misfit, SE units overstate the importance; I regard the k34 shift (the 34 C multiplier falls from {fit.loc['k34','value']:.3f} to about 0.917) as the one change that could matter for a 33-36 C recommendation. This is consistent with R7 being slower than R5, but that is not evidence about why.
- **R3 biomass included:** no material change (largest shift 3.3%).
- **K_s:** shifts of at most about 6% (mu_max) over 0.2-5 g/L; K_s does not change the picture.
- **CO2 floor:** removing the floor shifts mu_max by -13.9% and q_max by +7.1% (about 2.4-2.7 SE); a floor of 0.5 g/L shifts them by at most 4.4%. The early, small CO2 values therefore carry some weight in the growth-rate estimate, and the floor is a real, documented assumption.

## 8. Limitations and unresolved issues
1. The model does not reproduce the data within the stated noise (reduced chi-square {fr['reduced_chi2']:.1f}); the biomass plateau is too low and late-phase TRS curvature is systematically mismatched. Structure changes were not made after seeing the training fit (instructions) and none were made after seeing R6.
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
"""
open(OUT,'w').write(rep)
print(len(rep))
