#!/usr/bin/env python
"""Level 2 Tasks 3-4: carbon balance for all eight runs, ethanol yields, yield-gap decomposition, R7 review.
Raw CSVs only (no model). All eight runs are kept regardless of the fitting decisions.

Conventions (D-26, D-27)
  C-mol/L: TRS/180.16*6 ; biomass/24.6 ; ethanol/46.07*2 ; CO2/44.01 ; glycerol/92.09*3 ; lactic/90.08*3.
  Input  = measured t=0 TRS (as glucose) + inoculum biomass from runs.csv.
  Output = 48 h TRS + 48 h biomass + ethanol + cumulative CO2 + glycerol + lactic acid.
  n.d. lactic acid = uniform on [0, 0.2) g/L (central value 0.1), not zero.
  Monte-Carlo (20,000 draws, fixed seed) from the brief's sds: biomass 3.5%+0.08, TRS 1%+0.4, ethanol 1.2%+0.25,
  CO2 2%, glycerol/lactic 3%. t=0 TRS and inoculum are drawn with the TRS/biomass sds respectively (conservative).
  The R3 biomass sd is the DW formula but its OD600 calibration uncertainty is unknown (not quantified).
Limitations (not corrected): unmeasured organic carbon in molasses (input), unmeasured by-products (output),
dissolved CO2/bicarbonate (output), biomass composition fixed at 24.6 g/C-mol (brief), inoculum recorded not measured.
"""
import argparse, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

M_GLU, M_ETOH, M_CO2, M_GLY, M_LAC, M_X = 180.16, 46.07, 44.01, 92.09, 90.08, 24.6
YTHEORY = 2 * M_ETOH / M_GLU            # 0.5114 g ethanol / g glucose
NMC, SEED = 20000, 20261027
RUNS = [f"R{i}" for i in range(1, 9)]


def sd_X(x): return 0.035 * x + 0.08
def sd_S(s): return 0.01 * s + 0.4
def sd_P(e): return 0.012 * e + 0.25
def sd_C(c): return 0.02 * c


def load(data_dir):
    runs = pd.read_csv(os.path.join(data_dir, "runs.csv")).set_index("run")
    tc = pd.read_csv(os.path.join(data_dir, "timecourse.csv"))
    hp = pd.read_csv(os.path.join(data_dir, "endpoint_hplc.csv"), dtype={"lactic_acid_g_L": str}).set_index("run")
    d = {}
    for r in RUNS:
        g = tc[tc.run == r].set_index("time_h")
        lac_txt = hp.loc[r, "lactic_acid_g_L"].strip()
        d[r] = dict(T=float(runs.loc[r, "temperature_C"]), S0_nom=float(runs.loc[r, "initial_TRS_g_L_as_glucose"]), X0=float(runs.loc[r, "inoculum_biomass_g_L"]),
                    S0=float(g.loc[0, "TRS_g_L_as_glucose"]), X0_meas=float(g.loc[0, "biomass_g_L"]),
                    S48=float(g.loc[48, "TRS_g_L_as_glucose"]), X48=float(g.loc[48, "biomass_g_L"]), E=float(g.loc[48, "ethanol_g_L"]),
                    C=float(g.loc[48, "CO2_evolved_g_per_L"]), G=float(hp.loc[r, "glycerol_g_L"]),
                    L_nd=(lac_txt.lower() == "n.d."), L=(None if lac_txt.lower() == "n.d." else float(lac_txt)), pH=float(hp.loc[r, "final_pH"]))
    return d


def cmol(S0, X0, S48, X48, E, C, G, L):
    c = dict(in_sugar=S0 / M_GLU * 6, in_biomass=X0 / M_X, out_sugar=S48 / M_GLU * 6, out_biomass=X48 / M_X, out_ethanol=E / M_ETOH * 2,
             out_CO2=C / M_CO2, out_glycerol=G / M_GLY * 3, out_lactic=L / M_LAC * 3)
    c["C_in"] = c["in_sugar"] + c["in_biomass"]
    c["C_out"] = c["out_sugar"] + c["out_biomass"] + c["out_ethanol"] + c["out_CO2"] + c["out_glycerol"] + c["out_lactic"]
    c["unaccounted"] = c["C_in"] - c["C_out"]
    c["recovery_pct"] = 100 * c["C_out"] / c["C_in"]
    cons = c["in_sugar"] - c["out_sugar"]
    c["C_consumed_sugar"] = cons
    c["recovery_consumed_basis_pct"] = 100 * (c["out_biomass"] - c["in_biomass"] + c["out_ethanol"] + c["out_CO2"] + c["out_glycerol"] + c["out_lactic"]) / cons
    c["molE"] = E / M_ETOH
    return c


