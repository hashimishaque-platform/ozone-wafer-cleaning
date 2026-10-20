"""Photoresist removal by dissolved ozone.

Literature on ozonated-water stripping reports that the rate is limited by the transport of
dissolved ozone to the resist surface: it rises with ozone concentration, with spin speed and
with megasonic agitation (Gottschalk and Schweckendiek 2004, MICRO; Chen 2002, MSc thesis,
National Chiao Tung University; Dussault, Fittkau and Gottschalk, ProSys/ASTeX). The default
model therefore takes every ozone molecule that reaches the resist as reacting there, and the
strip rate as

    strip rate = yield * ozone flux into the resist,

where the yield is the resist volume removed per mole of ozone. The yield depends on the resist
(i-line resists strip faster than KrF, and ArF resists, which lack phenol, slowest: Abe et al.
2003, IEEE Trans. Semicond. Manuf. 16, 401) and must be calibrated. A finite surface rate
constant with an activation energy can be set when measurements show kinetic limitation.
"""
import math
from dataclasses import dataclass

from .properties import R, M_O3


@dataclass
class Resist:
    name: str = 'i-line resist, default calibration'
    yield_m3_per_mol: float = M_O3 / 1200.0   # 1 g of ozone per g of resist at 1200 kg/m3 (see calibration.py)
    density: float = 1200.0                   # kg/m3, used only to express the ozone demand
    k_wall_ref: float = math.inf         # m/s at T_ref; inf means transport-limited
    Ea_wall: float = 0.0                 # J/mol
    T_ref: float = 293.15

    def k_wall(self, T):
        if math.isinf(self.k_wall_ref) or self.k_wall_ref == 0:
            return self.k_wall_ref
        return self.k_wall_ref * math.exp(-self.Ea_wall / R * (1.0 / T - 1.0 / self.T_ref))

    def ozone_demand(self):
        """Grams of ozone used per gram of resist removed."""
        return M_O3 / (self.yield_m3_per_mol * self.density)
