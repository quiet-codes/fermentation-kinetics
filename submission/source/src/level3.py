#!/usr/bin/env python
"""Level 3 core: model policy, batch simulation, completion criterion and plant economics.

This module holds the *policy* for Level 3.  It contains no search: the grid, the
recommendations, the uncertainty analysis and the report are produced by
``level3_optimize.py`` / ``make_level3_report.py`` which import this module.

Everything here is deliberately explicit so that each number in ``reports/level3.md``
can be traced to a formula in this file.

MODEL POLICY (D-24, frozen before Level 3)
    preferred model      M5        (from outputs/tables/model_selection_frozen.json)
    selection rule       D-24      (QAICc with the c-hat variance inflation, plus a
                                    convergence requirement)
    held-out run         R6        (never used for fitting, tuning or optimisation)
    parameter source     outputs/tables/work/fit_M5.json  (see ``load_parameter_set``)
    robust alternatives  M2, M6    (compared, never substituted for M5)

BATCH MODEL
    The ODE system is *not* re-implemented here: Level 3 integrates exactly the frozen
    Level 2 structure through ``models.simulate``.  That keeps Level 1/Level 2 results
    authoritative and makes it impossible for Level 3 to silently use a different
    kinetic model.

    X, S, P, C in g/L; t in h; constant broth volume; X0 = 2.5 g/L for every plant
    scenario (the inoculum every one of the eight lab runs used, read from runs.csv).

COMPLETION CRITERION (brief section 4)
    A batch is complete only when residual TRS <= 5 g/L.  Completion is the *first*
    crossing of 5 g/L going down, linearly interpolated between the two bracketing
    time points.  If the crossing does not occur inside the documented horizon the
    batch is UNFINISHED: it gets no completion time, no ethanol end point and no
    margin of any kind.  An unfinished batch is never treated as a profitable batch
    stopped at an arbitrary time.

HORIZON
    Primary horizon 120 h at a 0.25 h time step.  The lab data end at 48 h, so any
    completion time > 48 h is a time extrapolation and is flagged as such.
    A 240 h run is kept as a *diagnostic only* (``HORIZON_EXTENDED_H``) to show what
    the unfinished cases would eventually do; it is never used for ranking.

PLANT ECONOMICS (brief section 4) -- per completed feasible batch
    Sugar charged            S0 [g/L] = S0 [kg/m3]  ->  m_S = S0 * V          [kg]
    Ethanol mass             m_E = P_end [g/L] * V                          [kg]
    Ethanol volume           V_E = m_E / 0.789                              [L]
    Revenue                  R   = V_E * 60                                 [INR]
    Sugar cost               Cs  = m_S * 25                                 [INR]
    Wash strength            w   = P_end / 7.89                             [% v/v]
    Steam intensity          s   = design curve at w                        [kg/L ethanol]
    Steam mass               m_St = s * V_E                                 [kg]
    Steam cost               Cst = m_St * 1.6      (1600 INR/t = 1.6 INR/kg) [INR]
    Batch margin             M   = R - Cs - Cst                             [INR]
    Cycle time               t_c = t_end + 8                                [h]
    Margin per cycle time    M / t_c                                        [INR/h]
    24 h equivalent          24 * M / t_c   (DERIVED, not an assignment term) [INR/day]

    Note the unit identity used above: 1 g/L = 1 kg/m3, so a concentration in g/L
    multiplied by a volume in m3 is a mass in kg with no extra factor.  The assignment
    prices sugar per kg TRS charged (including sugar left unfermented), so the sugar
    cost uses S0, not the sugar consumed.

STEAM CURVE -- no silent extrapolation
    The design curve is supplied only for wash strengths 7-14 % v/v.  Inside that
    range the steam intensity is linearly interpolated between the tabulated points.
    Outside it, ``steam_kg_per_L`` is NaN, ``steam_curve_in_range`` is False, the
    status records which side was violated, and NO margin is assigned.  A completed
    batch outside the curve is therefore reported as completed-but-not-costable, not
    as profitable.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import OrderedDict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit as F  # noqa: E402
import models as M  # noqa: E402

# ------------------------------------------------------------------ assignment constants
V_WORKING_M3 = 170.0                 # fermenter working volume (brief s4)
TURNAROUND_H = 8.0                   # empty / clean / refill between batches (brief s4)
TRS_COMPLETION_G_PER_L = 5.0         # highest allowed sugar left at the end (brief s4)
PRICE_ETHANOL_INR_PER_L = 60.0       # fuel ethanol price (brief s4)
COST_SUGAR_INR_PER_KG = 25.0         # fermentable sugar cost per kg TRS charged (brief s4)
STEAM_COST_INR_PER_KG = 1.6          # LP steam 1600 INR/tonne (brief s4)
RHO_ETHANOL_KG_PER_L = 0.789         # ethanol density (brief s4)
WASH_PCT_PER_G_PER_L = 1.0 / 7.89    # wash strength % v/v = ethanol g/L / 7.89 (brief s4)

# Steam design curve exactly as tabulated in brief section 4 (7-14 % v/v).
STEAM_CURVE_WASH_PCT = np.array([7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0])
STEAM_CURVE_KG_PER_L = np.array([3.15, 2.94, 2.77, 2.64, 2.53, 2.44, 2.36, 2.29])
STEAM_CURVE_MIN_PCT = float(STEAM_CURVE_WASH_PCT.min())
STEAM_CURVE_MAX_PCT = float(STEAM_CURVE_WASH_PCT.max())

# ------------------------------------------------------------------ operating window
S0_MIN_G_PER_L, S0_MAX_G_PER_L = 160.0, 260.0    # range covered by the lab data (brief s4)
T_MIN_C, T_MAX_C = 33.0, 37.0                    # October constraint / model upper limit
T_MIN_WARM_C = 36.0                              # alternative scenario: cooling water +3 C
X0_DEFAULT_G_PER_L = 2.5                         # inoculum used by all eight lab runs

# ------------------------------------------------------------------ numerical settings
HORIZON_PRIMARY_H = 120.0
HORIZON_EXTENDED_H = 240.0
TIME_STEP_H = 0.25
DATA_END_H = 48.0                    # last measured time point in timecourse.csv
SEED = 20261028

# ------------------------------------------------------------------ model policy
PREFERRED_MODEL = "M5"
ROBUST_ALTERNATIVES = ("M2", "M6")
SELECTION_RULE = "D-24"

PRIMARY_PARAMETER_SOURCE = "outputs/tables/work/fit_M5.json"
LEVEL1_FROZEN = "outputs/tables/level1_frozen.json"
SELECTION_FROZEN = "outputs/tables/model_selection_frozen.json"
CANDIDATE_PARAMETERS = "outputs/tables/candidate_parameters.csv"

# Discrete model/assumption alternatives reused from the Task 2 evidence tree.
# These are *not* new fits made for Level 3: they are the stored Task 2 sensitivity fits.
DISCRETE_ALTERNATIVES = OrderedDict([
    ("co2_floor_0p0_M5", dict(
        path="outputs/audits/task2/sensitivity/level2/floor_0/outputs/tables/work/fit_M5.json",
        model="M5", description="M5 refitted with the CO2 sd floor set to 0.0 g/L (Task 2)")),
    ("co2_floor_0p5_M5", dict(
        path="outputs/audits/task2/sensitivity/level2/floor_0p5/outputs/tables/work/fit_M5.json",
        model="M5", description="M5 refitted with the CO2 sd floor set to 0.5 g/L (Task 2)")),
])

STATUS_COMPLETED = "completed_feasible"
STATUS_OUT_OF_CURVE = "completed_outside_steam_curve"
STATUS_UNFINISHED = "unfinished"
STATUS_FAILED = "simulation_failed"


# ------------------------------------------------------------------ small helpers
def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def write_csv(df, path):
    """Write a table as ASCII/UTF-8 with Unix line endings, independent of platform."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def write_json(obj, path, indent=2):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    text = json.dumps(obj, indent=indent, sort_keys=False, ensure_ascii=True, allow_nan=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text + "\n")


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def parameter_set_id(model, theta, source):
    """Stable short identifier for a parameter set, so every row can be traced back."""
    payload = json.dumps(dict(model=model, source=source, theta=[float(x) for x in theta]),
                         sort_keys=True).encode("utf-8")
    return f"{model}_{hashlib.sha256(payload).hexdigest()[:16]}"


