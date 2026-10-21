"""Validation of the model against published measurements that were not used to build it, and a
cross-check of every input against its source.

    python3 validation.py      -> validation.json (tables on the page) and validation.svg (Figure 7)

1. Solubility. Every measured Henry's law value for ozone in water in the compilation of
   Sander (2023), Atmos. Chem. Phys. 23, 10901, against the value the model uses (Burkholder et
   al. 2019, a review). Values in that compilation are given to two figures.
2. Life of ozone in ultrapure water. The half-lives that tool makers and patents quote for pH 7
   (MKS 'Ozone Conversion' data sheet, rev. 10/22; ACM Research US 12,334,367; Sumco US 7,678,200)
   against the rate law at the ozone levels used in practice.
3. Strip rate, leave one out. The three published room-temperature strip rates are independent
   (three laboratories). The yield is fitted to two of them and the third is predicted.
4. Heated wafer. The NEC patent (US 6,559,064) reports faster stripping when the wafer under cold
   ozone water is heated; the model has one temperature, so only the direction can be compared.
5. The film. Mean film thickness against direct numerical simulation, and the wave regime.
"""
import json
import math
from pathlib import Path

from dio3 import properties as P, decomposition as Dc, mechanism as M
from dio3.calibration import LITERATURE, implied_yield
from dio3.carbonate import total_carbonate
from dio3.process import Process, simulate
from dio3.resist import Resist

here = Path(__file__).resolve().parent

# (reference, year, Hcp in mol/(m3 Pa) at T_ref, T_ref in K, d ln H / d(1/T) in K or None).
# Type "M" (measured) entries of Sander (2023) for ozone, CAS 10028-15-6.
HENRY_MEASURED = [
    ('Levanov et al.', 2008, 1.1e-4, 293.15, None),
    ('Gershenzon et al.', 2001, 1.1e-4, 298.15, 2300.0),
    ('Rischbieter et al.', 2000, 9.9e-5, 298.15, 2600.0),
    ('Andreozzi et al.', 1996, 9.2e-5, 298.15, 2600.0),
    ('Sotelo et al.', 1989, 1.2e-4, 298.15, 1400.0),
    ('Kosak-Channing and Helz', 1983, 1.1e-4, 298.15, 2300.0),
    ('Gurol and Singer', 1982, 1.7e-4, 293.15, None),
    ('Stumm', 1958, 1.2e-4, 298.15, 1900.0),
    ('Kilpatrick et al.', 1956, 9.9e-5, 298.15, 2600.0),
    ('Briner and Perrottet', 1939, 1.3e-4, 298.15, 2000.0),
    ('Fischer and Tropsch', 1917, 2.0e-4, 298.15, None),
    ('Luther', 1905, 8.0e-5, 298.15, 2900.0),
    ('Mailfert', 1894, 1.2e-4, 298.15, 4100.0),
    ('Schöne', 1873, 1.2e-4, 291.15, None),
]

# MKS Instruments, 'Ozone Conversion' data sheet, rev. 10/22: half-life of ozone dissolved in water
# at pH 7, "based on thermal decomposition, no wall effects"; concentration not stated.
MKS_HALF_LIFE = [(15.0, 30.0), (20.0, 20.0), (25.0, 15.0), (30.0, 12.0), (35.0, 8.0)]


def henry_measured(entry, T):
    _, _, h, t_ref, b = entry
    return h * math.exp(b * (1.0 / T - 1.0 / t_ref)) if b else (h if abs(T - t_ref) < 1e-9 else None)


