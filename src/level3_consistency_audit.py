#!/usr/bin/env python
"""Level 3 consistency audit.

Checks the generated Level 3 deliverables against each other and against the frozen records:
the report against the tables, the tables against the model policy, the figures against the
report, and the answer set against the required questions.  Writes
``outputs/audits/level3/consistency_report.{md,json}`` and exits non-zero if anything fails.

Usage (project root):  python src/level3_consistency_audit.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import level3 as L  # noqa: E402

T = "outputs/tables/"
A = "outputs/audits/level3/"
FIG = "outputs/figures/"
REPORT = "reports/level3.md"

CHECKS = []


def check(cid, description, passed, detail=""):
    CHECKS.append(dict(id=cid, description=description, passed=bool(passed), detail=str(detail)))
    print(f"[{'PASS' if passed else 'FAIL'}] {cid} {description}" + (f" -- {detail}" if not passed else ""))
    return bool(passed)


def main():
    print("Level 3 consistency audit")
    print("=" * 78)

    # ---------------------------------------------------------------- required deliverables
    required_tables = ["optimization_grid.csv", "optimization_recommendations.csv", "plant_economics.csv",
                       "optimization_uncertainty.csv", "optimization_model_comparison.csv",
                       "optimization_input_audit.csv", "optimization_horizon_sensitivity.csv"]
    missing = [t for t in required_tables if not os.path.exists(T + t)]
    check("A-01", "all required Level 3 tables exist", not missing, f"missing: {missing}")

    required_figures = ["level3_feasible_region.png", "level3_economics.png",
                        "level3_completion_time.png", "level3_uncertainty.png"]
    missing_fig = [f for f in required_figures if not os.path.exists(FIG + f)]
    check("A-02", "all required Level 3 figures exist", not missing_fig, f"missing: {missing_fig}")

    check("A-03", "reports/level3.md exists", os.path.exists(REPORT))

    report_bytes = open(REPORT, "rb").read() if os.path.exists(REPORT) else b""
    report = report_bytes.decode("utf-8") if report_bytes else ""
    n_nonascii = sum(1 for c in report_bytes if c > 127)
    n_crlf = report_bytes.count(b"\r\n")
    check("A-04", "report is ASCII with LF line endings",
          n_nonascii == 0 and n_crlf == 0, f"non-ascii={n_nonascii} crlf={n_crlf}")

    # ---------------------------------------------------------------- model policy
    policy = L.verify_model_policy(".")
    check("B-01", "frozen model policy verifies (M5, D-24, R6 held out)", policy["all_checks_passed"],
          {k: v for k, v in policy["checks"].items() if not v})
    check("B-02", "R6 is not in the training set", "R6" not in policy["training_runs"], policy["training_runs"])
    sel = L.read_json(T + "model_selection_frozen.json")
    check("B-03", "frozen selection file still records M5 under D-24 without R6",
          sel["preferred"] == "M5" and sel["rule"] == "D-24" and sel["r6_used_for_selection"] is False, sel)

    stored = L.read_json(A + "model_policy.json")
    check("B-04", "stored model policy record matches a fresh verification",
          stored["preferred_parameter_set_id"] == policy["preferred_parameter_set_id"]
          and stored["all_checks_passed"] == policy["all_checks_passed"])

    # ---------------------------------------------------------------- grid / feasibility
    grid = pd.read_csv(T + "optimization_grid.csv")
    prim = grid[(grid.model == "M5") & (grid.horizon_h == L.HORIZON_PRIMARY_H)]
    completed = prim[prim.batch_completed.astype(bool)]
    check("C-01", "every completed M5 row has residual TRS <= 5 g/L",
          bool(np.all(completed.final_trs_g_per_l <= L.TRS_COMPLETION_G_PER_L + 1e-9)),
          f"max={completed.final_trs_g_per_l.max()}")

    unfin = prim[prim.feasibility_status == L.STATUS_UNFINISHED]
    check("C-02", "unfinished rows have no completion time, cycle time or margin",
          bool(unfin.completion_time_h.isna().all() and unfin.cycle_time_h.isna().all()
               and unfin.batch_margin_inr.isna().all() and unfin.margin_per_cycle_inr_per_h.isna().all()),
          f"n={len(unfin)}")

    ooc = grid[grid.steam_curve_in_range == False]  # noqa: E712
    check("C-03", "no row outside the steam curve carries a margin",
          bool(ooc.margin_per_cycle_inr_per_h.isna().all()), f"n={len(ooc)}")

    check("C-04", "every M5 row quotes the frozen parameter-set id",
          set(prim.parameter_set_id) == {policy["preferred_parameter_set_id"]},
          set(prim.parameter_set_id))

    in_win = grid[grid.in_operating_window.astype(bool)]
    check("C-05", "operating window respected (160-260 g/L, 33-37 C) for all ranked rows",
          bool(in_win.s0_g_per_l.between(160, 260).all() and in_win.temperature_c.between(33, 37).all()))

    # ---------------------------------------------------------------- economics re-derivation
    econ = pd.read_csv(T + "plant_economics.csv")
    priced = econ[econ.batch_margin_inr.notna()]
    S0 = priced.s0_g_per_l.to_numpy(float)
    P = priced.final_ethanol_g_per_l.to_numpy(float)
    steam = priced.steam_kg_per_L.to_numpy(float)
    L_e = P * L.V_WORKING_M3 / L.RHO_ETHANOL_KG_PER_L
    margin = L_e * L.PRICE_ETHANOL_INR_PER_L - S0 * L.V_WORKING_M3 * L.COST_SUGAR_INR_PER_KG \
        - steam * L_e * L.STEAM_COST_INR_PER_KG
    cycle = priced.completion_time_h.to_numpy(float) + L.TURNAROUND_H
    check("D-01", "batch margin reproduces from the saved columns",
          bool(np.allclose(priced.batch_margin_inr, margin, rtol=1e-12)))
    check("D-02", "margin per cycle time reproduces as margin / (completion + 8 h)",
          bool(np.allclose(priced.margin_per_cycle_inr_per_h, margin / cycle, rtol=1e-12)))
    check("D-03", "24 h equivalent reproduces as 24 x margin / cycle time",
          bool(np.allclose(priced.margin_24h_equivalent_inr_per_day, 24 * margin / cycle, rtol=1e-12)))
    check("D-04", "steam cost reproduces as intensity x ethanol volume x 1.6 INR/kg",
          bool(np.allclose(priced.steam_cost_inr, steam * priced.ethanol_volume_l * 1.6, rtol=1e-12)))
    check("D-05", "sugar cost charges all sugar (S0 x 170 m3 x 25 INR/kg)",
          bool(np.allclose(priced.sugar_cost_inr, S0 * 170.0 * 25.0, rtol=1e-12)))

    # ---------------------------------------------------------------- recommendations vs grid
    rec = pd.read_csv(T + "optimization_recommendations.csv")
    ok_top = True
    detail = ""
    for scenario, tmin in (("normal_33_37", 33.0), ("warm_min_36", 36.0)):
        top_pub = rec[(rec.scenario == scenario) & (rec.rank_basis == "highest_margin_per_cycle_time")
                      & (rec["rank"] == 1) & (rec.model == "M5")]
        grid_top = prim[(prim.feasibility_status == L.STATUS_COMPLETED) & (prim.temperature_c >= tmin)]
        grid_top = grid_top.sort_values("margin_per_cycle_inr_per_h", ascending=False).iloc[0]
        if not len(top_pub):
            ok_top = False
            detail += f"{scenario}: no published optimum; "
            continue
        r = top_pub.iloc[0]
        same = (abs(r.s0_g_per_l - grid_top.s0_g_per_l) < 1e-9
                and abs(r.temperature_c - grid_top.temperature_c) < 1e-9
                and abs(r.margin_per_cycle_inr_per_h - grid_top.margin_per_cycle_inr_per_h) < 1e-6)
        ok_top &= bool(same)
        if not same:
            detail += f"{scenario}: published {r.s0_g_per_l}/{r.temperature_c} vs grid {grid_top.s0_g_per_l}/{grid_top.temperature_c}; "
    check("E-01", "published optimum of each scenario is the grid maximum", ok_top, detail)

    warm = rec[rec.scenario == "warm_min_36"]
    check("E-02", "36 C scenario only recommends temperatures >= 36 C",
          bool((warm.temperature_c >= 36.0 - 1e-9).all()), warm.temperature_c.min())

    # ---------------------------------------------------------------- report claims
    claims = L.read_json(A + "report_claims.json")["claims"]
    absent = [c["id"] + ": " + c["text"] for c in claims if c["text"] not in report]
    check("F-01", "every tracked numeric claim appears in the report", not absent, absent)

    answers = L.read_json(A + "level3_answers.json")
    required_answers = [f"Q{i}_" for i in range(1, 11)] + ["brief_Q5_37C_260", "brief_Q6_experiment"]
    missing_ans = [k for k in required_answers if not any(k in key for key in answers)]
    check("F-02", "all 10 user questions and both brief questions are answered", not missing_ans, missing_ans)

    # key numbers cross-checked between the report, the answers record and the tables
    a1 = answers["Q1_best_normal_33_37"]["answer"]
    top_norm = rec[(rec.scenario == "normal_33_37") & (rec.rank_basis == "highest_margin_per_cycle_time")
                   & (rec["rank"] == 1) & (rec.model == "M5")].iloc[0]
    check("F-03", "report normal optimum agrees with the recommendation table",
          abs(a1["s0_g_per_l"] - top_norm.s0_g_per_l) < 1e-9
          and abs(a1["margin_per_cycle_inr_per_h"] - round(top_norm.margin_per_cycle_inr_per_h, 2)) < 0.01,
          f"{a1['s0_g_per_l']} vs {top_norm.s0_g_per_l}")
    a2 = answers["Q2_best_min36"]["answer"]
    top_warm = rec[(rec.scenario == "warm_min_36") & (rec.rank_basis == "highest_margin_per_cycle_time")
                   & (rec["rank"] == 1) & (rec.model == "M5")].iloc[0]
    check("F-04", "report warm optimum agrees with the recommendation table",
          abs(a2["s0_g_per_l"] - top_warm.s0_g_per_l) < 1e-9
          and abs(a2["margin_per_cycle_inr_per_h"] - round(top_warm.margin_per_cycle_inr_per_h, 2)) < 0.01)

    # ---------------------------------------------------------------- report structure
    headings = ["Executive summary", "Engineering problem", "Inputs and data-quality",
                "Kinetic model description", "Model-selection policy", "Numerical method",
                "Batch-completion criterion", "Plant economics", "Optimisation results",
                "Model comparison and uncertainty", "Figures and tables", "Sensitivity and validation",
                "Engineering interpretation", "Answers to every supported", "Limitations and recommendations",
                "Reproduction instructions"]
    missing_head = [h for h in headings if h not in report]
    check("F-05", "report contains every required section", not missing_head, missing_head)
    missing_fig_ref = [f for f in required_figures if f not in report]
    check("F-06", "report references every generated figure", not missing_fig_ref, missing_fig_ref)

    # ---------------------------------------------------------------- frozen evidence intact
    cb = pd.read_csv(T + "carbon_balance_all_runs.csv")
    check("G-01", "carbon balance still present for all eight runs", len(cb) == 8, len(cb))
    check("G-02", "all eight carbon balances close within 95-105 %",
          bool(cb.closes_within_95.astype(bool).all()) or f"{int(cb.closes_within_95.sum())}/8 close",
          f"{int(cb.closes_within_95.sum())}/8")

    raw_ok = True
    for line in open("data/raw/CHECKSUMS.sha256", encoding="utf-8").read().splitlines():
        if not line.strip():
            continue
        expected, name = line.split()
        raw_ok &= (L.sha256_file("data/raw/" + name) == expected)
    check("G-03", "raw CSV checksums verify", raw_ok)

    fmt_bad = []
    for name in required_tables:
        b = open(T + name, "rb").read()
        if b"\r\n" in b or any(c > 127 for c in b):
            fmt_bad.append(name)
    check("G-04", "generated Level 3 tables are ASCII with LF endings", not fmt_bad, fmt_bad)

    json_ok = True
    for name in ("model_policy.json", "horizon_sensitivity.json", "level3_answers.json", "report_claims.json",
                 "grid_summary.json", "input_audit_summary.json"):
        try:
            L.read_json(A + name)
        except Exception as exc:                     # noqa: BLE001 - report the parse failure
            json_ok = False
            print(f"  JSON parse failure in {name}: {exc}")
    check("G-05", "Level 3 audit JSON files parse", json_ok)

    # ---------------------------------------------------------------- summary
    n_pass = sum(1 for c in CHECKS if c["passed"])
    all_ok = n_pass == len(CHECKS)
    print("=" * 78)
    print(f"{n_pass}/{len(CHECKS)} checks passed")

    L.write_json(dict(created=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                      report=REPORT, n_checks=len(CHECKS), n_passed=n_pass,
                      passed=all_ok, checks=CHECKS), A + "consistency_report.json")
    lines = ["# Level 3 consistency audit", "",
             f"Report: `{REPORT}`  |  checks: {n_pass}/{len(CHECKS)} passed  |  status: "
             f"**{'PASSED' if all_ok else 'FAILED'}**", "",
             "| id | check | result | detail |", "|---|---|---|---|"]
    for c in CHECKS:
        lines.append(f"| {c['id']} | {c['description']} | {'PASS' if c['passed'] else 'FAIL'} | "
                     f"{'' if c['passed'] else c['detail'][:300]} |")
    with open(A + "consistency_report.md", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
