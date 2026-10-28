"""Level 2 tests. Run from the project root:  pytest -q tests/test_level2.py   (fallback: python tests/test_level2.py)
Tests needing generated outputs are skipped (not passed) if the files are absent."""
import json, os, re, sys, traceback, unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import carbon_balance as CB   # noqa: E402
import compare as C           # noqa: E402
import fit                    # noqa: E402
import kinetics as K          # noqa: E402
import models as M            # noqa: E402
import plant_uncertainty as PU  # noqa: E402
import uncertainty as U       # noqa: E402

RAW = os.path.join(ROOT, "data", "raw"); TAB = os.path.join(ROOT, "outputs", "tables")
T14 = np.array([0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 30, 36, 42, 48.0])


def _need(*names):
    for n in names:
        if not os.path.exists(os.path.join(TAB, n)): raise unittest.SkipTest(n + " not generated")


def _l1theta():
    _need("level1_parameters.csv")
    p = pd.read_csv(os.path.join(TAB, "level1_parameters.csv")); f = p[p.status == "fitted"].set_index("parameter")
    return np.array([f.loc[n, "value"] for n in K.PARAM_NAMES])


# -------------------------------------------------------------- model family
def test_M0_reproduces_level1_exactly():
    th = _l1theta()
    for T, S0 in [(30, 160), (34, 260), (37, 220)]:
        a = np.maximum(K.simulate(T, S0, 2.5, T14, th), 0); b = M.simulate("M0", T, S0, 2.5, T14, th)
        assert np.max(np.abs(a - b)) < 1e-10


def test_parameter_counts():
    assert [len(M.spec(v)[0]) for v in M.VARIANTS] == [8, 7, 9, 9, 8, 10, 9]


def test_nested_variants_reduce_to_baseline():
    th = _l1theta(); names0 = M.spec("M0")[0]; base = dict(zip(names0, th))
    ref = M.simulate("M0", 34, 220, 2.5, T14, th)
    t2 = np.array([base.get(n, 0.0) if n != "beta_P" else 0.0 for n in M.spec("M2")[0]])
    assert np.max(np.abs(M.simulate("M2", 34, 220, 2.5, T14, t2) - ref)) < 1e-9               # beta_P = 0
    t3 = np.array([base.get(n, 1.0) for n in M.spec("M3")[0]])
    assert np.max(np.abs(M.simulate("M3", 34, 220, 2.5, T14, t3) - ref)) < 1e-9               # n = 1
    b1 = dict(base); b1["k34"] = 1.0; th1 = np.array([b1[n] for n in names0]); t1 = np.array([b1[n] for n in M.spec("M1")[0]])
    assert np.max(np.abs(M.simulate("M1", 34, 220, 2.5, T14, t1) - M.simulate("M0", 34, 220, 2.5, T14, th1))) < 1e-9
    b4 = dict(base); b4["P_max"] = 1e9; th4 = np.array([b4[n] for n in names0])
    assert np.max(np.abs(M.simulate("M4", 34, 220, 2.5, T14, th4) - M.simulate("M0", 34, 220, 2.5, T14, th4))) < 1e-6   # no inhibition -> same


def test_pmax_T_lowers_tolerance_at_high_T():
    names = M.spec("M2")[0]; th = np.array([dict(mu_max=.2, X_max=10, q_max=1.2, P_max=130, Y_P=.48, rho_CO2=.98, k34=1, k37=1, beta_P=0.04)[n] for n in names])
    hot = M.simulate("M2", 37, 260, 2.5, np.array([0, 48.0]), th)[-1, 2]; cold = M.simulate("M2", 30, 260, 2.5, np.array([0, 48.0]), th)[-1, 2]
    assert hot < cold


def test_models_refuse_extrapolation_in_temperature():
    th = M.spec("M2")[1]
    for T in (25.0, 38.0):
        try:
            M.simulate("M2", T, 220, 2.5, T14, th); raise AssertionError("accepted")
        except ValueError:
            pass


