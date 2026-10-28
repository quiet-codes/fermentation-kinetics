#!/usr/bin/env python
"""Level 2 Task 5: how parameter and structure uncertainty propagate to plant-relevant predictions, and which single
extra experiment would reduce it most. NOT an optimisation: the brief's margin formula is evaluated only at FIXED
scenarios (D-28) and nothing is recommended.

Margin per fermenter per day = (ethanol value - sugar cost - steam cost) / (batch time + 8 h), 170 m3, brief s4.
  batch ends when TRS <= 5 g/L (first crossing, simulated to 120 h; the data stop at 48 h so any end time beyond 48 h is
  an extrapolation in time); ethanol L/m3 = P/0.789; value 60 Rs/L; sugar 25 Rs/kg for ALL sugar charged; steam from the
  design curve (7-14 % v/v; outside it the value is clipped and flagged); steam 1600 Rs/t.
Temperature: scenarios at 33 and 36 C use the piecewise-linear multipliers (interpolation between 30/34/37 C, an assumption).

Stages
  ksens     plant predictions of M5 with K_s re-optimised on the fixed grid -> plant_Ks_sensitivity.csv
  discriminate  how strongly each candidate experiment separates the competing structures -> experiment_discrimination.csv
  predict   parameter ensembles (linearised-Gaussian draws; profile-ensemble band), structure spread across candidates,
            labelled secondary refit with R6 added -> plant_prediction_uncertainty.csv, structure_spread.csv
  design    linearised experimental-design criterion -> experiment_design.csv, variance_decomposition.csv, plant_uncertainty.png
"""
import argparse, json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare as C, fit, models as M

SCEN = [(33.0, 220.0), (34.0, 260.0), (36.0, 260.0), (37.0, 260.0)]
STEAM = np.array([[7, 3.15], [8, 2.94], [9, 2.77], [10, 2.64], [11, 2.53], [12, 2.44], [13, 2.36], [14, 2.29]])
TGRID = np.arange(0, 120.0001, 0.25)
V_M3, TURN, PRICE_E, COST_S, STEAM_RS_KG, RHO_E = 170.0, 8.0, 60.0, 25.0, 1.6, 0.789


def steam_per_L(P):
    wash = P / 7.89
    return float(np.interp(wash, STEAM[:, 0], STEAM[:, 1])), bool(wash < 7 or wash > 14), wash


def margin(variant, theta, T, S0, fixed=None, horizon=96.0):
    sim = M.simulate(variant, T, S0, 2.5, TGRID, theta, fixed)
    if sim is None: return None
    S = sim[:, 1]; k = np.where(S <= 5.0)[0]
    out = dict(S48=float(np.interp(48.0, TGRID, S)), P48=float(np.interp(48.0, TGRID, sim[:, 2])), S96=float(np.interp(96.0, TGRID, S)), P96=float(np.interp(96.0, TGRID, sim[:, 2])), X48=float(np.interp(48.0, TGRID, sim[:, 0])))
    if len(k) == 0 or k[0] == 0:
        out.update(t_end=np.nan, P_end=np.nan, wash=np.nan, daily_margin_Rs=np.nan, steam_extrap=False, feasible=False); return out
    i = k[0]; t_end = float(np.interp(5.0, [S[i], S[i - 1]], [TGRID[i], TGRID[i - 1]])) if S[i - 1] > S[i] else float(TGRID[i])
    P_end = float(np.interp(t_end, TGRID, sim[:, 2])); st, ext, wash = steam_per_L(P_end)
    L_per_m3 = P_end / RHO_E; value = L_per_m3 * PRICE_E; sugar = S0 * COST_S; steam = L_per_m3 * st * STEAM_RS_KG
    m_batch = (value - sugar - steam) * V_M3
    out.update(t_end=t_end, P_end=P_end, wash=wash, daily_margin_Rs=float(m_batch / (t_end + TURN) * 24.0), steam_extrap=ext, feasible=(t_end <= horizon))
    return out


def draw_ensemble(fj, names, lo, hi, n, rng):
    th0 = np.array(fj["theta"]); cov = np.array([[np.nan if x is None else x for x in r] for r in fj["cov"]])
    ok = np.isfinite(np.diag(cov)); out = []; tries = 0
    L = np.linalg.cholesky(cov[np.ix_(ok, ok)] + 1e-12 * np.eye(ok.sum()))
    while len(out) < n and tries < 20 * n:
        tries += 1; th = th0.copy(); th[ok] += L @ rng.standard_normal(ok.sum())
        if np.all(th >= lo) and np.all(th <= hi): out.append(th)
    return np.array(out), len(out) / tries


