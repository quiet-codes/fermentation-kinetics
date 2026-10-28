#!/usr/bin/env python
"""Task 2 consistency audit for an isolated Level 2 reproduction.

Compares original vs reproduced tables/figures/reports, checks frozen hashes,
raw checksums, path references, D-03/D-24 consistency, CO2 floor, carbon/yield
arithmetic, and residual chi-square.  Writes machine-readable JSON and a short
markdown report.  It is read-only with respect to the original project.
"""
from __future__ import annotations

import difflib
import glob
import hashlib
import json
import locale
import math
import os
import platform
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import carbon_balance as CB  # noqa: E402
import compare as C  # noqa: E402
import fit  # noqa: E402
import models as M  # noqa: E402

PATH_TOKEN = re.compile(
    r"(?<![\w./-])(?:[A-Za-z0-9_.*-]+/)*[A-Za-z0-9_.*-]+\.(?:py|md|csv|json|png|sha256|txt|pdf)(?![\w])"
)
PREFIXES = (
    "", "outputs/tables/", "outputs/tables/work/", "outputs/figures/",
    "outputs/audits/", "outputs/audits/task2/", "src/", "tests/", "docs/",
    "reports/", "data/raw/", "handoff/",
)
IGNORE_TOKENS = {
    "*_1.md", "_1.md", "_report.py", "conftest.py", "sitecustomize.py",
}
PNG_SIG = b"\x89PNG\r\n\x1a\n"


# ------------------------------------------------------------------ generic helpers
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json_load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"),
                      parse_constant=lambda s: f"<{s}>")


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        obj = float(obj)
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(obj), indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{prefix}[{i}]")
    elif isinstance(obj, (int, float, str, bool)) or obj is None:
        yield prefix, obj
    else:
        yield prefix, str(obj)


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ------------------------------------------------------------------ file comparisons
def compare_bytes(path1: Path, path2: Path):
    rec = dict(original=str(path1), reproduced=str(path2),
               original_exists=path1.exists(), reproduced_exists=path2.exists())
    if not (path1.exists() and path2.exists()):
        rec["byte_equal"] = False
        return rec
    b1, b2 = path1.read_bytes(), path2.read_bytes()
    rec.update(original_sha256=_sha256(path1), reproduced_sha256=_sha256(path2),
               original_size=len(b1), reproduced_size=len(b2), byte_equal=(b1 == b2))
    return rec


def compare_text(path1: Path, path2: Path):
    rec = compare_bytes(path1, path2)
    if not (path1.exists() and path2.exists()):
        rec.update(text_equal=False, line_difference_count=None)
        return rec
    t1, t2 = _read_text(path1), _read_text(path2)
    diff = list(difflib.unified_diff(t1.splitlines(), t2.splitlines(),
                                     fromfile=str(path1), tofile=str(path2), lineterm=""))
    rec.update(text_equal=(t1 == t2), original_lines=len(t1.splitlines()),
               reproduced_lines=len(t2.splitlines()), diff_line_count=len(diff),
               first_diff_lines=diff[:8])
    return rec


def compare_json(path1: Path, path2: Path):
    rec = compare_bytes(path1, path2)
    if not (path1.exists() and path2.exists()):
        rec.update(parsed_equal=False)
        return rec
    o1, o2 = _json_load(path1), _json_load(path2)
    f1, f2 = dict(_flatten(o1)), dict(_flatten(o2))
    keys = sorted(set(f1) | set(f2))
    missing_left = sorted(set(f1) - set(f2))
    missing_right = sorted(set(f2) - set(f1))
    numeric_abs, numeric_rel = [], []
    string_mismatch = []
    for k in keys:
        if k not in f1 or k not in f2:
            continue
        a, b = f1[k], f2[k]
        if _num(a) and _num(b):
            d = abs(float(a) - float(b))
            numeric_abs.append(d)
            if float(b) != 0:
                numeric_rel.append(d / abs(float(b)))
            elif float(a) != 0:
                numeric_rel.append(float("inf"))
        elif a != b:
            string_mismatch.append(k)
    rec.update(
        parsed_equal=(f1 == f2),
        field_count=len(keys),
        missing_in_reproduced=missing_left,
        new_in_reproduced=missing_right,
        numeric_max_abs_diff=max(numeric_abs) if numeric_abs else None,
        numeric_max_rel_diff=max(numeric_rel) if numeric_rel else None,
        numeric_allclose=all(abs(float(f1[k]) - float(f2[k])) <= 1e-8 + 1e-6 * abs(float(f2[k]))
                             for k in keys if k in f1 and k in f2 and _num(f1[k]) and _num(f2[k])),
        nonnumeric_mismatches=string_mismatch,
        tolerance=dict(rtol=1e-6, atol=1e-8),
    )
    return rec


