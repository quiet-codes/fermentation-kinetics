"""Level 1 model, protocol and reproducibility tests.
Run from the project root:   pytest -q tests/test_model.py
Fallback without pytest:     python tests/test_model.py
Tests that need generated outputs are skipped (not passed) if the files are absent."""
import hashlib, json, os, sys, traceback, unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import fit            # noqa: E402
import kinetics as K  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
TAB = os.path.join(ROOT, "outputs", "tables")


def _need(path):
    if not os.path.exists(path):
        raise unittest.SkipTest(f"{path} not generated yet")


def _frozen_theta():
    _need(os.path.join(TAB, "level1_parameters.csv"))
    p = pd.read_csv(os.path.join(TAB, "level1_parameters.csv"))
    f = p[p.status == "fitted"].set_index("parameter")
    return np.array([f.loc[n, "value"] for n in K.PARAM_NAMES]), p


def _train_residuals(tc_override=None, runs_override=None):
    runs, tc = fit.read_raw(RAW)
    tc = tc if tc_override is None else tc_override
    pol = fit.default_policy()
    recs = fit.make_records(pol["train"], runs, tc)
    th = K.START.copy()
    return fit.residual_fn(recs, pol, dict(failures=0))(th)


# ---------------------------------------------------------------- model equations
def test_constants():
    assert abs(K.SUGAR_PER_BIOMASS - 1.2206) < 5e-4
    assert abs(K.Y_P_STOICH - 0.5114) < 5e-4
    assert abs(K.RHO_STOICH - 0.9553) < 5e-4


def test_carbon_and_co2_identities():
    rng = np.random.default_rng(1)
    for _ in range(200):
        th = K.LOWER + rng.random(len(K.LOWER)) * (K.UPPER - K.LOWER)
        p = K.unpack(th); y = [rng.uniform(2, 12), rng.uniform(0, 260), rng.uniform(0, 100), 0.0]
        T = float(rng.choice(K.T_LEVELS))
        mu, q, dX, dS, dP, dC = K.rates(y, T, p, K.FIXED_DEFAULT)
        assert abs(dS + K.SUGAR_PER_BIOMASS * dX + q * y[0]) < 1e-12      # sugar split: growth + catabolism
        assert abs(dP - p["Y_P"] * q * y[0]) < 1e-12
        assert abs(dC - p["rho_CO2"] * dP) < 1e-12


def test_logistic_growth_matches_analytic_solution():
    th = K.START.copy(); p = K.unpack(th)
    th[K.PARAM_NAMES.index("q_max")] = 0.0
    t = np.linspace(0, 12, 13)
    sim = K.simulate(30.0, 260.0, 2.5, t, th, fixed={"K_s": 1e-12})
    X0, Xm, mu = 2.5, p["X_max"], p["mu_max"]
    analytic = Xm / (1 + ((Xm - X0) / X0) * np.exp(-mu * t))
    assert np.max(np.abs(sim[:, 0] - analytic)) < 1e-5
    assert np.allclose(sim[:, 2], 0) and np.allclose(sim[:, 3], 0)       # no ethanol, no CO2


def test_states_nonnegative_and_monotone_over_parameter_space():
    rng = np.random.default_rng(2)
    t = np.array([0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 30, 36, 42, 48.0])
    for _ in range(30):
        th = K.LOWER + rng.random(len(K.LOWER)) * (K.UPPER - K.LOWER)
        T = float(rng.choice(K.T_LEVELS)); S0 = float(rng.choice([160, 220, 260]))
        sim = K.simulate(T, S0, 2.5, t, th)
        assert sim is not None
        assert sim.min() > -1e-6
        assert np.all(np.diff(sim[:, 0]) >= -1e-8) and np.all(np.diff(sim[:, 2]) >= -1e-8)
        assert np.all(np.diff(sim[:, 3]) >= -1e-8) and np.all(np.diff(sim[:, 1]) <= 1e-8)


def test_thermal_multiplier_levels_interpolation_and_no_extrapolation():
    assert K.thermal_multiplier(30, 0.9, 0.6) == 1.0
    assert abs(K.thermal_multiplier(34, 0.9, 0.6) - 0.9) < 1e-12
    assert abs(K.thermal_multiplier(37, 0.9, 0.6) - 0.6) < 1e-12
    assert abs(K.thermal_multiplier(35.5, 0.9, 0.6) - 0.75) < 1e-12
    for bad in (29.0, 38.0):
        try:
            K.thermal_multiplier(bad, 0.9, 0.6); raise AssertionError("no error")
        except ValueError:
            pass


def test_sugar_exhaustion_stops_ethanol_in_160_g_per_L_run():
    th, _ = _frozen_theta()
    t = np.array([0, 24, 30, 36, 42, 48.0])
    sim = K.simulate(30.0, 160.0, 2.5, t, th)
    assert sim[-1, 1] < 0.5 and abs(sim[-1, 2] - sim[-3, 2]) < 0.5


# ---------------------------------------------------------------- weights
def test_measurement_sd_formulas_and_co2_floor():
    assert abs(float(fit.sd_X(10.0)) - (0.35 + 0.08)) < 1e-12
    assert abs(float(fit.sd_S(100.0)) - 1.4) < 1e-12
    assert abs(float(fit.sd_P(50.0)) - (0.6 + 0.25)) < 1e-12
    assert abs(float(fit.sd_C(50.0)) - (1.0 + fit.CO2_FLOOR)) < 1e-12
    assert float(fit.sd_C(0.0)) > 0                                       # no division by zero