def summarise(vals, feas_total):
    v = np.array(vals, float); f = np.isfinite(v)
    return dict(n=feas_total, n_defined=int(f.sum()), frac_defined=float(f.mean()), median=float(np.nanmedian(v)) if f.any() else np.nan,
                lo=float(np.nanpercentile(v, 2.5)) if f.any() else np.nan, hi=float(np.nanpercentile(v, 97.5)) if f.any() else np.nan)


def stage_predict(a):
    t, w, fdir = C.dirs(a.root); runs, tc = C.load_data(a.data_dir); fr = json.load(open(os.path.join(t, "model_selection_frozen.json"), encoding="utf-8")); pref = fr["preferred"]
    rng = np.random.default_rng(20261028); rows = []; spread = []
    for v in (pref, "M0"):
        fj = C.json.load(open(os.path.join(w, f"fit_{v}.json"), encoding="utf-8")); names, start, lo, hi, *_ = M.spec(v); th0 = np.array(fj["theta"])
        ens, acc = draw_ensemble(fj, names, lo, hi, a.n_draws, rng)
        pj = C.json.load(open(os.path.join(w, f"profile_{v}.json"), encoding="utf-8")) if os.path.exists(os.path.join(w, f"profile_{v}.json")) else None
        prof_sets = []
        if pj:
            thr = pj["c_hat"] * 3.84
            for nm, pts in pj["profiles"].items():
                prof_sets += [np.array(p["theta"]) for p in pts if p["chi2"] - pj["chi0"] <= thr]
        for (T, S0) in SCEN:
            res = [margin(v, th, T, S0) for th in ens]; res = [r for r in res if r is not None]
            best = margin(v, th0, T, S0)
            pe = [margin(v, th, T, S0) for th in prof_sets] if prof_sets else []
            pe = [r for r in pe if r is not None]
            for key in ("P48", "S48", "S96", "t_end", "P_end", "wash", "daily_margin_Rs"):
                s = summarise([r[key] for r in res], len(res)); pr = [r[key] for r in pe]
                rows.append(dict(model=v, preferred=(v == pref), T_C=T, S0_gL=S0, quantity=key, point_estimate=best[key], ens_median=s["median"], ens_95_lo=s["lo"], ens_95_hi=s["hi"],
                                 ens_frac_defined=s["frac_defined"], n_draws=s["n"], profile_ensemble_min=float(np.nanmin(pr)) if pr and np.isfinite(pr).any() else np.nan,
                                 profile_ensemble_max=float(np.nanmax(pr)) if pr and np.isfinite(pr).any() else np.nan, n_profile_sets=len(pe),
                                 batch_ends_within_96h_point=bool(best["feasible"]), frac_draws_end_within_96h=float(np.mean([r["feasible"] for r in res])),
                                 steam_curve_extrapolated_point=bool(best["steam_extrap"]), temperature_interpolated=(T not in (30.0, 34.0, 37.0)),
                                 beyond_48h_data=bool(np.isfinite(best["t_end"]) and best["t_end"] > 48.0), gaussian_accept_rate=acc))
    # structure spread: every candidate at its own optimum
    for v in M.VARIANTS:
        fj = C.json.load(open(os.path.join(w, f"fit_{v}.json"), encoding="utf-8")); th0 = np.array(fj["theta"])
        for (T, S0) in SCEN:
            r = margin(v, th0, T, S0)
            spread.append(dict(model=v, k=fj["k"], reduced_chi2=fj["red"], params_at_bound=int(sum(fj["at_bound"])), T_C=T, S0_gL=S0, **{k: r[k] for k in ("P48", "S48", "S96", "t_end", "P_end", "wash", "daily_margin_Rs", "feasible")}))
    # labelled secondary: preferred model refitted with R6 added (R6 no longer blind; not used for selection)
    fj = C.json.load(open(os.path.join(w, f"fit_{pref}.json"), encoding="utf-8")); th0 = np.array(fj["theta"])
    pol = fit.default_policy(train=fit.TRAIN + ["R6"], allow_holdout_in_train=True); recs = fit.make_records(pol["train"], runs, tc)
    best, out, counter, fun = C.fit_variant(pref, recs, pol, n_lhs=0, warm=th0, max_nfev=300)
    for (T, S0) in SCEN:
        r = margin(pref, best["theta"], T, S0)
        spread.append(dict(model=pref + "+R6 refit (secondary, R6 used as training)", k=len(th0), reduced_chi2=best["chi2"] / (len(fun(best["theta"])) - len(th0)), params_at_bound=int(C.at_bound(best["theta"], *M.spec(pref)[2:4]).sum()), T_C=T, S0_gL=S0, **{k: r[k] for k in ("P48", "S48", "S96", "t_end", "P_end", "wash", "daily_margin_Rs", "feasible")}))
    pd.DataFrame(rows).to_csv(os.path.join(t, "plant_prediction_uncertainty.csv"), index=False, lineterminator='\n', encoding='utf-8'); pd.DataFrame(spread).to_csv(os.path.join(t, "structure_spread.csv"), index=False, lineterminator='\n', encoding='utf-8')
    pd.set_option("display.width", 250); d = pd.DataFrame(rows); print(d[d.quantity.isin(["P48", "S48", "t_end", "daily_margin_Rs"])][["model", "T_C", "S0_gL", "quantity", "point_estimate", "ens_median", "ens_95_lo", "ens_95_hi", "ens_frac_defined", "profile_ensemble_min", "profile_ensemble_max"]].round(1).to_string(index=False))
    print(pd.DataFrame(spread)[["model", "T_C", "S0_gL", "P48", "S48", "S96", "t_end", "daily_margin_Rs"]].round(1).to_string(index=False))


