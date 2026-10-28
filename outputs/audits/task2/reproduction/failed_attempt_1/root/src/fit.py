#!/usr/bin/env python
"""Level 1 fitting, held-out prediction and predeclared sensitivity analyses.

Stages (run in this order; later stages refuse to run if the earlier one is missing):
  fit          weighted nonlinear least squares on the approved TRAINING runs only.
               Writes level1_parameters.csv + level1_frozen.json (SHA-256 of the parameters).
  predict      verifies the hash, loads the frozen parameters, THEN loads R6 and predicts it.
               No refitting. Writes heldout_metrics.csv, heldout_predictions.csv and the figure.
  sensitivity  predeclared sensitivity fits (R7 included, R3 biomass, K_s, CO2 floor).
               Parameter changes and training fit only; R6 is never evaluated here.
  all          fit -> predict -> sensitivity.

Usage (project root):  python src/fit.py --data-dir data/raw --root . --stage all
"""
import argparse, hashlib, json, os, platform, sys, time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.optimize import least_squares
from scipy.stats import qmc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kinetics as K

# ------------------------------------------------------------------ approved decisions
HOLDOUT = "R6"                                  # D-10
TRAIN = ["R1", "R2", "R3", "R4", "R5", "R8"]    # D-11
EXCLUDED_PRIMARY = ["R7"]                       # D-13
BIOMASS_EXCLUDED = ("R3",)                      # D-12
VARS = ("X", "S", "P", "C")
COL = {"X": "biomass_g_L", "S": "TRS_g_L_as_glucose", "P": "ethanol_g_L", "C": "CO2_evolved_g_per_L"}
LABEL = {"X": "Biomass (g/L)", "S": "TRS (g/L)", "P": "Ethanol (g/L)", "C": "Cumulative CO2 (g/L)"}
CO2_FLOOR = 0.10        # g/L, documented assumption (D-18)
PENALTY = 1.0e3         # residual value used when the ODE solver fails (counted and reported)
SEED = 20261026
N_STARTS = 40
LOG_PARAMS = ("mu_max", "q_max")
TCOLOR = {30: "tab:blue", 34: "tab:orange", 37: "tab:red"}

# ------------------------------------------------------------------ measurement sds (brief s3)
def sd_X(x): return 0.035 * np.asarray(x, float) + 0.08
def sd_S(s): return 0.01 * np.asarray(s, float) + 0.4
def sd_P(e): return 0.012 * np.asarray(e, float) + 0.25
def sd_C(c, floor=CO2_FLOOR): return 0.02 * np.asarray(c, float) + floor

def sd_of(var, obs, policy):
    if var == "X": return sd_X(obs)
    if var == "S": return sd_S(obs)
    if var == "P": return sd_P(obs)
    return sd_C(obs, policy["co2_floor"])

def default_policy(**over):
    pol = dict(train=list(TRAIN), biomass_excluded=set(BIOMASS_EXCLUDED), sd_factor={},
               co2_floor=CO2_FLOOR, fixed=dict(K.FIXED_DEFAULT))
    pol.update(over)
    if HOLDOUT in pol["train"] and not pol.get("allow_holdout_in_train", False):
        raise ValueError("held-out run R6 must never be in the training set")
    return pol

# ------------------------------------------------------------------ data
def read_raw(data_dir):
    runs = pd.read_csv(os.path.join(data_dir, "runs.csv")).set_index("run")
    tc = pd.read_csv(os.path.join(data_dir, "timecourse.csv"))
    return runs, tc

def make_records(run_ids, runs, tc):
    recs = []
    for rid in run_ids:
        m = runs.loc[rid]
        g = tc[tc.run == rid].sort_values("time_h")
        recs.append(dict(run=rid, T=float(m.temperature_C), S0=float(m.initial_TRS_g_L_as_glucose),
                         X0=float(m.inoculum_biomass_g_L), t=g.time_h.to_numpy(float),
                         obs={v: g[COL[v]].to_numpy(float) for v in VARS}))
    return recs

def simulate_record(theta, rec, policy):
    sim = K.simulate(rec["T"], rec["S0"], rec["X0"], rec["t"], theta, policy["fixed"])
    return None if sim is None else np.maximum(sim, 0.0)