# -------------------------------------------------------------- protocol
def test_comparison_fits_use_training_runs_only():
    assert "R6" not in C.TRAIN and "R7" not in C.TRAIN
    _need("work/fit_M0.json")
    for v in M.VARIANTS:
        assert json.load(open(os.path.join(TAB, "work", f"fit_{v}.json")))["n_obs"] == 299


def test_selection_rule_reproduces_and_is_frozen_before_r6():
    _need("model_comparison.csv", "model_selection_frozen.json", "model_r6_diagnostic.csv")
    cmp = pd.read_csv(os.path.join(TAB, "model_comparison.csv")); fr = json.load(open(os.path.join(TAB, "model_selection_frozen.json")))
    assert fit.sha256(os.path.join(TAB, "model_comparison.csv")) == fr["model_comparison_sha256"] and fr["r6_used_for_selection"] is False
    q = cmp.chi2 / fr["c_hat"] + 2 * cmp.k_params + 2 * cmp.k_params * (cmp.k_params + 1) / (cmp.n_obs - cmp.k_params - 1)
    assert np.allclose(q, cmp.QAICc)
    ok = cmp[(cmp.params_at_bound == 0) & (cmp.ode_failures == 0)]; best = ok.loc[ok.QAICc.idxmin()]
    close = ok[(ok.QAICc - best.QAICc <= 4) & (ok.k_params < best.k_params)]
    pref = close.loc[close.k_params.idxmin()].model if len(close) else best.model
    assert pref == fr["preferred"] and list(cmp[cmp.selected_by_D24].model) == [pref]
    d = pd.read_csv(os.path.join(TAB, "model_r6_diagnostic.csv"))                                    # content check (file times are not reliable after copying)
    assert list(d[d.preferred].model) == [fr["preferred"]] and d.note.str.contains("not used for selection").all()


def test_level1_files_preserved():
    _need("level1_frozen.json")
    fr = json.load(open(os.path.join(TAB, "level1_frozen.json")))
    assert fit.sha256(os.path.join(TAB, "level1_parameters.csv")) == fr["parameters_csv_sha256"]
    for f in ["src/kinetics.py", "src/fit.py", "reports/level1.md", "outputs/tables/heldout_metrics.csv"]:
        assert os.path.getsize(os.path.join(ROOT, f)) > 0


# -------------------------------------------------------------- uncertainty helpers
def test_profile_crossing_matches_analytic_parabola():
    xs = np.array([-8, -4, -2, 0, 2, 4, 8.0]); pts = [dict(value=x, chi2=10 + x ** 2) for x in xs]   # chi2 = chi0 + x^2
    hi, open_hi, _ = U.crossing(pts, 10.0, 3.84, +1); lo, open_lo, _ = U.crossing(pts, 10.0, 3.84, -1)
    assert not open_hi and not open_lo and abs(hi - np.sqrt(3.84)) < 0.05 and abs(lo + np.sqrt(3.84)) < 0.05


def test_open_profile_is_reported_open_not_numeric():
    pts = [dict(value=x, chi2=10 + 0.01 * x) for x in (0, 1, 2, 3.0)]
    v, is_open, edge = U.crossing(pts, 10.0, 3.84, +1)
    assert v is None and is_open and edge == 3.0


def test_parameter_uncertainty_table_consistency():
    _need("parameter_uncertainty.csv")
    d = pd.read_csv(os.path.join(TAB, "parameter_uncertainty.csv")); f = d[d.status == "fitted"]
    assert len(f) > 0 and f.identifiability.notna().all()
    closed = f[~f.ci_open_lo.astype(bool) & ~f.ci_open_hi.astype(bool)]
    assert ((closed.ci_lo <= closed.value + 1e-9) & (closed.value <= closed.ci_hi + 1e-9)).all()
    openr = f[f.ci_open_lo.astype(bool)]; assert openr.ci_lo.isna().all()
    assert "K_s" in set(d[d.status == "fixed"].parameter)


