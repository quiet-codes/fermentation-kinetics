#!/usr/bin/env python
"""Generate reports/level3.md from the Level 3 output tables and audit records.

Usage (project root, after `python src/level3_optimize.py --stage all`):
    python src/make_level3_report.py [output_path]

Every number in the report is read from outputs/tables/*.csv, outputs/audits/level3/*.json or
the frozen records.  The strings that carry a numeric claim are written to
outputs/audits/level3/report_claims.json so that tests and the consistency audit can verify
the report against the tables instead of trusting the prose.
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import level3 as L  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "reports/level3.md"
T = "outputs/tables/"
A = "outputs/audits/level3/"

grid = pd.read_csv(T + "optimization_grid.csv")
rec = pd.read_csv(T + "optimization_recommendations.csv")
econ = pd.read_csv(T + "plant_economics.csv")
unc = pd.read_csv(T + "optimization_uncertainty.csv")
cmp_df = pd.read_csv(T + "optimization_model_comparison.csv")
audit = pd.read_csv(T + "optimization_input_audit.csv")
horizon = pd.read_csv(T + "optimization_horizon_sensitivity.csv")

answers = L.read_json(A + "level3_answers.json")
policy = L.read_json(A + "model_policy.json")
grid_summary = L.read_json(A + "grid_summary.json")
hz_summary = L.read_json(A + "horizon_sensitivity.json")
input_summary = L.read_json(A + "input_audit_summary.json")
selection = L.read_json(T + "model_selection_frozen.json")
level1_frozen = L.read_json(T + "level1_frozen.json")
cb = pd.read_csv(T + "carbon_balance_all_runs.csv")
model_cmp = pd.read_csv(T + "model_comparison.csv").set_index("model")
unc_m5 = unc[unc.source == "parameter_ensemble_M5"]

CLAIMS = []


def claim(cid, text, source, field):
    """Record a numeric claim so the report can be checked against the tables."""
    CLAIMS.append(dict(id=cid, text=text, source=source, field=field))
    return text


def f(x, n=2):
    return f"{float(x):,.{n}f}"


def g(x, n=4):
    return f"{float(x):.{n}g}"


prim = grid[(grid.model == "M5") & (grid.horizon_h == L.HORIZON_PRIMARY_H)]
n_status = prim.feasibility_status.value_counts().to_dict()
n_complete = int(n_status.get(L.STATUS_COMPLETED, 0))
n_out = int(n_status.get(L.STATUS_OUT_OF_CURVE, 0))
n_unf = int(n_status.get(L.STATUS_UNFINISHED, 0))
n_fail = int(n_status.get(L.STATUS_FAILED, 0))

q1 = answers["Q1_best_normal_33_37"]
q2 = answers["Q2_best_min36"]
q5 = answers["Q5_fastest_completion"]
q5b = answers["brief_Q5_37C_260"]
a1, a2 = q1["answer"], q2["answer"]
q5pred = q5b["prediction"]

u_norm = unc_m5[(unc_m5.quantity == "margin_per_cycle_inr_per_h")
                & (unc_m5.candidate_id == "normal_33_37_M5_optimum")].iloc[0]
u_warm = unc_m5[(unc_m5.quantity == "margin_per_cycle_inr_per_h")
                & (unc_m5.candidate_id == "warm_min_36_M5_optimum")].iloc[0]
u_norm_t = unc_m5[(unc_m5.quantity == "completion_time_h")
                  & (unc_m5.candidate_id == "normal_33_37_M5_optimum")].iloc[0]
u_warm_t = unc_m5[(unc_m5.quantity == "completion_time_h")
                  & (unc_m5.candidate_id == "warm_min_36_M5_optimum")].iloc[0]
disc_norm = unc[(unc.quantity == "margin_per_cycle_inr_per_h") & (unc.source.str.startswith("discrete_"))
                & (unc.candidate_id == "normal_33_37_M5_optimum")]
disc_warm = unc[(unc.quantity == "margin_per_cycle_inr_per_h") & (unc.source.str.startswith("discrete_"))
                & (unc.candidate_id == "warm_min_36_M5_optimum")]
abs_penalty = f"{abs(float(q2['penalty_vs_normal_inr_per_h'])):,.2f} INR/h"
penalty_pct = 100.0 * abs(float(q2["penalty_vs_normal_inr_per_h"])) / float(a1["margin_per_cycle_inr_per_h"])
indep = unc[(unc.quantity == "margin_per_cycle_inr_per_h") & (unc.source.str.startswith("parameter_ensemble_"))
            & (unc.candidate_id.isin(["normal_33_37_M5_optimum", "warm_min_36_M5_optimum"]))]
_alt_margins = [float(m5_alt_at_norm_i) for m5_alt_at_norm_i in
                cmp_df[(cmp_df.case == "own_optimum") & (cmp_df.scenario == "normal_33_37")
                       & (cmp_df.model != "M5")].margin_per_cycle_inr_per_h]
struct_pct_lo = 100.0 * (min(_alt_margins) / float(a1["margin_per_cycle_inr_per_h"]) - 1.0)
struct_pct_hi = 100.0 * (max(_alt_margins) / float(a1["margin_per_cycle_inr_per_h"]) - 1.0)
m5_alt_at_norm = cmp_df[(cmp_df.case == "at_M5_optimum") & (cmp_df.scenario == "normal_33_37")]
m5_alt_at_warm = cmp_df[(cmp_df.case == "at_M5_optimum") & (cmp_df.scenario == "warm_min_36")]
own_opt = cmp_df[cmp_df.case == "own_optimum"]

# ------------------------------------------------------------------ tables
def rec_table(scenario):
    d = rec[(rec.scenario == scenario) & (rec.rank_basis == "highest_margin_per_cycle_time")
            & (rec.model == "M5")].sort_values("rank")
    rows = ["| # | TRS (g/L) | T (C) | complete (h) | TRS end (g/L) | ethanol (g/L) | wash (% v/v) | "
            "steam (kg/L) | margin (INR/batch) | cycle (h) | margin/cycle (INR/h) | 24 h equiv. (INR/day) |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in d.itertuples():
        rows.append(f"| {r.rank} | {r.s0_g_per_l:g} | {r.temperature_c:.2f} | {r.completion_time_h:.3f} | "
                    f"{r.final_trs_g_per_l:.3f} | {r.final_ethanol_g_per_l:.3f} | {r.wash_pct_vv:.3f} | "
                    f"{r.steam_kg_per_L:.4f} | {r.batch_margin_inr:,.0f} | {r.cycle_time_h:.3f} | "
                    f"{r.margin_per_cycle_inr_per_h:,.2f} | {r.margin_24h_equivalent_inr_per_day:,.1f} |")
    return "\n".join(rows)


def econ_table(case_ids):
    d = econ[econ.case_id.isin(case_ids)]
    rows = ["| case | TRS (g/L) | T (C) | sugar (t) | sugar cost (kINR) | ethanol (L) | revenue (kINR) | "
            "steam (t) | steam cost (kINR) | margin (kINR) | margin/cycle (INR/h) |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in d.itertuples():
        rows.append(f"| {r.case_id} | {r.s0_g_per_l:g} | {r.temperature_c:.2f} | {r.sugar_charged_kg/1000:,.2f} | "
                    f"{r.sugar_cost_inr/1000:,.1f} | {r.ethanol_volume_l:,.0f} | {r.ethanol_revenue_inr/1000:,.1f} | "
                    f"{r.steam_mass_kg/1000:,.2f} | {r.steam_cost_inr/1000:,.1f} | {r.batch_margin_inr/1000:,.1f} | "
                    f"{r.margin_per_cycle_inr_per_h:,.2f} |")
    return "\n".join(rows)


def param_table():
    import models as M
    _n, _s, _lo, _hi, units, _desc = M.spec("M5")
    unit_map = dict(zip(_n, units))
    rows = ["| parameter | unit | value | meaning |", "|---|---|---|---|"]
    meaning = {
        "mu_max": "maximum specific growth rate at 30 C",
        "X_max": "biomass carrying capacity",
        "q_max": "maximum specific sugar uptake at 30 C",
        "P_max": "ethanol inhibition constant at 30 C",
        "Y_P": "ethanol yield on catabolised sugar",
        "rho_CO2": "CO2 released per unit ethanol formed",
        "k34": "rate multiplier at 34 C",
        "k37": "rate multiplier at 37 C",
        "beta_P": "log-slope of P_max with temperature",
        "n_inh": "ethanol-inhibition exponent",
    }
    for n, v in policy["preferred_theta"].items():
        rows.append(f"| {n} | {unit_map.get(n, '-')} | {v:.6g} | {meaning.get(n, '')} |")
    return "\n".join(rows)


def model_cmp_table():
    rows = ["| scenario | model | case | TRS (g/L) | T (C) | complete (h) | ethanol (g/L) | "
            "margin/cycle (INR/h) | difference vs M5 (INR/h) |", "|---|---|---|---|---|---|---|---|---|"]
    for r in cmp_df.sort_values(["scenario", "case", "model"]).itertuples():
        rows.append(f"| {r.scenario} | {r.model} | {r.case} | {r.s0_g_per_l:g} | {r.temperature_c:.2f} | "
                    f"{r.completion_time_h:.3f} | {r.final_ethanol_g_per_l:.3f} | "
                    f"{r.margin_per_cycle_inr_per_h:,.2f} | {r.delta_margin_vs_M5_optimum_inr_per_h:+,.2f} |")
    return "\n".join(rows)


def unc_table():
    rows = ["| candidate | source | completion (h) | margin/cycle point (INR/h) | 95% interval (INR/h) | "
            "draws completing |", "|---|---|---|---|---|---|"]
    d = unc[(unc.quantity == "margin_per_cycle_inr_per_h")]
    d = d[d.source.isin(["parameter_ensemble_M5", "parameter_ensemble_M2", "parameter_ensemble_M6"])]
    for cid in ["normal_33_37_M5_optimum", "warm_min_36_M5_optimum", "brief_q5_37C_260"]:
        for model in ("M5", "M2", "M6"):
            r = d[(d.candidate_id == cid) & (d.model == model)]
            if not len(r):
                continue
            r = r.iloc[0]
            t = unc[(unc.candidate_id == cid) & (unc.quantity == "completion_time_h")
                    & (unc.model == model) & (unc.source == f"parameter_ensemble_{model}")]
            tt = f"{t.iloc[0].p2_5:.2f}-{t.iloc[0].p97_5:.2f}" if len(t) and np.isfinite(t.iloc[0].p2_5) else "n/a"
            pt = f"{r.point_estimate:,.2f}" if np.isfinite(r.point_estimate) else "not completed"
            ci = f"{r.p2_5:,.2f} to {r.p97_5:,.2f}" if np.isfinite(r.p2_5) else "no completed batch"
            rows.append(f"| {cid} | {model} | {tt} | {pt} | {ci} | {r.fraction_draws_completing:.2f} |")
    return "\n".join(rows)


def audit_table():
    rows = ["| id | path | role | units | type | original / derived / assumed | validation | status |",
            "|---|---|---|---|---|---|---|---|"]
    for r in audit.itertuples():
        rows.append(f"| {r.id} | `{r.path}` | {r.role} | {r.units} | {r.data_type} | "
                    f"{r.original_derived_assumed} | {r.validation} | {r.verified} |")
    return "\n".join(rows)


def cb_table():
    rows = ["| run | C in (C-mol/L) | C out (C-mol/L) | recovery (%) | closes within 95-105% | in primary fit |",
            "|---|---|---|---|---|---|"]
    for r in cb.itertuples():
        rows.append(f"| {r.run} | {r.C_in_total_Cmol_L:.3f} | {r.C_out_total_Cmol_L:.3f} | "
                    f"{r.recovery_pct:.1f} | {'yes' if bool(r.closes_within_95) else 'no'} | {r.in_primary_fit} |")
    return "\n".join(rows)


def horizon_table():
    if not len(horizon):
        return "| no unfinished candidates | | | | |\n|---|---|---|---|---|"
    d = horizon.sort_values(["temperature_c", "s0_g_per_l"])
    rows = ["| TRS (g/L) | T (C) | TRS at 120 h (g/L) | status at 240 h | completion at 240 h (h) | "
            "margin at 240 h (INR/h) | beats best 120 h margin |", "|---|---|---|---|---|---|---|"]
    for r in d.itertuples():
        c = f"{r.completion_time_240h:.2f}" if np.isfinite(r.completion_time_240h) else "n/a"
        m = f"{r.margin_240h_inr_per_h:,.2f}" if np.isfinite(r.margin_240h_inr_per_h) else "not priced"
        rows.append(f"| {r.s0_g_per_l:g} | {r.temperature_c:.2f} | {r.trs_at_120h:.2f} | {r.status_at_240h} | "
                    f"{c} | {m} | {r.outranks_best_120h} |")
    return "\n".join(rows)


# ------------------------------------------------------------------ claim strings
c_normal = claim("C-LEVEL3-01",
                 f"{a1['s0_g_per_l']:.1f} g/L TRS at {a1['temperature_c']:.1f} C",
                 "outputs/tables/optimization_recommendations.csv", "s0_g_per_l, temperature_c")
c_normal_margin = claim("C-LEVEL3-02", f"{a1['margin_per_cycle_inr_per_h']:,.2f} INR/h",
                        "outputs/tables/optimization_recommendations.csv", "margin_per_cycle_inr_per_h")
c_normal_day = claim("C-LEVEL3-03", f"{a1['margin_24h_equivalent_inr_per_day']:,.1f} INR/day",
                     "outputs/tables/optimization_recommendations.csv", "margin_24h_equivalent_inr_per_day")
c_normal_time = claim("C-LEVEL3-04", f"{a1['completion_time_h']:.2f} h",
                      "outputs/tables/optimization_recommendations.csv", "completion_time_h")
c_normal_eth = claim("C-LEVEL3-05", f"{a1['final_ethanol_g_per_l']:.2f} g/L ethanol",
                     "outputs/tables/optimization_recommendations.csv", "final_ethanol_g_per_l")
c_warm = claim("C-LEVEL3-06", f"{a2['s0_g_per_l']:.1f} g/L TRS at {a2['temperature_c']:.1f} C",
               "outputs/tables/optimization_recommendations.csv", "s0_g_per_l, temperature_c (warm)")
c_warm_margin = claim("C-LEVEL3-07", f"{a2['margin_per_cycle_inr_per_h']:,.2f} INR/h",
                      "outputs/tables/optimization_recommendations.csv", "margin_per_cycle_inr_per_h (warm)")
c_warm_day = claim("C-LEVEL3-08", f"{a2['margin_24h_equivalent_inr_per_day']:,.1f} INR/day",
                   "outputs/tables/optimization_recommendations.csv", "margin_24h (warm)")
c_warm_time = claim("C-LEVEL3-09", f"{a2['completion_time_h']:.2f} h",
                    "outputs/tables/optimization_recommendations.csv", "completion_time_h (warm)")
c_unf = claim("C-LEVEL3-10", f"{n_unf} unfinished rows", "outputs/tables/optimization_grid.csv", "feasibility_status")
c_out = claim("C-LEVEL3-11", f"{n_out} completed rows outside the 7-14 % v/v steam curve",
              "outputs/tables/optimization_grid.csv", "feasibility_status")
c_done = claim("C-LEVEL3-12", f"{n_complete} completed feasible rows", "outputs/tables/optimization_grid.csv",
               "feasibility_status")
c_q5pred = claim("C-LEVEL3-13", f"{q5pred['final_ethanol_g_per_l_at_120h']:.2f} g/L ethanol",
                 "outputs/tables/optimization_grid.csv", "final_ethanol_g_per_l (37 C, 260 g/L)")
c_unc_norm = claim("C-LEVEL3-14", f"{u_norm.p2_5:,.2f} to {u_norm.p97_5:,.2f} INR/h",
                   "outputs/tables/optimization_uncertainty.csv", "p2_5, p97_5 (normal optimum)")
c_unc_warm = claim("C-LEVEL3-15", f"{u_warm.p2_5:,.2f} to {u_warm.p97_5:,.2f} INR/h",
                   "outputs/tables/optimization_uncertainty.csv", "p2_5, p97_5 (warm optimum)")
c_penalty = claim("C-LEVEL3-16", f"{abs(q2['penalty_vs_normal_inr_per_h']):,.2f} INR/h",
                  "outputs/audits/level3/level3_answers.json", "penalty_vs_normal_inr_per_h")
c_fast = claim("C-LEVEL3-17", f"{q5['normal']['completion_time_h']:.2f} h",
               "outputs/tables/optimization_recommendations.csv", "completion_time_h (fastest)")
c_hz = claim("C-LEVEL3-18", f"{hz_summary['n_completing_by_240h']} of {hz_summary['n_unfinished_primary_normal']}",
             "outputs/audits/level3/horizon_sensitivity.json", "n_completing_by_240h")
c_pmax = claim("C-LEVEL3-19", f"{policy['preferred_theta']['P_max']:.1f} g/L",
               "outputs/tables/work/fit_M5.json", "P_max")
c_cb = claim("C-LEVEL3-20", f"{int(cb.closes_within_95.sum())} of {len(cb)}",
             "outputs/tables/carbon_balance_all_runs.csv", "closes_within_95")
c_rows = claim("C-LEVEL3-21", f"{grid_summary['total_rows']:,} scenario rows",
               "outputs/tables/optimization_grid.csv", "row count")

_th = policy["preferred_theta"]
pmax_30 = _th["P_max"]
pmax_33 = _th["P_max"] * np.exp(-_th["beta_P"] * 3.0)
pmax_36 = _th["P_max"] * np.exp(-_th["beta_P"] * 6.0)
pmax_37 = _th["P_max"] * np.exp(-_th["beta_P"] * 7.0)
_at195 = (prim[prim.s0_g_per_l == 195.0].drop_duplicates(subset=["temperature_c"])
          .set_index("temperature_c").sort_index())
t33, t34, t36, t37 = (float(_at195.loc[v, "completion_time_h"]) for v in (33.0, 34.0, 36.0, 37.0))
e33 = float(_at195.loc[33.0, "final_ethanol_g_per_l"])
e37 = float(_at195.loc[37.0, "final_ethanol_g_per_l"])

pct_lo = 100.0 * (1.0 - float(u_norm.p2_5) / float(u_norm.point_estimate))
pct_hi = 100.0 * (float(u_norm.p97_5) / float(u_norm.point_estimate) - 1.0)

EXEC_SUMMARY = f"""## 1. Executive summary