def residual_fn(records, policy, counter):
    def fun(theta):
        out = []
        for r in records:
            sim = simulate_record(theta, r, policy)
            pos = r["t"] > 0                              # D-19: positive-time data only
            for j, v in enumerate(VARS):
                if v == "X" and r["run"] in policy["biomass_excluded"]:
                    continue                              # D-12
                n = int(pos.sum())
                if sim is None:
                    counter["failures"] += 1
                    out.append(np.full(n, PENALTY)); continue
                obs = r["obs"][v][pos]
                sd = sd_of(v, obs, policy) * policy["sd_factor"].get((r["run"], v), 1.0)
                out.append((sim[pos, j] - obs) / sd)
        return np.concatenate(out)
    return fun

# ------------------------------------------------------------------ optimisation
def sample_starts(n, seed):
    d = len(K.PARAM_NAMES)
    u = qmc.LatinHypercube(d=d, seed=seed).random(n)
    th = np.empty_like(u)
    for j, name in enumerate(K.PARAM_NAMES):
        lo, hi = K.LOWER[j], K.UPPER[j]
        th[:, j] = np.exp(np.log(lo) + u[:, j] * (np.log(hi) - np.log(lo))) if name in LOG_PARAMS \
            else lo + u[:, j] * (hi - lo)
    return th

def multistart(records, policy, n_starts, seed, extra_starts=()):
    counter = dict(failures=0)
    fun = residual_fn(records, policy, counter)
    starts = [K.START.copy()] + [np.asarray(s, float) for s in extra_starts] + list(sample_starts(n_starts, seed))
    results = []
    for i, x0 in enumerate(starts):
        x0 = np.clip(x0, K.LOWER, K.UPPER)
        try:
            r = least_squares(fun, x0, bounds=(K.LOWER, K.UPPER), method="trf", x_scale="jac",
                              diff_step=1e-6, ftol=1e-10, xtol=1e-10, gtol=1e-10, max_nfev=400)
            results.append(dict(start=i, chi2=2 * r.cost, status=int(r.status), nfev=int(r.nfev),
                                theta=r.x, res=r))
        except Exception as ex:                      # reported, not hidden
            results.append(dict(start=i, chi2=np.inf, status=-99, nfev=0, theta=x0, res=None, error=str(ex)))
    best = min(results, key=lambda d: d["chi2"])
    return best, results, counter

def at_bound_mask(theta, tol=1e-6):
    rng = K.UPPER - K.LOWER
    return (np.abs(theta - K.LOWER) < tol * rng) | (np.abs(theta - K.UPPER) < tol * rng)

def linear_uncertainty(res, theta, n_obs):
    """Linearised (Gauss-Newton) covariance on the parameters not sitting at a bound.
    Local, assumes the sds are right; not a profile-likelihood interval (that is Level 2)."""
    free = ~at_bound_mask(theta)
    J = res.jac[:, free]
    chi2 = 2 * res.cost
    dof = n_obs - len(theta)
    red = chi2 / dof
    se = np.full(len(theta), np.nan); se_s = np.full(len(theta), np.nan)
    cov = np.linalg.pinv(J.T @ J)
    se[free] = np.sqrt(np.diag(cov)); se_s[free] = se[free] * np.sqrt(max(1.0, red))
    corr = cov / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
    Jn = J * theta[free]                          # relative (dimensionless) sensitivities
    sv = np.linalg.svd(Jn, compute_uv=False)
    full_cov = np.full((len(theta), len(theta)), np.nan)
    idx = np.where(free)[0]
    full_cov[np.ix_(idx, idx)] = cov * max(1.0, red)
    return dict(free=free, se=se, se_scaled=se_s, red=red, dof=dof, chi2=chi2, corr=corr,
                corr_names=[K.PARAM_NAMES[i] for i in idx], sv=sv, cond=sv[0] / sv[-1], cov_scaled=full_cov)

# ------------------------------------------------------------------ tables
NOTES = {
 "mu_max": "growth rate at 30 C; biomass sd is large and growth sampled every 2 h",
 "X_max": "plateau of 10-11.5 g/L is visible in every run",
 "q_max": "early specific uptake; correlated with Y_P/k(T) through the ethanol rate",
 "P_max": "likely above observed ethanol (extrapolated); see bound flag",
 "Y_P": "catabolic yield; glycerol and CO2 not separated",
 "rho_CO2": "compare with stoichiometric 0.955",
 "k34": "34 C estimated from R4, R5 (R6 held out, R7 excluded)",
 "k37": "37 C rests on ONE run (R8)",
}