def lactic_central(r): return 0.1 if r["L_nd"] else r["L"]


def draws(r, rng, n=NMC, lac="mc"):
    S0 = np.maximum(rng.normal(r["S0"], sd_S(r["S0"]), n), 0); X0 = np.maximum(rng.normal(r["X0"], sd_X(r["X0"]), n), 0)
    S48 = np.maximum(rng.normal(r["S48"], sd_S(r["S48"]), n), 0); X48 = np.maximum(rng.normal(r["X48"], sd_X(r["X48"]), n), 0)
    E = np.maximum(rng.normal(r["E"], sd_P(r["E"]), n), 0); C = np.maximum(rng.normal(r["C"], sd_C(r["C"]), n), 0)
    G = np.maximum(rng.normal(r["G"], 0.03 * r["G"], n), 0)
    L = rng.uniform(0, 0.2, n) if r["L_nd"] else np.maximum(rng.normal(r["L"], 0.03 * r["L"], n), 0)
    return S0, X0, S48, X48, E, C, G, L


def q(x): return float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))


def balance_tables(d):
    rng = np.random.default_rng(SEED); rows, yrows, drows = [], [], []
    for r in RUNS:
        x = d[r]; Lc = lactic_central(x)
        c = cmol(x["S0"], x["X0"], x["S48"], x["X48"], x["E"], x["C"], x["G"], Lc)
        S0, X0, S48, X48, E, C, G, L = draws(x, rng)
        mc = cmol(S0, X0, S48, X48, E, C, G, L)
        # sensitivities (central values)
        sens = dict(
            recovery_pct_nominal_S0=cmol(x["S0_nom"], x["X0"], x["S48"], x["X48"], x["E"], x["C"], x["G"], Lc)["recovery_pct"],
            recovery_pct_measured_X0=cmol(x["S0"], x["X0_meas"], x["S48"], x["X48"], x["E"], x["C"], x["G"], Lc)["recovery_pct"],
            recovery_pct_lactic_nd_as_0=cmol(x["S0"], x["X0"], x["S48"], x["X48"], x["E"], x["C"], x["G"], 0.0 if x["L_nd"] else x["L"])["recovery_pct"],
            recovery_pct_lactic_nd_as_0p2=cmol(x["S0"], x["X0"], x["S48"], x["X48"], x["E"], x["C"], x["G"], 0.2 if x["L_nd"] else x["L"])["recovery_pct"],
            recovery_pct_lactic_removed=cmol(x["S0"], x["X0"], x["S48"], x["X48"], x["E"], x["C"], x["G"], 0.0)["recovery_pct"])
        lo, hi = q(mc["recovery_pct"]); ulo, uhi = q(mc["unaccounted"]); clo, chi = q(mc["recovery_consumed_basis_pct"])
        rows.append(dict(run=r, T_C=x["T"], S0_TRS_measured=x["S0"], inoculum_X0=x["X0"], lactic_used_g_L=Lc, lactic_is_nd=x["L_nd"],
                         C_in_sugar_Cmol_L=c["in_sugar"], C_in_inoculum_Cmol_L=c["in_biomass"], C_in_total_Cmol_L=c["C_in"],
                         C_out_residual_sugar=c["out_sugar"], C_out_biomass=c["out_biomass"], C_out_ethanol=c["out_ethanol"], C_out_CO2=c["out_CO2"],
                         C_out_glycerol=c["out_glycerol"], C_out_lactic=c["out_lactic"], C_out_total_Cmol_L=c["C_out"],
                         unaccounted_Cmol_L=c["unaccounted"], unaccounted_pct_of_input=100 * c["unaccounted"] / c["C_in"],
                         unaccounted_g_C_L=c["unaccounted"] * 12.011, recovery_pct=c["recovery_pct"], recovery_mc_mean=float(np.mean(mc["recovery_pct"])),
                         recovery_mc_sd=float(np.std(mc["recovery_pct"])), recovery_95_lo=lo, recovery_95_hi=hi,
                         unaccounted_95_lo_Cmol_L=ulo, unaccounted_95_hi_Cmol_L=uhi,
                         recovery_consumed_basis_pct=c["recovery_consumed_basis_pct"], recovery_consumed_95_lo=clo, recovery_consumed_95_hi=chi,
                         closes_within_95=bool(lo <= 100 <= hi), **sens,
                         in_primary_fit={"R6": "held out", "R7": "excluded"}.get(r, "yes"), note=("R3 biomass by OD600 (calibration uncertainty not quantified)" if r == "R3" else "")))
        # yields
        dS = x["S0"] - x["S48"]; dS_nom = x["S0_nom"] - x["S48"]; dX = x["X48"] - x["X0"]
        y = x["E"] / dS; ymc = E / np.maximum(S0 - S48, 1e-9)
        cat = x["E"] / (dS - 1.2206 * dX)
        yrows.append(dict(run=r, TRS_consumed_g_L=dS, ethanol_g_L=x["E"], yield_g_per_g=y, yield_95_lo=q(ymc)[0], yield_95_hi=q(ymc)[1],
                          yield_pct_of_theory=100 * y / YTHEORY, yield_nominalS0=x["E"] / dS_nom, yield_catabolic_after_biomass_sugar=cat,
                          theory=YTHEORY, residual_TRS_48h=x["S48"], sugar_exhausted=bool(x["S48"] < 1.0), in_primary_fit=rows[-1]["in_primary_fit"]))
        # exact decomposition of the carbon not routed through ethanol (+ its paired CO2); components as % of consumed sugar carbon
        def comp(cc):
            Cc = cc["C_consumed_sugar"]; molE = cc["molE"]
            return dict(gap_total=100 * (Cc - 3 * molE) / Cc, biomass=100 * (cc["out_biomass"] - cc["in_biomass"]) / Cc, glycerol=100 * cc["out_glycerol"] / Cc,
                        lactic=100 * cc["out_lactic"] / Cc, excess_CO2=100 * (cc["out_CO2"] - molE) / Cc,
                        unaccounted=100 * (Cc - ((cc["out_biomass"] - cc["in_biomass"]) + cc["out_ethanol"] + cc["out_CO2"] + cc["out_glycerol"] + cc["out_lactic"])) / Cc)
        cd = comp(c); cm = comp(mc)
        drow = dict(run=r, yield_pct_of_theory=100 * y / YTHEORY, gap_pct_of_consumed_carbon=cd["gap_total"])
        for k in ("biomass", "glycerol", "lactic", "excess_CO2", "unaccounted"):
            drow[f"{k}_pct_pts"] = cd[k]; drow[f"{k}_95_lo"], drow[f"{k}_95_hi"] = q(cm[k])
        drow["check_sum_minus_gap"] = sum(cd[k] for k in ("biomass", "glycerol", "lactic", "excess_CO2", "unaccounted")) - cd["gap_total"]
        drows.append(drow)
    return pd.DataFrame(rows), pd.DataFrame(yrows), pd.DataFrame(drows)


