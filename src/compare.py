#!/usr/bin/env python
"""Level 2 model comparison (Task 1). Training runs only; R6 and R7 are not loaded until the stated stages.

Stages
  fit      --models M0,M1,...   multistart WLS fit of each candidate on R1,R2,R3(no biomass),R4,R5,R8 -> work/fit_<M>.json
  loro     --models ...         leave-one-run-out cross-validation within the training runs -> work/loro_<M>.json
  select   assembles model_comparison.csv, candidate_parameters.csv, model_residuals.csv, applies the D-24 rule,
           writes the residual figure and model_selection_frozen.json (SHA-256 of the comparison table)
  r6diag   verifies the frozen hash, THEN loads R6 and reports an out-of-fit diagnostic for every candidate
           (never used for selection, D-22)
Usage: python src/compare.py --stage fit --models M0,M1 --data-dir data/raw --root .
"""
import argparse, json, os, sys, time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.stats import qmc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit, kinetics as K, models as M

PENALTY = 1.0e3
LOG_PARAMS = ("mu_max", "q_max")
TRAIN = list(fit.TRAIN)
MOST_COMPLEX = "M5"


def dirs(root):
    t = os.path.join(root, "outputs", "tables"); w = os.path.join(t, "work"); f = os.path.join(root, "outputs", "figures")
    for d in (t, w, f): os.makedirs(d, exist_ok=True)
    return t, w, f


def resid_fun(variant, records, policy, counter):
    def fun(theta):
        out = []
        for r in records:
            sim = M.simulate(variant, r["T"], r["S0"], r["X0"], r["t"], theta, policy["fixed"])
            pos = r["t"] > 0
            for j, v in enumerate(fit.VARS):
                if v == "X" and r["run"] in policy["biomass_excluded"]:
                    continue
                n = int(pos.sum())
                if sim is None:
                    counter["failures"] += 1; out.append(np.full(n, PENALTY)); continue
                obs = r["obs"][v][pos]
                sd = fit.sd_of(v, obs, policy) * policy["sd_factor"].get((r["run"], v), 1.0)
                out.append((sim[pos, j] - obs) / sd)
        return np.concatenate(out)
    return fun


def sample_starts(variant, n, seed):
    names, start, lo, hi, *_ = M.spec(variant)
    u = qmc.LatinHypercube(d=len(names), seed=seed).random(n)
    th = np.empty_like(u)
    for j, nm in enumerate(names):
        th[:, j] = np.exp(np.log(lo[j]) + u[:, j] * (np.log(hi[j]) - np.log(lo[j]))) if nm in LOG_PARAMS else lo[j] + u[:, j] * (hi[j] - lo[j])
    return th


def fit_variant(variant, records, policy, n_lhs=6, seed=1, warm=None, max_nfev=300, only_warm=False):
    names, start, lo, hi, *_ = M.spec(variant)
    counter = dict(failures=0)
    fun = resid_fun(variant, records, policy, counter)
    starts = [] if only_warm else [start.copy()]
    if warm is not None: starts.append(np.clip(np.asarray(warm, float), lo, hi))
    if n_lhs and not only_warm: starts += list(sample_starts(variant, n_lhs, seed))
    out = []
    for i, x0 in enumerate(starts):
        try:
            r = least_squares(fun, np.clip(x0, lo, hi), bounds=(lo, hi), method="trf", x_scale="jac", diff_step=1e-6,
                              ftol=1e-10, xtol=1e-10, gtol=1e-10, max_nfev=max_nfev)
            out.append(dict(chi2=2 * r.cost, theta=r.x, res=r, status=int(r.status), nfev=int(r.nfev)))
        except Exception as ex:
            out.append(dict(chi2=np.inf, theta=x0, res=None, status=-99, nfev=0, err=str(ex)))
    best = min(out, key=lambda d: d["chi2"])
    return best, out, counter, fun


def at_bound(theta, lo, hi, tol=1e-6):
    rng = hi - lo
    return (np.abs(theta - lo) < tol * rng) | (np.abs(theta - hi) < tol * rng)


def scaled_cov(res, theta, lo, hi, n_obs):
    ab = at_bound(theta, lo, hi); free = ~ab
    J = res.jac[:, free]; chi2 = 2 * res.cost; red = chi2 / (n_obs - len(theta))
    cov = np.full((len(theta), len(theta)), np.nan)
    idx = np.where(free)[0]
    cov[np.ix_(idx, idx)] = np.linalg.pinv(J.T @ J) * max(1.0, red)
    return cov, red


