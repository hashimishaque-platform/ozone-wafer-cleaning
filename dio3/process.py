"""The whole single-wafer process: supply, film on the spinning substrate, resist removal."""
import math
from dataclasses import dataclass, field

import numpy as np

from . import properties as P
from . import decomposition as Dc
from . import film as F
from .supply import Supply, deliver
from .resist import Resist

R_MIN = 0.01      # m; results inside 10 mm (impingement zone) are not modelled


@dataclass
class Process:
    T: float = 298.15                 # process temperature (water on the substrate), K
    pH: float = 5.6                   # ultrapure water in contact with air (De Smedt et al. 2002)
    flow_lpm: float = 1.5             # L/min
    rpm: float = 500.0
    diameter: float = 0.300           # m
    ambient: str = 'air'              # 'air', 'process gas' (chamber filled with generator gas) or ppm by volume
    enhancement: float = 1.0          # mass-transfer enhancement, e.g. megasonic agitation (1 = none)
    resist_thickness: float = 1.0e-6  # m
    exhaust_m3h: float = 100.0        # chamber exhaust, m3/h, for the ozone concentration in it
    nozzle_ppm: float = None          # set to fix the ozone at the nozzle (mg/L) instead of computing the supply
    ring_radius: float = None         # optional second dispense: a ring of nozzles at this radius, m
    ring_flow_lpm: float = 0.0        # flow through the ring, L/min (same ozone water as the centre nozzle)
    supply: Supply = field(default_factory=Supply)
    resist: Resist = field(default_factory=Resist)
    n_layers: int = 48
    n_steps: int = 400


def ambient_mole_fraction(p: Process):
    if p.ambient == 'air':
        return 0.0
    if p.ambient == 'process gas':
        return P.mole_fraction_from_g_per_Nm3(p.supply.gas_g_per_Nm3)
    return float(p.ambient) * 1e-6


def simulate(p: Process, profile_radii=(0.02, 0.075, 0.14)):
    Q = p.flow_lpm / 60e3
    omega = p.rpm * 2.0 * math.pi / 60.0
    R = p.diameter / 2.0
    sup = deliver(p.supply, Q, p.T, p.pH)
    if p.nozzle_ppm is not None:
        sup['c_nozzle'] = P.mol_per_m3(p.nozzle_ppm)
        sup['supersaturation'] = sup['c_nozzle'] / sup['c_sat_nozzle']
    y_amb = ambient_mole_fraction(p)
    c_surface = P.equilibrium_ozone(p.T, y_amb, P.P_ATM)
    nu, D = P.kinematic_viscosity(p.T), P.ozone_diffusivity(p.T)
    inp = F.FilmInput(Q=Q, omega=omega, R=R, c_in=sup['c_nozzle'], nu=nu, D=D * p.enhancement,
                      k1=Dc.k1(p.T), k2=Dc.k2(p.pH, p.T), c_surface=c_surface,
                      k_wall=p.resist.k_wall(p.T), n_layers=p.n_layers, n_steps=p.n_steps,
                      r_inject=p.ring_radius if p.ring_flow_lpm > 0 else None, Q_inject=p.ring_flow_lpm / 60e3,
                      c_inject=sup['c_nozzle'])
    radii = [x for x in profile_radii if x < R]
    fr = F.solve(inp, profile_radii=radii)
    rate = p.resist.yield_m3_per_mol * fr.wall_flux                     # m/s
    keep = fr.r >= R_MIN
    mean = F.area_average(fr.r, rate, R_MIN)
    rmax, rmin = float(rate[keep].max()), float(rate[keep].min())
    b = fr.budget
    t_clear = p.resist_thickness / rmin if rmin > 0 else math.inf
    emitted = max(-b['gas_exchange'], 0.0)
    exhaust_ppm = emitted / (p.exhaust_m3h / 3600.0 / P.MOLAR_VOLUME_NORMAL) * 1e6 if p.exhaust_m3h > 0 else math.inf
    return {
        'input': p,
        'supply': sup,
        'film': fr,
        'c_surface': c_surface,
        'nu': nu, 'D': D,
        'half_life_nozzle': Dc.half_life(sup['c_nozzle'], p.pH, p.T) if sup['c_nozzle'] > 0 else math.inf,
        'strip_rate': rate,                       # m/s along fr.r
        'strip_mean': mean,
        'strip_max': rmax, 'strip_min': rmin,
        'nonuniformity': (rmax - rmin) / (2.0 * mean) if mean > 0 else math.nan,
        'time_to_clear': t_clear,
        'budget': b,
        'ozone_per_wafer_g': Q * sup['c_nozzle'] * P.M_O3 * 1e3 * t_clear if math.isfinite(t_clear) else math.inf,
        'exhaust_ppm': exhaust_ppm,
        'h_mid': F.film_thickness(R / 2.0, Q, omega, nu),
        'inertia_mid': F.inertia_ratio(R / 2.0, Q, omega, nu),
    }


def sweep(p: Process, temperatures, rpms):
    """Mean strip rate (m/s), non-uniformity and supersaturation on a grid of T and rpm."""
    mean = np.zeros((len(rpms), len(temperatures)))
    nonu = np.zeros_like(mean)
    sat = np.zeros_like(mean)
    for i, rpm in enumerate(rpms):
        for j, T in enumerate(temperatures):
            q = Process(**{**p.__dict__, 'T': T, 'rpm': rpm, 'n_layers': 32, 'n_steps': 200})
            r = simulate(q, profile_radii=())
            mean[i, j], nonu[i, j], sat[i, j] = r['strip_mean'], r['nonuniformity'], r['supply']['supersaturation']
    return mean, nonu, sat
