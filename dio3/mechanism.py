"""Radical-chain mechanism of ozone decomposition in water (Staehelin-Hoigne-Buhler type).

This module is for understanding, not for the process calculation: it shows why pH, carbonate
and hydrogen peroxide change the lifetime of dissolved ozone. It is valid near 20 degC only,
because temperature dependences of the elementary steps are not well known.

Rate constants are those compiled by Lesko (2004), Chemical Effects of Acoustic Cavitation,
PhD thesis, California Institute of Technology, chapter 5, table 1, from Staehelin and Hoigne
(1982) Environ. Sci. Technol. 16, 676; Buhler, Staehelin and Hoigne (1984) J. Phys. Chem. 88,
2560; Elovitz and von Gunten (1999); and the NDRL/NIST Solution Kinetics Database. Two values
are taken from Buxton et al. (1988), J. Phys. Chem. Ref. Data 17, 513: OH + OH (2k = 1.1e10)
and OH + CO3(2-) (3.9e8).

Concentrations inside this module are in mol/L; pH and total carbonate are held constant.
"""
import numpy as np
from scipy.integrate import solve_ivp

PKW_20C = 14.17          # ionic product of water at 20 degC
PKA1_CO2 = 6.35          # carbonic acid, 25 degC
PKA2_CO2 = 10.33

SPECIES = ['O3', 'H2O2', 'HO2-', 'OH', 'HO2', 'O2-', 'O3-', 'HO3', 'CO3-']
O3, H2O2, HO2m, OH, HO2, O2m, O3m, HO3, CO3m = range(len(SPECIES))

# (reaction, rate constant) in M and s; used by rhs() below and listed on the web page
REACTIONS = [
    ('O3 + OH- -> HO2- + O2', 70.0),
    ('O3 + HO2- -> OH + O2- + O2', 2.8e6),
    ('H2O2 -> HO2- + H+', 7.9e-2),
    ('HO2- + H+ -> H2O2', 5.0e10),
    ('O3 + OH -> HO2 + O2', 1.1e8),
    ('H2O2 + OH -> HO2 + H2O', 2.7e7),
    ('HO2- + OH -> HO2 + OH-', 7.5e9),
    ('HO2 -> O2- + H+', 7.9e5),
    ('O2- + H+ -> HO2', 5.0e10),
    ('O3 + O2- -> O3- + O2', 1.6e9),
    ('HO3 -> O3- + H+', 3.3e2),
    ('O3- + H+ -> HO3', 5.2e10),
    ('HO3 -> OH + O2', 1.1e5),
    ('OH + HCO3- -> CO3- + H2O', 1.2e7),
    ('OH + CO3(2-) -> CO3- + OH-', 3.9e8),
    ('CO3- + HO2- -> CO3(2-) + HO2', 3.0e7),
    ('CO3- + H2O2 -> HCO3- + HO2', 4.3e5),
    ('OH + OH -> H2O2', 5.5e9),
    ('OH + O2- -> O2 + OH-', 1.1e10),
    ('HO2 + HO2 -> H2O2 + O2', 9.8e5),
    ('OH + HO2 -> H2O + O2', 3.7e10),
    ('HO2 + O2- (+H2O) -> H2O2 + O2 + OH-', 9.7e7),
    ('CO3- + CO3- -> products', 2.0e7),
    ('CO3- + O3- -> CO3(2-) + O3', 6.0e7),
    ('CO3- + O3 -> products', 1.0e5),
    ('CO3- + HO3 -> HCO3- + O3', 1.0e8),
]
K = [k for _, k in REACTIONS]


def carbonate_species(ct, pH):
    """HCO3- and CO3(2-) in mol/L for total carbonate ct (mol/L) at fixed pH."""
    h = 10.0 ** -pH
    k1, k2 = 10.0 ** -PKA1_CO2, 10.0 ** -PKA2_CO2
    d = h * h + k1 * h + k1 * k2
    return ct * k1 * h / d, ct * k1 * k2 / d


