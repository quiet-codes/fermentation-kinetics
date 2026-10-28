#!/usr/bin/env python
"""Post-hoc summary numbers for reports/level1.md (read-only analysis; changes nothing).
Runs only after the fit AND predict stages exist. Writes outputs/tables/level1_correlations.csv
and outputs/tables/level1_summary_numbers.csv.   python src/level1_summary.py --data-dir data/raw --root ."""
import argparse, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit, kinetics as K

ap = argparse.ArgumentParser(); ap.add_argument("--data-dir", default="data/raw"); ap.add_argument("--root", default=".")
a = ap.parse_args()
tdir = os.path.join(a.root, "outputs", "tables")
if not os.path.exists(os.path.join(tdir, "heldout_metrics.csv")):
    raise SystemExit("run fit.py --stage fit and --stage predict first")
fr, ptab, theta, fixed = fit.load_frozen(tdir)
runs, tc = fit.read_raw(a.data_dir)
pol = fit.default_policy(fixed=fixed, co2_floor=fr["co2_floor"])
recs = fit.make_records(pol["train"], runs, tc)
fun = fit.residual_fn(recs, pol, dict(failures=0))
out = []
def add(name, value, note=""): out.append(dict(name=name, value=value, note=note))

# numerical (central-difference) Jacobian -> correlation matrix of the free parameters
J = np.zeros((len(fun(theta)), len(theta)))
for i in range(len(theta)):
    h = 1e-5 * abs(theta[i]); tp, tm = theta.copy(), theta.copy(); tp[i] += h; tm[i] -= h
    J[:, i] = (fun(tp) - fun(tm)) / (2 * h)
cov = np.linalg.inv(J.T @ J); sd = np.sqrt(np.diag(cov)); corr = cov / np.outer(sd, sd)
cdf = pd.DataFrame(corr, index=K.PARAM_NAMES, columns=K.PARAM_NAMES); cdf.to_csv(os.path.join(tdir, "level1_correlations.csv"), lineterminator='\n', encoding='utf-8')
for i in range(len(theta)):
    for j in range(i + 1, len(theta)):
        if abs(corr[i, j]) >= 0.8:
            add(f"corr[{K.PARAM_NAMES[i]},{K.PARAM_NAMES[j]}]", corr[i, j], "|r| >= 0.8 (linearised, at the optimum)")
Jn = J * theta; sv = np.linalg.svd(Jn, compute_uv=False)
add("relative_jacobian_singular_values_min", sv[-1]); add("relative_jacobian_singular_values_max", sv[0])
add("relative_jacobian_condition_number", sv[0] / sv[-1])

# pooled training vs held-out error (z units)
d = pd.read_csv(os.path.join(tdir, "level1_fit_diagnostics.csv")); d = d[d.in_objective]
h = pd.read_csv(os.path.join(tdir, "heldout_metrics.csv")); h = h[h.scope == "timecourse_t>0"].set_index("variable")
for v in fit.VARS:
    g = d[d.variable == v]
    add(f"train_pooled_rms_z[{v}]", float(np.sqrt((g.chi2_per_point * g.n).sum() / g.n.sum())), "training runs, in objective")
    add(f"train_pooled_mean_z[{v}]", float((g.mean_z * g.n).sum() / g.n.sum()))
    add(f"R6_rms_z[{v}]", float(h.loc[v, "rms_z"])); add(f"R6_mean_z[{v}]", float(h.loc[v, "mean_z"]))
add("train_overall_rms_z", float(np.sqrt(fr["chi2"] / fr["n_residuals"])))

# yields and CO2:ethanol ratio at 48 h (observed) and model
for r in fit.make_records(pol["train"] + ["R6", "R7"], runs, tc):
    dS = r["S0"] - r["obs"]["S"][-1]
    add(f"obs_ethanol_per_TRS_dropped_nominalS0[{r['run']}]", r["obs"]["P"][-1] / dS)
    add(f"obs_CO2_over_ethanol_48h[{r['run']}]", r["obs"]["C"][-1] / r["obs"]["P"][-1])
rec6 = fit.make_records(["R6"], runs, tc)[0]
s6 = fit.simulate_record(theta, rec6, pol)
add("pred_R6_ethanol_per_TRS_dropped", s6[-1, 2] / (rec6["S0"] - s6[-1, 1]))
add("pred_R6_biomass_sugar_use_g_per_L", K.SUGAR_PER_BIOMASS * (s6[-1, 0] - rec6["X0"]))
add("obs_R6_biomass_sugar_use_g_per_L", K.SUGAR_PER_BIOMASS * (rec6["obs"]["X"][-1] - rec6["X0"]), "DW biomass, uses observed 48 h value")
th = dict(zip(K.PARAM_NAMES, theta))
add("rho_minus_stoich_in_SE", (th["rho_CO2"] - K.RHO_STOICH) / ptab.set_index("parameter").loc["rho_CO2", "se_linear_scaled"])

# CO2 floor effect
allc = np.concatenate([r["obs"]["C"][1:] for r in recs])
add("min_positive_time_CO2_g_per_L", float(allc.min()))
add("CO2_sd_floor_vs_pure2pct_ratio_at_min_CO2", float(fit.sd_C(allc.min(), 0.1) / fit.sd_C(allc.min(), 0.0)))
add("CO2_sd_floor_vs_pure2pct_ratio_median", float(np.median(fit.sd_C(allc, 0.1) / fit.sd_C(allc, 0.0))))
# early ethanol rate (0-12 h) observed vs predicted for R6 (post-hoc description only)
k12 = list(rec6["t"]).index(12.0)
add("R6_ethanol_0_12h_rate_obs", rec6["obs"]["P"][k12] / 12); add("R6_ethanol_0_12h_rate_pred", s6[k12, 2] / 12)
k36 = list(rec6["t"]).index(36.0)
add("R6_ethanol_36_48h_rate_obs", (rec6["obs"]["P"][-1] - rec6["obs"]["P"][k36]) / 12)
add("R6_ethanol_36_48h_rate_pred", (s6[-1, 2] - s6[k36, 2]) / 12)
add("R6_TRS_36_48h_rate_obs", (rec6["obs"]["S"][k36] - rec6["obs"]["S"][-1]) / 12)
add("R6_TRS_36_48h_rate_pred", (s6[k36, 1] - s6[-1, 1]) / 12)
pd.DataFrame(out).to_csv(os.path.join(tdir, "level1_summary_numbers.csv"), index=False, lineterminator='\n', encoding='utf-8')
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 200)
print(pd.DataFrame(out).round(4).to_string(index=False))
