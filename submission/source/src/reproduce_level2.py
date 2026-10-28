#!/usr/bin/env python
"""Reproduce the available Level 2 stages in an isolated root.

The script copies the preserved project inputs into a fresh directory, runs the
Phase 0 / Level 1 prerequisite verification stages, all available Level 2
fitting, selection, uncertainty, plant, carbon-balance and report stages, then
runs a consistency audit against the original outputs.  The original
``outputs/``, ``reports/`` and raw CSVs are never written.

Usage (from project root):
  python src/reproduce_level2.py --mode all
  python src/reproduce_level2.py --mode audit --run-id level2_repro
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "audits" / "task2" / "reproduction"
sys.path.insert(0, str(ROOT / "src"))
import task2_consistency_audit as audit  # noqa: E402


@dataclass
class Stage:
    name: str
    cmd: list[str]
    deps: tuple[str, ...] = ()
    priority: int = 50
    outputs: tuple[str, ...] = ()
    note: str = ""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _copytree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))


def _copy_file(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def setup_root(original: Path, root: Path, run_dir: Path) -> Path:
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"reproduction root is not empty: {root}; use a new --run-id or --overwrite")
    for rel in ("outputs/tables/work", "outputs/figures", "reports", "data/raw", "src", "docs", "logs"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    # Preserved inputs / baseline outputs.  Stages overwrite only their own files.
    _copytree(original / "outputs" / "tables", root / "outputs" / "tables")
    _copytree(original / "outputs" / "figures", root / "outputs" / "figures")
    _copytree(original / "reports", root / "reports")
    _copytree(original / "data" / "raw", root / "data" / "raw")
    _copytree(original / "src", root / "src")
    _copytree(original / "docs", root / "docs")
    if (original / "handoff").exists():
        _copytree(original / "handoff", root / "handoff")
    for name in ("README.md", "CLAUDE.md", "AI_USE.md", "worklog.md", "requirements.txt"):
        _copy_file(original / name, root / name)
    manifest = {}
    for base in ("outputs", "reports", "data/raw", "src", "docs"):
        for p in sorted((root / base).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                manifest[p.relative_to(root).as_posix()] = _sha256(p)
    manifest_path = root / "logs" / "baseline_manifest.json"
    _write_json(manifest_path, manifest)
    (run_dir / "logs" / "stage_logs").mkdir(parents=True, exist_ok=True)
    return manifest_path


def stage_list(root: Path, py: str):
    s = str(root / "src")
    d = ["--data-dir", "data/raw", "--root", "."]
    def cmd(script, *extra):
        return [py, f"{s}/{script}", *extra]
    return [
        Stage("compare_fit", cmd("compare.py", "--stage", "fit", *d), (), 1,
              tuple(f"outputs/tables/work/fit_{v}.json" for v in ("M0", "M1", "M2", "M3", "M4", "M5", "M6")),
              "Seven Level 2 candidate fits (training runs only)."),
        Stage("compare_loro", cmd("compare.py", "--stage", "loro", *d), ("compare_fit",), 2,
              tuple(f"outputs/tables/work/loro_{v}.json" for v in ("M0", "M1", "M2", "M3", "M4", "M5", "M6")),
              "Leave-one-run-out cross-validation."),
        Stage("uncertainty_profile_M5", cmd("uncertainty.py", "--stage", "profile", "--models", "M5", *d),
              ("compare_fit",), 3, ("outputs/tables/work/profile_M5.json",)),
        Stage("uncertainty_profile_M0", cmd("uncertainty.py", "--stage", "profile", "--models", "M0", *d),
              ("compare_fit",), 4, ("outputs/tables/work/profile_M0.json",)),
        Stage("uncertainty_fixedgrid", cmd("uncertainty.py", "--stage", "fixedgrid", "--models", "M5,M0", *d),
              ("compare_fit",), 5, ("outputs/tables/work/fixedgrid_M5.json", "outputs/tables/work/fixedgrid_M0.json")),
        Stage("uncertainty_r7", cmd("uncertainty.py", "--stage", "r7", "--models", "M5,M0", *d),
              ("compare_fit",), 6, ("outputs/tables/work/r7_M5.json", "outputs/tables/work/r7_M0.json")),
        Stage("compare_select", cmd("compare.py", "--stage", "select", *d), ("compare_loro",), 7,
              ("outputs/tables/model_comparison.csv", "outputs/tables/candidate_parameters.csv",
               "outputs/tables/model_residuals.csv", "outputs/tables/model_selection_frozen.json",
               "outputs/figures/model_comparison_residuals.png"),
              "D-24 selection and frozen hashes in the isolated root."),
        Stage("compare_r6diag", cmd("compare.py", "--stage", "r6diag", *d), ("compare_select",), 8,
              ("outputs/tables/model_r6_diagnostic.csv",),
              "Hash check before R6 is loaded; out-of-fit diagnostic only."),
        Stage("uncertainty_assemble", cmd("uncertainty.py", "--stage", "assemble", "--models", "M5,M0", *d),
              ("compare_select", "compare_loro", "uncertainty_profile_M5", "uncertainty_profile_M0",
               "uncertainty_fixedgrid", "uncertainty_r7"), 9,
              ("outputs/tables/parameter_uncertainty.csv", "outputs/tables/parameter_profiles.csv",
               "outputs/tables/fixed_parameter_sensitivity.csv", "outputs/tables/r7_inclusion_effect.csv",
               "outputs/tables/parameter_correlations_material.csv",
               "outputs/figures/parameter_profiles_M5.png", "outputs/figures/parameter_profiles_M0.png")),
        Stage("carbon_balance", cmd("carbon_balance.py", *d), (), 15,
              ("outputs/tables/carbon_balance_all_runs.csv", "outputs/tables/ethanol_yields.csv",
               "outputs/tables/ethanol_yield_pooled.csv", "outputs/tables/yield_gap_decomposition.csv",
               "outputs/tables/r7_review.csv", "outputs/figures/carbon_balance_all_runs.png",
               "outputs/figures/ethanol_yield_gap.png")),
        Stage("phase0", cmd("phase0_inspect.py", *d), (), 20,
              ("outputs/tables/data_quality.csv", "outputs/tables/endpoint_diagnostics.csv",
               "outputs/tables/preliminary_carbon_balance.csv", "outputs/tables/run_descriptive_summary.csv",
               "outputs/figures/raw_curves.png"),
              "Phase 0 prerequisite verification (no fitting)."),
        Stage("level1_predict", cmd("fit.py", "--stage", "predict", *d), (), 21,
              ("outputs/tables/heldout_metrics.csv", "outputs/tables/heldout_predictions.csv",
               "outputs/figures/heldout_prediction.png"),
              "Level 1 prediction only; frozen Level 1 fit is intentionally NOT refit."),
        Stage("level1_summary", cmd("level1_summary.py", *d), ("level1_predict",), 22,
              ("outputs/tables/level1_correlations.csv", "outputs/tables/level1_summary_numbers.csv")),
        Stage("report_level1", cmd("make_level1_report.py", "reports/level1.md"), ("level1_summary",), 23,
              ("reports/level1.md",)),
        Stage("plant_predict", cmd("plant_uncertainty.py", "--stage", "predict", *d),
              ("compare_select", "uncertainty_profile_M5", "uncertainty_profile_M0"), 24,
              ("outputs/tables/plant_prediction_uncertainty.csv", "outputs/tables/structure_spread.csv")),
        Stage("plant_design", cmd("plant_uncertainty.py", "--stage", "design", *d),
              ("compare_select", "compare_fit"), 25,
              ("outputs/tables/plant_linearised_sd.csv", "outputs/tables/variance_decomposition.csv",
               "outputs/tables/experiment_design.csv")),
        Stage("plant_ksens", cmd("plant_uncertainty.py", "--stage", "ksens", *d),
              ("compare_select", "uncertainty_fixedgrid"), 26, ("outputs/tables/plant_Ks_sensitivity.csv",)),
        Stage("plant_discriminate", cmd("plant_uncertainty.py", "--stage", "discriminate", *d),
              ("compare_select", "compare_fit"), 27, ("outputs/tables/experiment_discrimination.csv",)),
        Stage("plant_plot", cmd("plant_uncertainty.py", "--stage", "plot", *d),
              ("plant_predict", "plant_design", "compare_select"), 28, ("outputs/figures/plant_uncertainty.png",)),
        Stage("report_level2", cmd("make_level2_report.py", "reports/level2.md"),
              ("compare_r6diag", "uncertainty_assemble", "carbon_balance", "plant_plot", "plant_ksens",
               "plant_design", "plant_discriminate"), 29, ("reports/level2.md",)),
    ]


def _env():
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               NUMEXPR_NUM_THREADS="1", MPLBACKEND="Agg", PYTHONHASHSEED="0")
    return env


def run_stages(stages, root: Path, run_dir: Path, max_workers: int):
    stage_logs = run_dir / "logs" / "stage_logs"
    stage_logs.mkdir(parents=True, exist_ok=True)
    pending = {s.name: s for s in stages}
    order = {s.name: i for i, s in enumerate(stages)}
    done = {}
    running = {}
    ready = []
    failed = False
    while pending or running or ready:
        for name, st in list(pending.items()):
            if all(dep in done and done[dep]["returncode"] == 0 for dep in st.deps):
                heapq.heappush(ready, (st.priority, order[name], name))
                del pending[name]
        while ready and len(running) < max_workers and not failed:
            _, _, name = heapq.heappop(ready)
            st = next(s for s in stages if s.name == name)
            log_path = stage_logs / f"{name}.log"
            start = time.time()
            with log_path.open("w", encoding="utf-8", newline="\n") as log:
                log.write(f"# stage {name}\n# started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log.write(f"# cwd {root}\n# command: {' '.join(st.cmd)}\n")
                if st.note:
                    log.write(f"# note: {st.note}\n")
                log.write("\n")
                log.flush()
                proc = subprocess.Popen(st.cmd, cwd=str(root), env=_env(),
                                        stdout=log, stderr=subprocess.STDOUT)
            running[name] = (proc, log_path, start, st)
            print(f"[start] {name}", flush=True)
        progress = False
        for name, (proc, log_path, start, st) in list(running.items()):
            rc = proc.poll()
            if rc is None:
                continue
            progress = True
            duration = time.time() - start
            tail = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:])
            try:
                log_rel = str(log_path.relative_to(ROOT))
            except ValueError:
                log_rel = str(log_path)
            done[name] = dict(
                name=name, command=st.cmd, deps=list(st.deps), priority=st.priority,
                expected_outputs=list(st.outputs), note=st.note,
                log=log_rel, returncode=rc,
                duration_s=round(duration, 2), log_tail=tail,
                status="passed" if rc == 0 else "failed",
            )
            del running[name]
            print(f"[done] {name} rc={rc} {duration:.1f}s", flush=True)
            if rc != 0:
                failed = True
        if failed:
            ready.clear()
            # Preserve pending stages as skipped for the log.
            for name, st in list(pending.items()):
                done[name] = dict(name=name, command=st.cmd, deps=list(st.deps),
                                  priority=st.priority, expected_outputs=list(st.outputs),
                                  note=st.note, status="skipped",
                                  reason="stopped after a stage failure")
                del pending[name]
            pending.clear()
        if running:
            time.sleep(0.5)
        elif progress:
            # A dependency just became satisfied; loop again to populate ready.
            continue
        elif not ready and pending:
            # Dependency deadlock (should only happen after a failure).
            for name, st in pending.items():
                done[name] = dict(name=name, command=st.cmd, deps=list(st.deps),
                                  status="skipped", reason="unmet dependency or scheduler deadlock")
            pending.clear()
    return [done[s.name] for s in stages]


def changed_vs_baseline(root: Path, manifest_path: Path):
    base = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = []
    for rel, expected in base.items():
        p = root / rel
        if not p.exists() or _sha256(p) != expected:
            changed.append(rel)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["run", "audit", "all"], default="all")
    ap.add_argument("--original-root", default=str(ROOT))
    ap.add_argument("--run-id", default="level2_repro")
    ap.add_argument("--max-workers", type=int, default=2)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    original = Path(args.original_root).resolve()
    run_dir = (OUT / args.run_id).resolve()
    root = run_dir / "root"
    if args.mode in ("run", "all"):
        if run_dir.exists():
            if not args.overwrite:
                raise SystemExit(f"run directory exists: {run_dir}; use a new --run-id or --overwrite")
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = setup_root(original, root, run_dir)
        stages = stage_list(root, sys.executable)
        t0 = time.time()
        results = run_stages(stages, root, run_dir, args.max_workers)
        total = time.time() - t0
        failures = [r for r in results if r["status"] != "passed"]
        changed = changed_vs_baseline(root, manifest)
        log = dict(
            created=time.strftime("%Y-%m-%d %H:%M:%S"), run_id=args.run_id,
            original_root=str(original), reproduced_root=str(root),
            mode=args.mode, max_workers=args.max_workers,
            environment=dict(python=platform.python_version(), platform=platform.platform(),
                             numpy=audit.np.__version__, pandas=audit.pd.__version__,
                             scipy=__import__("scipy").__version__),
            stage_count=len(stages), passed=sum(1 for r in results if r["status"] == "passed"),
            failed=sum(1 for r in results if r["status"] == "failed"),
            skipped=sum(1 for r in results if r["status"] == "skipped"),
            total_runtime_s=round(total, 2), stages=results,
            baseline_manifest=str(manifest.relative_to(ROOT)),
            files_with_hash_changed_vs_copied_baseline=changed,
            level1_fit_and_sensitivity_not_refit=True,
            note="Level 1 frozen parameters were copied as inputs; fit.py --stage predict and level1_summary.py were run as prerequisite verification only.",
        )
        _write_json(run_dir / "reproduction_log.json", log)
        lines = [f"# Reproduction log ({args.run_id})", "",
                 f"- passed {log['passed']}/{log['stage_count']} stages in {total:.1f}s",
                 f"- original root: {original}", f"- reproduced root: {root}", ""]
        for r in results:
            lines.append(f"- {r['name']}: {r['status']} (rc={r.get('returncode')}, {r.get('duration_s')}s) log `{r.get('log')}`")
        _write_text(run_dir / "reproduction.log", "\n".join(lines) + "\n")
        if failures:
            print(json.dumps({"failed": [r["name"] for r in failures]}, indent=2), file=sys.stderr)
            raise SystemExit(1)
    else:
        log_path = run_dir / "reproduction_log.json"
        if not log_path.exists():
            raise SystemExit(f"missing {log_path}; run --mode run first")
        log = json.loads(log_path.read_text(encoding="utf-8"))
        results = log.get("stages", [])
        manifest = Path(log.get("baseline_manifest", "outputs/audits/task2/reproduction/" + args.run_id + "/root/logs/baseline_manifest.json"))
        manifest = ROOT / manifest if not manifest.is_absolute() else manifest
    if args.mode in ("audit", "all"):
        report = audit.run_audit(original, root, run_dir,
                                 stage_results=results, reproduction_log=str(run_dir / "reproduction_log.json"),
                                 baseline_manifest=str(manifest.relative_to(ROOT)))
        print(json.dumps({
            "run_id": args.run_id,
            "stages": len(results),
            "files_compared": report["file_comparison_summary"]["file_count"],
            "byte_equal": report["file_comparison_summary"]["byte_equal_count"],
            "csv_json_not_allclose": len(report["file_comparison_summary"]["csv_json_not_allclose"]),
            "d24_preferred": report["checks"]["d24_convergence_reproduced"]["recomputed_preferred"],
            "report": str(run_dir / "consistency_report.md"),
        }, indent=2))


if __name__ == "__main__":
    main()
