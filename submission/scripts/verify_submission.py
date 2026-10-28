#!/usr/bin/env python
"""Verify the generated ``submission/`` snapshot and (if present) the final archive.

Checks
------
1. every file listed in ``submission/manifest.csv`` exists with the recorded SHA-256 and size;
2. every required item of the mandated structure is present;
3. every figure referenced by a snapshot report exists inside the snapshot;
4. no forbidden content (``.pyc``, ``__pycache__``, virtual environments, caches, secrets, ``.zip``);
5. every raw data file still matches ``data/raw/CHECKSUMS.sha256``;
6. the frozen Level 2 decision and the frozen Level 1 parameter hash are unchanged;
7. the archive, when it exists, contains the required entries and passes ``zipfile.testzip``.

Writes ``outputs/audits/level3/submission_verification.json``.  Exit code 1 on any failure.

Usage (project root):  python scripts/verify_submission.py [--zip fermentation_kinetics_final_submission.zip]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB = os.path.join(ROOT, "submission")
AUD = os.path.join(ROOT, "outputs", "audits", "level3")
ZIP_DEFAULT = "fermentation_kinetics_final_submission.zip"

REQUIRED = [
    "README_SUBMISSION.md", "SUBMISSION_CHECKLIST.md", "assignment/assignment_brief.md",
    "phase0", "level1", "level2", "level3", "source/src", "source/tests", "data/raw", "logs",
    "worklog.md", "AI_USE.md", "requirements_traceability.csv", "handoff", "requirements.txt",
    "manifest.csv", "CHECKSUMS.sha256",
]
REQUIRED_LEVEL3 = [
    "level3/level3.md", "level3/optimization_grid.csv", "level3/optimization_recommendations.csv",
    "level3/plant_economics.csv", "level3/optimization_uncertainty.csv",
    "level3/optimization_model_comparison.csv", "level3/optimization_input_audit.csv",
    "level3/figures/level3_feasible_region.png", "level3/figures/level3_economics.png",
    "level3/figures/level3_completion_time.png", "level3/figures/level3_uncertainty.png",
]
FORBIDDEN_PATTERNS = [r"__pycache__", r"\.pyc$", r"\.pyo$", r"/\.venv/", r"/venv/", r"/\.pytest_cache/",
                      r"\.zip$", r"(^|/)\.env$", r"\.netrc$", r"id_rsa", r"\.git/"]
FIGURE_LINK = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

CHECKS = []


def check(cid, description, passed, detail=""):
    CHECKS.append(dict(id=cid, description=description, passed=bool(passed), detail=str(detail)))
    print(f"[{'PASS' if passed else 'FAIL'}] {cid} {description}" + (f" -- {detail}" if not passed else ""))
    return bool(passed)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=ZIP_DEFAULT)
    args = ap.parse_args(argv)

    print("Submission verification")
    print("=" * 78)

    check("S-01", "submission snapshot exists", os.path.isdir(SUB), SUB)
    manifest_path = os.path.join(SUB, "manifest.csv")
    check("S-02", "manifest.csv exists", os.path.exists(manifest_path))
    manifest = pd.read_csv(manifest_path) if os.path.exists(manifest_path) else pd.DataFrame()

    if len(manifest):
        bad, missing, size_bad = [], [], []
        for r in manifest.itertuples():
            p = os.path.join(SUB, r.dest)
            if not os.path.exists(p):
                missing.append(r.dest)
                continue
            if sha256(p) != r.sha256:
                bad.append(r.dest)
            if os.path.getsize(p) != r.bytes:
                size_bad.append(r.dest)
        check("S-03", "every manifest entry exists with the recorded SHA-256",
              not missing and not bad, f"missing={missing[:5]} hash_mismatch={bad[:5]}")
        check("S-04", "every manifest entry has the recorded size", not size_bad, size_bad[:5])
        check("S-05", "manifest covers source, data, reports, figures and logs",
              all(any(d.startswith(p) for d in manifest.dest) for p in
                  ("source/src/", "source/tests/", "data/raw/", "level1/", "level2/", "level3/", "logs/")))

    absent = [p for p in REQUIRED if not os.path.exists(os.path.join(SUB, p))]
    check("S-06", "required snapshot structure present", not absent, absent)
    absent3 = [p for p in REQUIRED_LEVEL3 if not os.path.exists(os.path.join(SUB, p))]
    check("S-07", "all required Level 3 deliverables present", not absent3, absent3)

    # figure references inside the snapshot reports must resolve inside the snapshot
    unresolved = []
    for name in ("level3/level3.md", "level1/level1.md", "level2/level2.md"):
        p = os.path.join(SUB, name)
        if not os.path.exists(p):
            continue
        base = os.path.dirname(p)
        for target in FIGURE_LINK.findall(open(p, encoding="utf-8").read()):
            if target.startswith("http"):
                continue
            if not os.path.exists(os.path.normpath(os.path.join(base, target))):
                unresolved.append(f"{name} -> {target}")
    check("S-08", "every figure referenced by a snapshot report exists in the snapshot",
          not unresolved, unresolved[:5])

    bad_names = []
    for base, dirs, files in os.walk(SUB):
        for f in files:
            rel = os.path.relpath(os.path.join(base, f), SUB).replace(os.sep, "/")
            if any(re.search(pat, rel) for pat in FORBIDDEN_PATTERNS):
                bad_names.append(rel)
    check("S-09", "no caches, virtual environments, secrets or nested archives", not bad_names, bad_names[:8])

    raw_ok, raw_detail = True, []
    with open(os.path.join(ROOT, "data", "raw", "CHECKSUMS.sha256"), encoding="utf-8") as fh:
        for line in fh.read().splitlines():
            if not line.strip():
                continue
            expected, name = line.split()
            snap = os.path.join(SUB, "data", "raw", name)
            src = os.path.join(ROOT, "data", "raw", name)
            if not os.path.exists(snap) or sha256(snap) != expected:
                raw_ok = False
                raw_detail.append(f"snapshot {name}")
            if sha256(src) != expected:
                raw_ok = False
                raw_detail.append(f"canonical {name}")
    check("S-10", "raw data match CHECKSUMS.sha256 in both the snapshot and the canonical tree",
          raw_ok, raw_detail)

    sel = json.load(open(os.path.join(SUB, "level2", "model_selection_frozen.json"), encoding="utf-8"))
    check("S-11", "snapshot frozen selection is still M5 under D-24 without R6",
          sel["preferred"] == "M5" and sel["rule"] == "D-24" and sel["r6_used_for_selection"] is False, sel)
    l1 = json.load(open(os.path.join(SUB, "level1", "level1_frozen.json"), encoding="utf-8"))
    check("S-12", "snapshot Level 1 frozen parameter hash still matches its parameter table",
          sha256(os.path.join(SUB, "level1", "level1_parameters.csv")) == l1["parameters_csv_sha256"])
    cb = pd.read_csv(os.path.join(SUB, "level2", "carbon_balance_all_runs.csv"))
    check("S-13", "snapshot contains all eight carbon balances", len(cb) == 8, len(cb))

    n_files = sum(len(f) for _, _, f in os.walk(SUB))
    print(f"snapshot file count: {n_files}")

    # ---- archive (optional at this stage)
    zip_path = args.zip if os.path.isabs(args.zip) else os.path.join(ROOT, args.zip)
    zip_info = dict(path=zip_path, exists=os.path.exists(zip_path))
    if os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            bad_member = zf.testzip()
            required_entries = ["submission/manifest.csv", "submission/README_SUBMISSION.md",
                                "submission/level3/level3.md", "src/level3.py", "src/level3_optimize.py",
                                "tests/test_level3.py", "data/raw/runs.csv", "worklog.md",
                                "AI_USE.md", "requirements_traceability.csv",
                                "reports/level3.md", "scripts/reproduce_level3.ps1"]
            missing_entries = [e for e in required_entries if e not in names]
            forbidden = [n for n in names if any(re.search(p, n) for p in FORBIDDEN_PATTERNS)]
        zip_info.update(bytes=os.path.getsize(zip_path), sha256=sha256(zip_path), file_count=len(names),
                        testzip_bad_member=bad_member, required_entries_missing=missing_entries,
                        forbidden_entries=forbidden[:10],
                        passed=bad_member is None and not missing_entries and not forbidden)
        check("S-14", "archive passes zipfile.testzip and contains the required entries",
              zip_info["passed"], f"bad_member={bad_member} missing={missing_entries} forbidden={forbidden[:3]}")
    else:
        check("S-15", "archive not checked at this stage (created after this audit)", True,
              "create_final_zip.py runs afterwards")

    n_pass = sum(1 for c in CHECKS if c["passed"])
    ok = n_pass == len(CHECKS)
    print("=" * 78)
    print(f"{n_pass}/{len(CHECKS)} checks passed")
    os.makedirs(AUD, exist_ok=True)
    with open(os.path.join(AUD, "submission_verification.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(dict(created=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                       snapshot_files=n_files, n_checks=len(CHECKS), n_passed=n_pass,
                       passed=ok, archive=zip_info, checks=CHECKS), fh, indent=2)
        fh.write("\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