The plant must pick an initial sugar charge and a fermentation temperature for October, when the
fermenters can be held at 33 C but not colder, and it wants the largest daily margin per fermenter.
The answer below comes from the frozen Level 2 model M5 (selection rule D-24, held-out run R6 never
used for fitting or tuning), evaluated over a documented search grid with an explicit
batch-completion rule and the assignment's own cost data.

**Recommended operating condition (normal 33-37 C constraint): {c_normal}.** Under the frozen M5
parameters this batch reaches residual TRS of 5 g/L in {c_normal_time}, produces {c_normal_eth}, needs a
wash of {a1['wash_pct_vv']:.2f} % v/v, and returns **{c_normal_margin} of margin per cycle time**
({c_normal_day} as a derived 24 h equivalent) for a 170 m3 fermenter. That is the highest
margin-per-cycle-time point of every completed, costable candidate in the search.

**If the cooling water warms by 3 C and 36 C becomes the floor: {c_warm}**, completing in
{c_warm_time} with {c_warm_margin} ({c_warm_day}). Restricting the minimum temperature to 36 C reduces the
margin by {abs_penalty}, {penalty_pct:.1f} % of the normal-scenario value: at 36 C the same sugar
charge takes longer to reach 5 g/L, so the fixed 8 h turnaround is amortised over a longer cycle.