def load_data(data_dir):
    runs, tc = fit.read_raw(data_dir)
    return runs, tc


def stage_fit(a):
    t, w, f = dirs(a.root); runs, tc = load_data(a.data_dir)
    policy = fit.default_policy(); recs = fit.make_records(policy["train"], runs, tc)       # R6, R7 never loaded
    base = pd.read_csv(os.path.join(t, "level1_parameters.csv")); base = base[base.status == "fitted"].set_index("parameter")["value"]
    for vname in a.models.split(","):
        t0 = time.time(); names, start, lo, hi, *_ = M.spec(vname)
        warm = np.array([base[n] if n in base.index else s for n, s in zip(names, start)])   # Level 1 optimum as one start
        best, out, counter, fun = fit_variant(vname, recs, policy, n_lhs=a.n_lhs, seed=a.seed, warm=warm)
        n_obs = len(fun(best["theta"])); cov, red = scaled_cov(best["res"], best["theta"], lo, hi, n_obs)
        chi = np.array([d["chi2"] for d in out]); near = int(np.sum(chi <= best["chi2"] * 1.001 + 0.01))
        json.dump(dict(variant=vname, names=names, theta=best["theta"].tolist(), chi2=best["chi2"], n_obs=n_obs, k=len(names),
                       red=red, cov=np.where(np.isnan(cov), None, cov).tolist(), at_bound=at_bound(best["theta"], lo, hi).tolist(),
                       n_starts=len(out), n_near_best=near, chi2_all=chi.tolist(), failures=counter["failures"],
                       status=best["status"], runtime=round(time.time() - t0, 1)), open(os.path.join(w, f"fit_{vname}.json"), "w"))
        print(vname, "k=%d chi2=%.2f red=%.2f starts_near_best=%d/%d fail=%d %.0fs" % (len(names), best["chi2"], red, near, len(out), counter["failures"], time.time() - t0), flush=True)


def stage_loro(a):
    t, w, f = dirs(a.root); runs, tc = load_data(a.data_dir)
    policy = fit.default_policy()
    for vname in a.models.split(","):
        fj = json.load(open(os.path.join(w, f"fit_{vname}.json"))); th0 = np.array(fj["theta"]); rows = []
        for held in TRAIN:
            tr = [r for r in TRAIN if r != held]
            pol = fit.default_policy(train=tr)
            recs = fit.make_records(tr, runs, tc)
            best, out, counter, fun = fit_variant(vname, recs, pol, n_lhs=0, warm=th0, max_nfev=120)
            rec_h = fit.make_records([held], runs, tc)[0]
            sim = M.simulate(vname, rec_h["T"], rec_h["S0"], rec_h["X0"], rec_h["t"], best["theta"], policy["fixed"])
            pos = rec_h["t"] > 0; zs = {}
            for j, v in enumerate(fit.VARS):
                if v == "X" and held in policy["biomass_excluded"]: continue
                obs = rec_h["obs"][v][pos]; zs[v] = (sim[pos, j] - obs) / fit.sd_of(v, obs, policy)
            allz = np.concatenate(list(zs.values()))
            rows.append(dict(model=vname, held_out_run=held, chi2_per_point=float(np.mean(allz ** 2)), n=len(allz),
                             **{f"rms_z_{v}": float(np.sqrt(np.mean(z ** 2))) for v, z in zs.items()},
                             theta=best["theta"].tolist(), train_chi2=best["chi2"]))
        json.dump(rows, open(os.path.join(w, f"loro_{vname}.json"), "w"))
        print(vname, "LORO chi2/pt:", {r["held_out_run"]: round(r["chi2_per_point"], 1) for r in rows}, flush=True)


def qaicc(chi2, c_hat, k, n):
    return chi2 / c_hat + 2 * k + 2 * k * (k + 1) / (n - k - 1)


def residual_table(vname, theta, runs, tc, policy, ids):
    recs = fit.make_records(ids, runs, tc); rows = []
    for r in recs:
        sim = M.simulate(vname, r["T"], r["S0"], r["X0"], r["t"], theta, policy["fixed"])
        for j, v in enumerate(fit.VARS):
            obs = r["obs"][v]; sd = fit.sd_of(v, obs, policy)
            for k, tt in enumerate(r["t"]):
                if tt > 0:
                    rows.append(dict(model=vname, run=r["run"], variable=v, time_h=tt, observed=obs[k], predicted=sim[k, j],
                                     z=(sim[k, j] - obs[k]) / sd[k], in_objective=not (v == "X" and r["run"] in policy["biomass_excluded"])))
    return pd.DataFrame(rows)


