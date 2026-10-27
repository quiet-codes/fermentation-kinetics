"""Generates reports/level2.md from the output tables (run from the project root after the Level 2 stages have produced them).
Usage: python src/make_level2_report.py [output_path]   (default: reports/level2.md)
Every number in the report is read from outputs/tables/*.csv or *.json; hand-typed numbers in the text are checked by tests/test_report_claims.py."""
import sys
OUT = sys.argv[1] if len(sys.argv) > 1 else 'reports/level2.md'
import json, numpy as np, pandas as pd
T='outputs/tables/'
cmp=pd.read_csv(T+'model_comparison.csv').set_index('model'); fz=json.load(open(T+'model_selection_frozen.json')); r6=pd.read_csv(T+'model_r6_diagnostic.csv').set_index('model')
U=pd.read_csv(T+'parameter_uncertainty.csv'); FX=pd.read_csv(T+'fixed_parameter_sensitivity.csv'); R7=pd.read_csv(T+'r7_inclusion_effect.csv')
CB=pd.read_csv(T+'carbon_balance_all_runs.csv').set_index('run'); YL=pd.read_csv(T+'ethanol_yields.csv').set_index('run'); DEC=pd.read_csv(T+'yield_gap_decomposition.csv').set_index('run')
PO=pd.read_csv(T+'ethanol_yield_pooled.csv').set_index('set'); RV=pd.read_csv(T+'r7_review.csv').set_index('quantity')
PU=pd.read_csv(T+'plant_prediction_uncertainty.csv'); SP=pd.read_csv(T+'structure_spread.csv'); KS=pd.read_csv(T+'plant_Ks_sensitivity.csv'); VD=pd.read_csv(T+'variance_decomposition.csv')
ED=pd.read_csv(T+'experiment_design.csv'); DS=pd.read_csv(T+'experiment_discrimination.csv'); LS=pd.read_csv(T+'plant_linearised_sd.csv'); CP=pd.read_csv(T+'candidate_parameters.csv')
loro=pd.concat([pd.DataFrame(json.load(open(T+f'work/loro_{m}.json'))).assign(model=m) for m in cmp.index]); LP=loro.pivot(index='model',columns='held_out_run',values='chi2_per_point')
pref=fz['preferred']; chat=fz['c_hat']
f=lambda x,n=3: f"{x:.{n}g}"
# --- model comparison table
desc={'M0':'Level 1 baseline (linear inhibition, one P_max, k34 and k37 free)','M1':'M0 with k34 = 1','M2':'M0 + P_max(T) = P30 exp(-beta (T-30))','M3':'M0 + estimated exponent n','M4':'M0 with the ethanol factor also on growth','M5':'P_max(T) + estimated n','M6':'P_max(T) + ethanol factor on growth'}
rows=[]
for m,r in cmp.iterrows():
    flag=' (n at bound 4.0: excluded by D-24)' if r.params_at_bound>0 else ''
    rows.append(f"| {m} | {desc[m]}{flag} | {int(r.k_params)} | {r.chi2:.0f} | {r.reduced_chi2:.2f} | {r.QAICc:.1f} | {r.delta_QAICc:.1f} | {r.rms_z_X:.2f} / {r.rms_z_S:.2f} / {r.rms_z_P:.2f} / {r.rms_z_C:.2f} | {r.mean_lag1_autocorr:.2f} | {LP.loc[m].drop('R8').mean():.1f} | {LP.loc[m,'R8']:.0f} |")
cmp_tab="\n".join(rows)
r6rows="\n".join(f"| {m} | {r.rms_z_X:.2f} / {r.rms_z_S:.2f} / {r.rms_z_P:.2f} / {r.rms_z_C:.2f} | {r.TRS_48h_pred:.1f} | {r.EtOH_48h_pred:.1f} |" for m,r in r6.iterrows())
lorotab="\n".join(f"| {m} | "+" | ".join(f"{LP.loc[m,c]:.1f}" for c in ['R1','R2','R3','R4','R5','R8'])+" |" for m in cmp.index)
# --- parameter tables
def ptable(model):
    d=U[(U.model==model)&(U.status=='fitted')]; out=[]
    for _,r in d.iterrows():
        lo=f"{r.ci_lo:.4g}" if not r.ci_open_lo else f"open (to {r.ci_lo_if_open_searched_to:.3g})"; hi=f"{r.ci_hi:.4g}" if not r.ci_open_hi else f"open (to {r.ci_hi_if_open_searched_to:.3g})"
        out.append(f"| {r.parameter} | {r.unit} | {r.value:.4g} | [{lo}, {hi}] | [{r.ci_nominal_lo:.4g}, {r.ci_nominal_hi:.4g}] | [{r.linear_ci95_lo:.4g}, {r.linear_ci95_hi:.4g}] | {r.jackknife_min:.4g} – {r.jackknife_max:.4g} | {r.identifiability} | {r.correlated_with} |")
    return "\n".join(out)
fixed_tab=[]
m5=FX[FX.model==pref]; ks=m5[m5.fixed_parameter=='K_s'].set_index('value'); kmin=ks.chi2.min()
for v,r in ks.iterrows(): fixed_tab.append(f"| {pref} | K_s = {v:g} g/L | {r.chi2:.0f} | {(r.chi2-kmin)/chat:+.1f} | {r.P_max:.0f} | {r.k37:.3f} |")
m0n=FX[(FX.model=='M0')&(FX.fixed_parameter=='n_inh')].set_index('value'); m0min=m0n.chi2.min()
for v,r in m0n.iterrows(): fixed_tab.append(f"| M0 | n = {v:g} (fixed) | {r.chi2:.0f} | {(r.chi2-m0min)/cmp.loc['M0','reduced_chi2']:+.1f} | {r.P_max:.0f} | {r.k37:.3f} |")
fixed_tab="\n".join(fixed_tab)
r7tab=[]
for m in (pref,'M0'):
    d=R7[R7.model==m].set_index('parameter')
    r7tab.append(f"| {m} | {d.reduced_chi2_primary.iloc[0]:.2f} → {d.reduced_chi2_with_R7.iloc[0]:.2f} | "+"; ".join(f"{p} {d.loc[p,'change_pct']:+.1f}%" for p in d.index if abs(d.loc[p,'change_over_profile_halfwidth'])>=1 or abs(d.loc[p,'change_pct'])>=10)+" | "+", ".join(f"{p} ({d.loc[p,'change_over_profile_halfwidth']:+.1f})" for p in d.index if abs(d.loc[p,'change_over_profile_halfwidth'])>=2)+" |")
