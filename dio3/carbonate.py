"""pH of ultrapure water that holds dissolved CO2 (closed charge balance, 25 degC constants).

CO2 is added to ultrapure water to lower its resistivity, for example in photomask cleaning,
and lowers the pH, which slows ozone decomposition. Constants: Henry's law for CO2 from
properties.henry_co2; pKa1 = 6.35, pKa2 = 10.33 and pKw = 14.00 at 25 degC (Stumm and Morgan,
Aquatic Chemistry, 3rd ed., 1996).

A resistivity meter is the practical way to see the pH of such water on a tool, because glass pH
electrodes drift in ultrapure water. resistivity_co2 gives the reading to expect, at 25 degC as
meters report it, from the limiting molar conductivities of H+ and OH- (349.19 and 199.24
S cm2/mol, Light et al. 2005, Electrochem. Solid-State Lett. 8, E16) and of HCO3- (44.5 S cm2/mol,
CRC Handbook of Chemistry and Physics). The ions are so dilute that their limiting values apply.
"""
import math

from .properties import henry_co2

PKA1, PKA2, PKW = 6.35, 10.33, 14.00
LAMBDA_H, LAMBDA_OH, LAMBDA_HCO3 = 349.19, 199.24, 44.5     # S cm2/mol at 25 degC


def ph_from_co2(p_co2, T=298.15):
    """pH of pure water in equilibrium with CO2 at partial pressure p_co2 (Pa)."""
    co2 = henry_co2(T) * p_co2 * 1e-3          # mol/L of dissolved CO2
    k1, k2, kw = 10 ** -PKA1, 10 ** -PKA2, 10 ** -PKW
    lo, hi = 1e-14, 1.0
    for _ in range(200):                       # bisection on log [H+]
        h = math.sqrt(lo * hi)
        f = h - (k1 * co2 / h + 2 * k1 * k2 * co2 / h ** 2 + kw / h)
        if f > 0:
            hi = h
        else:
            lo = h
    return -math.log10(math.sqrt(lo * hi))


def total_carbonate(p_co2, T=298.15):
    """Total dissolved carbonate (mol/L) in that water."""
    co2 = henry_co2(T) * p_co2 * 1e-3
    h = 10 ** -ph_from_co2(p_co2, T)
    k1, k2 = 10 ** -PKA1, 10 ** -PKA2
    return co2 * (1 + k1 / h + k1 * k2 / h ** 2)


def co2_pressure_for_ph(pH, T=298.15):
    """CO2 partial pressure (Pa) that brings pure water to this pH; the inverse of ph_from_co2.
    CO2 cannot raise the pH above 7, so 0 is returned there."""
    h = 10.0 ** -pH
    k1, k2, kw = 10 ** -PKA1, 10 ** -PKA2, 10 ** -PKW
    if h * h <= kw:
        return 0.0
    co2 = (h - kw / h) / (k1 / h + 2 * k1 * k2 / h ** 2)       # mol/L of dissolved CO2
    return co2 * 1e3 / henry_co2(T)


def resistivity_co2(pH):
    """Resistivity in MOhm cm at 25 degC of ultrapure water brought to this pH with CO2 alone.
    Carbonate ions are left out (below 0.05 % of the bicarbonate at pH 7). Above pH 7, where CO2
    cannot set the pH, the result is nan."""
    if pH > 7.0 + 1e-9:
        return math.nan
    h = 10.0 ** -pH
    oh = 10.0 ** -PKW / h
    hco3 = max(h - oh, 0.0)
    kappa = (LAMBDA_H * h + LAMBDA_OH * oh + LAMBDA_HCO3 * hco3) * 1e-3        # S/cm
    return 1e-6 / kappa