# -------------------------------------------------------------- carbon balance and yields
def test_carbon_balance_arithmetic_and_all_runs_present():
    _need("carbon_balance_all_runs.csv")
    cb = pd.read_csv(os.path.join(TAB, "carbon_balance_all_runs.csv")); assert list(cb.run) == [f"R{i}" for i in range(1, 9)]
    d = CB.load(RAW); x = d["R2"]
    cin = x["S0"] / 180.16 * 6 + x["X0"] / 24.6
    cout = x["S48"] / 180.16 * 6 + x["X48"] / 24.6 + x["E"] / 46.07 * 2 + x["C"] / 44.01 + x["G"] / 92.09 * 3 + 0.1 / 90.08 * 3
    r = cb.set_index("run").loc["R2"]
    assert abs(r.C_in_total_Cmol_L - cin) < 1e-9 and abs(r.C_out_total_Cmol_L - cout) < 1e-9 and abs(r.recovery_pct - 100 * cout / cin) < 1e-9
    assert abs(r.unaccounted_Cmol_L - (cin - cout)) < 1e-9
    assert (cb.lactic_is_nd.sum() == 7) and (cb[cb.lactic_is_nd].lactic_used_g_L == 0.1).all()          # n.d. is not zero
    assert (cb.recovery_95_lo < cb.recovery_pct).all() and (cb.recovery_pct < cb.recovery_95_hi).all()


def test_yield_and_gap_decomposition_are_exact():
    _need("ethanol_yields.csv", "yield_gap_decomposition.csv", "ethanol_yield_pooled.csv")
    y = pd.read_csv(os.path.join(TAB, "ethanol_yields.csv")).set_index("run"); d = CB.load(RAW)
    assert abs(y.loc["R2", "yield_g_per_g"] - d["R2"]["E"] / (d["R2"]["S0"] - d["R2"]["S48"])) < 1e-12
    assert abs(y.theory.iloc[0] - 2 * 46.07 / 180.16) < 1e-12
    dec = pd.read_csv(os.path.join(TAB, "yield_gap_decomposition.csv")); assert dec.check_sum_minus_gap.abs().max() < 1e-9
    assert np.allclose(dec.gap_pct_of_consumed_carbon, 100 - dec.yield_pct_of_theory)
    p = pd.read_csv(os.path.join(TAB, "ethanol_yield_pooled.csv")).set_index("set")
    E = sum(d[r]["E"] for r in d); dS = sum(d[r]["S0"] - d[r]["S48"] for r in d)
    assert abs(p.loc["all 8 runs", "pooled_yield_sum_ratio"] - E / dS) < 1e-12


# -------------------------------------------------------------- plant-relevant calculations (no optimisation)
def test_steam_curve_and_margin_formula():
    st, ext, wash = PU.steam_per_L(78.9); assert abs(wash - 10.0) < 1e-9 and abs(st - 2.64) < 1e-9 and not ext
    assert PU.steam_per_L(40.0)[1] and PU.steam_per_L(150.0)[1]                                        # flagged extrapolation
    th = np.array([0.1874, 9.7484, 1.2701, 125.4494, 0.4794, 0.9858, 1.0713, 0.7820, 0.0426]); r = PU.margin("M2", th, 33.0, 220.0)
    assert r["feasible"], "scenario chosen so that the formula branch is exercised"
    if r["feasible"]:
        L = r["P_end"] / 0.789; exp = (L * 60 - 220 * 25 - L * PU.steam_per_L(r["P_end"])[0] * 1.6) * 170 / (r["t_end"] + 8) * 24
        assert abs(exp - r["daily_margin_Rs"]) < 1e-6 * abs(exp)


def test_no_optimisation_code_in_plant_module():
    src = open(os.path.join(ROOT, "src", "plant_uncertainty.py")).read()
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    assert not re.search(r"minimize|differential_evolution|brute\(|shgo|basinhopping|scipy\.optimize", code)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    npass = nfail = nskip = 0
    for n, f in tests:
        try:
            f(); npass += 1; print("PASS ", n)
        except unittest.SkipTest as e:
            nskip += 1; print("SKIP ", n, "-", e)
        except Exception:
            nfail += 1; print("FAIL ", n); traceback.print_exc()
    print(f"\n{npass} passed, {nfail} failed, {nskip} skipped (fallback runner, not pytest)"); sys.exit(1 if nfail else 0)