def rhs_factory(pH, ct=0.0, scale=None):
    h = 10.0 ** -pH
    oh_ion = 10.0 ** (pH - PKW_20C)
    hco3, co3 = carbonate_species(ct, pH)
    k = K if scale is None else [ki * scale.get(i, 1.0) for i, ki in enumerate(K)]

    def rhs(t, y):
        y = np.maximum(y, 0.0)
        o3, h2o2, ho2m, oh, ho2, o2m, o3m, ho3, co3m = y
        r = [
            k[0] * o3 * oh_ion,
            k[1] * o3 * ho2m,
            k[2] * h2o2,
            k[3] * ho2m * h,
            k[4] * o3 * oh,
            k[5] * h2o2 * oh,
            k[6] * ho2m * oh,
            k[7] * ho2,
            k[8] * o2m * h,
            k[9] * o3 * o2m,
            k[10] * ho3,
            k[11] * o3m * h,
            k[12] * ho3,
            k[13] * oh * hco3,
            k[14] * oh * co3,
            k[15] * co3m * ho2m,
            k[16] * co3m * h2o2,
            k[17] * oh * oh,
            k[18] * oh * o2m,
            k[19] * ho2 * ho2,
            k[20] * oh * ho2,
            k[21] * ho2 * o2m,
            k[22] * co3m * co3m,
            k[23] * co3m * o3m,
            k[24] * co3m * o3,
            k[25] * co3m * ho3,
        ]
        d = np.zeros(9)
        d[O3] = -r[0] - r[1] - r[4] - r[9] + r[23] - r[24] + r[25]
        d[H2O2] = -r[2] + r[3] - r[5] - r[16] + r[17] + r[19] + r[21]
        d[HO2m] = r[0] - r[1] + r[2] - r[3] - r[6] - r[15]
        d[OH] = r[1] - r[4] - r[5] - r[6] + r[12] - r[13] - r[14] - 2 * r[17] - r[18] - r[20]
        d[HO2] = r[4] + r[5] + r[6] - r[7] + r[8] + r[15] + r[16] - 2 * r[19] - r[20] - r[21]
        d[O2m] = r[1] + r[7] - r[8] - r[9] - r[18] - r[21]
        d[O3m] = r[9] + r[10] - r[11] - r[23]
        d[HO3] = -r[10] + r[11] - r[12] - r[25]
        d[CO3m] = r[13] + r[14] - r[15] - r[16] - 2 * r[22] - r[23] - r[24] - r[25]
        return d

    return rhs


def half_life(c0_molL, pH, ct=0.0, h2o2_0=0.0, t_max=1e7, scale=None):
    """Half-life (s) of ozone from the mechanism at 20 degC."""
    y0 = np.zeros(9)
    y0[O3] = c0_molL
    y0[H2O2] = h2o2_0
    rhs = rhs_factory(pH, ct, scale)

    def half(t, y):
        return y[O3] - 0.5 * c0_molL
    half.terminal = True
    half.direction = -1
    sol = solve_ivp(rhs, (0.0, t_max), y0, method='LSODA', rtol=1e-8, atol=1e-20, events=half)
    if sol.t_events[0].size:
        return float(sol.t_events[0][0])
    return float('inf')


def decay_curve(c0_molL, pH, t_end, ct=0.0, h2o2_0=0.0, n=200):
    """Ozone against time from the mechanism: returns times (s) and O3 (mol/L)."""
    y0 = np.zeros(9)
    y0[O3] = c0_molL
    y0[H2O2] = h2o2_0
    ts = np.linspace(0.0, t_end, n)
    sol = solve_ivp(rhs_factory(pH, ct), (0.0, t_end), y0, method='LSODA', rtol=1e-8, atol=1e-20, t_eval=ts)
    return sol.t, sol.y[O3]
