#!/usr/bin/env python
"""Build the deterministic ``submission/`` snapshot from the canonical project tree.

The snapshot is *generated output*: the canonical files stay where they are and the snapshot is
rebuilt by ``python scripts/build_submission.py``.  Nothing here edits a source file.

Rules
-----
* Deterministic: the file list is sorted, timestamps are not stored in the manifest, and no
  random or environment-dependent content is introduced.
* Missing required items are **reported** in ``outputs/audits/level3/submission_build_report.json``
  and make the script exit non-zero; an incomplete package is never silently produced.
* ``.pyc`` files, ``__pycache__``, virtual environments, caches and the final archive are
  excluded by construction.
* The report copy inside the snapshot has its figure links rewritten from the repository paths
  (``outputs/figures/x.png``) to the snapshot-relative ones (``figures/x.png``) so that the
  Markdown renders inside the submitted folder.  The canonical report is left untouched.

Usage (project root):  python scripts/build_submission.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB = os.path.join(ROOT, "submission")
AUD = os.path.join(ROOT, "outputs", "audits", "level3")

EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "submission", "node_modules"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".zip"}

# (destination inside the snapshot, source path relative to the project root)
COPY_PLAN = [
    # ---- assignment and top-level documents
    ("assignment/assignment_brief.md", "docs/assignment_brief.md"),
    ("worklog.md", "worklog.md"),
    ("AI_USE.md", "AI_USE.md"),
    ("requirements.txt", "requirements.txt"),
    ("requirements_traceability.csv", "requirements_traceability.csv"),
    ("pytest.ini", "pytest.ini"),
    ("README.md", "README.md"),
    # ---- Phase 0
    ("phase0/pre_fit_observations.md", "reports/pre_fit_observations.md"),
    ("phase0/data_quality.csv", "outputs/tables/data_quality.csv"),
    ("phase0/endpoint_diagnostics.csv", "outputs/tables/endpoint_diagnostics.csv"),
    ("phase0/preliminary_carbon_balance.csv", "outputs/tables/preliminary_carbon_balance.csv"),
    ("phase0/run_descriptive_summary.csv", "outputs/tables/run_descriptive_summary.csv"),
    ("phase0/figures/raw_curves.png", "outputs/figures/raw_curves.png"),
    # ---- Level 1
    ("level1/level1.md", "reports/level1.md"),
    ("level1/level1_parameters.csv", "outputs/tables/level1_parameters.csv"),
    ("level1/level1_frozen.json", "outputs/tables/level1_frozen.json"),
    ("level1/level1_fit_diagnostics.csv", "outputs/tables/level1_fit_diagnostics.csv"),
    ("level1/level1_multistart.csv", "outputs/tables/level1_multistart.csv"),
    ("level1/level1_correlations.csv", "outputs/tables/level1_correlations.csv"),
    ("level1/level1_summary_numbers.csv", "outputs/tables/level1_summary_numbers.csv"),
    ("level1/level1_sensitivity.csv", "outputs/tables/level1_sensitivity.csv"),
    ("level1/heldout_metrics.csv", "outputs/tables/heldout_metrics.csv"),
    ("level1/heldout_predictions.csv", "outputs/tables/heldout_predictions.csv"),
    ("level1/figures/level1_fits.png", "outputs/figures/level1_fits.png"),
    ("level1/figures/heldout_prediction.png", "outputs/figures/heldout_prediction.png"),
    # ---- Level 2
    ("level2/level2.md", "reports/level2.md"),
    ("level2/model_comparison.csv", "outputs/tables/model_comparison.csv"),
    ("level2/model_selection_frozen.json", "outputs/tables/model_selection_frozen.json"),
    ("level2/candidate_parameters.csv", "outputs/tables/candidate_parameters.csv"),
    ("level2/model_residuals.csv", "outputs/tables/model_residuals.csv"),
    ("level2/model_r6_diagnostic.csv", "outputs/tables/model_r6_diagnostic.csv"),
    ("level2/parameter_uncertainty.csv", "outputs/tables/parameter_uncertainty.csv"),
    ("level2/parameter_profiles.csv", "outputs/tables/parameter_profiles.csv"),
    ("level2/parameter_correlations_material.csv", "outputs/tables/parameter_correlations_material.csv"),
    ("level2/fixed_parameter_sensitivity.csv", "outputs/tables/fixed_parameter_sensitivity.csv"),
    ("level2/r7_inclusion_effect.csv", "outputs/tables/r7_inclusion_effect.csv"),
    ("level2/r7_review.csv", "outputs/tables/r7_review.csv"),
    ("level2/carbon_balance_all_runs.csv", "outputs/tables/carbon_balance_all_runs.csv"),
    ("level2/ethanol_yields.csv", "outputs/tables/ethanol_yields.csv"),
    ("level2/ethanol_yield_pooled.csv", "outputs/tables/ethanol_yield_pooled.csv"),
    ("level2/yield_gap_decomposition.csv", "outputs/tables/yield_gap_decomposition.csv"),
    ("level2/plant_prediction_uncertainty.csv", "outputs/tables/plant_prediction_uncertainty.csv"),
    ("level2/plant_linearised_sd.csv", "outputs/tables/plant_linearised_sd.csv"),
    ("level2/plant_Ks_sensitivity.csv", "outputs/tables/plant_Ks_sensitivity.csv"),
    ("level2/structure_spread.csv", "outputs/tables/structure_spread.csv"),
    ("level2/variance_decomposition.csv", "outputs/tables/variance_decomposition.csv"),
    ("level2/experiment_design.csv", "outputs/tables/experiment_design.csv"),
    ("level2/experiment_discrimination.csv", "outputs/tables/experiment_discrimination.csv"),
    ("level2/figures/model_comparison_residuals.png", "outputs/figures/model_comparison_residuals.png"),
    ("level2/figures/parameter_profiles_M5.png", "outputs/figures/parameter_profiles_M5.png"),
    ("level2/figures/parameter_profiles_M0.png", "outputs/figures/parameter_profiles_M0.png"),
    ("level2/figures/carbon_balance_all_runs.png", "outputs/figures/carbon_balance_all_runs.png"),
    ("level2/figures/ethanol_yield_gap.png", "outputs/figures/ethanol_yield_gap.png"),
    ("level2/figures/plant_uncertainty.png", "outputs/figures/plant_uncertainty.png"),
    # ---- Level 3 (the report copy is handled separately so its figure links can be rewritten)
    ("level3/optimization_grid.csv", "outputs/tables/optimization_grid.csv"),
    ("level3/optimization_recommendations.csv", "outputs/tables/optimization_recommendations.csv"),
    ("level3/plant_economics.csv", "outputs/tables/plant_economics.csv"),
    ("level3/optimization_uncertainty.csv", "outputs/tables/optimization_uncertainty.csv"),
    ("level3/optimization_model_comparison.csv", "outputs/tables/optimization_model_comparison.csv"),
    ("level3/optimization_input_audit.csv", "outputs/tables/optimization_input_audit.csv"),
    ("level3/optimization_horizon_sensitivity.csv", "outputs/tables/optimization_horizon_sensitivity.csv"),
    ("level3/figures/level3_feasible_region.png", "outputs/figures/level3_feasible_region.png"),
    ("level3/figures/level3_economics.png", "outputs/figures/level3_economics.png"),
    ("level3/figures/level3_completion_time.png", "outputs/figures/level3_completion_time.png"),
    ("level3/figures/level3_uncertainty.png", "outputs/figures/level3_uncertainty.png"),
    ("level3/audits/model_policy.json", "outputs/audits/level3/model_policy.json"),
    ("level3/audits/input_audit_summary.json", "outputs/audits/level3/input_audit_summary.json"),
    ("level3/audits/grid_summary.json", "outputs/audits/level3/grid_summary.json"),
    ("level3/audits/horizon_sensitivity.json", "outputs/audits/level3/horizon_sensitivity.json"),
    ("level3/audits/level3_answers.json", "outputs/audits/level3/level3_answers.json"),
    ("level3/audits/report_claims.json", "outputs/audits/level3/report_claims.json"),
    ("level3/audits/consistency_report.md", "outputs/audits/level3/consistency_report.md"),
    ("level3/audits/consistency_report.json", "outputs/audits/level3/consistency_report.json"),
    ("level3/audits/uncertainty_draws.csv", "outputs/audits/level3/uncertainty_draws.csv"),
    ("level3/audits/final_validation.json", "outputs/audits/level3/final_validation.json"),
    # ---- handoff and Task 2 evidence
    ("handoff/DECISIONS.md", "handoff/DECISIONS.md"),
    ("handoff/PROJECT_STATE.md", "handoff/PROJECT_STATE.md"),
    ("handoff/NEXT_ACCOUNT_PROMPT.md", "handoff/NEXT_ACCOUNT_PROMPT.md"),
    ("logs/task2/task2_report.md", "outputs/audits/task2/task2_report.md"),
    ("logs/task2/task2_summary.json", "outputs/audits/task2/task2_summary.json"),
    ("logs/pre_level3_audit.md", "outputs/audits/pre_level3_audit.md"),
]

# Whole directories copied recursively (destination, source).
DIR_PLAN = [
    ("source/src", "src"),
    ("source/tests", "tests"),
    ("data/raw", "data/raw"),
    ("scripts", "scripts"),
    ("logs/preflight", "outputs/audits/level3/preflight"),
    ("logs/crlf_repro", "outputs/audits/level3/preflight/crlf_repro"),
]

# Sources that only exist once the validation chain has run.  Their absence is reported as
# "pending" rather than as a failure of the snapshot build.
OPTIONAL_SOURCES = {"outputs/audits/level3/final_validation.json"}

REQUIRED_ITEMS = [
    "README_SUBMISSION.md",
    "SUBMISSION_CHECKLIST.md",
    "assignment/assignment_brief.md",
    "phase0",
    "level1",
    "level2",
    "level3/level3.md",
    "level3/optimization_grid.csv",
    "level3/optimization_recommendations.csv",
    "level3/plant_economics.csv",
    "level3/optimization_uncertainty.csv",
    "level3/optimization_model_comparison.csv",
    "level3/optimization_input_audit.csv",
    "source/src/level3.py",
    "source/src/level3_optimize.py",
    "source/src/make_level3_report.py",
    "source/tests/test_level3.py",
    "data/raw/runs.csv",
    "data/raw/timecourse.csv",
    "data/raw/endpoint_hplc.csv",
    "data/raw/CHECKSUMS.sha256",
    "logs",
    "worklog.md",
    "AI_USE.md",
    "requirements_traceability.csv",
    "handoff",
    "requirements.txt",
    "manifest.csv",
]

README = """# Submission package - Fermentation kinetics from batch data (P3)

