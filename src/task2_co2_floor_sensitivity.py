#!/usr/bin/env python
"""Task 2 CO2-floor sensitivity worker (isolated roots only).

This script performs ONLY the additional sensitivity calculations needed to
interpret the pre-Level-3 audit's CO2-floor findings.  It never writes to the
original ``outputs/`` tree.  Two modes are provided:

  level1  reproduce the two existing Level 1 M0 CO2-floor cases
          (``CO2_floor_0`` and ``CO2_floor_0.5``) from ``level1_sensitivity.csv``.
  level2  refit all seven Level 2 candidates under one alternative CO2 floor in
          an isolated root, then recompute the D-24 selection WITH the written
          multistart-convergence condition made explicit.

Usage (from project root):
  python src/task2_co2_floor_sensitivity.py --mode level1 --output <file.json>
  python src/task2_co2_floor_sensitivity.py --mode level2 --floor 0.0 \
      --root <isolated-root> --output <file.json>
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import compare as C  # noqa: E402
import fit  # noqa: E402
import kinetics as K  # noqa: E402
import models as M  # noqa: E402


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def _max_abs(a, b):
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        return None
    return float(np.max(np.abs(a - b)))


def _environment(floor=None):
    return dict(
        python=platform.python_version(),
        platform=platform.platform(),
        numpy=np.__version__,
        pandas=pd.__version__,
        scipy=__import__("scipy").__version__,
        co2_floor=floor,
        default_co2_floor=fit.CO2_FLOOR,
    )


# ------------------------------------------------------------------ Level 1 verification
def run_level1(args):
    original = Path(args.original_root).resolve()
    tdir = original / "outputs" / "tables"
    outdir = Path(args.output).resolve().parent
    outdir.mkdir(parents=True, exist_ok=True)
    fr, ptab, theta0, fixed = fit.load_frozen(str(tdir))
    se0 = ptab[ptab.status == "fitted"].set_index("parameter")["se_linear_scaled"]
    runs, tc = fit.read_raw(str((original / args.data_dir).resolve()))
    original_sens = pd.read_csv(tdir / "level1_sensitivity.csv")
    cases = [("CO2_floor_0", 0.0), ("CO2_floor_0.5", 0.5)]
    results = []
    all_rows = []
    for name, floor in cases:
        t0 = time.time()
        pol = fit.default_policy(fixed=fixed, co2_floor=floor)
        assert fit.HOLDOUT not in pol["train"]
        recs = fit.make_records(pol["train"], runs, tc)
        best, results_multistart, counter = fit.multistart(recs, pol, 8, args.level1_seed + 1, extra_starts=[theta0])
        th = best["theta"]
        n_obs = len(fit.residual_fn(recs, pol, dict(failures=0))(th))
        unc = fit.linear_uncertainty(best["res"], th, n_obs)
        rows = []
        for i, n in enumerate(K.PARAM_NAMES):
            rows.append(dict(
                case=name, parameter=n, value=float(th[i]), primary_value=float(theta0[i]),
                change_pct=float(100 * (th[i] - theta0[i]) / abs(theta0[i])),
                change_in_primary_se=float((th[i] - theta0[i]) / se0[n]) if np.isfinite(se0[n]) else None,
                at_bound=bool(fit.at_bound_mask(th)[i]), chi2=float(unc["chi2"]), n_residuals=int(n_obs),
                reduced_chi2=float(unc["red"]), ode_failures=int(counter["failures"])))
        df = pd.DataFrame(rows)
        all_rows.append(df)
        ref = original_sens[original_sens.case == name].reset_index(drop=True)
        merged = df.merge(ref, on=["case", "parameter"], suffixes=("_repro", "_original"))
        comparisons = {}
        for col in ("value", "primary_value", "change_pct", "change_in_primary_se", "chi2", "n_residuals", "reduced_chi2"):
            a = pd.to_numeric(merged[f"{col}_repro"], errors="coerce").to_numpy(float)
            b = pd.to_numeric(merged[f"{col}_original"], errors="coerce").to_numpy(float)
            comparisons[col] = dict(
                max_abs_diff=_max_abs(a, b),
                allclose=bool(np.allclose(a, b, rtol=1e-6, atol=1e-6, equal_nan=True)),
            )
        original_max_change = float(np.max(np.abs(ref["change_pct"].to_numpy(float))))
        repro_max_change = float(np.max(np.abs(df["change_pct"].to_numpy(float))))
        results.append(dict(
            case=name, floor=floor, chi2=float(unc["chi2"]), n_residuals=int(n_obs),
            reduced_chi2=float(unc["red"]), ode_failures=int(counter["failures"]),
            best_status=int(best["status"]), n_starts=len(results_multistart),
            max_abs_change_pct_original=original_max_change,
            max_abs_change_pct_reproduced=repro_max_change,
            comparison_to_existing_evidence=comparisons,
            runtime_s=round(time.time() - t0, 2),
        ))
        print(f"level1 {name}: chi2={unc['chi2']:.3f} max|change|={repro_max_change:.4f}% "
              f"({time.time() - t0:.1f}s)", flush=True)
    pd.concat(all_rows, ignore_index=True).to_csv(outdir / "level1_co2_floor_sensitivity_repro.csv", index=False, lineterminator='\n', encoding='utf-8')
    return dict(
        purpose="Verify the two existing Level 1 M0 CO2-floor sensitivity cases from level1_sensitivity.csv.",
        original_root=str(original), data_dir=args.data_dir, seed=args.level1_seed,
        multistart_seed=args.level1_seed + 1,
        multistart_starts=8, extra_starts=["frozen Level 1 optimum"],
        cases=results, environment=_environment(),
        note="This is a reproduction of the two existing cases; no new Level 1 decision is made.",
    )


# ------------------------------------------------------------------ Level 2 additional calculation
def _prepare_root(original: Path, root: Path, data_dir: str) -> None:
    for rel in ("outputs/tables/work", "outputs/figures", "data/raw", "logs"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    for name in ("level1_parameters.csv", "level1_frozen.json"):
        shutil.copy2(original / "outputs" / "tables" / name, root / "outputs" / "tables" / name)
    for p in (original / data_dir).glob("*.csv"):
        shutil.copy2(p, root / "data" / "raw" / p.name)


def _selection_from_fits(fits):
    n = fits["M5"]["n_obs"]
    c_hat = fits["M5"]["red"]
    metrics = {}
    for v, fj in fits.items():
        metrics[v] = dict(
            k=int(fj["k"]), chi2=float(fj["chi2"]), red=float(fj["red"]),
            qaicc=float(C.qaicc(fj["chi2"], c_hat, fj["k"], n)),
            params_at_bound=int(sum(fj["at_bound"])), ode_failures=int(fj["failures"]),
            n_near_best=int(fj["n_near_best"]), n_starts=int(fj["n_starts"]),
            status=int(fj["status"]),
        )
    def eligible(include_convergence):
        out = []
        for v, x in metrics.items():
            if x["params_at_bound"] != 0 or x["ode_failures"] != 0:
                continue
            if include_convergence and not (x["n_near_best"] == x["n_starts"] and x["status"] > 0):
                continue
            out.append(v)
        return out
    def choose(pool):
        best = min(pool, key=lambda v: metrics[v]["qaicc"])
        close = [v for v in pool if metrics[v]["qaicc"] - metrics[best]["qaicc"] <= 4
                 and metrics[v]["k"] < metrics[best]["k"]]
        return (min(close, key=lambda v: metrics[v]["k"]) if close else best), best
    with_conv = eligible(True)
    without_conv = eligible(False)
    pref_conv, best_conv = choose(with_conv) if with_conv else (None, None)
    pref_no_conv, best_no_conv = choose(without_conv) if without_conv else (None, None)
    return dict(
        n_obs=int(n), c_hat=float(c_hat), metrics=metrics,
        eligible_with_convergence=with_conv, eligible_without_convergence=without_conv,
        best_qaicc_model_with_convergence=best_conv,
        preferred_with_convergence=pref_conv,
        best_qaicc_model_without_convergence=best_no_conv,
        preferred_without_convergence=pref_no_conv,
        convergence_condition_changes_selection=bool(pref_conv != pref_no_conv),
    )


def run_level2(args):
    original = Path(args.original_root).resolve()
    root = Path(args.root).resolve()
    outpath = Path(args.output).resolve()
    _prepare_root(original, root, args.data_dir)
    fit.CO2_FLOOR = float(args.floor)
    t0 = time.time()
    ns = argparse.Namespace(root=str(root), data_dir=str(root / "data" / "raw"),
                            models=",".join(M.VARIANTS), n_lhs=args.n_lhs, seed=args.level2_seed)
    C.stage_fit(ns)
    fits = {}
    for v in M.VARIANTS:
        fits[v] = json.loads((root / "outputs" / "tables" / "work" / f"fit_{v}.json").read_text(encoding="utf-8"))
    selection = _selection_from_fits(fits)
    # Parameter changes relative to the original floor=0.10 fits.
    original_fits = {v: json.loads((original / "outputs" / "tables" / "work" / f"fit_{v}.json").read_text(encoding="utf-8"))
                     for v in M.VARIANTS}
    changes = {}
    for v in M.VARIANTS:
        a = np.array(fits[v]["theta"], float); b = np.array(original_fits[v]["theta"], float)
        rel = 100 * (a - b) / np.abs(b)
        changes[v] = dict(
            max_abs_change_pct=float(np.max(np.abs(rel))),
            mean_abs_change_pct=float(np.mean(np.abs(rel))),
            per_parameter_pct={n: float(x) for n, x in zip(fits[v]["names"], rel)},
        )
    result = dict(
        purpose="Additional Level 2 CO2-floor sensitivity: refit all seven candidates under an alternative floor and recompute D-24 with explicit multistart convergence.",
        floor=float(args.floor), original_floor=float(original_fits["M5"].get("co2_floor", 0.10)),
        root=str(root), original_root=str(original), data_dir=args.data_dir,
        seed=args.level2_seed, n_lhs=args.n_lhs, models=list(M.VARIANTS),
        runtime_s=round(time.time() - t0, 2),
        fits=dict(
            chi2={v: float(fits[v]["chi2"]) for v in M.VARIANTS},
            c_hat={v: float(fits[v]["red"]) for v in M.VARIANTS},
            n_near_best={v: f"{fits[v]['n_near_best']}/{fits[v]['n_starts']}" for v in M.VARIANTS},
            params_at_bound={v: int(sum(fits[v]["at_bound"])) for v in M.VARIANTS},
            ode_failures={v: int(fits[v]["failures"]) for v in M.VARIANTS},
        ),
        selection=selection,
        parameter_changes_vs_original_floor_0p10=changes,
        environment=_environment(float(args.floor)),
        note="This is an additional sensitivity calculation in an isolated root; it does NOT alter the frozen M5/D-24 decision.",
    )
    _json(outpath, result)
    print(f"level2 floor={args.floor}: preferred={selection['preferred_with_convergence']} "
          f"best_QAICc={selection['best_qaicc_model_with_convergence']} runtime={result['runtime_s']}s", flush=True)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["level1", "level2"])
    ap.add_argument("--floor", type=float, default=None)
    ap.add_argument("--root", default=None)
    ap.add_argument("--output", required=True)
    ap.add_argument("--original-root", default=".")
    ap.add_argument("--data-dir", default="data/raw")
    ap.add_argument("--level1-seed", type=int, default=20261026,
                    help="fit.py SEED; sensitivity uses SEED+1")
    ap.add_argument("--level2-seed", type=int, default=20261027,
                    help="compare.py --stage fit seed")
    ap.add_argument("--n-lhs", type=int, default=6)
    a = ap.parse_args()
    if a.mode == "level1":
        result = run_level1(a)
        _json(Path(a.output).resolve(), result)
    else:
        if a.floor is None or a.root is None:
            raise SystemExit("--mode level2 requires --floor and --root")
        run_level2(a)


if __name__ == "__main__":
    main()
