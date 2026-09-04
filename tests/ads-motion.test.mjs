import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const vendor = await readFile(new URL('../public/vendor/countUp.umd.js', import.meta.url), 'utf8');
const motion = await readFile(new URL('../public/ads-motion.js', import.meta.url), 'utf8');
function setup(reduced = false) {
  let id = 0;
  const frames = new Map();
  const context = vm.createContext({
    matchMedia: () => ({ matches: reduced }),
    requestAnimationFrame: callback => { frames.set(++id, callback); return id; },
    cancelAnimationFrame: key => frames.delete(key),
  });
  vm.runInContext('window = globalThis;', context);
  vm.runInContext(vendor, context);
  vm.runInContext(motion, context);
  return {
    mount: context.TrovAdsMotion.mount,
    frame(time) { const callbacks = [...frames.values()]; frames.clear(); callbacks.forEach(fn => fn(time)); },
    pending: () => frames.size,
  };
}
function value(target, decimals, formatted) {
  let text = formatted;
  return { tagName: 'SPAN', dataset: { countTarget: String(target), countDecimals: String(decimals) },
    get textContent() { return text; }, set textContent(v) { text = v; },
    get innerHTML() { return text; }, set innerHTML(v) { text = v; },
  };
}
const root = values => ({ querySelectorAll: () => values });

test('all three KPIs count from zero and finish at the exact displayed precision in 800ms', () => {
  const app = setup();
  const values = [value(1250.12,2,'1,250.12'), value(13,0,'13'), value(2.348,2,'2.35')];
  app.mount(root(values), '30:today');
  assert.deepEqual(values.map(v => v.textContent), ['0.00','0','0.00']);
  app.frame(100);
  app.frame(400);
  assert.ok(Number(values[0].textContent.replaceAll(',', '')) > 0);
  assert.ok(Number(values[0].textContent.replaceAll(',', '')) < 1250.12);
  app.frame(900);
  assert.deepEqual(values.map(v => v.textContent), ['1,250.12','13','2.35']);
  assert.equal(app.pending(), 0);
});

test('navigation cancels old counters, reentry replays, and reduced motion keeps final values', () => {
  const app = setup();
  const first = value(20,0,'20');
  app.mount(root([first]), '30:today');
  app.mount(root([]), null);
  assert.equal(app.pending(), 0);
  const next = value(20,0,'20');
  app.mount(root([next]), '30:today');
  assert.equal(next.textContent, '0');
  const accessible = setup(true);
  const still = value(20,0,'20');
  accessible.mount(root([still]), '30:today', { replay: true });
  assert.equal(still.textContent, '20');
  assert.equal(accessible.pending(), 0);
});
