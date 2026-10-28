"""Phase 0 checks. Run from the project root:  pytest -q
The script is re-run into a temporary folder, so nothing in outputs/ is overwritten."""
import hashlib, os, re, subprocess, sys
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    d = tmp_path_factory.mktemp("p0")
    subprocess.run([sys.executable, os.path.join(ROOT, "src", "phase0_inspect.py"), "--data-dir", RAW, "--root", str(d)], check=True)
    return d


def test_raw_files_unchanged():
    for line in open(os.path.join(RAW, "CHECKSUMS.sha256")):
        digest, name = line.split()
        assert hashlib.sha256(open(os.path.join(RAW, name), "rb").read()).hexdigest() == digest, name


def test_no_fitting_code():
    src = open(os.path.join(ROOT, "src", "phase0_inspect.py")).read()
    assert not re.search(r"curve_fit|least_squares|minimize|solve_ivp|odeint", src)


def test_all_outputs_exist(out):
    for f in ["outputs/tables/data_quality.csv", "outputs/tables/endpoint_diagnostics.csv",
              "outputs/tables/preliminary_carbon_balance.csv", "outputs/figures/raw_curves.png"]:
        assert os.path.getsize(os.path.join(out, f)) > 0, f


def test_no_run_excluded(out):
    runs = [f"R{i}" for i in range(1, 9)]
    for f in ["endpoint_diagnostics", "preliminary_carbon_balance", "run_descriptive_summary"]:
        assert list(pd.read_csv(os.path.join(out, "outputs/tables", f + ".csv")).run) == runs


def test_carbon_fractions_and_balance_arithmetic(out):
    cb = pd.read_csv(os.path.join(out, "outputs/tables/preliminary_carbon_balance.csv"))
    # recompute R2 by hand from the brief constants
    r = cb[cb.run == "R2"].iloc[0]
    assert r.C_in == pytest.approx((r.TRS_t0_measured - r.TRS_48h) * 72.066 / 180.16, abs=0.01)
    assert r.C_ethanol == pytest.approx(r.ethanol_48h * 24.022 / 46.07, abs=0.01)
    assert r.C_CO2 == pytest.approx(r.CO2_48h * 12.011 / 44.01, abs=0.01)
    assert r.C_biomass_gain == pytest.approx(r.biomass_gain * 12.011 / 24.6, abs=0.01)
    assert r.recovery_pct == pytest.approx(100 * r.C_out_total / r.C_in, abs=0.1)
    assert (cb.recovery_pct.between(90, 110)).all()   # sanity band only, not a pass/fail criterion for the data


def test_known_facts_from_raw_data(out):
    ed = pd.read_csv(os.path.join(out, "outputs/tables/endpoint_diagnostics.csv")).set_index("run")
    assert ed.loc["R7", "lactic_detected"] and ed.lactic_detected.sum() == 1
    dq = pd.read_csv(os.path.join(out, "outputs/tables/data_quality.csv"))
    assert dq.id.is_unique
    assert (dq[(dq.check == "duplicate keys")].observed.astype(int) == 0).all()
