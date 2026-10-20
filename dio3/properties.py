"""Physical properties of water and dissolved ozone.

Every correlation is taken from the literature cited next to it. Temperatures are in kelvin,
everything else in SI units unless the name says otherwise.
"""
import math

R = 8.314462618          # gas constant, J/(mol K)
P_ATM = 101325.0         # Pa
T_ZERO = 273.15          # K
M_O3 = 47.998e-3         # kg/mol
M_O2 = 31.998e-3         # kg/mol
MOLAR_VOLUME_NORMAL = R * T_ZERO / P_ATM   # m3/mol of an ideal gas at 0 degC and 1 atm (22.414 L/mol)


def celsius(T):
    return T - T_ZERO


def water_density(T):
    """Density of liquid water at 0.1 MPa in kg/m3, 0 to 150 degC.

    Kell, G. S. (1975) J. Chem. Eng. Data 20, 97-105.
    """
    t = celsius(T)
    num = (999.83952 + 16.945176 * t - 7.9870401e-3 * t ** 2 - 46.170461e-6 * t ** 3
           + 105.56302e-9 * t ** 4 - 280.54253e-12 * t ** 5)
    return num / (1.0 + 16.879850e-3 * t)


def water_viscosity(T):
    """Dynamic viscosity of liquid water at 0.1 MPa in Pa s.

    Kestin, Sokolov and Wakeham (1978) J. Phys. Chem. Ref. Data 7, 941, in the form given by
    Kestin, Khalifa and Correia (1981) J. Phys. Chem. Ref. Data 10, 71:
    log10(mu/mu20) = sum a_i (20 - t)^i / (96 + t), mu20 = 1002.0 uPa s.
    Stated for 20 to 150 degC; between 0 and 20 degC it still agrees with tabulated values to
    about 0.2 % (see tests).
    """
    t = celsius(T)
    d = 20.0 - t
    s = 1.2378 * d - 1.303e-3 * d ** 2 + 3.06e-6 * d ** 3 + 2.55e-8 * d ** 4
    return 1002.0e-6 * 10.0 ** (s / (96.0 + t))


def kinematic_viscosity(T):
    return water_viscosity(T) / water_density(T)


def ozone_diffusivity(T):
    """Diffusion coefficient of ozone in water in m2/s.

    Johnson, P. N. and Davis, R. A. (1996) J. Chem. Eng. Data 41, 1485-1487:
    D = 0.011 cm2/s exp(-1896 K / T).
    """
    return 1.1e-6 * math.exp(-1896.0 / T)


def henry_ozone(T):
    """Henry's law solubility of ozone in water, Hcp = c / p, in mol/(m3 Pa).

    Hcp(298.15 K) = 1.0e-4 mol/(m3 Pa) and d ln Hcp / d(1/T) = 2800 K, as evaluated by
    Burkholder et al. (2019), JPL Publication 19-5, and listed by Sander (2023),
    Atmos. Chem. Phys. 23, 10901. Single measurements scatter by about +-20 % around it.
    """
    return 1.0e-4 * math.exp(2800.0 * (1.0 / T - 1.0 / 298.15))


def henry_co2(T):
    """Henry's law solubility of CO2 in water in mol/(m3 Pa).

    Hcp(298.15 K) = 3.4e-4 mol/(m3 Pa), d ln Hcp / d(1/T) = 2300 K (Burkholder et al. 2019,
    as listed by Sander 2023).
    """
    return 3.4e-4 * math.exp(2300.0 * (1.0 / T - 1.0 / 298.15))


# ---------------------------------------------------------------- unit conversions
def mole_fraction_from_g_per_Nm3(c):
    """Ozone mole fraction in the generator gas from its concentration in g per normal m3."""
    return (c / (M_O3 * 1e3)) * MOLAR_VOLUME_NORMAL


def mole_fraction_from_wt(w):
    """Ozone mole fraction from its mass fraction in an ozone/oxygen mixture."""
    n3, n2 = w / M_O3, (1.0 - w) / M_O2
    return n3 / (n3 + n2)


def wt_from_mole_fraction(y):
    m3, m2 = y * M_O3, (1.0 - y) * M_O2
    return m3 / (m3 + m2)


def g_per_Nm3_from_mole_fraction(y):
    return y / MOLAR_VOLUME_NORMAL * M_O3 * 1e3


def mg_per_L(c):
    """Dissolved ozone in mg/L (the 'ppm' used in practice) from mol/m3."""
    return c * M_O3 * 1e3


def mol_per_m3(ppm):
    """Dissolved ozone in mol/m3 from mg/L."""
    return ppm / (M_O3 * 1e3)


def equilibrium_ozone(T, y, pressure=P_ATM):
    """Dissolved ozone (mol/m3) in equilibrium with gas of ozone mole fraction y at total pressure."""
    return henry_ozone(T) * y * pressure