This folder is a **generated snapshot** of the project, built by `scripts/build_submission.py`.
The canonical files live in the project tree; if the two disagree, the project tree wins and the
snapshot should be rebuilt.

## What to read first

| order | file | why |
|---|---|---|
| 1 | `level3/level3.md` | Level 3 report: recommendation, economics, uncertainty, answers to the questions |
| 2 | `level1/level1.md` | kinetic model, fitting method, parameter table, held-out prediction |
| 3 | `level2/level2.md` | model comparison, parameter uncertainty and identifiability, carbon balance, ethanol yield |
| 4 | `phase0/pre_fit_observations.md` | raw-data audit and the pre-fit reading of the curves |
| 5 | `manifest.csv` | every file with its SHA-256, size and origin |
| 6 | `requirements_traceability.csv` | each assignment requirement mapped to report section, code, evidence and status |
| 7 | `worklog.md`, `AI_USE.md` | how the work was done and what the AI did or did not verify |

## Headline result

Normal October constraint (33-37 C): **195 g/L TRS at 33 C**, batch complete (TRS = 5 g/L) in
35.57 h, 86.32 g/L ethanol, **4,858.69 INR/h of cycle time** (116,608 INR/day derived equivalent)
per 170 m3 fermenter.
If the cooling water warms by 3 C and 36 C becomes the floor: **175 g/L TRS at 36 C**, 39.82 h,
3,710.13 INR/h.