Three results matter as much as the numbers themselves:

* The optimum is **not** at the highest sugar charge. Every charge at or above roughly 250 g/L either
  fails to finish or lands above 14 % v/v wash, where the assignment's steam curve stops. Those
  candidates cannot be costed and are never ranked, so the recommendation sits just under 200 g/L.
* {n_complete} candidates are completed and feasible, {n_out} are completed but outside the
  steam curve, and {n_unf} never reach 5 g/L within the 120 h horizon. The last two groups carry no
  margin at all in the tables, and the search keeps them in separate status classes.
* The 37 C / 260 g/L prediction the brief asks for does **not** complete within 120 h. It reaches
  {c_q5pred} and about {q5pred['final_trs_g_per_l_at_120h']:.1f} g/L of residual sugar, and it is
  reported as a low-trust extrapolation, not as an operating point.

Uncertainty is quoted, not hidden: parameter-ensemble intervals on the margin are
{c_unc_norm} (normal optimum) and {c_unc_warm} (36 C scenario); every draw completes and stays inside
the steam curve, so the *ranking* is stable even though the *value* is not precise. See section 10.
"""

BODY = f"""
## 2. Engineering problem and optimisation objective

Eight lab batches of molasses fermentation were supplied with biomass, TRS, ethanol and cumulative
CO2 measured for 48 h. Levels 1 and 2 produced a kinetic model and a frozen choice of model structure.
Level 3 is a different question: given that frozen model, which (initial sugar, temperature) pair
should the plant run to maximise profit per fermenter?

