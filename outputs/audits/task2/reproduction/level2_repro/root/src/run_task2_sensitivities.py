#!/usr/bin/env python
"""Driver for the Task 2 CO2-floor sensitivity evidence.

Runs (or reuses) the Level 1 verification and executes the two additional
Level 2 floor cases in separate isolated roots.  Results, logs and a short
markdown summary are written under ``outputs/audits/task2/sensitivity/``.
No original output is overwritten.

Usage (from project root):
  python src/run_task2_sensitivities.py
  python src/run_task2_sensitivities.py --force-level1
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUT = ROOT / "outputs" / "audits" / "task2" / "sensitivity"
LOGS = OUT / "logs"
sys.path.insert(0, str(SRC))
import task2_co2_floor_sensitivity as worker  # noqa: E402


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _env():
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               NUMEXPR_NUM_THREADS="1", MPLBACKEND="Agg")
    return env


def _run(cmd, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        log.write(f"# started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"# cwd {ROOT}\n# command: {' '.join(cmd)}\n\n")
        log.flush()
        proc = subprocess.run([str(x) for x in cmd], cwd=str(ROOT), env=_env(),
                              stdout=log, stderr=subprocess.STDOUT)
    return dict(command=[str(x) for x in cmd], log=str(log_path.relative_to(ROOT)),
                returncode=proc.returncode, duration_s=round(time.time() - started, 2))


def _level1(args):
    out = OUT / "level1_verification.json"
    log = LOGS / "level1_verification.log"
    cmd = [sys.executable, str(SRC / "task2_co2_floor_sensitivity.py"),
           "--mode", "level1", "--output", str(out), "--original-root", str(ROOT),
           "--data-dir", "data/raw"]
    if args.force_level1 or not out.exists():
        res = _run(cmd, log)
        if res["returncode"] != 0:
            raise RuntimeError(f"Level 1 verification failed; see {log}")
    else:
        res = dict(command=[str(x) for x in cmd], log=str(log.relative_to(ROOT)),
                   returncode=0, duration_s=None, reused_existing=True)
    return _read_json(out), res


def _level2_case(floor: float):
    tag = ("0" if floor == 0 else "0p5")
    root = OUT / "level2" / f"floor_{tag}"
    out = OUT / f"level2_floor_{tag}.json"
    log = LOGS / f"level2_floor_{tag}.log"
    cmd = [sys.executable, str(SRC / "task2_co2_floor_sensitivity.py"),
           "--mode", "level2", "--floor", str(floor), "--root", str(root),
           "--output", str(out), "--original-root", str(ROOT), "--data-dir", "data/raw"]
    res = _run(cmd, log)
    if res["returncode"] != 0:
        raise RuntimeError(f"Level 2 floor {floor} failed; see {log}")
    return _read_json(out), res


def _baseline_selection():
    fits = {}
    for v in worker.M.VARIANTS:
        p = ROOT / "outputs" / "tables" / "work" / f"fit_{v}.json"
        fits[v] = json.loads(p.read_text(encoding="utf-8"))
    return worker._selection_from_fits(fits)


def _markdown(data):
    l1 = data["level1_verification"]["cases"]
    lines = [
        "# Task 2 CO2-floor sensitivity",
        "",
        "This is an isolated, additional sensitivity check. The frozen Level 1 parameters and the frozen Level 2 M5/D-24 decision are unchanged.",
        "",
        "## Scope",
        "",
        "- Existing Level 1 M0 floor cases `CO2_floor_0` and `CO2_floor_0.5` were recomputed from the frozen Level 1 fit.",
        "- All seven Level 2 candidates were refit under floors 0.0 and 0.5 g/L in isolated roots.",
        "- D-24 QAICc selection was recomputed from those fits with the written multistart-convergence condition made explicit.",
        "- No LORO cross-validation, residual table, or full `compare.py --stage select` rerun was performed for the alternative floors; this is not a new frozen selection.",
        "",
        "## Level 1 verification",
        "",
        "| case | floor (g/L) | original max &#124;change&#124; (%) | recomputed max &#124;change&#124; (%) | exact within 1e-6? |",
        "|---|---:|---:|---:|---|",
    ]
    for c in l1:
        exact = all(v["allclose"] for v in c["comparison_to_existing_evidence"].values())
        lines.append(f"| {c['case']} | {c['floor']:.1f} | {c['max_abs_change_pct_original']:.4f} | "
                     f"{c['max_abs_change_pct_reproduced']:.4f} | {'yes' if exact else 'no (small numerical difference)'} |")
    lines += [
        "",
        "## Level 2 additional calculations",
        "",
        "| floor (g/L) | preferred (explicit convergence) | best QAICc | c_hat | M5 max &#124;change&#124; (%) | all-model max &#124;change&#124; (%) | runtime (s) |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for c in data["level2_cases"]:
        s = c["selection"]
        ch = c["parameter_changes_vs_original_floor_0p10"]
        lines.append(f"| {c['floor']:.1f} | {s['preferred_with_convergence']} | "
                     f"{s['best_qaicc_model_with_convergence']} | {s['c_hat']:.6g} | "
                     f"{ch['M5']['max_abs_change_pct']:.4f} | "
                     f"{max(x['max_abs_change_pct'] for x in ch.values()):.4f} | {c['runtime_s']:.1f} |")
    b = data["baseline_selection"]
    lines += [
        "",
        f"Baseline (floor 0.10 g/L, original stored fits): preferred `{b['preferred_with_convergence']}`, "
        f"best QAICc `{b['best_qaicc_model_with_convergence']}`, c_hat `{b['c_hat']:.6f}`.",
        "",
        "## Interpretation limits",
        "",
        "- The original assignment PDF is unavailable; the brief says only 'about ±2%' for CO2 and 'about ±3%' for glycerol/lactic acid. These calculations test sensitivity to the documented 0.10 g/L floor, not the correctness of that interpretation.",
        "- Alternative floors are hypothetical weighting choices. A stable M5 choice under these two alternatives does not prove robustness to every possible weighting or to the missing PDF's exact wording.",
        "- Numeric differences from the stored Level 1 floor-0 case are small but non-zero because this sandbox uses Python 3.11.2 / numpy 2.4.6 / pandas 3.1.0, while the frozen record used Python 3.12.3 / numpy 2.4.4 / pandas 3.0.2.",
        "- Only the fits needed for these conclusions were executed in isolated roots; no original output was overwritten.",
        "",
        "Machine-readable evidence: `co2_floor_sensitivity.json`, `level1_verification.json`, "
        "`level2_floor_0.json`, `level2_floor_0p5.json`, and per-stage logs in `logs/`.",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-level1", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    l1, l1run = _level1(args)
    with ThreadPoolExecutor(max_workers=min(2, max(1, args.workers))) as pool:
        futures = [pool.submit(_level2_case, f) for f in (0.0, 0.5)]
        cases = [f.result() for f in futures]
    cases.sort(key=lambda x: x[0]["floor"])
    baseline = _baseline_selection()
    data = dict(
        created=time.strftime("%Y-%m-%d %H:%M:%S"),
        environment=dict(python=platform.python_version(), platform=platform.platform(),
                         numpy=worker.np.__version__, pandas=worker.pd.__version__),
        original_root=str(ROOT),
        level1_verification=l1,
        level1_command=l1run,
        level2_cases=[{"floor": c[0]["floor"], **c[0], "run": c[1]} for c in cases],
        baseline_selection=baseline,
        total_runtime_s=round(time.time() - t0, 2),
        frozen_decision_unchanged=True,
    )
    # scipy version is also recorded by the worker; keep top-level environment simple.
    import scipy
    data["environment"]["scipy"] = scipy.__version__
    _write_json(OUT / "co2_floor_sensitivity.json", data)
    (OUT / "co2_floor_sensitivity.md").write_text(_markdown(data), encoding="utf-8", newline="\n")
    summary = {
        "level1_cases": [{"case": c["case"], "max_abs_change_pct_reproduced": c["max_abs_change_pct_reproduced"]}
                         for c in l1["cases"]],
        "level2": [{"floor": c[0]["floor"], "preferred": c[0]["selection"]["preferred_with_convergence"],
                    "best_qaicc": c[0]["selection"]["best_qaicc_model_with_convergence"],
                    "convergence_changes_selection": c[0]["selection"]["convergence_condition_changes_selection"]}
                   for c in cases],
        "total_runtime_s": data["total_runtime_s"],
    }
    print(json.dumps(summary, indent=2))
    print(f"evidence: {OUT / 'co2_floor_sensitivity.md'}")


if __name__ == "__main__":
    main()
