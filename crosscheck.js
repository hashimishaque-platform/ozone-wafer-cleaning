// Compares the browser model (model.js) with the Python package on the cases in tests/golden.json.
// Usage: python3 -m tests.golden && node crosscheck.js
'use strict';
const M = require('./model.js');
const golden = require('./tests/golden.json');
const fn = require('./tests/golden_functions.json');
let worst = 0, failed = 0;
const same = (label, js, py) => {
  const d = Math.abs(js - py) / Math.max(Math.abs(py), 1e-30);
  worst = Math.max(worst, d);
  if (!(d < 1e-9)) { failed++; console.log(`${label}: python ${py} js ${js} (rel diff ${d.toExponential(2)})`); }
};
for (const [name, g] of Object.entries(golden)) {
  const p = M.defaultProcess();
  for (const [k, v] of Object.entries(g.changes)) {
    if (k === 'supply') Object.assign(p.supply, v); else if (k === 'resist') Object.assign(p.resist, v); else p[k] = v;
  }
  const r = M.simulate(p);
  const js = {
    c_nozzle: r.supply.c_nozzle, supersaturation: r.supply.supersaturation, half_life_nozzle: r.half_life_nozzle,
    strip_mean: r.strip_mean, strip_min: r.strip_min, strip_max: r.strip_max, nonuniformity: r.nonuniformity,
    exhaust_ppm: r.exhaust_ppm, resist: r.budget.resist, gas_exchange: r.budget.gas_exchange, edge: r.budget.edge,
    decomposed: r.budget.decomposed, h_mid: r.h_mid,
  };
  for (const [k, v] of Object.entries(g.result)) same(`${name}.${k}`, js[k], v);
}
fn.pH.filter((x) => x <= 7).forEach((x, i) => same(`resistivity(${x})`, M.resistivityCO2(x), fn.resistivity[i]));
fn.pH.forEach((x, i) => same(`co2 pressure(${x})`, M.co2PressureForPH(x), fn.co2_pressure[i]));
for (const [f, pH, T, t] of fn.time_to_fraction) same(`time to ${f} at pH ${pH}, ${T} K`, M.timeToFraction(fn.c0, f, pH, T), t);
console.log(`cases: ${Object.keys(golden).length}, largest relative difference ${worst.toExponential(2)}, ${failed ? failed + ' mismatches' : 'all agree'}`);
process.exit(failed ? 1 : 0);
