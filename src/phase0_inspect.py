"""Phase 0: raw-data audit only. NO kinetic fitting, NO optimisation, NO run exclusion.

Usage (from project root):
    python src/phase0_inspect.py --data-dir data/raw --root .

Inputs : runs.csv, timecourse.csv, endpoint_hplc.csv (read-only)
Outputs: outputs/tables/data_quality.csv
         outputs/tables/endpoint_diagnostics.csv
         outputs/tables/preliminary_carbon_balance.csv
         outputs/tables/run_descriptive_summary.csv   (supplementary)
         outputs/figures/raw_curves.png

Constants and 1-sd measurement uncertainties are taken from docs/assignment_brief.md (sections 3).
The uncertainty table in the brief is PDF-extracted text; it is read in row order:
biomass, TRS, ethanol, CO2, by-products (glycerol/lactic), pH.
"""
import argparse
import os

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", default="data/raw")
ap.add_argument("--root", default=".")
a = ap.parse_args()
TAB = os.path.join(a.root, "outputs", "tables")
FIG = os.path.join(a.root, "outputs", "figures")
os.makedirs(TAB, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

runs = pd.read_csv(os.path.join(a.data_dir, "runs.csv"))
tc = pd.read_csv(os.path.join(a.data_dir, "timecourse.csv"))
hp = pd.read_csv(os.path.join(a.data_dir, "endpoint_hplc.csv"))
VARS = ["biomass_g_L", "TRS_g_L_as_glucose", "ethanol_g_L", "CO2_evolved_g_per_L"]

# ---- constants from the brief ----
MW = dict(glucose=180.16, sucrose=342.30, ethanol=46.07, CO2=44.01, glycerol=92.09, lactic=90.08)
C_ATOM = 12.011
NC = dict(glucose=6, ethanol=2, CO2=1, glycerol=3, lactic=3)
FC = {k: NC[k] * C_ATOM / MW[k] for k in NC}          # g C per g species
FC_X = C_ATOM / 24.6                                  # biomass: 24.6 g per C-mol (brief)
Y_THEORY = 2 * MW["ethanol"] / MW["glucose"]          # g ethanol per g glucose, 0.5114
SUCROSE_HYDROLYSIS_GAIN = 2 * MW["glucose"] / MW["sucrose"]   # g glucose-equivalent per g sucrose
LACTIC_ND_LIMIT = 0.2                                 # g/L, "n.d." means below 0.2 g/L (brief)
PH_SD = 0.04


# ---- 1-sd measurement uncertainties (brief, section 3) ----
def sd_X(x): return 0.035 * np.asarray(x, float) + 0.08
def sd_S(s): return 0.01 * np.asarray(s, float) + 0.4
def sd_E(e): return 0.012 * np.asarray(e, float) + 0.25
def sd_CO2(c): return 0.02 * np.asarray(c, float)
def sd_G(g): return 0.03 * np.asarray(g, float)


SD = {"biomass_g_L": sd_X, "TRS_g_L_as_glucose": sd_S, "ethanol_g_L": sd_E, "CO2_evolved_g_per_L": sd_CO2}
Z_FLAG = 2.0   # screening threshold in sd units: analyst choice (the sds themselves come from the brief)

dq = []


def add(scope, file, run, variable, time_h, check, status, observed, expected, detail=""):
    dq.append(dict(scope=scope, file=file, run=run, variable=variable, time_h=time_h, check=check,
                   status=status, observed=observed, expected=expected, detail=detail))


# ---------- 1. schema / types / missing / duplicates ----------
for fname, df in [("runs.csv", runs), ("timecourse.csv", tc), ("endpoint_hplc.csv", hp)]:
    add("file", fname, "", "", "", "rows x cols", "INFO", f"{df.shape[0]} x {df.shape[1]}", "", "; ".join(df.columns))
    for c in df.columns:
        add("file", fname, "", c, "", "dtype", "INFO", str(df[c].dtype), "", "")
        n_na = int(df[c].isna().sum())
        add("file", fname, "", c, "", "empty/NaN cells", "PASS" if n_na == 0 else "INFO", n_na, 0,
            "blank = no lab note for that run (not an error)" if (fname == "runs.csv" and c == "notes") else "")
    add("file", fname, "", "", "", "fully duplicated rows", "PASS" if df.duplicated().sum() == 0 else "FLAG",
        int(df.duplicated().sum()), 0)
for fname, df, key in [("timecourse.csv", tc, ["run", "time_h"]), ("runs.csv", runs, ["run"]), ("endpoint_hplc.csv", hp, ["run"])]:
    n = int(df.duplicated(key).sum())
    add("file", fname, "", ",".join(key), "", "duplicate keys", "PASS" if n == 0 else "FLAG", n, 0)

nd = hp.lactic_acid_g_L.astype(str).str.strip()
bad = sorted(set(nd[pd.to_numeric(nd, errors="coerce").isna()]))
add("file", "endpoint_hplc.csv", "", "lactic_acid_g_L", "", "non-numeric tokens", "INFO", ";".join(bad), "numeric",
    "Column is text because of 'n.d.' = not detected, below 0.2 g/L (brief). Treated as 0 (upper bound 0.2 g/L) in carbon balance.")
hp["lactic_num"] = pd.to_numeric(nd, errors="coerce")

# ---------- 2. IDs, time grid ----------
sets = {n: set(d.run) for n, d in [("runs", runs), ("timecourse", tc), ("endpoint_hplc", hp)]}
add("cross-file", "all", "", "run", "", "run IDs identical across 3 files, R1-R8",
    "PASS" if sets["runs"] == sets["timecourse"] == sets["endpoint_hplc"] == {f"R{i}" for i in range(1, 9)} else "FLAG",
    ",".join(sorted(sets["timecourse"])), "R1..R8")
grids = {r: tuple(g.sort_values("time_h").time_h) for r, g in tc.groupby("run")}
BRIEF_GRID = (0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 30, 36, 42, 48)
add("cross-file", "timecourse.csv", "", "time_h", "", "time grid equals brief grid in every run",
    "PASS" if all(g == BRIEF_GRID for g in grids.values()) else "FLAG", str(list(BRIEF_GRID)), str(list(BRIEF_GRID)),
    "Brief lists 0,2,4,6,8,10,12,16,20,24,30,36,42,48 h")
for r, g in tc.groupby("run"):
    add("run", "timecourse.csv", r, "time_h", "", "rows in file are time-sorted",
        "PASS" if (np.diff(g.time_h.values) > 0).all() else "FLAG", len(g), 14)

# ---------- 3. ranges / units ----------
for v in VARS:
    add("file", "timecourse.csv", "", v, "", "min / max", "INFO", f"{tc[v].min()} / {tc[v].max()}", "",
        "unit g/L from column name and brief; not independently verifiable")
    add("file", "timecourse.csv", "", v, "", "negative values", "PASS" if (tc[v] < 0).sum() == 0 else "FLAG", int((tc[v] < 0).sum()), 0)
add("file", "endpoint_hplc.csv", "", "final_pH", "", "min / max", "INFO", f"{hp.final_pH.min()} / {hp.final_pH.max()}", "",
    "pH given at 48 h only; no initial pH in the files")
add("file", "timecourse.csv", "", "TRS_g_L_as_glucose", "", "exact zeros", "INFO", int((tc.TRS_g_L_as_glucose == 0).sum()), "",
    "Detection limit for TRS not given in brief; zeros may be clipped values")

# ---------- 4. initial measurements vs metadata (z in brief-sd units) ----------
t0 = tc[tc.time_h == 0].set_index("run")
rm = runs.set_index("run")
for r in rm.index:
    S, Sn = t0.loc[r, "TRS_g_L_as_glucose"], rm.loc[r, "initial_TRS_g_L_as_glucose"]
    z = (S - Sn) / sd_S(S)
    add("run", "timecourse vs runs", r, "TRS", 0, "t=0 TRS vs metadata initial TRS", "PASS" if abs(z) <= Z_FLAG else "FLAG",
        f"{S} ({100*(S-Sn)/Sn:+.2f}%, z={z:+.2f})", Sn, f"z uses brief sd = 1% + 0.4 g/L; flag if |z|>{Z_FLAG} (analyst choice)")
    X, Xn = t0.loc[r, "biomass_g_L"], rm.loc[r, "inoculum_biomass_g_L"]
    z = (X - Xn) / sd_X(X)
    add("run", "timecourse vs runs", r, "biomass", 0, "t=0 biomass vs metadata inoculum", "PASS" if abs(z) <= Z_FLAG else "FLAG",
        f"{X} ({100*(X-Xn)/Xn:+.1f}%, z={z:+.2f})", Xn, "z uses brief sd = 3.5% + 0.08 g/L; nominal inoculum treated as exact"
        + ("; R3 biomass is OD600-based so the dry-weight sd may not apply" if r == "R3" else ""))
    E = t0.loc[r, "ethanol_g_L"]
    z = E / sd_E(0)
    add("run", "timecourse", r, "ethanol", 0, "t=0 ethanol vs 0", "PASS" if abs(z) <= Z_FLAG else "FLAG", f"{E} (z={z:+.2f})", 0,
        "within brief sd (0.25 g/L) at 1-2 sd" if E > 0 else "")
    add("run", "timecourse", r, "CO2", 0, "t=0 cumulative CO2 is 0", "PASS" if t0.loc[r, "CO2_evolved_g_per_L"] == 0 else "FLAG",
        t0.loc[r, "CO2_evolved_g_per_L"], 0)

col2 = "initial_sugars_sucrose_plus_reducing_g_L"
ratio = runs[col2] / runs.initial_TRS_g_L_as_glucose
x_suc = (1 / ratio - 1) / (SUCROSE_HYDROLYSIS_GAIN - 1)
add("cross-file", "runs.csv", "", "initial TRS / sucrose+reducing sugars", "", "implied sucrose mass fraction of sugar charge",
    "INFO", f"TRS/sugars = {(1/ratio).min():.4f}-{(1/ratio).max():.4f}; implied sucrose fraction {x_suc.min():.3f}-{x_suc.max():.3f}", "",
    f"Brief: second column is the same charge by mass BEFORE inversion. Inversion adds water (x{SUCROSE_HYDROLYSIS_GAIN:.4f} per g sucrose), so "
    "a constant ratio fits ~70% of sugar mass being sucrose. Inference, not stated in brief.")
cols5 = ["temperature_C", "initial_TRS_g_L_as_glucose", col2, "inoculum_biomass_g_L"]
add("run", "runs.csv", "R5,R7", "metadata", "", "R5 and R7 have identical conditions",
    "PASS" if rm.loc["R5", cols5].tolist() == rm.loc["R7", cols5].tolist() else "FLAG", "identical", "identical", "Notes: R7 repeats R5")
add("run", "runs.csv", "R3", "biomass", "", "biomass method differs from dry cell weight", "FLAG", "OD600 calibration", "dry cell weight",
    "Run note: dry-weight oven under repair. Not excluded; its biomass series is less comparable.")

# ---------- 5. step changes vs measurement noise; plateaus ----------
for r, g in tc.groupby("run"):
    g = g.sort_values("time_h")
    T = g.time_h.values
    for v in VARS:
        vals = g[v].values
        sd = SD[v](vals)
        d = np.diff(vals)
        sd_d = np.sqrt(sd[1:] ** 2 + sd[:-1] ** 2)
        if v == "TRS_g_L_as_glucose":
            idx = np.where(d > 0)[0]
            what = "TRS rises between samples"
        elif v == "biomass_g_L":
            idx = np.where(d < 0)[0]
            what = "biomass falls between samples"
        else:
            idx = np.where(d < 0)[0]
            what = f"{v} falls between samples (should be non-decreasing)"
        for i in idx:
            z = abs(d[i]) / sd_d[i]
            add("run-time", "timecourse.csv", r, v, int(T[i + 1]), what, "FLAG" if z > Z_FLAG else "INFO",
                f"{vals[i]} -> {vals[i+1]} ({d[i]:+.2f}); z={z:.2f}", "",
                "exceeds 2 sd of the difference (brief sds)" if z > Z_FLAG else "within brief measurement noise (|z|<=2)")
    c = g.CO2_evolved_g_per_L.values
    if (np.diff(c) >= 0).all():
        add("run", "timecourse.csv", r, "CO2_evolved_g_per_L", "", "cumulative CO2 non-decreasing", "PASS", "monotone", "monotone")
    k = 0
    while k < len(c) - 1 and c[-1 - k - 1] == c[-1]:
        k += 1
    if k >= 2:
        trs_start = g.TRS_g_L_as_glucose.values[-1 - k]
        add("run", "timecourse.csv", r, "CO2_evolved_g_per_L", int(T[-1 - k]), "identical cumulative CO2 repeated", "INFO",
            f"{c[-1]} at {k+1} consecutive samples (t={int(T[-1-k])}-{int(T[-1])} h); TRS at start of plateau = {trs_start}", "",
            "Plausible for an integrated off-gas flow once sugar is exhausted (zero flow adds nothing); cannot be confirmed from the CSV.")
    e, co = g.ethanol_g_L.values[-1], c[-1]
    rr = e / co
    s_rr = rr * np.hypot(sd_E(e) / e, sd_CO2(co) / co)
    add("run", "timecourse.csv", r, "ethanol/CO2", int(T[-1]), "48 h ethanol:CO2 mass ratio vs 1:1 molar (1.047)", "INFO",
        f"{rr:.3f} (z={(rr-MW['ethanol']/MW['CO2'])/s_rr:+.2f})", round(MW["ethanol"] / MW["CO2"], 3),
        "descriptive; CO2 also comes from biomass formation and other pathways")

dqdf = pd.DataFrame(dq)
dqdf.insert(0, "id", [f"DQ{i+1:03d}" for i in range(len(dqdf))])
dqdf.to_csv(os.path.join(TAB, "data_quality.csv"), index=False)


# ---------- 6. descriptive per-run summary (finite differences, NOT model fits) ----------
def rate(g, t1, t2, v="ethanol_g_L"):
    return (g.loc[g.time_h == t2, v].iloc[0] - g.loc[g.time_h == t1, v].iloc[0]) / (t2 - t1)


rows = []
for r, g in tc.groupby("run"):
    g = g.sort_values("time_h")
    m = rm.loc[r]
    l = g.iloc[-1]
    le1, le5 = g[g.TRS_g_L_as_glucose <= 1.0], g[g.TRS_g_L_as_glucose <= 5.0]
    peak = max(rate(g, 0, 12), rate(g, 12, 24))
    cons = g.TRS_g_L_as_glucose.iloc[0] - l.TRS_g_L_as_glucose
    rows.append(dict(
        run=r, temperature_C=m.temperature_C, initial_TRS_nominal=m.initial_TRS_g_L_as_glucose,
        TRS_t0_meas=g.TRS_g_L_as_glucose.iloc[0], ethanol_24h=g.loc[g.time_h == 24, "ethanol_g_L"].iloc[0],
        ethanol_48h=l.ethanol_g_L, TRS_48h=l.TRS_g_L_as_glucose, CO2_48h=l.CO2_evolved_g_per_L,
        biomass_24h=g.loc[g.time_h == 24, "biomass_g_L"].iloc[0], biomass_48h=l.biomass_g_L, biomass_max=g.biomass_g_L.max(),
        first_time_TRS_le_1=(le1.time_h.iloc[0] if len(le1) else np.nan),
        first_time_TRS_le_5=(le5.time_h.iloc[0] if len(le5) else np.nan),
        wash_strength_pct_v_v_48h=l.ethanol_g_L / 7.89,
        ethanol_yield_on_TRS_consumed=l.ethanol_g_L / cons,
        yield_pct_of_theoretical=100 * l.ethanol_g_L / cons / Y_THEORY,
        EtOH_rate_0_12h=rate(g, 0, 12), EtOH_rate_12_24h=rate(g, 12, 24), EtOH_rate_24_36h=rate(g, 24, 36),
        EtOH_rate_36_48h=rate(g, 36, 48), EtOH_rate_36_48_over_peak_window=rate(g, 36, 48) / peak,
        TRS_rate_0_12h=-rate(g, 0, 12, "TRS_g_L_as_glucose"), TRS_rate_24_36h=-rate(g, 24, 36, "TRS_g_L_as_glucose"),
        TRS_rate_36_48h=-rate(g, 36, 48, "TRS_g_L_as_glucose")))
summ = pd.DataFrame(rows).round(3)
summ.to_csv(os.path.join(TAB, "run_descriptive_summary.csv"), index=False)

# ---------- 7. endpoint diagnostics ----------
ed = hp.merge(runs[["run", "temperature_C", "initial_TRS_g_L_as_glucose"]], on="run").merge(
    summ[["run", "TRS_t0_meas", "TRS_48h", "ethanol_48h", "biomass_48h"]], on="run")
ed["lactic_detected"] = ed.lactic_num.notna()
ed["lactic_note"] = np.where(ed.lactic_detected, "detected", "n.d. (<0.2 g/L per brief)")
ed["sugar_consumed_g_L"] = (ed.TRS_t0_meas - ed.TRS_48h).round(2)
ed["glycerol_per_sugar_consumed"] = (ed.glycerol_g_L / ed.sugar_consumed_g_L).round(4)
ed["glycerol_per_ethanol"] = (ed.glycerol_g_L / ed.ethanol_48h).round(4)
ed["glycerol_sd_g_L"] = sd_G(ed.glycerol_g_L).round(2)
ed["pH_sd"] = PH_SD
ed["pH_z_vs_median_of_other_runs"] = [round((row.final_pH - ed.loc[ed.run != row.run, "final_pH"].median()) / PH_SD, 1) for row in ed.itertuples()]
ed["flag_lactic_detected"] = ed.lactic_detected
ed["flag_pH_gt5sd_from_other_runs_median"] = ed.pH_z_vs_median_of_other_runs.abs() > 5
pair = {"R5": "R7", "R7": "R5"}
SDF = {"glycerol_g_L": sd_G, "final_pH": lambda x: PH_SD + 0 * np.asarray(x, float), "TRS_48h": sd_S,
       "ethanol_48h": sd_E, "biomass_48h": sd_X}
eds = ed.set_index("run")
for col, name in [("glycerol_g_L", "glycerol"), ("final_pH", "pH"), ("TRS_48h", "TRS_48h"), ("ethanol_48h", "ethanol_48h"), ("biomass_48h", "biomass_48h")]:
    diffs, zs = [], []
    for r in ed.run:
        if r in pair:
            p = pair[r]
            d = eds.loc[r, col] - eds.loc[p, col]
            s = float(np.hypot(SDF[col](eds.loc[r, col]), SDF[col](eds.loc[p, col])))
            diffs.append(round(d, 2))
            zs.append(round(d / s, 1))
        else:
            diffs.append(np.nan)
            zs.append(np.nan)
    ed[f"R5R7_diff_{name}_(this_minus_partner)"] = diffs
    ed[f"R5R7_diff_{name}_in_sd"] = zs
ed["note"] = "HPLC and pH are 48 h values (brief). Initial pH not supplied."
ed.drop(columns=["lactic_num"]).to_csv(os.path.join(TAB, "endpoint_diagnostics.csv"), index=False)

# ---------- 8. preliminary carbon balance (brief constants; first-order sd propagation) ----------
cb = []
fin = tc.sort_values("time_h").groupby("run").last()
hpi = hp.set_index("run")
for r in rm.index:
    S0, S0n, S48 = t0.loc[r, "TRS_g_L_as_glucose"], rm.loc[r, "initial_TRS_g_L_as_glucose"], fin.loc[r, "TRS_g_L_as_glucose"]
    E, CO2, G = fin.loc[r, "ethanol_g_L"], fin.loc[r, "CO2_evolved_g_per_L"], hpi.loc[r, "glycerol_g_L"]
    lact_nd = bool(np.isnan(hpi.loc[r, "lactic_num"]))
    L = 0.0 if lact_nd else float(hpi.loc[r, "lactic_num"])
    X0, X48 = t0.loc[r, "biomass_g_L"], fin.loc[r, "biomass_g_L"]
    dX = X48 - X0
    Cin = (S0 - S48) * FC["glucose"]
    Cin_nom = (S0n - S48) * FC["glucose"]
    sd_in = FC["glucose"] * float(np.hypot(sd_S(S0), sd_S(S48)))
    parts = dict(C_ethanol=E * FC["ethanol"], C_CO2=CO2 * FC["CO2"], C_glycerol=G * FC["glycerol"], C_lactic=L * FC["lactic"],
                 C_biomass_gain=dX * FC_X)
    sd_parts = [sd_E(E) * FC["ethanol"], sd_CO2(CO2) * FC["CO2"], sd_G(G) * FC["glycerol"], float(np.hypot(sd_X(X0), sd_X(X48))) * FC_X]
    out = sum(parts.values())
    sd_out = float(np.sqrt(np.sum(np.square(sd_parts))))
    rec = 100 * out / Cin
    sd_rec = rec * float(np.hypot(sd_out / out, sd_in / Cin))
    row = dict(run=r, TRS_t0_measured=S0, TRS_t0_nominal=S0n, TRS_48h=S48, sugar_consumed=round(S0 - S48, 2),
               ethanol_48h=E, CO2_48h=CO2, glycerol=G, lactic_used=L, lactic_is_nd=lact_nd,
               biomass_t0=X0, biomass_48h=X48, biomass_gain=round(dX, 2), C_in=round(Cin, 2), sd_C_in=round(sd_in, 2))
    row.update({k: round(v, 2) for k, v in parts.items()})
    row.update(C_out_total=round(out, 2), sd_C_out=round(sd_out, 2), recovery_pct=round(rec, 1), sd_recovery_pct=round(sd_rec, 1),
               recovery_minus_100_in_sd=round((rec - 100) / sd_rec, 2),
               recovery_pct_if_nominal_t0_TRS=round(100 * out / Cin_nom, 1),
               recovery_pct_lactic_omitted=round(100 * (out - parts["C_lactic"]) / Cin, 1),
               recovery_pct_ethanol_plus_CO2_only=round(100 * (parts["C_ethanol"] + parts["C_CO2"]) / Cin, 1),
               unrecovered_C_g_L=round(Cin - out, 2))
    row["flags"] = ("R3 biomass by OD600 (its sd may be larger); " if r == "R3" else "") + ("lactic acid detected; " if not lact_nd else "") + \
                   ("residual TRS > 5 g/L at 48 h; " if S48 > 5 else "")
    row["basis"] = (f"C fractions from brief formulae/molar masses; biomass {FC_X:.4f} g C/g (24.6 g per C-mol); TRS as glucose (0.4000 g C/g); "
                    "lactic n.d.=0 (<0.2 g/L ~ <0.08 gC/L); constant volume; ethanol in off-gas returned (brief); dissolved CO2 not measured; "
                    "sd by first-order propagation of brief sds (independent errors assumed)")
    cb.append(row)
pd.DataFrame(cb).to_csv(os.path.join(TAB, "preliminary_carbon_balance.csv"), index=False)

# ---------- 9. raw curves figure ----------
col = {30: "tab:blue", 34: "tab:orange", 37: "tab:red"}
ls = {160: ":", 220: "-", 260: "--"}
fig, ax = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
lab = dict(zip(VARS, ["Biomass (g/L, dry weight)", "TRS (g/L as glucose)", "Ethanol (g/L)", "Cumulative CO$_2$ evolved (g/L)"]))
for a_, v in zip(ax.ravel(), VARS):
    for r, g in tc.groupby("run"):
        g = g.sort_values("time_h")
        m = rm.loc[r]
        hollow = (r == "R3" and v == "biomass_g_L")
        a_.plot(g.time_h, g[v], color=col[m.temperature_C], ls=ls[m.initial_TRS_g_L_as_glucose], lw=2.2 if r == "R7" else 1.4,
                marker="s" if r == "R7" else "o", ms=4, mfc="white" if hollow else None,
                label=f"{r}: {m.temperature_C}°C, {m.initial_TRS_g_L_as_glucose} g/L")
    a_.set_ylabel(lab[v])
    a_.grid(alpha=.3)
for a_ in ax[1]:
    a_.set_xlabel("Time (h)")
h_, l_ = ax[0, 0].get_legend_handles_labels()
fig.legend(h_, l_, loc="lower center", ncol=4, fontsize=9, frameon=False)
fig.suptitle("Phase 0 raw data, all 8 runs (no fitting, no exclusions)\n"
             "colour = temperature; line style = initial TRS (dotted 160, solid 220, dashed 260); "
             "R7 = squares, thick; R3 biomass = OD600-based (hollow markers)", fontsize=10)
fig.tight_layout(rect=[0, 0.07, 1, 0.93])
fig.savefig(os.path.join(FIG, "raw_curves.png"), dpi=200)
print("Phase 0 outputs written to", a.root)
print(dqdf.status.value_counts().to_dict())