# ------------------------------------------------------------------ frozen model policy
def load_parameter_set(model, root="."):
    """Load one candidate model's fitted parameters and verify them against the frozen records.

    Returns dict(model, theta, names, source, parameter_set_id, checks, fit_json).
    ``checks`` records every verification so the audit can report them verbatim.
    """
    names = M.spec(model)[0]
    if model == PREFERRED_MODEL:
        path = os.path.join(root, PRIMARY_PARAMETER_SOURCE)
    else:
        path = os.path.join(root, "outputs", "tables", "work", f"fit_{model}.json")
    fj = read_json(path)
    theta = np.array(fj["theta"], float)
    if list(fj["names"]) != list(names):
        raise ValueError(f"{model}: parameter names in {path} do not match models.spec()")
    checks = {
        "source_path": os.path.relpath(path, root).replace(os.sep, "/"),
        "source_sha256": sha256_file(path),
        "n_parameters": len(theta),
        "solver_status": int(fj.get("status", -99)),
        "ode_failures": int(fj.get("failures", -1)),
        "parameters_at_bound": int(sum(bool(x) for x in fj.get("at_bound", []))),
        "n_starts": int(fj.get("n_starts", 0)),
        "n_near_best": int(fj.get("n_near_best", 0)),
        "reduced_chi2": float(fj.get("red", float("nan"))),
    }
    checks["converged"] = checks["solver_status"] > 0 and checks["ode_failures"] == 0
    checks["near_best_all_starts"] = checks["n_near_best"] == checks["n_starts"] and checks["n_starts"] > 0

    # The frozen selection must still name M5 and must not have used R6.
    selection = read_json(os.path.join(root, SELECTION_FROZEN))
    checks["frozen_preferred_model"] = selection["preferred"]
    checks["frozen_selection_rule"] = selection["rule"]
    checks["frozen_r6_used_for_selection"] = bool(selection["r6_used_for_selection"])
    checks["model_comparison_sha256_matches"] = (
        sha256_file(os.path.join(root, "outputs/tables/model_comparison.csv")) == selection["model_comparison_sha256"])
    checks["candidate_parameters_sha256_matches"] = (
        sha256_file(os.path.join(root, CANDIDATE_PARAMETERS)) == selection["candidate_parameters_sha256"])

    # Level 1 frozen record: R6 held out, parameter CSV hash unchanged.
    if os.path.exists(os.path.join(root, LEVEL1_FROZEN)):
        l1 = read_json(os.path.join(root, LEVEL1_FROZEN))
        checks["level1_holdout"] = l1.get("holdout")
        checks["level1_training_runs"] = l1.get("training_runs")
        checks["r6_in_level1_training"] = "R6" in (l1.get("training_runs") or [])
        checks["level1_parameters_sha256_matches"] = (
            sha256_file(os.path.join(root, "outputs/tables/level1_parameters.csv")) == l1["parameters_csv_sha256"])

    if model == PREFERRED_MODEL:
        # The frozen candidate table must reproduce fit_M5.json exactly.
        cand = pd.read_csv(os.path.join(root, CANDIDATE_PARAMETERS))
        row = cand[cand.model == model].set_index("parameter")["value"]
        checks["candidate_table_matches_fit_json"] = bool(
            all(abs(float(row[n]) - float(v)) <= 1e-12 * max(1.0, abs(float(v))) for n, v in zip(names, theta)))
        checks["selection_is_M5"] = selection["preferred"] == PREFERRED_MODEL
        checks["rule_is_D24"] = selection["rule"] == SELECTION_RULE
    return dict(model=model, theta=theta, names=list(names), source=checks["source_path"],
                parameter_set_id=parameter_set_id(model, theta, checks["source_path"]),
                checks=checks, fit_json=fj)