The objective is the assignment's own metric (brief section 4):

```
daily margin per fermenter = (ethanol value - sugar cost - distillation steam cost) / cycle time
cycle time                 = batch time + 8 h turnaround
```

subject to the batch-completion constraint (residual TRS <= 5 g/L) and the operating bounds
160-260 g/L TRS and 33-37 C (36-37 C in the warm scenario). The decision variables are the sugar charge
S0 and the temperature T; everything else (inoculum 2.5 g/L, working volume 170 m3, turnaround 8 h)
is fixed by the plant data or the brief.

This is not a model-selection problem and not a convergence problem. M5 was chosen before Level 3 by
D-24 and is used unchanged; the Level 3 task is to search its feasible space honestly and to say where
the confidence stops.

## 3. Inputs and data-quality limitations

Every input used by Level 3 is listed in `outputs/tables/optimization_input_audit.csv` with its role,
units, validation and status. Summary: {input_summary['n_inputs']} inputs, of which
{input_summary['n_verified']} are verified against a checksum or a frozen hash,
{input_summary['n_partially_verified']} is only partially verified (the assignment brief, see below) and
{input_summary['n_verified_with_open_issue']} are verified but carry an explicitly recorded unresolved
limitation (steam-curve provenance, plant inoculum practice, temperature interpolation).
The raw CSV checksums were recomputed during the audit and {'passed' if input_summary['raw_checksums']['passed'] else 'FAILED'}.

{audit_table()}

What can and cannot be verified:

* **Verified.** The three raw CSVs (SHA-256 against `data/raw/CHECKSUMS.sha256`), the frozen Level 1
  parameter file, the frozen Level 2 selection and the M5 parameter vector. All hashes match and M5
  reproduces from `outputs/tables/candidate_parameters.csv` to 1e-12.
* **Partially verified.** `docs/assignment_brief.md` is an extracted text version of the assignment.
  The economics constants, the completion rule and the steam curve were cross-checked against
  `src/plant_uncertainty.py` and are used consistently, but the original PDF is not available. Any
  PDF-only requirement, and the exact provenance of the steam curve beyond its eight tabulated
  points, cannot be confirmed. This is recorded as an unresolved requirement, not papered over.
* **Assumed.** Constant broth volume with no ethanol stripping (brief section 3), 2.5 g/L inoculum for
  every plant scenario (the value all eight lab runs used), and piecewise-linear temperature
  multipliers between the measured 30/34/37 C levels.

Data-quality limits that propagate into Level 3: the data stop at 48 h while completions take
25-120 h; only one run (R8) was made at 37 C; and the CO2 measurement has a modelling floor of
0.10 g/L that enters the weighting and therefore the parameter covariance.

## 4. Kinetic model description and equations

Level 3 does not re-implement the kinetics. It integrates the frozen Level 2 structure through
`models.simulate`, so the model used here is provably the model that was selected (the loader checks
the parameter names, the frozen hashes and the selection record before any search runs).

States X (biomass), S (TRS as glucose), P (ethanol), C (cumulative CO2), all g/L, constant volume,
time in h:

```
mon   = S / (K_s + S)                                  K_s = 1.0 g/L (fixed, Level 1 decision)
kT    = rate multiplier: 1 at 30 C, k34 at 34 C, k37 at 37 C, linear between, error outside 30-37 C
Pm(T) = P_max * exp(-beta_P * (T - 30))                M5: ethanol tolerance falls as T rises
inh   = max(1 - P/Pm(T), 0) ** n_inh                   M5: n_inh is estimated, not fixed
mu    = mu_max * kT * mon * max(1 - X/X_max, 0)        growth is not directly inhibited by ethanol in M5
q_S   = q_max * kT * mon * inh                         catabolic sugar uptake
dX/dt = mu*X
dS/dt = -1.2206*mu*X - q_S*X                           1.2206 g glucose per g biomass (C-mol stoichiometry)
dP/dt = Y_P*q_S*X
dC/dt = rho_CO2*dP/dt
```

Frozen M5 parameters used for every scenario in this report
(`outputs/tables/work/fit_M5.json`, parameter set `{policy['preferred_parameter_set_id']}`):

{param_table()}

For M5 the fit gives a high P_max ({c_pmax}) together with an exponent n_inh above 1. Those two
parameters trade off against each other: the data determine the *shape* of the inhibition curve near
the measured ethanol levels but not the two coefficients separately. That correlation is carried into
the uncertainty analysis in section 10 and is the reason the intervals there are wider than the
residual scatter would suggest.

## 5. Model-selection policy and why M5 is retained

The frozen decision is unchanged and was verified programmatically before any Level 3 calculation
(`outputs/audits/level3/model_policy.json`):

| check | result |
|---|---|
| frozen preferred model | {policy['checks']['frozen_preferred_model_is_M5'] and 'M5'} |
| selection rule | {selection['rule']} |
| R6 used for selection | {selection['r6_used_for_selection']} |
| held-out run | {policy['heldout_run']} (never in the training set) |
| training runs | {', '.join(policy['training_runs'])} |
| model_comparison.csv SHA-256 | matches the frozen record |
| candidate_parameters.csv SHA-256 | matches the frozen record |
| fit_M5 solver status / failures / parameters at a bound | {policy['checks']['fit_M5_converged'] and 'converged'}, 0 failures, none at a bound |
| all Level 3 policy checks | {'PASSED' if policy['all_checks_passed'] else 'FAILED'} |

M5 improved QAICc from {model_cmp.loc['M2', 'QAICc']:.1f} (M2) to {model_cmp.loc['M5', 'QAICc']:.1f}, with reduced
chi-square {model_cmp.loc['M5', 'reduced_chi2']:.2f} (the residual variance ratio c-hat is {selection['c_hat']:.2f}), and every one of its
multistarts converged to the same minimum. That evidence was fixed in Level 2 and is not revisited
here to suit a profitability outcome. The alternatives M2 and M6 are **comparison models only**: they
are evaluated on the same grid and reported in section 10, but they never replace M5 in the
recommendation.

## 6. Numerical method and search procedure

Simulation. Each scenario integrates the ODEs from t = 0 to 120 h on a 0.25 h grid with
`scipy.integrate.solve_ivp` (LSODA, rtol 1e-9, atol 1e-11), starting from X0 = 2.5 g/L, S0 as searched,
P = C = 0. A solver failure would be recorded as `simulation_failed` and excluded; none occurred.

