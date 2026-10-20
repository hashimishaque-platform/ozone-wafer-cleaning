"""Self-decomposition of dissolved ozone in ultrapure water: the engineering rate law.

    -d[O3]/dt = k1(T) [O3] + k2(pH, T) [O3]^2

The first-order term describes acidic water, where ozone decays slowly and in first order:
De Smedt et al. (2002), Ozone Sci. Eng. 24, 379-390, report a half-life of about 3 to 4 h at
pH 1.8 to 3 and room temperature (initial 10 mg/L) and an activation energy of
39.6 +- 4.1 kJ/mol between 19 and 67 degC (pH 1.8).

The second-order term is the hydroxide-initiated decay that dominates near neutral pH:
Ershov and Morozov (2009), Russ. J. Phys. Chem. A 83, 1295-1299, found second-order kinetics
for pH 1 to 8 with log10 k = -2.66 + 0.49 pH at 19 degC above about pH 3, and an activation
energy of 76.0 +- 8.3 kJ/mol. k is taken in L/(mol s). The pH exponent 0.49 is close to the
0.55 power of [OH-] of Gurol and Singer (1982), Environ. Sci. Technol. 16, 377.

Concentrations are in mol/m3 and times in seconds.
"""
import math

from .properties import R

T_ACID_REF = 295.15            # 'room temperature' of De Smedt et al., taken as 22 degC
HALF_LIFE_ACID_REF = 3.5 * 3600.0
EA_ACID = 39.6e3               # J/mol
T_BASE_REF = 292.15            # 19 degC, Ershov and Morozov
EA_BASE = 76.0e3               # J/mol
PH_RANGE = (2.0, 8.0)          # range the two sources cover between them


def k1(T):
    """First-order rate constant in 1/s."""
    return math.log(2.0) / HALF_LIFE_ACID_REF * math.exp(-EA_ACID / R * (1.0 / T - 1.0 / T_ACID_REF))


def k2(pH, T):
    """Second-order rate constant in m3/(mol s)."""
    k_L = 10.0 ** (-2.66 + 0.49 * pH)            # L/(mol s) at 19 degC
    return 1e-3 * k_L * math.exp(-EA_BASE / R * (1.0 / T - 1.0 / T_BASE_REF))


def rate(c, pH, T):
    """Decomposition rate in mol/(m3 s) and its derivative with respect to c."""
    a, b = k1(T), k2(pH, T)
    return a * c + b * c * c, a + 2.0 * b * c


def concentration_after(c0, t, pH, T):
    """Exact solution of dc/dt = -k1 c - k2 c^2 after time t."""
    a, b = k1(T), k2(pH, T)
    if t <= 0 or c0 <= 0:
        return c0
    e = math.exp(-a * t)
    return a * c0 * e / (a + b * c0 * (1.0 - e))


def half_life(c0, pH, T):
    """Time in s for the concentration to fall from c0 to c0/2."""
    a, b = k1(T), k2(pH, T)
    return math.log((2.0 * a + b * c0) / (a + b * c0)) / a


def time_to_fraction(c0, fraction, pH, T):
    """Time in s for the concentration to fall from c0 to fraction * c0 (0 < fraction < 1);
    time_to_fraction(c0, 0.5, ...) is the half-life."""
    a, b = k1(T), k2(pH, T)
    x = fraction * (a + b * c0) / (a + fraction * b * c0)
    return -math.log(x) / a
