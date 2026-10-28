"""Task 2 regression checks.

These tests add coverage requested by the pre-Level-3 audit without changing the
frozen Level 1/Level 2 decisions.  They verify:

* deterministic UTF-8 report generation even when a Windows-like cp1252 default
  is simulated (the original report-equality tests are unchanged);
* every path-like reference in the reports / traceability evidence resolves;
* every generated figure is named somewhere in the report/documentation corpus;
* the written D-24 multistart-convergence condition is satisfied by the stored
  Level 2 fits, and M5 remains the frozen choice;
* the documented D-03 uncertainty mapping and the 0.10 g/L CO2 floor are used
  consistently in the source and frozen records;
* all eight runs, carbon-balance arithmetic, pooled yield and residual chi-square
  remain internally consistent;
* frozen hashes and raw-data checksums still verify.

They are deliberately static/arithmetic checks; they do not refit models or
overwrite outputs.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TAB = ROOT / "outputs" / "tables"
FIG = ROOT / "outputs" / "figures"
sys.path.insert(0, str(SRC))
import carbon_balance as CB  # noqa: E402
import compare as C  # noqa: E402
import fit  # noqa: E402
import models as M  # noqa: E402


# ------------------------------------------------------------------ helpers
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corpus_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "CLAUDE.md", ROOT / "AI_USE.md", ROOT / "worklog.md"]
    files += sorted(ROOT.glob("reports/*.md"))
    files += sorted(ROOT.glob("handoff/*.md"))
    files += sorted(ROOT.glob("docs/*.md"))
    files += sorted(ROOT.glob("docs/*.csv"))
    return [p for p in files if p.exists()]


PATH_TOKEN = re.compile(
    r"(?<![\w./-])(?:[A-Za-z0-9_.*-]+/)*[A-Za-z0-9_.*-]+\.(?:py|md|csv|json|png|sha256|txt|pdf)(?![\w])"
)
PREFIXES = (
    "",
    "outputs/tables/",
    "outputs/tables/work/",
    "outputs/figures/",
    "outputs/audits/",
    "outputs/audits/task2/",
    "src/",
    "tests/",
    "docs/",
    "reports/",
    "data/raw/",
    "handoff/",
)
IGNORE_TOKENS = {"*_1.md", "_1.md", "_report.py", "conftest.py", "sitecustomize.py"}


def _resolve_token(token: str) -> bool:
    token = token.split("::", 1)[0].strip().strip("()[]{}<>,;")
    if not token or token.endswith("/") or token in IGNORE_TOKENS:
        # Ignored tokens are documented non-paths or regex artifacts from longer names.
        return True
    token = token.replace("\\", "/")
    if token.startswith("work/"):
        candidates = [token, "outputs/tables/" + token]
    elif "/" in token:
        candidates = [token]
    else:
        candidates = [pre + token for pre in PREFIXES]
    for cand in candidates:
        if "*" in cand or "?" in cand:
            if glob.glob(str(ROOT / cand)):
                return True
        elif (ROOT / cand).exists():
            return True
    return False


def _path_tokens(text: str) -> list[str]:
    # Backticked tokens carry the file references in the reports.  Evidence cells
    # in the traceability CSV are not backticked, so also scan the full text.
    chunks = re.findall(r"`([^`]+)`", text)
    chunks.append(text)
    out: list[str] = []
    for chunk in chunks:
        out.extend(PATH_TOKEN.findall(chunk))
    # Keep order, remove duplicates.
    return list(dict.fromkeys(out))


def _fit_json(variant: str) -> dict:
    return json.loads((TAB / "work" / f"fit_{variant}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ UTF-8 / Windows simulation
def test_report_generators_write_utf8_under_windows_cp1252_simulation(tmp_path):
    sitecustomize = tmp_path / "sitecustomize.py"
    sitecustomize.write_text(
        "# Simulate a Windows cp1252 default for report .md writes only.\n"
        "import builtins, os, sys\n"
        "_orig_open = builtins.open\n"
        "def _open(file, mode='r', *args, **kwargs):\n"
        "    if ('b' not in mode and any(c in mode for c in 'wax') and kwargs.get('encoding') is None\n"
        "            and str(file).lower().endswith('.md') and os.path.basename(sys.argv[0]).startswith('make_level')):\n"
        "        kwargs['encoding'] = 'cp1252'\n"
        "    return _orig_open(file, mode, *args, **kwargs)\n"
        "builtins.open = _open\n",
        encoding="utf-8",
        newline="\n",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUTF8"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["MPLBACKEND"] = "Agg"
    for script, expected in (
        ("make_level1_report.py", ROOT / "reports" / "level1.md"),
        ("make_level2_report.py", ROOT / "reports" / "level2.md"),
    ):
        out = tmp_path / (script.replace(".py", ".md"))
        proc = subprocess.run(
            [sys.executable, str(SRC / script), str(out)],
            cwd=str(ROOT), env=env, capture_output=True, text=True, encoding="utf-8",
        )
        assert proc.returncode == 0, f"{script} failed:\n{proc.stdout}\n{proc.stderr}"
        assert out.exists() and out.stat().st_size > 0
        assert out.read_bytes() == expected.read_bytes(), f"{script} output is not byte-identical"


def test_committed_reports_are_utf8_with_lf():
    for path in sorted((ROOT / "reports").glob("*.md")):
        data = path.read_bytes()
        data.decode("utf-8")
        assert b"\r\n" not in data, f"{path.name} contains CRLF"


def test_generated_tables_and_json_are_ascii_with_lf():
    for path in sorted(TAB.rglob("*")):
        if not path.is_file() or path.suffix not in (".csv", ".json"):
            continue
        data = path.read_bytes()
        data.decode("ascii")
        assert b"\r\n" not in data, f"{path} contains CRLF"


# ------------------------------------------------------------------ asset references
def test_all_path_like_report_references_resolve():
    corpus = "\n".join(_read(p) for p in _corpus_files())
    unresolved = sorted({tok for tok in _path_tokens(corpus) if not _resolve_token(tok)})
    assert unresolved == [], f"unresolved report/documentation references: {unresolved}"


def test_traceability_evidence_paths_resolve():
    df = pd.read_csv(ROOT / "docs" / "requirements_traceability.csv")
    unresolved = []
    for value in df["evidence"].fillna(""):
        for tok in _path_tokens(str(value)):
            if not _resolve_token(tok):
                unresolved.append(tok)
    assert sorted(set(unresolved)) == [], f"unresolved traceability evidence: {sorted(set(unresolved))}"


def test_every_generated_figure_is_named_in_documentation():
    corpus = "\n".join(_read(p) for p in _corpus_files())
    unnamed = [p.name for p in sorted(FIG.glob("*.png")) if p.name not in corpus]
    assert unnamed == [], f"generated figures not named in reports/docs/worklog: {unnamed}"


# ------------------------------------------------------------------ D-03 / CO2 floor
def test_d03_uncertainty_mapping_documented_and_implemented_consistently():
    brief = _read(ROOT / "docs" / "assignment_brief.md")
    for s in ("±(3.5% + 0.08 g/L)", "±(1% + 0.4 g/L)", "±(1.2% + 0.25 g/L)",
              "About ±2%", "About ±3%", "±0.04"):
        assert s in brief, f"assignment brief no longer contains {s!r}"
    phase0 = _read(SRC / "phase0_inspect.py")
    fit_src = _read(SRC / "fit.py")
    cb_src = _read(SRC / "carbon_balance.py")
    assert "def sd_X(x): return 0.035 * np.asarray(x, float) + 0.08" in phase0
    assert "def sd_S(s): return 0.01 * np.asarray(s, float) + 0.4" in phase0
    assert "def sd_E(e): return 0.012 * np.asarray(e, float) + 0.25" in phase0
    assert "def sd_CO2(c): return 0.02 * np.asarray(c, float)" in phase0
    assert "def sd_G(g): return 0.03 * np.asarray(g, float)" in phase0
    assert "PH_SD = 0.04" in phase0
    assert "def sd_X(x): return 0.035 * np.asarray(x, float) + 0.08" in fit_src
    assert "def sd_C(c, floor=CO2_FLOOR): return 0.02 * np.asarray(c, float) + floor" in fit_src
    assert "def sd_C(c): return 0.02 * c" in cb_src
    assert "0.03 * r[\"G\"]" in cb_src and "0.03 * r[\"L\"]" in cb_src
    assert "0.04" in cb_src


def test_co2_floor_used_in_fitting_and_frozen_records():
    assert fit.CO2_FLOOR == 0.10
    assert fit.default_policy()["co2_floor"] == 0.10
    assert fit.sd_C(0.0) == 0.10
    assert fit.sd_C(3.0) == pytest.approx(0.16)
    assert CB.sd_C(0.0) == 0.0
    assert CB.sd_C(3.0) == pytest.approx(0.06)
    frozen = json.loads((TAB / "level1_frozen.json").read_text(encoding="utf-8"))
    assert frozen["co2_floor"] == 0.10
    sens = pd.read_csv(TAB / "level1_sensitivity.csv")
    for case in ("CO2_floor_0", "CO2_floor_0.5"):
        assert case in set(sens["case"]), f"missing Level 1 sensitivity case {case}"
    comparison = pd.read_csv(TAB / "model_comparison.csv").set_index("model")
    assert len(comparison) == len(M.VARIANTS) == 7
    assert comparison.loc["M5", "c_hat_used"] == pytest.approx(_fit_json("M5")["red"])


# ------------------------------------------------------------------ D-24 convergence
def test_d24_written_convergence_condition_is_satisfied_and_m5_selected():
    fits = {v: _fit_json(v) for v in M.VARIANTS}
    for v, fj in fits.items():
        assert fj["n_near_best"] == fj["n_starts"], f"{v} did not converge from every multistart"
        assert fj["status"] > 0, f"{v} optimiser status is not a successful stop"
        assert fj["failures"] == 0, f"{v} had ODE failures"
    bound_models = [v for v, fj in fits.items() if sum(fj["at_bound"]) != 0]
    assert bound_models == ["M3"], f"unexpected bound-model set: {bound_models}"
    N = fits["M5"]["n_obs"]
    c_hat = fits["M5"]["red"]
    qaicc = {v: C.qaicc(fj["chi2"], c_hat, fj["k"], N) for v, fj in fits.items()}
    ok = [v for v, fj in fits.items()
          if sum(fj["at_bound"]) == 0 and fj["failures"] == 0
          and fj["n_near_best"] == fj["n_starts"] and fj["status"] > 0]
    best = min(ok, key=lambda v: qaicc[v])
    close = [v for v in ok if qaicc[v] - qaicc[best] <= 4 and fits[v]["k"] < fits[best]["k"]]
    preferred = min(close, key=lambda v: fits[v]["k"]) if close else best
    assert preferred == "M5"
    fr = json.loads((TAB / "model_selection_frozen.json").read_text(encoding="utf-8"))
    assert fr["preferred"] == "M5"
    assert fr["best_QAICc_model"] == "M5"
    assert fr["rule"] == "D-24"
    assert fr["c_hat"] == pytest.approx(c_hat)
    assert fr["r6_used_for_selection"] is False
    assert _sha256(TAB / "model_comparison.csv") == fr["model_comparison_sha256"]
    assert _sha256(TAB / "candidate_parameters.csv") == fr["candidate_parameters_sha256"]


# ------------------------------------------------------------------ arithmetic consistency
def test_all_eight_runs_carbon_balance_and_yield_arithmetic():
    cb = pd.read_csv(TAB / "carbon_balance_all_runs.csv").set_index("run")
    yl = pd.read_csv(TAB / "ethanol_yields.csv").set_index("run")
    dec = pd.read_csv(TAB / "yield_gap_decomposition.csv").set_index("run")
    pooled = pd.read_csv(TAB / "ethanol_yield_pooled.csv").set_index("set")
    assert list(cb.index) == CB.RUNS
    assert cb["closes_within_95"].sum() == 7
    assert set(cb.index[~cb["closes_within_95"]]) == {"R4"}
    d = CB.load(str(ROOT / "data" / "raw"))
    for r in CB.RUNS:
        x = d[r]
        Lc = CB.lactic_central(x)
        c = CB.cmol(x["S0"], x["X0"], x["S48"], x["X48"], x["E"], x["C"], x["G"], Lc)
        assert c["C_in"] == pytest.approx(cb.loc[r, "C_in_total_Cmol_L"], rel=1e-12, abs=1e-12)
        assert c["C_out"] == pytest.approx(cb.loc[r, "C_out_total_Cmol_L"], rel=1e-12, abs=1e-12)
        assert c["recovery_pct"] == pytest.approx(cb.loc[r, "recovery_pct"], rel=1e-12, abs=1e-12)
        assert x["E"] / (x["S0"] - x["S48"]) == pytest.approx(yl.loc[r, "yield_g_per_g"], rel=1e-12, abs=1e-12)
    assert np.max(np.abs(dec["check_sum_minus_gap"].to_numpy(float))) < 1e-10
    ratio = sum(d[r]["E"] for r in CB.RUNS) / sum(d[r]["S0"] - d[r]["S48"] for r in CB.RUNS)
    assert ratio == pytest.approx(pooled.loc["all 8 runs", "pooled_yield_sum_ratio"], rel=1e-12, abs=1e-12)


def test_model_residuals_reproduce_model_comparison_chi2():
    resid = pd.read_csv(TAB / "model_residuals.csv")
    resid = resid[resid["in_objective"].astype(bool)]
    cmp = pd.read_csv(TAB / "model_comparison.csv").set_index("model")
    for v, g in resid.groupby("model"):
        assert float(np.sum(g["z"].to_numpy(float) ** 2)) == pytest.approx(cmp.loc[v, "chi2"], rel=1e-10, abs=1e-8)


def test_frozen_hashes_and_raw_checksums_verify():
    frozen = json.loads((TAB / "level1_frozen.json").read_text(encoding="utf-8"))
    assert fit.sha256(str(TAB / "level1_parameters.csv")) == frozen["parameters_csv_sha256"]
    fr = json.loads((TAB / "model_selection_frozen.json").read_text(encoding="utf-8"))
    assert fit.sha256(str(TAB / "model_comparison.csv")) == fr["model_comparison_sha256"]
    assert fit.sha256(str(TAB / "candidate_parameters.csv")) == fr["candidate_parameters_sha256"]
    raw = ROOT / "data" / "raw"
    for line in (raw / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines():
        expected, name = line.split()
        assert _sha256(raw / name) == expected, f"raw checksum mismatch for {name}"


def test_all_csv_writers_pin_utf8_and_lf_line_terminator():
    """pandas.DataFrame.to_csv defaults to os.linesep, so on Windows every table came out CRLF.

    That is the actual cause of the reported local Windows failure
    ('1 failed ... outputs/tables/data_quality.csv contains CRLF').  Every writer must pin the
    encoding and the line terminator explicitly instead of relying on the platform default.
    """
    import ast

    offenders: list[str] = []
    sites = 0
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == "to_csv"):
                continue
            sites += 1
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            lt = kw.get("lineterminator")
            enc = kw.get("encoding")
            if not (isinstance(lt, ast.Constant) and lt.value == "\n"):
                offenders.append(f"{path.name}:{node.lineno} to_csv without lineterminator='\\n'")
            if not (isinstance(enc, ast.Constant) and str(enc.value).lower() == "utf-8"):
                offenders.append(f"{path.name}:{node.lineno} to_csv without encoding='utf-8'")
    assert sites > 0, "no to_csv call sites found: the guard would be vacuous"
    assert offenders == [], "unpinned CSV writers:\n" + "\n".join(offenders)