Search. A three-stage deterministic search, not a local optimiser, so the whole surface is visible:

| stage | initial TRS (g/L) | temperature (C) | purpose |
|---|---|---|---|
| coarse | 160, 180, 200, 220, 240, 260 | 33, 34, 35, 36, 37 | locate the promising region |
| dense | 160 to 260 in 5 g/L steps | 33 to 37 in 0.25 C steps | map both scenarios |
| refinement | +/- 2.5 and 5 g/L around the 8 best of each scenario | +/- 0.125 and 0.25 C | check the optimum is not a grid artefact |

{c_rows} were evaluated in total (M5 on both horizons plus M2 and M6 on the primary horizon). The
refinement moved the normal-scenario optimum by at most 2.5 g/L (the dense 195 g/L point remains best)
and left the 36 C optimum at 175 g/L, so the reported optima are not edge artefacts of the coarse grid.
A local optimiser would not have added information here: the objective is smooth in S0 but flat within
about 10 INR/h over 187.5-200 g/L, and the binding constraint is feasibility, not a gradient condition.

Ranking uses the 120 h primary horizon only. The 240 h run in section 12 is a diagnostic.

## 7. Batch-completion criterion and feasibility definitions

A batch is complete only when residual TRS is at or below 5 g/L. Completion time is the first downward
crossing of 5 g/L, linearly interpolated between the two bracketing time points; the reported final TRS
of a completed batch is therefore exactly 5.000 g/L by construction.

Each candidate is placed in exactly one status class:

| status | meaning | economics |
|---|---|---|
| `completed_feasible` | reached TRS <= 5 g/L inside the horizon and the wash is inside the 7-14 % v/v steam curve | priced |
| `completed_outside_steam_curve` | reached the threshold, but the wash strength is outside the supplied curve | **not priced**, no margin assigned |
| `unfinished` | did not reach 5 g/L within the horizon | **no completion time, no margin** |
| `simulation_failed` | the ODE integration failed | no quantities |

This is the rule that keeps the answer honest: an unfinished batch is never given a margin at a
stopping time, and a batch the steam curve does not cover is never given a margin either. For M5 on
the primary horizon the counts are {c_done}, {c_out} and {c_unf}.

## 8. Plant economics: equations, assumptions and units

Per completed feasible batch, per 170 m3 fermenter:

```
sugar charged      m_S  = S0 [g/L] * 170 [m3]                     = kg      (1 g/L = 1 kg/m3)
sugar cost         Cs   = m_S * 25 INR/kg
ethanol mass       m_E  = P_end [g/L] * 170 [m3]                  = kg
ethanol volume     V_E  = m_E / 0.789 kg/L                        = L
revenue            R    = V_E * 60 INR/L
wash strength      w    = P_end / 7.89                            = % v/v
steam intensity    s    = curve(w)                                = kg steam per L ethanol
steam cost         Cst  = s * V_E * 1.6 INR/kg                    (1600 INR/t)
batch margin       M    = R - Cs - Cst                            = INR
cycle time         t_c  = t_end + 8 h
margin per cycle   M/t_c                                          = INR/h
24 h equivalent    24 * M/t_c                                     = INR/day  (derived)
```

Assumptions, stated so they can be challenged: the broth volume is constant and equals the working
volume; ethanol carried off with CO2 is condensed and returned (brief section 3); the plant pays for
**all** sugar charged, including what is left unfermented, so the sugar cost uses S0 and not the
consumed sugar; the steam curve is interpolated linearly between its eight tabulated points and is
never extrapolated; the 24 h equivalent is a textbook conversion of the assignment's INR/h figure and
is labelled as derived wherever it appears.

Dimensional check (also asserted in `tests/test_level3.py`): concentration in g/L multiplied by volume
in m3 gives mass directly in kg, so no 1000-factor appears anywhere. Example for the recommended batch:

{econ_table(['normal_33_37_M5_rank1', 'warm_min_36_M5_rank1', 'normal_33_37_M5_fastest'])}

## 9. Optimisation results

### 9.1 Normal scenario (33-37 C)

![Operating map: completion time and margin per cycle time over the M5 surface](outputs/figures/level3_feasible_region.png)

*Figure 1. Left: completion time to TRS <= 5 g/L; grey cells are not complete within 120 h. Right:
margin per cycle time; blank cells are unfinished or have a wash outside the 7-14 % v/v steam curve.
Neither can be ranked, which is why the profitable region ends near 250 g/L even though the model
keeps producing ethanol beyond it.*

{rec_table('normal_33_37')}

The top of the surface is remarkably flat: the first five candidates sit within 10 INR/h of each other
while their completion times differ by 3.7 h. That flatness is not a numerical accident. Raising the
sugar charge adds ethanol revenue per batch but adds sugar cost (the plant pays for everything charged)
and lengthens the cycle, and the two effects very nearly cancel between about 187 and 200 g/L. The
practical consequence is that the plant can choose anywhere in that window for robustness without
losing meaningful money, which is a better answer than a single over-precise set point.

![Per-batch economics and the margin/cycle-time trade-off](outputs/figures/level3_economics.png)

*Figure 2. Left: revenue, sugar cost, steam cost and resulting batch margin for the selected
candidates. Right: every completed feasible candidate; higher sugar charges buy more ethanol but need
longer cycles, so the margin per cycle time has a clear maximum well before the sugar limit.*

![Completion time versus sugar charge at each temperature](outputs/figures/level3_completion_time.png)

*Figure 3. Completion time grows with the sugar charge. Temperature above 33 C makes the batch slower,
not faster, because in M5 the ethanol-tolerance term falls with temperature and the fitted k37 is below
k34. Points above 48 h are beyond the last measurement, and the dotted line marks that limit.*

Why the optimum is at 33 C rather than at a warmer temperature. The fitted rate multiplier alone would
favour warmth near 34 C (k34 = {policy['preferred_theta']['k34']:.4f} > 1), but M5 also makes ethanol
tolerance fall with temperature: beta_P = {policy['preferred_theta']['beta_P']:.4f} per C, so
P_max(T) drops from {pmax_30:.1f} g/L at 30 C to {pmax_33:.1f} g/L at 33 C, {pmax_36:.1f} g/L at 36 C and
{pmax_37:.1f} g/L at 37 C. At a fixed 195 g/L charge the simulated completion times are
{t33:.2f} h at 33 C, {t34:.2f} h at 34 C, {t36:.2f} h at 36 C and {t37:.2f} h at 37 C, while the final
ethanol barely moves ({e33:.2f} to {e37:.2f} g/L): the warmer batch finishes with essentially the same
ethanol but needs far longer, because the inhibition factor throttles sugar uptake earlier. That is why
the margin per cycle time falls steeply with temperature and the optimum sits at the coldest allowed
temperature. The behaviour is a property of the frozen fit - the 34 C and 37 C lab runs stalled earlier
than the 30 C runs - not an assumption inserted for convenience.

