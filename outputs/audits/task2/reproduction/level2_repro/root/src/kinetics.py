"""Level 1 kinetic model ("Model A-prime") for the molasses batch fermentations.

Equations are written out explicitly; SciPy is used only to integrate them.

State variables (g/L; constant broth volume; time in h)
    X  yeast biomass (dry weight)
    S  residual total reducing sugars, as glucose (TRS)
    P  ethanol
    C  cumulative CO2 released since inoculation

Rate expressions
    k(T)  = thermal multiplier on the 30 C rates: k(30) = 1, k(34) = k34, k(37) = k37,
            piecewise-linear in between, NO extrapolation outside 30-37 C
    m(S)  = S / (K_s + S)                               Monod saturation (-), K_s fixed
    mu    = mu_max * k(T) * m(S) * (1 - X / X_max)      specific growth rate (1/h)
    q_S   = q_max  * k(T) * m(S) * (1 - P / P_max)^n    specific catabolic sugar uptake (g/g/h)
            with n = 1 fixed (linear ethanol inhibition), P_max common to all temperatures

ODEs
    dX/dt = mu * X
    dS/dt = -SUGAR_PER_BIOMASS * mu * X  -  q_S * X
    dP/dt =  Y_P * q_S * X
    dC/dt =  rho_CO2 * dP/dt            (CO2 is an output tied to ethanol, no kinetic parameter)

SUGAR_PER_BIOMASS = (12.011/24.6) / (72.066/180.16) = 1.2206 g glucose per g biomass is the
glucose carbon needed to build CH1.8O0.5N0.2 biomass (24.6 g per C-mol, brief s3). Fixed.
Glycerol, lactic acid and pH are NOT states; glycerol is handled in the Level 2 carbon balance.

Numerical safeguards (not data changes)
    * X, S, P are clipped at 0 inside rate expressions; (1 - X/X_max) and (1 - P/P_max) are
      clipped at 0, so no rate can be negative.
    * LSODA with rtol 1e-9, atol 1e-11. If integration fails, simulate() returns None and the
      caller must handle it (fit.py applies a counted penalty).
"""
from __future__ import annotations

from collections import OrderedDict

import numpy as np
from scipy.integrate import solve_ivp

C_FRAC_BIOMASS = 12.011 / 24.6            # g C / g biomass (brief: 24.6 g per C-mol)
C_FRAC_GLUCOSE = 72.066 / 180.16          # g C / g glucose
SUGAR_PER_BIOMASS = C_FRAC_BIOMASS / C_FRAC_GLUCOSE   # 1.2206 g glucose / g biomass
RHO_STOICH = 44.01 / 46.07                # 0.955 g CO2 per g ethanol (C6H12O6 -> 2 EtOH + 2 CO2)
Y_P_STOICH = 2 * 46.07 / 180.16           # 0.511 g ethanol per g glucose

T_LEVELS = (30.0, 34.0, 37.0)             # observed temperature levels

# name: (start value, lower bound, upper bound, unit, description)
PARAMS = OrderedDict([
    ("mu_max",  (0.30, 0.05, 1.50, "1/h",    "max specific growth rate at 30 C")),
    ("X_max",   (11.5, 8.0, 20.0, "g/L",     "biomass carrying capacity (saturation term)")),
    ("q_max",   (1.00, 0.20, 5.00, "g/g/h",  "max specific catabolic sugar uptake at 30 C")),
    ("P_max",   (150., 108., 500., "g/L",    "ethanol at which uptake would stop (linear inhibition); lower bound just above 107.8 g/L, the highest ethanol observed in training")),
    ("Y_P",     (0.47, 0.30, 0.511, "g/g",   "ethanol per g catabolised sugar (<= 0.511 stoichiometric)")),
    ("rho_CO2", (0.96, 0.80, 1.20, "g/g",    "CO2 released per g ethanol formed (0.955 stoichiometric)")),
    ("k34",     (1.00, 0.20, 1.50, "-",      "rate multiplier at 34 C relative to 30 C (applies to mu and q)")),
    ("k37",     (0.80, 0.20, 1.50, "-",      "rate multiplier at 37 C relative to 30 C (applies to mu and q)")),
])
PARAM_NAMES = list(PARAMS.keys())
LOWER = np.array([PARAMS[k][1] for k in PARAM_NAMES])
UPPER = np.array([PARAMS[k][2] for k in PARAM_NAMES])
START = np.array([PARAMS[k][0] for k in PARAM_NAMES])

# fixed a priori (NOT estimated; sensitivity analyses in fit.py)
FIXED_DEFAULT = {"K_s": 1.0, "n_inh": 1.0}
FIXED_INFO = {
    "K_s":   ("g/L", "Monod constant; sparse low-sugar data cannot determine it; fixed a priori, sensitivity 0.2-5"),
    "n_inh": ("-",   "ethanol-inhibition exponent fixed at 1 (linear), per user decision"),
}


def unpack(theta):
    return dict(zip(PARAM_NAMES, theta))


def thermal_multiplier(T, k34, k37):
    """Rate multiplier relative to 30 C. Piecewise linear through (30,1), (34,k34), (37,k37).
    Raises ValueError outside 30-37 C: the data do not support extrapolation."""
    if T < T_LEVELS[0] - 1e-9 or T > T_LEVELS[-1] + 1e-9:
        raise ValueError(f"T = {T} C is outside the observed 30-37 C range")
    return float(np.interp(T, T_LEVELS, [1.0, k34, k37]))


def rates(y, T, p, fixed):
    """Return (mu, q_S, dX, dS, dP, dC) for state y = (X, S, P, C)."""
    X, S, P, _ = y
    Xp, Sp, Pp = max(X, 0.0), max(S, 0.0), max(P, 0.0)
    kT = thermal_multiplier(T, p["k34"], p["k37"])
    mon = Sp / (fixed["K_s"] + Sp)
    mu = p["mu_max"] * kT * mon * max(1.0 - Xp / p["X_max"], 0.0)
    q = p["q_max"] * kT * mon * max(1.0 - Pp / p["P_max"], 0.0) ** fixed["n_inh"]
    dX = mu * Xp
    dS = -SUGAR_PER_BIOMASS * dX - q * Xp
    dP = p["Y_P"] * q * Xp
    dC = p["rho_CO2"] * dP
    return mu, q, dX, dS, dP, dC


def simulate(T, S0, X0, t, theta, fixed=None, rtol=1e-9, atol=1e-11):
    """Integrate the model. Returns array (len(t), 4) of X, S, P, C, or None on failure.
    t must be increasing and start at 0. Initial state: (X0, S0, 0, 0)."""
    fixed = dict(FIXED_DEFAULT) if fixed is None else {**FIXED_DEFAULT, **fixed}
    p = unpack(theta)
    t = np.asarray(t, float)
    thermal_multiplier(T, p["k34"], p["k37"])      # raises early if T is out of range

    def rhs(_t, y):
        r = rates(y, T, p, fixed)
        return [r[2], r[3], r[4], r[5]]

    try:
        sol = solve_ivp(rhs, (t[0], t[-1]), [X0, S0, 0.0, 0.0], method="LSODA",
                        t_eval=t, rtol=rtol, atol=atol)
    except ValueError:
        raise
    except Exception:
        return None
    if (not sol.success) or sol.y.shape[1] != len(t) or not np.all(np.isfinite(sol.y)):
        return None
    return sol.y.T
