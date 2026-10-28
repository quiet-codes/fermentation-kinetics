#!/usr/bin/env python
"""Level 2 Task 2: parameter uncertainty and identifiability (training runs only; D-25).

Stages
  profile    --models M5,M0   profile likelihood of every fitted parameter (re-optimising the others) -> work/profile_<M>.json
  fixedgrid  --models M5,M0   K_s and n grids with the rest re-optimised -> work/fixedgrid_<M>.json
  r7         --models M5,M0   refit with R7 added (sensitivity; R6 never used) -> work/r7_<M>.json
  assemble   --models M5,M0   parameter_uncertainty.csv, parameter_profiles.csv, fixed_parameter_sensitivity.csv,
                              r7_inclusion_effect.csv, parameter_profiles.png, correlation table
Intervals: profile-likelihood interval at chi2_min + c_hat*3.84 (c_hat = the model's reduced chi-square, because the fit is
far from chi2 ~ dof) and, for reference, at chi2_min + 3.84 (valid only if the sds were exact). An interval that does not
close before a parameter bound is reported as OPEN, not as a number. Jackknife = leave-one-training-run-out refits (from compare.py loro).
"""
import argparse, json, os, sys, time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare as C, fit, models as M

MULT = [1, 2, 3.5, 5.5, 8, 12, 18, 26]


def load_fit(w, v): return json.load(open(os.path.join(w, f"fit_{v}.json"), encoding="utf-8"))


def refit_fixed(variant, fun_full, theta_start, idx, val, lo, hi, max_nfev=80):
    n = len(theta_start); free = [i for i in range(n) if i != idx]
    base = theta_start.copy(); base[idx] = val

    def f(phi):
        th = base.copy(); th[free] = phi; return fun_full(th)
    r = least_squares(f, np.clip(base[free], lo[free], hi[free]), bounds=(lo[free], hi[free]), x_scale="jac", diff_step=1e-6,
                      ftol=1e-9, xtol=1e-9, gtol=1e-9, max_nfev=max_nfev)
    th = base.copy(); th[free] = r.x
    return 2 * r.cost, th


def stage_profile(a):
    t, w, fdir = C.dirs(a.root); runs, tc = C.load_data(a.data_dir); policy = fit.default_policy(); recs = fit.make_records(policy["train"], runs, tc)
    for v in a.models.split(","):
        fj = load_fit(w, v); names, start, lo, hi, *_ = M.spec(v); th0 = np.array(fj["theta"]); chi0 = fj["chi2"]; c_hat = fj["red"]
        fun = C.resid_fun(v, recs, policy, dict(failures=0)); thr_s = c_hat * 3.84
        cov = np.array([[np.nan if x is None else x for x in row] for row in fj["cov"]]); se = np.sqrt(np.diag(cov)); out = {}
        t0 = time.time()
        for i, nm in enumerate(names):
            scale = se[i] if np.isfinite(se[i]) else 0.05 * (hi[i] - lo[i]); scale = max(scale, 0.02 * abs(th0[i]), 1e-4)
            pts = [dict(value=th0[i], chi2=chi0, theta=th0.tolist())]
            for sgn in (+1, -1):
                prev = th0.copy(); cum = 0.0
                for m in MULT:
                    cum_target = m * scale; val = th0[i] + sgn * cum_target
                    val = min(max(val, lo[i]), hi[i]); hitb = (val <= lo[i] + 1e-12) or (val >= hi[i] - 1e-12)
                    if any(abs(val - p["value"]) < 1e-12 for p in pts): break
                    chi2, th = refit_fixed(v, fun, prev, i, val, lo, hi); prev = th
                    pts.append(dict(value=val, chi2=chi2, theta=th.tolist(), at_param_bound=bool(hitb)))
                    if chi2 - chi0 > 3 * thr_s or hitb: break
            pts.sort(key=lambda p: p["value"]); out[nm] = pts
            print(v, nm, "%d pts, %.0fs" % (len(pts), time.time() - t0), flush=True)
        json.dump(dict(variant=v, names=names, chi0=chi0, c_hat=c_hat, profiles=out), open(os.path.join(w, f"profile_{v}.json"), "w", encoding="utf-8", newline="\n"))