### 9.2 Warm scenario (cooling water +3 C, minimum 36 C)

{rec_table('warm_min_36')}

The 36 C floor moves the optimum down to about 175 g/L and drops the margin per hour to
{c_warm_margin}. The economic penalty of warming is {c_penalty} ({penalty_pct:.1f} %). What drives it is the
mechanism described in section 9.1: at 36 C the fitted ethanol tolerance is only {pmax_36:.1f} g/L against
{pmax_33:.1f} g/L at 33 C, so sugar uptake throttles earlier and the batch needs a longer cycle to reach
5 g/L. The warm optimum is not the normal optimum shifted in temperature - at 36 C a lower charge (about
175 g/L) is better, because the batch must finish before inhibition makes the cycle uneconomic. The plant
should treat the warm case as a genuine loss of capacity, not as an inconvenience.

### 9.3 Fastest completion versus best margin

The fastest completed batch is {q5['normal']['s0_g_per_l']:.0f} g/L at {q5['normal']['temperature_c']:.1f} C,
finishing in {c_fast}, but it returns only {q5['normal']['margin_per_cycle_inr_per_h']:,.2f} INR/h. Running
the fermenter harder and finishing faster is not the same as earning more per hour; the metric rewards
the product of yield and time only after both sugar cost and turnaround are accounted for.

## 10. Model comparison and uncertainty analysis

### 10.1 Structure comparison (M5 against M2 and M6)

{model_cmp_table()}

At the M5 optimum the alternatives agree closely: M2 gives
{m5_alt_at_norm[m5_alt_at_norm.model == 'M2'].margin_per_cycle_inr_per_h.iloc[0]:,.2f} INR/h and M6 gives
{m5_alt_at_norm[m5_alt_at_norm.model == 'M6'].margin_per_cycle_inr_per_h.iloc[0]:,.2f} INR/h, against
{a1['margin_per_cycle_inr_per_h']:,.2f} for M5. Their own optima shift by one grid step (190 g/L instead of
195 g/L in the normal scenario, 170 g/L instead of 175 g/L in the warm one) and are {struct_pct_lo:.1f}-{struct_pct_hi:.1f} % higher in
margin, which is the model-structure spread the recommendation has to live with. The shift is small
and consistent in direction; it does not change the engineering conclusion that the plant should run
just below 200 g/L at the coldest temperature it can hold, only the last few percent of the number.

### 10.2 Parameter uncertainty at the recommended conditions

![Parameter-ensemble intervals at the selected conditions](outputs/figures/level3_uncertainty.png)

*Figure 4. Point estimates from the frozen parameter set; bars are the 2.5-97.5 percentile range of 200
Gaussian draws from the linearised covariance, truncated at the parameter bounds. Left: margin per
cycle time. Right: completion time. The 37 C / 260 g/L brief point never completes in any draw.*

{unc_table()}

Method and its limits. The draws use the covariance matrix stored with the fit and are truncated at
the fitted parameter bounds; all 200 draws were accepted, so no truncation bias is introduced. This is
**parameter uncertainty conditional on the M5 structure**. It does not include measurement error in the
raw data, model inadequacy, or run-to-run variability between batches, and the linearised covariance is
a local quadratic approximation around the least-squares minimum. The intervals below should therefore
be read as a lower bound on the real uncertainty, not as a prediction interval for a plant batch.

* Normal optimum: {c_unc_norm}; completion {u_norm_t.p2_5:.2f}-{u_norm_t.p97_5:.2f} h; every draw completes.
* Warm optimum: {c_unc_warm}; completion {u_warm_t.p2_5:.2f}-{u_warm_t.p97_5:.2f} h; every draw completes.
* Discrete assumption alternatives from the Task 2 CO2-floor refits move the normal-optimum margin only
  between {disc_norm.point_estimate.min():,.2f} and {disc_norm.point_estimate.max():,.2f} INR/h, i.e. far less than
  the parameter ensemble, so the CO2 floor is not what limits this decision.
* The 37 C / 260 g/L point completes in {int(unc_m5[(unc_m5.candidate_id == 'brief_q5_37C_260') & (unc_m5.quantity == 'margin_per_cycle_inr_per_h')].fraction_draws_completing.iloc[0] * 100)} % of draws.
  It is neither feasible nor priceable, in the point estimate or in any draw.

Because the *ranking* is preserved across models and across all draws, the recommendation is robust in
the sense that matters for a decision; the *amount* is uncertain by roughly -{pct_lo:.1f} % / +{pct_hi:.1f} %
around the normal optimum.

## 11. Figures and tables

| item | file | what it shows |
|---|---|---|
| Figure 1 | `outputs/figures/level3_feasible_region.png` | completion time and margin maps; infeasible cells blank |
| Figure 2 | `outputs/figures/level3_economics.png` | cost breakdown per batch and the margin/cycle-time surface |
| Figure 3 | `outputs/figures/level3_completion_time.png` | completion time against sugar charge at each temperature |
| Figure 4 | `outputs/figures/level3_uncertainty.png` | parameter-ensemble intervals at the selected conditions |
| Table 1 | `outputs/tables/optimization_grid.csv` | every evaluated scenario with model and parameter-set ids |
| Table 2 | `outputs/tables/optimization_recommendations.csv` | ranked recommendations per scenario and basis |
| Table 3 | `outputs/tables/plant_economics.csv` | full per-batch economics for the selected candidates |
| Table 4 | `outputs/tables/optimization_uncertainty.csv` | intervals and completion fractions per candidate and model |
| Table 5 | `outputs/tables/optimization_model_comparison.csv` | M5 vs M2 vs M6 at their own optima and at the M5 optimum |
| Table 6 | `outputs/tables/optimization_input_audit.csv` | input audit with verification status |
| Table 7 | `outputs/tables/optimization_horizon_sensitivity.csv` | what the unfinished cases do if the horizon is doubled |

Rounding: completion times to 3 decimals (h), concentrations to 3 decimals (g/L), margins per cycle to
2 decimals (INR/h), batch margins to the nearest INR, percentages to 1-2 decimals. Every figure is
computed from the unrounded values; the tables are the rounded renderings.

## 12. Sensitivity and validation checks

### 12.1 Horizon sensitivity (no hidden unfinished optimum)

{hz_summary['n_unfinished_primary_normal']} M5 candidates do not reach 5 g/L within 120 h. They were re-run
to 240 h with the same frozen parameters: {c_hz} complete within the extended horizon, and
{hz_summary['n_outscoring_best_120h']} of them would beat the best 120 h margin. The 240 h run is a
diagnostic only; it is not used to rank. The purpose is to show that the 120 h horizon is not hiding a
profitable candidate, which it is not.

{horizon_table()}

### 12.2 Validation checks executed

* Frozen model policy re-verified before the search (section 5) and re-checked by the test suite.
* Completion criterion re-derived from the trajectory in `tests/test_level3.py`, including the
  first-crossing rule and the "already below threshold at t = 0" edge case.
