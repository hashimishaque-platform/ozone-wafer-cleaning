"""Command line: python3 -m dio3 [options]. Prints the main results for one set of conditions."""
import argparse
import math

from . import properties as P
from .process import Process, simulate
from .resist import Resist
from .supply import Supply


def main(argv=None):
    a = argparse.ArgumentParser(prog='python3 -m dio3', description='Ozonated-water resist strip on a spinning wafer.')
    a.add_argument('--gas', type=float, default=200.0, help='ozone in the generator gas, g/Nm3 (200)')
    a.add_argument('--pressure', type=float, default=1.01325, help='contactor pressure, bar absolute (1.013)')
    a.add_argument('--t-contactor', type=float, default=25.0, help='contactor temperature, degC (25)')
    a.add_argument('--approach', type=float, default=100.0, help='approach to equilibrium in the contactor, %% (100)')
    a.add_argument('--line', type=float, default=5.0, help='supply line length, m (5)')
    a.add_argument('--t', type=float, default=25.0, help='process temperature, degC (25)')
    a.add_argument('--ph', type=float, default=5.6, help='pH (5.6)')
    a.add_argument('--flow', type=float, default=1.5, help='flow, L/min (1.5)')
    a.add_argument('--rpm', type=float, default=500.0, help='spin speed, rpm (500)')
    a.add_argument('--diameter', type=float, default=300.0, help='substrate diameter, mm (300)')
    a.add_argument('--ambient', default='air', help="gas above the film: 'air', 'process gas' or ppm by volume")
    a.add_argument('--enhancement', type=float, default=1.0, help='mass-transfer factor, e.g. megasonics (1)')
    a.add_argument('--demand', type=float, default=1.0, help='g of ozone per g of resist (1.0)')
    a.add_argument('--thickness', type=float, default=1.0, help='resist thickness, um (1)')
    o = a.parse_args(argv)
    sup = Supply(gas_g_per_Nm3=o.gas, pressure=o.pressure * 1e5, T_contactor=o.t_contactor + 273.15,
                 approach=o.approach / 100.0, line_length=o.line)
    p = Process(T=o.t + 273.15, pH=o.ph, flow_lpm=o.flow, rpm=o.rpm, diameter=o.diameter / 1000.0, ambient=o.ambient,
                enhancement=o.enhancement, resist_thickness=o.thickness * 1e-6, supply=sup,
                resist=Resist(yield_m3_per_mol=P.M_O3 / (o.demand * 1200.0)))
    r = simulate(p)
    s, b = r['supply'], r['budget']
    nm = lambda v: v * 6e10
    print(f"ozone at the nozzle        {P.mg_per_L(s['c_nozzle']):8.1f} mg/L   (supersaturation {s['supersaturation']:.2f})")
    print(f"half-life at {o.t:.0f} degC        {r['half_life_nozzle'] / 60:8.1f} min")
    print(f"film thickness at R/2      {r['h_mid'] * 1e6:8.1f} um")
    print(f"mean strip rate            {nm(r['strip_mean']):8.1f} nm/min  (range {nm(r['strip_min']):.0f} to {nm(r['strip_max']):.0f})")
    print(f"non-uniformity             {r['nonuniformity'] * 100:8.1f} %   (max - min) / (2 mean)")
    print(f"time to clear              {r['time_to_clear'] / 60:8.2f} min")
    gas = b['gas_exchange']
    gas_text = f"absorbed from the gas {100 * gas / b['in']:.1f} %" if gas > 0 else f"escaped to the gas {-100 * gas / b['in']:.1f} %"
    print(f"ozone, as a share of what is dispensed: to the resist {100 * b['resist'] / b['in']:.1f} %, {gas_text}, "
          f"decayed on the wafer {100 * b['decomposed'] / b['in']:.1f} %, off the edge {100 * b['edge'] / b['in']:.1f} %")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
