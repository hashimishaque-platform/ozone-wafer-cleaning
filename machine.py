"""A closed-loop machine for ozonated-water resist strip: its design point, found with the model,
and its use of water, ozone, oxygen, energy and exhaust per wafer, against the open test-rig
process and against single-wafer SPM.

    python3 machine.py      -> machine.json (tables on the page) and machine_space.svg (Figure 14)

The machine differs from the test rig in four ways that the model can describe:

1. A quartz cover sits 3 mm above the wafer, so the gas over the film is a thin, closed layer.
2. That layer is fed with the off-gas of the contactor (the ozone the water did not take up),
   so the surface of the film stays near saturation instead of losing ozone to fresh air. In the
   model this is the gas above the film at the mole fraction of the off-gas.
3. The supply line is short (1 m, 4 mm inside) and the heater sits next to the nozzle.
4. Heat is recovered from the drain, and the oxygen behind the destruct unit is dried and fed
   back to the generator.

The footprint per wafer counts the strip step only (300 mm wafer, 1 um of resist, until the
slowest point is clear), plus a rinse that is the same for every option. Assumptions that do not
come from the model are listed in ASSUMPTIONS with their sources.
"""
import json
import math
from pathlib import Path

from dio3 import properties as P, film as F
from dio3.process import Process, simulate
from dio3.supply import Supply, deliver
from dio3.resist import Resist

here = Path(__file__).resolve().parent

ASSUMPTIONS = {
    'generator_Wh_per_g': (12.0, 'about 10 to 20 times the theoretical 0.82 Wh/g for oxygen-fed corona generators '
                                 '(Oxidation Technologies); 12 Wh/g taken'),
    'upw_Wh_per_L': (9.0, 'ultrapure water: 9.0 kWh/m3 (SEMI S23 model) to 18.1 kWh/m3 (IRDS energy-equivalent model), '
                          'UPM 2022; the lower value taken'),
    'upw_inlet_C': (20.0, 'ultrapure water supplied at 20 C'),
    'heat_recovery': (0.6, 'counterflow PFA exchanger between the drain and the water to the heater; assumed'),
    'oxygen_recovery': (0.6, 'oxygen recovered behind the destruct and fed back to the generator; at least 60 % in '
                             'commercial units for ozone plants (Linde OZORA)'),
    'chiller_COP': (3.0, 'assumed'),
    'rinse_L': (0.75, 'rinse with ozone-free water, 30 s at 1.5 L/min, the same for every option'),
    'rig_exhaust_m3h': (100.0, 'open chamber of the test rig'),
    'machine_exhaust_m3h': (10.0, 'enclosure purge of the closed module, plus the cover gas'),
    'spm_per_wafer_L': ((0.45, 2.4), 'single-wafer SPM: about 0.45 L of H2O2 and 2.4 L of H2SO4 per wafer, from the savings '
                                     'ACM Research reports for 2000 wafers a day (852 L/day of H2O2 is 94 %, 1608 L/day of '
                                     'H2SO4 is 33 %); SPM 4:1 at 120 C'),
}
A = {k: v[0] for k, v in ASSUMPTIONS.items()}
CP = 4180.0          # J/(kg K)


def offgas_mole_fraction(s: Supply, Q, T_process, pH):
    """Ozone mole fraction of the gas leaving the contactor: generator ozone less what dissolved."""
    d = deliver(s, Q, T_process, pH)
    f_gas = s.gas_flow_Nlpm / 60e3 / P.MOLAR_VOLUME_NORMAL         # mol/s of generator gas
    n_gen, n_dis = d['y_gas'] * f_gas, d['ozone_dissolved']
    return max(n_gen - n_dis, 0.0) / max(f_gas - n_dis, 1e-30), f_gas - n_dis