def lag1(z):
    z = np.asarray(z); return float(np.sum(z[1:] * z[:-1]) / np.sum(z ** 2))


def stage_select(a):
    t, w, fdir = dirs(a.root); runs, tc = load_data(a.data_dir); policy = fit.default_policy()
    fits = {v: json.load(open(os.path.join(w, f"fit_{v}.json"))) for v in M.VARIANTS}
    c_hat = fits[MOST_COMPLEX]["red"]; N = fits[MOST_COMPLEX]["n_obs"]
    rows, prow, resid = [], [], []
    for v, fj in fits.items():
        th = np.array(fj["theta"]); rt = residual_table(v, th, runs, tc, policy, TRAIN); rt = rt[rt.in_objective]; resid.append(rt)
        loro = json.load(open(os.path.join(w, f"loro_{v}.json"))) if os.path.exists(os.path.join(w, f"loro_{v}.json")) else None
        ls = {}
        if loro:
            c = {r["held_out_run"]: r["chi2_per_point"] for r in loro}
            ls = dict(loro_chi2pt_mean_all=np.mean(list(c.values())), loro_chi2pt_mean_excl_R8=np.mean([x for k, x in c.items() if k != "R8"]),
                      loro_chi2pt_R8=c["R8"])
        ser = [lag1(g.sort_values("time_h").z) for _, g in rt.groupby(["run", "variable"])]
        pv = rt.groupby("variable").z.agg(lambda z: np.sqrt(np.mean(z ** 2)))
        mz = rt.groupby("variable").z.mean()
        k = fj["k"]
        rows.append(dict(model=v, description=M.VARIANTS[v]["label"], k_params=k, chi2=fj["chi2"], n_obs=fj["n_obs"], reduced_chi2=fj["red"],
                         AIC_unscaled=fj["chi2"] + 2 * k, BIC_unscaled=fj["chi2"] + k * np.log(fj["n_obs"]),
                         QAICc=qaicc(fj["chi2"], c_hat, k, N), c_hat_used=c_hat, params_at_bound=int(sum(fj["at_bound"])),
                         starts_near_best=f"{fj['n_near_best']}/{fj['n_starts']}", ode_failures=fj["failures"],
                         mean_lag1_autocorr=float(np.mean(ser)), rms_z_X=pv["X"], rms_z_S=pv["S"], rms_z_P=pv["P"], rms_z_C=pv["C"],
                         mean_z_X=mz["X"], mean_z_S=mz["S"], mean_z_P=mz["P"], mean_z_C=mz["C"], **ls))
        for n, val, ab in zip(fj["names"], fj["theta"], fj["at_bound"]):
            _, _, lo, hi, unit, _ = M.spec(v)
            i = fj["names"].index(n); se = np.sqrt(fj["cov"][i][i]) if fj["cov"][i][i] is not None else np.nan
            prow.append(dict(model=v, parameter=n, value=val, unit=unit[i], lower=lo[i], upper=hi[i], at_bound=bool(ab), se_linear_scaled=se))
    cmp = pd.DataFrame(rows)
    cmp["delta_QAICc"] = cmp.QAICc - cmp.QAICc.min()
    # D-24 rule
    ok = cmp[(cmp.params_at_bound == 0) & (cmp.ode_failures == 0)]
    best = ok.loc[ok.QAICc.idxmin()]
    close = ok[(ok.QAICc - best.QAICc <= 4) & (ok.k_params < best.k_params)]
    pref = close.loc[close.k_params.idxmin()] if len(close) else best
    cmp["selected_by_D24"] = cmp.model == pref.model
    cmp["note"] = ""
    cmp.loc[cmp.model == "M0", "note"] = "Level 1 baseline (preserved)"
    cmp.to_csv(os.path.join(t, "model_comparison.csv"), index=False)
    pd.DataFrame(prow).to_csv(os.path.join(t, "candidate_parameters.csv"), index=False)
    pd.concat(resid).to_csv(os.path.join(t, "model_residuals.csv"), index=False)
    fr = dict(preferred=pref.model, best_QAICc_model=best.model, rule="D-24", c_hat=c_hat, model_comparison_sha256=fit.sha256(os.path.join(t, "model_comparison.csv")),
              candidate_parameters_sha256=fit.sha256(os.path.join(t, "candidate_parameters.csv")), r6_used_for_selection=False)
    json.dump(fr, open(os.path.join(t, "model_selection_frozen.json"), "w"), indent=2)
    # figure: QAICc and pooled residual-vs-time for M0 and the preferred model
    allr = pd.concat(resid)
    fig, ax = plt.subplots(2, 4, figsize=(16, 7), gridspec_kw=dict(height_ratios=[1, 1.2]))
    for j, v in enumerate(fit.VARS):
        for m, col in (("M0", "tab:gray"), (pref.model, "tab:red")):
            g = allr[(allr.model == m) & (allr.variable == v)].groupby("time_h").z.mean()
            ax[0, j].plot(g.index, g.values, "o-", color=col, label=f"{m} mean z over runs", ms=3)
        ax[0, j].axhline(0, color="k", lw=0.6); ax[0, j].set_title(fit.LABEL[v]); ax[0, j].set_xlabel("Time (h)"); ax[0, j].grid(alpha=0.3)
    ax[0, 0].set_ylabel("mean z = (model-data)/sd"); ax[0, 0].legend(fontsize=7)
    for j, v in enumerate(fit.VARS):
        bars = [cmp.set_index("model").loc[m, f"rms_z_{v}"] for m in M.VARIANTS]
        ax[1, j].bar(list(M.VARIANTS), bars, color=["tab:red" if m == pref.model else "tab:gray" for m in M.VARIANTS]); ax[1, j].set_ylabel(f"rms z, {v}")
        ax[1, j].grid(alpha=0.3, axis="y")
    fig.suptitle(f"Training residuals (R3 biomass excluded): Level 1 baseline M0 vs {pref.model} (D-24 choice); bars = rms z per candidate"); fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(fdir, "model_comparison_residuals.png"), dpi=140); plt.close(fig)
    pd.set_option("display.width", 220)
    print(cmp[["model", "k_params", "chi2", "reduced_chi2", "QAICc", "delta_QAICc", "params_at_bound", "starts_near_best", "loro_chi2pt_mean_excl_R8", "loro_chi2pt_R8", "selected_by_D24"]].round(2).to_string(index=False))
    print("preferred:", pref.model)


