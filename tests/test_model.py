"""Checks against published values and against exact limits. Run with: python3 -m pytest -q"""
import math

import pytest

from dio3 import properties as P, decomposition as Dc, mechanism as M, film as F
from dio3.carbonate import ph_from_co2, co2_pressure_for_ph, resistivity_co2
from dio3.calibration import literature_table
from dio3.process import Process, simulate
from dio3.resist import Resist

# CRC Handbook of Chemistry and Physics values for water at 0.1 MPa
CRC_DENSITY = {4: 999.972, 25: 997.047, 50: 988.03, 80: 971.79, 100: 958.35}
CRC_VISCOSITY_MPAS = {0: 1.793, 10: 1.307, 20: 1.002, 25: 0.890, 40: 0.653, 60: 0.466, 80: 0.354, 100: 0.282}


def test_water_density():
    for t, rho in CRC_DENSITY.items():
        assert P.water_density(t + 273.15) == pytest.approx(rho, rel=2e-4)


def test_water_viscosity():
    for t, mu in CRC_VISCOSITY_MPAS.items():
        assert P.water_viscosity(t + 273.15) * 1e3 == pytest.approx(mu, rel=4e-3)


def test_henry_reference_value():
    assert P.henry_ozone(298.15) == pytest.approx(1.0e-4)


def test_generator_gas_gives_typical_ozone_water():
    # 9 wt% ozone (Abe et al. 2003) at 1 atm and 25 degC: they quote 10 to 30 ppm as typical
    y = P.mole_fraction_from_wt(0.09)
    ppm = P.mg_per_L(P.equilibrium_ozone(298.15, y))
    assert 25.0 < ppm < 32.0


def test_solubility_ratio_5_to_25_C():
    # NEC patent US 6,559,064 (Fig. 6): about 120 ppm at 5 degC and 65 ppm at 25 degC
    ratio = P.henry_ozone(278.15) / P.henry_ozone(298.15)
    assert ratio == pytest.approx(120.0 / 65.0, rel=0.08)


def test_diffusivity_and_stokes_einstein():
    assert P.ozone_diffusivity(293.15) == pytest.approx(1.71e-9, rel=0.01)
    T1, T2 = 298.15, 333.15
    se = P.ozone_diffusivity(T1) * (T2 / P.water_viscosity(T2)) / (T1 / P.water_viscosity(T1))
    assert P.ozone_diffusivity(T2) == pytest.approx(se, rel=0.10)


def test_ph_of_air_equilibrated_water():
    # De Smedt et al. (2002): ultrapure water exposed to air reaches pH of about 5.6
    assert ph_from_co2(42.0) == pytest.approx(5.6, abs=0.05)


def test_resistivity_of_ultrapure_water():
    # Light et al. (2005), Electrochem. Solid-State Lett. 8, E16: 18.186 MOhm cm at 25 degC
    assert resistivity_co2(7.0) == pytest.approx(18.186, rel=5e-3)


def test_co2_pressure_is_the_inverse_of_ph():
    for p_co2 in (42.0, 1013.25, 1.0e4):
        assert co2_pressure_for_ph(ph_from_co2(p_co2)) == pytest.approx(p_co2, rel=1e-9)
    assert co2_pressure_for_ph(7.5) == 0.0


def test_acidic_half_life():
    # De Smedt et al. (2002): about 3 to 4 h at pH 1.8 to 3, room temperature, 10 mg/L
    t = Dc.half_life(P.mol_per_m3(10.0), 2.5, 295.15) / 3600.0
    assert 3.0 <= t <= 4.0


def test_time_to_fraction():
    c0 = P.mol_per_m3(25.0)
    assert Dc.time_to_fraction(c0, 0.5, 6.5, 313.15) == pytest.approx(Dc.half_life(c0, 6.5, 313.15), rel=1e-12)
    t = Dc.time_to_fraction(c0, 0.9, 6.5, 313.15)
    assert Dc.concentration_after(c0, t, 6.5, 313.15) == pytest.approx(0.9 * c0, rel=1e-12)


def test_engineering_law_against_mechanism_near_neutral_pH():
    # The radical mechanism with air-level carbonate and the empirical law agree within a factor of 2
    c0 = P.mol_per_m3(10.0)
    for pH in (6.0, 7.0):
        te = Dc.half_life(c0, pH, 293.15)
        tm = M.half_life(c0 / 1e3, pH, ct=1.4e-5)
        assert 0.5 < tm / te < 2.0