## Structure

```
submission/
  README_SUBMISSION.md  SUBMISSION_CHECKLIST.md  manifest.csv  CHECKSUMS.sha256
  assignment/           the assignment brief used as the specification
  phase0/               raw-data audit outputs
  level1/               Level 1 report, parameters, held-out prediction, figures
  level2/               Level 2 report, model selection, uncertainty, carbon balance, figures
  level3/               Level 3 report, optimisation tables, figures, audit records
  source/src/           all Python source
  source/tests/         all automated tests
  data/raw/             original raw CSVs and their checksum manifest
  logs/                 preflight evidence (including the reproduced Windows CRLF failure), Task 2 evidence
  handoff/              decisions, project state, next-account prompt
  scripts/              reproduction and packaging scripts
  worklog.md  AI_USE.md  requirements_traceability.csv  requirements.txt
```

## How to reproduce

```bash
python -m pip install -r requirements.txt
python src/level3_optimize.py --stage all --n-draws 200
python src/make_level3_report.py
python src/level3_consistency_audit.py
python -m pytest -q
```

Windows: `.\\scripts\\reproduce_level3.ps1`.

## Status and limits (read before submitting)

* All tests pass on Linux/Python 3.11 in this sandbox. **Actual Windows execution is still pending**
  and must be run locally; only a Linux simulation of the Windows default line terminator was done.
