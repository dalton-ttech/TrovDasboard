import http from 'node:http';
import { readFile, realpath } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import os from 'node:os';
import path from 'node:path';

const run = promisify(execFile);
const project = fileURLToPath(new URL('./', import.meta.url));
const root = path.join(project, 'public');
const ads = path.resolve(process.env.TROV_ADS_ROOT || path.join(project, '..', 'Trov_ADS'));
const bundledPython = path.join(os.homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'python', 'python.exe');
const python = process.env.TROV_PYTHON || (existsSync(bundledPython) ? bundledPython : 'python');
const port = Number(process.env.PORT || 4173);
const host = '127.0.0.1';
const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.png': 'image/png', '.pdf': 'application/pdf' };
let syncState = { status: 'idle', message: null }, reportIndexAt = 0, reportJob = null;
let adsSyncState = { status: 'idle', message: null };
async function jsonFile(name, fallback) { try { return JSON.parse(await readFile(path.join(project, 'data', name), 'utf8')); } catch { return fallback; } }
function reply(res, status, data, headers = {}) { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...headers }); res.end(typeof data === 'string' ? data : JSON.stringify(data)); }
async function refreshReports() {
  if (!reportJob && Date.now() - reportIndexAt > 30_000) {
    reportJob = run(python, [path.join(project, 'scripts', 'report_catalog.py')], { cwd: project, windowsHide: true, timeout: 30_000, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONIOENCODING: 'utf-8' } })
      .then(() => { reportIndexAt = Date.now(); }).catch(() => {}).finally(() => { reportJob = null; });
  }
  if (reportJob) await reportJob;
  return jsonFile('reports.json', { reports: [], source: 'Trov_ADS' });
}
function startSync() {
  syncState = { status: 'running', startedAt: new Date().toISOString(), message: null };
  run(python, [path.join(project, 'scripts', 'shopify_logistics.py')], { cwd: project, windowsHide: true, timeout: 240_000, maxBuffer: 256 * 1024, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONIOENCODING: 'utf-8' } })
    .then(({ stdout }) => { const result = JSON.parse(stdout.trim().split(/\r?\n/).at(-1)); syncState = { status: result.status === 'ready' ? 'ready' : 'error', finishedAt: new Date().toISOString(), message: result.status === 'ready' ? null : result.message }; })
    .catch(() => { syncState = { status: 'error', finishedAt: new Date().toISOString(), message: 'Shopify 同步未完成，保留上次成功数据。请检查网络与现有只读访问权限。' }; });
}
function startAdsSync() {
  adsSyncState = { status: 'running', startedAt: new Date().toISOString(), message: null };
  run(python, [path.join(project, 'scripts', 'ads_overview.py')], { cwd: project, windowsHide: true, timeout: 240_000, maxBuffer: 256 * 1024, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONIOENCODING: 'utf-8' } })
    .then(({ stdout }) => { const result = JSON.parse(stdout.trim().split(/\r?\n/).at(-1)); adsSyncState = { status: result.status === 'ready' ? 'ready' : 'error', finishedAt: new Date().toISOString() }; })
    .catch(() => { adsSyncState = { status: 'error', message: '投流数据暂未更新，保留上次成功快照。' }; });
}
http.createServer(async (req, res) => {
  try {
    if (![`127.0.0.1:${port}`, `localhost:${port}`].includes(req.headers.host)) return reply(res, 403, { error: 'Local host required' });
    const pathname = decodeURIComponent(new URL(req.url, `http://${host}:${port}`).pathname);
    if (pathname === '/api/ads-overview/sync' && req.method === 'POST') {
      if (req.headers['x-trov-request'] !== 'local' || (req.headers.origin && req.headers.origin !== `http://${req.headers.host}`)) return reply(res, 403, { error: 'Local same-origin request required' });
      if (adsSyncState.status !== 'running') startAdsSync();
      return reply(res, 202, adsSyncState);
    }
    if (pathname === '/api/logistics/sync' && req.method === 'POST') {
      if (req.headers['x-trov-request'] !== 'local' || (req.headers.origin && req.headers.origin !== `http://${req.headers.host}`)) return reply(res, 403, { error: 'Local same-origin request required' });
      if (syncState.status === 'running') return reply(res, 202, syncState);
      startSync(); return reply(res, 202, syncState);
    }
    if (!['GET', 'HEAD'].includes(req.method)) return reply(res, 405, { error: 'Method not allowed' });
    if (pathname === '/api/logistics') return reply(res, 200, await jsonFile('shopify-logistics.json', { status: 'not_connected' }));
    if (pathname === '/api/logistics/sync-status') return reply(res, 200, syncState);
    if (pathname === '/api/ads-overview') return reply(res, 200, await jsonFile('ads-overview.json', { status: 'not_connected' }));
    if (pathname === '/api/ads-overview/sync-status') return reply(res, 200, adsSyncState);
    if (pathname === '/api/reports') return reply(res, 200, await refreshReports());
    if (pathname === '/api/health') return reply(res, 200, { status: 'ready', app: 'trov-dashboard', readOnly: true });
    if (pathname === '/data.js') {
      const history = await jsonFile('history.json', null);
      if (history) return reply(res, 200, 'window.TROV_DATA = ' + JSON.stringify(history).replaceAll('<', '\\u003c') + ';', { 'Content-Type': 'text/javascript; charset=utf-8' });
    }
    if (pathname === '/runtime.js') {
      const runtime = { logistics: await jsonFile('shopify-logistics.json', null), adsOverview: await jsonFile('ads-overview.json', null), reports: await refreshReports(), serverAvailable: true };
      return reply(res, 200, 'window.TROV_RUNTIME = ' + JSON.stringify(runtime).replaceAll('<', '\\u003c') + ';', { 'Content-Type': 'text/javascript; charset=utf-8' });
    }
    const report = pathname.match(/^\/reports\/(daily|weekly)\/(\d{4}-\d{2}-\d{2})\/(report\.html|report-preview\.png)$/);
    if (report) {
      const [, kind, date, file] = report;
      const folder = path.join(ads, 'audits', 'automation', `meta-shopify-${kind}`, date);
      const manifest = JSON.parse(await readFile(path.join(folder, 'run-manifest.json'), 'utf8'));
      if (manifest.status !== 'ready' || manifest.writes_performed !== false) return reply(res, 404, { error: 'Report unavailable' });
      const actual = await realpath(path.join(folder, file));
      const allowed = await realpath(path.join(ads, 'audits', 'automation', `meta-shopify-${kind}`));
      if (!actual.startsWith(allowed + path.sep)) return reply(res, 403, { error: 'Forbidden' });
      const bytes = await readFile(actual);
      res.writeHead(200, { 'Content-Type': mime[path.extname(file)], 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, max-age=60', ...(file.endsWith('.html') ? { 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; script-src 'none'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'" } : {}) });
      res.end(bytes); return;
    }
    const filename = path.resolve(root, pathname === '/' ? 'index.html' : pathname.slice(1));
    if (!filename.startsWith(root + path.sep)) return reply(res, 403, { error: 'Forbidden' });
    const actual = await realpath(filename);
    if (!actual.startsWith(root + path.sep)) return reply(res, 403, { error: 'Forbidden' });
    const bytes = await readFile(actual);
    res.writeHead(200, { 'Content-Type': mime[path.extname(actual)] || 'application/octet-stream', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
    res.end(bytes);
  } catch { reply(res, 404, { error: 'Not found' }); }
}).listen(port, host, () => console.log(`Trov workspace: http://${host}:${port}`));
