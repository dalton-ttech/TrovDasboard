import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const context = vm.createContext({ window: {} });
vm.runInContext(readFileSync(new URL('../public/logistics-model.js', import.meta.url), 'utf8'), context);
const M = context.window.TrovLogistics;
const at = '2026-09-04T12:00:00Z';
const snapshot = shipments => ({ status: 'ready', shipments });

test('Shopify fulfillment confirmation cannot silently reuse an OMS delivered status', () => {
  const [s] = M.merge([{id:'001',status:'派送成功',cost:20,zip:'06111'}], snapshot([{id:'001',displayStatus:'FULFILLED',fulfillmentCreatedAt:'2026-07-21T00:00:00Z',estimatedDeliveryAt:'2026-07-27T00:00:00Z'}]));
  assert.equal(s.dataConflict,true);
  assert.equal(M.delivered(s),false);
  assert.equal(M.age(s,at),null);
  assert.equal(M.classify(s,at).level,'REVIEW');
  assert.equal(s.cost,20);
  assert.equal(s.zip,'06111');
  assert.equal(M.samples([s],'fulfillmentCreatedAt','deliveredAt').length,0);
});

test('real delivered timestamp supersedes an old transit status', () => {
  const [s] = M.merge([{id:'002',status:'运输中'}], snapshot([{id:'002',displayStatus:'IN_TRANSIT',deliveredAt:'2026-09-03T10:00:00Z',fulfillmentCreatedAt:'2026-09-01T10:00:00Z'}]));
  assert.equal(M.delivered(s),true);
  assert.equal(M.age(s,at),null);
  assert.equal(M.classify(s,at).level,'DELIVERED');
  assert.equal(M.samples([s],'fulfillmentCreatedAt','deliveredAt')[0],2);
});

test('duration uses absolute timestamps and excludes missing, negative and historical-only samples', () => {
  assert.equal(M.duration({a:'2026-09-01T09:00:00-07:00',b:'2026-09-02T16:00:00Z'},'a','b'),1);
  for (const s of [{a:null,b:at},{a:at,b:'invalid'},{a:at,b:'2026-09-03T00:00:00Z'}]) assert.equal(M.duration(s,'a','b'),null);
  assert.equal(M.samples([{isLive:false,status:'派送成功',a:at,b:at}],'a','b').length,0);
});

test('multi-tracking fulfillments do not allocate a whole fulfillment quantity to every package', () => {
  const rows = M.merge([],snapshot([{id:'a',trackingCount:2,fulfillmentQuantity:4},{id:'b',trackingCount:2,fulfillmentQuantity:4},{id:'c',trackingCount:1,fulfillmentQuantity:2}]));
  assert.equal(rows[0].quantity,null);
  assert.equal(rows[1].quantity,null);
  assert.equal(rows[2].quantity,2);
});

test('delay thresholds use Shopify estimated delivery and distinguish missing status from a confirmed delay', () => {
  const [s] = M.merge([],snapshot([{id:'1',displayStatus:'IN_TRANSIT',estimatedDeliveryAt:'2026-09-03T10:00:00Z'}]));
  assert.equal(M.classify(s,at).level,'CRITICAL');
  assert.equal(M.classify({...s,estimatedDeliveryAt:'2026-09-04T11:00:00Z'},at).level,'WARNING');
  assert.equal(M.classify({...s,estimatedDeliveryAt:'2026-09-05T10:00:00Z'},at).level,'WATCH');
  const [unknown] = M.merge([],snapshot([{id:'2',displayStatus:'UNKNOWN'}]));
  assert.equal(M.classify(unknown,at).level,'REVIEW');
});
