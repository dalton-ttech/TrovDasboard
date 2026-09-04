import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const context = vm.createContext({ window: {}, Intl, Date });
vm.runInContext(await readFile(new URL('../public/pacific-clock.js', import.meta.url), 'utf8'), context);
const format = iso => context.window.TrovClock.format(new Date(iso));

test('Pacific date stays on the previous day before PDT midnight', () => {
  const value = format('2026-09-04T06:59:59Z');
  assert.equal(value.date, '2026.09.03 周四');
  assert.equal(value.time, '23:59:59');
  assert.equal(value.zone, 'PDT');
  assert.equal(format('2026-09-04T07:00:00Z').time, '00:00:00');
});

test('Pacific clock follows both DST transitions without a fixed offset', () => {
  assert.equal(format('2026-03-08T09:59:59Z').time, '01:59:59');
  assert.equal(format('2026-03-08T10:00:00Z').time, '03:00:00');
  assert.equal(format('2026-11-01T08:59:59Z').zone, 'PDT');
  const value = format('2026-11-01T09:00:00Z');
  assert.equal(value.time, '01:00:00');
  assert.equal(value.zone, 'PST');
});