def verify_model_policy(root="."):
    """Run every frozen-policy check and return a JSON-able policy record."""
    pol = load_parameter_set(PREFERRED_MODEL, root)
    ch = pol["checks"]
    required = {
        "frozen_preferred_model_is_M5": ch.get("frozen_preferred_model") == PREFERRED_MODEL,
        "selection_rule_is_D24": ch.get("frozen_selection_rule") == SELECTION_RULE,
        "r6_not_used_for_selection": ch.get("frozen_r6_used_for_selection") is False,
        "model_comparison_hash_matches": bool(ch.get("model_comparison_sha256_matches")),
        "candidate_parameters_hash_matches": bool(ch.get("candidate_parameters_sha256_matches")),
        "level1_parameters_hash_matches": bool(ch.get("level1_parameters_sha256_matches")),
        "level1_holdout_is_R6": ch.get("level1_holdout") == F.HOLDOUT,
        "r6_not_in_training": ch.get("r6_in_level1_training") is False,
        "candidate_table_matches_fit_M5": bool(ch.get("candidate_table_matches_fit_json")),
        "fit_M5_converged": bool(ch.get("converged")),
        "fit_M5_no_parameter_at_bound": ch.get("parameters_at_bound") == 0,
        "fit_M5_all_starts_near_best": bool(ch.get("near_best_all_starts")),
    }
    alternatives = {}
    for v in ROBUST_ALTERNATIVES:
        a = load_parameter_set(v, root)
        alternatives[v] = dict(parameter_set_id=a["parameter_set_id"], source=a["source"],
                               theta=[float(x) for x in a["theta"]],
                               converged=a["checks"]["converged"],
                               parameters_at_bound=a["checks"]["parameters_at_bound"])
    return dict(
        preferred_model=PREFERRED_MODEL,
        preferred_parameter_set_id=pol["parameter_set_id"],
        preferred_source=pol["source"],
        preferred_theta={n: float(v) for n, v in zip(pol["names"], pol["theta"])},
        selection_rule=SELECTION_RULE,
        heldout_run=F.HOLDOUT,
        training_runs=list(F.TRAIN),
        excluded_primary=list(F.EXCLUDED_PRIMARY),
        robust_alternatives=alternatives,
        checks=required,
        all_checks_passed=all(required.values()),
        note="Level 3 uses the frozen M5 parameter set unchanged. R6 is never used for "
             "fitting, tuning or optimisation; M2/M6 are comparison models only.")