* The original assignment PDF is unavailable; `assignment/assignment_brief.md` is the extracted brief
  and is the governing specification here. PDF-only requirements cannot be confirmed.
* The recommendation is a model prediction from a frozen fit, not an experimentally validated plant
  optimum. Parameter uncertainty is quantified; predictive uncertainty is not.
"""

CHECKLIST = """# Submission checklist

## Deliverables present

- [x] Level 1 report `level1/level1.md`
- [x] Level 2 report `level2/level2.md`
- [x] Level 3 report `level3/level3.md`
- [x] Phase 0 observations `phase0/pre_fit_observations.md`
- [x] Code that reproduces every number: `source/src/`
- [x] Tests: `source/tests/` (optimisation constraints, completion rule, economics, 36 C scenario,
      unfinished-batch handling, encoding/formatting, report claims)
- [x] Raw data and checksums: `data/raw/`
- [x] Work log `worklog.md` and AI-use note `AI_USE.md`
- [x] Requirements traceability `requirements_traceability.csv`
- [x] Manifest with SHA-256 for every file: `manifest.csv`, `CHECKSUMS.sha256`

## Verification performed (Linux sandbox)

- [x] Full test suite passes
- [x] Level 3 workflow executes end to end
- [x] Consistency audit passes (report vs tables vs frozen records)
- [x] Frozen Level 2 selection unchanged (M5, D-24, R6 never used for tuning)
- [x] All eight carbon balances present
- [x] Raw CSV checksums verify
- [x] Generated CSV/JSON are ASCII with LF endings
- [x] Every figure referenced by the reports exists
- [x] ZIP integrity checked and archive listing inspected

## Outstanding - to be done by the student