def crossing(pts, chi0, thr, side):
    """first crossing of chi2-chi0 = thr going away from the optimum; returns (value, open_flag, bound_value)."""
    vals = [p["value"] for p in pts]; d = [p["chi2"] - chi0 for p in pts]; k0 = int(np.argmin(d))
    rng = range(k0 + 1, len(pts)) if side > 0 else range(k0 - 1, -1, -1)
    prev = k0
    for k in rng:
        if d[k] >= thr:
            x0, x1 = vals[prev], vals[k]; s0, s1 = np.sqrt(max(d[prev], 0)), np.sqrt(d[k])
            f = (np.sqrt(thr) - s0) / (s1 - s0) if s1 > s0 else 1.0
            return x0 + f * (x1 - x0), False, None
        prev = k
    edge = vals[-1] if side > 0 else vals[0]
    return None, True, edge


def stage_fixedgrid(a):
    t, w, fdir = C.dirs(a.root); runs, tc = C.load_data(a.data_dir); recs = fit.make_records(fit.default_policy()["train"], runs, tc)
    for v in a.models.split(","):
        fj = load_fit(w, v); th0 = np.array(fj["theta"]); rows = []
        grids = {"K_s": [0.05, 0.2, 1.0, 5.0, 20.0]}
        if not M.VARIANTS[v]["n_free"]: grids["n_inh"] = [0.5, 1.0, 1.5, 2.0, 3.0]
        for pname, vals in grids.items():
            for val in vals:
                pol = fit.default_policy(fixed={**M.FIXED_DEFAULT, pname: val})
                best, out, counter, fun = C.fit_variant(v, recs, pol, n_lhs=0, warm=th0, max_nfev=150)
                nm = M.spec(v)[0]
                rows.append(dict(model=v, fixed_parameter=pname, value=val, chi2=best["chi2"], delta_chi2=best["chi2"] - fj["chi2"], delta_chi2_over_chat=(best["chi2"] - fj["chi2"]) / fj["red"],
                                 **{k: float(x) for k, x in zip(nm, best["theta"])}, params_at_bound=int(C.at_bound(best["theta"], *M.spec(v)[2:4]).sum())))
                print(v, pname, val, round(best["chi2"], 1), flush=True)
        json.dump(rows, open(os.path.join(w, f"fixedgrid_{v}.json"), "w", encoding="utf-8", newline="\n"))


def stage_r7(a):
    t, w, fdir = C.dirs(a.root); runs, tc = C.load_data(a.data_dir)
    for v in a.models.split(","):
        fj = load_fit(w, v); th0 = np.array(fj["theta"]); names, start, lo, hi, *_ = M.spec(v)
        pol = fit.default_policy(train=fit.TRAIN + ["R7"]); recs = fit.make_records(pol["train"], runs, tc)
        best, out, counter, fun = C.fit_variant(v, recs, pol, n_lhs=0, warm=th0, max_nfev=300)
        n_obs = len(fun(best["theta"]))
        json.dump(dict(variant=v, names=names, theta=best["theta"].tolist(), chi2=best["chi2"], n_obs=n_obs, red=best["chi2"] / (n_obs - len(names)), at_bound=C.at_bound(best["theta"], lo, hi).tolist()),
                  open(os.path.join(w, f"r7_{v}.json"), "w", encoding="utf-8", newline="\n"))
        print(v, "with R7: chi2=%.1f N=%d red=%.2f" % (best["chi2"], n_obs, best["chi2"] / (n_obs - len(names))), flush=True)


def classify(row):
    if row["status"] != "fitted": return "fixed (not estimated)"
    if row["ci_open_lo"] or row["ci_open_hi"]: return "NOT determined (profile interval open to a bound)"
    if row.get("max_abs_corr", 0) >= 0.9: return "determined only jointly (ridge, |r| >= 0.9 with " + str(row.get("max_corr_partner")) + ")"
    if row["parameter"] == "k37": return "determined by ONE run (R8): precision is conditional, no replication"
    rel = (row["ci_hi"] - row["ci_lo"]) / (2 * abs(row["value"])); jk = row.get("jackknife_rel_sd", np.nan)
    if rel > 0.4: return "weakly determined (wide interval)"
    if np.isfinite(jk) and jk > rel: return "partly determined (run-to-run spread exceeds the within-fit interval)"
    return "determined (within this model structure)"