def pooled(d, ids, rng):
    E = np.array([d[r]["E"] for r in ids]); dS = np.array([d[r]["S0"] - d[r]["S48"] for r in ids])
    pooled_y = E.sum() / dS.sum(); slope = float((E * dS).sum() / (dS ** 2).sum())
    boots = []
    for _ in range(10000):
        i = rng.integers(0, len(ids), len(ids)); boots.append(E[i].sum() / dS[i].sum())
    return pooled_y, slope, float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)), float(np.mean(E / dS))


def pooled_table(d):
    rng = np.random.default_rng(SEED + 1); sets = {"all 8 runs": RUNS, "7 runs (R7 excluded)": [r for r in RUNS if r != "R7"],
                                                 "6 Level-1 training runs": ["R1", "R2", "R3", "R4", "R5", "R8"], "R7 alone": ["R7"], "R5 alone": ["R5"]}
    rows = []
    for k, ids in sets.items():
        y, s, lo, hi, mean = pooled(d, ids, rng) if len(ids) > 1 else (pooled(d, ids, rng)[0],) * 2 + (np.nan, np.nan, pooled(d, ids, rng)[4])
        rows.append(dict(set=k, n_runs=len(ids), pooled_yield_sum_ratio=y, slope_through_origin=s, bootstrap_95_lo=lo, bootstrap_95_hi=hi, mean_of_run_yields=mean,
                         pct_of_theory=100 * y / YTHEORY, theory=YTHEORY, note="bootstrap over runs (10,000), ratio of sums; run-to-run spread, not measurement sd"))
    return pd.DataFrame(rows)