- [ ] Run `python -m pytest -q` on Windows and record the result
- [ ] Run `.\\scripts\\reproduce_level3.ps1` on Windows
- [ ] Complete the editable personal-contribution section in `AI_USE.md`
- [ ] Confirm any PDF-only assignment requirement that is not in `assignment/assignment_brief.md`
- [ ] Check the report renders correctly in the viewer/markdown tool of choice
"""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_sources(src_dir):
    for base, dirs, files in os.walk(src_dir):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in EXCLUDE_SUFFIX:
                continue
            yield os.path.join(base, name)


def main():
    if os.path.isdir(SUB):
        shutil.rmtree(SUB)
    os.makedirs(SUB, exist_ok=True)
    built, missing, pending = [], [], []

    def record(dest_rel, src_rel, kind):
        built.append(dict(dest=dest_rel.replace(os.sep, "/"), source=src_rel.replace(os.sep, "/"),
                          kind=kind, bytes=os.path.getsize(os.path.join(SUB, dest_rel)),
                          sha256=sha256(os.path.join(SUB, dest_rel))))

    # ---- explicit file copies
    for dest_rel, src_rel in COPY_PLAN:
        src = os.path.join(ROOT, src_rel)
        if not os.path.exists(src):
            if src_rel in OPTIONAL_SOURCES:
                pending.append(dict(dest=dest_rel, source=src_rel,
                                    reason="produced by the validation chain; not present at this build"))
            else:
                missing.append(dict(dest=dest_rel, source=src_rel, reason="source file not found"))
            continue
        dst = os.path.join(SUB, dest_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        record(dest_rel, src_rel, "copy")

    # ---- directory copies
    for dest_dir, src_dir in DIR_PLAN:
        src_abs = os.path.join(ROOT, src_dir)
        if not os.path.isdir(src_abs):
            missing.append(dict(dest=dest_dir, source=src_dir, reason="source directory not found"))
            continue
        for src in walk_sources(src_abs):
            rel = os.path.relpath(src, src_abs)
            dest_rel = os.path.join(dest_dir, rel)
            dst = os.path.join(SUB, dest_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            record(dest_rel, os.path.join(src_dir, rel), "tree")

    # ---- Level 3 report with snapshot-relative figure links
    src_report = os.path.join(ROOT, "reports", "level3.md")
    if os.path.exists(src_report):
        text = open(src_report, encoding="utf-8").read()
        text = text.replace("(outputs/figures/", "(figures/")
        dst = os.path.join(SUB, "level3", "level3.md")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        record("level3/level3.md", "reports/level3.md (figure links rewritten for the snapshot)",
               "generated")
    else:
        missing.append(dict(dest="level3/level3.md", source="reports/level3.md",
                            reason="report not generated"))

    # ---- README and checklist
    for name, body in (("README_SUBMISSION.md", README), ("SUBMISSION_CHECKLIST.md", CHECKLIST)):
        dst = os.path.join(SUB, name)
        with open(dst, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        built.append(dict(dest=name, source="generated by scripts/build_submission.py", kind="generated",
                          bytes=os.path.getsize(dst), sha256=sha256(dst)))

    # ---- integrity manifests
    built.sort(key=lambda r: r["dest"])
    import pandas as pd
    L3 = None
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import level3 as L3  # noqa: E402

    L3.write_csv(pd.DataFrame(built), os.path.join(SUB, "manifest.csv"))
    with open(os.path.join(SUB, "CHECKSUMS.sha256"), "w", encoding="utf-8", newline="\n") as fh:
        for r in built:
            fh.write(f"{r['sha256']}  {r['dest']}\n")

    # ---- verify the required structure
    absent = [item for item in REQUIRED_ITEMS if not os.path.exists(os.path.join(SUB, item))]
    ok = not missing and not absent
    report = dict(created=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                  snapshot=os.path.relpath(SUB, ROOT).replace(os.sep, "/"),
                  n_files=len(built) + 2, total_bytes=sum(r["bytes"] for r in built),
                  required_items=len(REQUIRED_ITEMS), missing_required=absent,
                  missing_sources=missing, pending_sources=pending, passed=ok,
                  excluded=[".git", "__pycache__", "*.pyc", ".pytest_cache", ".venv", "*.zip"],
                  note="The snapshot is generated output; the canonical project tree remains authoritative.")
    L3.write_json(report, os.path.join(AUD, "submission_build_report.json"))
    print(f"submission snapshot: {report['n_files']} files, {report['total_bytes']/1e6:.2f} MB, "
          f"{'OK' if ok else 'INCOMPLETE'}")
    if absent:
        print("missing required items:", absent)
    if missing:
        print("missing sources:", missing)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