def stage_assemble(a):
    t, w, fdir = C.dirs(a.root); rows, prof_rows, fx_rows, r7_rows, corr_rows = [], [], [], [], []
    fr = json.load(open(os.path.join(t, "model_selection_frozen.json"), encoding="utf-8"))
    for v in a.models.split(","):
        fj = load_fit(w, v); pj = json.load(open(os.path.join(w, f"profile_{v}.json"), encoding="utf-8")); names, start, lo, hi, units, desc = M.spec(v)
        cov = np.array([[np.nan if x is None else x for x in row] for row in fj["cov"]]); se = np.sqrt(np.diag(cov)); th0 = np.array(fj["theta"])
        loro = json.load(open(os.path.join(w, f"loro_{v}.json"), encoding="utf-8")); chi0, c_hat = pj["chi0"], pj["c_hat"]
        sd_ = np.sqrt(np.diag(cov)); corr = cov / np.outer(sd_, sd_)
        for i, nm in enumerate(names):
            pts = pj["profiles"][nm]
            for p in pts: prof_rows.append(dict(model=v, parameter=nm, value=p["value"], chi2=p["chi2"], delta_chi2=p["chi2"] - chi0, delta_over_chat=(p["chi2"] - chi0) / c_hat))
            lo_s, olo, elo = crossing(pts, chi0, c_hat * 3.84, -1); hi_s, ohi, ehi = crossing(pts, chi0, c_hat * 3.84, +1)
            lo_n, onlo, _ = crossing(pts, chi0, 3.84, -1); hi_n, onhi, _ = crossing(pts, chi0, 3.84, +1)
            jk = [r["theta"][i] for r in loro if not (nm == "k37" and r["held_out_run"] == "R8")]
            jk = np.array(jk); jsd = float(np.sqrt((len(jk) - 1) / len(jk) * np.sum((jk - jk.mean()) ** 2))) if len(jk) > 2 else np.nan
            big = [(names[j], corr[i, j]) for j in range(len(names)) if j != i and np.isfinite(corr[i, j]) and abs(corr[i, j]) >= 0.7]
            row = dict(model=v, preferred_by_D24=(v == fr["preferred"]), parameter=nm, value=th0[i], unit=units[i], status="fitted", method="weighted NLS (multistart); profile likelihood, Delta chi2 = c_hat*3.84",
                       ci_lo=lo_s if lo_s is not None else np.nan, ci_hi=hi_s if hi_s is not None else np.nan, ci_open_lo=olo, ci_open_hi=ohi,
                       ci_lo_if_open_searched_to=elo, ci_hi_if_open_searched_to=ehi, bound_lo=lo[i], bound_hi=hi[i],
                       ci_nominal_lo=lo_n if lo_n is not None else np.nan, ci_nominal_hi=hi_n if hi_n is not None else np.nan,
                       linear_se_scaled=se[i], linear_ci95_lo=th0[i] - 1.96 * se[i], linear_ci95_hi=th0[i] + 1.96 * se[i],
                       jackknife_sd=jsd, jackknife_n=len(jk), jackknife_rel_sd=jsd / abs(th0[i]) if np.isfinite(jsd) else np.nan,
                       jackknife_min=float(jk.min()), jackknife_max=float(jk.max()), correlated_with=("; ".join(f"{n} ({c:+.2f})" for n, c in big) or "none |r|>=0.7"),
                       c_hat=c_hat, note="")
            cs = [(abs(corr[i, j]), names[j]) for j in range(len(names)) if j != i and np.isfinite(corr[i, j])]
            row["max_abs_corr"], row["max_corr_partner"] = (max(cs) if cs else (0.0, ""))
            row["identifiability"] = classify(row)
            if nm == "k37": row["note"] = "rests on ONE run (R8); jackknife undefined when R8 dropped"
            rows.append(row)
        # fixed parameters
        for pn, val, un, why in (("K_s", 1.0, "g/L", "fixed a priori; see fixed_parameter_sensitivity.csv"), ("n_inh", 1.0, "-", "fixed at 1 (user decision); see fixed_parameter_sensitivity.csv")):
            if pn == "n_inh" and M.VARIANTS[v]["n_free"]: continue
            rows.append(dict(model=v, preferred_by_D24=(v == fr["preferred"]), parameter=pn, value=val, unit=un, status="fixed", method="not estimated; chi2 re-optimised on a grid", identifiability="fixed (not estimated)", note=why))
        fg = os.path.join(w, f"fixedgrid_{v}.json")
        if os.path.exists(fg): fx_rows += json.load(open(fg, encoding="utf-8"))
        r7f = os.path.join(w, f"r7_{v}.json")
        if os.path.exists(r7f):
            rj = json.load(open(r7f, encoding="utf-8")); pm = {r["parameter"]: r for r in rows if r["model"] == v and r["status"] == "fitted"}
            for i, nm in enumerate(names):
                r = pm[nm]; chg = rj["theta"][i] - th0[i]; half = (np.nanmax([r["ci_hi"] - th0[i], th0[i] - r["ci_lo"]]) if not (r["ci_open_lo"] or r["ci_open_hi"]) else np.nan)
                r7_rows.append(dict(model=v, parameter=nm, primary=th0[i], with_R7=rj["theta"][i], change_pct=100 * chg / abs(th0[i]), change_over_profile_halfwidth=chg / half if np.isfinite(half) else np.nan,
                                    chi2_primary=fj["chi2"], chi2_with_R7=rj["chi2"], N_primary=fj["n_obs"], N_with_R7=rj["n_obs"], reduced_chi2_primary=fj["red"], reduced_chi2_with_R7=rj["red"], at_bound_with_R7=rj["at_bound"][i]))
        for i, ni in enumerate(names):
            for j in range(i + 1, len(names)):
                if np.isfinite(corr[i, j]) and abs(corr[i, j]) >= 0.7: corr_rows.append(dict(model=v, parameter_1=ni, parameter_2=names[j], correlation_linearised=corr[i, j]))
    pd.DataFrame(rows).to_csv(os.path.join(t, "parameter_uncertainty.csv"), index=False, lineterminator='\n', encoding='utf-8')
    pd.DataFrame(prof_rows).to_csv(os.path.join(t, "parameter_profiles.csv"), index=False, lineterminator='\n', encoding='utf-8')
    if fx_rows: pd.DataFrame(fx_rows).to_csv(os.path.join(t, "fixed_parameter_sensitivity.csv"), index=False, lineterminator='\n', encoding='utf-8')
    if r7_rows: pd.DataFrame(r7_rows).to_csv(os.path.join(t, "r7_inclusion_effect.csv"), index=False, lineterminator='\n', encoding='utf-8')
    pd.DataFrame(corr_rows).to_csv(os.path.join(t, "parameter_correlations_material.csv"), index=False, lineterminator='\n', encoding='utf-8')
    pr = pd.DataFrame(prof_rows)
    for v in a.models.split(","):
        d = pr[pr.model == v]; ps = list(dict.fromkeys(d.parameter)); nc = 5; nr = int(np.ceil(len(ps) / nc))
        fig, ax = plt.subplots(nr, nc, figsize=(3.3 * nc, 2.7 * nr), squeeze=False)
        for k, nm in enumerate(ps):
            g = d[d.parameter == nm].sort_values("value"); x = ax[k // nc, k % nc]; x.plot(g.value, g.delta_over_chat, "o-", ms=3)
            x.axhline(3.84, color="r", ls="--", lw=0.8); x.set_title(nm, fontsize=9); x.set_ylim(0, 12); x.grid(alpha=0.3)
            if k % nc == 0: x.set_ylabel("Delta chi2 / c_hat")
        for k in range(len(ps), nr * nc): ax[k // nc, k % nc].axis("off")
        fig.suptitle(f"Profile likelihood, model {v} (red line = 95% threshold after scaling by c_hat = {load_fit(w, v)['red']:.2f}; curves leaving the panel exceed it)", fontsize=9)
        fig.tight_layout(rect=[0, 0, 1, 0.94]); fig.savefig(os.path.join(fdir, f"parameter_profiles_{v}.png"), dpi=130); plt.close(fig)
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(out[out.status == "fitted"][["model", "parameter", "value", "ci_lo", "ci_hi", "ci_open_lo", "ci_open_hi", "linear_se_scaled", "jackknife_rel_sd", "identifiability"]].round(4).to_string(index=False))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--stage", required=True, choices=["profile", "fixedgrid", "r7", "assemble"])
    ap.add_argument("--models", default="M5,M0"); ap.add_argument("--data-dir", default="data/raw"); ap.add_argument("--root", default=".")
    a = ap.parse_args(); {"profile": stage_profile, "fixedgrid": stage_fixedgrid, "r7": stage_r7, "assemble": stage_assemble}[a.stage](a)


if __name__ == "__main__":
    main()
