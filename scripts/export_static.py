"""Build a complete static dashboard from local, read-only snapshots.

The output contains private business data. This command does not upload it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
ASSETS = (
    'index.html', 'preview.html', 'favicon.svg', 'styles.css', 'workspace.css',
    'app.js', 'workspace.js', 'logistics-model.js', 'pacific-clock.js', 'ads-motion.js',
    'vendor/countUp.umd.js', 'vendor/countUp-LICENSE.txt',
    'assets/trov-logo-transparent.png', 'assets/noto-sans-sc.woff2',
    'assets/notosanssc-OFL.txt', 'assets/manrope.woff2', 'assets/manrope-OFL.txt',
)
FORBIDDEN = {'accesstoken', 'token', 'clientsecret', 'apikey', 'authorization',
             'password', 'email', 'phone', 'address1', 'address2', 'firstname', 'lastname'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def inspect_fields(value):
    if isinstance(value, dict):
        for key, child in value.items():
            require(re.sub(r'[^a-z]', '', key.lower()) not in FORBIDDEN,
                    'Snapshot contains a prohibited private or credential field')
            inspect_fields(child)
    elif isinstance(value, list):
        for child in value:
            inspect_fields(child)
    elif isinstance(value, float):
        require(math.isfinite(value), 'Snapshot contains a non-finite number')


def day(value):
    return dt.date.fromisoformat(value)


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Snapshot timestamp has no timezone')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(history, logistics, ads, catalog):
    for item in (history, logistics, ads, catalog):
        inspect_fields(item)
    day(history['snapshotDate'])
    for item in (history, logistics):
        require(isinstance(item.get('shipments'), list), 'Missing shipment array')
        ids = [s['id'] for s in item['shipments']]
        require(all(ids) and len(set(ids)) == len(ids), 'Missing or duplicate shipment ID')
    for item in (logistics, ads):
        require(item.get('status') == 'ready' and item.get('writesPerformed') is False,
                'A read-only, successful source snapshot is required')
        timestamp(item['syncedAt'])
    for key, count in logistics['coverage'].items():
        require(count == sum(bool(s.get(key)) for s in logistics['shipments']),
                'Logistics coverage does not match its shipments')
    require(ads.get('timezone') == 'America/Los_Angeles', 'Unexpected advertising timezone')
    require(sorted(ads.get('adScope', [])) == ['A02', 'A03'], 'Unexpected advertising scope')
    require(set(ads['periods']) == {'7', '30'}, 'Both 7-day and 30-day periods are required')
    require(ads['periods']['7']['until'] == ads['periods']['30']['until'], 'Mismatched period end dates')
    for key, period in ads['periods'].items():
        require(period.get('status') == 'ready', 'Advertising period is not ready')
        require(period.get('currency') == 'USD' and period.get('days') == int(key), 'Unexpected period currency or days')
        require((day(period['until']) - day(period['since'])).days + 1 == int(key), 'Invalid period length')
        for field in ('shopifyNetSales', 'shopifyOrders', 'metaSpend', 'metaPurchaseValue'):
            require(finite(period[field]), 'Missing advertising metric')
        expected = period['metaPurchaseValue'] / period['metaSpend'] if period['metaSpend'] > 0 else None
        require(period['metaRoas'] == expected, 'ROAS is inconsistent with revenue and spend')
        comparison = period['comparison']
        for bound in ('since', 'until'):
            require((day(period[bound]) - day(comparison[bound])).days == 1, 'Invalid previous-day window')
        for field in ('shopifyNetSales', 'shopifyOrders', 'metaRoas'):
            previous, current = comparison['values'][field], period[field]
            direction = None if not finite(previous) or not finite(current) else (
                'flat' if abs(current - previous) <= 1e-9 else 'up' if current > previous else 'down')
            require(comparison['directions'][field] == direction, 'Incorrect metric direction')
    require(isinstance(catalog.get('reports'), list), 'Missing report index')
    ids = [r['id'] for r in catalog['reports']]
    require(len(set(ids)) == len(ids), 'Duplicate report ID')


class ReportCheck(HTMLParser):
    def handle_starttag(self, tag, attrs):
        require(tag not in {'script', 'form', 'iframe', 'object', 'embed', 'base'}, 'Report contains active content')
        for key, value in attrs:
            require(not key.lower().startswith('on'), 'Report contains an event handler')
            if key in {'src', 'href', 'srcset', 'action', 'poster', 'data'}:
                require(not value or value.startswith('#') or (tag == 'img' and value.startswith('data:image/')),
                        'Report requires an external or relative resource')
            require(key != 'http-equiv', 'Report contains an HTTP directive')


def report_files(catalog, ads_root):
    files = {}
    for report in catalog['reports']:
        require(report.get('status') == 'ready' and report.get('writesPerformed') is False, 'Report is not ready')
        match = re.fullmatch(r'(daily|weekly)-(\d{4}-\d{2}-\d{2})', report['id'])
        require(match is not None, 'Invalid report ID')
        kind, date = match.groups()
        day(date)
        require(kind == report['kind'], 'Mismatched report kind')
        require(set(report['adScope']) <= {'A02', 'A03'}, 'Unexpected report ad scope')
        relative = f'reports/{kind}/{date}/report.html'
        require(report['files']['html'] == '/' + relative, 'Unexpected report URL')
        base = (ads_root / 'audits' / 'automation' / f'meta-shopify-{kind}').resolve()
        folder = (base / date).resolve()
        require(folder.is_relative_to(base), 'Report source escapes its allowed directory')
        source = (folder / 'report.html').resolve()
        require(source.is_relative_to(folder), 'Report file escapes its directory')
        manifest = read_json(folder / 'run-manifest.json')
        require(manifest.get('status') == 'ready' and manifest.get('writes_performed') is False, 'Report manifest is not ready')
        content = source.read_bytes()
        html = content.decode('utf-8-sig')
        ReportCheck().feed(html)
        require(not re.search(r'url\s*\(|@import', html, re.I), 'Report requires CSS resources')
        require(not re.search(r'(?:shpat_|shpca_|ghp_)[a-zA-Z0-9]{15,}', html), 'Report contains a credential')
        files[relative] = content
        report['files'] = {'html': '/' + relative}
    return files


def js_assignment(name, value):
    data = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return f'window.{name} = ' + data.replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029') + ';\n'


def export_static(data_dir, ads_root, output):
    output = Path(output).resolve()
    require(output.is_relative_to(ROOT) and output != ROOT, 'Output must be inside this project')
    require(output == ROOT / 'dist' or output.is_relative_to(ROOT / '.tmp'), 'Use dist/ or a directory under .tmp/')
    if output.exists():
        require((output / '.trov-static-export.json').is_file(), 'Refusing to replace a directory not created by this exporter')
    history, logistics, ads, catalog = [read_json(Path(data_dir) / name) for name in (
        'history.json', 'shopify-logistics.json', 'ads-overview.json', 'reports.json')]
    validate(history, logistics, ads, catalog)
    reports = report_files(catalog, Path(ads_root))
    runtime = {'logistics': logistics, 'adsOverview': ads, 'reports': catalog,
               'serverAvailable': False, 'deliveryMode': 'static-snapshot'}
    manifest = {'format': 1, 'builtAt': dt.datetime.now(dt.timezone.utc).isoformat(),
                'logisticsSyncedAt': logistics['syncedAt'], 'adsSyncedAt': ads['syncedAt'],
                'historyCount': len(history['shipments']), 'shipmentCount': len(logistics['shipments']),
                'reportCount': len(reports), 'containsBusinessData': True}
    temp_root = ROOT / '.tmp'
    temp_root.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='static-build-', dir=temp_root)).resolve()
    backup = None
    try:
        for relative in ASSETS:
            source = (ROOT / 'public' / relative).resolve()
            require(source.is_relative_to(ROOT / 'public'), 'Asset escapes public directory')
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        (stage / 'data.js').write_text(js_assignment('TROV_DATA', history), encoding='utf-8')
        (stage / 'runtime.js').write_text(js_assignment('TROV_RUNTIME', runtime), encoding='utf-8')
        for relative, content in reports.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (stage / '_headers').write_text(
            '/*\n  Cache-Control: no-cache\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: same-origin\n'
            '/data.js\n  Cache-Control: no-store\n/runtime.js\n  Cache-Control: no-store\n'
            '/reports/*\n  Content-Security-Policy: default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; font-src data:; script-src \'none\'; frame-ancestors \'self\'; base-uri \'none\'; form-action \'none\'\n', encoding='utf-8')
        manifest['sha256'] = {str(p.relative_to(stage)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(stage.rglob('*')) if p.is_file()}
        (stage / '.trov-static-export.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            backup = Path(tempfile.mkdtemp(prefix='static-previous-', dir=temp_root)).resolve()
            backup.rmdir()
            output.rename(backup)
        try:
            stage.rename(output)
        except OSError:
            if backup:
                backup.rename(output)
                backup = None
            raise
    finally:
        for disposable in (stage, backup):
            if disposable and disposable.exists():
                require(disposable.resolve().is_relative_to(temp_root.resolve()), 'Cleanup path escapes build workspace')
                shutil.rmtree(disposable)
    return {k: v for k, v in manifest.items() if k != 'sha256'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--ads-root', type=Path, default=Path(os.environ.get('TROV_ADS_ROOT', ROOT.parent / 'Trov_ADS')))
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    try:
        result = export_static(args.data_dir, args.ads_root, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Static export failed ({type(exc).__name__}): {exc}\n')
    print(json.dumps({'status': 'ready', 'output': str(args.output), **result}, ensure_ascii=True))


if __name__ == '__main__':
    main()
