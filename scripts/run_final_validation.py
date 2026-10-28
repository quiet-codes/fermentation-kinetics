#!/usr/bin/env python
"""Run the complete final validation chain and record every command, exit code and result.

Stages (in order):
    1  environment                       record interpreter and package versions
    2  git_status                        what is committed vs generated
    3  raw_checksums                     SHA-256 of the original CSVs
    4  level3_workflow                   src/level3_optimize.py --stage all
    5  level3_report                     src/make_level3_report.py
    6  consistency_audit                 src/level3_consistency_audit.py
    7  submission_snapshot_provisional   scripts/build_submission.py (before the ZIP exists)
    8  submission_verification           scripts/verify_submission.py
    9  full_test_suite                   python -m pytest -q
    10 submission_snapshot_final         rebuild so the snapshot carries the validation record
    11 submission_verification_final     re-verify the rebuilt snapshot
    12 create_final_zip                  scripts/create_final_zip.py
    13 zip_integrity_and_listing         independent re-check of the archive
    14 final_handoff_summary             collate the handoff record

Each stage's stdout/stderr is written to ``outputs/audits/level3/final_validation_logs/``.
The run continues through the stages (so one failure does not hide the rest) but the overall
status is failed if any stage returned non-zero.  A note records explicitly that this is
Linux/sandbox validation and that actual Windows execution has not been performed.

Usage (project root):  python scripts/run_final_validation.py
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, "outputs", "audits", "level3")
LOGS = os.path.join(AUD, "final_validation_logs")
PY = sys.executable
ZIP_NAME = "fermentation_kinetics_final_submission.zip"

# Stages 1-9 run *before* the submission snapshot is built, so the snapshot (and therefore the
# archive) carries this run's validation record.  Stages 10-13 build and validate the archive
# afterwards; those cannot be inside the archive they produce.
PRE_STAGES = [
    ("01_environment", "environment", None),
    ("02_git_status", "git_status", None),
    ("03_raw_checksums", "raw_checksums", None),
    ("04_level3_workflow", "level3_workflow", None),
    ("05_level3_report", "level3_report", None),
    ("06_consistency_audit", "consistency_audit", None),
    ("07_submission_snapshot_provisional", "submission_snapshot_provisional", None),
    ("08_submission_verification", "submission_verification", None),
    ("09_full_test_suite", "full_test_suite", None),
]

POST_STAGES = [
    ("10_submission_snapshot_final", "submission_snapshot_final", None),
    ("11_submission_verification_final", "submission_verification_final", None),
    ("12_create_final_zip", "create_final_zip", None),
    ("13_zip_integrity_and_listing", "zip_integrity_and_listing", None),
]

STAGES = PRE_STAGES + POST_STAGES


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_command(label, cmd, log_path, cwd=None):
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    with open(log_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"$ {' '.join(cmd)}\n# cwd: {cwd or ROOT}\n# exit: {proc.returncode}\n\n{out}")
    return dict(label=label, command=cmd, cwd=os.path.relpath(cwd or ROOT, ROOT).replace(os.sep, "/"),
                exit_code=proc.returncode, runtime_s=round(time.time() - t0, 2),
                log=os.path.relpath(log_path, ROOT).replace(os.sep, "/"),
                tail=out.strip().splitlines()[-3:] if out.strip() else [])


def shell_capture(label, cmd_str, log_path, cwd=None):
    """Run a shell pipeline (for sha256sum -c) and capture it."""
    t0 = time.time()
    proc = subprocess.run(cmd_str, shell=True, cwd=cwd or ROOT, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    with open(log_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"$ {cmd_str}\n# cwd: {cwd or ROOT}\n# exit: {proc.returncode}\n\n{out}")
    return dict(label=label, command=[cmd_str], cwd=os.path.relpath(cwd or ROOT, ROOT).replace(os.sep, "/"),
                exit_code=proc.returncode, runtime_s=round(time.time() - t0, 2),
                log=os.path.relpath(log_path, ROOT).replace(os.sep, "/"),
                tail=out.strip().splitlines()[-3:] if out.strip() else [])


def _write_validation(records, all_passed, phase, note):
    """Write outputs/audits/level3/final_validation.json from the records so far."""
    validation = dict(
        created=time.strftime("%Y-%m-%d %H:%M:%S"),
        phase=phase,
        status=("passed" if all_passed else "failed") if all_passed is not None else "in_progress",
        all_passed=all_passed,
        command_count=len(records),
        stages=records,
        actual_windows_execution=False,
        original_assignment_pdf_available=False,
        environment=dict(platform=platform.platform(), python=platform.python_version()),
        note=note,
    )
    with open(os.path.join(AUD, "final_validation.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(validation, fh, indent=2)
        fh.write("\n")
    return validation


def main():
    os.makedirs(LOGS, exist_ok=True)
    stale = os.path.join(ROOT, ZIP_NAME)
    if os.path.exists(stale):
        os.remove(stale)
        print(f"removed the previous archive so the chain rebuilds it from scratch")
    records = []
    print("Final validation chain")
    print("=" * 78)

    for phase, batch in (("pre-archive", PRE_STAGES), ("post-archive", POST_STAGES)):
      if phase == "post-archive":
        # Record the completed pre-archive checks first, so the snapshot built next carries them.
        _write_validation(records, all_passed=all(r["exit_code"] == 0 for r in records),
                          phase="pre-archive",
                          note="Pre-archive checks. The submission snapshot and the archive are built after "
                               "this record is written, so the archive contains this run's results. The "
                               "authoritative record of the full run, including archive validation, is the "
                               "workspace copy of this file and final_zip_validation.json.")
        print("-" * 78)
      for idx, (slug, kind, _) in enumerate(batch, start=1):
        log = os.path.join(LOGS, f"{slug}.log")
        print(f"[{idx}/{len(STAGES)}] {kind} ...", end=" ", flush=True)

        if kind == "environment":
            def env_script():
                import importlib
                lines = [f"python {platform.python_version()}",
                         f"platform {platform.platform()}",
                         f"executable {sys.executable}",
                         f"cpu_count {os.cpu_count()}"]
                for mod in ("numpy", "scipy", "pandas", "matplotlib", "pytest"):
                    try:
                        m = importlib.import_module(mod)
                        lines.append(f"{mod} {getattr(m, '__version__', 'unknown')}")
                    except Exception as exc:      # noqa: BLE001
                        lines.append(f"{mod} MISSING ({exc})")
                return lines
            body = "\n".join(env_script())
            with open(log, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("# environment\n" + body + "\n")
            rec = dict(label=kind, command=["python", "-c", "<environment report>"], exit_code=0,
                       runtime_s=0.0, log=os.path.relpath(log, ROOT).replace(os.sep, "/"),
                       tail=body.splitlines()[:4])
        elif kind == "git_status":
            rec = run_command(kind, ["git", "status", "--short", "--branch"], log)
        elif kind == "raw_checksums":
            rec = shell_capture(kind, "sha256sum -c CHECKSUMS.sha256",
                                log, cwd=os.path.join(ROOT, "data", "raw"))
        elif kind == "level3_workflow":
            rec = run_command(kind, [PY, "src/level3_optimize.py", "--stage", "all", "--n-draws", "200"], log)
        elif kind == "level3_report":
            rec = run_command(kind, [PY, "src/make_level3_report.py"], log)
        elif kind == "consistency_audit":
            rec = run_command(kind, [PY, "src/level3_consistency_audit.py"], log)
        elif kind == "submission_snapshot_provisional":
            rec = run_command(kind, [PY, "scripts/build_submission.py"], log)
        elif kind == "submission_verification":
            rec = run_command(kind, [PY, "scripts/verify_submission.py", "--zip", ZIP_NAME], log)
        elif kind == "full_test_suite":
            rec = run_command(kind, [PY, "-m", "pytest", "-q"], log)
        elif kind == "submission_snapshot_final":
            rec = run_command(kind, [PY, "scripts/build_submission.py"], log)
        elif kind == "submission_verification_final":
            rec = run_command(kind, [PY, "scripts/verify_submission.py", "--zip", ZIP_NAME], log)
        elif kind == "create_final_zip":
            rec = run_command(kind, [PY, "scripts/create_final_zip.py"], log)
        elif kind == "zip_integrity_and_listing":
            zip_path = os.path.join(ROOT, ZIP_NAME)
            lines = []
            ok = os.path.exists(zip_path)
            if ok:
                import zipfile
                with zipfile.ZipFile(zip_path) as zf:
                    bad = zf.testzip()
                    names = zf.namelist()
                lines = [f"exists: {ok}", f"bytes: {os.path.getsize(zip_path)}",
                         f"sha256: {sha256(zip_path)}", f"entries: {len(names)}",
                         f"testzip: {bad}"]
                ok = bad is None
            else:
                lines = ["archive missing"]
            with open(log, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("# independent archive check\n" + "\n".join(lines) + "\n")
            rec = dict(label=kind, command=["python", "-c", "<zip integrity check>"],
                       exit_code=0 if ok else 1, runtime_s=0.0,
                       log=os.path.relpath(log, ROOT).replace(os.sep, "/"), tail=lines)
        elif kind == "final_handoff_summary":
            rec = dict(label=kind, command=[PY, "scripts/run_final_validation.py", "--handoff-only"],
                       exit_code=0, runtime_s=0.0, log="", tail=["handoff collated below"])
        else:                                  # pragma: no cover - defensive
            raise RuntimeError(f"unknown stage {kind}")

        records.append(rec)
        print(f"exit {rec['exit_code']} ({rec['runtime_s']}s)")

    all_passed = all(r["exit_code"] == 0 for r in records)

    # ---- collate the handoff summary ------------------------------------------------
    def load(rel):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as fh:
            return json.load(fh) if rel.endswith(".json") else fh.read()

    answers = load("outputs/audits/level3/level3_answers.json") or {}
    zipinfo = load("outputs/audits/level3/final_zip_validation.json") or {}
    consistency = load("outputs/audits/level3/consistency_report.json") or {}
    submission = load("outputs/audits/level3/submission_verification.json") or {}
    policy = load("outputs/audits/level3/model_policy.json") or {}

    a1 = (answers.get("Q1_best_normal_33_37") or {}).get("answer", {})
    a2 = (answers.get("Q2_best_min36") or {}).get("answer", {})

    handoff = dict(
        created=time.strftime("%Y-%m-%d %H:%M:%S"),
        archive=dict(name=ZIP_NAME, path=os.path.join(ROOT, ZIP_NAME),
                     bytes=zipinfo.get("zip_bytes"), sha256=zipinfo.get("zip_sha256"),
                     entries=zipinfo.get("file_count"), testzip_bad_member=zipinfo.get("testzip_bad_member"),
                     validated=zipinfo.get("passed")),
        snapshot=dict(files=submission.get("snapshot_files"), verification_passed=submission.get("passed"),
                      build_passed=(load("outputs/audits/level3/submission_build_report.json") or {}).get("passed")),
        results=dict(
            normal_scenario=a1, warm_scenario=a2,
            model_policy_all_checks_passed=policy.get("all_checks_passed"),
            frozen_model=(load("outputs/tables/model_selection_frozen.json") or {}).get("preferred"),
            consistency_audit=dict(n_checks=consistency.get("n_checks"), n_passed=consistency.get("n_passed"),
                                   passed=consistency.get("passed")),
        ),
        execution=dict(platform=platform.platform(), python=platform.python_version(),
                       stages=[dict(label=r["label"], command=r["command"], exit_code=r["exit_code"],
                                    runtime_s=r["runtime_s"], log=r["log"]) for r in records],
                       command_count=len(records)),
        actual_windows_execution=False,
        original_assignment_pdf_available=False,
        limitations=[
            "All checks in this run are Linux/sandbox checks. Actual Windows execution of the test suite and the "
            "reproduction scripts has not been performed and remains pending.",
            "The original assignment PDF is unavailable; docs/assignment_brief.md is the governing specification and "
            "PDF-only requirements cannot be confirmed.",
            "Level 3 recommendations are model predictions from the frozen M5 fit, not plant-validated optima.",
            "Parameter uncertainty is quantified; predictive uncertainty (measurement error, model inadequacy, "
            "run-to-run variability) is not.",
        ],
    )
    with open(os.path.join(AUD, "final_handoff_summary.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(handoff, fh, indent=2)
        fh.write("\n")

    _write_validation(records, all_passed=all_passed, phase="full",
                      note="Linux/sandbox validation only. Stages 1-9 were recorded before the submission "
                           "snapshot was built, so the archive contains this run's checks; stages 10-13 build "
                           "and validate the archive itself and can only exist outside it. Actual Windows "
                           "execution has not been performed.")

    print("=" * 78)
    print(f"{sum(1 for r in records if r['exit_code'] == 0)}/{len(records)} stages passed -- "
          f"{'PASSED' if all_passed else 'FAILED'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
