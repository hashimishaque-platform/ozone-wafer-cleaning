// Browser version of the Python package dio3 (same equations, same numbers; checked by crosscheck.js).
// Units: SI inside, temperatures in kelvin, dissolved ozone in mol/m3.
'use strict';

const RGAS = 8.314462618, P_ATM = 101325.0, T_ZERO = 273.15;
const M_O3 = 47.998e-3, M_O2 = 31.998e-3;
const V_NORMAL = RGAS * T_ZERO / P_ATM;

// ---------------------------------------------------------------- properties
function waterDensity(T) {            // Kell (1975)
  const t = T - T_ZERO;
  const n = 999.83952 + 16.945176 * t - 7.9870401e-3 * t ** 2 - 46.170461e-6 * t ** 3 + 105.56302e-9 * t ** 4 - 280.54253e-12 * t ** 5;
  return n / (1 + 16.879850e-3 * t);
}
function waterViscosity(T) {          // Kestin, Sokolov and Wakeham (1978)
  const t = T - T_ZERO, d = 20 - t;
  const s = 1.2378 * d - 1.303e-3 * d ** 2 + 3.06e-6 * d ** 3 + 2.55e-8 * d ** 4;
  return 1002.0e-6 * Math.pow(10, s / (96 + t));
}
const kinematicViscosity = (T) => waterViscosity(T) / waterDensity(T);
const ozoneDiffusivity = (T) => 1.1e-6 * Math.exp(-1896 / T);            // Johnson and Davis (1996)
const henryO3 = (T) => 1.0e-4 * Math.exp(2800 * (1 / T - 1 / 298.15));   // Burkholder et al. (2019)
const henryCO2 = (T) => 3.4e-4 * Math.exp(2300 * (1 / T - 1 / 298.15));
const moleFractionFromGNm3 = (c) => (c / (M_O3 * 1e3)) * V_NORMAL;
function moleFractionFromWt(w) { const a = w / M_O3, b = (1 - w) / M_O2; return a / (a + b); }
function wtFromMoleFraction(y) { const a = y * M_O3, b = (1 - y) * M_O2; return a / (a + b); }
const gNm3FromMoleFraction = (y) => y / V_NORMAL * M_O3 * 1e3;
const mgL = (c) => c * M_O3 * 1e3;
const molm3 = (ppm) => ppm / (M_O3 * 1e3);
const equilibriumOzone = (T, y, p) => henryO3(T) * y * (p === undefined ? P_ATM : p);

// ---------------------------------------------------------------- decomposition (engineering law)
const DEC = { Tacid: 295.15, tHalfAcid: 3.5 * 3600, EaAcid: 39.6e3, Tbase: 292.15, EaBase: 76.0e3 };
const k1 = (T) => Math.log(2) / DEC.tHalfAcid * Math.exp(-DEC.EaAcid / RGAS * (1 / T - 1 / DEC.Tacid));
const k2 = (pH, T) => 1e-3 * Math.pow(10, -2.66 + 0.49 * pH) * Math.exp(-DEC.EaBase / RGAS * (1 / T - 1 / DEC.Tbase));
function concentrationAfter(c0, t, pH, T) {
  const a = k1(T), b = k2(pH, T);
  if (t <= 0 || c0 <= 0) return c0;
  const e = Math.exp(-a * t);
  return a * c0 * e / (a + b * c0 * (1 - e));
}
function halfLife(c0, pH, T) { const a = k1(T), b = k2(pH, T); return Math.log((2 * a + b * c0) / (a + b * c0)) / a; }
function timeToFraction(c0, frac, pH, T) {   // time for c0 to fall to frac * c0
  const a = k1(T), b = k2(pH, T);
  return -Math.log(frac * (a + b * c0) / (a + frac * b * c0)) / a;
}