def parameter_table(theta, unc, policy):
    rows = []
    for i, n in enumerate(K.PARAM_NAMES):
        ab = bool(at_bound_mask(theta)[i])
        which = "" if not ab else ("lower" if abs(theta[i] - K.LOWER[i]) < abs(theta[i] - K.UPPER[i]) else "upper")
        rows.append(dict(parameter=n, value=theta[i], unit=K.PARAMS[n][3], status="fitted",
                         start=K.START[i], lower=K.LOWER[i], upper=K.UPPER[i],
                         at_bound=which if ab else "no", se_linear_unit_weights=unc["se"][i],
                         se_linear_scaled=unc["se_scaled"][i],
                         rel_se_pct=100 * unc["se_scaled"][i] / abs(theta[i]) if np.isfinite(unc["se_scaled"][i]) else np.nan,
                         note=NOTES[n]))
    for n, v in policy["fixed"].items():
        rows.append(dict(parameter=n, value=v, unit=K.FIXED_INFO[n][0], status="fixed", start=v, lower=np.nan,
                         upper=np.nan, at_bound="n/a", se_linear_unit_weights=np.nan, se_linear_scaled=np.nan,
                         rel_se_pct=np.nan, note=K.FIXED_INFO[n][1]))
    # derived (delta method, only if the underlying parameters are free)
    p = dict(zip(K.PARAM_NAMES, theta)); C = unc["cov_scaled"]; ix = {n: i for i, n in enumerate(K.PARAM_NAMES)}
    for name, (a, b) in {"mu_max*k34": ("mu_max", "k34"), "mu_max*k37": ("mu_max", "k37"),
                         "q_max*k34": ("q_max", "k34"), "q_max*k37": ("q_max", "k37")}.items():
        val = p[a] * p[b]
        g = np.zeros(len(theta)); g[ix[a]] = p[b]; g[ix[b]] = p[a]
        var = g @ C @ g
        se = np.sqrt(var) if np.isfinite(var) else np.nan
        rows.append(dict(parameter=name, value=val, unit=K.PARAMS[a][3], status="derived", start=np.nan, lower=np.nan,
                         upper=np.nan, at_bound="n/a", se_linear_unit_weights=np.nan, se_linear_scaled=se,
                         rel_se_pct=100 * se / val if np.isfinite(se) else np.nan,
                         note="effective maximum rate at that temperature"))
    return pd.DataFrame(rows)

def sign_stats(e):
    s = np.sign(e); s[s == 0] = 1
    changes = int(np.sum(s[1:] != s[:-1]))
    longest = cur = 1
    for a, b in zip(s[:-1], s[1:]):
        cur = cur + 1 if a == b else 1
        longest = max(longest, cur)
    return changes, longest

def block_metrics(pred, obs, sd):
    e = pred - obs; z = e / sd
    ch, lg = sign_stats(e)
    return dict(n=len(e), rmse=float(np.sqrt(np.mean(e ** 2))), mae=float(np.mean(np.abs(e))), bias=float(np.mean(e)),
                rel_rmse_pct=float(100 * np.sqrt(np.mean(e ** 2)) / np.mean(obs)), mean_z=float(np.mean(z)),
                rms_z=float(np.sqrt(np.mean(z ** 2))), frac_abs_z_le_2=float(np.mean(np.abs(z) <= 2)),
                chi2_per_point=float(np.mean(z ** 2)), sign_changes=ch, longest_same_sign_run=lg)

def fit_diagnostics(theta, records, policy):
    rows = []
    for r in records:
        sim = simulate_record(theta, r, policy); pos = r["t"] > 0
        for j, v in enumerate(VARS):
            obs = r["obs"][v][pos]
            inobj = not (v == "X" and r["run"] in policy["biomass_excluded"])
            m = block_metrics(sim[pos, j], obs, sd_of(v, obs, policy))
            rows.append(dict(run=r["run"], variable=v, in_objective=inobj, **m))
    return pd.DataFrame(rows)

def t0_diagnostics(records, policy):
    rows = []
    for r in records:
        nominal = dict(X=r["X0"], S=r["S0"], P=0.0, C=0.0)
        for v in VARS:
            meas = r["obs"][v][0]; sd = float(sd_of(v, meas, policy))
            rows.append(dict(run=r["run"], variable=v, nominal_initial_state=nominal[v], measured_t0=meas,
                             sd=sd, z=(meas - nominal[v]) / sd, used_in_objective=False))
    return pd.DataFrame(rows)