def footprint(p: Process, r, closed):
    """Use of water, ozone, oxygen, energy and exhaust air per wafer for the strip step."""
    t = r['time_to_clear']
    s = r['supply']
    rho = P.water_density(p.T)
    q = p.flow_lpm / 60e3                                           # m3/s
    water = p.flow_lpm * t / 60.0 + A['rinse_L']                    # L
    o3_g = s['ozone_from_generator'] * P.M_O3 * 1e3 * t             # g made while dispensing
    o2_NL = p.supply.gas_flow_Nlpm * t / 60.0 * (1 - (A['oxygen_recovery'] if closed else 0.0))
    dT_heat = max(p.T - max(p.supply.T_contactor, A['upw_inlet_C'] + 273.15), 0.0) + \
        max(p.supply.T_contactor - (A['upw_inlet_C'] + 273.15), 0.0)
    heat_kWh = q * rho * CP * dT_heat * t * (1 - (A['heat_recovery'] if closed else 0.0)) / 3.6e6
    chill = max(A['upw_inlet_C'] + 273.15 - p.supply.T_contactor, 0.0)
    chill_kWh = q * rho * CP * chill * t / A['chiller_COP'] / 3.6e6
    gen_kWh = o3_g * A['generator_Wh_per_g'] / 1000.0
    upw_kWh = water * A['upw_Wh_per_L'] / 1000.0
    exhaust_m3 = (A['machine_exhaust_m3h'] if closed else A['rig_exhaust_m3h']) * t / 3600.0
    used = r['budget']['resist'] * t                                # mol of ozone into the resist
    return {
        'time_to_clear_min': t / 60.0, 'strip_mean_nm_min': r['strip_mean'] * 6e10, 'nonuniformity': r['nonuniformity'],
        'water_L': water, 'ozone_g': o3_g, 'oxygen_NL': o2_NL, 'exhaust_m3': exhaust_m3,
        'energy_kWh': {'generator': gen_kWh, 'heating': heat_kWh, 'chiller': chill_kWh, 'ultrapure water': upw_kWh},
        'energy_total_kWh': gen_kWh + heat_kWh + chill_kWh + upw_kWh,
        'ozone_used_fraction': used * P.M_O3 * 1e3 / o3_g if o3_g > 0 else 0.0,
        'c_nozzle_mg_L': P.mg_per_L(s['c_nozzle']), 'supersaturation': s['supersaturation'],
    }


def rig():
    p = Process()
    r = simulate(p, profile_radii=())
    return p, r


def machine_case(T, rpm, q, gas_flow, pH, T_contactor=293.15, gas=300.0, n_layers=32, n_steps=200):
    sup = Supply(gas_g_per_Nm3=gas, pressure=P.P_ATM, T_contactor=T_contactor, approach=0.9,
                 line_length=1.0, line_diameter=4e-3, gas_flow_Nlpm=gas_flow)
    y_off, f_off = offgas_mole_fraction(sup, q / 60e3, T, pH)
    p = Process(T=T, pH=pH, flow_lpm=q, rpm=rpm, ambient=str(y_off * 1e6), supply=sup,
                exhaust_m3h=A['machine_exhaust_m3h'], n_layers=n_layers, n_steps=n_steps)
    r = simulate(p, profile_radii=())
    absorbed = max(r['budget']['gas_exchange'], 0.0)
    depletion = absorbed / max(y_off * f_off, 1e-30)
    Q, w = q / 60e3, rpm * 2 * math.pi / 60
    h_edge = F.film_thickness(p.diameter / 2, Q, w, P.kinematic_viscosity(T))
    return p, r, {'y_off': y_off, 'depletion': depletion, 'h_edge_um': h_edge * 1e6, 'inertia_mid': r['inertia_mid']}


def feasible(info, r):
    return (r['supply']['supersaturation'] <= 2.0 and info['h_edge_um'] >= 20.0 and info['depletion'] <= 0.3
            and info['inertia_mid'] <= 0.5)


def search():
    space = []
    for T_c in (293.15, 283.15):
        for pH in (4.5, 5.6):
            for gas_flow in (1.0, 2.0, 3.0):
                for q in (0.5, 0.8, 1.0, 1.5, 2.0):
                    for T in (298.15, 303.15, 308.15, 313.15, 318.15, 323.15):
                        for rpm in (300.0, 500.0, 800.0, 1200.0, 1600.0):
                            p, r, info = machine_case(T, rpm, q, gas_flow, pH, T_c)
                            fp = footprint(p, r, closed=True)
                            space.append({'T_C': T - 273.15, 'rpm': rpm, 'flow_lpm': q, 'gas_flow_Nlpm': gas_flow, 'pH': pH,
                                          'T_contactor_C': T_c - 273.15, 'feasible': feasible(info, r), **info,
                                          'time_to_clear_min': fp['time_to_clear_min'], 'water_L': fp['water_L'],
                                          'ozone_g': fp['ozone_g'], 'energy_total_kWh': fp['energy_total_kWh'],
                                          'supersaturation': fp['supersaturation']})
    return space


def pick(space):
    """Among the feasible settings within 15 % of the shortest time to clear, the one that makes the
    least ozone, then uses the least water."""
    ok = [s for s in space if s['feasible']]
    t_min = min(s['time_to_clear_min'] for s in ok)
    near = [s for s in ok if s['time_to_clear_min'] <= 1.15 * t_min]
    return min(near, key=lambda s: (round(s['ozone_g'], 2), s['water_L']))