# ------------------------------------------------------------------ steam curve
def steam_intensity(ethanol_g_per_l):
    """Steam intensity from the brief's design curve, with explicit range handling.

    Linear interpolation only *inside* the supplied 7-14 % v/v wash range.  Outside it
    nothing is extrapolated: ``steam_kg_per_L`` is NaN and ``in_range`` is False, so the
    caller cannot accidentally price a batch the curve does not cover.
    """
    P = float(ethanol_g_per_l)
    wash = P * WASH_PCT_PER_G_PER_L
    row = dict(ethanol_g_per_l=P, wash_pct_vv=wash, steam_kg_per_L=float("nan"),
               steam_curve_in_range=False, steam_curve_status="")
    if not np.isfinite(P) or P <= 0.0:
        row["steam_curve_status"] = "no_ethanol"
        return row
    if wash < STEAM_CURVE_MIN_PCT:
        row["steam_curve_status"] = "below_7_pct_vv"
        return row
    if wash > STEAM_CURVE_MAX_PCT:
        row["steam_curve_status"] = "above_14_pct_vv"
        return row
    row["steam_kg_per_L"] = float(np.interp(wash, STEAM_CURVE_WASH_PCT, STEAM_CURVE_KG_PER_L))
    row["steam_curve_in_range"] = True
    row["steam_curve_status"] = "in_range"
    return row


