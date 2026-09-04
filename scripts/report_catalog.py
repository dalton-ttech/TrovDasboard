"""Index existing ready daily/weekly report bundles. The source project is read-only."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADS = Path(os.environ.get('TROV_ADS_ROOT', str(ROOT.parent / 'Trov_ADS')))

class ReportText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.summary = []
        self.depth = 0
        self.summary_depth = None
        self.scripts = 0
        self.external_assets = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == 'section':
            self.depth += 1
            if 'summary' in attr.get('class', '').split():
                self.summary_depth = self.depth
        if tag == 'script':
            self.scripts += 1
        for key in ('src', 'href'):
            if attr.get(key, '').startswith('http'):
                self.external_assets.append(attr[key])

    def handle_endtag(self, tag):
        if tag == 'section':
            if self.depth == self.summary_depth:
                self.summary_depth = None
            self.depth -= 1

    def handle_data(self, data):
        if self.summary_depth is not None:
            self.summary.append(data.strip())

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def catalog():
    reports, skipped = [], []
    for kind in ('daily', 'weekly'):
        base = ADS / 'audits' / 'automation' / f'meta-shopify-{kind}'
        for manifest_path in sorted(base.glob('????-??-??/run-manifest.json')):
            try:
                manifest = read_json(manifest_path)
                folder = manifest_path.parent
                if manifest.get('status') != 'ready' or manifest.get('writes_performed') is not False:
                    continue
                data = read_json(folder / 'data.json')
                html = (folder / 'report.html').read_text(encoding='utf-8-sig')
                parsed = ReportText()
                parsed.feed(html)
                window = manifest.get('window', {})
                date = manifest.get('report_date') or manifest.get('period_end') or folder.name
                ads = (data.get('meta') or {}).get('ads', {})
                focus = {k: v for k, v in ads.items() if k in ('A02', 'A03')}
                def total(key):
                    values = [v.get(key) for v in focus.values()]
                    return sum(float(v) for v in values if v is not None) if values and any(v is not None for v in values) else None
                spend, purchases, revenue = total('spend'), total('purchases'), total('purchase_value')
                shopify = data.get('shopify', {})
                files = {name: f'/reports/{kind}/{folder.name}/{filename}' for name, filename in [('html', 'report.html'), ('preview', 'report-preview.png')] if (folder / filename).is_file()}
                reports.append({
                    'id': f'{kind}-{folder.name}', 'kind': kind, 'date': date,
                    'since': window.get('since') or manifest.get('period_start') or date,
                    'until': window.get('until') or date,
                    'timezone': manifest.get('timezone', 'America/Los_Angeles'),
                    'generatedAt': data.get('generated_at_utc'),
                    'title': 'Meta × Shopify ' + ('投流日报' if kind == 'daily' else '投流周报'),
                    'summary': ' '.join(s for s in parsed.summary if s and s != '只读生成'),
                    'spend': spend, 'metaPurchases': purchases,
                    'metaPurchaseValue': revenue,
                    'metaRoas': revenue / spend if spend and revenue is not None else None,
                    'metaCpa': spend / purchases if purchases and spend is not None else None,
                    'shopifyOrders': shopify.get('all_orders'),
                    'campaignOrders': shopify.get('campaign_utm_orders'),
                    'campaignNetSales': shopify.get('campaign_net_sales'),
                    'adScope': list(focus), 'status': 'ready', 'writesPerformed': False,
                    'files': files,
                })
            except (OSError, ValueError, TypeError) as exc:
                skipped.append({'id': f'{kind}-{manifest_path.parent.name}', 'reason': type(exc).__name__})
    reports.sort(key=lambda r: (r['until'], r['kind'] == 'daily'), reverse=True)
    return {'indexedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': 'Trov_ADS', 'reports': reports, 'skipped': skipped}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    result = catalog()
    if args.inspect:
        sample_path = ADS / 'audits/automation/meta-shopify-daily/2026-09-03/data.json'
        data = read_json(sample_path)
        print(json.dumps({'topKeys': list(data), 'adKeys': {k: list(v) for k, v in data.get('meta_ads', {}).items()}, 'shopifyKeys': list(data.get('shopify', {})), 'counts': {kind: sum(r['kind'] == kind for r in result['reports']) for kind in ('daily', 'weekly')}, 'latest': result['reports'][:2], 'skipped': result['skipped']}, ensure_ascii=True, indent=2))
    else:
        output = ROOT / 'data' / 'reports.json'
        output.parent.mkdir(exist_ok=True)
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(output)
        print(json.dumps({'status': 'ready', 'count': len(result['reports']), 'writes_performed': False}))

if __name__ == '__main__':
    main()