def r7_review(d, cb, yl):
    a, b = d["R7"], d["R5"]; rows = []
    def add(name, v7, v5, sd7, sd5, unit):
        sdd = float(np.hypot(sd7, sd5)); rows.append(dict(quantity=name, R7=v7, R5=v5, difference=v7 - v5, sd_of_difference=sdd, z=(v7 - v5) / sdd if sdd > 0 else np.nan, unit=unit))
    add("final TRS", a["S48"], b["S48"], sd_S(a["S48"]), sd_S(b["S48"]), "g/L")
    add("ethanol 48 h", a["E"], b["E"], sd_P(a["E"]), sd_P(b["E"]), "g/L")
    add("CO2 48 h", a["C"], b["C"], sd_C(a["C"]), sd_C(b["C"]), "g/L")
    add("biomass 48 h", a["X48"], b["X48"], sd_X(a["X48"]), sd_X(b["X48"]), "g/L")
    add("glycerol", a["G"], b["G"], 0.03 * a["G"], 0.03 * b["G"], "g/L")
    add("final pH", a["pH"], b["pH"], 0.04, 0.04, "-")
    add("lactic acid (n.d. = 0.1 +/- 0.058)", 9.0, 0.1, 0.27, 0.0577, "g/L")
    lac_C = 9.0 / M_LAC * 3; lac_gluc = lac_C / 6 * M_GLU
    rows.append(dict(quantity="lactic acid carbon", R7=lac_C, R5=np.nan, difference=np.nan, sd_of_difference=np.nan, z=np.nan, unit="C-mol/L"))
    rows.append(dict(quantity="lactic acid as glucose equivalent (1 glucose -> 2 lactic acid)", R7=lac_gluc, R5=np.nan, difference=np.nan, sd_of_difference=np.nan, z=np.nan, unit="g/L"))
    dS7, dS5 = a["S0"] - a["S48"], b["S0"] - b["S48"]
    rows.append(dict(quantity="TRS consumed", R7=dS7, R5=dS5, difference=dS7 - dS5, sd_of_difference=np.nan, z=np.nan, unit="g/L"))
    rows.append(dict(quantity="share of the R5-R7 TRS-consumption gap that lactic acid carbon could account for", R7=lac_gluc / (dS5 - dS7), R5=np.nan, difference=np.nan, sd_of_difference=np.nan, z=np.nan, unit="fraction"))
    rows.append(dict(quantity="ethanol per TRS consumed, as measured", R7=a["E"] / dS7, R5=b["E"] / dS5, difference=a["E"] / dS7 - b["E"] / dS5, sd_of_difference=np.nan, z=np.nan, unit="g/g"))
    rows.append(dict(quantity="ethanol per TRS consumed after removing lactic-acid glucose equivalent", R7=a["E"] / (dS7 - lac_gluc), R5=b["E"] / dS5, difference=a["E"] / (dS7 - lac_gluc) - b["E"] / dS5, sd_of_difference=np.nan, z=np.nan, unit="g/g"))
    c = cb.set_index("run")
    rows.append(dict(quantity="carbon recovery, lactate counted (total-input basis)", R7=c.loc["R7", "recovery_pct"], R5=c.loc["R5", "recovery_pct"], difference=np.nan, sd_of_difference=np.nan, z=np.nan, unit="%"))
    rows.append(dict(quantity="carbon recovery, lactate omitted", R7=c.loc["R7", "recovery_pct_lactic_removed"], R5=c.loc["R5", "recovery_pct_lactic_removed"], difference=np.nan, sd_of_difference=np.nan, z=np.nan, unit="%"))
    rows.append(dict(quantity="carbon recovery, consumed basis, lactate counted", R7=c.loc["R7", "recovery_consumed_basis_pct"], R5=c.loc["R5", "recovery_consumed_basis_pct"], difference=np.nan, sd_of_difference=np.nan, z=np.nan, unit="%"))
    return pd.DataFrame(rows)