def pareto(space):
    ok = sorted([s for s in space if s['feasible']], key=lambda s: (s['time_to_clear_min'], s['water_L']))
    front, best_w = [], float('inf')
    for s in ok:
        if s['water_L'] < best_w - 1e-9:
            front.append(s)
            best_w = s['water_L']
    return front


def contributions(best):
    """From the rig to the machine one change at a time, to show where the gain comes from."""
    T, rpm, q, gf, pH, Tc = (best['T_C'] + 273.15, best['rpm'], best['flow_lpm'], best['gas_flow_Nlpm'], best['pH'],
                             best['T_contactor_C'] + 273.15)
    sup = Supply(gas_g_per_Nm3=300.0, pressure=P.P_ATM, T_contactor=Tc, approach=0.9, line_length=1.0,
                 line_diameter=4e-3, gas_flow_Nlpm=gf)
    out = []
    p = Process()
    out.append(('Test rig, default settings', p, False))
    out.append(('Supply: 300 g/Nm³, contactor at %.0f °C, CO₂ to pH %.1f, short line' % (Tc - 273.15, pH),
                Process(pH=pH, supply=sup), False))
    out.append(('Process: %.0f °C, %.0f rpm, %.1f L/min' % (T - 273.15, rpm, q),
                Process(T=T, pH=pH, flow_lpm=q, rpm=rpm, supply=sup), False))
    y_off, _ = offgas_mole_fraction(sup, q / 60e3, T, pH)
    covered = Process(T=T, pH=pH, flow_lpm=q, rpm=rpm, supply=sup, ambient=str(y_off * 1e6), exhaust_m3h=A['machine_exhaust_m3h'])
    out.append(('Cover with the contactor off-gas', covered, False))
    out.append(('Recovery of heat and oxygen, small exhaust', covered, True))
    out.append(('Option: megasonics (mass transfer x 1.65, Dussault et al. 2014)',
                Process(**{**covered.__dict__, 'enhancement': 1.65}), True))
    rows = []
    for label, proc, closed in out:
        r = simulate(proc, profile_radii=())
        fp = footprint(proc, r, closed=closed)
        rows.append({'step': label, 'time_to_clear_min': fp['time_to_clear_min'], 'water_L': fp['water_L'],
                     'ozone_g': fp['ozone_g'], 'oxygen_NL': fp['oxygen_NL'], 'energy_kWh': fp['energy_total_kWh'],
                     'exhaust_m3': fp['exhaust_m3'], 'ozone_used_fraction': fp['ozone_used_fraction'],
                     'supersaturation': fp['supersaturation'], 'c_nozzle_mg_L': fp['c_nozzle_mg_L']})
    return rows


def ring_options(best):
    """A second dispense ring for the slow edge: time to clear and water for a few rings."""
    rows = []
    for r2, q2 in ((0.05, 0.5), (0.05, 1.0), (0.07, 1.0), (0.09, 1.0)):
        p, _, _ = machine_case(best['T_C'] + 273.15, best['rpm'], best['flow_lpm'], best['gas_flow_Nlpm'], best['pH'],
                               best['T_contactor_C'] + 273.15)
        sup = p.supply
        y_off, _ = offgas_mole_fraction(sup, (best['flow_lpm'] + q2) / 60e3, p.T, p.pH)
        pr = Process(**{**p.__dict__, 'ring_radius': r2, 'ring_flow_lpm': q2, 'ambient': str(y_off * 1e6)})
        r = simulate(pr, profile_radii=())
        t = r['time_to_clear'] / 60.0
        rows.append({'ring_radius_mm': r2 * 1000, 'ring_flow_lpm': q2, 'time_to_clear_min': t,
                     'water_L': (best['flow_lpm'] + q2) * t + A['rinse_L'], 'nonuniformity': r['nonuniformity']})
    return rows