def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

# ------------------------------------------------------------------ figures
def smooth_t(rec):
    return np.linspace(0, rec["t"][-1], 241)

def plot_runs(theta, records, policy, path, title, cols=6, held_out=False):
    n = len(records)
    fig, axes = plt.subplots(4, n, figsize=(3.3 * n, 10), sharex=True, squeeze=False)
    for c, r in enumerate(records):
        ts = smooth_t(r)
        sim = np.maximum(K.simulate(r["T"], r["S0"], r["X0"], ts, theta, policy["fixed"]), 0)
        col = TCOLOR[int(r["T"])]
        for j, v in enumerate(VARS):
            ax = axes[j, c]
            ax.plot(ts, sim[:, j], color=col, lw=1.8, label="model")
            obs = r["obs"][v]; sd = sd_of(v, obs, policy)
            excl = (v == "X" and r["run"] in policy["biomass_excluded"])
            kw = dict(mfc="white", color="gray") if excl else dict(color=col)
            ax.errorbar(r["t"][1:], obs[1:], yerr=sd[1:], fmt="o", ms=3.5, lw=0.8, capsize=1.5,
                        label=("OD600 data (NOT fitted)" if excl else "data (positive t)"), **kw)
            ax.plot(r["t"][0], obs[0], "D", mfc="white", mec="k", ms=4, label="t=0 measured (diagnostic)")
            ax.grid(alpha=0.3)
            if c == 0: ax.set_ylabel(LABEL[v])
            if j == 0: ax.set_title(f"{r['run']}: {int(r['T'])} C, {int(r['S0'])} g/L" + (" (held out)" if held_out else ""), fontsize=10)
            if j == 3: ax.set_xlabel("Time (h)")
        if c == 0: axes[0, 0].legend(fontsize=6.5, loc="lower right")
    fig.suptitle(title, fontsize=11); fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(path, dpi=150); plt.close(fig)

def plot_heldout(theta, rec, policy, path):
    ts = smooth_t(rec)
    sim = np.maximum(K.simulate(rec["T"], rec["S0"], rec["X0"], ts, theta, policy["fixed"]), 0)
    simk = np.maximum(K.simulate(rec["T"], rec["S0"], rec["X0"], rec["t"], theta, policy["fixed"]), 0)
    fig, axes = plt.subplots(2, 4, figsize=(15, 6.5), gridspec_kw=dict(height_ratios=[3, 1.3]), sharex=True)
    for j, v in enumerate(VARS):
        obs = rec["obs"][v]; sd = sd_of(v, obs, policy)
        ax = axes[0, j]
        ax.plot(ts, sim[:, j], "k-", lw=1.8, label="prediction (frozen training fit)")
        ax.errorbar(rec["t"], obs, yerr=sd, fmt="o", color="tab:orange", ms=4, capsize=2, label="R6 measured (+/-1 sd)")
        ax.set_ylabel(LABEL[v]); ax.grid(alpha=0.3)
        z = (simk[:, j] - obs) / sd
        a2 = axes[1, j]
        a2.bar(rec["t"], z, width=1.2, color=np.where(np.abs(z) > 2, "tab:red", "tab:gray"))
        a2.axhline(0, color="k", lw=0.6); a2.axhline(2, color="r", lw=0.5, ls="--"); a2.axhline(-2, color="r", lw=0.5, ls="--")
        a2.set_xlabel("Time (h)"); a2.set_ylabel("(pred - obs)/sd"); a2.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=7)
    fig.suptitle("R6 held out (34 C, 260 g/L): prediction only, parameters frozen before R6 was loaded", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95]); fig.savefig(path, dpi=150); plt.close(fig)

# ------------------------------------------------------------------ stages
def paths(root):
    t = os.path.join(root, "outputs", "tables"); f = os.path.join(root, "outputs", "figures")
    os.makedirs(t, exist_ok=True); os.makedirs(f, exist_ok=True)
    return t, f

