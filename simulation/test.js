// Checks of the simulation core: node simulation/test.js
const fs = require('fs'), path = require('path'), assert = require('assert');
const model = fs.readFileSync(path.join(__dirname, '..', 'model.js'), 'utf8');
const props = model.slice(0, model.indexOf('// ---------------------------------------------------------------- pH of water'));
const core = fs.readFileSync(path.join(__dirname, 'core.js'), 'utf8');
const { setup, steady, march, compute, mgL } = new Function(props + '\n' + core + '\nreturn { setup, steady, march, compute, mgL };')();

const DESIGN = { rpm: 1600, flow_lpm: 2.0, T_C: 30, Tc_C: 10, pH: 4.5, gas_gNm3: 300, gas_Nlpm: 1.0, cover: 'offgas', resist_um: 1.0, line_m: 1.0, line_mm: 4 };
const OPEN = { rpm: 500, flow_lpm: 1.5, T_C: 25, Tc_C: 25, pH: 5.6, gas_gNm3: 200, gas_Nlpm: 2.0, cover: 'air', resist_um: 1.0, line_m: 5.0, line_mm: 6 };
const near = (a, b, tol, what) => { assert(Math.abs(a - b) <= tol, what + ': ' + a + ' is not within ' + tol + ' of ' + b); console.log('ok  ', what, a.toFixed(3)); };

for (const [name, set, tSteady, tStepped] of [['design point', DESIGN, 2.284, 1.902], ['open process', OPEN, 8.09, 7.35]]) {
  const m = setup(set), st = steady(m, 48, 400), mr = march(m, 32, 200, st.tClear);
  near(st.tClear / 60, tSteady, 0.02, name + ', steady time to clear (min)');
  near(mr.tClear / 60, tStepped, 0.03, name + ', stepped time to clear (min)');
  assert(m.ct.nDis <= m.ct.nGen, 'the dissolver takes no more ozone than the generator makes');
  // every mole of ozone made is accounted for: not dissolved, lost in the line, to the gas, the drain or the resist
  const made = m.ct.nGen * mr.tClear, fed = m.inp.c_in * m.inp.Q * mr.tClear;
  near((mr.toResist + mr.toGas + mr.toDrain) / fed, 1, 0.03, name + ', ozone fed to the wafer that is accounted for');
  near(mr.removedVol / (Math.PI * (0.15 * 0.15 - 0.01 * 0.01) * set.resist_um * 1e-6), 1, 0.01, name + ', resist removed over resist present');
  assert(fed <= made, 'no more ozone reaches the wafer than was made');
}
const r = compute(DESIGN), s = r.shares;
near(s.notDissolved + s.resist + s.gas + s.drain, 1, 0.03, 'design point, shares of the ozone made add up');
near(r.summary.approach, 0.897, 0.005, 'design point, dissolver approach to equilibrium');
console.log('all checks passed');