// ---------------------------------------------------------------- pH of water holding CO2 (25 degC constants)
function phFromCO2(pCO2, T) {
  const co2 = henryCO2(T || 298.15) * pCO2 * 1e-3;
  const ka1 = Math.pow(10, -6.35), ka2 = Math.pow(10, -10.33), kw = 1e-14;
  let lo = 1e-14, hi = 1;
  for (let i = 0; i < 200; i++) {
    const h = Math.sqrt(lo * hi);
    const f = h - (ka1 * co2 / h + 2 * ka1 * ka2 * co2 / (h * h) + kw / h);
    if (f > 0) hi = h; else lo = h;
  }
  return -Math.log10(Math.sqrt(lo * hi));
}
// CO2 partial pressure (Pa) that brings pure water to a pH, the inverse of phFromCO2 (0 above pH 7)
function co2PressureForPH(pH, T) {
  const h = Math.pow(10, -pH), ka1 = Math.pow(10, -6.35), ka2 = Math.pow(10, -10.33), kw = 1e-14;
  if (h * h <= kw) return 0;
  const co2 = (h - kw / h) / (ka1 / h + 2 * ka1 * ka2 / (h * h));
  return co2 * 1e3 / henryCO2(T || 298.15);
}
// Resistivity (MOhm cm, at 25 degC as meters report it) of water brought to a pH with CO2 alone.
// Limiting molar conductivities in S cm2/mol: H+ and OH- from Light et al. (2005), HCO3- from the CRC Handbook.
const LAMBDA = { H: 349.19, OH: 199.24, HCO3: 44.5 };
function resistivityCO2(pH) {
  if (pH > 7 + 1e-9) return NaN;
  const h = Math.pow(10, -pH), oh = 1e-14 / h, hco3 = Math.max(h - oh, 0);
  return 1e-6 / ((LAMBDA.H * h + LAMBDA.OH * oh + LAMBDA.HCO3 * hco3) * 1e-3);
}

// ---------------------------------------------------------------- supply
function deliver(s, Q, Tp, pH) {
  const y = moleFractionFromGNm3(s.gas_g_per_Nm3);
  const cEq = equilibriumOzone(s.T_contactor, y, s.pressure);
  const cOut = s.approach * cEq;
  const vol = Math.PI * s.line_diameter ** 2 / 4 * s.line_length;
  const tau = vol / Q;
  const cNoz = concentrationAfter(cOut, tau, pH, Tp);
  const cSat = equilibriumOzone(Tp, y, P_ATM);
  return {
    y_gas: y, wt_gas: wtFromMoleFraction(y), c_contactor_eq: cEq, c_contactor_out: cOut,
    line_residence_time: tau, c_nozzle: cNoz, c_sat_nozzle: cSat, supersaturation: cNoz / cSat,
    ozone_from_generator: s.gas_flow_Nlpm / 60e3 / V_NORMAL * y, ozone_dissolved: Q * cOut,
    ozone_decayed_in_line: Q * (cOut - cNoz),
  };
}

// ---------------------------------------------------------------- film on the spinning substrate
const filmThickness = (r, Q, w, nu) => Math.pow(3 * nu * Q / (2 * Math.PI * w * w * r * r), 1 / 3);
function inertiaRatio(r, Q, w, nu) { return Q * filmThickness(r, Q, w, nu) / (2 * Math.PI * nu * r * r); }
function layers(n) {
  const faces = new Float64Array(n + 1), centres = new Float64Array(n);
  for (let i = 0; i <= n; i++) faces[i] = 0.5 * (1 - Math.cos(Math.PI * i / n));
  for (let i = 0; i < n; i++) centres[i] = 0.5 * (faces[i] + faces[i + 1]);
  return { faces, centres };
}
function stations(r0, R, n) {
  const out = new Float64Array(n + 1);
  for (let i = 0; i <= n; i++) { const s = i / n; out[i] = r0 + (R - r0) * s * s; }
  return out;
}
function thomas(a, b, c, d) {
  const n = b.length, cp = new Float64Array(n), dp = new Float64Array(n), x = new Float64Array(n);
  cp[0] = c[0] / b[0]; dp[0] = d[0] / b[0];
  for (let i = 1; i < n; i++) {
    const m = b[i] - a[i] * cp[i - 1];
    cp[i] = i < n - 1 ? c[i] / m : 0;
    dp[i] = (d[i] - a[i] * dp[i - 1]) / m;
  }
  x[n - 1] = dp[n - 1];
  for (let i = n - 2; i >= 0; i--) x[i] = dp[i] - cp[i] * x[i + 1];
  return x;
}