# ------------------------------------------------------------------ simulation
def time_grid(horizon_h=HORIZON_PRIMARY_H, step_h=TIME_STEP_H):
    n = int(round(float(horizon_h) / float(step_h)))
    return np.linspace(0.0, n * float(step_h), n + 1)


def completion_time(t, S, threshold=TRS_COMPLETION_G_PER_L):
    """First downward crossing of ``threshold``, linearly interpolated.  None if not reached."""
    t = np.asarray(t, float)
    S = np.asarray(S, float)
    below = np.where(S <= threshold)[0]
    if below.size == 0:
        return None
    i = int(below[0])
    if i == 0:
        return None                     # already at/below threshold at t = 0: not a batch end
    s_hi, s_lo = float(S[i - 1]), float(S[i])
    if not np.isfinite(s_hi) or not np.isfinite(s_lo) or s_hi <= s_lo:
        return float(t[i])
    return float(np.interp(threshold, [s_lo, s_hi], [t[i], t[i - 1]]))


def simulate_batch(model, theta, T, S0, X0=X0_DEFAULT_G_PER_L,
                   horizon_h=HORIZON_PRIMARY_H, step_h=TIME_STEP_H):
    """Integrate one plant scenario with the frozen Level 2 model structure.

    Returns a dict with the full trajectory summary, the completion time and a status.
    On solver failure the status is ``simulation_failed`` and every derived quantity is NaN.
    """
    t = time_grid(horizon_h, step_h)
    out = dict(model=model, temperature_c=float(T), s0_g_per_l=float(S0), x0_g_per_l=float(X0),
               horizon_h=float(horizon_h), time_step_h=float(step_h),
               simulation_status="ok", completion_time_h=float("nan"), final_trs_g_per_l=float("nan"),
               final_ethanol_g_per_l=float("nan"), final_biomass_g_per_l=float("nan"),
               final_co2_g_per_l=float("nan"), batch_completed=False,
               max_ethanol_in_trajectory_g_per_l=float("nan"))
    try:
        sim = M.simulate(model, float(T), float(S0), float(X0), t, theta)
    except ValueError:
        sim = None
        out["simulation_status"] = "temperature_outside_model_range"
    if sim is None:
        if out["simulation_status"] == "ok":
            out["simulation_status"] = "integration_failed"
        out["feasibility_status"] = STATUS_FAILED
        return out

    tc = completion_time(t, sim[:, 1])
    out["max_ethanol_in_trajectory_g_per_l"] = float(np.max(sim[:, 2]))
    if tc is None:
        out["final_trs_g_per_l"] = float(sim[-1, 1])
        out["final_ethanol_g_per_l"] = float(sim[-1, 2])
        out["final_biomass_g_per_l"] = float(sim[-1, 0])
        out["final_co2_g_per_l"] = float(sim[-1, 3])
        out["completion_time_h"] = float("nan")
        out["feasibility_status"] = STATUS_UNFINISHED
        return out

    out["completion_time_h"] = tc
    out["batch_completed"] = True
    out["final_trs_g_per_l"] = float(np.interp(tc, t, sim[:, 1]))
    out["final_ethanol_g_per_l"] = float(np.interp(tc, t, sim[:, 2]))
    out["final_biomass_g_per_l"] = float(np.interp(tc, t, sim[:, 0]))
    out["final_co2_g_per_l"] = float(np.interp(tc, t, sim[:, 3]))
    out["feasibility_status"] = STATUS_COMPLETED     # refined by economics (steam-curve test)
    return out