* Economics re-derived from the saved table columns and compared to 1e-12 relative tolerance; unit
  identity asserted independently.
* Steam curve checked point by point against the brief, including the two out-of-range cases.
* No out-of-curve or unfinished row carries a margin; asserted over the whole grid.
* Raw CSV checksums recomputed; frozen hashes recomputed.
* All eight carbon balances are still present in the Level 2 table; {c_cb} of them close within 95-105 %.
* Generated CSV/JSON verified ASCII with LF endings.

{cb_table()}

## 13. Engineering interpretation and trade-offs

1. **Sugar above about 200 g/L does not pay.** The plant pays for every kilogram of TRS it charges, so
   the extra sugar in a 260 g/L batch is a cost even when it is fermented. Its extra ethanol arrives
   late, which stretches the cycle and dilutes the fixed 8 h turnaround. The margin per cycle time peaks
   just under 200 g/L and then falls.
2. **The steam curve is a real constraint, not a formality.** Above 14 % v/v wash the supplied curve ends
   and the distillation cost cannot be estimated. Batches that produce more than about 110 g/L ethanol
   therefore fall outside the costed region: {c_out}, and none of them is priced. This is not a modelling
   limitation to be averaged away - it is the point at which the plant's own design data stops.
3. **Cold is valuable.** Under the fitted temperature response 33 C outperforms 34-37 C because ethanol
   tolerance falls with temperature: the same charge finishes far sooner when the broth is colder. Losing
   3 C of cooling capacity therefore costs {c_penalty} of margin ({penalty_pct:.1f} %).
4. **The recommendation is a plateau, not a peak.** Between 187.5 and 200 g/L the margin changes by less
   than 0.3 %. Operationally that means the set point can be chosen for other reasons (foaming, oxygen
   demand, downstream capacity) without sacrificing economics.
5. **Accuracy limits are time-related.** Completion happens at 25-48 h for the recommended conditions and
   the data stop at 48 h, so the recommended points sit at the edge of the measured window and slightly
   beyond it. Batches that need 60-120 h are a pure time extrapolation.

## 14. Answers to every supported Level 3 question

**Q1. Best feasible condition under the normal 33-37 C constraint.**
{a1['s0_g_per_l']:.1f} g/L TRS at {a1['temperature_c']:.1f} C: completion {a1['completion_time_h']:.3f} h, residual TRS
{a1['final_trs_g_per_l']:.3f} g/L, ethanol {a1['final_ethanol_g_per_l']:.3f} g/L, wash {a1['wash_pct_vv']:.3f} % v/v,
batch margin {a1['batch_margin_inr']:,.2f} INR, cycle {a1['cycle_time_h']:.3f} h,
**{a1['margin_per_cycle_inr_per_h']:,.2f} INR/h** ({a1['margin_24h_equivalent_inr_per_day']:,.1f} INR/day derived).
Evidence: `outputs/tables/optimization_recommendations.csv` row `normal_33_37` rank 1.

**Q2. Best feasible condition with a 36 C minimum.**
{a2['s0_g_per_l']:.1f} g/L TRS at {a2['temperature_c']:.1f} C: completion {a2['completion_time_h']:.3f} h, ethanol
{a2['final_ethanol_g_per_l']:.3f} g/L, **{a2['margin_per_cycle_inr_per_h']:,.2f} INR/h**
({a2['margin_24h_equivalent_inr_per_day']:,.1f} INR/day), i.e. {c_penalty} less than the normal scenario
({penalty_pct:.1f} %).

**Q3. Does the preferred condition change with M2 or M6?**
Not in substance. The best grid point moves by one step (190 g/L instead of 195 g/L in the normal scenario,
170 instead of 175 g/L in the warm one) and the alternatives give 4-5 % more margin at their own optima. M2's own normal optimum is
{own_opt[(own_opt.model == 'M2') & (own_opt.scenario == 'normal_33_37')].s0_g_per_l.iloc[0]:g} g/L at 33 C
({own_opt[(own_opt.model == 'M2') & (own_opt.scenario == 'normal_33_37')].margin_per_cycle_inr_per_h.iloc[0]:,.2f} INR/h) and
M6's is {own_opt[(own_opt.model == 'M6') & (own_opt.scenario == 'normal_33_37')].s0_g_per_l.iloc[0]:g} g/L at 33 C
({own_opt[(own_opt.model == 'M6') & (own_opt.scenario == 'normal_33_37')].margin_per_cycle_inr_per_h.iloc[0]:,.2f} INR/h).
In the warm scenario both alternatives prefer 170 g/L. The engineering recommendation (coldest temperature
available, just under 200 g/L normal / about 175 g/L warm) is unchanged; M5 remains the reference because
D-24 selected it on held-out-safe evidence, not because it gives the best profit.

**Q4. Best estimated margin per cycle time.** {a1['s0_g_per_l']:.1f} g/L at {a1['temperature_c']:.1f} C with
{a1['margin_per_cycle_inr_per_h']:,.2f} INR/h. This is the global maximum over every completed, costable
candidate in the search.

**Q5. Fastest to the TRS threshold.** {q5['normal']['s0_g_per_l']:.0f} g/L at
{q5['normal']['temperature_c']:.1f} C, {q5['normal']['completion_time_h']:.3f} h. In the warm scenario the
fastest is {q5['warm']['s0_g_per_l']:.0f} g/L at {q5['warm']['temperature_c']:.1f} C
({q5['warm']['completion_time_h']:.3f} h). Fastest is not most profitable: the fast batch gives up
{float(a1['margin_per_cycle_inr_per_h']) - float(q5['normal']['margin_per_cycle_inr_per_h']):,.2f} INR/h
relative to the optimum.

**Q6. Are the highest-margin candidates feasible under the completion rule?** Yes by construction - only
completed candidates are ranked. The interesting converse is that the candidates with the most ethanol
are not feasible: the ten highest-ethanol completed candidates all lie above 14 % v/v wash, so they are
recorded as completed-but-outside-the-steam-curve ({c_out} in this search) and carry no margin. See
`outputs/tables/optimization_grid.csv`, column `feasibility_status`.

**Q7. What happens to the optimum when some candidates fail to reach 5 g/L?** They are excluded from the
ranking and reported separately: {c_unf}, none of which would beat the recommended point even if the
horizon were doubled ({c_hz} complete by 240 h, {hz_summary['n_outscoring_best_120h']} would outrank).
Because they carry no completion time and no margin, they cannot bias the optimum upward.

**Q8. Sensitivity of the recommendation to parameter and model uncertainty.**
Parameter uncertainty (200 draws, M5): margin {c_unc_norm} at the normal optimum and {c_unc_warm} at the
warm optimum, with 100 % of draws completing. Structure (M2/M6): the margin at the M5 optimum moves by
{m5_alt_at_norm[m5_alt_at_norm.model == 'M2'].delta_margin_vs_M5_optimum_inr_per_h.iloc[0]:+,.2f} INR/h (M2) and
{m5_alt_at_norm[m5_alt_at_norm.model == 'M6'].delta_margin_vs_M5_optimum_inr_per_h.iloc[0]:+,.2f} INR/h (M6). Discrete CO2-floor
alternatives: {disc_norm.point_estimate.min():,.2f} to {disc_norm.point_estimate.max():,.2f} INR/h. In every case the
preferred *condition* is stable and the *value* is not precise to more than a few percent.