def stage_fit(args):
    tdir, fdir = paths(args.root)
    runs, tc = read_raw(args.data_dir)
    policy = default_policy()
    assert HOLDOUT not in policy["train"]
    records = make_records(policy["train"], runs, tc)         # R6 and R7 are never loaded here
    t0 = time.time()
    best, results, counter = multistart(records, policy, args.n_starts, args.seed)
    theta = best["theta"]; res = best["res"]
    n_obs = len(residual_fn(records, policy, dict(failures=0))(theta))
    unc = linear_uncertainty(res, theta, n_obs)
    ptab = parameter_table(theta, unc, policy)
    ptab.to_csv(os.path.join(tdir, "level1_parameters.csv"), index=False)
    # multistart log
    ms = pd.DataFrame([dict(start=d["start"], chi2=d["chi2"], status=d["status"], nfev=d["nfev"],
                            **dict(zip(K.PARAM_NAMES, d["theta"]))) for d in results]).sort_values("chi2")
    ms.to_csv(os.path.join(tdir, "level1_multistart.csv"), index=False)
    fit_diagnostics(theta, records, policy).to_csv(os.path.join(tdir, "level1_fit_diagnostics.csv"), index=False)
    t0_diagnostics(records, policy).to_csv(os.path.join(tdir, "level1_t0_diagnostics.csv"), index=False)
    plot_runs(theta, records, policy, os.path.join(fdir, "level1_fits.png"),
              "Level 1 training fits (R1, R2, R3, R4, R5, R8). Model lines vs data; R3 biomass is OD600-based and not fitted")
    near = ms[ms.chi2 <= unc["chi2"] * 1.001 + 0.01]
    frozen = dict(created=time.strftime("%Y-%m-%d %H:%M:%S"), parameters_csv_sha256=sha256(os.path.join(tdir, "level1_parameters.csv")),
                  training_runs=policy["train"], biomass_excluded=sorted(policy["biomass_excluded"]), excluded_runs=EXCLUDED_PRIMARY,
                  holdout=HOLDOUT, chi2=unc["chi2"], n_residuals=n_obs, n_fitted_params=len(theta), dof=unc["dof"],
                  reduced_chi2=unc["red"], solver="scipy solve_ivp LSODA rtol=1e-9 atol=1e-11",
                  optimiser="scipy least_squares trf, x_scale=jac, diff_step=1e-6, ftol=xtol=gtol=1e-10, max_nfev=400",
                  n_starts=1 + args.n_starts, seed=args.seed, starts_within_0p1pct_of_best=int(len(near)),
                  ode_failures_counted=counter["failures"], best_status=int(best["status"]), best_nfev=int(best["nfev"]),
                  fixed=policy["fixed"], co2_floor=policy["co2_floor"], jacobian_cond_relative=float(unc["cond"]),
                  python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, pandas=pd.__version__,
                  runtime_s=round(time.time() - t0, 1))
    json.dump(frozen, open(os.path.join(tdir, "level1_frozen.json"), "w", encoding="utf-8", newline="\n"), indent=2)
    print(json.dumps({k: frozen[k] for k in ["chi2", "n_residuals", "dof", "reduced_chi2", "starts_within_0p1pct_of_best",
                                             "ode_failures_counted", "best_status", "runtime_s"]}, indent=1))
    print(ptab[["parameter", "value", "se_linear_scaled", "at_bound"]].to_string(index=False))

def load_frozen(tdir):
    fp = os.path.join(tdir, "level1_frozen.json")
    if not os.path.exists(fp):
        raise SystemExit("fit stage has not been run (level1_frozen.json missing)")
    fr = json.load(open(fp, encoding="utf-8"))
    cp = os.path.join(tdir, "level1_parameters.csv")
    if sha256(cp) != fr["parameters_csv_sha256"]:
        raise SystemExit("level1_parameters.csv changed after being frozen; refusing to predict")
    ptab = pd.read_csv(cp)
    fit = ptab[ptab.status == "fitted"].set_index("parameter")
    theta = np.array([fit.loc[n, "value"] for n in K.PARAM_NAMES])
    fixed = {r.parameter: float(r.value) for r in ptab[ptab.status == "fixed"].itertuples()}
    return fr, ptab, theta, fixed