def num_grad(f, th, lo, hi, rel=1e-4):
    g = np.zeros(len(th))
    for i in range(len(th)):
        h = rel * max(abs(th[i]), 1e-3); tp, tm = th.copy(), th.copy(); tp[i] = min(th[i] + h, hi[i]); tm[i] = max(th[i] - h, lo[i])
        g[i] = (f(tp) - f(tm)) / (tp[i] - tm[i])
    return g


def stage_design(a):
    t, w, fdir = C.dirs(a.root); fr = json.load(open(os.path.join(t, "model_selection_frozen.json"), encoding="utf-8")); v = fr["preferred"]
    fj = C.json.load(open(os.path.join(w, f"fit_{v}.json"), encoding="utf-8")); names, start, lo, hi, *_ = M.spec(v); th0 = np.array(fj["theta"]); c_hat = fj["red"]
    cov = np.array([[np.nan if x is None else x for x in r] for r in fj["cov"]]); assert np.all(np.isfinite(cov)), "parameters at a bound: linearised design not defined"
    pol = fit.default_policy()
    # gradients of plant quantities
    targets = {}
    for (T, S0) in SCEN:
        for key in ("daily_margin_Rs", "S96", "P_end"):
            def f(th, T=T, S0=S0, key=key):
                r = margin(v, th, T, S0); return np.nan if r is None else r[key]
            base = f(th0)
            g = num_grad(f, th0, lo, hi) if np.isfinite(base) else np.full(len(th0), np.nan)
            targets[(T, S0, key)] = (base, g)
    rows = []; var_rows = []
    for (T, S0, key), (base, g) in targets.items():
        if not np.isfinite(base): continue
        var = g @ cov @ g; contrib = (g * (cov @ g))                     # additive (Euler) decomposition: sum = var
        rows.append(dict(T_C=T, S0_gL=S0, quantity=key, value=base, sd_linearised=np.sqrt(var), rel_sd_pct=100 * np.sqrt(var) / abs(base)))
        for n, c in zip(names, contrib): var_rows.append(dict(T_C=T, S0_gL=S0, quantity=key, parameter=n, variance_share_pct=100 * c / var))
    pd.DataFrame(rows).to_csv(os.path.join(t, "plant_linearised_sd.csv"), index=False, lineterminator='\n', encoding='utf-8'); vd = pd.DataFrame(var_rows); vd.to_csv(os.path.join(t, "variance_decomposition.csv"), index=False, lineterminator='\n', encoding='utf-8')
    # candidate experiments
    tdense = np.array([0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 30, 36, 42, 48.0]); t96 = np.concatenate([tdense, [60, 72, 84, 96.0]])
    cand = []; Sig_inv = np.linalg.inv(cov)
    for T in (33.0, 34.0, 36.0, 37.0):
        for S0 in (220.0, 260.0):
            for hz, tt in ((48, tdense), (96, t96)):
                sim0 = M.simulate(v, T, S0, 2.5, tt, th0, pol["fixed"]); J = []
                for j, var in enumerate(fit.VARS):
                    obs = sim0[1:, j]; sd = fit.sd_of(var, obs, pol)
                    cols = []
                    for i in range(len(th0)):
                        h = 1e-4 * max(abs(th0[i]), 1e-3); tp, tm = th0.copy(), th0.copy(); tp[i] = min(th0[i] + h, hi[i]); tm[i] = max(th0[i] - h, lo[i])
                        cols.append((M.simulate(v, T, S0, 2.5, tt, tp, pol["fixed"])[1:, j] - M.simulate(v, T, S0, 2.5, tt, tm, pol["fixed"])[1:, j]) / (tp[i] - tm[i]) / sd)
                    J.append(np.array(cols).T)
                J = np.vstack(J); post = np.linalg.inv(Sig_inv + J.T @ J / c_hat)
                d = dict(T_C=T, S0_gL=S0, horizon_h=hz, n_obs_new=J.shape[0])
                rel = []
                for (T2, S02, key), (base, g) in targets.items():
                    if key != "daily_margin_Rs" or not np.isfinite(base): continue
                    s0 = np.sqrt(g @ cov @ g); s1 = np.sqrt(g @ post @ g); d[f"margin_sd_Rs_day_{int(T2)}C_{int(S02)}"] = s1; d[f"margin_sd_reduction_pct_{int(T2)}C_{int(S02)}"] = 100 * (1 - s1 / s0); rel.append(1 - s1 / s0)
                for (T2, S02, key), (base, g) in targets.items():
                    if key != "S96" or not np.isfinite(base): continue
                    s0 = np.sqrt(g @ cov @ g); s1 = np.sqrt(g @ post @ g); d[f"TRS96_sd_reduction_pct_{int(T2)}C_{int(S02)}"] = 100 * (1 - s1 / s0)
                d["mean_margin_sd_reduction_pct"] = 100 * float(np.mean(rel)) if rel else np.nan; cand.append(d)
    cd = pd.DataFrame(cand).sort_values("mean_margin_sd_reduction_pct", ascending=False); cd.to_csv(os.path.join(t, "experiment_design.csv"), index=False, lineterminator='\n', encoding='utf-8')
    pd.set_option("display.width", 250)
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print(vd[vd.quantity == "daily_margin_Rs"].pivot_table(index="parameter", columns=["T_C", "S0_gL"], values="variance_share_pct").round(1).to_string())
    print(cd[["T_C", "S0_gL", "horizon_h", "mean_margin_sd_reduction_pct"] + [c for c in cd.columns if c.startswith("margin_sd_reduction")]].round(1).head(10).to_string(index=False))


