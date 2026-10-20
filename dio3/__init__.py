"""dio3: a process model of ozonated water (DIO3) for photoresist removal on a spinning wafer.

    from dio3 import Process, simulate
    r = simulate(Process(T=298.15, rpm=500, flow_lpm=1.5))
    print(r['strip_mean'] * 6e10, 'nm/min')
"""
from .process import Process, simulate, sweep
from .supply import Supply
from .resist import Resist

__version__ = '0.1.0'
__all__ = ['Process', 'Supply', 'Resist', 'simulate', 'sweep', '__version__']