r7tab="\n".join(r7tab)
# --- carbon table
cbrows="\n".join(f"| {r} | {x.C_in_total_Cmol_L:.3f} | {x.C_out_total_Cmol_L:.3f} | {x.unaccounted_Cmol_L:+.3f} ({x.unaccounted_pct_of_input:+.1f}%) | {x.recovery_pct:.1f} | [{x.recovery_95_lo:.1f}, {x.recovery_95_hi:.1f}] | {x.recovery_consumed_basis_pct:.1f} | {'yes' if x.closes_within_95 else 'NO'} | {x.in_primary_fit} |" for r,x in CB.iterrows())
comptab="\n".join(f"| {r} | {x.C_in_sugar_Cmol_L:.3f} | {x.C_in_inoculum_Cmol_L:.3f} | {x.C_out_residual_sugar:.3f} | {x.C_out_biomass:.3f} | {x.C_out_ethanol:.3f} | {x.C_out_CO2:.3f} | {x.C_out_glycerol:.3f} | {x.C_out_lactic:.4f} |" for r,x in CB.iterrows())
senstab="\n".join(f"| {r} | {x.recovery_pct:.1f} | {x.recovery_pct_nominal_S0:.1f} | {x.recovery_pct_measured_X0:.1f} | {x.recovery_pct_lactic_nd_as_0:.1f} / {x.recovery_pct_lactic_nd_as_0p2:.1f} |" for r,x in CB.iterrows())
ytab="\n".join(f"| {r} | {x.TRS_consumed_g_L:.1f} | {x.ethanol_g_L:.1f} | {x.yield_g_per_g:.4f} | [{x.yield_95_lo:.3f}, {x.yield_95_hi:.3f}] | {x.yield_pct_of_theory:.1f} | {x.yield_nominalS0:.4f} | {x.yield_catabolic_after_biomass_sugar:.3f} |" for r,x in YL.iterrows())
dtab="\n".join(f"| {r} | {x.gap_pct_of_consumed_carbon:.1f} | {x.biomass_pct_pts:.1f} [{x.biomass_95_lo:.1f}, {x.biomass_95_hi:.1f}] | {x.glycerol_pct_pts:.1f} | {x.lactic_pct_pts:.2f} | {x.excess_CO2_pct_pts:+.1f} [{x.excess_CO2_95_lo:+.1f}, {x.excess_CO2_95_hi:+.1f}] | {x.unaccounted_pct_pts:+.1f} [{x.unaccounted_95_lo:+.1f}, {x.unaccounted_95_hi:+.1f}] |" for r,x in DEC.iterrows())
pooltab="\n".join(f"| {k} | {x.pooled_yield_sum_ratio:.4f} | {x.pct_of_theory:.1f} | "+(f"[{x.bootstrap_95_lo:.3f}, {x.bootstrap_95_hi:.3f}]" if np.isfinite(x.bootstrap_95_lo) else "n/a (one run)")+" |" for k,x in PO.iterrows())
mean_dec=DEC[['biomass_pct_pts','glycerol_pct_pts','lactic_pct_pts','excess_CO2_pct_pts','unaccounted_pct_pts','gap_pct_of_consumed_carbon']].mean()
rvtab="\n".join(f"| {q} | {x.R7:.3g} | {x.R5:.3g} | {('' if not np.isfinite(x.z) else f'{x.z:+.1f}')} | {x.unit} |" for q,x in RV.iterrows())
# --- plant
def pu(model,T,S0,key,col): 
    r=PU[(PU.model==model)&(PU['T_C']==T)&(PU.S0_gL==S0)&(PU.quantity==key)].iloc[0]; return r[col]
scen=[(33.0,220.0),(34.0,260.0),(36.0,260.0),(37.0,260.0)]
ptab=[]
for T,S0 in scen:
    ptab.append(f"| {int(T)} C / {int(S0)} | {pu(pref,T,S0,'P48','point_estimate'):.1f} [{pu(pref,T,S0,'P48','ens_95_lo'):.1f}, {pu(pref,T,S0,'P48','ens_95_hi'):.1f}] | {pu(pref,T,S0,'S48','point_estimate'):.1f} [{pu(pref,T,S0,'S48','ens_95_lo'):.1f}, {pu(pref,T,S0,'S48','ens_95_hi'):.1f}] | {pu(pref,T,S0,'S96','point_estimate'):.1f} [{pu(pref,T,S0,'S96','ens_95_lo'):.1f}, {pu(pref,T,S0,'S96','ens_95_hi'):.1f}] | "
      +(f"{pu(pref,T,S0,'t_end','point_estimate'):.0f} h [{pu(pref,T,S0,'t_end','ens_95_lo'):.0f}, {pu(pref,T,S0,'t_end','ens_95_hi'):.0f}]; margin {pu(pref,T,S0,'daily_margin_Rs','point_estimate')/1000:.1f}k [{pu(pref,T,S0,'daily_margin_Rs','ens_95_lo')/1000:.1f}k, {pu(pref,T,S0,'daily_margin_Rs','ens_95_hi')/1000:.1f}k]" if np.isfinite(pu(pref,T,S0,'t_end','point_estimate')) else "not reached in 120 h; no margin") + " |")
ptab="\n".join(ptab)
sp=SP[~SP.model.str.contains('refit')]
sptab="\n".join(f"| {m} | "+" | ".join((f"{d[(d['T_C']==T)&(d.S0_gL==S0)].S96.iloc[0]:.0f} / "+(f"{d[(d['T_C']==T)&(d.S0_gL==S0)].t_end.iloc[0]:.0f} h / {d[(d['T_C']==T)&(d.S0_gL==S0)].daily_margin_Rs.iloc[0]/1000:.0f}k" if np.isfinite(d[(d['T_C']==T)&(d.S0_gL==S0)].t_end.iloc[0]) else "never / –")) for T,S0 in scen)+" |" for m,d in sp.groupby('model'))
ks_tab="\n".join(f"| {r.K_s:g} | {r.chi2:.0f} | "+(f"{r.t_end:.1f} h / {r.daily_margin_Rs/1000:.1f}k" if np.isfinite(r.t_end) else "–")+f" | {r.S96:.1f} |" for _,r in KS[(KS['T_C']==33.0)].iterrows())
r6ref=SP[SP.model.str.contains('refit')]
grp={'ethanol-inhibition shape (P_max, n)':['P_max','n_inh'],'temperature (beta_P, k34, k37)':['beta_P','k34','k37'],'yield (Y_P, rho_CO2)':['Y_P','rho_CO2'],'growth and uptake (mu_max, X_max, q_max)':['mu_max','X_max','q_max']}
g=VD.copy(); g['group']=g.parameter.map({p:k for k,v in grp.items() for p in v})
gt=g.groupby(['quantity','T_C','S0_gL','group']).variance_share_pct.sum().reset_index()
def gshare(q,T,S0): 
    d=gt[(gt.quantity==q)&(gt['T_C']==T)&(gt.S0_gL==S0)].set_index('group').variance_share_pct; return d
vtab=[]
for (q,T,S0,lab) in [('daily_margin_Rs',33.0,220.0,'margin 33 C/220'),('daily_margin_Rs',34.0,260.0,'margin 34 C/260'),('S96',36.0,260.0,'TRS(96 h) 36 C/260'),('S96',37.0,260.0,'TRS(96 h) 37 C/260')]:
    d=gshare(q,T,S0); vtab.append(f"| {lab} | "+" | ".join(f"{d.get(k,0):.0f}%" for k in grp)+" |")
