// Read-only smoke checks against the running local service.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import vm from 'node:vm';

const base = `http://127.0.0.1:${process.env.PORT || 4173}`;
const get = async route => { const r = await fetch(base + route); assert.equal(r.status,200,route); return r; };
const live = await (await get('/api/logistics')).json();
const catalog = await (await get('/api/reports')).json();
const ads = await (await get('/api/ads-overview')).json();
assert.equal(ads.status,'ready');
assert.equal(ads.writesPerformed,false);
assert.equal(ads.periods['30'].until,ads.periods['7'].until);
for (const [key,p] of Object.entries(ads.periods)) {
  assert.equal((Date.parse(p.until)-Date.parse(p.since))/86400000+1,Number(key));
  assert.equal(p.metaRoas,p.metaSpend>0?p.metaPurchaseValue/p.metaSpend:null);
  assert.equal(Date.parse(p.since)-Date.parse(p.comparison.since),86400000);
  assert.equal(Date.parse(p.until)-Date.parse(p.comparison.until),86400000);
  for (const key of ['shopifyNetSales','shopifyOrders','metaRoas']) {
    const previous=p.comparison.values[key], current=p[key];
    const expected=!Number.isFinite(previous)||!Number.isFinite(current)?null:Math.abs(current-previous)<=1e-9?'flat':current>previous?'up':'down';
    assert.equal(p.comparison.directions[key],expected);
  }
}
assert.equal(live.status,'ready');
assert.equal(live.writesPerformed,false);
assert.equal(new Set(live.shipments.map(s=>s.id)).size,live.shipments.length);
const firstSeenPreserved = live.shipments.filter(s=>Date.parse(s.trackingFirstSeenAt)<Date.parse(s.observedAt)).length;
for (const [field,count] of Object.entries(live.coverage)) assert.equal(count,live.shipments.filter(s=>Boolean(s[field]) && (!Array.isArray(s[field]) || s[field].length)).length,field);
const forbidden = new Set(['access_token','token','client_secret','email','phone','address1','address2','firstName','lastName']);
const inspectKeys = value => { if (!value || typeof value !== 'object') return; for (const [key,child] of Object.entries(value)) { assert.equal(forbidden.has(key),false,`Disallowed field ${key}`); inspectKeys(child); } };
inspectKeys(live); inspectKeys(catalog); inspectKeys(ads);
const ctx=vm.createContext({window:{}});
for (const file of ['data.js','logistics-model.js']) vm.runInContext(await (await get('/'+file)).text(),ctx);
const localHistory = JSON.parse(await readFile(new URL('../data/history.json',import.meta.url),'utf8'));
assert.equal(JSON.stringify(ctx.window.TROV_DATA),JSON.stringify(localHistory));
const rows=ctx.window.TrovLogistics.merge(ctx.window.TROV_DATA.shipments,live);
const states=Object.fromEntries(['DELIVERED','CRITICAL','WARNING','REVIEW','WATCH','NORMAL'].map(level=>[level,rows.filter(s=>ctx.window.TrovLogistics.classify(s,live.syncedAt).level===level).length]));
assert.equal(new Set(catalog.reports.map(r=>r.id)).size,catalog.reports.length);
for (const r of catalog.reports) { assert.equal(r.status,'ready'); assert.equal(r.writesPerformed,false); assert.ok(r.files.html && r.since && r.until); assert.ok(r.adScope.every(a=>['A02','A03'].includes(a))); }
const latest=catalog.reports[0];
const html=await get(latest.files.html);
assert.ok(html.headers.get('content-security-policy').includes("script-src 'none'"));
const original=await readFile(new URL(`../../Trov_ADS/audits/automation/meta-shopify-${latest.kind}/${latest.id.slice(latest.kind.length+1)}/report.html`,import.meta.url));
const returned=Buffer.from(await html.arrayBuffer());
assert.equal(createHash('sha256').update(original).digest('hex'),createHash('sha256').update(returned).digest('hex'));
assert.ok(catalog.reports.every(r => !r.files.pdf), 'PDF downloads are not offered');
assert.equal((await fetch(base+latest.files.html.replace('report.html','report.pdf'))).status,404);
for (const route of ['/server.mjs','/data/shopify-logistics.json','/data/history.json',latest.files.html.replace('report.html','data.json')]) assert.equal((await fetch(base+route)).status,404,route);
assert.equal((await fetch(base+'/api/logistics/sync',{method:'POST'})).status,403);
assert.equal((await fetch(base+'/api/logistics/sync',{method:'POST',headers:{'X-Trov-Request':'local','Origin':'https://example.invalid'}})).status,403);
console.log(JSON.stringify({status:'passed',shipments:live.shipments.length,historicalMatches:live.historicalMatches,states,firstSeenPreserved,reports:catalog.reports.length,reportHtmlUnchanged:true,pdfAvailable:Boolean(latest.files.pdf),privateRoutesProtected:true,syncedAt:live.syncedAt},null,2));
