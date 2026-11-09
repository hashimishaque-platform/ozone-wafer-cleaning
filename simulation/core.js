// ---------------------------------------------------------------- strip simulation core for the 3D page
// Same equations as the project's model (dio3 / model.js). Two additions:
//  1. the contactor is N theoretical counterflow stages (Kremser), so it never dissolves more than the generator makes;
//  2. the resist is stripped radius by radius in time: where it is gone, the wafer stops taking up ozone.
const N_STAGES = 4, R_WAFER = 0.15, R_MIN = 0.01, CARBON_FRACTION = 0.7;
function filmThickness(r, Q, w, nu) { return Math.pow(3 * nu * Q / (2 * Math.PI * w * w * r * r), 1 / 3); }
function layersOf(n) {
  const faces = new Float64Array(n + 1), centres = new Float64Array(n);
  for (let i = 0; i <= n; i++) faces[i] = 0.5 * (1 - Math.cos(Math.PI * i / n));
  for (let i = 0; i < n; i++) centres[i] = 0.5 * (faces[i] + faces[i + 1]);
  return { faces, centres };
}
function stationsOf(r0, R, n) {
  const out = new Float64Array(n + 1);
  for (let i = 0; i <= n; i++) { const s = i / n; out[i] = r0 + (R - r0) * s * s; }
  return out;
}
function thomas(a, b, c, d) {
  const n = b.length, cp = new Float64Array(n), dp = new Float64Array(n), x = new Float64Array(n);
  cp[0] = c[0] / b[0]; dp[0] = d[0] / b[0];
  for (let i = 1; i < n; i++) { const m = b[i] - a[i] * cp[i - 1]; cp[i] = i < n - 1 ? c[i] / m : 0; dp[i] = (d[i] - a[i] * dp[i - 1]) / m; }
  x[n - 1] = dp[n - 1];
  for (let i = n - 2; i >= 0; i--) x[i] = dp[i] - cp[i] * x[i + 1];
  return x;
}
// Film solver of model.js; `active[n]` = 0 switches off the uptake by the wafer at station n (resist gone there).
function solveFilm(inp, active) {
  const N = inp.n_layers, NS = inp.n_steps, r0 = 5e-3;
  const { faces, centres: zc } = layersOf(N);
  const dz = new Float64Array(N), q = new Float64Array(N), dzc = new Float64Array(N - 1);
  const Fz = (z) => z * z / 2 - z * z * z / 6;
  for (let i = 0; i < N; i++) { dz[i] = faces[i + 1] - faces[i]; q[i] = 3 * inp.Q / (2 * Math.PI) * (Fz(faces[i + 1]) - Fz(faces[i])); }
  for (let i = 0; i < N - 1; i++) dzc[i] = zc[i + 1] - zc[i];
  const rs = stationsOf(r0, inp.R, NS);
  let c = new Float64Array(N).fill(inp.c_in);
  const cs = inp.c_surface;
  const wall = new Float64Array(NS + 1), surf = new Float64Array(NS + 1), cm = new Float64Array(NS + 1), hh = new Float64Array(NS + 1);
  cm[0] = inp.c_in; hh[0] = filmThickness(rs[0], inp.Q, inp.omega, inp.nu);
  let totWall = 0, totSurf = 0, totDec = 0;
  const lower = new Float64Array(N), diag = new Float64Array(N), upper = new Float64Array(N), res = new Float64Array(N);
  const g = new Float64Array(N - 1), V = new Float64Array(N);
  for (let n = 1; n <= NS; n++) {
    const r = rs[n], dr = rs[n] - rs[n - 1];
    const h = filmThickness(r, inp.Q, inp.omega, inp.nu);
    for (let i = 0; i < N - 1; i++) g[i] = r * inp.D / (h * dzc[i]);
    const gw = (active && !active[n]) ? 0 : r * inp.D / (h * zc[0]);
    const gs = r * inp.D / (h * (1 - zc[N - 1]));
    for (let i = 0; i < N; i++) V[i] = r * h * dz[i];
    const old = c, x = Float64Array.from(c);
    for (let it = 0; it < 8; it++) {
      for (let i = 0; i < N; i++) {
        lower[i] = 0; upper[i] = 0;
        diag[i] = q[i] / dr + V[i] * (inp.k1 + 2 * inp.k2 * x[i]);
        res[i] = q[i] / dr * (x[i] - old[i]) + V[i] * (inp.k1 * x[i] + inp.k2 * x[i] * x[i]);
      }
      for (let i = 0; i < N - 1; i++) {
        diag[i] += g[i]; diag[i + 1] += g[i]; upper[i] = -g[i]; lower[i + 1] = -g[i];
        res[i] -= g[i] * (x[i + 1] - x[i]); res[i + 1] -= g[i] * (x[i] - x[i + 1]);
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
    const w = gw * c[0], s = gs * (cs - c[N - 1]);
    let dec = 0, qc = 0, qs = 0;
    for (let i = 0; i < N; i++) { dec += V[i] * (inp.k1 * c[i] + inp.k2 * c[i] * c[i]); qc += q[i] * c[i]; qs += q[i]; }
    totWall += 2 * Math.PI * w * dr; totSurf += 2 * Math.PI * s * dr; totDec += 2 * Math.PI * dec * dr;
    wall[n] = w / r; surf[n] = s / r; cm[n] = qc / qs; hh[n] = h;
  }
  wall[0] = wall[1]; surf[0] = surf[1];
  let edge = 0;
  for (let i = 0; i < N; i++) edge += q[i] * c[i];
  edge *= 2 * Math.PI;
  return { r: rs, h: hh, wall, surf, c_mean: cm, budget: { in: inp.Q * inp.c_in, resist: totWall, gas: totSurf, decay: totDec, edge } };
}
// Contactor: N ideal counterflow stages fed with fresh water (Kremser equation).
function contactor(set, Q) {
  const y = moleFractionFromGNm3(set.gas_gNm3);
  const nGas = set.gas_Nlpm / 60e3 / V_NORMAL, nGen = y * nGas;
  const Tc = set.Tc_C + T_ZERO, p = P_ATM;
  const A = Q * henryO3(Tc) * p / nGas;
  const N = N_STAGES;
  const phi = Math.abs(A - 1) < 1e-9 ? N / (N + 1) : (Math.pow(A, N + 1) - A) / (Math.pow(A, N + 1) - 1);
  const nDis = phi * nGen, cOut = nDis / Q, cEq = henryO3(Tc) * y * p;
  return { y, nGas, nGen, A, phi, nDis, cOut, cEq, approach: cOut / cEq, yOff: Math.max(nGen - nDis, 0) / (nGas - nDis) };
}
function setup(set) {
  const Q = set.flow_lpm / 60e3, omega = set.rpm * 2 * Math.PI / 60, T = set.T_C + T_ZERO;
  const ct = contactor(set, Q);
  const tau = Math.PI * (set.line_mm * 1e-3) ** 2 / 4 * set.line_m / Q;
  const cNoz = concentrationAfter(ct.cOut, tau, set.pH, T);
  const cSat = equilibriumOzone(T, ct.y, P_ATM);
  const yCover = set.cover === 'offgas' ? ct.yOff : set.cover === 'fresh' ? ct.y : 0;
  const nu = kinematicViscosity(T), D = ozoneDiffusivity(T);
  const Y = M_O3 / 1200.0;    // 1 g of ozone per g of resist, resist 1200 kg/m3
  const inp = { Q, omega, R: R_WAFER, c_in: cNoz, nu, D, k1: k1(T), k2: k2(set.pH, T), c_surface: equilibriumOzone(T, yCover, P_ATM) };
  return { set, Q, omega, T, ct, tau, cNoz, cSat, S: cNoz / cSat, yCover, nu, D, Y, inp,
    hEdge: filmThickness(R_WAFER, Q, omega, nu), hMid: filmThickness(R_WAFER / 2, Q, omega, nu),
    inertiaMid: Q * filmThickness(R_WAFER / 2, Q, omega, nu) / (2 * Math.PI * nu * (R_WAFER / 2) ** 2) };
}
function interpAt(x, xs, ys) {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (x <= xs[i]) { const f = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] + f * (ys[i] - ys[i - 1]); }
  return ys[ys.length - 1];
}
// Area average over the wafer; inside rMin the value at rMin is used, as in the project model.
function areaMean(r, y, rMin) {
  const ym = interpAt(rMin, r, y);
  const rr = [rMin], yy = [ym];
  for (let i = 0; i < r.length; i++) if (r[i] > rMin) { rr.push(r[i]); yy.push(y[i]); }
  let outer = 0;
  for (let i = 1; i < rr.length; i++) outer += 0.5 * (2 * Math.PI * rr[i] * yy[i] + 2 * Math.PI * rr[i - 1] * yy[i - 1]) * (rr[i] - rr[i - 1]);
  return (Math.PI * rMin * rMin * ym + outer) / (Math.PI * r[r.length - 1] ** 2);
}
// Steady film with the whole wafer covered, and with a bare wafer (end-point reference).
function steady(m, layers, steps) {
  const inp = Object.assign({}, m.inp, { n_layers: layers, n_steps: steps });
  const full = solveFilm(inp, null);
  const bare = solveFilm(inp, new Uint8Array(steps + 1));
  const rate = Array.from(full.wall, (w) => m.Y * w);
  let mx = -Infinity, mn = Infinity;
  for (let i = 0; i < full.r.length; i++) if (full.r[i] >= R_MIN) { mx = Math.max(mx, rate[i]); mn = Math.min(mn, rate[i]); }
  const mean = areaMean(full.r, rate, R_MIN);
  return { full, bare, rate, mean, min: mn, max: mx, nonu: (mx - mn) / (2 * mean), tClear: m.set.resist_um * 1e-6 / mn,
    drainFull: full.budget.edge / m.Q, drainBare: bare.budget.edge / m.Q };
}
// Time stepping: each step solves the steady film (it renews itself in about 0.1 s) for the resist still left.
function march(m, layers, steps, tStatic) {
  const inp = Object.assign({}, m.inp, { n_layers: layers, n_steps: steps });
  const rs = stationsOf(5e-3, R_WAFER, steps);
  const ring = new Float64Array(steps + 1);
  for (let i = 0; i <= steps; i++) {
    const a = i === 0 ? 0 : 0.5 * (rs[i - 1] + rs[i]), b = i === steps ? R_WAFER : 0.5 * (rs[i] + rs[i + 1]);
    ring[i] = Math.PI * (b * b - a * a);
  }
  const d0 = m.set.resist_um * 1e-6;
  const delta = new Float64Array(steps + 1).fill(d0);
  const snaps = [];
  let t = 0, toResist = 0, toGas = 0, toDrain = 0, removed = 0;
  const dtMin = tStatic / 150, dtMax = tStatic / 40;
  for (let k = 0; k < 600; k++) {
    const active = new Uint8Array(steps + 1);
    let any = false;
    for (let i = 0; i <= steps; i++) if (delta[i] > 0) { active[i] = 1; any = true; }
    const sol = solveFilm(inp, active);
    const rate = new Float64Array(steps + 1);
    let next = Infinity, volRate = 0, cleared = 0;
    for (let i = 0; i <= steps; i++) {
      rate[i] = active[i] ? m.Y * sol.wall[i] : 0;
      if (active[i] && rate[i] > 0) next = Math.min(next, delta[i] / rate[i]);
      volRate += rate[i] * ring[i];
      if (!active[i]) cleared += ring[i];
    }
    snaps.push({ t, delta: Float32Array.from(delta), rate: Float32Array.from(rate), cm: Float32Array.from(sol.c_mean),
      drain: sol.budget.edge / m.Q, uptake: sol.budget.resist, gasOut: -sol.budget.gas, edgeOut: sol.budget.edge,
      cleared: cleared / (Math.PI * R_WAFER * R_WAFER), carbon: volRate * 1200 * CARBON_FRACTION });
    if (!any) break;
    const dt = Math.min(Math.max(next, dtMin), dtMax);
    let dVol = 0;
    for (let i = 0; i <= steps; i++) if (active[i]) { const d = Math.min(delta[i], rate[i] * dt); delta[i] -= d; dVol += d * ring[i]; }
    toResist += dVol / m.Y; toGas += Math.max(-sol.budget.gas, 0) * dt; toDrain += sol.budget.edge * dt + (sol.budget.resist * dt - dVol / m.Y);
    removed += dVol;
    t += dt;
  }
  return { r: rs, snaps, tClear: t, toResist, toGas, toDrain, removedVol: removed };
}
function resample(xs, ys, xv) {
  const out = new Float32Array(xv.length);
  for (let k = 0; k < xv.length; k++) out[k] = interpAt(Math.max(xv[k], xs[0]), xs, ys);
  return out;
}
// Everything the page needs for one set of settings.
function compute(set) {
  const m = setup(set);
  const st = steady(m, 48, 400);
  const K = 90, rv = new Float64Array(K + 1);
  for (let k = 0; k <= K; k++) rv[k] = k * R_WAFER / K;
  let V = 0;
  for (let i = 0; i < 400; i++) {
    const a = 5e-3 + (R_WAFER - 5e-3) * i / 400, b = 5e-3 + (R_WAFER - 5e-3) * (i + 1) / 400, r = 0.5 * (a + b);
    V += 2 * Math.PI * r * filmThickness(r, m.Q, m.omega, m.nu) * (b - a);
  }
  const rF = Array.from(st.full.r);
  const out = {
    set,
    rv: Array.from(rv),
    hv: Array.from(rv, (r) => filmThickness(Math.max(r, 5e-3), m.Q, m.omega, m.nu)),
    rate0: Array.from(resample(rF, st.rate, rv)),
    cm0: Array.from(resample(rF, st.full.c_mean, rv)),
    summary: {
      y: m.ct.y, yOff: m.ct.yOff, yCover: m.yCover, A: m.ct.A, approach: m.ct.approach, dissolved: m.ct.phi,
      cNoz: mgL(m.cNoz), cOut: mgL(m.ct.cOut), S: m.S, tau: m.tau, hEdge: m.hEdge, hMid: m.hMid, inertiaMid: m.inertiaMid,
      residence: V / m.Q, gen_g_min: m.ct.nGen * M_O3 * 1e3 * 60, tStatic: st.tClear, mean: st.mean, min: st.min, max: st.max,
      nonu: st.nonu, drainFull: mgL(st.drainFull), drainBare: mgL(st.drainBare),
    },
    snaps: [], tClear: Infinity, shares: null,
  };
  if (!isFinite(st.tClear) || st.tClear > 3600) return out;
  const mr = march(m, 32, 200, st.tClear);
  const rS = Array.from(mr.r);
  out.snaps = mr.snaps.map((s) => ({ t: s.t, delta: Array.from(resample(rS, s.delta, rv)), rate: Array.from(resample(rS, s.rate, rv)),
    cm: Array.from(resample(rS, s.cm, rv)), drain: mgL(s.drain), carbon: s.carbon * 1e6 * 60, cleared: s.cleared }));
  out.tClear = mr.tClear;
  const made = m.ct.nGen * mr.tClear;
  out.shares = { notDissolved: 1 - m.ct.phi, resist: mr.toResist / made, gas: mr.toGas / made, drain: mr.toDrain / made };
  out.summary.ozonePerWafer = made * M_O3 * 1e3;
  return out;
}
