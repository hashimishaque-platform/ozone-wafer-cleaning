"""Writes the data the web page shows but does not compute itself.

    python3 make_data.py      -> checks.json (the checks table) and mechanism.json (Figure 6)

The checks are the same as in tests/test_model.py, with the numbers written out.
"""
import json
import math
from pathlib import Path

import numpy as np

from dio3 import properties as P, decomposition as Dc, mechanism as M, film as F
from dio3.carbonate import ph_from_co2, total_carbonate, resistivity_co2
from dio3.calibration import literature_table
from dio3.process import Process, simulate

here = Path(__file__).resolve().parent
rows = []


def add(group, label, expected, model, source):
    rows.append({'group': group, 'label': label, 'expected': expected, 'model': model, 'source': source})
    print(f'{group} | {label} | {expected} | {model}')


def pct(a, b):
    return f'{100 * (a / b - 1):+.1f} %'.replace('-', '−')


# ---------------------------------------------------------------- properties
G = 'Properties of water and ozone'
add(G, 'Density of water at 25 °C and 80 °C (kg/m³)', '997.05 and 971.79',
    f'{P.water_density(298.15):.2f} and {P.water_density(353.15):.2f}', 'CRC Handbook; model: Kell (1975)')
add(G, 'Viscosity of water at 25 °C and 80 °C (mPa s)', '0.890 and 0.354',
    f'{P.water_viscosity(298.15) * 1e3:.3f} and {P.water_viscosity(353.15) * 1e3:.3f}',
    'CRC Handbook; model: Kestin, Sokolov and Wakeham (1978)')
y9 = P.mole_fraction_from_wt(0.09)
add(G, 'Ozone water from 9 wt % ozone gas at 1 atm and 25 °C (mg/L)', '10 to 30 typical',
    f'{P.mg_per_L(P.equilibrium_ozone(298.15, y9)):.1f}', 'Abe et al. (2003); model: Henry\'s law, Burkholder et al. (2019)')
ratio = P.henry_ozone(278.15) / P.henry_ozone(298.15)
add(G, 'Ozone solubility at 5 °C divided by that at 25 °C', f'{120 / 65:.2f} (120 and 65 ppm)', f'{ratio:.2f}',
    'NEC patent US 6,559,064, Fig. 6')
T1, T2 = 298.15, 333.15
se = P.ozone_diffusivity(T1) * (T2 / P.water_viscosity(T2)) / (T1 / P.water_viscosity(T1))
add(G, 'Ozone diffusivity at 60 °C (10⁻⁹ m²/s)', f'{se * 1e9:.2f} by Stokes-Einstein from 25 °C',
    f'{P.ozone_diffusivity(T2) * 1e9:.2f}', 'Johnson and Davis (1996) correlation')
add(G, 'pH of ultrapure water in contact with air (420 ppm CO₂)', 'about 5.6', f'{ph_from_co2(42.0):.2f}',
    'De Smedt et al. (2002)')
add(G, 'Resistivity of ultrapure water at 25 °C (MΩ cm)', '18.19', f'{resistivity_co2(7.0):.2f}',
    'Light et al. (2005); model: limiting ionic conductivities')

# ---------------------------------------------------------------- decomposition
G = 'Ozone decomposition'
c10 = P.mol_per_m3(10.0)
add(G, 'Half-life at pH 2.5, room temperature, 10 mg/L (h)', '3 to 4', f'{Dc.half_life(c10, 2.5, 295.15) / 3600:.1f}',
    'De Smedt et al. (2002), pH 1.8 to 3')
for pH in (6.0, 7.0):
    te, tm = Dc.half_life(c10, pH, 293.15), M.half_life(c10 / 1e3, pH, ct=1.4e-5)
    add(G, f'Half-life at pH {pH:.0f}, 20 °C, 10 mg/L (min): rate law and radical mechanism with air-level carbonate',
        f'{te / 60:.1f} (rate law, Ershov and Morozov 2009)', f'{tm / 60:.1f} (mechanism)',
        'Mechanism: Staehelin, Hoigné and Bühler; constants as compiled by Lesko (2004)')