def compare_csv(path1: Path, path2: Path):
    rec = compare_bytes(path1, path2)
    if not (path1.exists() and path2.exists()):
        rec.update(numeric_allclose=False)
        return rec
    d1, d2 = pd.read_csv(path1), pd.read_csv(path2)
    s1 = pd.read_csv(path1, dtype=str, keep_default_na=False)
    s2 = pd.read_csv(path2, dtype=str, keep_default_na=False)
    cols1, cols2 = list(d1.columns), list(d2.columns)
    common = [c for c in cols1 if c in cols2]
    numeric_abs, numeric_rel, numeric_close = [], [], True
    nonnum_mismatch = 0
    for c in common:
        a = pd.to_numeric(d1[c], errors="coerce").to_numpy(float)
        b = pd.to_numeric(d2[c], errors="coerce").to_numpy(float)
        if len(a) != len(b):
            numeric_close = False
            continue
        both = ~(np.isnan(a) | np.isnan(b))
        if both.any():
            d = np.abs(a[both] - b[both])
            numeric_abs.append(float(d.max()))
            nz = b[both] != 0
            if nz.any():
                numeric_rel.append(float((d[nz] / np.abs(b[both][nz])).max()))
            numeric_close &= bool(np.allclose(a[both], b[both], rtol=1e-6, atol=1e-8))
        sa = s1[c].to_numpy() if c in s1 else np.array([""] * len(d1))
        sb = s2[c].to_numpy() if c in s2 else np.array([""] * len(d2))
        if len(sa) == len(sb):
            nonnum_mismatch += int(np.sum(sa != sb))
        else:
            nonnum_mismatch += abs(len(sa) - len(sb))
    rec.update(
        original_rows=len(d1), reproduced_rows=len(d2), original_columns=cols1,
        reproduced_columns=cols2, columns_equal=(cols1 == cols2),
        numeric_max_abs_diff=max(numeric_abs) if numeric_abs else None,
        numeric_max_rel_diff=max(numeric_rel) if numeric_rel else None,
        numeric_allclose=bool(numeric_close),
        text_cell_mismatch_count=nonnum_mismatch,
        tolerance=dict(rtol=1e-6, atol=1e-8),
    )
    return rec


def compare_png(path1: Path, path2: Path):
    rec = compare_bytes(path1, path2)
    if path1.exists() and path2.exists():
        rec.update(original_signature_ok=path1.read_bytes()[:8] == PNG_SIG,
                   reproduced_signature_ok=path2.read_bytes()[:8] == PNG_SIG,
                   pixel_level_comparison=False,
                   note="PNG byte equality is not required: matplotlib/font metadata can differ by version.")
    return rec


# ------------------------------------------------------------------ corpus / reference checks
def _corpus_files(root: Path):
    files = [root / "README.md", root / "CLAUDE.md", root / "AI_USE.md", root / "worklog.md",
             root / "outputs" / "audits" / "pre_level3_audit.md"]
    for pattern in ("reports/*.md", "handoff/*.md", "docs/*.md", "docs/*.csv"):
        files += sorted(root.glob(pattern))
    return [p for p in files if p.exists()]