def stage_r6diag(a):
    t, w, fdir = dirs(a.root)
    fr = json.load(open(os.path.join(t, "model_selection_frozen.json")))
    if fit.sha256(os.path.join(t, "model_comparison.csv")) != fr["model_comparison_sha256"] or fit.sha256(os.path.join(t, "candidate_parameters.csv")) != fr["candidate_parameters_sha256"]:
        raise SystemExit("selection tables changed after freezing; refusing to look at R6")
    runs, tc = load_data(a.data_dir); policy = fit.default_policy()
    rec = fit.make_records(["R6"], runs, tc)[0]; cp = pd.read_csv(os.path.join(t, "candidate_parameters.csv")); rows = []
    for v in M.VARIANTS:
        th = cp[cp.model == v].set_index("parameter").loc[M.spec(v)[0], "value"].to_numpy()
        sim = M.simulate(v, rec["T"], rec["S0"], rec["X0"], rec["t"], th, policy["fixed"]); pos = rec["t"] > 0; d = dict(model=v, preferred=(v == fr["preferred"]))
        for j, var in enumerate(fit.VARS):
            obs = rec["obs"][var][pos]; z = (sim[pos, j] - obs) / fit.sd_of(var, obs, policy)
            d[f"rms_z_{var}"] = float(np.sqrt(np.mean(z ** 2))); d[f"mean_z_{var}"] = float(np.mean(z))
        d["TRS_48h_pred"] = sim[-1, 1]; d["TRS_48h_obs"] = rec["obs"]["S"][-1]; d["EtOH_48h_pred"] = sim[-1, 2]; d["EtOH_48h_obs"] = rec["obs"]["P"][-1]
        rows.append(d)
    out = pd.DataFrame(rows); out["note"] = "out-of-fit diagnostic only; not used for selection (D-22)"
    out.to_csv(os.path.join(t, "model_r6_diagnostic.csv"), index=False)
    print(out.round(2).to_string(index=False))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--stage", required=True, choices=["fit", "loro", "select", "r6diag"])
    ap.add_argument("--models", default=",".join(M.VARIANTS)); ap.add_argument("--data-dir", default="data/raw"); ap.add_argument("--root", default=".")
    ap.add_argument("--n-lhs", type=int, default=6); ap.add_argument("--seed", type=int, default=20261027)
    a = ap.parse_args()
    {"fit": stage_fit, "loro": stage_loro, "select": stage_select, "r6diag": stage_r6diag}[a.stage](a)


if __name__ == "__main__":
    main()