def figures(cb, yl, dec, fdir):
    parts = ["C_out_residual_sugar", "C_out_biomass", "C_out_ethanol", "C_out_CO2", "C_out_glycerol", "C_out_lactic"]
    labels = ["residual sugar", "biomass", "ethanol", "CO2", "glycerol", "lactic acid"]; cols = ["#bbbbbb", "#2ca02c", "#d62728", "#1f77b4", "#ff7f0e", "#9467bd"]
    fig, ax = plt.subplots(1, 2, figsize=(14, 5)); bottom = np.zeros(len(cb))
    for p, l, c in zip(parts, labels, cols):
        v = 100 * cb[p] / cb.C_in_total_Cmol_L; ax[0].bar(cb.run, v, bottom=bottom, label=l, color=c); bottom += v.values
    ax[0].errorbar(cb.run, cb.recovery_pct, yerr=[cb.recovery_pct - cb.recovery_95_lo, cb.recovery_95_hi - cb.recovery_pct], fmt="k_", capsize=6, lw=1.5, label="recovery, MC 95%")
    ax[0].axhline(100, color="k", lw=0.8, ls="--"); ax[0].set_ylim(0, 125); ax[0].set_ylabel("% of carbon input"); ax[0].legend(fontsize=7, ncol=2); ax[0].set_title("Carbon output as % of carbon input (all 8 runs)")
    ax[1].bar(cb.run, cb.recovery_consumed_basis_pct, color="tab:gray"); ax[1].errorbar(cb.run, cb.recovery_consumed_basis_pct, yerr=[cb.recovery_consumed_basis_pct - cb.recovery_consumed_95_lo, cb.recovery_consumed_95_hi - cb.recovery_consumed_basis_pct], fmt="k_", capsize=6)
    ax[1].axhline(100, color="k", lw=0.8, ls="--"); ax[1].set_ylim(80, 112); ax[1].set_title("Recovery on consumed-sugar carbon basis (Phase 0 basis), MC 95%"); ax[1].set_ylabel("%")
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "carbon_balance_all_runs.png"), dpi=140); plt.close(fig)
    fig, ax = plt.subplots(1, 2, figsize=(14, 5)); ax[0].bar(yl.run, yl.yield_g_per_g, color="tab:gray"); ax[0].errorbar(yl.run, yl.yield_g_per_g, yerr=[yl.yield_g_per_g - yl.yield_95_lo, yl.yield_95_hi - yl.yield_g_per_g], fmt="k_", capsize=6)
    ax[0].axhline(YTHEORY, color="r", ls="--", label=f"theory {YTHEORY:.4f}"); ax[0].set_ylim(0.40, 0.53); ax[0].set_ylabel("g ethanol / g TRS consumed"); ax[0].legend(); ax[0].set_title("Ethanol yield per run (error bars: MC 95%, measurement only)")
    comp = ["biomass_pct_pts", "glycerol_pct_pts", "lactic_pct_pts", "excess_CO2_pct_pts", "unaccounted_pct_pts"]; cl = ["biomass", "glycerol", "lactic acid", "CO2 beyond 1:1 with ethanol", "unaccounted"]; cc = ["#2ca02c", "#ff7f0e", "#9467bd", "#1f77b4", "#7f7f7f"]
    pos = np.zeros(len(dec)); neg = np.zeros(len(dec))
    for k, l, c in zip(comp, cl, cc):
        v = dec[k].values; b = np.where(v >= 0, pos, neg); ax[1].bar(dec.run, v, bottom=b, label=l, color=c); pos += np.where(v >= 0, v, 0); neg += np.where(v < 0, v, 0)
    ax[1].plot(dec.run, dec.gap_pct_of_consumed_carbon, "k_", ms=18, mew=2, label="total gap"); ax[1].axhline(0, color="k", lw=0.6); ax[1].set_ylabel("% of consumed sugar carbon")
    ax[1].set_title("Where the carbon not routed to ethanol (+ paired CO2) went"); ax[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "ethanol_yield_gap.png"), dpi=140); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data-dir", default="data/raw"); ap.add_argument("--root", default=".")
    a = ap.parse_args(); t = os.path.join(a.root, "outputs", "tables"); f = os.path.join(a.root, "outputs", "figures"); os.makedirs(t, exist_ok=True); os.makedirs(f, exist_ok=True)
    d = load(a.data_dir); cb, yl, dec = balance_tables(d)
    cb.to_csv(os.path.join(t, "carbon_balance_all_runs.csv"), index=False)
    yl.to_csv(os.path.join(t, "ethanol_yields.csv"), index=False)
    dec.to_csv(os.path.join(t, "yield_gap_decomposition.csv"), index=False)
    pt = pooled_table(d); pt.to_csv(os.path.join(t, "ethanol_yield_pooled.csv"), index=False)
    rv = r7_review(d, cb, yl); rv.to_csv(os.path.join(t, "r7_review.csv"), index=False)
    figures(cb, yl, dec, f)
    pd.set_option("display.width", 250)
    print(cb[["run", "C_in_total_Cmol_L", "C_out_total_Cmol_L", "unaccounted_Cmol_L", "recovery_pct", "recovery_95_lo", "recovery_95_hi", "recovery_consumed_basis_pct", "closes_within_95"]].round(3).to_string(index=False))
    print(yl[["run", "yield_g_per_g", "yield_95_lo", "yield_95_hi", "yield_pct_of_theory", "yield_catabolic_after_biomass_sugar"]].round(4).to_string(index=False))
    print(pt.round(4).to_string(index=False)); print(dec.round(2).to_string(index=False)); print(rv.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