def test_film_thickness_matches_lepehin_riabchuk():
    Q, w, nu, r = 2.5e-5, 52.36, 1.0e-6, 0.075
    h = F.film_thickness(r, Q, w, nu)
    assert h == pytest.approx(0.782 * (nu * Q) ** (1 / 3) * w ** (-2 / 3) * r ** (-2 / 3), rel=1e-3)


def _film(**kw):
    T = 298.15
    base = dict(Q=2.5e-5, omega=52.36, R=0.15, c_in=0.6, nu=P.kinematic_viscosity(T), D=P.ozone_diffusivity(T),
                k1=0.0, k2=0.0)
    base.update(kw)
    return F.solve(F.FilmInput(**base))


def test_film_inert_wall_keeps_concentration():
    r = _film(c_surface=None, k_wall=0.0)
    assert max(abs(x - 0.6) for x in r.c_mean) < 1e-12


def test_film_well_mixed_limit():
    k, Q, w, nu = 0.02, 2.5e-5, 52.36, P.kinematic_viscosity(298.15)
    r = _film(D=1e-2, k1=k, c_surface=None, k_wall=0.0, n_steps=800)
    A = F.film_thickness(1.0, Q, w, nu)           # h r^(2/3) is constant
    tau = 2 * math.pi / Q * A * 0.75 * (0.15 ** (4 / 3) - 0.005 ** (4 / 3))
    assert r.c_mean[-1] / 0.6 == pytest.approx(math.exp(-k * tau), rel=1e-5)


def test_film_balance_and_grid():
    a = _film(k1=1e-4, k2=1e-3, c_surface=0.0)
    b = _film(k1=1e-4, k2=1e-3, c_surface=0.0, n_layers=192, n_steps=1600)
    assert abs(a.budget['closure']) < 1e-12 * a.budget['in']
    fa = F.area_average(a.r, a.wall_flux, 0.01)
    fb = F.area_average(b.r, b.wall_flux, 0.01)
    assert fa == pytest.approx(fb, rel=5e-3)


def test_strip_rate_trends():
    base = dict(nozzle_ppm=30.0, profile=None)
    rate = lambda **kw: simulate(Process(nozzle_ppm=kw.pop('ppm', 30.0), **kw), profile_radii=())['strip_mean']
    assert rate(rpm=1000) > rate(rpm=500) > rate(rpm=100)            # spin speed matters (Dussault et al.)
    assert rate(T=333.15) > rate(T=298.15) > rate(T=283.15)          # warmer at fixed ozone (Gottschalk 2004)
    assert rate(ppm=60.0) == pytest.approx(2.0 * rate(ppm=30.0), rel=0.01)   # transport-limited: linear


def test_default_yield_within_literature_range():
    for row in literature_table():
        assert 0.6 < row['g_ozone_per_g_resist'] < 1.7


def test_bare_wafer_takes_up_no_ozone():
    # stage 2 of the test plan: an inert surface, so the ozone only decays, escapes or runs off
    r = simulate(Process(resist=Resist(k_wall_ref=0.0)), profile_radii=())
    b = r['budget']
    assert b['resist'] == 0.0 and r['strip_mean'] == 0.0
    assert abs(b['closure']) < 1e-12 * b['in']
    assert b['edge'] > 0 and b['gas_exchange'] < 0


def test_second_dispense_ring_conserves_ozone():
    # liquid of the same concentration added on top of a closed, inert film changes nothing
    inp = F.FilmInput(Q=2.5e-5, omega=52.36, R=0.15, c_in=0.6, nu=1e-6, D=1.7e-9, k1=0.0, k2=0.0, c_surface=None,
                      k_wall=0.0, r_inject=0.08, Q_inject=1e-5, c_inject=0.6)
    r = F.solve(inp)
    assert max(abs(x - 0.6) for x in r.c_mean) < 1e-12
    # and with uptake, decay and gas exchange the balance still closes
    res = simulate(Process(ring_radius=0.07, ring_flow_lpm=0.5), profile_radii=())
    assert abs(res['budget']['closure']) < 1e-12 * res['budget']['in']