def _path_tokens(text: str):
    chunks = re.findall(r"`([^`]+)`", text)
    chunks.append(text)
    out = []
    for chunk in chunks:
        out.extend(PATH_TOKEN.findall(chunk))
    return list(dict.fromkeys(out))


def _resolve_token(root: Path, token: str):
    token = token.split("::", 1)[0].strip().strip("()[]{}<>,;")
    if not token or token.endswith("/") or token in IGNORE_TOKENS:
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
            if glob.glob(str(root / cand)):
                return True
        elif (root / cand).exists():
            return True
    return False


def check_asset_references(root: Path):
    corpus = "\n".join(_read_text(p) for p in _corpus_files(root))
    unresolved = sorted({tok for tok in _path_tokens(corpus) if not _resolve_token(root, tok)})
    figures = sorted((root / "outputs" / "figures").glob("*.png"))
    unnamed = [p.name for p in figures if p.name not in corpus]
    return dict(
        corpus_files=[str(p.relative_to(root)) for p in _corpus_files(root)],
        path_token_count=len(_path_tokens(corpus)), unresolved=unresolved,
        unresolved_count=len(unresolved), figure_count=len(figures),
        figures_not_named_in_corpus=unnamed,
        note=("Ignored tokens are documented non-paths/regex artifacts: '*_1.md' is a generic upload "
              "placeholder, 'conftest.py' is explicitly noted as absent, 'sitecustomize.py' was a temporary "
              "simulation file, and '_report.py'/'_1.md' come from truncated longer names."),
    )


def check_traceability_evidence(root: Path):
    df = pd.read_csv(root / "docs" / "requirements_traceability.csv")
    unresolved = []
    for value in df["evidence"].fillna(""):
        for tok in _path_tokens(str(value)):
            if not _resolve_token(root, tok):
                unresolved.append(tok)
    return dict(row_count=len(df), unresolved=sorted(set(unresolved)),
                unresolved_count=len(set(unresolved)))