function solveFilm(inp, profileRadii) {
  const N = inp.n_layers || 48, NS = inp.n_steps || 400, r0 = inp.r0 || 5e-3;
  const { faces, centres: zc } = layers(N);
  const dz = new Float64Array(N), q = new Float64Array(N), dzc = new Float64Array(N - 1);
  const Fz = (z) => z * z / 2 - z * z * z / 6;
  for (let i = 0; i < N; i++) { dz[i] = faces[i + 1] - faces[i]; q[i] = 3 * inp.Q / (2 * Math.PI) * (Fz(faces[i + 1]) - Fz(faces[i])); }
  for (let i = 0; i < N - 1; i++) dzc[i] = zc[i + 1] - zc[i];
  const rs = stations(r0, inp.R, NS);
  let c = new Float64Array(N).fill(inp.c_in);
  const closed = inp.c_surface === null;
  const cs = closed ? 0 : inp.c_surface;
  const kw = inp.k_wall === undefined ? Infinity : inp.k_wall;
  const fluxes = (r, h) => {
    let gw;
    if (kw === 0) gw = 0;
    else if (!isFinite(kw)) gw = r * inp.D / (h * zc[0]);
    else gw = r / (1 / kw + h * zc[0] / inp.D);
    const gs = closed ? 0 : r * inp.D / (h * (1 - zc[N - 1]));
    return [gw, gs];
  };
  const want = (profileRadii || []).slice().sort((a, b) => a - b);
  const profiles = [];
  const outR = [rs[0]], outH = [], outWall = [], outSurf = [], outCm = [inp.c_in];
  const h0 = filmThickness(rs[0], inp.Q, inp.omega, inp.nu);
  let [gw0, gs0] = fluxes(rs[0], h0);
  outH.push(h0); outWall.push(gw0 * c[0] / rs[0]); outSurf.push(gs0 * (cs - c[N - 1]) / rs[0]);
  let totWall = 0, totSurf = 0, totDec = 0;
  const lower = new Float64Array(N), diag = new Float64Array(N), upper = new Float64Array(N), res = new Float64Array(N);
  const g = new Float64Array(N - 1), V = new Float64Array(N);
  for (let n = 1; n < rs.length; n++) {
    const r = rs[n], dr = rs[n] - rs[n - 1];
    const h = filmThickness(r, inp.Q, inp.omega, inp.nu);
    for (let i = 0; i < N - 1; i++) g[i] = r * inp.D / (h * dzc[i]);
    const [gw, gs] = fluxes(r, h);
    for (let i = 0; i < N; i++) V[i] = r * h * dz[i];
    const old = c;
    let x = Float64Array.from(c);
    for (let it = 0; it < 8; it++) {
      for (let i = 0; i < N; i++) {
        const rate = inp.k1 * x[i] + inp.k2 * x[i] * x[i];
        lower[i] = 0; upper[i] = 0;
        diag[i] = q[i] / dr + V[i] * (inp.k1 + 2 * inp.k2 * x[i]);
        res[i] = q[i] / dr * (x[i] - old[i]) + V[i] * rate;
      }
      for (let i = 0; i < N - 1; i++) {
        diag[i] += g[i]; diag[i + 1] += g[i];
        upper[i] = -g[i]; lower[i + 1] = -g[i];
        res[i] -= g[i] * (x[i + 1] - x[i]);
        res[i + 1] -= g[i] * (x[i] - x[i + 1]);
      }
      diag[0] += gw; res[0] += gw * x[0];
      diag[N - 1] += gs; res[N - 1] -= gs * (cs - x[N - 1]);
      for (let i = 0; i < N; i++) res[i] = -res[i];
      const step = thomas(lower, diag, upper, res);
      let mx = 0;
      for (let i = 0; i < N; i++) { x[i] += step[i]; mx = Math.max(mx, Math.abs(step[i])); }
      if (mx <= 1e-12 * Math.max(inp.c_in, 1e-30)) break;
    }
    c = x;
    const wall = gw * c[0], surf = gs * (cs - c[N - 1]);
    let dec = 0, qc = 0, qs = 0;
    for (let i = 0; i < N; i++) { dec += V[i] * (inp.k1 * c[i] + inp.k2 * c[i] * c[i]); qc += q[i] * c[i]; qs += q[i]; }
    totWall += 2 * Math.PI * wall * dr; totSurf += 2 * Math.PI * surf * dr; totDec += 2 * Math.PI * dec * dr;
    outR.push(r); outH.push(h); outWall.push(wall / r); outSurf.push(surf / r); outCm.push(qc / qs);
    while (want.length && r >= want[0] - 1e-12) profiles.push({ r: want.shift(), c: Float64Array.from(c) });
  }
  let edge = 0;
  for (let i = 0; i < N; i++) edge += q[i] * c[i];
  edge *= 2 * Math.PI;
  return {
    r: outR, h: outH, wall_flux: outWall, surface_flux: outSurf, c_mean: outCm, zeta: zc, profiles,
    budget: { in: inp.Q * inp.c_in, resist: totWall, gas_exchange: totSurf, decomposed: totDec, edge,
      closure: (inp.Q * inp.c_in + totSurf) - (totWall + totDec + edge) },
  };
}

