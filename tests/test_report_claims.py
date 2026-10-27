"""Checks that numbers typed by hand into reports/level1.md and reports/level2.md (via the generators) match the raw
CSVs and generated tables, and that each report equals the output of its generator.
Run from the project root:  pytest -q tests/test_report_claims.py   (fallback: python tests/test_report_claims.py)"""
import json, os, re, subprocess, sys, tempfile, traceback, unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, "outputs", "tables"); RAW = os.path.join(ROOT, "data", "raw")


def tab(n): return pd.read_csv(os.path.join(T, n))
def near(a, b, tol): assert abs(a - b) <= tol, f"{a} vs {b} (tol {tol})"


def raw():
    r = pd.read_csv(os.path.join(RAW, "runs.csv")).set_index("run"); tc = pd.read_csv(os.path.join(RAW, "timecourse.csv"))
    return r, tc


def val(tc, run, t, col): return float(tc[(tc.run == run) & (tc.time_h == t)][col].iloc[0])
def rate(tc, run, col, a, b): return (val(tc, run, b, col) - val(tc, run, a, col)) / (b - a)


# ---------------------------------------------------------------- reports equal their generators
def _regen(script, out):
    subprocess.run([sys.executable, os.path.join(ROOT, "src", script), out], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    return open(out, encoding="utf-8").read()


def test_level2_report_equals_generator_output():
    with tempfile.TemporaryDirectory() as d:
        assert _regen("make_level2_report.py", os.path.join(d, "r.md")) == open(os.path.join(ROOT, "reports", "level2.md"), encoding="utf-8").read()


def test_level1_report_equals_generator_output():
    with tempfile.TemporaryDirectory() as d:
        assert _regen("make_level1_report.py", os.path.join(d, "r.md")) == open(os.path.join(ROOT, "reports", "level1.md"), encoding="utf-8").read()


# ---------------------------------------------------------------- Level 2 hand-typed numbers vs raw data
def test_early_ethanol_rates_and_late_rates():
    _, tc = raw()
    for run, v in (("R1", 2.84), ("R4", 2.88), ("R2", 2.53), ("R5", 2.58), ("R8", 1.95)):
        near((val(tc, run, 12, "ethanol_g_L") - val(tc, run, 0, "ethanol_g_L")) / 12, v, 0.011)
    r5, r3 = rate(tc, "R5", "ethanol_g_L", 24, 36), rate(tc, "R3", "ethanol_g_L", 24, 36)
    near(r5, 1.71, 0.011); near(r3, 2.18, 0.011); near(100 * (1 - r5 / r3), 22, 1.0)
    assert 65.5 <= val(tc, "R8", 36, "ethanol_g_L") <= 66.5 and 79.0 <= val(tc, "R8", 48, "ethanol_g_L") <= 80.5   # "66-80 g/L"


def test_raw_facts_quoted_in_text():
    r, tc = raw()
    near(val(tc, "R4", 0, "TRS_g_L_as_glucose"), 155.9, 0.05); assert r.loc["R4", "initial_TRS_g_L_as_glucose"] == 160
    z = (155.9 - 160) / (0.01 * 155.9 + 0.4); near(z, -2.09, 0.01)
    ratio = (r.initial_TRS_g_L_as_glucose / r.initial_sugars_sucrose_plus_reducing_g_L); assert ratio.min() > 1.0365 and ratio.max() < 1.0371   # 1.0368
    hp = pd.read_csv(os.path.join(RAW, "endpoint_hplc.csv"), dtype=str).set_index("run")
    near(float(hp.loc["R7", "lactic_acid_g_L"]) / 0.2, 45, 1e-9); near(float(hp.loc["R7", "final_pH"]), 3.84, 1e-9)
    assert len(tc[tc.run == "R7"]) * 4 - 4 == 52                      # 13 positive times x 4 variables = 52 residuals
    near(tab("heldout_predictions.csv").query("variable=='S' and time_h==48").observed.iloc[0], 48.7, 0.05)
    near(tab("heldout_predictions.csv").query("variable=='P' and time_h==48").observed.iloc[0], 100.1, 0.05)
    assert max(tc.ethanol_g_L) == 107.8 or abs(max(tc[tc.run != "R6"].ethanol_g_L) - 107.8) < 1e-9
    t24 = tc[tc.time_h == 24].set_index("run")
    assert 10.0 <= t24.biomass_g_L.min() and t24.biomass_g_L.max() <= 11.5                   # "10.0-11.5 g/L at 24 h"
    assert 70 <= t24.loc[["R2", "R3", "R5", "R6", "R7", "R8"], "TRS_g_L_as_glucose"].min() <= 71 and 121 <= t24.loc[["R2", "R3", "R5", "R6", "R7", "R8"], "TRS_g_L_as_glucose"].max() <= 122.5
    near(val(tc, "R1", 48, "ethanol_g_L"), 71.8, 0.05); near(val(tc, "R4", 48, "ethanol_g_L"), 74.6, 0.05)


# ---------------------------------------------------------------- Level 2 hand-typed numbers vs tables
def test_model_comparison_claims():
    c = tab("model_comparison.csv").set_index("model")
    assert (c.starts_near_best == "8/8").all() and (c.ode_failures == 0).all() and (c.n_obs == 299).all()
    assert c.loc["M3", "params_at_bound"] == 1 and c.drop("M3").params_at_bound.eq(0).all()
    d = c.loc["M2", "QAICc"] - c.loc["M5", "QAICc"]; near(d, 144, 1.0); near(d / 3, 48, 1.0)
    assert c.loc["M5", "mean_z_X":"mean_z_C"].between(-0.62, -0.05).all()
    assert c.mean_lag1_autocorr.between(0.5, 0.75).all()
    cp = tab("candidate_parameters.csv"); near(cp.query("model=='M3' and parameter=='n_inh'").value.iloc[0], 4.0, 1e-6)
    l1 = tab("level1_parameters.csv").set_index("parameter"); near(l1.loc["X_max", "value"], 9.3, 0.05); near(l1.loc["k34", "value"], 0.97, 0.005)
    near(c.loc["M0", "chi2"], json.load(open(os.path.join(T, "level1_frozen.json")))["chi2"], 1e-3)                         # M0 == Level 1
    loro = pd.concat([pd.DataFrame(json.load(open(os.path.join(T, "work", f"loro_{m}.json")))).assign(model=m) for m in c.index]).pivot(index="held_out_run", columns="model", values="chi2_per_point")
    assert loro.loc["R1"].idxmin() == "M3" and loro.loc["R3", list(c.index)].idxmin() == "M6"
    assert [r for r in ["R1", "R2", "R3", "R4", "R5"] if loro.loc[r].idxmin() == "M5"] == ["R2", "R4", "R5"]
    r6 = tab("model_r6_diagnostic.csv").set_index("model"); near(r6.loc["M0", "TRS_48h_pred"] - 48.7, -10.0, 0.06)


def test_uncertainty_claims():
    u = tab("parameter_uncertainty.csv"); f = u[u.status == "fitted"]
    assert not f.ci_open_lo.astype(bool).any() and not f.ci_open_hi.astype(bool).any()                  # "none was open"
    corr = tab("parameter_correlations_material.csv"); m5 = corr[corr.model == "M5"]
    def cc(a, b):
        x = m5[((m5.parameter_1 == a) & (m5.parameter_2 == b)) | ((m5.parameter_1 == b) & (m5.parameter_2 == a))]
        return float(x.correlation_linearised.iloc[0])
    near(cc("P_max", "n_inh"), 0.98, 0.006); near(cc("beta_P", "k34"), 0.70, 0.02); near(cc("beta_P", "k37"), 0.75, 0.02)
    rho = f[(f.model == "M5") & (f.parameter == "rho_CO2")].iloc[0]; assert rho.ci_lo > 0.9553                 # stoichiometric value outside interval
    lab = f[f.model == "M5"].set_index("parameter").identifiability
    assert "jointly" in lab["P_max"] and "jointly" in lab["n_inh"] and "ONE run" in lab["k37"]
    fx = tab("fixed_parameter_sensitivity.csv"); ks = fx[(fx.model == "M5") & (fx.fixed_parameter == "K_s")].set_index("value").chi2
    assert ks.idxmin() == 0.05 and ks.is_monotonic_increasing
    chat = tab("model_comparison.csv").set_index("model").loc["M5", "reduced_chi2"]
    assert (ks[0.2] - ks[0.05]) / chat > 3.84 and 30 < (ks[1.0] - ks[0.05]) / chat < 42
    n0 = fx[(fx.model == "M0") & (fx.fixed_parameter == "n_inh")].set_index("value").chi2; assert n0.is_monotonic_decreasing
    r7 = tab("r7_inclusion_effect.csv"); m5r = r7[r7.model == "M5"]; assert m5r.change_pct.abs().max() < 13.5 and m5r.change_pct.abs().max() > 12.5


def test_carbon_and_yield_claims():
    cb = tab("carbon_balance_all_runs.csv").set_index("run"); p0 = tab("preliminary_carbon_balance.csv").set_index("run")
    near(cb.recovery_pct.min(), 98.2, 0.06); near(cb.recovery_pct.max(), 104.7, 0.06)
    assert list(cb[~cb.closes_within_95.astype(bool)].index) == ["R4"]
    assert (cb.recovery_consumed_basis_pct - p0.recovery_pct).abs().max() < 0.4                                  # "within 0.4 points"
    d = tab("yield_gap_decomposition.csv").set_index("run"); r4 = d.loc["R4"]
    near(r4.unaccounted_pct_pts, -4.9, 0.06); near(r4.unaccounted_95_lo, -8.5, 0.06); near(r4.unaccounted_95_hi, -1.5, 0.06)
    inc0 = ((d.unaccounted_95_lo <= 0) & (d.unaccounted_95_hi >= 0)); assert inc0.sum() == 7 and not inc0["R4"]
    y = tab("ethanol_yields.csv").set_index("run"); assert y.loc["R4", "yield_catabolic_after_biomass_sugar"] > 0.5114
    near(tab("ethanol_yield_pooled.csv").set_index("set").loc["all 8 runs", "pooled_yield_sum_ratio"] * 1.0368, 0.476, 0.0006)
    rv = tab("r7_review.csv").set_index("quantity"); near(rv.loc["lactic acid as glucose equivalent (1 glucose -> 2 lactic acid)", "R7"], 9.0, 0.05)


def test_plant_and_design_claims():
    sp = tab("structure_spread.csv"); m3 = sp[(sp.model == "M3") & (sp.T_C == 37) & (sp.S0_gL == 260)].iloc[0]; near(m3.t_end, 94, 0.5)
    m5 = sp[(sp.model == "M5") & (sp.T_C == 37) & (sp.S0_gL == 260)].iloc[0]; assert not bool(m5.feasible)
    ks = tab("plant_Ks_sensitivity.csv"); k = ks[(ks["T_C"] == 33)].set_index("K_s")
    near(k.loc[0.05, "t_end"], 46.0, 0.06); near(k.loc[5.0, "t_end"], 47.6, 0.06)
    for kk in (0.05, 0.2, 5.0): assert abs(k.loc[kk, "daily_margin_Rs"] / k.loc[1.0, "daily_margin_Rs"] - 1) <= 0.045          # "1-4%"
    assert abs(k.loc[20.0, "daily_margin_Rs"] / k.loc[1.0, "daily_margin_Rs"] - 1) > 0.10
    pu = tab("plant_prediction_uncertainty.csv"); assert len(set(pu.n_draws)) == 1 and pu.n_draws.iloc[0] == 150
    e = tab("experiment_design.csv").set_index(["T_C", "S0_gL", "horizon_h"])
    near(e.loc[(36, 260, 96), "TRS96_sd_reduction_pct_37C_260"], 64, 0.6); near(e.loc[(34, 260, 96), "TRS96_sd_reduction_pct_37C_260"], 52, 0.6)
    near(e.loc[(36, 260, 96), "TRS96_sd_reduction_pct_36C_260"], 65, 0.6); near(e.loc[(34, 260, 96), "TRS96_sd_reduction_pct_36C_260"], 65, 0.6)
    assert e.mean_margin_sd_reduction_pct.idxmax() == (34.0, 260.0, 96)
    fz = json.load(open(os.path.join(T, "model_selection_frozen.json"))); assert fz["preferred"] == "M5" and fz["r6_used_for_selection"] is False


def test_level1_report_hand_typed_numbers():
    r, tc = raw(); hp = pd.read_csv(os.path.join(RAW, "endpoint_hplc.csv"), dtype=str).set_index("run"); p0 = tab("preliminary_carbon_balance.csv").set_index("run")
    ph = [float(hp.loc[x, "final_pH"]) for x in ("R1", "R2", "R4", "R5", "R8")]; assert min(ph) == 4.38 and max(ph) == 4.43
    near(p0.loc["R3", "recovery_pct"], 101.8, 0.06); near(p0.loc["R6", "recovery_pct"], 100.4, 0.06); near(p0.loc["R7", "recovery_pct"], 101.2, 0.06)
    cb = tab("carbon_balance_all_runs.csv").set_index("run"); near(cb.loc["R7", "recovery_pct_lactic_removed"], 96.5, 1.1)             # "about 96.5%" (Phase 0 basis 96.5; total-input basis 97.0)
    near(100 * cb.loc["R7", "C_out_lactic"] / (cb.loc["R7", "C_in_sugar_Cmol_L"] - cb.loc["R7", "C_out_residual_sugar"]), 4.7, 0.06)   # lactic carbon ~4.7% of consumed carbon
    for run, a, b in (("R7", 28.7, 84.2), ("R5", 6.6, 96.6)):
        near(val(tc, run, 48, "TRS_g_L_as_glucose"), a, 0.05); near(val(tc, run, 48, "ethanol_g_L"), b, 0.05)
    t48 = tc[tc.time_h == 48].biomass_g_L; near(t48.min(), 10.9, 0.05); near(t48.max(), 12.3, 0.05)
    t24 = tc[tc.time_h == 24].set_index("run"); assert 49.5 <= t24.loc["R8", "ethanol_g_L"] <= 50.5 and 68 <= t24.loc[["R1", "R2"], "ethanol_g_L"].min() and t24.loc[["R1", "R2"], "ethanol_g_L"].max() <= 69
    for run in ("R3", "R6", "R7", "R8"):                                                                                                  # late uptake 30-50% of early
        q = rate(tc, run, "TRS_g_L_as_glucose", 36, 48) / rate(tc, run, "TRS_g_L_as_glucose", 0, 12); assert 0.30 <= q <= 0.51, (run, q)
    ratios = (tc[tc.time_h == 48].set_index("run").CO2_evolved_g_per_L / tc[tc.time_h == 48].set_index("run").ethanol_g_L)
    near(ratios.min(), 0.938, 0.0006); near(ratios.max(), 1.022, 0.0006); assert ratios.idxmin() == "R4" and ratios.idxmax() == "R1"
    hpred = tab("heldout_predictions.csv"); h = hpred[hpred.time_h > 0]
    for v, n in (("P", 7), ("S", 9), ("C", 9), ("X", 6)): assert int((h[h.variable == v].z.abs() > 2).sum()) == n, v
    s = h[h.variable == "S"]; assert (s[s.time_h >= 8].error < 0).all()
    c = h[(h.variable == "C") & (h.time_h >= 12)]; near(c.error.min(), 2.1, 0.06); near(c.error.max(), 6.4, 0.06); assert c.z.min() > 2.95 and c.z.max() < 3.75
    p = h[h.variable == "P"]; near(p.error.max(), 5.6, 0.06)
    e = hpred[(hpred.time_h == 48)].set_index("variable"); y6 = e.loc["P", "observed"] / (260 - e.loc["S", "observed"]); pred_dS = 260 - e.loc["S", "predicted"]
    near(e.loc["P", "predicted"] / y6, 214.9, 0.1); near(pred_dS, 221.3, 0.1); near(pred_dS - e.loc["P", "predicted"] / y6, 6.4, 0.1)
    near(e.loc["P", "predicted"] - e.loc["P", "observed"], 1.7, 0.06)
    sens = tab("level1_sensitivity.csv"); g = lambda c_, p_, col: float(sens[(sens.case == c_) & (sens.parameter == p_)][col].iloc[0])
    near(g("R7_included", "mu_max", "change_pct"), 10.1, 0.06); near(g("R7_included", "k34", "change_pct"), -5.6, 0.06); near(g("R7_included", "Y_P", "change_pct"), -1.7, 0.06)
    near(g("R7_included", "k34", "change_in_primary_se"), -6.5, 0.06); near(g("R7_included", "P_max", "change_in_primary_se"), -2.1, 0.06); near(g("R7_included", "Y_P", "change_in_primary_se"), -1.9, 0.06)
    near(sens[(sens.case == "R7_included") & (sens.parameter == "k34")].value.iloc[0], 0.917, 0.0006)
    near(sens[sens.case == "R3_biomass_included_sd_x2"].change_pct.abs().max(), 3.3, 0.06)
    near(max(abs(g("Ks_0.2", "mu_max", "change_pct")), abs(g("Ks_5", "mu_max", "change_pct"))), 6.1, 0.06)
    near(g("CO2_floor_0", "mu_max", "change_pct"), -13.9, 0.06); near(g("CO2_floor_0", "q_max", "change_pct"), 7.1, 0.06)
    near(sens[sens.case == "CO2_floor_0.5"].change_pct.abs().max(), 4.4, 0.06)
    l1 = tab("level1_parameters.csv").set_index("parameter"); near(100 * l1.loc["rho_CO2", "value"] / 0.9553 - 100, 3.3, 0.06)


def test_phase0_counts_quoted_in_reports():
    dq = tab("data_quality.csv"); col = [c for c in dq.columns if c.lower() in ("status", "flag", "result")][0]
    vc = dq[col].value_counts(); assert (vc.get("PASS", 0), vc.get("INFO", 0), vc.get("FLAG", 0)) == (74, 58, 5)


def test_test_counts_quoted_in_reports():
    for f, n in (("test_level2.py", 15), ("test_model.py", 16)):
        assert len(re.findall(r"^def test_", open(os.path.join(ROOT, "tests", f)).read(), re.M)) == n
    txt = open(os.path.join(ROOT, "reports", "level2.md"), encoding="utf-8").read()
    assert "15 passed / 0 failed / 0 skipped" in txt and "16 passed / 0 failed / 0 skipped" in txt and "`tests/test_report_claims.py` 11 passed / 0 failed" in txt
    assert len(re.findall(r"^def test_", open(os.path.join(ROOT, "tests", "test_report_claims.py")).read(), re.M)) == 11


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    npass = nfail = 0
    for n, f in tests:
        try:
            f(); npass += 1; print("PASS ", n)
        except Exception:
            nfail += 1; print("FAIL ", n); traceback.print_exc()
    print(f"\n{npass} passed, {nfail} failed (fallback runner, not pytest)"); sys.exit(1 if nfail else 0)