def solubility():
    rows = []
    for e in HENRY_MEASURED:
        name, year, h, t_ref, b = e
        model = P.henry_ozone(t_ref)
        row = {'source': name, 'year': year, 'T_ref': t_ref, 'measured': h, 'model': model, 'ratio': model / h, 'B': b}
        if b:
            for t in (278.15, 323.15):
                row[f'ratio_{int(round(t - 273.15))}C'] = P.henry_ozone(t) / henry_measured(e, t)
        rows.append(row)
    modern = sorted(r['ratio'] for r in rows if r['year'] >= 1950)
    n = len(modern)
    median = modern[n // 2] if n % 2 else 0.5 * (modern[n // 2 - 1] + modern[n // 2])
    within = sum(1 for x in modern if abs(x - 1.0) <= 0.2)
    bs = sorted(r['B'] for r in rows if r['B'] and r['year'] >= 1950)
    return {'rows': rows, 'modern_n': n, 'modern_median_ratio': median, 'modern_min': modern[0],
            'modern_max': modern[-1], 'modern_within_20pct': within,
            'model_B': 2800.0, 'measured_B_median': bs[len(bs) // 2]}


def half_life_industry():
    """Rate law at pH 7 for 5 to 90 mg/L against the quoted half-lives, and the effect of CO2."""
    mks = []
    for t, quoted in MKS_HALF_LIFE:
        T = t + 273.15
        row = {'T_C': t, 'quoted_min': quoted}
        for c in (5.0, 10.0, 20.0, 90.0):
            row[f'model_{int(c)}'] = Dc.half_life(P.mol_per_m3(c), 7.0, T) / 60.0
        mks.append(row)
    c90 = P.mol_per_m3(90.0)
    curves = {}
    for label, c, pH in (('5 mg/L, pH 7', 5.0, 7.0), ('20 mg/L, pH 7', 20.0, 7.0), ('90 mg/L, pH 7', 90.0, 7.0),
                         ('90 mg/L, pH 4.5 (CO₂)', 90.0, 4.5)):
        curves[label] = [[t, Dc.half_life(P.mol_per_m3(c), pH, t + 273.15) / 60.0] for t in range(10, 41)]
    ratio_T = mks[-1]['model_10'] / mks[0]['model_10']
    return {
        'mks': mks, 'curves': curves,
        'acm': {'T_C': 25.0, 'quoted_min': 15.0, 'ppm': 90.0, 'model_pH7': Dc.half_life(c90, 7.0, 298.15) / 60.0,
                'model_pH4_5': Dc.half_life(c90, 4.5, 298.15) / 60.0, 'model_pH4': Dc.half_life(c90, 4.0, 298.15) / 60.0,
                'source': 'ACM Research, US 12,334,367 (priority 2020): about 15 min at 25 °C and pH 7.0, for 90 ppm baths'},
        'sumco': {'quoted': '10 to 30 min', 'source': 'Sumco, Echo Giken and Chlorine Engineers, US 7,678,200 (priority 2002)',
                  'model_min': min(Dc.half_life(P.mol_per_m3(c), pH, 295.15) for pH in (5.6, 7.0) for c in (5.0, 10.0, 20.0)) / 60,
                  'model_max': max(Dc.half_life(P.mol_per_m3(c), pH, 295.15) for pH in (5.6, 7.0) for c in (5.0, 10.0, 20.0)) / 60},
        'temperature_ratio_15_35': {'quoted': MKS_HALF_LIFE[0][1] / MKS_HALF_LIFE[-1][1], 'model': 1.0 / ratio_T},
    }


def leave_one_out():
    """Fit the yield to two independent sources and predict the third (log mean of the two)."""
    pick = {'Abe et al. 2003': LITERATURE[0], 'NEC US 6,559,064': LITERATURE[1],
            'Dussault et al. 2014': LITERATURE[4]}
    ys = {k: implied_yield(v['rate_nm_min'], v['conditions']) for k, v in pick.items()}
    rows = []
    for k, v in pick.items():
        others = [math.log(y) for name, y in ys.items() if name != k]
        y_fit = math.exp(sum(others) / len(others))
        r = simulate(Process(resist=Resist(yield_m3_per_mol=y_fit), **v['conditions']), profile_radii=())
        pred = r['strip_mean'] * 6e10
        rows.append({'left_out': k, 'published': v['rate_nm_min'], 'predicted': pred, 'ratio': pred / v['rate_nm_min'],
                     'conditions': v['conditions']})
    return rows


def heated_wafer():
    """NEC US 6,559,064: about 3000 A/min without heating, about 6000 A/min with the wafer heated by
    an IR lamp and about 9000 A/min on a heated stage, with cold ozone water of about 100 ppm.
    The model with the whole film at one temperature, 100 ppm at the nozzle."""
    rate = lambda T: simulate(Process(nozzle_ppm=100.0, T=T, diameter=0.2), profile_radii=())['strip_mean'] * 6e10
    r25 = rate(298.15)
    return {'published_ratio': [1.0, 2.0, 3.0], 'model_ratio_60C': rate(333.15) / r25, 'model_ratio_80C': rate(353.15) / r25}


def film():
    """Wave parameter Q nu / (omega^2 r^5) at mid-radius for the default settings. Stafford et
    al. (2024) find that the azimuthally averaged thickness from direct simulation follows the
    Nusselt (Emslie-Bonner-Peck) film, and that films carry waves below about 1e-7."""
    p = Process()
    Q, w, nu, r = p.flow_lpm / 60e3, p.rpm * 2 * math.pi / 60, P.kinematic_viscosity(p.T), p.diameter / 4
    return {'lambda_mid': Q * nu / (w ** 2 * r ** 5), 'threshold': 1e-7}


def mechanism_constants():
    """Two constants where the compilation used (Lesko 2004) and Buxton et al. (1988) differ."""
    c0 = P.mol_per_m3(10.0) / 1e3
    ct = total_carbonate(42.0)
    idx = {n: i for i, (n, _) in enumerate(M.REACTIONS)}
    i_ho2 = [i for n, i in idx.items() if n.startswith('OH + HO2 ->')][0]
    i_hco3 = [i for n, i in idx.items() if n.startswith('OH + HCO3-')][0]
    base = M.half_life(c0, 7.0, ct=ct)
    a = M.half_life(c0, 7.0, ct=ct, scale={i_ho2: 6.6e9 / M.K[i_ho2]})
    b = M.half_life(c0, 7.0, ct=ct, scale={i_hco3: 8.5e6 / M.K[i_hco3]})
    return {'base_min': base / 60, 'oh_ho2_buxton_min': a / 60, 'oh_hco3_buxton_min': b / 60,
            'k_oh_ho2': M.K[i_ho2], 'k_oh_hco3': M.K[i_hco3]}


def inputs(sol, hl, mech):
    """Every input of the model, where it comes from, what it was checked against and the result."""
    acm = hl['acm']
    return [
        {'item': "Ozone solubility (Henry's law)", 'value': '1.0 × 10⁻⁴ mol m⁻³ Pa⁻¹ at 25 °C, 2800 K',
         'source': 'Burkholder et al. (2019), JPL evaluation 19-5; listed by Sander (2023)',
         'checked': f"{sol['modern_n']} measurements since 1950 in Sander (2023)",
         'result': f"model/measured median {sol['modern_median_ratio']:.2f} ({sol['modern_min']:.2f} to {sol['modern_max']:.2f}); "
                   f"{sol['modern_within_20pct']} of {sol['modern_n']} within 20 %. Measured temperature coefficients have a median "
                   f"of {sol['measured_B_median']:.0f} K, so the model leans high below 25 °C and low above."},
        {'item': 'CO₂ solubility', 'value': '3.4 × 10⁻⁴ mol m⁻³ Pa⁻¹, 2300 K', 'source': 'Burkholder et al. (2019)',
         'checked': 'Sander (2023)', 'result': 'same value'},
        {'item': 'Carbonate and water constants', 'value': 'pKa 6.35 and 10.33, pKw 14.00 at 25 °C',
         'source': 'Stumm and Morgan (1996)', 'checked': 'pH of water in contact with air; resistivity of pure water',
         'result': 'pH 5.60 (about 5.6 expected); 18.23 MΩ cm against 18.19 (Light et al. 2005)'},
        {'item': 'Decay in acid (k₁)', 'value': 'half-life 3.5 h at 22 °C, 39.6 kJ/mol', 'source': 'De Smedt et al. (2002)',
         'checked': 'De Smedt et al. (2002)', 'result': '3.1 h at pH 2.5 and 10 mg/L (3 to 4 h reported)'},
        {'item': 'Decay near neutral (k₂)', 'value': 'log k = −2.66 + 0.49 pH at 19 °C, 76 kJ/mol', 'source': 'Ershov and Morozov (2009)',
         'checked': 'Half-lives quoted by MKS (data sheet), ACM (US 12,334,367) and Sumco (US 7,678,200)',
         'result': f"agrees at 5 to 10 mg/L; at 90 mg/L and pH 7 the model gives {acm['model_pH7']:.1f} min against about 15 min. "
                   f"With CO₂ to pH 4.5 the model gives {acm['model_pH4_5']:.0f} min. The model's half-life falls "
                   f"{hl['temperature_ratio_15_35']['model']:.1f} times from 15 to 35 °C, the quoted values "
                   f"{hl['temperature_ratio_15_35']['quoted']:.1f} times. Open question; stage 1 of the test plan measures it."},
        {'item': 'Radical mechanism', 'value': '26 reactions', 'source': 'Lesko (2004), two from Buxton et al. (1988)',
         'checked': 'Staehelin and Hoigné (1982), Bühler et al. (1984), Buxton et al. (1988)',
         'result': f"all within the published ranges except OH + HO₂ ({mech['k_oh_ho2']:.1e}; Buxton 6.6 × 10⁹, no effect on the "
                   f"half-life) and OH + HCO₃⁻ ({mech['k_oh_hco3']:.1e}; Buxton 8.5 × 10⁶, half-life at pH 7 "
                   f"{mech['base_min']:.1f} → {mech['oh_hco3_buxton_min']:.1f} min)"},
        {'item': 'Ozone diffusivity', 'value': '1.1 × 10⁻⁶ exp(−1896/T) m²/s', 'source': 'Johnson and Davis (1996)',
         'checked': 'Stokes-Einstein scaling with the viscosity', 'result': 'within 10 % from 25 to 60 °C'},
        {'item': 'Water density and viscosity', 'value': 'Kell (1975); Kestin et al. (1978)', 'source': 'as named',
         'checked': 'CRC Handbook', 'result': 'within 0.02 % and 0.4 %'},
        {'item': 'Film thickness', 'value': 'h = (3νQ / 2πω²r²)^(1/3)', 'source': 'Emslie, Bonner and Peck (1958)',
         'checked': 'Lepehin and Riabchuk correlation; direct simulation and experiments (Stafford et al. 2024)',
         'result': 'same coefficient; the mean thickness follows it, but the film is wavy at these settings, with peaks up to '
                   'twice the mean'},
        {'item': 'Transfer across the film', 'value': 'smooth laminar film, no waves', 'source': 'this model',
         'checked': 'Aoune and Ramshaw (1999); Burns and Jachuck (2005); Zhao (2020)',
         'result': 'measured gas-liquid and liquid-solid transfer on spinning discs is higher than the smooth-film value, so the '
                   'model gives a lower bound; the fitted yield absorbs part of the difference'},
        {'item': 'Resist yield', 'value': '1.0 g of ozone per g of resist', 'source': 'calibration, three sources',
         'checked': 'leave one out (below)', 'result': 'each source predicted within a factor of 1.6 from the other two'},
        {'item': 'Dussault et al. calibration point', 'value': '279 nm/min, megasonic gain 65 %',
         'source': 'Solid State Phenomena 219, 187 (2014)', 'checked': 'the paper',
         'result': 'corrected: 279 nm/min is for a negative resist with megasonics; the 65 % gain was measured on a positive '
                   'resist; the water came through a radial manifold, not a centre nozzle'},
        {'item': 'Chemical oxide on silicon', 'value': '0.5 to 1.2 nm, self-limiting', 'source': 'De Smedt et al. (2002)',
         'checked': 'De Smedt et al. (2002)', 'result': 'as reported'},
        {'item': 'Ozone absorption near 260 nm', 'value': '3000 L mol⁻¹ cm⁻¹', 'source': 'Levanov et al. (2016)',
         'checked': 'Levanov et al. (2016)', 'result': '2992 ± 71 measured; 3000 recommended'},
        {'item': 'Workplace limits', 'value': '0.1 ppm (OSHA 8 h, NIOSH ceiling), 5 ppm IDLH', 'source': 'NIOSH Pocket Guide',
         'checked': 'NIOSH Pocket Guide', 'result': 'as listed'},
        {'item': 'Generator gas', 'value': 'up to 300 g/Nm³', 'source': 'De Smedt et al. (2002)',
         'checked': 'MKS SEMOZON data (2020s)', 'result': 'current generators exceed 400 g/Nm³'},
    ]


# ---------------------------------------------------------------- Figure 7
FONT = "'Times New Roman', Times, 'Liberation Serif', serif"


def figure(sol, hl, loo, path):
    W, H = 640, 905
    o = [f'<svg id="fig7" class="plot" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
         f'aria-label="Model against published measurements" font-family="{FONT}">',
         f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>']
    T = lambda x, y, s, size=12, a='middle', extra='': o.append(
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{a}"{extra}>{s}</text>')
    L = lambda x1, y1, x2, y2, w=1.0, c='#000000', d=None: o.append(
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{w}"'
        + (f' stroke-dasharray="{d}"' if d else '') + '/>')
    frame = lambda x0, y0, x1, y1: o.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" '
                                            'stroke="#000000" stroke-width="1"/>')
    # ---- (a) solubility, model / measured
    rows = [r for r in sol['rows'] if r['year'] >= 1950]
    rows.sort(key=lambda r: -r['year'])
    X0, X1, Y0 = 200, 620, 30
    dy = 19
    Y1 = Y0 + dy * len(rows) + 8
    xs = lambda v: X0 + (X1 - X0) * (v - 0.6) / 0.8
    T(12, 18, '(a) Ozone solubility: the model divided by each measurement', 13, 'start', ' font-weight="bold"')
    o.append(f'<rect x="{xs(0.8):.1f}" y="{Y0}" width="{xs(1.2) - xs(0.8):.1f}" height="{Y1 - Y0}" fill="#eeeeee"/>')
    frame(X0, Y0, X1, Y1)
    L(xs(1.0), Y0, xs(1.0), Y1, 1, '#808080', '4 3')
    for i, r in enumerate(rows):
        y = Y0 + 14 + i * dy
        T(X0 - 8, y + 4, f"{r['source']} {r['year']}", 12, 'end')
        o.append(f'<circle cx="{xs(r["ratio"]):.1f}" cy="{y:.1f}" r="4" fill="#cc0000"/>')
    for v in (0.6, 0.8, 1.0, 1.2, 1.4):
        L(xs(v), Y1, xs(v), Y1 - 5)
        T(xs(v), Y1 + 15, f'{v:.1f}', 12)
    T((X0 + X1) / 2, Y1 + 31, 'H model / H measured, at the temperature of each measurement (grey: within 20 %)', 12)
    # ---- (b) half-life at pH 7
    top = Y1 + 58
    X0, X1, Y0, Y1 = 70, 600, top + 14, top + 254
    tl, th, lo, hi = 10.0, 40.0, -1.0, 2.5           # log10 minutes
    xs = lambda t: X0 + (X1 - X0) * (t - tl) / (th - tl)
    ys = lambda m: Y1 - (Y1 - Y0) * (math.log10(max(m, 1e-3)) - lo) / (hi - lo)
    T(12, top, '(b) Half-life of dissolved ozone: quoted by tool makers against the rate law', 13, 'start', ' font-weight="bold"')
    frame(X0, Y0, X1, Y1)
    for m in (0.1, 0.3, 1, 3, 10, 30, 100, 300):
        if lo <= math.log10(m) <= hi:
            L(X0, ys(m), X0 + 5, ys(m))
            T(X0 - 6, ys(m) + 4, f'{m:g}', 12, 'end')
    for t in range(10, 41, 5):
        L(xs(t), Y1, xs(t), Y1 - 5)
        T(xs(t), Y1 + 15, str(t), 12)
    T((X0 + X1) / 2, Y1 + 31, 'temperature (°C)', 12)
    o.append(f'<text x="22" y="{(Y0 + Y1) / 2:.1f}" font-size="12" text-anchor="middle" '
             f'transform="rotate(-90 22 {(Y0 + Y1) / 2:.1f})">half-life (min)</text>')
    styles = {'5 mg/L, pH 7': ('#000000', ''), '20 mg/L, pH 7': ('#000000', '6 4'), '90 mg/L, pH 7': ('#000000', '2 3'),
              '90 mg/L, pH 4.5 (CO₂)': ('#0000cc', '')}
    for label, pts in hl['curves'].items():
        c, d = styles[label]
        dd = ' L'.join(f'{xs(t):.1f},{ys(m):.1f}' for t, m in pts)
        o.append(f'<path d="M{dd}" fill="none" stroke="{c}" stroke-width="1.5"' + (f' stroke-dasharray="{d}"' if d else '') + '/>')
    for i, (label, (c, d)) in enumerate(styles.items()):
        lx, ly = X0 + (i % 2) * 270, Y1 + 50 + (i // 2) * 17
        o.append(f'<line x1="{lx}" y1="{ly - 4}" x2="{lx + 30}" y2="{ly - 4}" stroke="{c}" stroke-width="1.5"'
                 + (f' stroke-dasharray="{d}"' if d else '') + '/>')
        T(lx + 36, ly, 'rate law, ' + label, 11, 'start', f' fill="{c}"' if c != '#000000' else '')
    for t, q in MKS_HALF_LIFE:
        o.append(f'<rect x="{xs(t) - 4:.1f}" y="{ys(q) - 4:.1f}" width="8" height="8" fill="#cc0000"/>')
    a = hl['acm']
    o.append(f'<polygon points="{xs(a["T_C"]):.1f},{ys(a["quoted_min"]) - 12:.1f} {xs(a["T_C"]) - 5:.1f},{ys(a["quoted_min"]) - 3:.1f} '
             f'{xs(a["T_C"]) + 5:.1f},{ys(a["quoted_min"]) - 3:.1f}" fill="#ffffff" stroke="#cc0000" stroke-width="1.2"/>')
    T(xs(30.5), ys(30) - 4, 'squares: MKS data sheet, pH 7', 11, 'start', ' fill="#cc0000"')
    T(xs(30.5), ys(30) + 10, 'triangle: ACM patent, 90 ppm, pH 7', 11, 'start', ' fill="#cc0000"')
    # ---- (c) strip rate, leave one out
    top = Y1 + 104
    X0, X1, Y0, Y1 = 120, 420, top + 14, top + 214
    lo, hi = math.log10(50), math.log10(1000)
    xs = lambda v: X0 + (X1 - X0) * (math.log10(v) - lo) / (hi - lo)
    ys = lambda v: Y1 - (Y1 - Y0) * (math.log10(v) - lo) / (hi - lo)
    T(12, top, '(c) Strip rate: each source predicted from the other two', 13, 'start', ' font-weight="bold"')
    frame(X0, Y0, X1, Y1)
    o.append(f'<path d="M{xs(50):.1f},{ys(50):.1f} L{xs(1000):.1f},{ys(1000):.1f}" stroke="#000000" stroke-width="1" fill="none"/>')
    for f in (2.0, 0.5):
        a0, a1 = (50, 500) if f > 1 else (100, 1000)
        o.append(f'<path d="M{xs(a0):.1f},{ys(a0 * f):.1f} L{xs(a1):.1f},{ys(a1 * f):.1f}" stroke="#808080" '
                 'stroke-width="1" stroke-dasharray="4 3" fill="none"/>')
    for v in (50, 100, 200, 500, 1000):
        L(xs(v), Y1, xs(v), Y1 - 5); T(xs(v), Y1 + 15, str(v), 12)
        L(X0, ys(v), X0 + 5, ys(v)); T(X0 - 6, ys(v) + 4, str(v), 12, 'end')
    T((X0 + X1) / 2, Y1 + 31, 'published (nm/min)', 12)
    o.append(f'<text x="{X0 - 44}" y="{(Y0 + Y1) / 2:.1f}" font-size="12" text-anchor="middle" '
             f'transform="rotate(-90 {X0 - 44} {(Y0 + Y1) / 2:.1f})">predicted (nm/min)</text>')
    for r in loo:
        x, y = xs(r['published']), ys(r['predicted'])
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#cc0000"/>')
        T(x + 8, y + 4, r['left_out'], 11, 'start')
    T(436, Y0 + 24, 'line: prediction equals', 12, 'start')
    T(436, Y0 + 40, 'the published value', 12, 'start')
    T(436, Y0 + 60, 'dashed: a factor of 2', 12, 'start')
    o.append('</svg>')
    svg = '\n'.join(o) + '\n'
    assert '–' not in svg and '—' not in svg
    path.write_text(svg, encoding='utf-8')


if __name__ == '__main__':
    sol, hl, loo, mech = solubility(), half_life_industry(), leave_one_out(), mechanism_constants()
    out = {'solubility': sol, 'half_life': hl, 'leave_one_out': loo, 'heated_wafer': heated_wafer(), 'film': film(),
           'mechanism': mech, 'inputs': inputs(sol, hl, mech)}
    (here / 'validation.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    figure(sol, hl, loo, here / 'validation.svg')
    s = out['solubility']
    print(f"solubility: {s['modern_n']} measurements since 1950, model/measured median {s['modern_median_ratio']:.2f}, "
          f"range {s['modern_min']:.2f} to {s['modern_max']:.2f}, {s['modern_within_20pct']} within 20 %")
    for r in hl['mks']:
        print(f"half-life {r['T_C']:.0f} C: quoted {r['quoted_min']:.0f} min; model 5/10/20/90 mg/L "
              f"{r['model_5']:.1f}/{r['model_10']:.1f}/{r['model_20']:.1f}/{r['model_90']:.2f} min")
    print(f"ACM 90 ppm 25 C: quoted 15 min; model pH 7 {hl['acm']['model_pH7']:.1f}, pH 4.5 {hl['acm']['model_pH4_5']:.1f}, "
          f"pH 4 {hl['acm']['model_pH4']:.1f} min")
    for r in loo:
        print(f"leave out {r['left_out']}: published {r['published']:.0f}, predicted {r['predicted']:.0f} nm/min ({r['ratio']:.2f})")
    hw = out['heated_wafer']
    print(f"heated wafer: NEC 1 : 2 : 3; model 60 C x{hw['model_ratio_60C']:.2f}, 80 C x{hw['model_ratio_80C']:.2f}")
    print(f"mechanism: {mech}")
    print(f"wave parameter at mid-radius {out['film']['lambda_mid']:.1e} (waves below {out['film']['threshold']:.0e})")
