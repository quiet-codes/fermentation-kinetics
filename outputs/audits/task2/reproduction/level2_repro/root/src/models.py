"""Level 2 model family. Level 1's kinetics.py is NOT modified; M0 here must reproduce it exactly.

Common structure (see kinetics.py): states X, S, P, C (g/L); constant volume; time in h
    mon   = S/(K_s + S)
    kT    = rate multiplier (1 at 30 C, k34 at 34 C, k37 at 37 C; linear between; error outside 30-37 C)
    Pm(T) = P_max                         (variants without pmax_T)
          = P_max * exp(-beta_P*(T-30))   (variants with pmax_T; P_max is then the 30 C value)
    inh   = max(1 - P/Pm(T), 0)^n         (n fixed = 1 unless n_free)
    mu    = mu_max*kT*mon*max(1 - X/X_max, 0) * (inh if growth_inh else 1)
    q_S   = q_max *kT*mon*inh
    dX/dt = mu X ;  dS/dt = -1.2206 mu X - q_S X ;  dP/dt = Y_P q_S X ;  dC/dt = rho_CO2 dP/dt
Variants (D-23): M0 Level 1 baseline; M1 k34 = 1; M2 + P_max(T); M3 + free n; M4 growth also inhibited by ethanol;
M5 = M2 + M3; M6 = M2 + M4.
"""
from collections import OrderedDict

import numpy as np
from scipy.integrate import solve_ivp

import kinetics as K

VARIANTS = OrderedDict([
    ("M0", dict(label="Level 1 baseline", pmax_T=False, n_free=False, growth_inh=False, k34_fixed=False)),
    ("M1", dict(label="baseline with k34 = 1", pmax_T=False, n_free=False, growth_inh=False, k34_fixed=True)),
    ("M2", dict(label="baseline + P_max(T)", pmax_T=True, n_free=False, growth_inh=False, k34_fixed=False)),
    ("M3", dict(label="baseline + estimated exponent n", pmax_T=False, n_free=True, growth_inh=False, k34_fixed=False)),
    ("M4", dict(label="ethanol factor also on growth", pmax_T=False, n_free=False, growth_inh=True, k34_fixed=False)),
    ("M5", dict(label="P_max(T) + estimated n", pmax_T=True, n_free=True, growth_inh=False, k34_fixed=False)),
    ("M6", dict(label="P_max(T) + ethanol factor on growth", pmax_T=True, n_free=False, growth_inh=True, k34_fixed=False)),
])
EXTRA = OrderedDict([
    ("beta_P", (0.01, -0.02, 0.06, "1/C", "log-slope of P_max with temperature (P_max falls with T if > 0)")),
    ("n_inh", (1.0, 0.3, 4.0, "-", "ethanol-inhibition exponent")),
])
FIXED_DEFAULT = dict(K.FIXED_DEFAULT)


def spec(variant):
    v = VARIANTS[variant]
    names, start, lo, hi, unit, desc = [], [], [], [], [], []
    for n, (s, l, h, u, d) in K.PARAMS.items():
        if n == "k34" and v["k34_fixed"]:
            continue
        names.append(n); start.append(s); lo.append(l); hi.append(h); unit.append(u); desc.append(d)
    for n, flag in (("beta_P", v["pmax_T"]), ("n_inh", v["n_free"])):
        if flag:
            s, l, h, u, d = EXTRA[n]
            names.append(n); start.append(s); lo.append(l); hi.append(h); unit.append(u); desc.append(d)
    return names, np.array(start), np.array(lo), np.array(hi), unit, desc


def rates(y, T, p, fixed, v):
    X, S, P, _ = y
    Xp, Sp, Pp = max(X, 0.0), max(S, 0.0), max(P, 0.0)
    kT = K.thermal_multiplier(T, p.get("k34", 1.0), p["k37"])
    mon = Sp / (fixed["K_s"] + Sp)
    pm = p["P_max"] * np.exp(-p["beta_P"] * (T - 30.0)) if v["pmax_T"] else p["P_max"]
    n = p["n_inh"] if v["n_free"] else fixed["n_inh"]
    inh = max(1.0 - Pp / pm, 0.0) ** n
    mu = p["mu_max"] * kT * mon * max(1.0 - Xp / p["X_max"], 0.0) * (inh if v["growth_inh"] else 1.0)
    q = p["q_max"] * kT * mon * inh
    dX = mu * Xp
    dS = -K.SUGAR_PER_BIOMASS * dX - q * Xp
    dP = p["Y_P"] * q * Xp
    return mu, q, dX, dS, dP, p["rho_CO2"] * dP


def simulate(variant, T, S0, X0, t, theta, fixed=None, rtol=1e-9, atol=1e-11):
    """Returns (len(t), 4) array X,S,P,C (clipped at 0) or None on solver failure."""
    v = VARIANTS[variant]
    fixed = dict(FIXED_DEFAULT) if fixed is None else {**FIXED_DEFAULT, **fixed}
    names = spec(variant)[0]
    p = dict(zip(names, theta))
    t = np.asarray(t, float)
    K.thermal_multiplier(T, p.get("k34", 1.0), p["k37"])           # raises if T outside 30-37 C

    def rhs(_t, y):
        r = rates(y, T, p, fixed, v)
        return [r[2], r[3], r[4], r[5]]

    try:
        sol = solve_ivp(rhs, (t[0], t[-1]), [X0, S0, 0.0, 0.0], method="LSODA", t_eval=t, rtol=rtol, atol=atol)
    except ValueError:
        raise
    except Exception:
        return None
    if (not sol.success) or sol.y.shape[1] != len(t) or not np.all(np.isfinite(sol.y)):
        return None
    return np.maximum(sol.y.T, 0.0)