# ---------------------------------------------------------------- film
G = 'Film on the spinning wafer'
Q, w, nu, r = 2.5e-5, 52.36, P.kinematic_viscosity(298.15), 0.075
h = F.film_thickness(r, Q, w, nu)
add(G, 'Film thickness at r = 75 mm, 1.5 L/min, 500 rpm, 25 °C (µm)',
    f'{0.782 * (nu * Q) ** (1 / 3) * w ** (-2 / 3) * r ** (-2 / 3) * 1e6:.1f}', f'{h * 1e6:.1f}',
    'Lepehin and Riabchuk (1975) correlation, in Bhatelia et al. (2009)')
base = dict(Q=Q, omega=w, R=0.15, c_in=0.6, nu=nu, D=P.ozone_diffusivity(298.15), k1=0.0, k2=0.0)
k = 0.02
fr = F.solve(F.FilmInput(**dict(base, D=1e-2, k1=k), c_surface=None, k_wall=0.0, n_steps=800))
A = F.film_thickness(1.0, Q, w, nu)
tau = 2 * math.pi / Q * A * 0.75 * (0.15 ** (4 / 3) - 0.005 ** (4 / 3))
add(G, 'Well-mixed film with first-order decay (k = 0.02 s⁻¹): ozone left at the edge', f'{math.exp(-k * tau):.6f} (exact)',
    f'{fr.c_mean[-1] / 0.6:.6f}', 'Exact solution c = c₀ exp(−k τ)')
a = F.solve(F.FilmInput(**dict(base, k1=1e-4, k2=1e-3), c_surface=0.0))
b = F.solve(F.FilmInput(**dict(base, k1=1e-4, k2=1e-3), c_surface=0.0, n_layers=192, n_steps=1600))
fa, fb = F.area_average(a.r, a.wall_flux, 0.01), F.area_average(b.r, b.wall_flux, 0.01)
add(G, 'Mean ozone flux to the resist, normal grid against 4 times finer grid', 'same', pct(fa, fb), 'Grid convergence')
add(G, 'Ozone balance on the wafer (in = to resist + to gas + decomposed + off the edge)', '0',
    f'{abs(a.budget["closure"]) / a.budget["in"]:.0e}', 'Conservation')

# ---------------------------------------------------------------- strip rate
G = 'Strip rate'
rate = lambda **kw: simulate(Process(nozzle_ppm=kw.pop('ppm', 30.0), **kw), profile_radii=())['strip_mean'] * 6e10
add(G, 'Mean strip rate at 100, 500 and 1000 rpm, 30 ppm, 25 °C (nm/min)', 'rises with spin speed',
    f'{rate(rpm=100):.0f}, {rate(rpm=500):.0f}, {rate(rpm=1000):.0f}', 'Dussault, Fittkau and Gottschalk: rpm is a large factor')
add(G, 'Mean strip rate at 10, 25 and 60 °C with the same 30 ppm (nm/min)', 'rises with temperature',
    f'{rate(T=283.15):.0f}, {rate(T=298.15):.0f}, {rate(T=333.15):.0f}', 'Gottschalk and Schweckendiek (2004)')
add(G, 'Strip rate at 60 ppm divided by that at 30 ppm', 'about 2 (transport-limited)', f'{rate(ppm=60.0) / rate(ppm=30.0):.3f}',
    'Chen (2002); Gottschalk and Schweckendiek (2004)')
for row in literature_table():
    add(G, f'Ozone per gram of resist implied by {row["source"]}', '1.0 (default)', f'{row["g_ozone_per_g_resist"]:.2f}',
        'Calibration: see the text')

(here / 'checks.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))

# ---------------------------------------------------------------- Figure 6 data: half-life against pH at 20 degC
pHs = [round(x, 2) for x in np.arange(3.0, 8.001, 0.25)]
mech = {'pH': pHs, 'c0_mg_L': 10.0, 'T_C': 20.0}
for key, kw in {'pure': {}, 'air': {'ct': total_carbonate(42.0)}, 'co2': {'ct': total_carbonate(1013.25)},
                'h2o2': {'ct': total_carbonate(42.0), 'h2o2_0': 1e-5}}.items():
    mech[key] = [M.half_life(c10 / 1e3, pH, **kw) for pH in pHs]
mech['ct_air'] = total_carbonate(42.0)
mech['ct_co2'] = total_carbonate(1013.25)
mech['reactions'] = [[name, k] for name, k in M.REACTIONS]
(here / 'mechanism.json').write_text(json.dumps(mech))
print('written', len(rows), 'checks and', len(pHs), 'mechanism points')