# ------------------------------------------------------------------ numeric / decision checks
def check_frozen_hashes(root: Path):
    t = root / "outputs" / "tables"
    frozen1 = _json_load(t / "level1_frozen.json")
    frozen2 = _json_load(t / "model_selection_frozen.json")
    raw = root / "data" / "raw"
    raw_results = {}
    for line in (raw / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines():
        exp, name = line.split()
        got = _sha256(raw / name)
        raw_results[name] = dict(expected=exp, actual=got, ok=(exp == got))
    return dict(
        level1_parameters_sha256=dict(stored=frozen1["parameters_csv_sha256"],
                                      actual=_sha256(t / "level1_parameters.csv"),
                                      ok=_sha256(t / "level1_parameters.csv") == frozen1["parameters_csv_sha256"]),
        model_comparison_sha256=dict(stored=frozen2["model_comparison_sha256"],
                                     actual=_sha256(t / "model_comparison.csv"),
                                     ok=_sha256(t / "model_comparison.csv") == frozen2["model_comparison_sha256"]),
        candidate_parameters_sha256=dict(stored=frozen2["candidate_parameters_sha256"],
                                         actual=_sha256(t / "candidate_parameters.csv"),
                                         ok=_sha256(t / "candidate_parameters.csv") == frozen2["candidate_parameters_sha256"]),
        raw_checksums=raw_results,
    )


def check_d03_mapping(root: Path):
    brief = _read_text(root / "docs" / "assignment_brief.md")
    strings = ["±(3.5% + 0.08 g/L)", "±(1% + 0.4 g/L)", "±(1.2% + 0.25 g/L)",
               "About ±2%", "About ±3%", "±0.04"]
    phase0 = _read_text(root / "src" / "phase0_inspect.py")
    fit_src = _read_text(root / "src" / "fit.py")
    cb_src = _read_text(root / "src" / "carbon_balance.py")
    patterns = [
        "def sd_X(x): return 0.035 * np.asarray(x, float) + 0.08",
        "def sd_S(s): return 0.01 * np.asarray(s, float) + 0.4",
        "def sd_E(e): return 0.012 * np.asarray(e, float) + 0.25",
        "def sd_CO2(c): return 0.02 * np.asarray(c, float)",
        "def sd_G(g): return 0.03 * np.asarray(g, float)",
        "PH_SD = 0.04",
        "def sd_C(c, floor=CO2_FLOOR): return 0.02 * np.asarray(c, float) + floor",
        "def sd_C(c): return 0.02 * c",
    ]
    found = {p: (p in phase0 or p in fit_src or p in cb_src) for p in patterns}
    return dict(
        brief_strings_present={s: (s in brief) for s in strings},
        source_patterns_present=found,
        all_source_patterns_present=all(found.values()),
        mapping=dict(
            biomass="0.035*measured + 0.08 g/L",
            TRS="0.01*measured + 0.4 g/L",
            ethanol="0.012*measured + 0.25 g/L",
            CO2_fitting="0.02*measured + 0.10 g/L floor",
            CO2_phase0_and_carbon_balance="0.02*measured (no floor)",
            glycerol_and_detected_lactic="0.03*measured",
            pH="absolute 0.04",
        ),
        limits=("Original assignment PDF is unavailable. The extracted brief's uncertainty table is unlabelled "
                "and read in row order; the exact meaning of 'about ±2%' / 'about ±3%' and row alignment "
                "cannot be definitively verified. Do not infer additional requirements."),
    )


def check_co2_floor(root: Path):
    frozen = _json_load(root / "outputs" / "tables" / "level1_frozen.json")
    sens = pd.read_csv(root / "outputs" / "tables" / "level1_sensitivity.csv")
    runs, tc = fit.read_raw(str(root / "data" / "raw"))
    recs = fit.make_records(fit.TRAIN, runs, tc)
    allc = np.concatenate([r["obs"]["C"][1:] for r in recs])
    return dict(
        source_floor=fit.CO2_FLOOR,
        default_policy_floor=fit.default_policy()["co2_floor"],
        level1_frozen_floor=frozen["co2_floor"],
        fit_sd_C_at_zero=float(fit.sd_C(0.0)),
        carbon_balance_sd_C_at_zero=float(CB.sd_C(0.0)),
        existing_level1_sensitivity_cases=sorted(set(sens["case"])),
        min_positive_time_CO2_g_L=float(allc.min()),
        sd_ratio_at_min_CO2=float(fit.sd_C(allc.min(), 0.1) / fit.sd_C(allc.min(), 0.0)),
        sd_ratio_median=float(np.median(fit.sd_C(allc, 0.1) / fit.sd_C(allc, 0.0))),
        note="Phase 0 / carbon balance use no floor; fitting, all Level 2 fits and frozen selection use 0.10 g/L.",
    )


def check_d24_convergence(root: Path):
    w = root / "outputs" / "tables" / "work"
    fits = {v: _json_load(w / f"fit_{v}.json") for v in M.VARIANTS}
    per_model = {}
    for v, fj in fits.items():
        per_model[v] = dict(
            n_near_best=int(fj["n_near_best"]), n_starts=int(fj["n_starts"]),
            status=int(fj["status"]), failures=int(fj["failures"]),
            params_at_bound=int(sum(fj["at_bound"])),
            converged=bool(fj["n_near_best"] == fj["n_starts"] and fj["status"] > 0),
        )
    N = fits["M5"]["n_obs"]; chat = fits["M5"]["red"]
    qaicc = {v: float(C.qaicc(fits[v]["chi2"], chat, fits[v]["k"], N)) for v in M.VARIANTS}
    ok = [v for v, x in per_model.items() if x["params_at_bound"] == 0 and x["failures"] == 0 and x["converged"]]
    best = min(ok, key=lambda v: qaicc[v])
    close = [v for v in ok if qaicc[v] - qaicc[best] <= 4 and fits[v]["k"] < fits[best]["k"]]
    preferred = min(close, key=lambda v: fits[v]["k"]) if close else best
    frozen = _json_load(root / "outputs" / "tables" / "model_selection_frozen.json")
    return dict(
        written_rule_condition="D-24 also requires multistart converged to one minimum; compare.py:stage_select filters only params_at_bound == 0 and ode_failures == 0.",
        code_enforces_convergence_explicitly=False,
        per_model=per_model,
        all_models_converged=all(x["converged"] for x in per_model.values()),
        eligible_with_convergence=ok,
        qaicc=qaicc,
        best_qaicc_model=best,
        recomputed_preferred=preferred,
        frozen_preferred=frozen["preferred"],
        frozen_rule=frozen["rule"],
        frozen_c_hat=frozen["c_hat"],
        recomputed_c_hat=chat,
        r6_used_for_selection=frozen["r6_used_for_selection"],
        current_results_satisfy_written_condition=bool(preferred == frozen["preferred"] == "M5"),
        note="No decision or rule was changed; this is a verification against stored results.",
    )


def check_carbon_yield_arithmetic(root: Path):
    t = root / "outputs" / "tables"
    cb = pd.read_csv(t / "carbon_balance_all_runs.csv").set_index("run")
    yl = pd.read_csv(t / "ethanol_yields.csv").set_index("run")
    dec = pd.read_csv(t / "yield_gap_decomposition.csv")
    pooled = pd.read_csv(t / "ethanol_yield_pooled.csv").set_index("set")
    d = CB.load(str(root / "data" / "raw"))
    max_cin = max_cout = max_rec = max_yield = 0.0
    for r in CB.RUNS:
        x = d[r]; Lc = CB.lactic_central(x)
        c = CB.cmol(x["S0"], x["X0"], x["S48"], x["X48"], x["E"], x["C"], x["G"], Lc)
        max_cin = max(max_cin, abs(c["C_in"] - cb.loc[r, "C_in_total_Cmol_L"]))
        max_cout = max(max_cout, abs(c["C_out"] - cb.loc[r, "C_out_total_Cmol_L"]))
        max_rec = max(max_rec, abs(c["recovery_pct"] - cb.loc[r, "recovery_pct"]))
        max_yield = max(max_yield, abs(x["E"] / (x["S0"] - x["S48"]) - yl.loc[r, "yield_g_per_g"]))
    ratio = sum(d[r]["E"] for r in CB.RUNS) / sum(d[r]["S0"] - d[r]["S48"] for r in CB.RUNS)
    return dict(
        runs=list(cb.index), all_eight_runs=list(cb.index) == CB.RUNS,
        non_closing_runs=list(cb.index[~cb["closes_within_95"]]),
        max_abs_C_in_diff=max_cin, max_abs_C_out_diff=max_cout,
        max_abs_recovery_pct_diff=max_rec, max_abs_yield_diff=max_yield,
        max_abs_yield_gap_additivity_residual=float(np.max(np.abs(dec["check_sum_minus_gap"].to_numpy(float)))),
        pooled_yield_from_raw=float(ratio),
        pooled_yield_stored=float(pooled.loc["all 8 runs", "pooled_yield_sum_ratio"]),
        pooled_yield_abs_diff=float(abs(ratio - pooled.loc["all 8 runs", "pooled_yield_sum_ratio"])),
    )


def check_residual_chi2(root: Path):
    t = root / "outputs" / "tables"
    resid = pd.read_csv(t / "model_residuals.csv")
    resid = resid[resid["in_objective"].astype(bool)]
    cmp = pd.read_csv(t / "model_comparison.csv").set_index("model")
    out = {}
    for v, g in resid.groupby("model"):
        got = float(np.sum(g["z"].to_numpy(float) ** 2))
        out[v] = dict(stored_chi2=float(cmp.loc[v, "chi2"]), residual_chi2=got,
                      abs_diff=float(abs(got - cmp.loc[v, "chi2"])))
    return dict(per_model=out, max_abs_diff=max(x["abs_diff"] for x in out.values()))


def environment_info():
    import scipy
    import matplotlib
    return dict(
        python=platform.python_version(), platform=platform.platform(),
        numpy=np.__version__, scipy=scipy.__version__, pandas=pd.__version__,
        matplotlib=matplotlib.__version__, cpu_count=os.cpu_count(),
        locale_preferred_encoding=locale.getpreferredencoding(False),
        filesystem_encoding=sys.getfilesystemencoding(),
    )


# ------------------------------------------------------------------ top-level audit
def _collect(root: Path, subdirs):
    out = []
    for sub in subdirs:
        base = root / sub
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file():
                out.append((sub, p.relative_to(root).as_posix(), p))
    return out


def run_audit(original_root: Path, repro_root: Path, output_dir: Path,
              stage_results=None, reproduction_log=None, baseline_manifest=None):
    original_root = Path(original_root).resolve()
    repro_root = Path(repro_root).resolve()
    output_dir = Path(output_dir).resolve()
    subdirs = ("outputs/tables", "outputs/figures", "reports")
    orig_files = {rel: p for _, rel, p in _collect(original_root, subdirs)}
    rep_files = {rel: p for _, rel, p in _collect(repro_root, subdirs)}
    keys = sorted(set(orig_files) | set(rep_files))
    comparisons = {}
    for rel in keys:
        p1, p2 = orig_files.get(rel), rep_files.get(rel)
        if p1 is None or p2 is None:
            comparisons[rel] = dict(original_exists=p1 is not None, reproduced_exists=p2 is not None,
                                    byte_equal=False, note="missing on one side")
            continue
        suffix = p1.suffix.lower()
        if suffix == ".csv":
            rec = compare_csv(p1, p2)
        elif suffix == ".json":
            rec = compare_json(p1, p2)
        elif suffix == ".png":
            rec = compare_png(p1, p2)
        else:
            rec = compare_text(p1, p2)
        rec["relative_path"] = rel
        comparisons[rel] = rec
    # Baseline hash changes (what the isolated run actually rewrote).
    changed = []
    if baseline_manifest and Path(baseline_manifest).exists():
        base = _json_load(Path(baseline_manifest))
        for rel, expected in base.items():
            p = repro_root / rel
            if not p.exists() or _sha256(p) != expected:
                changed.append(rel)
    elif baseline_manifest is None:
        default_manifest = repro_root / "logs" / "baseline_manifest.json"
        if default_manifest.exists():
            base = _json_load(default_manifest)
            for rel, expected in base.items():
                p = repro_root / rel
                if not p.exists() or _sha256(p) != expected:
                    changed.append(rel)
    checks = dict(
        frozen_hashes=check_frozen_hashes(original_root),
        frozen_hashes_reproduced=check_frozen_hashes(repro_root),
        asset_references=check_asset_references(original_root),
        traceability_evidence=check_traceability_evidence(original_root),
        d03_mapping=check_d03_mapping(original_root),
        co2_floor=check_co2_floor(original_root),
        d24_convergence=check_d24_convergence(original_root),
        d24_convergence_reproduced=check_d24_convergence(repro_root),
        carbon_yield_arithmetic=check_carbon_yield_arithmetic(original_root),
        carbon_yield_arithmetic_reproduced=check_carbon_yield_arithmetic(repro_root),
        residual_chi2=check_residual_chi2(original_root),
        residual_chi2_reproduced=check_residual_chi2(repro_root),
    )
    numeric_files = [rel for rel, r in comparisons.items()
                     if r.get("original_exists") and r.get("reproduced_exists")
                     and Path(rel).suffix.lower() in (".csv", ".json")]
    numeric_allclose = [rel for rel in numeric_files if comparisons[rel].get("numeric_allclose") is False]
    report = dict(
        created=time.strftime("%Y-%m-%d %H:%M:%S"),
        original_root=str(original_root), reproduced_root=str(repro_root),
        environment=environment_info(),
        stage_results=stage_results or [],
        reproduction_log=reproduction_log,
        baseline_manifest=baseline_manifest,
        file_comparison_summary=dict(
            file_count=len(comparisons),
            byte_equal_count=sum(1 for r in comparisons.values() if r.get("byte_equal")),
            csv_json_count=len(numeric_files),
            csv_json_not_allclose=numeric_allclose,
            png_count=sum(1 for rel in comparisons if rel.lower().endswith(".png")),
            text_report_count=sum(1 for rel in comparisons if rel.lower().endswith(".md")),
        ),
        files_with_hash_changed_vs_copied_baseline=changed,
        comparisons=comparisons,
        checks=checks,
        limitations=[
            "The original assignment PDF is unavailable; D-03 is verified only against docs/assignment_brief.md.",
            "Actual Windows execution was not performed in this Linux sandbox; a cp1252 file-encoding simulation is used for the UTF-8 fix.",
            "Figures are checked for valid PNG signature and byte equality only, not pixel-level equality.",
            "Numeric reproduction uses Python 3.11.2 / numpy 2.4.6 / pandas 3.1.0; the frozen record used Python 3.12.3 / numpy 2.4.4 / pandas 3.0.2, so bit-exact agreement is not expected.",
            "Level 1 fit and full Level 1 sensitivity were not refit in the reproduction; the frozen Level 1 outputs were copied as inputs.",
        ],
    )
    _write_json(output_dir / "consistency_report.json", report)
    lines = [
        "# Task 2 Level 2 reproduction consistency audit",
        "",
        f"- Original root: `{original_root}`",
        f"- Reproduced root: `{repro_root}`",
        f"- Created: {report['created']}",
        f"- Files compared: {report['file_comparison_summary']['file_count']} "
        f"({report['file_comparison_summary']['csv_json_count']} CSV/JSON, "
        f"{report['file_comparison_summary']['png_count']} PNG, "
        f"{report['file_comparison_summary']['text_report_count']} Markdown).",
        f"- Byte-identical files: {report['file_comparison_summary']['byte_equal_count']}.",
        f"- CSV/JSON outside rtol=1e-6/atol=1e-8: {len(numeric_allclose)}"
        + (f" (`{', '.join(numeric_allclose)}`)" if numeric_allclose else "."),
        f"- Files whose bytes differ from copied baseline: {len(changed)}.",
        "",
        "## Decision / arithmetic checks",
        "",
        f"- D-03 source patterns present: {checks['d03_mapping']['all_source_patterns_present']}; "
        "original PDF remains unavailable.",
        f"- CO2 floor: fitting/frozen = {checks['co2_floor']['source_floor']} g/L; "
        f"Phase 0/carbon balance = no floor.",
        f"- D-24: all stored fits converged = {checks['d24_convergence']['all_models_converged']}; "
        f"recomputed preferred = `{checks['d24_convergence']['recomputed_preferred']}`; "
        f"frozen preferred = `{checks['d24_convergence']['frozen_preferred']}`.",
        f"- D-24 in reproduced root: preferred = `{checks['d24_convergence_reproduced']['recomputed_preferred']}`.",
        f"- Carbon balance: all eight runs = {checks['carbon_yield_arithmetic']['all_eight_runs']}; "
        f"non-closing runs = {checks['carbon_yield_arithmetic']['non_closing_runs']}.",
        f"- Max residual chi-square difference (original / reproduced): "
        f"{checks['residual_chi2']['max_abs_diff']:.3g} / {checks['residual_chi2_reproduced']['max_abs_diff']:.3g}.",
        f"- Unresolved asset references: {checks['asset_references']['unresolved_count']}; "
        f"unnamed figures: {len(checks['asset_references']['figures_not_named_in_corpus'])}; "
        f"unresolved traceability evidence paths: {checks['traceability_evidence']['unresolved_count']}.",
        "",
        "## Limits",
        "",
    ]
    lines += [f"- {x}" for x in report["limitations"]]
    lines += ["", "Full machine-readable detail: `consistency_report.json`.", ""]
    _write_text(output_dir / "consistency_report.md", "\n".join(lines))
    return report
