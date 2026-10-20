"""Mean strip rate over process temperature and spin speed, as in Figure 4 of the web page.

    python3 examples/process_window.py        -> process_window.png (needs matplotlib)
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # run from a clone without installing
from dio3 import Process, sweep  # noqa: E402

temps = np.arange(10.0, 80.01, 5.0) + 273.15
rpms = np.arange(100.0, 1500.01, 100.0)
mean, nonu, sat = sweep(Process(), temps, rpms)

fig, ax = plt.subplots(figsize=(6.4, 4.0))
cs = ax.contour(temps - 273.15, rpms, mean * 6e10, levels=8, colors='k', linewidths=0.8)
ax.clabel(cs, fmt='%.0f', fontsize=8)
ax.contour(temps - 273.15, rpms, sat, levels=[1.0], colors='r', linestyles='--')
ax.set_xlabel('process temperature (°C)')
ax.set_ylabel('spin speed (rpm)')
ax.set_title('Mean strip rate (nm/min); dashed: supersaturated at the nozzle', fontsize=10)
fig.tight_layout()
fig.savefig('process_window.png', dpi=150)
print('wrote process_window.png')
