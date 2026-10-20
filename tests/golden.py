"""Writes tests/golden.json: Python results that crosscheck.js compares the browser model with."""
import json
import math
from pathlib import Path

from dio3.process import Process, simulate
from dio3.supply import Supply
from dio3.resist import Resist
from dio3 import properties as P, decomposition as Dc
from dio3.carbonate import resistivity_co2, co2_pressure_for_ph

CASES = {
    'default': {},
    'hot_process_gas': {'T': 343.15, 'rpm': 1200.0, 'flow_lpm': 0.5, 'ambient': 'process gas'},
    'cold_slow_200mm': {'T': 288.15, 'rpm': 150.0, 'flow_lpm': 2.0, 'diameter': 0.2, 'pH': 4.0},
    'pressurised_megasonic': {'enhancement': 1.65, 'supply': {'pressure': 2.5e5, 'gas_g_per_Nm3': 300.0}},
    'fixed_nozzle': {'nozzle_ppm': 80.0, 'T': 293.15, 'rpm': 110.0, 'flow_lpm': 1.4, 'diameter': 0.2},
    'bare_wafer': {'resist': {'k_wall_ref': 0.0}, 'rpm': 1000.0, 'ambient': 'process gas'},
    'surface_rate': {'resist': {'k_wall_ref': 2.0e-5, 'Ea_wall': 30.0e3}, 'T': 318.15},
}
PH = [3.9, 4.5, 4.9, 5.6, 6.2, 6.9, 7.0]


def run(changes):
    sup = Supply(**changes.get('supply', {}))
    res = Resist(**changes.get('resist', {}))
    kw = {k: v for k, v in changes.items() if k not in ('supply', 'resist')}
    r = simulate(Process(supply=sup, resist=res, **kw), profile_radii=())
    b = r['budget']
    return {
        'c_nozzle': r['supply']['c_nozzle'], 'supersaturation': r['supply']['supersaturation'],
        'half_life_nozzle': r['half_life_nozzle'], 'strip_mean': r['strip_mean'], 'strip_min': r['strip_min'],
        'strip_max': r['strip_max'], 'nonuniformity': r['nonuniformity'], 'exhaust_ppm': r['exhaust_ppm'],
        'resist': b['resist'], 'gas_exchange': b['gas_exchange'], 'edge': b['edge'], 'decomposed': b['decomposed'],
        'h_mid': r['h_mid'],
    }


def finite(d):
    return {k: v for k, v in d.items() if math.isfinite(v)}


def functions():
    c0 = P.mol_per_m3(40.0)
    return {
        'pH': PH,
        'resistivity': [resistivity_co2(x) for x in PH if x <= 7.0],
        'co2_pressure': [co2_pressure_for_ph(x) for x in PH],
        'time_to_fraction': [[f, pH, T, Dc.time_to_fraction(c0, f, pH, T)]
                             for f in (0.9, 0.5) for pH in (4.0, 7.0) for T in (293.15, 333.15)],
        'c0': c0,
    }


if __name__ == '__main__':
    out = {name: {'changes': ch, 'result': finite(run(ch))} for name, ch in CASES.items()}
    Path(__file__).with_name('golden.json').write_text(json.dumps(out, indent=1))
    Path(__file__).with_name('golden_functions.json').write_text(json.dumps(functions(), indent=1))
    print('wrote golden.json with', len(out), 'cases and golden_functions.json')