function interp(x, xs, ys) {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (x <= xs[i]) { const f = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] + f * (ys[i] - ys[i - 1]); }
  return ys[ys.length - 1];
}
function areaAverage(r, y, rMin) {
  const ym = interp(rMin, r, y);
  const rr = [rMin], yy = [ym];
  for (let i = 0; i < r.length; i++) if (r[i] > rMin) { rr.push(r[i]); yy.push(y[i]); }
  let outer = 0;
  for (let i = 1; i < rr.length; i++) outer += 0.5 * (2 * Math.PI * rr[i] * yy[i] + 2 * Math.PI * rr[i - 1] * yy[i - 1]) * (rr[i] - rr[i - 1]);
  return (Math.PI * rMin * rMin * ym + outer) / (Math.PI * r[r.length - 1] ** 2);
}

// ---------------------------------------------------------------- whole process
const R_MIN = 0.01;
const DEFAULT_YIELD = M_O3 / 1200.0;     // 1 g of ozone per g of resist at 1200 kg/m3
function defaultProcess() {
  return {
    T: 298.15, pH: 5.6, flow_lpm: 1.5, rpm: 500, diameter: 0.300, ambient: 'air', enhancement: 1.0,
    resist_thickness: 1.0e-6, exhaust_m3h: 100.0, nozzle_ppm: null,
    supply: { gas_g_per_Nm3: 200.0, pressure: P_ATM, T_contactor: 298.15, approach: 1.0, line_length: 5.0, line_diameter: 6e-3, gas_flow_Nlpm: 2.0 },
    resist: { yield_m3_per_mol: DEFAULT_YIELD, density: 1200.0 },
    n_layers: 48, n_steps: 400,
  };
}
// rate constant at the resist surface (m/s): Infinity = transport-limited (default), 0 = inert surface (bare wafer)
function wallRate(resist, T) {
  const k = resist.k_wall_ref === undefined || resist.k_wall_ref === null ? Infinity : resist.k_wall_ref;
  if (!isFinite(k) || k === 0) return k;
  return k * Math.exp(-(resist.Ea_wall || 0) / RGAS * (1 / T - 1 / (resist.T_ref || 293.15)));
}
function ambientMoleFraction(p) {
  if (p.ambient === 'air') return 0;
  if (p.ambient === 'process gas') return moleFractionFromGNm3(p.supply.gas_g_per_Nm3);
  return parseFloat(p.ambient) * 1e-6;
}
function simulate(p, profileRadii) {
  const Q = p.flow_lpm / 60e3, omega = p.rpm * 2 * Math.PI / 60, R = p.diameter / 2;
  const sup = deliver(p.supply, Q, p.T, p.pH);
  if (p.nozzle_ppm !== null && p.nozzle_ppm !== undefined) {
    sup.c_nozzle = molm3(p.nozzle_ppm);
    sup.supersaturation = sup.c_nozzle / sup.c_sat_nozzle;
  }
  const cSurf = equilibriumOzone(p.T, ambientMoleFraction(p), P_ATM);
  const nu = kinematicViscosity(p.T), D = ozoneDiffusivity(p.T);
  const fr = solveFilm({ Q, omega, R, c_in: sup.c_nozzle, nu, D: D * p.enhancement, k1: k1(p.T), k2: k2(p.pH, p.T),
    c_surface: cSurf, k_wall: wallRate(p.resist, p.T), n_layers: p.n_layers, n_steps: p.n_steps }, (profileRadii || []).filter((x) => x < R));
  const rate = fr.wall_flux.map((f) => p.resist.yield_m3_per_mol * f);
  const mean = areaAverage(fr.r, rate, R_MIN);
  let mx = -Infinity, mn = Infinity;
  for (let i = 0; i < fr.r.length; i++) if (fr.r[i] >= R_MIN) { mx = Math.max(mx, rate[i]); mn = Math.min(mn, rate[i]); }
  const tClear = mn > 0 ? p.resist_thickness / mn : Infinity;
  const emitted = Math.max(-fr.budget.gas_exchange, 0);
  return {
    supply: sup, film: fr, c_surface: cSurf, nu, D,
    half_life_nozzle: sup.c_nozzle > 0 ? halfLife(sup.c_nozzle, p.pH, p.T) : Infinity,
    strip_rate: rate, strip_mean: mean, strip_max: mx, strip_min: mn,
    nonuniformity: mean > 0 ? (mx - mn) / (2 * mean) : NaN,
    time_to_clear: tClear, budget: fr.budget,
    ozone_per_wafer_g: isFinite(tClear) ? Q * sup.c_nozzle * M_O3 * 1e3 * tClear : Infinity,
    exhaust_ppm: p.exhaust_m3h > 0 ? emitted / (p.exhaust_m3h / 3600 / V_NORMAL) * 1e6 : Infinity,
    h_mid: filmThickness(R / 2, Q, omega, nu), inertia_mid: inertiaRatio(R / 2, Q, omega, nu),
  };
}
function withChanges(p, changes) {
  const q = JSON.parse(JSON.stringify(p));
  for (const k in changes) q[k] = changes[k];
  return q;
}
function sweep(p, temps, rpms) {
  const mean = [], nonu = [], sat = [];
  for (const rpm of rpms) {
    const a = [], b = [], c = [];
    for (const T of temps) {
      const r = simulate(withChanges(p, { T, rpm, n_layers: 32, n_steps: 200 }));
      a.push(r.strip_mean); b.push(r.nonuniformity); c.push(r.supply.supersaturation);
    }
    mean.push(a); nonu.push(b); sat.push(c);
  }
  return { mean, nonu, sat };
}
// resist yield from one measured mean strip rate at the given settings
function impliedYield(rateNmMin, p) {
  const r = simulate(withChanges(p, { resist: { yield_m3_per_mol: 1.0, density: p.resist.density } }));
  return rateNmMin * 1e-9 / 60 / r.strip_mean;
}

if (typeof module !== 'undefined') {
  module.exports = {
    RGAS, P_ATM, T_ZERO, M_O3, V_NORMAL, waterDensity, waterViscosity, kinematicViscosity, ozoneDiffusivity,
    henryO3, henryCO2, moleFractionFromGNm3, moleFractionFromWt, wtFromMoleFraction, gNm3FromMoleFraction,
    mgL, molm3, equilibriumOzone, k1, k2, concentrationAfter, halfLife, timeToFraction, phFromCO2, co2PressureForPH,
    resistivityCO2, deliver, filmThickness, inertiaRatio, solveFilm, areaAverage, wallRate, R_MIN, DEFAULT_YIELD,
    defaultProcess, simulate, sweep, withChanges, impliedYield,
  };
}