def stage_ksens(a):
    t, w, fdir = C.dirs(a.root); fr = json.load(open(os.path.join(t, "model_selection_frozen.json"), encoding="utf-8")); v = fr["preferred"]
    rows = json.load(open(os.path.join(w, f"fixedgrid_{v}.json"), encoding="utf-8")); names = M.spec(v)[0]; out = []
    for r in rows:
        if r["fixed_parameter"] != "K_s": continue
        th = np.array([r[n] for n in names])
        for (T, S0) in SCEN:
            m = margin(v, th, T, S0, fixed={"K_s": r["value"]})
            out.append(dict(model=v, K_s=r["value"], chi2=r["chi2"], T_C=T, S0_gL=S0, **{k: m[k] for k in ("P48", "S48", "S96", "t_end", "P_end", "daily_margin_Rs", "feasible")}))
    pd.DataFrame(out).to_csv(os.path.join(t, "plant_Ks_sensitivity.csv"), index=False, lineterminator='\n', encoding='utf-8'); pd.set_option("display.width", 250)
    print(pd.DataFrame(out).round(1).to_string(index=False))


def stage_discriminate(a):
    t, w, fdir = C.dirs(a.root); fr = json.load(open(os.path.join(t, "model_selection_frozen.json"), encoding="utf-8")); pol = fit.default_policy()
    ths = {v: np.array(C.json.load(open(os.path.join(w, f"fit_{v}.json"), encoding="utf-8"))["theta"]) for v in ("M0", "M2", "M5", "M6")}
    tdense = np.array([0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 30, 36, 42, 48.0]); t96 = np.concatenate([tdense, [60, 72, 84, 96.0]]); rows = []
    for T in (33.0, 34.0, 36.0, 37.0):
        for S0 in (220.0, 260.0):
            for hz, tt in ((48, tdense), (96, t96)):
                sims = {v: M.simulate(v, T, S0, 2.5, tt, th, pol["fixed"]) for v, th in ths.items()}; d = dict(T_C=T, S0_gL=S0, horizon_h=hz)
                for a_, b_ in (("M5", "M2"), ("M5", "M6"), ("M2", "M6"), ("M5", "M0"), ("M2", "M0")):
                    tot = 0.0
                    for j, var in enumerate(fit.VARS):
                        sd = fit.sd_of(var, sims["M5"][1:, j], pol); tot += float(np.sum(((sims[a_][1:, j] - sims[b_][1:, j]) / sd) ** 2))
                    d[f"sep_{a_}_{b_}"] = tot
                d["min_sep_among_M2_M5_M6"] = min(d["sep_M5_M2"], d["sep_M5_M6"], d["sep_M2_M6"]); rows.append(d)
    df = pd.DataFrame(rows).sort_values("min_sep_among_M2_M5_M6", ascending=False); df.to_csv(os.path.join(t, "experiment_discrimination.csv"), index=False, lineterminator='\n', encoding='utf-8')
    pd.set_option("display.width", 250); print(df.round(0).to_string(index=False))


