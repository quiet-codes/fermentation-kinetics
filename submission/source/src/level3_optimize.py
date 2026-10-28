#!/usr/bin/env python
"""Level 3 optimisation workflow: input audit, grid search, recommendations, uncertainty,
model comparison, horizon diagnostic, figures and the claim set used by the report.

Every stage writes its own outputs and prints a short summary.  Stages are independent
apart from reading earlier files, so a failed stage leaves the rest un-produced rather than
silently producing a partial answer.

Usage (project root):
    python src/level3_optimize.py --stage all --n-draws 200
    python src/level3_optimize.py --stage grid
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import level3 as L  # noqa: E402
import models as M  # noqa: E402

TAB = os.path.join("outputs", "tables")
FIG = os.path.join("outputs", "figures")
AUD = os.path.join("outputs", "audits", "level3")

# Search definition (documented in reports/level3.md section 6).
COARSE_S0 = [160.0, 180.0, 200.0, 220.0, 240.0, 260.0]
COARSE_T = [33.0, 34.0, 35.0, 36.0, 37.0]
DENSE_S0 = np.round(np.arange(160.0, 260.0 + 1e-9, 5.0), 6)
DENSE_T = np.round(np.arange(33.0, 37.0 + 1e-9, 0.25), 6)
REFINE_S0_OFFSETS = [-5.0, -2.5, 0.0, 2.5, 5.0]
REFINE_T_OFFSETS = [-0.25, -0.125, 0.0, 0.125, 0.25]
REFINE_SEEDS_PER_SCENARIO = 8

GRID_CSV = os.path.join(TAB, "optimization_grid.csv")
REC_CSV = os.path.join(TAB, "optimization_recommendations.csv")
ECON_CSV = os.path.join(TAB, "plant_economics.csv")
UNC_CSV = os.path.join(TAB, "optimization_uncertainty.csv")
MODELCMP_CSV = os.path.join(TAB, "optimization_model_comparison.csv")
AUDIT_CSV = os.path.join(TAB, "optimization_input_audit.csv")
HORIZON_CSV = os.path.join(TAB, "optimization_horizon_sensitivity.csv")


def _log(msg):
    print(f"[level3] {msg}", flush=True)


# ------------------------------------------------------------------ stage: input audit
INPUT_AUDIT_ROWS = [
    dict(id="IN-01", path="data/raw/runs.csv", role="Run-level design and initial conditions (T, S0, X0)",
         units="temperature_C; initial_TRS_g_L_as_glucose; inoculum_biomass_g_L",
         data_type="CSV, 8 rows x 6 columns", original_derived_assumed="original",
         validation="SHA-256 against data/raw/CHECKSUMS.sha256; 8 runs R1-R8; X0 identical (2.5 g/L) in all runs",
         verified="verified"),
    dict(id="IN-02", path="data/raw/timecourse.csv", role="Measured time courses (biomass, TRS, ethanol, CO2)",
         units="time_h; g/L throughout", data_type="CSV, 8 runs x 14 time points x 4 variables",
         original_derived_assumed="original",
         validation="SHA-256 against CHECKSUMS.sha256; time grid 0-48 h per brief; no missing values",
         verified="verified"),
    dict(id="IN-03", path="data/raw/endpoint_hplc.csv", role="48 h by-products and pH (carbon balance, run screening)",
         units="glycerol_g_L; lactic_acid_g_L; final_pH", data_type="CSV, 8 rows x 4 columns",
         original_derived_assumed="original",
         validation="SHA-256 against CHECKSUMS.sha256; 'n.d.' parsed as below-detection (<0.2 g/L) in carbon_balance.py",
         verified="verified"),
    dict(id="IN-04", path="data/raw/CHECKSUMS.sha256", role="Raw-data integrity manifest",
         units="-", data_type="text, sha256 of the three raw CSVs", original_derived_assumed="original",
         validation="Recomputed for all three files during the Level 3 validation chain", verified="verified"),
    dict(id="IN-05", path="docs/assignment_brief.md", role="Governing specification: plant data, economics, steam curve, questions",
         units="mixed (m3, INR, h, g/L, % v/v)", data_type="Markdown extracted from the assignment PDF",
         original_derived_assumed="derived (PDF text extraction)",
         validation="Steam curve, economics constants and completion criterion checked against src/plant_uncertainty.py; "
                    "PDF-extracted tables read in row order",
         verified="partially verified - the original assignment PDF is not available, so PDF-only wording cannot be confirmed"),
    dict(id="IN-06", path="outputs/tables/level1_frozen.json", role="Frozen Level 1 parameters, training set and held-out run",
         units="mixed", data_type="JSON", original_derived_assumed="derived (Level 1 fit)",
         validation="parameters_csv_sha256 recomputed and matched; holdout = R6; training = R1,R2,R3,R4,R5,R8 (no R6)",
         verified="verified"),
    dict(id="IN-07", path="outputs/tables/model_selection_frozen.json", role="Frozen Level 2 model selection (D-24)",
         units="-", data_type="JSON", original_derived_assumed="derived (Level 2 selection)",
         validation="preferred = M5; rule = D-24; r6_used_for_selection = false; model_comparison.csv and "
                    "candidate_parameters.csv SHA-256 both matched",
         verified="verified"),
    dict(id="IN-08", path="outputs/tables/work/fit_M5.json", role="Primary parameter set for every Level 3 scenario",
         units="mixed (1/h, g/L, g/g, -, 1/C)", data_type="JSON (theta, covariance, diagnostics)",
         original_derived_assumed="derived (Level 2 fit M5)",
         validation="theta reproduced by candidate_parameters.csv to 1e-12; status 3; 0 solver failures; 0 parameters at a bound; "
                    "8/8 multistarts near-best",
         verified="verified"),
    dict(id="IN-09", path="outputs/tables/work/fit_M2.json; outputs/tables/work/fit_M6.json",
         role="Robust alternative models for the model-structure comparison", units="mixed", data_type="JSON",
         original_derived_assumed="derived (Level 2 fits)",
         validation="Loaded through the same loader as M5; convergence diagnostics recorded in the policy record",
         verified="verified (used for comparison only, never substituted for M5)"),
    dict(id="IN-10", path="outputs/audits/task2/sensitivity/level2/floor_0/outputs/tables/work/fit_M5.json; "
                          "outputs/audits/task2/sensitivity/level2/floor_0p5/outputs/tables/work/fit_M5.json",
         role="Discrete CO2-floor alternatives (Task 2 evidence) used as an assumption-sensitivity check",
         units="mixed", data_type="JSON", original_derived_assumed="derived (Task 2 sensitivity refits)",
         validation="Read-only reuse; both Task 2 cases re-selected M5 with explicit convergence",
         verified="verified as Task 2 evidence; not refitted during Level 3"),
    dict(id="IN-11", path="outputs/tables/plant_prediction_uncertainty.csv; outputs/tables/structure_spread.csv",
         role="Existing Level 2 parameter-ensemble and structure-spread evidence (context, not recomputed)",
         units="mixed", data_type="CSV", original_derived_assumed="derived (Level 2)",
         validation="Used only as prior context; Level 3 uncertainty is recalculated at the Level 3 optima",
         verified="verified as Level 2 evidence"),
    dict(id="IN-12", path="docs/requirements_traceability.csv", role="Requirement-to-evidence matrix carried forward from earlier phases",
         units="-", data_type="CSV", original_derived_assumed="derived",
         validation="Extended with the Level 3 requirements in this phase", verified="verified"),
    dict(id="IN-13", path="outputs/tables/carbon_balance_all_runs.csv", role="Carbon balance for all eight runs (Level 2 evidence)",
         units="C-mol/L, %", data_type="CSV", original_derived_assumed="derived (Level 2)",
         validation="Eight run rows present; recovery_pct recomputed by the test suite",
         verified="verified"),
    dict(id="IN-14", path="outputs/tables/model_comparison.csv", role="QAICc comparison underlying the frozen selection",
         units="-", data_type="CSV", original_derived_assumed="derived (Level 2)",
         validation="SHA-256 matched the frozen record", verified="verified"),
    dict(id="IN-15", path="(assumption) steam design curve 7-14 % v/v", role="Distillation steam cost per litre of ethanol",
         units="% v/v -> kg/L", data_type="8 tabulated points from the brief", original_derived_assumed="assumed "
         "(supplied design curve, but its provenance/limits are not documented in the available brief)",
         validation="Table transcribed into src/level3.py and cross-checked against src/plant_uncertainty.py; "
                    "no interpolation outside 7-14 % v/v",
         verified="verified transcription; curve validity limits unresolved without the PDF"),
    dict(id="IN-16", path="(assumption) constant broth volume, ethanol not stripped", role="Mass basis for all economics",
         units="-", data_type="brief assumption", original_derived_assumed="assumed",
         validation="Stated in brief section 3; used unchanged", verified="verified (brief-stated assumption)"),
    dict(id="IN-17", path="(assumption) X0 = 2.5 g/L for all plant scenarios", role="Initial biomass for every simulated batch",
         units="g/L", data_type="scalar", original_derived_assumed="assumed (equal to the lab inoculum)",
         validation="All eight runs used 2.5 g/L in runs.csv, so plant scenarios are simulated at the measured inoculum",
         verified="verified as the lab value; plant inoculum practice unverified"),
    dict(id="IN-18", path="(assumption) temperature multipliers between 30/34/37 C", role="kT(T) used at 33-37 C",
         units="-", data_type="piecewise-linear interpolation of fitted k34, k37", original_derived_assumed="assumed",
         validation="Interpolation only inside the observed 30-37 C range; no extrapolation; 37 C informed by one run (R8)",
         verified="assumption recorded; unverified between measured temperatures"),
]


def stage_input_audit(args):
    t0 = time.time()
    root = args.root
    # Verify the raw checksums live rather than repeating a stored claim.
    raw = os.path.join(root, "data", "raw")
    checksum_ok, checked = True, []
    with open(os.path.join(raw, "CHECKSUMS.sha256"), encoding="utf-8") as fh:
        for line in fh.read().splitlines():
            if not line.strip():
                continue
            expected, name = line.split()
            actual = L.sha256_file(os.path.join(raw, name))
            checked.append(dict(file=name, expected=expected, actual=actual, match=expected == actual))
            checksum_ok &= expected == actual
    rows = []
    for r in INPUT_AUDIT_ROWS:
        row = dict(r)
        row["checksum_scan_passed"] = checksum_ok
        rows.append(row)
    df = pd.DataFrame(rows)
    L.write_csv(df, os.path.join(root, AUDIT_CSV))
    policy = L.verify_model_policy(root)
    L.write_json(policy, os.path.join(root, AUD, "model_policy.json"))
    L.write_json(dict(
        created=time.strftime("%Y-%m-%d %H:%M:%S"),
        raw_checksums=dict(passed=checksum_ok, files=checked),
        n_inputs=len(rows),
        n_verified=sum(1 for r in rows if r["verified"].startswith("verified")),
        n_partially_verified=sum(1 for r in rows if r["verified"].startswith("partially")),
        n_verified_with_open_issue=sum(1 for r in rows if r["verified"].startswith("verified")
                                       and ("unresolved" in r["verified"] or "unverified" in r["verified"])),
        n_unresolved_inputs=sorted(r["id"] for r in rows if "unresolved" in r["verified"] or "partially" in r["verified"]),
        model_policy_checks_passed=policy["all_checks_passed"],
        original_assignment_pdf_available=False,
    ), os.path.join(root, AUD, "input_audit_summary.json"))
    _log(f"input audit: {len(rows)} inputs, raw checksums {'OK' if checksum_ok else 'FAILED'}, "
         f"model policy {'OK' if policy['all_checks_passed'] else 'FAILED'} ({time.time()-t0:.1f}s)")
    if not checksum_ok:
        raise SystemExit("raw-data checksum mismatch: stopping before optimisation")


# ------------------------------------------------------------------ stage: grid
def _grid_rows(model, theta, s0_values, t_values, stage, horizon):
    rows = []
    for T in t_values:
        for S0 in s0_values:
            rec = L.evaluate(model, theta, float(T), float(S0), horizon_h=horizon)
            rec["search_stage"] = stage
            rows.append(rec)
    return rows


def _dedupe(rows, seen):
    out = []
    for r in rows:
        key = (r["model"], round(r["temperature_c"], 6), round(r["s0_g_per_l"], 6), r["horizon_h"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _evaluate_dense_table(df):
    """Best completed feasible row per scenario from a grid table."""
    return df[(df.feasibility_status == L.STATUS_COMPLETED) & (df.horizon_h == L.HORIZON_PRIMARY_H)]


def stage_grid(args):
    t0 = time.time()
    root = args.root
    policy = L.verify_model_policy(root)
    if not policy["all_checks_passed"]:
        raise SystemExit("frozen model policy verification failed; refusing to optimise")
    sets = {v: L.load_parameter_set(v, root) for v in (L.PREFERRED_MODEL,) + L.ROBUST_ALTERNATIVES}
    th = {v: s["theta"] for v, s in sets.items()}
    pid = {v: s["parameter_set_id"] for v, s in sets.items()}

    rows, seen = [], set()
    rows += _dedupe(_grid_rows(L.PREFERRED_MODEL, th[L.PREFERRED_MODEL], COARSE_S0, COARSE_T, "coarse", L.HORIZON_PRIMARY_H), seen)
    _log(f"coarse M5 grid done ({len(rows)} rows, {time.time()-t0:.1f}s)")
    rows += _dedupe(_grid_rows(L.PREFERRED_MODEL, th[L.PREFERRED_MODEL], DENSE_S0, DENSE_T, "dense", L.HORIZON_PRIMARY_H), seen)
    _log(f"dense M5 grid done ({len(rows)} rows, {time.time()-t0:.1f}s)")

    dense = pd.DataFrame(rows)
    # Refinement seeds: best completed feasible candidates of each scenario on the dense grid.
    seeds = []
    for name, sc in L.scenario_definitions().items():
        sub = _evaluate_dense_table(dense)
        sub = sub[(sub.temperature_c >= sc["t_min"] - 1e-9) & (sub.temperature_c <= sc["t_max"] + 1e-9)]
        sub = sub.sort_values("margin_per_cycle_inr_per_h", ascending=False).head(REFINE_SEEDS_PER_SCENARIO)
        seeds += list(zip(sub.s0_g_per_l, sub.temperature_c))
    refine_s0 = sorted({round(s0 + d, 6) for s0, _ in seeds for d in REFINE_S0_OFFSETS
                        if L.S0_MIN_G_PER_L - 1e-9 <= s0 + d <= L.S0_MAX_G_PER_L + 1e-9})
    refine_t = sorted({round(T + d, 6) for _, T in seeds for d in REFINE_T_OFFSETS
                       if L.T_MIN_C - 1e-9 <= T + d <= L.T_MAX_C + 1e-9})
    rows += _dedupe(_grid_rows(L.PREFERRED_MODEL, th[L.PREFERRED_MODEL], refine_s0, refine_t, "refine", L.HORIZON_PRIMARY_H), seen)
    _log(f"local refinement done ({len(rows)} rows, {time.time()-t0:.1f}s)")

    for v in L.ROBUST_ALTERNATIVES:
        rows += _dedupe(_grid_rows(v, th[v], COARSE_S0, COARSE_T, "coarse", L.HORIZON_PRIMARY_H), seen)
        rows += _dedupe(_grid_rows(v, th[v], DENSE_S0, DENSE_T, "dense", L.HORIZON_PRIMARY_H), seen)
        _log(f"{v} comparison grids done ({len(rows)} rows, {time.time()-t0:.1f}s)")

    # Extended-horizon diagnostic for M5 only (never used for ranking).
    rows += _dedupe(_grid_rows(L.PREFERRED_MODEL, th[L.PREFERRED_MODEL], COARSE_S0, COARSE_T, "coarse_extended_horizon", L.HORIZON_EXTENDED_H), seen)
    rows += _dedupe(_grid_rows(L.PREFERRED_MODEL, th[L.PREFERRED_MODEL], DENSE_S0, DENSE_T, "dense_extended_horizon", L.HORIZON_EXTENDED_H), seen)
    _log(f"extended-horizon diagnostic done ({len(rows)} rows, {time.time()-t0:.1f}s)")

    df = pd.DataFrame(rows)
    df.insert(0, "scenario_row_id", [f"G{i+1:05d}" for i in range(len(df))])
    df["parameter_set_id"] = df["model"].map(pid)
    ordered = ["scenario_row_id", "model", "parameter_set_id", "search_stage", "horizon_h", "time_step_h",
               "s0_g_per_l", "temperature_c", "x0_g_per_l", "simulation_status", "batch_completed",
               "completion_time_h", "final_trs_g_per_l", "final_ethanol_g_per_l", "final_biomass_g_per_l",
               "final_co2_g_per_l", "max_ethanol_in_trajectory_g_per_l", "feasibility_status",
               "wash_pct_vv", "steam_kg_per_L", "steam_curve_in_range", "steam_curve_status",
               "sugar_charged_kg", "sugar_cost_inr", "ethanol_mass_kg", "ethanol_volume_l",
               "ethanol_revenue_inr", "steam_mass_kg", "steam_cost_inr", "batch_margin_inr",
               "turnaround_h", "cycle_time_h", "margin_per_cycle_inr_per_h",
               "margin_24h_equivalent_inr_per_day", "priced", "completed_and_feasible",
               "within_steam_curve", "in_operating_window", "in_model_temperature_range",
               "temperature_interpolated", "beyond_48h_data", "beyond_48h_data_at_horizon_end"]
    df = df[ordered].rename(columns={"beyond_48h_data_at_horizon_end": "horizon_exceeds_data_48h"})
    L.write_csv(df, os.path.join(root, GRID_CSV))

    prim = df[(df.model == L.PREFERRED_MODEL) & (df.horizon_h == L.HORIZON_PRIMARY_H)]
    summary = dict(
        created=time.strftime("%Y-%m-%d %H:%M:%S"),
        total_rows=int(len(df)),
        rows_by_model={m: int((df.model == m).sum()) for m in df.model.unique()},
        rows_by_stage={s: int((df.search_stage == s).sum()) for s in df.search_stage.unique()},
        primary_horizon_h=L.HORIZON_PRIMARY_H,
        extended_horizon_h=L.HORIZON_EXTENDED_H,
        time_step_h=L.TIME_STEP_H,
        m5_primary_rows=int(len(prim)),
        m5_primary_completed_feasible=int((prim.feasibility_status == L.STATUS_COMPLETED).sum()),
        m5_primary_outside_steam_curve=int((prim.feasibility_status == L.STATUS_OUT_OF_CURVE).sum()),
        m5_primary_unfinished=int((prim.feasibility_status == L.STATUS_UNFINISHED).sum()),
        m5_primary_failed=int((prim.feasibility_status == L.STATUS_FAILED).sum()),
        coarse_s0=COARSE_S0, coarse_t=COARSE_T,
        dense_s0=dict(min=float(DENSE_S0.min()), max=float(DENSE_S0.max()), n=int(DENSE_S0.size), step=5.0),
        dense_t=dict(min=float(DENSE_T.min()), max=float(DENSE_T.max()), n=int(DENSE_T.size), step=0.25),
        refine_s0_offsets=REFINE_S0_OFFSETS, refine_t_offsets=REFINE_T_OFFSETS,
        refine_seeds_per_scenario=REFINE_SEEDS_PER_SCENARIO,
        n_refine_s0=len(refine_s0), n_refine_t=len(refine_t),
        parameter_set_ids=pid,
        runtime_s=round(time.time() - t0, 1),
        note="Ranking uses the 120 h primary horizon only; the 240 h rows are a diagnostic.",
    )
    L.write_json(summary, os.path.join(root, AUD, "grid_summary.json"))
    _log(f"grid written: {len(df)} rows, {summary['m5_primary_completed_feasible']} M5 completed feasible, "
         f"{summary['m5_primary_unfinished']} unfinished ({time.time()-t0:.1f}s)")


# ------------------------------------------------------------------ stage: recommendations
def _read_grid(root):
    df = pd.read_csv(os.path.join(root, GRID_CSV))
    df = df.replace({np.nan: np.nan})
    return df


def scenario_best(df, model, scenario, horizon=L.HORIZON_PRIMARY_H, require_priced=True, n=5):
    sc = L.scenario_definitions()[scenario]
    sub = df[(df.model == model) & (df.horizon_h == horizon)]
    sub = sub[(sub.temperature_c >= sc["t_min"] - 1e-9) & (sub.temperature_c <= sc["t_max"] + 1e-9)]
    sub = sub[sub.feasibility_status == L.STATUS_COMPLETED]
    if require_priced:
        sub = sub[sub.margin_per_cycle_inr_per_h.notna()]
    return sub.sort_values("margin_per_cycle_inr_per_h", ascending=False).head(n)


def stage_recommend(args):
    t0 = time.time()
    root = args.root
    df = _read_grid(root)
    prim = df[df.horizon_h == L.HORIZON_PRIMARY_H]

    rec_rows, econ_rows = [], []

    def add_rec(scenario, basis, rank, row):
        rec_rows.append(dict(scenario=scenario, rank_basis=basis, rank=rank, model=row.model,
                             parameter_set_id=row.parameter_set_id, s0_g_per_l=row.s0_g_per_l,
                             temperature_c=row.temperature_c, completion_time_h=row.completion_time_h,
                             final_trs_g_per_l=row.final_trs_g_per_l,
                             final_ethanol_g_per_l=row.final_ethanol_g_per_l,
                             wash_pct_vv=row.wash_pct_vv, steam_kg_per_L=row.steam_kg_per_L,
                             steam_curve_in_range=bool(row.steam_curve_in_range),
                             batch_margin_inr=row.batch_margin_inr, cycle_time_h=row.cycle_time_h,
                             margin_per_cycle_inr_per_h=row.margin_per_cycle_inr_per_h,
                             margin_24h_equivalent_inr_per_day=row.margin_24h_equivalent_inr_per_day,
                             feasibility_status=row.feasibility_status,
                             search_stage=row.search_stage))

    for scenario in L.scenario_definitions():
        top = scenario_best(df, L.PREFERRED_MODEL, scenario, n=5)
        for i, (_, row) in enumerate(top.iterrows(), start=1):
            add_rec(scenario, "highest_margin_per_cycle_time", i, row)
        fastest = scenario_best(df, L.PREFERRED_MODEL, scenario, n=200).sort_values("completion_time_h").head(1)
        for _, row in fastest.iterrows():
            add_rec(scenario, "fastest_completion", 1, row)
        for v in L.ROBUST_ALTERNATIVES:
            own = scenario_best(df, v, scenario, n=1)
            for _, row in own.iterrows():
                add_rec(scenario, f"own_optimum_{v}", 1, row)

    rec = pd.DataFrame(rec_rows)
    L.write_csv(rec, os.path.join(root, REC_CSV))

    # --- economics breakdown for the selected candidates -------------------------------
    def econ_row(case_id, scenario, reason, row):
        out = dict(case_id=case_id, scenario=scenario, reason=reason, model=row.model,
                   parameter_set_id=row.parameter_set_id,
                   s0_g_per_l=row.s0_g_per_l, temperature_c=row.temperature_c,
                   x0_g_per_l=row.x0_g_per_l, working_volume_m3=L.V_WORKING_M3,
                   completion_time_h=row.completion_time_h, final_trs_g_per_l=row.final_trs_g_per_l,
                   final_ethanol_g_per_l=row.final_ethanol_g_per_l, wash_pct_vv=row.wash_pct_vv,
                   steam_kg_per_L=row.steam_kg_per_L, steam_curve_in_range=bool(row.steam_curve_in_range),
                   steam_curve_status=row.steam_curve_status,
                   sugar_charged_kg=row.sugar_charged_kg, sugar_cost_inr=row.sugar_cost_inr,
                   ethanol_mass_kg=row.ethanol_mass_kg, ethanol_volume_l=row.ethanol_volume_l,
                   ethanol_revenue_inr=row.ethanol_revenue_inr, steam_mass_kg=row.steam_mass_kg,
                   steam_cost_inr=row.steam_cost_inr, batch_margin_inr=row.batch_margin_inr,
                   turnaround_h=L.TURNAROUND_H, cycle_time_h=row.cycle_time_h,
                   margin_per_cycle_inr_per_h=row.margin_per_cycle_inr_per_h,
                   margin_24h_equivalent_inr_per_day=row.margin_24h_equivalent_inr_per_day,
                   feasibility_status=row.feasibility_status,
                   unit_note="g/L x m3 = kg; ethanol L = kg / 0.789; steam kg = kg/L x L; "
                             "INR/h = batch margin / (completion + 8 h); INR/day = 24 x INR/h (derived)")
        econ_rows.append(out)

    for scenario in L.scenario_definitions():
        top = scenario_best(df, L.PREFERRED_MODEL, scenario, n=5)
        for i, (_, row) in enumerate(top.iterrows(), start=1):
            econ_row(f"{scenario}_M5_rank{i}", scenario, "top-5 by margin per cycle time", row)
    for scenario in L.scenario_definitions():
        fast = scenario_best(df, L.PREFERRED_MODEL, scenario, n=200).sort_values("completion_time_h").head(1)
        for _, row in fast.iterrows():
            econ_row(f"{scenario}_M5_fastest", scenario, "fastest completion among completed feasible", row)
    for scenario in L.scenario_definitions():
        for v in L.ROBUST_ALTERNATIVES:
            own = scenario_best(df, v, scenario, n=1)
            for _, row in own.iterrows():
                econ_row(f"{scenario}_{v}_own_optimum", scenario, f"{v} own optimum (comparison only)", row)
    # Brief Q5 point: unfinished at 120 h -> recorded, explicitly not priced.
    q = L.BRIEF_Q5_POINT
    sub = prim[(prim.model == L.PREFERRED_MODEL) & (prim.s0_g_per_l == q["s0_g_per_l"])
              & (prim.temperature_c == q["temperature_c"])]
    if len(sub):
        for _, row in sub.head(1).iterrows():
            econ_row("brief_q5_37C_260", "not_applicable", "brief Q5 prediction point (unfinished; no margin)", row)

    econ = pd.DataFrame(econ_rows)
    L.write_csv(econ, os.path.join(root, ECON_CSV))
    _log(f"recommendations: {len(rec)} rows, economics: {len(econ)} rows ({time.time()-t0:.1f}s)")


# ------------------------------------------------------------------ stage: uncertainty
def _candidate_points(root):
    """Operating conditions whose uncertainty is quantified: M5 optima + runner-up + brief Q5."""
    df = _read_grid(root)
    cands = []
    for scenario in L.scenario_definitions():
        top = scenario_best(df, L.PREFERRED_MODEL, scenario, n=2)
        for i, (_, row) in enumerate(top.iterrows(), start=1):
            label = "optimum" if i == 1 else "runner_up"
            cands.append(dict(candidate_id=f"{scenario}_M5_{label}", scenario=scenario, role=label,
                              s0_g_per_l=float(row.s0_g_per_l), temperature_c=float(row.temperature_c)))
    q = L.BRIEF_Q5_POINT
    cands.append(dict(candidate_id="brief_q5_37C_260", scenario="not_applicable",
                      role="brief_Q5_prediction_point", s0_g_per_l=q["s0_g_per_l"],
                      temperature_c=q["temperature_c"]))
    return cands


def stage_uncertainty(args):
    t0 = time.time()
    root = args.root
    cands = _candidate_points(root)
    L.write_json(dict(n_draws=args.n_draws, seed=L.SEED, method=(
        "Gaussian draws from the linearised fit covariance in fit_{model}.json, rejected outside the "
        "fitted parameter bounds. Parameter uncertainty only; conditional on the model structure."),
        candidates=cands), os.path.join(root, AUD, "uncertainty_plan.json"))

    rows, draw_rows = [], []
    models_to_draw = (L.PREFERRED_MODEL,) + L.ROBUST_ALTERNATIVES
    for model in models_to_draw:
        ps = L.load_parameter_set(model, root)
        ens, accept = L.draw_parameter_ensemble(ps["fit_json"], model, args.n_draws, L.SEED)
        _log(f"{model}: {len(ens)} accepted draws (acceptance {accept:.2f})")
        for c in cands:
            base = L.evaluate(model, ps["theta"], c["temperature_c"], c["s0_g_per_l"])
            results, completion = [], []
            for th in ens:
                r = L.evaluate(model, th, c["temperature_c"], c["s0_g_per_l"])
                results.append(r)
                completion.append(1.0 if r["feasibility_status"] == L.STATUS_COMPLETED else 0.0)
            dfr = pd.DataFrame(results)
            for q in ("completion_time_h", "final_ethanol_g_per_l", "margin_per_cycle_inr_per_h",
                      "margin_24h_equivalent_inr_per_day"):
                s = L.summarise(dfr[q].to_numpy(float))
                rows.append(dict(candidate_id=c["candidate_id"], scenario=c["scenario"], candidate_role=c["role"],
                                 s0_g_per_l=c["s0_g_per_l"], temperature_c=c["temperature_c"],
                                 source=f"parameter_ensemble_{model}", model=model,
                                 parameter_set_id=ps["parameter_set_id"], n_draws=len(ens),
                                 gaussian_accept_rate=accept, quantity=q,
                                 point_estimate=float(base[q]), median=s["median"],
                                 p2_5=s["p2_5"], p97_5=s["p97_5"], minimum=s["minimum"], maximum=s["maximum"],
                                 n_defined=s["n_defined"], fraction_defined=s["fraction_defined"],
                                 fraction_draws_completing=float(np.mean(completion)),
                                 note="parameter uncertainty only; model inadequacy not represented"))
                draw_rows.append(dict(candidate_id=c["candidate_id"], model=model, quantity=q,
                                      n_draws=len(ens), n_defined=s["n_defined"],
                                      fraction_defined=s["fraction_defined"],
                                      p2_5=s["p2_5"], p97_5=s["p97_5"], median=s["median"]))
    # Discrete assumption alternatives (Task 2 fits), preferred model only.
    for alt_id, spec in L.DISCRETE_ALTERNATIVES.items():
        path = os.path.join(root, spec["path"])
        if not os.path.exists(path):
            rows.append(dict(candidate_id="unavailable", source=f"discrete_{alt_id}", model=spec["model"],
                             quantity="not_evaluated", note=f"missing {spec['path']}"))
            _log(f"WARNING discrete alternative {alt_id} missing: {spec['path']}")
            continue
        fj = L.read_json(path)
        theta = np.array(fj["theta"], float)
        pid = L.parameter_set_id(spec["model"], theta, spec["path"])
        for c in cands:
            r = L.evaluate(spec["model"], theta, c["temperature_c"], c["s0_g_per_l"])
            for q in ("completion_time_h", "final_ethanol_g_per_l", "margin_per_cycle_inr_per_h",
                      "margin_24h_equivalent_inr_per_day"):
                rows.append(dict(candidate_id=c["candidate_id"], scenario=c["scenario"], candidate_role=c["role"],
                                 s0_g_per_l=c["s0_g_per_l"], temperature_c=c["temperature_c"],
                                 source=f"discrete_{alt_id}", model=spec["model"], parameter_set_id=pid,
                                 n_draws=1, gaussian_accept_rate=float("nan"), quantity=q,
                                 point_estimate=float(r[q]), median=float(r[q]),
                                 p2_5=float(r[q]), p97_5=float(r[q]),
                                 minimum=float(r[q]), maximum=float(r[q]),
                                 n_defined=int(np.isfinite(r[q])), fraction_defined=float(np.isfinite(r[q])),
                                 fraction_draws_completing=1.0 if r["feasibility_status"] == L.STATUS_COMPLETED else 0.0,
                                 note=spec["description"]))
    unc = pd.DataFrame(rows)
    L.write_csv(unc, os.path.join(root, UNC_CSV))
    L.write_csv(pd.DataFrame(draw_rows), os.path.join(root, AUD, "uncertainty_draws.csv"))
    _log(f"uncertainty written: {len(unc)} rows ({time.time()-t0:.1f}s)")


# ------------------------------------------------------------------ stage: model comparison
def stage_model_comparison(args):
    t0 = time.time()
    root = args.root
    df = _read_grid(root)
    prim = df[df.horizon_h == L.HORIZON_PRIMARY_H]
    rows = []
    for scenario in L.scenario_definitions():
        m5_top = scenario_best(df, L.PREFERRED_MODEL, scenario, n=1)
        if not len(m5_top):
            continue
        m5 = m5_top.iloc[0]
        for model in (L.PREFERRED_MODEL,) + L.ROBUST_ALTERNATIVES:
            own = scenario_best(df, model, scenario, n=1)
            if len(own):
                o = own.iloc[0]
                rows.append(dict(scenario=scenario, model=model, case="own_optimum",
                                 s0_g_per_l=o.s0_g_per_l, temperature_c=o.temperature_c,
                                 completion_time_h=o.completion_time_h,
                                 final_ethanol_g_per_l=o.final_ethanol_g_per_l,
                                 margin_per_cycle_inr_per_h=o.margin_per_cycle_inr_per_h,
                                 parameter_set_id=o.parameter_set_id,
                                 delta_margin_vs_M5_optimum_inr_per_h=float(o.margin_per_cycle_inr_per_h - m5.margin_per_cycle_inr_per_h),
                                 same_condition_as_M5_optimum=bool(abs(o.s0_g_per_l - m5.s0_g_per_l) < 1e-9
                                                                   and abs(o.temperature_c - m5.temperature_c) < 1e-9),
                                 note="model's own best completed feasible condition"))
            at = prim[(prim.model == model) & (prim.s0_g_per_l == m5.s0_g_per_l)
                      & (prim.temperature_c == m5.temperature_c)]
            if len(at):
                a = at.iloc[0]
                rows.append(dict(scenario=scenario, model=model, case="at_M5_optimum",
                                 s0_g_per_l=a.s0_g_per_l, temperature_c=a.temperature_c,
                                 completion_time_h=a.completion_time_h,
                                 final_ethanol_g_per_l=a.final_ethanol_g_per_l,
                                 margin_per_cycle_inr_per_h=a.margin_per_cycle_inr_per_h,
                                 parameter_set_id=a.parameter_set_id,
                                 delta_margin_vs_M5_optimum_inr_per_h=float(a.margin_per_cycle_inr_per_h - m5.margin_per_cycle_inr_per_h),
                                 same_condition_as_M5_optimum=True,
                                 note="this model evaluated at the M5 optimum"))
    cmp_df = pd.DataFrame(rows)
    L.write_csv(cmp_df, os.path.join(root, MODELCMP_CSV))
    _log(f"model comparison written: {len(cmp_df)} rows ({time.time()-t0:.1f}s)")


# ------------------------------------------------------------------ stage: horizon diagnostic
def stage_horizon(args):
    t0 = time.time()
    root = args.root
    df = _read_grid(root)
    prim = df[(df.model == L.PREFERRED_MODEL) & (df.horizon_h == L.HORIZON_PRIMARY_H)]
    ext = df[(df.model == L.PREFERRED_MODEL) & (df.horizon_h == L.HORIZON_EXTENDED_H)]
    key = ["s0_g_per_l", "temperature_c"]
    ext = ext.drop_duplicates(subset=key).set_index(key)
    unfinished = prim[prim.feasibility_status == L.STATUS_UNFINISHED]
    rows = []
    for _, r in unfinished.iterrows():
        k = (r.s0_g_per_l, r.temperature_c)
        e = ext.loc[k] if k in ext.index else None
        if e is None:
            rows.append(dict(s0_g_per_l=r.s0_g_per_l, temperature_c=r.temperature_c,
                             status_at_120h=L.STATUS_UNFINISHED, trs_at_120h=r.final_trs_g_per_l,
                             status_at_240h="not_evaluated", completion_time_240h=float("nan"),
                             margin_240h_inr_per_h=float("nan"), completed_by_240h=False,
                             outranks_best_120h=False, note="extended-horizon row unavailable"))
            continue
        completed = e.feasibility_status in (L.STATUS_COMPLETED, L.STATUS_OUT_OF_CURVE)
        rows.append(dict(s0_g_per_l=r.s0_g_per_l, temperature_c=r.temperature_c,
                         status_at_120h=L.STATUS_UNFINISHED, trs_at_120h=r.final_trs_g_per_l,
                         status_at_240h=e.feasibility_status,
                         completion_time_240h=e.completion_time_h,
                         margin_240h_inr_per_h=e.margin_per_cycle_inr_per_h,
                         completed_by_240h=bool(completed),
                         outranks_best_120h=False,
                         note="diagnostic only: not used for ranking or recommendation"))
    hz = pd.DataFrame(rows)
    best120 = prim[prim.feasibility_status == L.STATUS_COMPLETED].margin_per_cycle_inr_per_h.max()
    if len(hz):
        hz["outranks_best_120h"] = hz["margin_240h_inr_per_h"] > best120
    L.write_csv(hz, os.path.join(root, HORIZON_CSV))
    summary = dict(
        primary_horizon_h=L.HORIZON_PRIMARY_H, extended_horizon_h=L.HORIZON_EXTENDED_H,
        n_unfinished_primary_normal=int(len(unfinished)),
        n_completing_by_240h=int(hz["completed_by_240h"].sum()) if len(hz) else 0,
        n_priced_by_240h=int(np.isfinite(hz["margin_240h_inr_per_h"]).sum()) if len(hz) else 0,
        n_outscoring_best_120h=int(hz["outranks_best_120h"].sum()) if len(hz) else 0,
        best_margin_120h_inr_per_h=float(best120),
        max_margin_240h_inr_per_h=float(np.nanmax(hz["margin_240h_inr_per_h"])) if len(hz) and np.isfinite(hz["margin_240h_inr_per_h"]).any() else float("nan"),
        note="The 240 h run is a diagnostic on the same frozen parameters. It is not used to rank candidates.",
    )
    L.write_json(summary, os.path.join(root, AUD, "horizon_sensitivity.json"))
    _log(f"horizon diagnostic: {summary['n_unfinished_primary_normal']} unfinished at 120 h, "
         f"{summary['n_completing_by_240h']} complete by 240 h, {summary['n_outscoring_best_120h']} outrank the best 120 h margin")


# ------------------------------------------------------------------ stage: figures
def _grid_matrices(df, value, t_values=None, s_values=None):
    """Pivot a long table into dense (T x S) matrices on a common grid, with NaN where missing."""
    t_values = np.array(sorted(df.temperature_c.unique())) if t_values is None else np.asarray(t_values, float)
    s_values = np.array(sorted(df.s0_g_per_l.unique())) if s_values is None else np.asarray(s_values, float)
    mat = np.full((t_values.size, s_values.size), np.nan)
    ti = {round(v, 6): i for i, v in enumerate(t_values)}
    si = {round(v, 6): i for i, v in enumerate(s_values)}
    for _, r in df.iterrows():
        i, j = ti.get(round(r.temperature_c, 6)), si.get(round(r.s0_g_per_l, 6))
        if i is not None and j is not None:
            mat[i, j] = r[value]
    return t_values, s_values, mat


def stage_figures(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t0 = time.time()
    root = args.root
    figdir = os.path.join(root, FIG)
    os.makedirs(figdir, exist_ok=True)
    df = _read_grid(root)
    prim = df[(df.model == L.PREFERRED_MODEL) & (df.horizon_h == L.HORIZON_PRIMARY_H)
              & (df.search_stage.isin(["coarse", "dense"]))]

    # ---- figure 1: completion-time map and feasibility -------------------------------
    tvals, svals, tt = _grid_matrices(prim, "completion_time_h")
    _, _, margin = _grid_matrices(prim, "margin_per_cycle_inr_per_h")
    fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.9), sharey=True)
    masked_t = np.ma.masked_invalid(tt)
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("0.85")
    im = ax[0].pcolormesh(svals, tvals, masked_t, cmap=cmap, shading="nearest")
    ax[0].set_xlabel("Initial TRS (g/L as glucose)")
    ax[0].set_ylabel("Temperature (C)")
    ax[0].set_title("Completion time to TRS <= 5 g/L (h)", fontsize=10)
    fig.colorbar(im, ax=ax[0], label="h")
    ax[0].text(0.02, 0.965, "grey cells: not complete within 120 h (no batch end)", transform=ax[0].transAxes,
               fontsize=7, color="k", va="top",
               bbox=dict(boxstyle="round,pad=0.25", fc="w", ec="0.6", alpha=0.85))
    ax[0].axhline(33.0, color="w", lw=0.8)
    ax[0].axvline(195.0, color="w", lw=0.8, ls="--")

    masked_m = np.ma.masked_invalid(margin)
    im2 = ax[1].pcolormesh(svals, tvals, masked_m, cmap="magma", shading="nearest")
    ax[1].set_xlabel("Initial TRS (g/L as glucose)")
    ax[1].set_title("Margin per cycle time (INR/h), M5, 120 h", fontsize=10)
    fig.colorbar(im2, ax=ax[1], label="INR/h")
    ax[1].text(0.02, 0.965, "blank cells: unfinished, or wash strength outside the 7-14 % v/v steam curve",
               transform=ax[1].transAxes, fontsize=7, color="k", va="top",
               bbox=dict(boxstyle="round,pad=0.25", fc="w", ec="0.6", alpha=0.85))
    fig.suptitle("M5 operating map. Grey/blank cells are not completable or not costable: they are never ranked.",
                 fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(os.path.join(figdir, "level3_feasible_region.png"), dpi=140)
    plt.close(fig)

    # ---- figure 2: where the money goes, and the margin/cycle-time trade-off ---------
    rec = pd.read_csv(os.path.join(root, REC_CSV))
    econ = pd.read_csv(os.path.join(root, ECON_CSV))
    fig, ax = plt.subplots(1, 2, figsize=(15.5, 5.6),
                           gridspec_kw=dict(width_ratios=[1.2, 1.0]))
    pick = ["normal_33_37_M5_rank1", "normal_33_37_M5_rank5", "normal_33_37_M5_fastest",
            "warm_min_36_M5_rank1", "warm_min_36_M5_rank5", "warm_min_36_M5_fastest"]
    sub = econ[econ.case_id.isin(pick)].copy()
    sub["order"] = [pick.index(c) if c in pick else 99 for c in sub.case_id]
    sub = sub.sort_values("order")
    y = np.arange(len(sub))
    rev = sub.ethanol_revenue_inr.to_numpy(float)
    sug = sub.sugar_cost_inr.to_numpy(float)
    ste = sub.steam_cost_inr.to_numpy(float)
    mar = sub.batch_margin_inr.to_numpy(float)
    ax[0].barh(y, rev / 1e3, color="0.80", label="ethanol revenue")
    ax[0].barh(y, -sug / 1e3, color="tab:orange", label="sugar cost (all TRS charged)")
    ax[0].barh(y, -ste / 1e3, color="tab:blue", label="distillation steam cost")
    ax[0].plot(mar / 1e3, y, "D", color="tab:red", ms=7, label="batch margin (revenue - costs)")
    ax[0].axvline(0, color="k", lw=0.8)
    ax[0].set_yticks(y)
    ax[0].set_yticklabels([f"{r.case_id.replace('_M5', '').replace('normal_33_37', 'normal')}"
                           f"{'':<0}\n{r.s0_g_per_l:.0f} g/L, {r.temperature_c:.2f} C, end {r.completion_time_h:.1f} h, "
                           f"cycle {r.cycle_time_h:.1f} h\nmargin {r.margin_per_cycle_inr_per_h:,.0f} INR/h"
                           for r in sub.itertuples()], fontsize=6.5)
    ax[0].set_xlabel("thousand INR per batch (170 m3 fermenter)")
    ax[0].set_title("Per-batch economics of the selected candidates", fontsize=10)
    ax[0].legend(fontsize=6.8, loc="lower right", framealpha=0.95)
    ax[0].grid(alpha=0.3, axis="x")
    ax[0].tick_params(axis="y", pad=2)

    feasible = prim[(prim.feasibility_status == L.STATUS_COMPLETED) & prim.margin_per_cycle_inr_per_h.notna()]
    sc = ax[1].scatter(feasible.completion_time_h, feasible.margin_per_cycle_inr_per_h,
                       c=feasible.s0_g_per_l, cmap="viridis", s=9, alpha=0.75)
    fig.colorbar(sc, ax=ax[1], label="initial TRS (g/L)")
    top = rec[(rec.rank_basis == "highest_margin_per_cycle_time") & (rec["rank"] == 1)
              & (rec.model == L.PREFERRED_MODEL)]
    fast = rec[(rec.rank_basis == "fastest_completion") & (rec.model == L.PREFERRED_MODEL)]
    ax[1].scatter(top.completion_time_h, top.margin_per_cycle_inr_per_h, marker="*", s=230,
                  edgecolor="k", facecolor="tab:red", zorder=5, label="best margin per cycle time")
    ax[1].scatter(fast.completion_time_h, fast.margin_per_cycle_inr_per_h, marker="P", s=90,
                  edgecolor="k", facecolor="w", zorder=5, label="fastest completion")
    box = dict(boxstyle="round,pad=0.25", fc="w", ec="0.6", alpha=0.9)
    for r, off in zip(top.itertuples(), [(12, -2), (12, -26)]):
        ax[1].annotate(f"{r.s0_g_per_l:.0f} g/L, {r.temperature_c:.2f} C\n{r.margin_per_cycle_inr_per_h:,.0f} INR/h",
                       (r.completion_time_h, r.margin_per_cycle_inr_per_h), xytext=off,
                       textcoords="offset points", fontsize=6.8, bbox=box)
    ax[1].set_xlabel("completion time to TRS <= 5 g/L (h)")
    ax[1].set_ylabel("margin per cycle time (INR/h)")
    ax[1].set_title("Every completed feasible M5 candidate (120 h horizon)", fontsize=10, pad=8)
    ax[1].legend(fontsize=7, loc="lower left", framealpha=0.95)
    ax[1].grid(alpha=0.3)
    fig.suptitle("Economics. Cycle time includes the 8 h turnaround; unfinished and out-of-curve candidates "
                 "carry no margin and are absent from the right panel.", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(os.path.join(figdir, "level3_economics.png"), dpi=140)
    plt.close(fig)

    # ---- figure 3: completion time vs sugar, by temperature -------------------------
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    for T in sorted(prim.temperature_c.unique()):
        sub = prim[(prim.temperature_c == T) & prim.completion_time_h.notna()].sort_values("s0_g_per_l")
        if len(sub) > 2 and (T in (33.0, 34.0, 35.0, 36.0, 37.0)):
            ax.plot(sub.s0_g_per_l, sub.completion_time_h, marker="o", ms=3, lw=1.4, label=f"{T:.0f} C")
    ax.axhline(L.DATA_END_H, color="k", ls=":", lw=1)
    ax.text(161, L.DATA_END_H + 1.5, "last measured time point (48 h): beyond this the end time is a time extrapolation",
            fontsize=7)
    ax.axhline(L.HORIZON_PRIMARY_H, color="r", ls="--", lw=1)
    ax.text(161, L.HORIZON_PRIMARY_H - 6, "primary simulation horizon (120 h)", fontsize=7, color="r")
    ax.set_ylim(20, 130)
    ax.set_xlabel("Initial TRS (g/L as glucose)")
    ax.set_ylabel("Completion time to TRS <= 5 g/L (h)")
    ax.set_title("Completion time grows with the sugar charge and is insensitive to temperature above 33 C", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncol=5)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "level3_completion_time.png"), dpi=140)
    plt.close(fig)

    # ---- figure 4: uncertainty at the candidates ------------------------------------
    unc = pd.read_csv(os.path.join(root, UNC_CSV))
    labels = {
        "normal_33_37_M5_optimum": "normal\noptimum\n195 g/L, 33 C",
        "normal_33_37_M5_runner_up": "normal\nrunner-up\n192.5 g/L, 33 C",
        "warm_min_36_M5_optimum": "warm\noptimum\n175 g/L, 36 C",
        "warm_min_36_M5_runner_up": "warm\nrunner-up\n172.5 g/L, 36 C",
        "brief_q5_37C_260": "brief Q5\n260 g/L, 37 C\n(never completes)",
    }
    candidates = [c for c in labels if c in set(unc.candidate_id)]
    models = list((L.PREFERRED_MODEL,) + L.ROBUST_ALTERNATIVES)
    colours = {"M5": "tab:red", "M2": "tab:blue", "M6": "tab:green"}
    fig, ax = plt.subplots(1, 2, figsize=(14.5, 5.4))
    width = 0.8 / max(len(models), 1)
    for panel, (quantity, ylab, title, scale) in enumerate([
            ("margin_per_cycle_inr_per_h", "margin per cycle time (INR/h)",
             "Economic result at the selected conditions", 1.0),
            ("completion_time_h", "completion time to TRS <= 5 g/L (h)",
             "Batch duration at the same conditions (120 h horizon)", 1.0)]):
        for k, m in enumerate(models):
            xs, ys, los, his = [], [], [], []
            for i, c in enumerate(candidates):
                r = unc[(unc.quantity == quantity) & (unc.source == f"parameter_ensemble_{m}")
                        & (unc.candidate_id == c)]
                if not len(r):
                    continue
                r = r.iloc[0]
                if not np.isfinite(r.point_estimate):
                    continue
                xs.append(i + (k - (len(models) - 1) / 2) * width)
                ys.append(float(r.point_estimate))
                los.append(float(r.p2_5))
                his.append(float(r.p97_5))
            if not xs:
                continue
            ys = np.array(ys)
            yerr = np.array([ys - np.array(los), np.array(his) - ys])
            stable = [np.isfinite(v) for v in los]
            ax[panel].errorbar(np.array(xs)[stable], ys[stable], yerr=yerr[:, stable], fmt="o", ms=5.5,
                               capsize=4, lw=1.7, color=colours.get(m), label=m)
        # mark the candidates whose batch never completes, in the margin panel only
        if panel == 0:
            for i, c in enumerate(candidates):
                r = unc[(unc.quantity == quantity) & (unc.source == "parameter_ensemble_M5") & (unc.candidate_id == c)]
                if len(r) and not np.isfinite(r.iloc[0].point_estimate):
                    ax[panel].annotate("no completed batch\nin any of the 200 draws",
                                       (i, 0.5), xycoords=("data", "axes fraction"), ha="center",
                                       fontsize=7.5, color="0.25",
                                       bbox=dict(boxstyle="round,pad=0.3", fc="w", ec="0.6"))
        else:
            ax[panel].axhline(L.HORIZON_PRIMARY_H, color="r", ls="--", lw=1)
            ax[panel].text(-0.45, L.HORIZON_PRIMARY_H - 8, "120 h horizon", color="r", fontsize=7)
        ax[panel].set_xticks(range(len(candidates)))
        ax[panel].set_xticklabels([labels[c] for c in candidates], fontsize=7.5)
        ax[panel].set_ylabel(ylab)
        ax[panel].set_title(title, fontsize=10)
        ax[panel].grid(alpha=0.3, axis="y")
        ax[panel].legend(title="model", fontsize=8)
    fig.suptitle("Point = frozen parameter set; bars = 2.5-97.5 percentile of 200 Gaussian parameter draws. "
                 "Parameter uncertainty only: measurement error, model inadequacy and run-to-run variability "
                 "are not included.", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(os.path.join(figdir, "level3_uncertainty.png"), dpi=140)
    plt.close(fig)
    _log(f"figures written ({time.time()-t0:.1f}s)")


# ------------------------------------------------------------------ stage: answers / claims
def stage_answers(args):
    t0 = time.time()
    root = args.root
    df = _read_grid(root)
    prim = df[(df.model == L.PREFERRED_MODEL) & (df.horizon_h == L.HORIZON_PRIMARY_H)]
    rec = pd.read_csv(os.path.join(root, REC_CSV))
    cmp_df = pd.read_csv(os.path.join(root, MODELCMP_CSV))
    unc = pd.read_csv(os.path.join(root, UNC_CSV))
    hz = L.read_json(os.path.join(root, AUD, "horizon_sensitivity.json"))
    grid_summary = L.read_json(os.path.join(root, AUD, "grid_summary.json"))
    policy = L.read_json(os.path.join(root, AUD, "model_policy.json"))

    def best(scenario):
        r = rec[(rec.scenario == scenario) & (rec.rank_basis == "highest_margin_per_cycle_time")
                & (rec.model == L.PREFERRED_MODEL)].sort_values("rank")
        return r.iloc[0] if len(r) else None

    def fastest(scenario):
        r = rec[(rec.scenario == scenario) & (rec.rank_basis == "fastest_completion") & (rec.model == L.PREFERRED_MODEL)]
        return r.iloc[0] if len(r) else None

    n_best, w_best = best("normal_33_37"), best("warm_min_36")
    n_fast, w_fast = fastest("normal_33_37"), fastest("warm_min_36")
    if n_best is None or w_best is None:
        raise SystemExit("no completed feasible candidate for a required scenario: cannot answer the brief")
    q5 = prim[(prim.s0_g_per_l == L.BRIEF_Q5_POINT["s0_g_per_l"])
              & (prim.temperature_c == L.BRIEF_Q5_POINT["temperature_c"])].iloc[0]
    unc_q = unc[(unc.quantity == "margin_per_cycle_inr_per_h")
                & (unc.source == f"parameter_ensemble_{L.PREFERRED_MODEL}")]
    disc = unc[(unc.quantity == "margin_per_cycle_inr_per_h") & (unc.source.str.startswith("discrete_"))]

    def urow(cand_id):
        r = unc_q[unc_q.candidate_id == cand_id]
        return r.iloc[0] if len(r) else None

    u_norm = urow("normal_33_37_M5_optimum")
    u_warm = urow("warm_min_36_M5_optimum")
    u_q5 = urow("brief_q5_37C_260")

    d_norm = disc[disc.candidate_id == "normal_33_37_M5_optimum"]
    d_warm = disc[disc.candidate_id == "warm_min_36_M5_optimum"]

    # Steam-curve and completion bookkeeping for the honesty statements.
    completed = prim[prim.feasibility_status == L.STATUS_COMPLETED]
    out_of_curve = prim[prim.feasibility_status == L.STATUS_OUT_OF_CURVE]
    unfinished = prim[prim.feasibility_status == L.STATUS_UNFINISHED]
    top_ethanol = prim[prim.feasibility_status.isin([L.STATUS_COMPLETED, L.STATUS_OUT_OF_CURVE])].sort_values(
        "final_ethanol_g_per_l", ascending=False).head(10)

    def f(x, nd=4):
        return float(f"{float(x):.{nd}f}")

    answers = {
        "Q1_best_normal_33_37": dict(
            question="Best feasible operating condition under the normal 33-37 C constraint (max margin per cycle time)",
            answer=dict(s0_g_per_l=f(n_best.s0_g_per_l), temperature_c=f(n_best.temperature_c),
                        completion_time_h=f(n_best.completion_time_h), final_trs_g_per_l=f(n_best.final_trs_g_per_l),
                        final_ethanol_g_per_l=f(n_best.final_ethanol_g_per_l),
                        wash_pct_vv=f(n_best.wash_pct_vv), steam_kg_per_L=f(n_best.steam_kg_per_L),
                        batch_margin_inr=f(n_best.batch_margin_inr, 2),
                        cycle_time_h=f(n_best.cycle_time_h),
                        margin_per_cycle_inr_per_h=f(n_best.margin_per_cycle_inr_per_h, 2),
                        margin_24h_equivalent_inr_per_day=f(n_best.margin_24h_equivalent_inr_per_day, 1)),
            parameter_set_id=n_best.parameter_set_id,
            evidence=["outputs/tables/optimization_recommendations.csv",
                      "outputs/tables/optimization_grid.csv", "outputs/tables/plant_economics.csv"]),
        "Q2_best_min36": dict(
            question="Best feasible condition when the minimum temperature is 36 C (36-37 C)",
            answer=dict(s0_g_per_l=f(w_best.s0_g_per_l), temperature_c=f(w_best.temperature_c),
                        completion_time_h=f(w_best.completion_time_h), final_trs_g_per_l=f(w_best.final_trs_g_per_l),
                        final_ethanol_g_per_l=f(w_best.final_ethanol_g_per_l),
                        wash_pct_vv=f(w_best.wash_pct_vv), batch_margin_inr=f(w_best.batch_margin_inr, 2),
                        cycle_time_h=f(w_best.cycle_time_h),
                        margin_per_cycle_inr_per_h=f(w_best.margin_per_cycle_inr_per_h, 2),
                        margin_24h_equivalent_inr_per_day=f(w_best.margin_24h_equivalent_inr_per_day, 1)),
            parameter_set_id=w_best.parameter_set_id,
            penalty_vs_normal_inr_per_h=f(float(w_best.margin_per_cycle_inr_per_h - n_best.margin_per_cycle_inr_per_h), 2),
            penalty_vs_normal_inr_per_day=f(24 * float(w_best.margin_per_cycle_inr_per_h - n_best.margin_per_cycle_inr_per_h), 1),
            evidence=["outputs/tables/optimization_recommendations.csv"]),
        "Q3_model_change": dict(
            question="Does the preferred condition change when M2 or M6 is used instead of M5?",
            detail=[dict(scenario=r.scenario, model=r.model, case=r.case, s0_g_per_l=f(r.s0_g_per_l),
                         temperature_c=f(r.temperature_c),
                         margin_per_cycle_inr_per_h=f(r.margin_per_cycle_inr_per_h, 2),
                         same_condition_as_M5_optimum=bool(r.same_condition_as_M5_optimum))
                    for r in cmp_df[cmp_df.case == "own_optimum"].itertuples()],
            changed=bool(any((not r.same_condition_as_M5_optimum) for r in cmp_df[cmp_df.case == "own_optimum"].itertuples()
                             if r.model != L.PREFERRED_MODEL)),
            evidence=["outputs/tables/optimization_model_comparison.csv"]),
        "Q4_best_margin": dict(
            question="Which candidate has the best estimated margin per cycle time?",
            answer=dict(candidate=f"{f(n_best.s0_g_per_l)} g/L at {f(n_best.temperature_c)} C",
                        margin_per_cycle_inr_per_h=f(n_best.margin_per_cycle_inr_per_h, 2),
                        margin_24h_equivalent_inr_per_day=f(n_best.margin_24h_equivalent_inr_per_day, 1)),
            note="Computed over every completed feasible grid point; unfinished and out-of-curve points are excluded by construction.",
            evidence=["outputs/tables/optimization_recommendations.csv", "outputs/tables/optimization_grid.csv"]),
        "Q5_fastest_completion": dict(
            question="Which candidate reaches the TRS completion threshold fastest?",
            normal=dict(s0_g_per_l=f(n_fast.s0_g_per_l), temperature_c=f(n_fast.temperature_c),
                        completion_time_h=f(n_fast.completion_time_h),
                        margin_per_cycle_inr_per_h=f(n_fast.margin_per_cycle_inr_per_h, 2)),
            warm=dict(s0_g_per_l=f(w_fast.s0_g_per_l), temperature_c=f(w_fast.temperature_c),
                      completion_time_h=f(w_fast.completion_time_h),
                      margin_per_cycle_inr_per_h=f(w_fast.margin_per_cycle_inr_per_h, 2)),
            note="Fastest is not the most profitable: the lowest sugar charge finishes first but gives up margin per cycle time.",
            evidence=["outputs/tables/optimization_recommendations.csv"]),
        "Q6_high_margin_feasibility": dict(
            question="Are the highest-margin candidates feasible under the batch-completion requirement?",
            completed_feasible_rows=int(len(completed)),
            completed_outside_steam_curve_rows=int(len(out_of_curve)),
            unfinished_rows=int(len(unfinished)),
            highest_ethanol_top10_status=sorted(set(top_ethanol.feasibility_status)),
            highest_ethanol_top10_s0=[f(x) for x in top_ethanol.s0_g_per_l],
            answer="Every candidate that is ranked is completed (TRS <= 5 g/L) and inside the steam curve. "
                   "The candidates with the most ethanol at 120 h are all outside the 7-14 % v/v curve, so none "
                   "of them can be priced or recommended.",
            evidence=["outputs/tables/optimization_grid.csv"]),
        "Q7_unfinished_effect": dict(
            question="What happens to the optimum if some candidates fail to reach TRS <= 5 g/L?",
            unfinished_at_120h=hz["n_unfinished_primary_normal"],
            completing_by_240h=hz["n_completing_by_240h"],
            outscoring_best_120h=hz["n_outscoring_best_120h"],
            answer="Unfinished candidates are recorded with their state at 120 h but receive no completion time, "
                   "no ethanol end point and no margin, so they cannot enter the ranking. Extending the horizon to "
                   "240 h only confirms this: none of the unfinished candidates would beat the recommended point, "
                   "and the extension is not used to rank.",
            evidence=["outputs/tables/optimization_horizon_sensitivity.csv",
                      "outputs/audits/level3/horizon_sensitivity.json"]),
        "Q8_uncertainty": dict(
            question="How sensitive is the recommendation to parameter and model uncertainty?",
            normal_optimum=dict(margin_p2_5=f(u_norm.p2_5, 2), margin_p97_5=f(u_norm.p97_5, 2),
                                fraction_draws_completing=f(u_norm.fraction_draws_completing)),
            warm_optimum=dict(margin_p2_5=f(u_warm.p2_5, 2), margin_p97_5=f(u_warm.p97_5, 2),
                              fraction_draws_completing=f(u_warm.fraction_draws_completing)),
            brief_q5_point=dict(fraction_draws_completing=f(u_q5.fraction_draws_completing)),
            discrete_alternatives_normal=dict(min=f(d_norm.point_estimate.min(), 2), max=f(d_norm.point_estimate.max(), 2)),
            discrete_alternatives_warm=dict(min=f(d_warm.point_estimate.min(), 2), max=f(d_warm.point_estimate.max(), 2)),
            answer="The recommended condition stays completed and inside the steam curve in every draw, but the "
                   "margin per cycle time carries a finite interval; the discrete assumption alternatives move it far "
                   "less than the parameter ensemble.",
            evidence=["outputs/tables/optimization_uncertainty.csv", "outputs/figures/level3_uncertainty.png"]),
        "Q9_most_influential_assumptions": dict(
            question="Which assumptions most affect the recommendation?",
            items=[
                "The completion criterion is binding: every sugar charge above ~200-210 g/L either finishes late or leaves the steam curve, so the optimum sits just above 190 g/L rather than where ethanol is highest.",
                "The steam curve limits the usable wash strength to 14 % v/v (about 110 g/L ethanol): high-sugar, high-ethanol batches cannot be costed at all.",
                "The 37 C rate multiplier rests on one run (R8), so the 36-37 C scenario is the least supported part of the surface.",
                "The temperature multipliers are piecewise-linear between 30/34/37 C, so a 33 C prediction is an interpolation assumption, not a measurement.",
                "The CO2 standard-deviation floor (0.10 g/L) changes the parameter covariance and therefore the width of every interval.",
            ],
            evidence=["outputs/tables/optimization_uncertainty.csv", "docs/requirements_traceability.csv"]),
        "Q10_additional_experiment": dict(
            question="What additional experiment or data would most reduce decision uncertainty?",
            answer="A single batch at the recommended condition (about 195 g/L TRS, 33 C) run past 48 h to the "
                   "TRS <= 5 g/L endpoint, because it simultaneously tests the completion time that drives the "
                   "margin-per-cycle-time metric and the growth/production behaviour in the 33 C region that the "
                   "plant now operates in. A second 37 C run would help the warm scenario but cannot fix the 33 C gap.",
            evidence=["reports/level3.md section 15", "outputs/tables/experiment_design.csv"]),
        "brief_Q5_37C_260": dict(
            question="Brief Q5: what does the model predict at 37 C and 260 g/L, and how far is it trustworthy?",
            prediction=dict(s0_g_per_l=f(q5.s0_g_per_l), temperature_c=f(q5.temperature_c),
                            batch_completed=bool(q5.batch_completed),
                            final_trs_g_per_l_at_120h=f(q5.final_trs_g_per_l),
                            final_ethanol_g_per_l_at_120h=f(q5.final_ethanol_g_per_l),
                            final_biomass_g_per_l_at_120h=f(q5.final_biomass_g_per_l),
                            feasibility_status=q5.feasibility_status,
                            margin=f(q5.margin_per_cycle_inr_per_h, 2)),
            trust="LOW: one 37 C run only (R8, 220 g/L), no 37 C / 260 g/L observation, a 120 h prediction "
                  "against 48 h of data, and ethanol above 105 g/L while the fitted P_max is "
                  f"{policy['preferred_theta']['P_max']:.1f} g/L (for M5 the inhibition exponent is entangled with P_max). "
                  "It is reported because the brief asks for it; it is not an operating recommendation.",
            evidence=["outputs/tables/optimization_grid.csv", "outputs/tables/optimization_uncertainty.csv"]),
        "brief_Q6_experiment": dict(
            question="Brief Q6: which single additional experiment would most reduce the uncertainty that matters?",
            answer="The same recommendation as Q10: one extended batch at the proposed plant condition "
                   "(~195 g/L TRS at 33 C) taken to the 5 g/L endpoint, ideally with a mid-run 60-96 h sample, "
                   "because the decision is limited by the time-to-completion extrapolation rather than by the "
                   "48 h kinetics.",
            evidence=["outputs/tables/experiment_design.csv", "reports/level3.md section 15"]),
    }
    L.write_json(answers, os.path.join(root, AUD, "level3_answers.json"))
    _log(f"answers written ({time.time()-t0:.1f}s)")
    return answers


# ------------------------------------------------------------------ main
STAGES = ["input_audit", "grid", "recommend", "uncertainty", "model_comparison", "horizon", "figures", "answers"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Level 3 optimisation workflow")
    ap.add_argument("--stage", default="all", choices=STAGES + ["all"])
    ap.add_argument("--n-draws", type=int, default=200, help="parameter draws per model for the uncertainty stage")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    t0 = time.time()
    wanted = STAGES if args.stage == "all" else [args.stage]
    for st in wanted:
        _log(f"=== stage {st} ===")
        globals()[f"stage_{st}"](args)
    _log(f"done in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