def stage_predict(args):
    tdir, fdir = paths(args.root)
    fr, ptab, theta, fixed = load_frozen(tdir)                 # frozen BEFORE R6 is read
    runs, tc = read_raw(args.data_dir)
    policy = default_policy(fixed=fixed, co2_floor=fr["co2_floor"])
    rec = make_records([HOLDOUT], runs, tc)[0]                 # first and only place R6 is loaded
    sim = simulate_record(theta, rec, policy)
    if sim is None:
        raise SystemExit("ODE failure while predicting R6")
    pos = rec["t"] > 0
    rows, prow = [], []
    for j, v in enumerate(VARS):
        obs = rec["obs"][v]; sd = sd_of(v, obs, policy)
        for k, tt in enumerate(rec["t"]):
            prow.append(dict(run=HOLDOUT, time_h=tt, variable=v, observed=obs[k], sd=sd[k], predicted=sim[k, j],
                             error=sim[k, j] - obs[k], z=(sim[k, j] - obs[k]) / sd[k]))
        rows.append(dict(scope="timecourse_t>0", variable=v, **block_metrics(sim[pos, j], obs[pos], sd[pos])))
        rows.append(dict(scope="endpoint_48h", variable=v, n=1, rmse=abs(sim[-1, j] - obs[-1]), bias=sim[-1, j] - obs[-1],
                         mean_z=(sim[-1, j] - obs[-1]) / sd[-1], observed=obs[-1], predicted=sim[-1, j]))
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "heldout_metrics.csv"), index=False)
    pd.DataFrame(prow).to_csv(os.path.join(tdir, "heldout_predictions.csv"), index=False)
    plot_heldout(theta, rec, policy, os.path.join(fdir, "heldout_prediction.png"))
    print(pd.DataFrame(rows)[["scope", "variable", "n", "rmse", "bias", "rel_rmse_pct", "mean_z", "rms_z", "observed", "predicted"]].round(3).to_string(index=False))

def stage_sensitivity(args):
    tdir, fdir = paths(args.root)
    if not os.path.exists(os.path.join(tdir, "heldout_metrics.csv")):
        raise SystemExit("run the predict stage first (D-20: sensitivity only after the R6 prediction)")
    fr, ptab, theta0, fixed = load_frozen(tdir)
    se0 = ptab[ptab.status == "fitted"].set_index("parameter")["se_linear_scaled"]
    runs, tc = read_raw(args.data_dir)
    cases = {
        "R7_included": dict(train=TRAIN + ["R7"]),
        "R3_biomass_included_sd_x2": dict(biomass_excluded=set(), sd_factor={("R3", "X"): 2.0}),
        "Ks_0.2": dict(fixed={**fixed, "K_s": 0.2}),
        "Ks_5": dict(fixed={**fixed, "K_s": 5.0}),
        "CO2_floor_0": dict(co2_floor=0.0),
        "CO2_floor_0.5": dict(co2_floor=0.5),
    }
    rows = []
    for name, over in cases.items():
        pol = default_policy(fixed=over.pop("fixed", fixed), **over)
        assert HOLDOUT not in pol["train"]
        recs = make_records(pol["train"], runs, tc)
        best, results, counter = multistart(recs, pol, 8, args.seed + 1, extra_starts=[theta0])
        th = best["theta"]
        n_obs = len(residual_fn(recs, pol, dict(failures=0))(th))
        unc = linear_uncertainty(best["res"], th, n_obs)
        for i, n in enumerate(K.PARAM_NAMES):
            rows.append(dict(case=name, parameter=n, value=th[i], primary_value=theta0[i],
                             change_pct=100 * (th[i] - theta0[i]) / abs(theta0[i]),
                             change_in_primary_se=(th[i] - theta0[i]) / se0[n] if np.isfinite(se0[n]) else np.nan,
                             at_bound=bool(at_bound_mask(th)[i]), chi2=unc["chi2"], n_residuals=n_obs,
                             reduced_chi2=unc["red"], ode_failures=counter["failures"]))
        print(name, "chi2=%.1f N=%d red=%.2f" % (unc["chi2"], n_obs, unc["red"]))
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "level1_sensitivity.csv"), index=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/raw"); ap.add_argument("--root", default=".")
    ap.add_argument("--stage", choices=["fit", "predict", "sensitivity", "all"], default="all")
    ap.add_argument("--n-starts", type=int, default=N_STARTS); ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    if a.stage in ("fit", "all"): stage_fit(a)
    if a.stage in ("predict", "all"): stage_predict(a)
    if a.stage in ("sensitivity", "all"): stage_sensitivity(a)

if __name__ == "__main__":
    main()