vtab="\n".join(vtab)
edtab="\n".join(f"| {int(r['T_C'])} C / {int(r.S0_gL)} / {int(r.horizon_h)} h | {r.mean_margin_sd_reduction_pct:.0f}% | {r.margin_sd_reduction_pct_34C_260:.0f}% | {r.TRS96_sd_reduction_pct_36C_260:.0f}% | {r.TRS96_sd_reduction_pct_37C_260:.0f}% | {DS[(DS['T_C']==r['T_C'])&(DS.S0_gL==r.S0_gL)&(DS.horizon_h==r.horizon_h)].sep_M5_M2.iloc[0]:.0f} |" for _,r in pd.concat([ED[(ED.horizon_h==96)].head(5),ED[(ED['T_C']==34)&(ED.S0_gL==260)&(ED.horizon_h==48)]]).iterrows())
lin=LS.set_index(['T_C','S0_gL','quantity'])
u5=U[(U.model==pref)&(U.status=='fitted')].set_index('parameter'); u0=U[(U.model=='M0')&(U.status=='fitted')].set_index('parameter')
aut=cmp.mean_lag1_autocorr
kk=ks; dks02=(ks.loc[0.2,'chi2']-kmin)/chat; dks1=(ks.loc[1.0,'chi2']-kmin)/chat; dks5=(ks.loc[5.0,'chi2']-kmin)/chat
rec_mean=CB.recovery_pct.mean(); rec_no4=CB.drop('R4').recovery_pct.mean()
y_all=PO.loc['all 8 runs']; y_7=PO.loc['7 runs (R7 excluded)']
charged_basis=y_all.pooled_yield_sum_ratio*1.0368
rep=f"""# Level 2 report: model comparison, parameter uncertainty, carbon balance, ethanol yield and plant-relevant uncertainty

**Scope:** Level 2 only. No plant optimisation (Level 3): the brief's margin formula is evaluated at four fixed scenarios purely to propagate uncertainty, and nothing is recommended.
**Preserved:** raw CSVs, Phase 0 files and all Level 1 files (`kinetics.py`, `fit.py`, `level1_*`, `heldout_*`, `reports/level1.md`) are unchanged; the Level 1 baseline is candidate M0 and is reproduced exactly (max difference 0.0 in simulated states).
**Status of R6:** R6 was inspected in Level 1 and its Level 1 prediction is on file, so it is **not blind**. It was never used to develop, choose or tune a model. The selection was frozen (SHA-256 in `model_selection_frozen.json`) before the R6 diagnostic for the candidates was computed (`model_r6_diagnostic.csv`). R6 appears in two places only: (a) that labelled out-of-fit diagnostic and (b) one labelled secondary refit of the chosen model in `structure_spread.csv`.
**What was actually executed (AI sandbox, Python 3.12.3, numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, matplotlib 3.10.8, one CPU core):** `compare.py` (fit, loro, select, r6diag), `uncertainty.py` (r7, fixedgrid, profile, assemble), `plant_uncertainty.py` (predict, design, ksens, discriminate, plot), `carbon_balance.py`; `tests/test_level2.py` 15 passed / 0 failed / 0 skipped, `tests/test_model.py` 16 passed / 0 failed / 0 skipped and `tests/test_report_claims.py` 11 passed / 0 failed (it checks the numbers typed into this report and into the Level 1 report against the raw CSVs and tables, and that each report equals the output of its generator), all through the fallback runner because **pytest is not installed in the sandbox**; the six Phase 0 tests (`tests/test_phase0.py`) also passed (74 PASS / 58 INFO / 5 FLAG) when run through a minimal stand-in for pytest's `fixture` and `approx`. **Not executed:** pytest itself, anything on your machine. Your local Phase 0 and Level 1 results were never supplied.

---

## 0. Findings in brief
1. **Structure matters more than parameter precision.** Adding a temperature-dependent ethanol limit P_max(T) cuts the training chi-square from {cmp.loc['M0','chi2']:.0f} (Level 1 baseline) to {cmp.loc['M2','chi2']:.0f} (M2, one extra parameter); also estimating the inhibition exponent (M5) gives {cmp.loc['M5','chi2']:.0f} (reduced chi-square {cmp.loc['M0','reduced_chi2']:.1f} → {cmp.loc['M5','reduced_chi2']:.1f}). By the rule fixed in advance (D-24) **M5 is preferred**. It still does not fit within the stated noise, and it **fails badly when the only 37 C run is left out** (leave-one-run-out chi-square per point {LP.loc['M5','R8']:.0f}), so its 37 C behaviour rests on R8 alone.
2. **The linear ethanol-inhibition form (n = 1) used in Level 1 is not supported**: fixing n = 3 instead lowers the baseline chi-square by {m0n.loc[1.0,'chi2']-m0n.loc[3.0,'chi2']:.0f}; M5 estimates n = {u5.loc['n_inh','value']:.2f} (profile 95% [{u5.loc['n_inh','ci_lo']:.2f}, {u5.loc['n_inh','ci_hi']:.2f}]). **P_max and n are not separable** (linearised correlation +0.98, a ridge); only their combination is determined, and P_max = {u5.loc['P_max','value']:.0f} g/L lies well above any ethanol observed (maximum 107.8 g/L).
3. **K_s = 1 g/L was not harmless:** with the rest re-optimised, chi-square falls monotonically as K_s decreases to 0.05 g/L (scaled change {dks1:+.0f} at K_s = 1, {dks5:+.0f} at 5 g/L). The data favour a very sharp sugar cutoff (K_s = 0.2 g/L is already above the 95% threshold relative to 0.05 g/L; the lower end is unbounded and sits below the 0.4 g/L TRS measurement floor); the effect on the plant-relevant predictions is small (1-4%) for K_s up to 5 g/L.
4. **Carbon closes for all eight runs within measurement uncertainty except R4** (recovery {CB.loc['R4','recovery_pct']:.1f}%, Monte-Carlo 95% [{CB.loc['R4','recovery_95_lo']:.1f}, {CB.loc['R4','recovery_95_hi']:.1f}]%). Mean recovery {rec_mean:.1f}% ({rec_no4:.1f}% without R4).
5. **Overall ethanol yield {y_all.pooled_yield_sum_ratio:.3f} g ethanol per g TRS consumed (glucose-equivalent basis; run-bootstrap 95% [{y_all.bootstrap_95_lo:.3f}, {y_all.bootstrap_95_hi:.3f}]) = {y_all.pct_of_theory:.1f}% of 0.511.** The {100-y_all.pct_of_theory:.1f}% gap is accounted for by biomass ({mean_dec.biomass_pct_pts:.1f} points of consumed sugar carbon) and glycerol ({mean_dec.glycerol_pct_pts:.1f}), plus lactic acid in R7 ({DEC.loc['R7','lactic_pct_pts']:.1f}); the residual "unaccounted" term averages {mean_dec.unaccounted_pct_pts:+.1f} points, i.e. no unmeasured carbon sink is needed (if anything the output slightly exceeds the measured input).
6. **R7 is an unusual run** (lactic acid {RV.loc['lactic acid (n.d. = 0.1 +/- 0.058)','R7']:.1f} g/L, pH {RV.loc['final pH','R7']:.2f} against {RV.loc['final pH','R5']:.2f} in its repeat R5). Counting lactic acid, its carbon closes ({CB.loc['R7','recovery_pct']:.1f}%); leaving it out gives {CB.loc['R7','recovery_pct_lactic_removed']:.1f}%. Including R7 raises the reduced chi-square of M5 from {R7[R7.model==pref].reduced_chi2_primary.iloc[0]:.1f} to {R7[R7.model==pref].reduced_chi2_with_R7.iloc[0]:.1f}, while no parameter moves by more than {R7[R7.model==pref].change_pct.abs().max():.0f}%.
7. **For the plant, the unresolved quantity is the sugar tail at high ethanol and temperature.** At 37 C / 260 g/L the preferred model predicts {pu(pref,37.0,260.0,'P48','point_estimate'):.0f} g/L ethanol and {pu(pref,37.0,260.0,'S48','point_estimate'):.0f} g/L TRS at 48 h and {pu(pref,37.0,260.0,'S96','point_estimate'):.0f} g/L TRS at 96 h; the 5 g/L end-of-batch condition is not reached within 120 h in M5 (and in most other structures), but one candidate (M3, disqualified) reaches it at 94 h. That is a disagreement between structures, not a parameter interval.
8. **Most useful single additional experiment:** one 96-hour batch at 34 C and 260 g/L TRS (R6's conditions run to 96 h), with dry-weight biomass and endpoint HPLC (section 6.4).

## 1. Task 1: model structures

### 1.1 Candidates and why (training runs only, D-23)
Developed from R1, R2, R3 (no biomass), R4, R5 and R8 only. The training evidence behind the temperature-dependent ethanol limit: early ethanol rates are equal at 30 and 34 C (2.84 vs 2.88 g/L/h at 160 g/L; 2.53 vs 2.58 at 220 g/L) but, at similar ethanol and sugar, R5 (34 C) produces ethanol 22% more slowly than R3 (30 C) over 24-36 h (1.71 vs 2.18 g/L/h), and R8 (37 C) slows at only 66-80 g/L ethanol. M1 tests whether k34 can be dropped (k34 was 0.97 in Level 1). M3 and M5 ask whether the inhibition exponent should be estimated (Level 1 noted a fixed n = 1 was an imposed simplification). M4 and M6 apply the same ethanol factor to growth with no extra parameter. **Nothing was added to repair the Level 1 biomass plateau specifically**, and terms for viability loss, nutrient limitation, substrate inhibition and maintenance were not tested because the data contain no direct observation of them.

| Model | Description | k | chi-square | reduced | QAICc | Δ QAICc | rms z (X / S / P / C) | mean lag-1 residual autocorr. | LORO mean chi2/pt, excl. R8 | LORO chi2/pt, R8 fold |
|---|---|---|---|---|---|---|---|---|---|---|
{cmp_tab}

Training data: 299 residuals (R3 biomass excluded). QAICc = chi-square / c_hat + 2k + 2k(k+1)/(N-k-1) with c_hat = {chat:.2f} (reduced chi-square of the most complex candidate, M5; D-24). All seven candidates converged to a single minimum from all 8 starts and had 0 solver failures.

Leave-one-run-out chi-square per point (training runs only; the held-out run is predicted from a refit on the other five):

| Model | R1 | R2 | R3 | R4 | R5 | R8 |
|---|---|---|---|---|---|---|
{lorotab}

### 1.2 Selection (rule fixed before computing)
Rule D-24: lowest QAICc among candidates with no parameter at a bound; prefer a simpler candidate within 4 QAICc units. **Result: {pref}.** M3 has n at its bound of 4.0 and is excluded; the next best, M6, is {cmp.loc['M6','delta_QAICc']:.0f} QAICc units behind, so no simpler model qualified.

### 1.3 What supports it, and how far
- **Fit and residuals:** M5 removes most of the Level 1 structural misfit (chi-square {cmp.loc['M0','chi2']:.0f} → {cmp.loc['M5','chi2']:.0f}); its biomass plateau is {CP[(CP.model=='M5')&(CP.parameter=='X_max')].value.iloc[0]:.1f} g/L, matching the data (Level 1: 9.3), and its mean z is between −0.6 and −0.1 in all four variables. It still does not fit within the stated noise (reduced chi-square {cmp.loc['M5','reduced_chi2']:.1f}; rms z {cmp.loc['M5','rms_z_X']:.1f}-{cmp.loc['M5','rms_z_S']:.1f}).
- **Residuals are strongly autocorrelated** (mean lag-1 coefficient {aut.min():.2f}-{aut.max():.2f} for all candidates), so the chi-square and QAICc assumptions of independent errors with known sds are not met. If the effective sample size were a third of 299, the QAICc gaps would shrink about threefold (M5 vs M2: 144 → about 48), still well above 4. So in-sample, M5 is distinguishable from M2 and M6, and all three from M0/M1/M4. I treat the size of the gaps as indicative only.
- **Out-of-sample within the training runs** the picture is mixed: M5 has the lowest chi2/pt of all seven candidates in 3 of the 5 folds that leave R8 in (R2, R4, R5; R1 is best for M3 and R3 for M6) and the lowest mean (mean {LP.loc['M5'].drop('R8').mean():.1f} vs {LP.loc['M2'].drop('R8').mean():.1f} for M2 and {LP.loc['M6'].drop('R8').mean():.1f} for M6), **but with R8 removed it extrapolates to 37 C catastrophically** (chi2/pt {LP.loc['M5','R8']:.0f}; M2 {LP.loc['M2','R8']:.0f}, M6 {LP.loc['M6','R8']:.0f}). With three temperature levels and one run at 37 C, the exponent n and the temperature slope of P_max cannot be validated at 37 C. M2 and M6 are the safer alternatives; M2 and M6 cannot be told apart by any plausible experiment (their predictions differ by at most about {DS.sep_M2_M6.max():.0f} chi-square units over a 96 h run, section 6.4).
- **Out-of-fit diagnostic on R6 (not used for selection, D-22):** all candidates fail to predict R6 within the noise.

| Model | R6 rms z (X / S / P / C) | TRS at 48 h, predicted (measured 48.7) | Ethanol at 48 h, predicted (measured 100.1) |
|---|---|---|---|
{r6rows}

  Compared with M0 (TRS error −10.0 g/L), M5 reduces the 48 h TRS error to {r6.loc['M5','TRS_48h_pred']-48.7:+.1f} g/L, but its ethanol and CO2 rms z ({r6.loc['M5','rms_z_P']:.2f}, {r6.loc['M5','rms_z_C']:.2f}) are not better than M0's ({r6.loc['M0','rms_z_P']:.2f}, {r6.loc['M0','rms_z_C']:.2f}). Nothing here was used to choose; the labelled diagnostic should not be read as confirmation.
- **Are the candidates distinguishable with eight runs?** M0/M1/M4 versus M2/M5/M6, yes (large gaps that survive an autocorrelation discount). M5 versus M2/M6, only at the cost of two extra parameters whose individual values are a ridge and whose 37 C behaviour cannot be validated. M2 versus M6, no.

## 2. Task 2: parameter uncertainty and identifiability (preferred model {pref}; baseline M0 for comparison)

**Method (D-25).** Point estimates: weighted least squares, multistart, training runs only. Intervals: profile likelihood re-optimising all other parameters, with the 95% threshold at chi-square_min + c_hat × 3.84 (c_hat = {chat:.2f} for M5, {cmp.loc['M0','reduced_chi2']:.2f} for M0) because the fits are far from chi-square ≈ dof. The unscaled interval (valid only if the stated sds were exact) is shown for reference. Jackknife = refits with each training run left out in turn (6 refits; run-to-run stability; k37 cannot be estimated when R8 is dropped). Profile intervals that do not close inside the parameter bounds would be reported as open; none was open here.

**Are the Level 1 local (covariance) estimates trustworthy?** Partly. Within M5 the linearised 95% intervals and the profile intervals are close (for example n: linearised [{u5.loc['n_inh','linear_ci95_lo']:.2f}, {u5.loc['n_inh','linear_ci95_hi']:.2f}], profile [{u5.loc['n_inh','ci_lo']:.2f}, {u5.loc['n_inh','ci_hi']:.2f}]; P_max: [{u5.loc['P_max','linear_ci95_lo']:.0f}, {u5.loc['P_max','linear_ci95_hi']:.0f}] vs [{u5.loc['P_max','ci_lo']:.0f}, {u5.loc['P_max','ci_hi']:.0f}]), so the local approximation is acceptable *given the structure*. They are not trustworthy as statements about the real system, because (i) they are conditional on a structure that still misfits and whose alternatives give non-overlapping intervals (M0 k34 [{u0.loc['k34','ci_lo']:.3f}, {u0.loc['k34','ci_hi']:.3f}] vs M5 [{u5.loc['k34','ci_lo']:.3f}, {u5.loc['k34','ci_hi']:.3f}]), (ii) the stated sds understate scatter and the errors are autocorrelated, and (iii) the jackknife range, which reflects run-to-run variation, is wider than the profile interval for several parameters (below). A defensible overall uncertainty is at least the wider of the two.

### 2.1 Fitted parameters of {pref} (units in column 2)

| Parameter | Unit | Estimate | Profile 95% (scaled by c_hat) | Profile 95% (sds exact) | Linearised 95% | Jackknife range (leave-one-run-out) | Identifiability | Correlated (|r| ≥ 0.7, linearised) |
|---|---|---|---|---|---|---|---|---|
{ptable(pref)}

### 2.2 Level 1 baseline M0 (for comparison)

| Parameter | Unit | Estimate | Profile 95% (scaled by c_hat) | Profile 95% (sds exact) | Linearised 95% | Jackknife range | Identifiability | Correlated |
|---|---|---|---|---|---|---|---|---|
{ptable('M0')}

Identifiability labels are rule-based (`uncertainty.py: classify`): "determined" = closed interval, relative width ≤ 40%, run-to-run (jackknife) spread no larger than the interval; "partly determined" = closed but the leave-one-run-out spread exceeds the within-fit interval; "determined only jointly" = |r| ≥ 0.9 with another parameter; k37 is flagged separately because it rests on one run.

### 2.3 Reading the table honestly
- **Best determined (within this structure):** X_max, Y_P and rho_CO2 (relative profile half-widths ≈ {100*(u5.loc['X_max','ci_hi']-u5.loc['X_max','ci_lo'])/2/u5.loc['X_max','value']:.0f}%, {100*(u5.loc['Y_P','ci_hi']-u5.loc['Y_P','ci_lo'])/2/u5.loc['Y_P','value']:.1f}% and {100*(u5.loc['rho_CO2','ci_hi']-u5.loc['rho_CO2','ci_lo'])/2/u5.loc['rho_CO2','value']:.1f}%).
- **rho_CO2** is {u5.loc['rho_CO2','value']:.3f} [{u5.loc['rho_CO2','ci_lo']:.3f}, {u5.loc['rho_CO2','ci_hi']:.3f}]; the stoichiometric 0.955 is **outside** the interval, about {100*(u5.loc['rho_CO2','value']/0.9553-1):.1f}% higher. The carbon balance gives a compatible amount of CO2 beyond the 1:1 pairing with ethanol ({mean_dec.excess_CO2_pct_pts:+.1f} points of consumed carbon on average, with intervals that include zero for six runs). Extra CO2 from biomass synthesis is a plausible explanation but is not tested.
- **P_max and n (ethanol-inhibition shape):** correlation +0.98; the profile intervals are closed but P_max and n trade off along a ridge. The data determine the *combination* of inhibition strength over the observed ethanol range (up to 108 g/L). P_max is an extrapolated scale (≈ {u5.loc['P_max','value']/107.8:.1f} × the highest observed ethanol) and should not be quoted as a physical ethanol tolerance.
- **Temperature parameters (k34, k37, beta_P):** within-fit intervals are narrow, but the jackknife spreads (k34 {u5.loc['k34','jackknife_min']:.3f}–{u5.loc['k34','jackknife_max']:.3f}; beta_P {u5.loc['beta_P','jackknife_min']:.4f}–{u5.loc['beta_P','jackknife_max']:.4f}) are several times wider than the profile half-widths. k37 comes from one run, and beta_P correlates with both multipliers (+0.70, +0.75). A temperature of 33 or 36 C is reached only by linear interpolation of the multipliers (an assumption).
- **mu_max and q_max** are "partly determined": within-fit intervals ±{100*(u5.loc['mu_max','ci_hi']-u5.loc['mu_max','ci_lo'])/2/u5.loc['mu_max','value']:.0f}% and ±{100*(u5.loc['q_max','ci_hi']-u5.loc['q_max','ci_lo'])/2/u5.loc['q_max','value']:.0f}%, but the jackknife range is wider (mu_max {u5.loc['mu_max','jackknife_min']:.3f}–{u5.loc['mu_max','jackknife_max']:.3f}).
- **What I do about the weakly determined ones:** report jackknife ranges beside the profile intervals; carry the structural alternatives (M2, M6, M0) into the plant-relevant predictions rather than a single parameter set; flag everything that depends on P_max, n, beta_P and k37 as extrapolation (section 6); and recommend the experiment in section 6.4.

### 2.4 Fixed parameters K_s and the exponent n
Re-optimising the other parameters at each fixed value (D-25):

| Model | Fixed value | chi-square | Δ chi-square / c_hat vs best grid point | P_max | k37 |
|---|---|---|---|---|---|
{fixed_tab}

- **K_s:** the best grid point is the smallest (0.05 g/L). Relative to it, K_s = 0.2 is already {dks02:+.1f} scaled units (above the 3.84 threshold), K_s = 1 is {dks1:+.0f} and K_s = 5 is {dks5:+.0f}. So the data put the upper limit of K_s between 0.05 and 0.2 g/L, with the lower end unbounded; sampling at 24 and 30 h cannot resolve K_s below the 0.4 g/L TRS floor. The a-priori K_s = 1 g/L therefore costs fit but changes the plant-relevant predictions little (section 6.3). K_s is **not estimated**; I keep 1 g/L as the documented primary value (D-16) and report this sensitivity.
- **n (baseline M0, grid):** chi-square falls monotonically as n rises from 0.5 to 3, so n = 1 is not supported; in M5 n is estimated at {u5.loc['n_inh','value']:.2f} (profile [{u5.loc['n_inh','ci_lo']:.2f}, {u5.loc['n_inh','ci_hi']:.2f}]), but only jointly with P_max.

## 3. Task 3: carbon balance for all eight runs

Inputs: measured t = 0 TRS (as glucose equivalent; 6 C per 180.16 g) and the inoculum biomass from `runs.csv` (24.6 g per C-mol). Outputs: 48 h TRS, biomass, ethanol (2 C per 46.07 g), cumulative CO2 (44.01 g per C-mol), glycerol (3 C per 92.09 g) and lactic acid (3 C per 90.08 g). **n.d. lactic acid is uniform on [0, 0.2) g/L (central 0.1), not zero.** 95% intervals are Monte-Carlo (20,000 draws) from the brief's measurement sds (including the t = 0 TRS and the inoculum). All eight runs are included regardless of the fitting decisions.

| Run | Carbon in (C-mol/L) | Carbon out (C-mol/L) | Unaccounted (C-mol/L) | Recovery % of input | MC 95% | Recovery % of consumed-sugar carbon (Phase 0 basis) | Closes within 95%? | Role in fits |
|---|---|---|---|---|---|---|---|---|
{cbrows}

Components (C-mol/L):

| Run | In: sugar | In: inoculum | Out: residual sugar | Biomass | Ethanol | CO2 | Glycerol | Lactic acid |
|---|---|---|---|---|---|---|---|---|
{comptab}

Sensitivity of the recovery % (central values):

| Run | Primary | Nominal t = 0 TRS | Measured t = 0 biomass | n.d. lactic = 0 / = 0.2 g/L |
|---|---|---|---|---|
{senstab}

**Reading.**
- All runs recover 98.2-104.7% of the carbon; the Monte-Carlo sd is {CB.recovery_mc_sd.min():.1f}-{CB.recovery_mc_sd.max():.1f} points, so seven of eight close within 95% uncertainty. **R4 does not** ({CB.loc['R4','recovery_pct']:.1f}%, interval [{CB.loc['R4','recovery_95_lo']:.1f}, {CB.loc['R4','recovery_95_hi']:.1f}]); R4's measured t = 0 TRS (155.9 g/L) is 4.1 g/L below nominal (z = −2.09 in Phase 0), and with the nominal 160 g/L the recovery is {CB.loc['R4','recovery_pct_nominal_S0']:.1f}%. R4's catabolic yield is also above the stoichiometric 0.511 (section 4), which points to a measurement bias in this run, not a real source of carbon. It was not excluded (nothing independent says it is unfit for the yeast model).
- **Mean recovery {rec_mean:.1f}%** ({rec_no4:.1f}% without R4); total unaccounted carbon over the eight runs is {CB.unaccounted_Cmol_L.sum():+.2f} C-mol/L, i.e. output slightly *exceeds* input. A missing carbon sink therefore is not indicated.
- On the Phase 0 consumed-sugar basis (column 7) the recoveries agree with the Phase 0 table within 0.4 points for every run (differences arise from the nominal vs measured inoculum); the total-input basis in column 5 puts the same carbon over a larger denominator, so it sits closer to 100%.
- **Limitations that move the balance but were not corrected:** (i) the TRS assay is a reducing-sugar measurement, so non-sugar organic carbon in molasses (organic acids, amino acids, betaine) is not in the input; it would push recovery above 100%, which is the sign of the average residual; (ii) unmeasured by-products (acetate, succinate, 2,3-butanediol, higher alcohols) and dissolved CO2/bicarbonate are not in the output and would push recovery below 100%; (iii) biomass is converted with the brief's fixed 24.6 g/C-mol, and R3's biomass is OD600-based with no calibration uncertainty; (iv) the inoculum is the recorded charge, not a measurement. The sizes of (i) and (ii) are unknown from these data: they probably partly cancel, so a recovery near 100% does not prove the absence of either.

## 4. Task 4: ethanol yield and the questionable-run analysis

Yield = ethanol at 48 h / (TRS(0) − TRS(48 h)), with the measured t = 0 TRS; theoretical = 2 × 46.07 / 180.16 = **0.5114 g/g**. The last column removes the sugar used to build the biomass increase (1.2206 g/g, carbon equivalent), i.e. the catabolic yield (Level 1's Y_P is defined this way).

| Run | TRS consumed (g/L) | Ethanol (g/L) | Yield (g/g) | MC 95% (measurement only) | % of theory | Yield with nominal t = 0 TRS | Catabolic yield |
|---|---|---|---|---|---|---|---|
{ytab}

| Pooled set | Sum ethanol / sum TRS consumed | % of 0.5114 | Run-bootstrap 95% (10,000) |
|---|---|---|---|
{pooltab}

**Overall yield: {y_all.pooled_yield_sum_ratio:.4f} g/g on the consumed-TRS (glucose-equivalent, after inversion) basis, {y_all.pct_of_theory:.1f}% of theoretical; {y_7.pooled_yield_sum_ratio:.4f} g/g ({y_7.pct_of_theory:.1f}%) without R7.** On the basis of sugar as charged (sucrose plus reducing sugars by mass before inversion, which exceeds the TRS figure by the inversion factor 1.0368 seen in all runs), the same ethanol is about {charged_basis:.3f} g per g of sugar charged and consumed; the basis must always be stated.

**Where the gap goes** (exact decomposition, as points of the consumed sugar carbon not routed to ethanol plus its paired CO2; each row sums to the total gap, and the bracketed intervals are Monte-Carlo):

| Run | Total gap | Biomass | Glycerol | Lactic acid | CO2 beyond 1:1 with ethanol | Unaccounted |
|---|---|---|---|---|---|---|
{dtab}

Averages over the eight runs: biomass {mean_dec.biomass_pct_pts:.1f}, glycerol {mean_dec.glycerol_pct_pts:.1f}, lactic acid {mean_dec.lactic_pct_pts:.2f}, CO2 beyond pairing {mean_dec.excess_CO2_pct_pts:+.1f}, unaccounted {mean_dec.unaccounted_pct_pts:+.1f}; total {mean_dec.gap_pct_of_consumed_carbon:.1f}. **Biomass and glycerol (about {100*(mean_dec.biomass_pct_pts+mean_dec.glycerol_pct_pts)/mean_dec.gap_pct_of_consumed_carbon:.0f}% of the average gap) are measured and are sufficient to explain it;** the unaccounted term is negative on average and its interval includes zero in seven runs (R4 is the exception, −4.9 [−8.5, −1.5]). I do not attribute any of the gap to an unmeasured pathway. The per-run yields differ by more than the measurement sd would allow (R1 {YL.loc['R1','yield_g_per_g']:.3f} vs R4 {YL.loc['R4','yield_g_per_g']:.3f} at the same exhausted-sugar endpoint), so some yield variation between runs is outside the stated measurement noise.

### 4.1 R7 review (independent chemistry and carbon, not fit residuals)

| Quantity | R7 | R5 (repeat) | z of difference | Unit |
|---|---|---|---|---|
{rvtab}

- **Direct observations:** R7 is the only run with detectable lactic acid and the only low pH; at the same nominal conditions it ends with {RV.loc['final TRS','R7']-RV.loc['final TRS','R5']:.1f} g/L more TRS and {abs(RV.loc['ethanol 48 h','R7']-RV.loc['ethanol 48 h','R5']):.1f} g/L less ethanol than R5 with the same biomass. Counting the lactic acid, its carbon closes at {CB.loc['R7','recovery_pct']:.1f}%; leaving it out gives {CB.loc['R7','recovery_pct_lactic_removed']:.1f}% (about {(100-CB.loc['R7','recovery_pct_lactic_removed'])/CB.loc['R7','recovery_mc_sd']:.1f} Monte-Carlo sd below 100%). Lactic acid carbon is {DEC.loc['R7','lactic_pct_pts']:.1f}% of the carbon consumed. Its glucose equivalent (1 glucose → 2 lactic acid) is about {RV.loc['lactic acid as glucose equivalent (1 glucose -> 2 lactic acid)','R7']:.1f} g/L, which is {100*RV.loc['share of the R5-R7 TRS-consumption gap that lactic acid carbon could account for','R7']:.0f}% of the {abs(RV.loc['TRS consumed','difference']):.1f} g/L difference in TRS consumed relative to R5. After removing that sugar, R7's ethanol per sugar consumed is {RV.loc['ethanol per TRS consumed after removing lactic-acid glucose equivalent','R7']:.3f} g/g against R5's {RV.loc['ethanol per TRS consumed after removing lactic-acid glucose equivalent','R5']:.3f}.
- **Interpretation:** this is evidence of an *unusual* run: it contains a carbon sink and an acid stress that the yeast-only model lacks. It is **not proof of contamination**: no microbiology exists, lactic acid is measured at 48 h only, and the other roughly half of the slower sugar uptake is unexplained. That is why R7 is excluded from the primary fits, kept in every diagnostic table, and tested as a sensitivity case.
- **Effect of including R7 on the fits** (refit with R7 added, warm start, R6 not used; `r7_inclusion_effect.csv`):

| Model | Reduced chi-square | Parameters changing by ≥ 10% or ≥ 1 profile half-width | Parameters shifting by ≥ 2 profile half-widths (value in half-widths) |
|---|---|---|---|
{r7tab}

  R7 adds {R7[R7.model==pref].chi2_with_R7.iloc[0]-R7[R7.model==pref].chi2_primary.iloc[0]:.0f} chi-square units for its 52 residuals in M5 (an average |z| of about {np.sqrt((R7[R7.model==pref].chi2_with_R7.iloc[0]-R7[R7.model==pref].chi2_primary.iloc[0])/52):.1f}), so the yeast-only model cannot describe it, but the parameter estimates move modestly. The shifts that matter most for a 33-36 C question are k34 (down) and the temperature slope beta_P (up).

## 5. Level 2 questions of the brief

**Q2. Which parameters can these data pin down, and what do you do about the others?** Evidence in section 2. Within the preferred structure: Y_P, rho_CO2 and X_max are well determined; mu_max, q_max, k34 and beta_P are determined within-fit but not robustly across runs (jackknife wider); P_max and n are determined only jointly (ridge, P_max extrapolated); k37 rests on one run; K_s and n = 1 (Level 1) are not supported as fixed values (K_s < 0.2 g/L; n clearly above 1). Actions: report both profile and jackknife ranges; propagate structural alternatives; flag extrapolation; the experiment in 6.4.

**Q3. Is any run unfit for fitting the yeast model?** R7, on independent grounds (section 4.1): lactic acid 9.0 g/L (≥ 45 times the 0.2 g/L detection limit), pH {RV.loc['final pH','R7']:.2f} ({RV.loc['final pH','z']:+.1f} sd below R5), a lactate carbon sink of {DEC.loc['R7','lactic_pct_pts']:.1f}% of consumed carbon that a yeast-only model has no term for, and a carbon balance that closes only if lactate is counted. R4 is a measurement-quality case (recovery {CB.loc['R4','recovery_pct']:.1f}%, catabolic yield above stoichiometric) but is not unfit. R3 is fit for sugar, ethanol and CO2 (carbon closes at {CB.loc['R3','recovery_pct']:.1f}%); only its OD600 biomass is treated separately. Contamination is a hypothesis, not a finding.

**Q4. Overall ethanol yield, basis, and the gap to the maximum?** {y_all.pooled_yield_sum_ratio:.3f} g/g on consumed TRS (glucose equivalent), {y_all.pct_of_theory:.1f}% of 0.511; about {charged_basis:.3f} g per g sugar charged and consumed. The gap (≈{100-y_all.pct_of_theory:.0f}% of the theoretical yield) is accounted for by biomass formation ({mean_dec.biomass_pct_pts:.1f} points) and glycerol ({mean_dec.glycerol_pct_pts:.1f} points) with lactic acid in R7; the unaccounted carbon averages {mean_dec.unaccounted_pct_pts:+.1f} points.

**Q5. What does the model predict at 37 C and 260 g/L, and how far to trust it?** Section 6.1 gives the numbers. Trust is low for anything beyond the first ~48 h: 37 C is supported by one run (R8, 220 g/L), 260 g/L in the training set by R3 only (30 C; R6 at 34 C was not used), and the combination is not observed; ethanol above 108 g/L, the TRS tail below 50 g/L and any end time beyond 48 h are extrapolations; candidate structures disagree on the 96 h TRS by tens of g/L.

**Q6. Which single experiment?** Section 6.4.

## 6. Task 5: plant-relevant uncertainty (fixed scenarios only; not an optimisation)

The brief's margin formula was applied exactly as stated in section 4 of the brief (170 m3, 8 h turnaround, ₹60/L, ₹25/kg TRS for all sugar charged, steam from the design curve, batch ended when TRS ≤ 5 g/L). The batch end is searched to 120 h, but the data stop at 48 h. Where the wash strength leaves the 7-14% v/v design curve the steam value is clipped and flagged.

### 6.1 Preferred model {pref}: parameter uncertainty (150 draws from the linearised covariance; profile-ensemble range in `plant_prediction_uncertainty.csv`)

| Scenario (T / TRS g/L) | Ethanol at 48 h (g/L) | TRS at 48 h (g/L) | TRS at 96 h (g/L) | Time to ≤ 5 g/L and daily margin per fermenter |
|---|---|---|---|---|
{ptab}

Flags: the 33 C and 36 C scenarios use the interpolated multipliers; the 34 C / 260 g/L batch ends at an ethanol level of about {pu(pref,34.0,260.0,'P_end','point_estimate'):.0f} g/L (above the observed maximum of 107.8 g/L and at {pu(pref,34.0,260.0,'wash','point_estimate'):.1f}% v/v, above the 14% limit of the steam curve) and later than the 48 h data. For the 37 C / 260 g/L case the brief asks about, the preferred model gives ethanol {pu(pref,37.0,260.0,'P48','point_estimate'):.0f} g/L and TRS {pu(pref,37.0,260.0,'S48','point_estimate'):.0f} g/L at 48 h; {pu(pref,37.0,260.0,'S96','point_estimate'):.0f} g/L TRS at 96 h; **no end of batch within 120 h**.

### 6.2 Structure uncertainty: each candidate at its own optimum (TRS at 96 h g/L / time to ≤ 5 g/L / margin, ₹ per day)

| Model | 33 C / 220 | 34 C / 260 | 36 C / 260 | 37 C / 260 |
|---|---|---|---|---|
{sptab}

At 33 C / 220 g/L the structures agree on the batch time ({SP[(SP['T_C']==33.0)&(~SP.model.str.contains('refit'))].t_end.min():.0f}-{SP[(SP['T_C']==33.0)&(~SP.model.str.contains('refit'))].t_end.max():.0f} h) and the daily margin varies by ±{100*(SP[(SP['T_C']==33.0)&(~SP.model.str.contains('refit'))].daily_margin_Rs.max()-SP[(SP['T_C']==33.0)&(~SP.model.str.contains('refit'))].daily_margin_Rs.min())/2/SP[(SP['T_C']==33.0)&(~SP.model.str.contains('refit'))].daily_margin_Rs.mean():.0f}% about its mean, comparable to the parameter-only interval ({pu(pref,33.0,220.0,'daily_margin_Rs','ens_95_lo')/1000:.0f}k-{pu(pref,33.0,220.0,'daily_margin_Rs','ens_95_hi')/1000:.0f}k). At 34-37 C / 260 g/L the structures disagree on whether the batch can finish within 96 h at all, and by tens of g/L in TRS: that disagreement, not the parameter interval, dominates. Refitting {pref} with R6 added (labelled secondary, R6 used as training) moves the 34 C / 260 g/L batch time from {pu(pref,34.0,260.0,'t_end','point_estimate'):.0f} h to {r6ref[(r6ref['T_C']==34.0)].t_end.iloc[0]:.0f} h and the margin from ₹{pu(pref,34.0,260.0,'daily_margin_Rs','point_estimate')/1000:.1f}k to ₹{r6ref[(r6ref['T_C']==34.0)].daily_margin_Rs.iloc[0]/1000:.1f}k per day.

### 6.3 Which parameters drive the uncertainty (linearised, additive shares of the predictive variance; grouped because the P_max–n ridge makes single-parameter shares meaningless)

| Quantity | Ethanol-inhibition shape (P_max, n) | Temperature (beta_P, k34, k37) | Yield (Y_P, rho_CO2) | Growth and uptake (mu_max, X_max, q_max) |
|---|---|---|---|---|
{vtab}

Linearised 1-sd uncertainty of the daily margin: ₹{lin.loc[(33.0,220.0,'daily_margin_Rs'),'sd_linearised']/1000:.1f}k ({lin.loc[(33.0,220.0,'daily_margin_Rs'),'rel_sd_pct']:.1f}%) at 33 C / 220 and ₹{lin.loc[(34.0,260.0,'daily_margin_Rs'),'sd_linearised']/1000:.1f}k ({lin.loc[(34.0,260.0,'daily_margin_Rs'),'rel_sd_pct']:.1f}%) at 34 C / 260. At 33 C / 220 the yield (Y_P) and the inhibition shape dominate; at the 260 g/L scenarios the ethanol-inhibition shape and the temperature slope dominate. K_s: re-optimised {pref} predictions at 33 C / 220 are insensitive to the primary K_s = 1 g/L (K_s 0.05 → 5: batch time 46.0 → 47.6 h; margin ₹{KS[(KS['T_C']==33.0)&(KS.K_s<0.1)].daily_margin_Rs.iloc[0]/1000:.1f}k → ₹{KS[(KS['T_C']==33.0)&(KS.K_s==5)].daily_margin_Rs.iloc[0]/1000:.1f}k), and only a K_s of 20 g/L, which the data reject, gives a large change.

| K_s (g/L) | chi-square | Time to ≤ 5 g/L and margin at 33 C / 220 | TRS at 96 h |
|---|---|---|---|
{ks_tab}

### 6.4 The single most useful additional experiment
**One 96-hour batch at 34 C and 260 g/L TRS (the conditions of R6, extended to 96 h), sampled as before to 48 h and every 12 h to 96 h for biomass (dry weight, not OD600), TRS, ethanol and CO2, with endpoint and 48 h glycerol, lactic acid and pH. If a duplicate is possible it also measures run-to-run reproducibility, which the data lack.**
Why this one:
- **Model sensitivity:** the prediction uncertainty at the high-sugar scenarios is dominated by the shape and temperature dependence of ethanol inhibition at ethanol levels above 100 g/L and by the TRS tail after 48 h (section 6.3). No run contains data past 48 h or ethanol above 108 g/L at 34 C.
- **Coverage:** the run sits on the one cell (34 C, 260 g/L) already bracketed by R6 at 48 h and by R3 at 30 C, and extends it in time; the 33 and 36 C interpolations and the 37 C extrapolation stay unobserved, but the structures that disagree most there are the ones this run discriminates.
- **Linearised design criterion** (preferred model; extra data weighted by the stated sds; reduction in the predictive sd of the daily margin, of TRS at 96 h, and the chi-square distance between preferred model and M2 along the new run; `experiment_design.csv`, `experiment_discrimination.csv`):

| Candidate run (T / TRS / duration) | Mean reduction in margin sd (33/220 and 34/260 scenarios) | Margin sd reduction at 34/260 | TRS(96 h) sd reduction at 36/260 | TRS(96 h) sd reduction at 37/260 | Separation M5 vs M2 (chi-square units) |
|---|---|---|---|---|---|
{edtab}

  The best 96 h run reduces the predicted margin sd by about {ED.mean_margin_sd_reduction_pct.max():.0f}% on average, against {ED[(ED['T_C']==34)&(ED.S0_gL==260)&(ED.horizon_h==48)].mean_margin_sd_reduction_pct.iloc[0]:.0f}% for repeating the same condition to 48 h only: the added duration, not the condition, carries most of the information. A 36 C / 260 g/L run to 96 h is the alternative if the warm-water scenario matters most: it reduces the TRS(96 h) sd at the 37 C scenario more (64% vs 52%) and equals the 34 C run at the 36 C scenario (65%), but it separates the competing structures about {DS[(DS['T_C']==34)&(DS.S0_gL==260)&(DS.horizon_h==96)].sep_M5_M2.iloc[0]/DS[(DS['T_C']==36)&(DS.S0_gL==260)&(DS.horizon_h==96)].sep_M5_M2.iloc[0]:.1f} times less strongly and reduces the margin sd less. A 37 C / 260 g/L run to 96 h separates them about {DS[(DS['T_C']==34)&(DS.S0_gL==260)&(DS.horizon_h==96)].sep_M5_M2.iloc[0]/DS[(DS['T_C']==37)&(DS.S0_gL==260)&(DS.horizon_h==96)].sep_M5_M2.iloc[0]:.0f} times less strongly.
- **Caveats:** the design criterion is linearised around the preferred model, uses only that model's parameter uncertainty (structural uncertainty enters only through the separation column), and assumes the new run behaves like the training runs (no contamination, which the proposed lactate/pH check would reveal).

## 7. Limitations and unresolved issues
1. **Preferred structure is not validated at 37 C.** With R8 left out M5 extrapolates badly (chi2/pt {LP.loc['M5','R8']:.0f}); M2/M6 behave better there (≈ {LP.loc['M2','R8']:.0f}-{LP.loc['M6','R8']:.0f}). M5 was chosen by the pre-registered rule; I did not change the rule after seeing this.
2. **No candidate fits within noise** (reduced chi-square ≥ {cmp.reduced_chi2.min():.1f}); residuals are autocorrelated; the biomass of R3 remains OD600-based and unvalidated.
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
"""
open(OUT,'w').write(rep); print(len(rep))