def figure(space, rig_fp, chosen, path):
    """Figure 14: every setting searched, time to clear against water per wafer."""
    W, H = 640, 430
    X0, X1, Y0, Y1 = 70, 610, 20, 360
    ts = [s['time_to_clear_min'] for s in space] + [rig_fp['time_to_clear_min']]
    ws = [s['water_L'] for s in space] + [rig_fp['water_L']]
    t_hi = math.ceil(min(max(ts), 30.0) + 0.5)
    w_hi = math.ceil(min(max(ws), 40.0) / 2 + 0.5) * 2
    xs = lambda t: X0 + (X1 - X0) * min(t, t_hi) / t_hi
    ys = lambda w: Y1 - (Y1 - Y0) * min(w, w_hi) / w_hi
    o = [f'<svg id="fig14" class="plot" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
         'aria-label="Design space of the closed-loop machine" font-family="\'Times New Roman\', Times, \'Liberation Serif\', serif">',
         f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>',
         f'<rect x="{X0}" y="{Y0}" width="{X1 - X0}" height="{Y1 - Y0}" fill="none" stroke="#000000" stroke-width="1"/>']

    def ticks(hi):
        step = [1, 2, 5, 10][[hi / s <= 8 for s in (1, 2, 5, 10)].index(True)]
        return [k * step for k in range(0, int(hi // step) + 1)]
    for t in ticks(t_hi):
        o.append(f'<line x1="{xs(t):.1f}" y1="{Y1}" x2="{xs(t):.1f}" y2="{Y1 - 5}" stroke="#000000"/>'
                 f'<text x="{xs(t):.1f}" y="{Y1 + 16}" font-size="12" text-anchor="middle">{t:g}</text>')
    for w in ticks(w_hi):
        o.append(f'<line x1="{X0}" y1="{ys(w):.1f}" x2="{X0 + 5}" y2="{ys(w):.1f}" stroke="#000000"/>'
                 f'<text x="{X0 - 6}" y="{ys(w) + 4:.1f}" font-size="12" text-anchor="end">{w:g}</text>')
    o.append(f'<text x="{(X0 + X1) / 2}" y="{Y1 + 34}" font-size="13" text-anchor="middle">time to clear 1 µm of resist (min)</text>')
    o.append(f'<text x="22" y="{(Y0 + Y1) / 2}" font-size="13" text-anchor="middle" transform="rotate(-90 22 {(Y0 + Y1) / 2})">'
             'water per wafer (L)</text>')
    seen = set()
    for feasible in (False, True):
        for s in space:
            if s['feasible'] != feasible:
                continue
            key = (feasible, round(xs(s['time_to_clear_min'])), round(ys(s['water_L'])))
            if key in seen:
                continue
            seen.add(key)
            if feasible:
                o.append(f'<circle cx="{key[1]}" cy="{key[2]}" r="2.2" fill="#555555"/>')
            else:
                o.append(f'<circle cx="{key[1]}" cy="{key[2]}" r="1.8" fill="none" stroke="#aaaaaa" stroke-width="0.8"/>')
    front = pareto(space)
    o.append('<path d="M' + ' L'.join(f'{xs(s["time_to_clear_min"]):.1f},{ys(s["water_L"]):.1f}' for s in front) +
             '" fill="none" stroke="#000000" stroke-width="1.2"/>')
    for q in sorted({s['flow_lpm'] for s in space}):
        g = [s for s in space if s['flow_lpm'] == q]          # label beyond the last dot of the ray, grey or dark
        if any(s['feasible'] for s in g):
            end = max(g, key=lambda s: s['time_to_clear_min'])
            x = min(xs(end['time_to_clear_min']) + 6, X1 - 50)
            o.append(f'<text x="{x:.1f}" y="{ys(end["water_L"]) + 4:.1f}" font-size="11">{q:g} L/min</text>')
    cx, cy = xs(chosen['time_to_clear_min']), ys(chosen['water_L'])
    o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="#cc0000"/>')
    o.append(f'<text x="{cx - 10:.1f}" y="{cy - 8:.1f}" font-size="12" text-anchor="end" fill="#cc0000">chosen point</text>')
    rx, ry = xs(rig_fp['time_to_clear_min']), ys(rig_fp['water_L'])
    o.append(f'<rect x="{rx - 5:.1f}" y="{ry - 5:.1f}" width="10" height="10" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>')
    o.append(f'<text x="{rx - 10:.1f}" y="{ry + 4:.1f}" font-size="12" text-anchor="end">test rig, default settings</text>')
    o.append(f'<text x="{X1 - 8}" y="{Y1 - 40}" font-size="12" text-anchor="end">dark dots: settings that pass the limits; open</text>')
    o.append(f'<text x="{X1 - 8}" y="{Y1 - 24}" font-size="12" text-anchor="end">grey: bubbles, too thin a film or too little cover gas;</text>')
    o.append(f'<text x="{X1 - 8}" y="{Y1 - 8}" font-size="12" text-anchor="end">line: least water for a given time</text>')
    o.append('</svg>')
    path.write_text('\n'.join(o) + '\n', encoding='utf-8')


def main():
    p0, r0 = rig()
    rig_fp = footprint(p0, r0, closed=False)
    space = search()
    best = pick(space)
    p1, r1, info = machine_case(best['T_C'] + 273.15, best['rpm'], best['flow_lpm'], best['gas_flow_Nlpm'], best['pH'],
                                best['T_contactor_C'] + 273.15, n_layers=48, n_steps=400)
    machine_fp = footprint(p1, r1, closed=True)
    bare = simulate(Process(**{**p1.__dict__, 'resist': Resist(k_wall_ref=0.0)}), profile_radii=())
    q1 = p1.flow_lpm / 60e3
    endpoint = {'drain_with_resist_mg_L': P.mg_per_L(r1['budget']['edge'] / q1),
                'drain_bare_mg_L': P.mg_per_L(bare['budget']['edge'] / q1),
                'cover_gas_escape_with_resist_mol_s': -r1['budget']['gas_exchange'],
                'cover_gas_escape_bare_mol_s': -bare['budget']['gas_exchange']}
    # the same machine settings without the cover gas, to show what the cascade does
    p2 = Process(**{**p1.__dict__, 'ambient': 'air', 'exhaust_m3h': A['rig_exhaust_m3h']})
    r2 = simulate(p2, profile_radii=())
    no_cover_fp = footprint(p2, r2, closed=False)
    steps = contributions(best)
    rings = ring_options(best)
    spm_h2o2, spm_h2so4 = A['spm_per_wafer_L']
    out = {
        'assumptions': {k: {'value': v[0], 'note': v[1]} for k, v in ASSUMPTIONS.items()},
        'rig': {'settings': {'T_C': 25.0, 'rpm': 500.0, 'flow_lpm': 1.5, 'gas_g_per_Nm3': 200.0, 'gas_flow_Nlpm': 2.0,
                             'ambient': 'air'}, 'footprint': rig_fp,
                'budget_mol_s': r0['budget']},
        'machine': {'settings': {'T_C': best['T_C'], 'rpm': best['rpm'], 'flow_lpm': best['flow_lpm'],
                                 'gas_g_per_Nm3': 300.0, 'gas_flow_Nlpm': best['gas_flow_Nlpm'], 'pH': best['pH'],
                                 'T_contactor_C': best['T_contactor_C'], 'cover_gas_ozone_vol_pct': info['y_off'] * 100,
                                 'cover_gas_depletion': info['depletion'], 'h_edge_um': info['h_edge_um']},
                    'footprint': machine_fp, 'budget_mol_s': r1['budget']},
        'machine_without_cover_gas': {'footprint': no_cover_fp},
        'steps': steps,
        'endpoint': endpoint,
        'rings': rings,
        'spm': {'H2O2_L': spm_h2o2, 'H2SO4_L': spm_h2so4, 'note': ASSUMPTIONS['spm_per_wafer_L'][1]},
        'search': {'n': len(space), 'feasible': sum(s['feasible'] for s in space),
                   'pareto': [{k: s[k] for k in ('time_to_clear_min', 'water_L', 'T_C', 'rpm', 'flow_lpm', 'gas_flow_Nlpm', 'pH')}
                              for s in pareto(space)]},
    }
    (here / 'machine.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    figure(space, rig_fp, {'time_to_clear_min': machine_fp['time_to_clear_min'], 'water_L': machine_fp['water_L']},
           here / 'machine_space.svg')
    f = lambda d: {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items() if k != 'energy_kWh'}
    print('searched', len(space), 'settings,', out['search']['feasible'], 'feasible')
    print('rig     ', f(rig_fp))
    print('machine ', out['machine']['settings'])
    print('machine ', f(machine_fp))
    print('no cover', f(no_cover_fp))
    for row in rings:
        print('ring', {k: round(v, 3) for k, v in row.items()})
    for row in steps:
        print(f"{row['step'][:60]:60s} t {row['time_to_clear_min']:.2f} min  water {row['water_L']:.1f} L  O3 {row['ozone_g']:.2f} g  "
              f"O2 {row['oxygen_NL']:.1f} NL  E {row['energy_kWh']:.3f} kWh  exh {row['exhaust_m3']:.2f} m3  "
              f"used {row['ozone_used_fraction']*100:.1f} %  S {row['supersaturation']:.2f}  c {row['c_nozzle_mg_L']:.0f}")


if __name__ == '__main__':
    main()
