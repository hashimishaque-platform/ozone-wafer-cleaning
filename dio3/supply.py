"""Ozone supply: generator gas, dissolution in the contactor, transport to the nozzle.

The contactor is treated as reaching a chosen fraction ('approach') of Henry's-law
equilibrium with the generator gas at its pressure and temperature. In the line to the nozzle
the water is at the process temperature and ozone decays by the engineering rate law. When the
water leaves the nozzle it is at atmospheric pressure; if it holds more ozone than water in
equilibrium with the generator gas at 1 atm and the process temperature, it is supersaturated
and loses ozone as bubbles or at its surface.
"""
import math
from dataclasses import dataclass

from . import properties as P
from . import decomposition as Dc


@dataclass
class Supply:
    gas_g_per_Nm3: float = 200.0     # ozone in the generator gas, g per normal m3
    pressure: float = P.P_ATM        # absolute pressure in the contactor, Pa
    T_contactor: float = 298.15      # K
    approach: float = 1.0            # fraction of equilibrium reached in the contactor
    line_length: float = 5.0         # m, from the contactor to the nozzle
    line_diameter: float = 6e-3      # m, inner diameter
    gas_flow_Nlpm: float = 2.0       # generator gas flow, normal litres per minute


def deliver(s: Supply, Q, T_process, pH):
    """Dissolved ozone along the supply chain. Q is the liquid flow in m3/s."""
    y = P.mole_fraction_from_g_per_Nm3(s.gas_g_per_Nm3)
    c_eq = P.equilibrium_ozone(s.T_contactor, y, s.pressure)
    c_out = s.approach * c_eq
    volume = math.pi * s.line_diameter ** 2 / 4.0 * s.line_length
    tau = volume / Q
    c_nozzle = Dc.concentration_after(c_out, tau, pH, T_process)
    c_sat_nozzle = P.equilibrium_ozone(T_process, y, P.P_ATM)
    gas_in = s.gas_flow_Nlpm / 60e3 / P.MOLAR_VOLUME_NORMAL * y          # mol O3/s from the generator
    return {
        'y_gas': y,
        'wt_gas': P.wt_from_mole_fraction(y),
        'c_contactor_eq': c_eq,
        'c_contactor_out': c_out,
        'line_residence_time': tau,
        'c_nozzle': c_nozzle,
        'c_sat_nozzle': c_sat_nozzle,
        'supersaturation': c_nozzle / c_sat_nozzle,
        'ozone_from_generator': gas_in,
        'ozone_dissolved': Q * c_out,
        'ozone_decayed_in_line': Q * (c_out - c_nozzle),
    }