def stage_plot(a):
    t, w, fdir = C.dirs(a.root); sp = pd.read_csv(os.path.join(t, "structure_spread.csv")); pu = pd.read_csv(os.path.join(t, "plant_prediction_uncertainty.csv"))
    fr = json.load(open(os.path.join(t, "model_selection_frozen.json"), encoding="utf-8")); pref = fr["preferred"]
    models = [m for m in sp.model.unique() if "refit" not in m]; scen = SCEN
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8)); xs = np.arange(len(scen)); wd = 0.1
    for k, m in enumerate(models):
        d = sp[sp.model == m]
        for j, key in enumerate(("S96", "P48", "daily_margin_Rs")):
            y = [d[(d.T_C == T) & (d.S0_gL == S0)][key].iloc[0] for T, S0 in scen]
            ax[j].bar(xs + (k - len(models) / 2) * wd, y, wd, label=m, color="tab:red" if m == pref else None, alpha=0.9 if m == pref else 0.6)
    for j, key in enumerate(("S96", "P48", "daily_margin_Rs")):
        d = pu[(pu.model == pref) & (pu.quantity == key)]
        for i, (T, S0) in enumerate(scen):
            r = d[(d.T_C == T) & (d.S0_gL == S0)].iloc[0]
            if np.isfinite(r.ens_95_lo): ax[j].errorbar(i, r.ens_median, yerr=[[r.ens_median - r.ens_95_lo], [r.ens_95_hi - r.ens_median]], fmt="k_", capsize=5, lw=2)
        ax[j].set_xticks(xs); ax[j].set_xticklabels([f"{int(T)} C / {int(S0)}" for T, S0 in scen]); ax[j].grid(alpha=0.3, axis="y")
    ax[0].set_title("TRS at 96 h (g/L)", fontsize=10); ax[1].set_title("Ethanol at 48 h (g/L)", fontsize=10); ax[2].set_title("Daily margin (Rs/day)", fontsize=10)
    fig.suptitle(f"Fixed scenarios, not an optimisation. Bars = each candidate at its own optimum (red = {pref}, M3 sits at a parameter bound); black = {pref} parameter-ensemble 95% interval; missing margin bars = TRS <= 5 g/L not reached within 120 h", fontsize=9)
    ax[0].axhline(5, color="b", ls="--", lw=0.8); ax[0].legend(fontsize=7, ncol=2); fig.tight_layout(rect=[0, 0, 1, 0.93]); fig.savefig(os.path.join(fdir, "plant_uncertainty.png"), dpi=130); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--stage", required=True, choices=["predict", "design", "ksens", "discriminate", "plot"]); ap.add_argument("--n-draws", type=int, default=150)
    ap.add_argument("--data-dir", default="data/raw"); ap.add_argument("--root", default=".")
    a = ap.parse_args(); {"predict": stage_predict, "design": stage_design, "ksens": stage_ksens, "discriminate": stage_discriminate, "plot": stage_plot}[a.stage](a)


if __name__ == "__main__":
    main()
