"""Level 3 regression checks: model policy, completion criterion, economics, scenarios, packaging.

These tests are arithmetic and structural.  They re-derive the Level 3 numbers from the
frozen parameter set and the generated tables rather than trusting the stored values, so a
silent change in the economics, the steam curve, the completion rule or the model policy is
caught here.

They never refit a model, never touch R6 and never overwrite outputs.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TAB = ROOT / "outputs" / "tables"
AUD = ROOT / "outputs" / "audits" / "level3"
FIG = ROOT / "outputs" / "figures"
sys.path.insert(0, str(SRC))

import level3 as L  # noqa: E402
import models as M  # noqa: E402


def _grid():
    p = TAB / "optimization_grid.csv"
    if not p.exists():
        pytest.skip("Level 3 grid not generated yet")
    return pd.read_csv(p)


def _read(name):
    p = TAB / name
    if not p.exists():
        pytest.skip(f"{name} not generated yet")
    return pd.read_csv(p)


# ------------------------------------------------------------------ model policy
def test_frozen_model_policy_verifies_and_m5_is_primary():
    pol = L.verify_model_policy(str(ROOT))
    assert pol["all_checks_passed"], {k: v for k, v in pol["checks"].items() if not v}
    assert pol["preferred_model"] == "M5"
    assert pol["selection_rule"] == "D-24"
    assert pol["heldout_run"] == "R6"
    assert "R6" not in pol["training_runs"]
    assert pol["checks"]["r6_not_used_for_selection"] is True


def test_level3_uses_the_frozen_m5_parameter_values_unchanged():
    frozen = json.loads((TAB / "work" / "fit_M5.json").read_text(encoding="utf-8"))
    ps = L.load_parameter_set("M5", str(ROOT))
    assert list(ps["names"]) == list(frozen["names"])
    assert np.allclose(ps["theta"], np.array(frozen["theta"], float), rtol=0, atol=0)
    # and the parameter-set id quoted in the grid is the one this loader computes
    grid = _grid()
    ids = set(grid.loc[grid.model == "M5", "parameter_set_id"])
    assert ids == {ps["parameter_set_id"]}, ids


def test_grid_rows_are_traceable_to_a_parameter_set():
    grid = _grid()
    for model in ("M5", "M2", "M6"):
        sub = grid[grid.model == model]
        assert len(sub) > 0
        assert sub.parameter_set_id.nunique() == 1
        assert sub.parameter_set_id.iloc[0].startswith(model + "_")


# ------------------------------------------------------------------ steam curve
def test_steam_curve_matches_the_brief_and_is_never_extrapolated():
    brief = (ROOT / "docs" / "assignment_brief.md").read_text(encoding="utf-8")
    for wash, kg in zip(L.STEAM_CURVE_WASH_PCT, L.STEAM_CURVE_KG_PER_L):
        assert f"{wash:.0f}" in brief
        assert f"{kg:.2f}" in brief, kg
        row = L.steam_intensity(wash * 7.89)          # exactly on a tabulated point
        assert row["steam_curve_in_range"] is True
        assert row["steam_kg_per_L"] == pytest.approx(kg, abs=1e-12)
    # inside the range: interpolation stays between the bracketing values
    mid = L.steam_intensity(10.5 * 7.89)
    assert mid["steam_curve_in_range"] is True
    assert 2.53 < mid["steam_kg_per_L"] < 2.64
    # outside the range: NaN, flagged, both sides
    below = L.steam_intensity(6.5 * 7.89)
    above = L.steam_intensity(15.0 * 7.89)
    for row in (below, above):
        assert row["steam_curve_in_range"] is False
        assert math.isnan(row["steam_kg_per_L"])
    assert below["steam_curve_status"] == "below_7_pct_vv"
    assert above["steam_curve_status"] == "above_14_pct_vv"


def test_no_grid_row_outside_the_steam_curve_carries_a_margin():
    grid = _grid()
    outside = grid[grid.steam_curve_in_range == False]   # noqa: E712 - explicit boolean column
    assert len(outside) > 0, "expected at least one out-of-curve candidate in this search"
    assert outside.margin_per_cycle_inr_per_h.isna().all()
    assert outside.batch_margin_inr.isna().all()
    # and nothing inside the curve is left unpriced for a completed batch
    completed = grid[(grid.batch_completed == True) & (grid.steam_curve_in_range == True)]  # noqa: E712
    assert completed.margin_per_cycle_inr_per_h.notna().all()


# ------------------------------------------------------------------ completion criterion
def test_completion_criterion_is_residual_trs_at_or_below_5_g_per_l():
    grid = _grid()
    completed = grid[grid.batch_completed == True]                      # noqa: E712
    assert len(completed) > 0
    assert (completed.final_trs_g_per_l <= L.TRS_COMPLETION_G_PER_L + 1e-9).all()
    # the interpolated crossing point must sit exactly on the threshold
    assert np.allclose(completed.final_trs_g_per_l, L.TRS_COMPLETION_G_PER_L, atol=1e-9)
    unfinished = grid[grid.feasibility_status == L.STATUS_UNFINISHED]
    assert (unfinished.final_trs_g_per_l > L.TRS_COMPLETION_G_PER_L).all()


def test_unfinished_batches_get_no_completion_time_and_no_margin():
    grid = _grid()
    unfinished = grid[grid.feasibility_status == L.STATUS_UNFINISHED]
    assert len(unfinished) > 0, "this search must contain unfinished cases to be meaningful"
    assert unfinished.completion_time_h.isna().all()
    assert unfinished.cycle_time_h.isna().all()
    assert unfinished.batch_margin_inr.isna().all()
    assert unfinished.margin_per_cycle_inr_per_h.isna().all()
    assert unfinished.margin_24h_equivalent_inr_per_day.isna().all()
    assert (~unfinished.priced.astype(bool)).all()


def test_completion_time_function_locates_the_first_crossing():
    t = np.array([0.0, 1.0, 2.0, 3.0])
    S = np.array([10.0, 7.0, 4.0, 2.0])
    # crossing of 5 g/L lies between t=1 (S=7) and t=2 (S=4): 1 + (7-5)/(7-4) = 1.6667 h
    assert L.completion_time(t, S, 5.0) == pytest.approx(1 + 2.0 / 3.0)
    assert L.completion_time(t, np.array([10.0, 9.0, 8.0, 7.5]), 5.0) is None
    # already below the threshold at t = 0 is not a batch end
    assert L.completion_time(t, np.array([4.0, 3.0, 2.0, 1.0]), 5.0) is None


# ------------------------------------------------------------------ economics
def test_economics_rederived_from_the_grid_columns():
    econ = _read("plant_economics.csv")
    priced = econ[econ.batch_margin_inr.notna()]
    assert len(priced) > 0
    S0 = priced.s0_g_per_l.to_numpy(float)
    P = priced.final_ethanol_g_per_l.to_numpy(float)
    t_end = priced.completion_time_h.to_numpy(float)
    steam = priced.steam_kg_per_L.to_numpy(float)

    sugar_kg = S0 * L.V_WORKING_M3
    ethanol_kg = P * L.V_WORKING_M3
    ethanol_l = ethanol_kg / L.RHO_ETHANOL_KG_PER_L
    revenue = ethanol_l * L.PRICE_ETHANOL_INR_PER_L
    margin = revenue - sugar_kg * L.COST_SUGAR_INR_PER_KG - steam * ethanol_l * L.STEAM_COST_INR_PER_KG
    cycle = t_end + L.TURNAROUND_H

    assert np.allclose(priced.sugar_charged_kg, sugar_kg, rtol=1e-12)
    assert np.allclose(priced.ethanol_mass_kg, ethanol_kg, rtol=1e-12)
    assert np.allclose(priced.ethanol_volume_l, ethanol_l, rtol=1e-12)
    assert np.allclose(priced.ethanol_revenue_inr, revenue, rtol=1e-12)
    assert np.allclose(priced.batch_margin_inr, margin, rtol=1e-12, atol=1e-6)
    assert np.allclose(priced.cycle_time_h, cycle, rtol=1e-12)
    assert np.allclose(priced.margin_per_cycle_inr_per_h, margin / cycle, rtol=1e-12, atol=1e-9)
    assert np.allclose(priced.margin_24h_equivalent_inr_per_day, 24.0 * margin / cycle, rtol=1e-12, atol=1e-8)
    assert (priced.turnaround_h == L.TURNAROUND_H).all()


def test_economics_units_are_dimensionally_consistent():
    # 1 g/L = 1 kg/m3, so concentration x volume is a mass in kg with no conversion factor.
    one = L.economics(S0=200.0, ethanol_end_g_per_l=80.0, completion_h=30.0)
    assert one["sugar_charged_kg"] == pytest.approx(200.0 * 170.0)
    assert one["ethanol_mass_kg"] == pytest.approx(80.0 * 170.0)
    assert one["ethanol_volume_l"] == pytest.approx(80.0 * 170.0 / 0.789)
    assert one["ethanol_revenue_inr"] == pytest.approx(80.0 * 170.0 / 0.789 * 60.0)
    assert one["sugar_cost_inr"] == pytest.approx(200.0 * 170.0 * 25.0)
    assert one["steam_cost_inr"] == pytest.approx(one["steam_kg_per_L"] * one["ethanol_volume_l"] * 1.6)
    assert one["cycle_time_h"] == pytest.approx(38.0)
    assert one["steam_curve_in_range"] is True


def test_economics_refuses_to_price_an_unpriced_batch():
    nan = float("nan")
    out = L.economics(S0=200.0, ethanol_end_g_per_l=nan, completion_h=nan)
    assert math.isnan(out["batch_margin_inr"]) and math.isnan(out["margin_per_cycle_inr_per_h"])
    # an out-of-curve wash strength is also unpriced
    out2 = L.economics(S0=260.0, ethanol_end_g_per_l=120.0, completion_h=40.0)
    assert out2["steam_curve_in_range"] is False
    assert math.isnan(out2["batch_margin_inr"])


def test_brief_q5_point_is_reported_unfinished_and_unpriced():
    grid = _grid()
    row = grid[(grid.model == "M5") & (grid.horizon_h == L.HORIZON_PRIMARY_H)
               & (grid.s0_g_per_l == L.BRIEF_Q5_POINT["s0_g_per_l"])
               & (grid.temperature_c == L.BRIEF_Q5_POINT["temperature_c"])]
    assert len(row) == 1
    r = row.iloc[0]
    assert r.batch_completed == False          # noqa: E712 - explicit
    assert r.feasibility_status == L.STATUS_UNFINISHED
    assert math.isnan(r.margin_per_cycle_inr_per_h)
    assert r.final_ethanol_g_per_l > 100.0


# ------------------------------------------------------------------ scenarios
def test_both_temperature_scenarios_have_a_completed_feasible_optimum():
    grid = _grid()
    prim = grid[(grid.model == "M5") & (grid.horizon_h == L.HORIZON_PRIMARY_H)
                & (grid.feasibility_status == L.STATUS_COMPLETED)]
    normal = prim[(prim.temperature_c >= 33.0) & (prim.temperature_c <= 37.0)]
    warm = prim[(prim.temperature_c >= 36.0) & (prim.temperature_c <= 37.0)]
    assert len(normal) > 0 and len(warm) > 0
    # the warm-scenario optimum must satisfy the published 36 C constraint
    best_warm = warm.loc[warm.margin_per_cycle_inr_per_h.idxmax()]
    assert best_warm.temperature_c >= 36.0 - 1e-9
    assert best_warm.cycle_time_h == pytest.approx(best_warm.completion_time_h + 8.0)


def test_operating_window_and_recommendation_table_are_consistent():
    rec = _read("optimization_recommendations.csv")
    assert (rec.s0_g_per_l >= 160.0 - 1e-9).all() and (rec.s0_g_per_l <= 260.0 + 1e-9).all()
    assert (rec.temperature_c >= 33.0 - 1e-9).all() and (rec.temperature_c <= 37.0 + 1e-9).all()
    warm = rec[(rec.scenario == "warm_min_36")]
    assert (warm.temperature_c >= 36.0 - 1e-9).all()
    assert (rec.feasibility_status == L.STATUS_COMPLETED).all()
    assert (rec.final_trs_g_per_l <= 5.0 + 1e-9).all()
    assert rec.margin_per_cycle_inr_per_h.notna().all()
    # the published top-1 of each scenario is the grid maximum, not a hand-picked row
    grid = _grid()
    for scenario, tmin in (("normal_33_37", 33.0), ("warm_min_36", 36.0)):
        sub = grid[(grid.model == "M5") & (grid.horizon_h == L.HORIZON_PRIMARY_H)
                   & (grid.feasibility_status == L.STATUS_COMPLETED) & (grid.temperature_c >= tmin)]
        top = sub.sort_values("margin_per_cycle_inr_per_h", ascending=False).iloc[0]
        pub = rec[(rec.scenario == scenario) & (rec.rank_basis == "highest_margin_per_cycle_time")
                  & (rec["rank"] == 1)].iloc[0]
        assert pub.s0_g_per_l == pytest.approx(top.s0_g_per_l)
        assert pub.temperature_c == pytest.approx(top.temperature_c)
        assert pub.margin_per_cycle_inr_per_h == pytest.approx(top.margin_per_cycle_inr_per_h, rel=1e-9)


def test_horizon_diagnostic_never_claims_an_unfinished_batch_as_profitable():
    p = TAB / "optimization_horizon_sensitivity.csv"
    if not p.exists():
        pytest.skip("horizon diagnostic not generated yet")
    hz = pd.read_csv(p)
    if not len(hz):
        return
    assert (hz.status_at_120h == L.STATUS_UNFINISHED).all()
    # a scenario still unfinished at 240 h must not carry a margin
    late = hz[hz.completed_by_240h == False]                              # noqa: E712
    assert late.margin_240h_inr_per_h.isna().all()
    summary = json.loads((AUD / "horizon_sensitivity.json").read_text(encoding="utf-8"))
    assert summary["n_outscoring_best_120h"] == int(hz.outranks_best_120h.sum())


# ------------------------------------------------------------------ uncertainty
def test_uncertainty_intervals_are_ordered_and_completion_fractions_are_valid():
    p = TAB / "optimization_uncertainty.csv"
    if not p.exists():
        pytest.skip("uncertainty table not generated yet")
    unc = pd.read_csv(p)
    ens = unc[unc.source.str.startswith("parameter_ensemble_")]
    assert len(ens) > 0
    defined = ens[ens.p2_5.notna()]
    assert (defined["p2_5"] <= defined["median"] + 1e-9).all()
    assert (defined["median"] <= defined["p97_5"] + 1e-9).all()
    assert ens.fraction_draws_completing.between(0.0, 1.0).all()
    # the frozen optimum must complete in every draw; the 37 C / 260 g/L case in none
    q = ens[(ens.candidate_id == "normal_33_37_M5_optimum")
            & (ens.quantity == "margin_per_cycle_inr_per_h")]
    assert q.iloc[0].fraction_draws_completing == pytest.approx(1.0)
    q5 = ens[(ens.candidate_id == "brief_q5_37C_260") & (ens.quantity == "margin_per_cycle_inr_per_h")]
    assert q5.iloc[0].fraction_draws_completing == pytest.approx(0.0)


def test_model_comparison_keeps_m5_as_the_reference():
    p = TAB / "optimization_model_comparison.csv"
    if not p.exists():
        pytest.skip("model comparison not generated yet")
    cmp_df = pd.read_csv(p)
    assert set(cmp_df.model.unique()) == {"M5", "M2", "M6"}
    m5 = cmp_df[(cmp_df.model == "M5") & (cmp_df.case == "own_optimum")]
    assert (m5.delta_margin_vs_M5_optimum_inr_per_h.abs() < 1e-9).all()
    # the alternatives are reported as comparisons, never as the preferred model
    policy = json.loads((AUD / "model_policy.json").read_text(encoding="utf-8"))
    assert policy["preferred_model"] == "M5"


# ------------------------------------------------------------------ outputs and formatting
def test_level3_tables_are_ascii_with_lf_and_have_required_columns():
    required = {
        "optimization_grid.csv": ["scenario_row_id", "model", "parameter_set_id", "s0_g_per_l",
                                  "temperature_c", "simulation_status", "completion_time_h",
                                  "final_trs_g_per_l", "final_ethanol_g_per_l", "feasibility_status",
                                  "margin_per_cycle_inr_per_h"],
        "optimization_recommendations.csv": ["scenario", "model", "parameter_set_id", "s0_g_per_l",
                                             "temperature_c", "margin_per_cycle_inr_per_h"],
        "plant_economics.csv": ["case_id", "sugar_cost_inr", "ethanol_revenue_inr", "steam_cost_inr",
                                "batch_margin_inr", "cycle_time_h", "margin_per_cycle_inr_per_h"],
        "optimization_uncertainty.csv": ["candidate_id", "quantity", "p2_5", "p97_5", "fraction_draws_completing"],
        "optimization_model_comparison.csv": ["scenario", "model", "case", "margin_per_cycle_inr_per_h"],
        "optimization_input_audit.csv": ["id", "path", "role", "validation", "verified"],
    }
    for name, cols in required.items():
        p = TAB / name
        if not p.exists():
            pytest.skip(f"{name} not generated yet")
        raw = p.read_bytes()
        raw.decode("ascii")
        assert b"\r\n" not in raw, f"{name} contains CRLF"
        df = pd.read_csv(p)
        for c in cols:
            assert c in df.columns, f"{name} missing column {c}"


def test_level3_figures_exist_and_are_named_in_the_report():
    report = ROOT / "reports" / "level3.md"
    if not report.exists():
        pytest.skip("reports/level3.md not generated yet")
    text = report.read_text(encoding="utf-8")
    for name in ("level3_feasible_region.png", "level3_economics.png",
                 "level3_completion_time.png", "level3_uncertainty.png"):
        assert (FIG / name).exists(), f"{name} missing"
        assert name in text, f"{name} is not referenced by reports/level3.md"


def test_report_numbers_match_the_generated_tables():
    report = ROOT / "reports" / "level3.md"
    if not report.exists():
        pytest.skip("reports/level3.md not generated yet")
    text = report.read_text(encoding="utf-8")
    claims_path = AUD / "report_claims.json"
    assert claims_path.exists(), "report claims file missing"
    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    missing = [c["text"] for c in claims["claims"] if c["text"] not in text]
    assert missing == [], f"claims missing from the report: {missing}"