# ------------------------------------------------------------------ economics
def economics(S0, ethanol_end_g_per_l, completion_h):
    """Full plant economics for ONE completed batch.  NaN everywhere if it cannot be priced.

    All quantities are per fermenter (170 m3) for one batch.  See the module docstring for
    the derivation and the 1 g/L = 1 kg/m3 unit identity that makes the mass sums direct.
    """
    P = float(ethanol_end_g_per_l)
    S0 = float(S0)
    tc = float(completion_h)
    out = dict(wash_pct_vv=float("nan"), steam_kg_per_L=float("nan"), steam_curve_in_range=False,
               steam_curve_status="not_evaluated",
               sugar_charged_kg=float("nan"), sugar_cost_inr=float("nan"),
               ethanol_mass_kg=float("nan"), ethanol_volume_l=float("nan"),
               ethanol_revenue_inr=float("nan"), steam_mass_kg=float("nan"),
               steam_cost_inr=float("nan"), batch_margin_inr=float("nan"),
               turnaround_h=TURNAROUND_H, cycle_time_h=float("nan"),
               margin_per_cycle_inr_per_h=float("nan"), margin_24h_equivalent_inr_per_day=float("nan"))
    if not (np.isfinite(P) and np.isfinite(S0) and np.isfinite(tc)):
        return out

    steam = steam_intensity(P)
    out.update(wash_pct_vv=steam["wash_pct_vv"], steam_kg_per_L=steam["steam_kg_per_L"],
               steam_curve_in_range=steam["steam_curve_in_range"],
               steam_curve_status=steam["steam_curve_status"])

    sugar_kg = S0 * V_WORKING_M3                   # g/L * m3 = kg
    ethanol_kg = P * V_WORKING_M3                  # g/L * m3 = kg
    ethanol_l = ethanol_kg / RHO_ETHANOL_KG_PER_L
    revenue = ethanol_l * PRICE_ETHANOL_INR_PER_L
    sugar_cost = sugar_kg * COST_SUGAR_INR_PER_KG
    out.update(sugar_charged_kg=sugar_kg, sugar_cost_inr=sugar_cost,
               ethanol_mass_kg=ethanol_kg, ethanol_volume_l=ethanol_l, ethanol_revenue_inr=revenue)
    cycle = tc + TURNAROUND_H
    out["cycle_time_h"] = cycle
    if not steam["steam_curve_in_range"]:
        # Completed, but the supplied curve does not cover this wash strength: no steam cost,
        # therefore no margin.  The batch is not called profitable.
        return out
    steam_kg = steam["steam_kg_per_L"] * ethanol_l
    steam_cost = steam_kg * STEAM_COST_INR_PER_KG
    margin = revenue - sugar_cost - steam_cost
    out.update(steam_mass_kg=steam_kg, steam_cost_inr=steam_cost, batch_margin_inr=margin,
               margin_per_cycle_inr_per_h=margin / cycle,
               margin_24h_equivalent_inr_per_day=24.0 * margin / cycle)
    return out


def evaluate(model, theta, T, S0, X0=X0_DEFAULT_G_PER_L, horizon_h=HORIZON_PRIMARY_H,
             step_h=TIME_STEP_H):
    """One complete, traceable scenario record: simulation + completion + economics + flags."""
    sim = simulate_batch(model, theta, T, S0, X0, horizon_h, step_h)
    rec = dict(sim)
    if sim["batch_completed"]:
        econ = economics(S0, sim["final_ethanol_g_per_l"], sim["completion_time_h"])
    else:
        # An unfinished or failed batch gets no economics at all -- not a margin at a
        # stopping time, and not a "zero" that could be mistaken for a real value.
        econ = economics(float(S0), float("nan"), float("nan"))
        econ["steam_curve_status"] = "not_evaluated_unfinished_or_failed"
    rec.update(econ)

    if sim["feasibility_status"] == STATUS_COMPLETED and not econ["steam_curve_in_range"]:
        rec["feasibility_status"] = STATUS_OUT_OF_CURVE
    rec["priced"] = bool(np.isfinite(rec["margin_per_cycle_inr_per_h"]))
    rec["completed_and_feasible"] = rec["feasibility_status"] == STATUS_COMPLETED
    rec["within_steam_curve"] = bool(econ["steam_curve_in_range"])
    rec["in_operating_window"] = bool(S0_MIN_G_PER_L - 1e-9 <= S0 <= S0_MAX_G_PER_L + 1e-9
                                      and T_MIN_C - 1e-9 <= T <= T_MAX_C + 1e-9)
    rec["in_model_temperature_range"] = bool(30.0 - 1e-9 <= T <= 37.0 + 1e-9)
    rec["temperature_interpolated"] = bool(abs(T - 30.0) > 1e-9 and abs(T - 34.0) > 1e-9
                                           and abs(T - 37.0) > 1e-9)
    rec["beyond_48h_data"] = bool(np.isfinite(rec["completion_time_h"]) and rec["completion_time_h"] > DATA_END_H)
    rec["beyond_48h_data_at_horizon_end"] = bool(horizon_h > DATA_END_H)
    return rec