# ---------------------------------------------------------------- protocol (rules 6 and 7)
def test_policy_excludes_holdout_and_r7_and_r3_biomass():
    pol = fit.default_policy()
    assert "R6" not in pol["train"] and "R7" not in pol["train"]
    assert pol["train"] == ["R1", "R2", "R3", "R4", "R5", "R8"]
    assert pol["biomass_excluded"] == {"R3"}
    try:
        fit.default_policy(train=pol["train"] + ["R6"]); raise AssertionError("R6 accepted")
    except ValueError:
        pass


def test_objective_ignores_r6_r7_t0_and_r3_biomass():
    runs, tc = fit.read_raw(RAW)
    base = _train_residuals()
    assert len(base) == 299
    tc2 = tc.copy()
    tc2.loc[tc2.run.isin(["R6", "R7"]), ["biomass_g_L", "TRS_g_L_as_glucose", "ethanol_g_L", "CO2_evolved_g_per_L"]] *= 2.0
    assert np.array_equal(_train_residuals(tc2), base)                    # R6/R7 do not enter
    tc3 = tc.copy()
    tc3.loc[(tc3.run == "R3"), "biomass_g_L"] *= 1.5
    assert np.array_equal(_train_residuals(tc3), base)                    # R3 biomass does not enter
    tc4 = tc.copy()
    tc4.loc[tc4.time_h == 0, ["biomass_g_L", "TRS_g_L_as_glucose", "ethanol_g_L"]] += 1.0
    assert np.array_equal(_train_residuals(tc4), base)                    # t = 0 rows do not enter
    tc5 = tc.copy()
    tc5.loc[(tc5.run == "R3") & (tc5.time_h == 24), "TRS_g_L_as_glucose"] += 5.0
    assert not np.array_equal(_train_residuals(tc5), base)                # R3 sugar does enter


def test_initial_states_are_nominal_metadata():
    runs, tc = fit.read_raw(RAW)
    for r in fit.make_records(["R1", "R4", "R8"], runs, tc):
        assert r["X0"] == 2.5 and r["S0"] == runs.loc[r["run"], "initial_TRS_g_L_as_glucose"]


def test_raw_files_unchanged():
    cs = os.path.join(RAW, "CHECKSUMS.sha256")
    _need(cs)
    for line in open(cs):
        digest, name = line.split()
        assert hashlib.sha256(open(os.path.join(RAW, name), "rb").read()).hexdigest() == digest, name


# ---------------------------------------------------------------- generated outputs
def test_frozen_hash_matches_parameters_file():
    _need(os.path.join(TAB, "level1_frozen.json"))
    fr = json.load(open(os.path.join(TAB, "level1_frozen.json")))
    assert fr["holdout"] == "R6" and "R6" not in fr["training_runs"] and "R7" not in fr["training_runs"]
    assert fit.sha256(os.path.join(TAB, "level1_parameters.csv")) == fr["parameters_csv_sha256"]
    assert fr["ode_failures_counted"] == 0


def test_fitted_parameters_inside_bounds_and_flags_consistent():
    th, p = _frozen_theta()
    assert np.all(th >= K.LOWER) and np.all(th <= K.UPPER)
    flags = p[p.status == "fitted"].set_index("parameter").loc[K.PARAM_NAMES, "at_bound"].tolist()
    assert [f != "no" for f in flags] == list(fit.at_bound_mask(th))


def test_frozen_optimum_is_a_stationary_point_of_the_training_objective():
    from scipy.optimize import least_squares
    th, _ = _frozen_theta()
    runs, tc = fit.read_raw(RAW)
    pol = fit.default_policy(); recs = fit.make_records(pol["train"], runs, tc)
    fun = fit.residual_fn(recs, pol, dict(failures=0))
    chi2 = float(np.sum(fun(th) ** 2))
    r = least_squares(fun, th, bounds=(K.LOWER, K.UPPER), x_scale="jac", diff_step=1e-6, max_nfev=15)
    assert 2 * r.cost > chi2 * (1 - 2e-3)                                 # polishing cannot improve it materially


def test_stored_heldout_predictions_reproduce_from_frozen_parameters():
    _need(os.path.join(TAB, "heldout_predictions.csv"))
    th, p = _frozen_theta()
    fixed = {r.parameter: float(r.value) for r in p[p.status == "fixed"].itertuples()}
    runs, tc = fit.read_raw(RAW)
    rec = fit.make_records(["R6"], runs, tc)[0]
    sim = np.maximum(K.simulate(rec["T"], rec["S0"], rec["X0"], rec["t"], th, fixed), 0)
    hp = pd.read_csv(os.path.join(TAB, "heldout_predictions.csv"))
    for j, v in enumerate(fit.VARS):
        stored = hp[hp.variable == v].sort_values("time_h").predicted.to_numpy()
        assert np.allclose(stored, sim[:, j], rtol=1e-8, atol=1e-8)


def test_phase0_files_still_present():
    for f in ["outputs/tables/data_quality.csv", "outputs/tables/endpoint_diagnostics.csv",
              "outputs/tables/preliminary_carbon_balance.csv", "outputs/figures/raw_curves.png",
              "reports/pre_fit_observations.md", "src/phase0_inspect.py"]:
        assert os.path.getsize(os.path.join(ROOT, f)) > 0, f


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
    print(f"\n{npass} passed, {nfail} failed, {nskip} skipped (fallback runner, not pytest)")
    sys.exit(1 if nfail else 0)