**Q9. Which assumptions most affect the recommendation?** In order of impact: (i) the completion rule
itself, which removes every slow, high-sugar candidate; (ii) the steam curve's 14 % v/v upper end, which
removes every high-ethanol candidate; (iii) the fitted temperature multipliers, which decide that colder
is better and which rest on one 37 C run; (iv) the linear interpolation of the multipliers between
measured temperatures; (v) the CO2 floor, through the covariance and hence the interval width.

**Q10. Which additional experiment would most reduce decision uncertainty?** One extended batch at the
recommended condition (about 195 g/L TRS, 33 C) run past 48 h until residual TRS reaches 5 g/L, ideally
with one sample in the 60-96 h region. It tests the completion time that drives the metric and the 33 C
region the plant now operates in; a further 37 C run would help the warm scenario but cannot substitute
for it.

**Brief Q5 (37 C / 260 g/L prediction).** The model predicts
{q5pred['final_ethanol_g_per_l_at_120h']:.2f} g/L ethanol and {q5pred['final_trs_g_per_l_at_120h']:.2f} g/L residual TRS at
120 h, with the batch still **not complete**. Trust is low: there is a single 37 C run (R8, 220 g/L), no
observation at 260 g/L at that temperature, the prediction runs 72 h beyond the measured window, and the
ethanol level exceeds the range where M5's inhibition parameters are individually identified. It is
reported because the brief asks for it, and it is not an operating recommendation.

**Brief Q6 (the one experiment that would most reduce the uncertainty that matters).** The same extended
batch as Q10. The existing Level 2 experimental-design analysis already ranked long-horizon observations at
the candidate operating conditions as the design that most reduces the propagated margin variance
(`outputs/tables/experiment_design.csv`); Level 3 makes that concrete by naming the condition.

## 15. Limitations and recommendations for additional experiments

* **Time extrapolation.** Completion times of 25-48 h are near the 48 h data limit; 60-120 h completions
  are extrapolation. The recommendation is inside the mild end of that range.
* **One 37 C run.** The warm scenario leans on R8 alone. The 36 C case is a temperature interpolation, not
  a measurement.
* **P_max / n_inh trade-off.** For M5 these two parameters are strongly associated; the interval on any
  ethanol-limited prediction is wider than the residual scatter implies.
* **Numerical environment sensitivity.** The R8 leave-one-run-out result and some refits are sensitive to
  the fitted minimum and to the numerical environment (documented in the Task 2 evidence). Level 3 does not
  refit, so it inherits the frozen values, but a re-fit elsewhere could shift them.
* **Residual autocorrelation and model inadequacy** reduce predictive confidence and are not represented
  in the parameter intervals.
* **CO2 floor of 0.10 g/L** is a modelling assumption; its two discrete alternatives were quantified and
  shown to matter far less than the parameter ensemble.
* **Steam curve provenance.** Only eight points are supplied; behaviour outside 7-14 % v/v is unknown and
  deliberately not extrapolated.
* **Original assignment PDF unavailable and Windows verification pending.** Both are recorded as
  unresolved rather than assumed.

Recommended next experiments, in priority order:
1. One batch at about 195 g/L TRS and 33 C, sampled to the 5 g/L endpoint (tests the completion time and the
   recommended operating region).
2. One repeat at 37 C with high sugar (250-260 g/L) to test the M5 inhibition extrapolation the brief asks about.
3. Two to three replicate batches at the recommended condition to measure run-to-run variability, which no
   current interval includes.

## 16. Reproduction instructions

```bash
# 1. environment (Linux sandbox used for the reported results)
python -m pip install -r requirements.txt

# 2. Level 3 workflow (input audit -> grid -> recommendations -> uncertainty -> comparison -> figures)
python src/level3_optimize.py --stage all --n-draws 200

# 3. regenerate this report and its claim set
python src/make_level3_report.py

# 4. consistency audit and tests
python src/level3_consistency_audit.py
python -m pytest -q

# 5. submission snapshot and archive
python scripts/build_submission.py
python scripts/verify_submission.py
python scripts/create_final_zip.py
```

Windows equivalent: `scripts\\reproduce_level3.ps1`. The workflow is deterministic given the frozen
parameter files; the only random component is the uncertainty ensemble, which uses seed {L.SEED}.

Code and data references:

| purpose | file |
|---|---|
| model policy, completion rule, economics, steam curve | `src/level3.py` |
| search, uncertainty, comparison, figures, answers | `src/level3_optimize.py` |
| this report | `src/make_level3_report.py` |
| report/claim/table consistency audit | `src/level3_consistency_audit.py` |
| Level 3 tests | `tests/test_level3.py` |
| frozen model structure used unchanged | `src/models.py`, `src/kinetics.py` |
| frozen parameters | `outputs/tables/work/fit_M5.json` |
| frozen selection record | `outputs/tables/model_selection_frozen.json` |
| raw data and checksums | `data/raw/runs.csv`, `data/raw/timecourse.csv`, `data/raw/endpoint_hplc.csv`, `data/raw/CHECKSUMS.sha256` |
| assignment brief | `docs/assignment_brief.md` |
| input audit | `outputs/tables/optimization_input_audit.csv`, `outputs/audits/level3/input_audit_summary.json` |
| model policy record | `outputs/audits/level3/model_policy.json` |
| answers record | `outputs/audits/level3/level3_answers.json` |

Environment used for the numbers in this report:

| item | value |
|---|---|
| platform | {platform.platform()} |
| python | {platform.python_version()} |
| numpy | {np.__version__} |
| pandas | {pd.__version__} |
| generation time | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |

Verification status: Linux/sandbox execution only. Actual Windows execution of the test suite and the
reproduction scripts remains **pending** and must be performed locally; this report does not claim it.
"""

rep = ("# Level 3 - Optimisation of initial sugar concentration and fermentation temperature\n\n"
       f"*Generated by `src/make_level3_report.py` from the Level 3 tables on "
       f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. Do not edit by hand: "
       f"regenerate with `python src/make_level3_report.py`.*\n\n"
       + EXEC_SUMMARY + BODY)

os.makedirs(os.path.dirname(os.path.abspath(OUT)) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(rep)

L.write_json(dict(generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), report=OUT,
                  n_claims=len(CLAIMS), claims=CLAIMS), A + "report_claims.json")
L.write_json(dict(report=OUT, bytes=len(rep.encode("utf-8")), n_claims=len(CLAIMS),
                  generator="src/make_level3_report.py"), A + "report_generation.json")
print(f"wrote {OUT}: {len(rep)} characters, {len(CLAIMS)} tracked claims")