# ------------------------------------------------------------------ uncertainty draws
def draw_parameter_ensemble(fit_json, model, n_draws, seed, max_tries_factor=20):
    """Gaussian draws from the linearised covariance, truncated at the parameter bounds.

    Method (documented in the report): the fit covariance from fit_{model}.json is used as
    the local covariance of the estimate; draws outside the fitted bounds are rejected.
    This is a *parameter* uncertainty propagation conditional on the model structure.  It
    is not predictive uncertainty: measurement error, model inadequacy and run-to-run
    variability are not represented by these draws.
    """
    names, _start, lo, hi, *_ = M.spec(model)
    theta0 = np.array(fit_json["theta"], float)
    cov = np.array([[np.nan if x is None else x for x in row] for row in fit_json["cov"]], float)
    ok = np.isfinite(np.diag(cov))
    if not ok.any():
        return np.zeros((0, len(theta0))), 0.0
    sub = cov[np.ix_(ok, ok)]
    # Symmetrise and add a small jitter so the Cholesky factor always exists.
    sub = 0.5 * (sub + sub.T)
    jitter = 1e-12 * max(1.0, float(np.max(np.abs(np.diag(sub)))))
    L = np.linalg.cholesky(sub + jitter * np.eye(int(ok.sum())))
    rng = np.random.default_rng(seed)
    draws, tries = [], 0
    while len(draws) < n_draws and tries < max_tries_factor * n_draws:
        tries += 1
        th = theta0.copy()
        th[ok] += L @ rng.standard_normal(int(ok.sum()))
        if np.all(th >= lo) and np.all(th <= hi):
            draws.append(th)
    accept = len(draws) / tries if tries else 0.0
    return np.array(draws), float(accept)


def summarise(values):
    """Robust summary of a draw ensemble; NaN-aware and honest about undefined draws."""
    v = np.asarray(values, float)
    finite = np.isfinite(v)
    if not finite.any():
        return dict(n=len(v), n_defined=0, fraction_defined=0.0, median=float("nan"),
                    p2_5=float("nan"), p97_5=float("nan"), minimum=float("nan"), maximum=float("nan"))
    w = v[finite]
    return dict(n=len(v), n_defined=int(finite.sum()), fraction_defined=float(finite.mean()),
                median=float(np.median(w)), p2_5=float(np.percentile(w, 2.5)),
                p97_5=float(np.percentile(w, 97.5)), minimum=float(w.min()), maximum=float(w.max()))


# ------------------------------------------------------------------ scenario helper
def scenario_definitions():
    """The two temperature scenarios the brief requires, plus the brief's 37 C / 260 g/L case."""
    return OrderedDict([
        ("normal_33_37", dict(label="Normal / October constraint: 33-37 C", t_min=T_MIN_C, t_max=T_MAX_C)),
        ("warm_min_36", dict(label="Cooling water +3 C: minimum 36 C (36-37 C)", t_min=T_MIN_WARM_C, t_max=T_MAX_C)),
    ])


BRIEF_Q5_POINT = dict(s0_g_per_l=260.0, temperature_c=37.0,
                      description="Brief Q5: 37 C with 260 g/L initial TRS")
