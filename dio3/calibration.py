"""Calibration of the resist yield against published strip rates, and against your own data.

Published strip rates for ozonated water at room temperature (none of them gives every
setting, so the missing ones are assumed and shown here):

* Abe et al. (2003), IEEE Trans. Semicond. Manuf. 16, 401: typical ozone water of 10 to 30 ppm
  at room temperature and atmospheric pressure removes photoresist at about 100 nm/min.
  Assumed: 20 ppm, 25 degC, 500 rpm, 1.5 L/min, 200 mm wafer.
* NEC patent US 6,559,064 B1 (Shimizu, priority 1999): about 3000 A/min (300 nm/min) with
  ozone water of about 100 ppm on a rotating wafer without heating. Assumed: 25 degC, 200 mm,
  and 300 to 1000 rpm with 1 to 2 L/min.
* Dussault, Fittkau and Gottschalk, Solid State Phenomena 219, 187 (2014): 279 nm/min for the
  negative resist AZ nLof 2070 at 80 ppm, 20 degC, 110 rpm, 1.4 L/min on a 200 mm wafer, with
  megasonics at 2 W/cm2 and the water fed through a radial manifold under the transducer, not a
  centre nozzle. Megasonics raised the strip rate of a positive resist (AZ MIR 701) by over 65 %.
  Assumed: the same gain for the negative resist, so a rate without megasonics of 279 / 1.65
  nm/min. This point is the weakest of the three.

With these assumptions the three sources imply 0.8 to 1.6 g of ozone per g of resist. The
default is 1.0 g/g, which reproduces all three within their uncertainty (see the tests).
"""
import math

from .process import Process, simulate
from .resist import Resist
from .properties import M_O3

LITERATURE = [
    {'source': 'Abe et al. 2003', 'rate_nm_min': 100.0,
     'conditions': dict(nozzle_ppm=20.0, T=298.15, rpm=500.0, flow_lpm=1.5, diameter=0.2)},
    {'source': 'NEC US 6,559,064 (500 rpm, 1.5 L/min assumed)', 'rate_nm_min': 300.0,
     'conditions': dict(nozzle_ppm=100.0, T=298.15, rpm=500.0, flow_lpm=1.5, diameter=0.2)},
    {'source': 'NEC US 6,559,064 (1000 rpm, 1.0 L/min assumed)', 'rate_nm_min': 300.0,
     'conditions': dict(nozzle_ppm=100.0, T=298.15, rpm=1000.0, flow_lpm=1.0, diameter=0.2)},
    {'source': 'NEC US 6,559,064 (300 rpm, 2.0 L/min assumed)', 'rate_nm_min': 300.0,
     'conditions': dict(nozzle_ppm=100.0, T=298.15, rpm=300.0, flow_lpm=2.0, diameter=0.2)},
    {'source': 'Dussault et al. 2014 (megasonic gain taken out)', 'rate_nm_min': 279.0 / 1.65,
     'conditions': dict(nozzle_ppm=80.0, T=293.15, rpm=110.0, flow_lpm=1.4, diameter=0.2)},
]


def mean_flux(conditions):
    """Mean ozone flux into the resist (mol/(m2 s)) for the given process settings."""
    r = simulate(Process(resist=Resist(yield_m3_per_mol=1.0), **conditions), profile_radii=())
    return r['strip_mean']


def implied_yield(rate_nm_min, conditions):
    return rate_nm_min * 1e-9 / 60.0 / mean_flux(conditions)


def literature_table(density=1200.0):
    rows = []
    for item in LITERATURE:
        y = implied_yield(item['rate_nm_min'], item['conditions'])
        rows.append({**item, 'yield': y, 'g_ozone_per_g_resist': M_O3 / (y * density)})
    return rows


def fit_yield(measurements):
    """Best yield (m3/mol) for your own data: a list of (rate_nm_min, conditions dict).

    Least squares on the logarithm, so every point counts equally whatever its size.
    """
    logs = [math.log(implied_yield(rate, cond)) for rate, cond in measurements]
    return math.exp(sum(logs) / len(logs))
