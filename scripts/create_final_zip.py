#!/usr/bin/env python
"""Create ``fermentation_kinetics_final_submission.zip`` from the verified project tree.

Contents: the complete project (source, tests, data, reports, generated outputs, audits, logs,
handoff), including the generated ``submission/`` snapshot.  Excluded: ``.git``, caches, virtual
environments, ``__pycache__``, ``*.pyc`` and any previously built ``*.zip`` (so the archive can
never contain itself).

Deterministic: entries are written in sorted order with fixed timestamps and stored compression
settings, and the archive's own validation records are excluded from its contents, so rebuilding from
identical inputs reproduces the same bytes.

The archive is created only after the submission verification has passed; if a required entry is
missing the script fails instead of shipping an incomplete package.

Writes ``outputs/audits/level3/final_zip_validation.json`` and ``final_zip_listing.txt``.

Usage (project root):  python scripts/create_final_zip.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, "outputs", "audits", "level3")
ZIP_NAME = "fermentation_kinetics_final_submission.zip"
ZIP_PATH = os.path.join(ROOT, ZIP_NAME)

EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", ".mypy_cache"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".zip"}
# The archive's own validation records describe the archive, so they are written only outside it:
# including them would make every rebuild differ from the previous one.
EXCLUDE_NAMES = {".DS_Store", "Thumbs.db", "final_zip_validation.json", "final_zip_listing.txt"}

REQUIRED_ENTRIES = [
    "README.md", "AI_USE.md", "worklog.md", "requirements.txt", "requirements_traceability.csv",
    "pytest.ini",
    "docs/assignment_brief.md", "reports/level1.md", "reports/level2.md", "reports/level3.md",
    "data/raw/runs.csv", "data/raw/timecourse.csv", "data/raw/endpoint_hplc.csv",
    "data/raw/CHECKSUMS.sha256",
    "src/kinetics.py", "src/models.py", "src/fit.py", "src/compare.py",
    "src/level3.py", "src/level3_optimize.py", "src/make_level3_report.py",
    "src/level3_consistency_audit.py",
    "tests/test_level3.py", "tests/test_task2_consistency.py",
    "scripts/reproduce_level3.ps1", "scripts/reproduce_level3.sh",
    "scripts/build_submission.py", "scripts/verify_submission.py", "scripts/create_final_zip.py",
    "outputs/tables/optimization_grid.csv", "outputs/tables/optimization_recommendations.csv",
    "outputs/tables/plant_economics.csv", "outputs/tables/optimization_uncertainty.csv",
    "outputs/tables/optimization_model_comparison.csv", "outputs/tables/optimization_input_audit.csv",
    "outputs/figures/level3_feasible_region.png", "outputs/figures/level3_economics.png",
    "outputs/figures/level3_completion_time.png", "outputs/figures/level3_uncertainty.png",
    "outputs/audits/level3/model_policy.json", "outputs/audits/level3/consistency_report.json",
    "submission/manifest.csv", "submission/README_SUBMISSION.md", "submission/level3/level3.md",
    "handoff/DECISIONS.md", "handoff/PROJECT_STATE.md",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in EXCLUDE_SUFFIX or name in EXCLUDE_NAMES:
                continue
            path = os.path.join(base, name)
            if os.path.abspath(path) == os.path.abspath(ZIP_PATH):
                continue
            yield path, os.path.relpath(path, ROOT).replace(os.sep, "/")


def main():
    if not os.path.isdir(os.path.join(ROOT, "submission")):
        raise SystemExit("submission/ is missing: run scripts/build_submission.py first")
    verification = os.path.join(AUD, "submission_verification.json")
    if not os.path.exists(verification):
        raise SystemExit("submission_verification.json is missing: run scripts/verify_submission.py first")
    with open(verification, encoding="utf-8") as fh:
        ver = json.load(fh)
    if not ver.get("passed"):
        raise SystemExit("submission verification did not pass: refusing to build the archive")

    entries = list(iter_files())
    absent = [e for e in REQUIRED_ENTRIES if not os.path.exists(os.path.join(ROOT, e))]
    if absent:
        raise SystemExit(f"required entries missing from the project tree: {absent}")

    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path, rel in entries:
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(path, "rb") as fh:
                zf.writestr(info, fh.read())

    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = zf.namelist()
        bad_member = zf.testzip()
        missing_entries = [e for e in REQUIRED_ENTRIES if e not in names]
        listing = "\n".join(names) + "\n"

    with open(os.path.join(AUD, "final_zip_listing.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(listing)

    report = dict(
        created=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        zip_path=ZIP_PATH, zip_name=ZIP_NAME,
        zip_bytes=os.path.getsize(ZIP_PATH), zip_sha256=sha256(ZIP_PATH),
        file_count=len(names), testzip_bad_member=bad_member,
        required_entries_checked=len(REQUIRED_ENTRIES), required_entries_missing=missing_entries,
        passed=bad_member is None and not missing_entries,
        excluded=sorted(EXCLUDE_DIRS) + sorted(EXCLUDE_SUFFIX),
        note="The archive contains the complete project including the generated submission snapshot. "
             "ZIP validation files themselves are written outside the archive after it is built.")
    with open(os.path.join(AUD, "final_zip_validation.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")

    print(f"archive: {ZIP_NAME}")
    print(f"  bytes   : {report['zip_bytes']:,}")
    print(f"  sha256  : {report['zip_sha256']}")
    print(f"  entries : {report['file_count']:,}")
    print(f"  testzip : {'OK' if bad_member is None else bad_member}")
    print(f"  missing : {missing_entries if missing_entries else 'none'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
