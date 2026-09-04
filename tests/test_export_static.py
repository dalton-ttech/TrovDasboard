"""Verify complete static exports and fail-closed replacement with synthetic data."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
import export_static as exporter


def make_period(days):
    until = dt.date(2026, 9, 3)
    since = until - dt.timedelta(days=days - 1)
    return {
        'days': days, 'since': since.isoformat(), 'until': until.isoformat(),
        'status': 'ready', 'currency': 'USD', 'shopifyNetSales': 120.5,
        'shopifyOrders': 3, 'metaSpend': 20, 'metaPurchaseValue': 60,
        'metaPurchases': 2, 'metaRoas': 3,
        'comparison': {
            'since': (since - dt.timedelta(days=1)).isoformat(),
            'until': (until - dt.timedelta(days=1)).isoformat(),
            'basis': 'previous_day_snapshot', 'observedAt': '2026-09-03T12:00:00Z',
            'values': {'shopifyNetSales': 100, 'shopifyOrders': 3, 'metaRoas': 4},
            'directions': {'shopifyNetSales': 'up', 'shopifyOrders': 'flat', 'metaRoas': 'down'},
        },
    }


class StaticExportTests(unittest.TestCase):
    def setUp(self):
        temp_root = PROJECT / '.tmp'
        temp_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='test-static-export-', dir=temp_root)
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(temp_root.resolve()))
        self.addCleanup(self.temp.cleanup)
        self.root_patch = patch.object(exporter, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        for name in exporter.ASSETS:
            destination = self.root / 'public' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT / 'public' / name, destination)
        self.data_dir = self.root / 'data'
        self.data_dir.mkdir()
        self.ads_root = self.root / 'ads-source'
        self.report_dir = self.ads_root / 'audits/automation/meta-shopify-daily/2026-09-03'
        self.report_dir.mkdir(parents=True)
        self.report_html = b'\xef\xbb\xbf<!doctype html><html><head><style>body{color:#14223f}</style></head><body><h1>Fixture report</h1><p>120.50 USD</p></body></html>\r\n'
        (self.report_dir / 'report.html').write_bytes(self.report_html)
        (self.report_dir / 'run-manifest.json').write_text(json.dumps({
            'status': 'ready', 'writes_performed': False,
        }), encoding='utf-8')
        # These source artifacts must never leak into the static output.
        for name in ('report.pdf', 'report-preview.png', 'data.json'):
            (self.report_dir / name).write_bytes(b'not publishable')
        self.sources = {
            'history.json': {
                'snapshotDate': '2026-09-04', 'sourceFile': 'synthetic-history.xlsx',
                'timeBasis': 'OMS original timestamp; timezone unspecified',
                'shipments': [{'id': 'fixture-shipment', 'order': 'fixture-order',
                               'status': '运输中', 'createdAt': '2026-09-01 10:00:00',
                               'note': '<source text>\u2028\u2029'}],
            },
            'shopify-logistics.json': {
                'status': 'ready', 'writesPerformed': False,
                'syncedAt': '2026-09-04T10:00:00Z',
                'window': {'since': '2026-08-01', 'untilExclusive': '2026-09-05'},
                'shipments': [{'id': 'fixture-shipment', 'order': 'fixture-order',
                               'orderCreatedAt': '2026-09-01T17:00:00Z',
                               'events': [{'status': 'IN_TRANSIT', 'happenedAt': '2026-09-02T12:00:00Z'}]}],
                'coverage': {'orderCreatedAt': 1, 'events': 1},
            },
            'ads-overview.json': {
                'status': 'ready', 'writesPerformed': False,
                'syncedAt': '2026-09-04T11:00:00Z', 'calculatedForDate': '2026-09-04',
                'timezone': 'America/Los_Angeles', 'completeDaysOnly': True,
                'adScope': ['A02', 'A03'],
                'periods': {'7': make_period(7), '30': make_period(30)},
            },
            'reports.json': {
                'indexedAt': '2026-09-04T11:05:00Z', 'source': 'Trov_ADS',
                'reports': [{
                    'id': 'daily-2026-09-03', 'kind': 'daily', 'date': '2026-09-03',
                    'since': '2026-09-03', 'until': '2026-09-03',
                    'title': 'Fixture daily report', 'adScope': ['A02', 'A03'],
                    'status': 'ready', 'writesPerformed': False,
                    'files': {'html': '/reports/daily/2026-09-03/report.html',
                              'preview': '/reports/daily/2026-09-03/report-preview.png'},
                }], 'skipped': [],
            },
        }
        self.output = self.root / 'dist'
        self.write_sources(self.sources)

    def write_sources(self, sources):
        for name, value in sources.items():
            (self.data_dir / name).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def export(self):
        return exporter.export_static(self.data_dir, self.ads_root, self.output)

    def output_hashes(self):
        return {p.relative_to(self.output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.output.rglob('*') if p.is_file()}

    def read_assignment(self, filename, variable):
        text = (self.output / filename).read_text(encoding='utf-8')
        prefix = f'window.{variable} = '
        self.assertTrue(text.startswith(prefix))
        return json.loads(text[len(prefix):].strip().removesuffix(';'))

    def test_complete_export_preserves_values_report_bytes_and_source_files(self):
        source_bytes = {p.name: p.read_bytes() for p in self.data_dir.iterdir()}
        result = self.export()
        self.assertEqual(self.read_assignment('data.js', 'TROV_DATA'), self.sources['history.json'])
        runtime = self.read_assignment('runtime.js', 'TROV_RUNTIME')
        self.assertEqual(runtime['logistics'], self.sources['shopify-logistics.json'])
        self.assertEqual(runtime['adsOverview'], self.sources['ads-overview.json'])
        catalog = copy.deepcopy(self.sources['reports.json'])
        del catalog['reports'][0]['files']['preview']
        self.assertEqual(runtime['reports'], catalog)
        self.assertIs(runtime['serverAvailable'], False)
        self.assertEqual(runtime['deliveryMode'], 'static-snapshot')
        self.assertEqual((self.output / 'reports/daily/2026-09-03/report.html').read_bytes(), self.report_html)
        self.assertEqual(result['logisticsSyncedAt'], self.sources['shopify-logistics.json']['syncedAt'])
        self.assertEqual(result['adsSyncedAt'], self.sources['ads-overview.json']['syncedAt'])
        self.assertEqual(result['reportCount'], 1)
        self.assertEqual(source_bytes, {p.name: p.read_bytes() for p in self.data_dir.iterdir()})
        data_js = (self.output / 'data.js').read_text(encoding='utf-8')
        self.assertNotIn('<', data_js)
        self.assertNotIn('\u2028', data_js)
        self.assertNotIn('\u2029', data_js)
        expected = set(exporter.ASSETS) | {
            'data.js', 'runtime.js', '_headers', '.trov-static-export.json',
            'reports/daily/2026-09-03/report.html',
        }
        self.assertEqual(set(self.output_hashes()), expected)
        manifest = json.loads((self.output / '.trov-static-export.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['sha256'], {
            name: value for name, value in self.output_hashes().items()
            if name != '.trov-static-export.json'
        })

    def test_missing_snapshot_preserves_previous_output(self):
        self.export()
        before = self.output_hashes()
        (self.data_dir / 'ads-overview.json').unlink()
        with self.assertRaises(OSError):
            self.export()
        self.assertEqual(self.output_hashes(), before)

    def test_invalid_snapshots_preserve_previous_output(self):
        self.export()
        before = self.output_hashes()
        def invalid_status(s):
            s['shopify-logistics.json']['status'] = 'error'
        def missing_metric(s):
            del s['ads-overview.json']['periods']['7']['shopifyOrders']
        def wrong_direction(s):
            s['ads-overview.json']['periods']['30']['comparison']['directions']['metaRoas'] = 'up'
        def wrong_roas(s):
            s['ads-overview.json']['periods']['7']['metaRoas'] = 99
        def coverage_mismatch(s):
            s['shopify-logistics.json']['coverage']['events'] = 0
        def duplicate_id(s):
            s['history.json']['shipments'] *= 2
        for mutate in (invalid_status, missing_metric, wrong_direction, wrong_roas, coverage_mismatch, duplicate_id):
            with self.subTest(case=mutate.__name__):
                changed = copy.deepcopy(self.sources)
                mutate(changed)
                self.write_sources(changed)
                with self.assertRaises((ValueError, KeyError)):
                    self.export()
                self.assertEqual(self.output_hashes(), before)

    def test_copy_failure_preserves_previous_output(self):
        self.export()
        before = self.output_hashes()
        (self.root / 'public' / exporter.ASSETS[-1]).unlink()
        with self.assertRaises(OSError):
            self.export()
        self.assertEqual(self.output_hashes(), before)
        self.assertEqual(list((self.root / '.tmp').glob('static-build-*')), [])

    def test_illegal_report_path_and_id_are_rejected(self):
        self.export()
        before = self.output_hashes()
        for field, value in (('html', '/reports/daily/2026-09-03/../../data.json'),
                             ('html', 'https://example.invalid/report.html'),
                             ('id', 'daily-../../outside'), ('id', 'daily-2026-02-30')):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(self.sources)
                report = changed['reports.json']['reports'][0]
                (report['files'] if field == 'html' else report)[field] = value
                self.write_sources(changed)
                with self.assertRaises(ValueError):
                    self.export()
                self.assertEqual(self.output_hashes(), before)

    def test_report_active_content_and_external_dependencies_are_rejected(self):
        self.export()
        before = self.output_hashes()
        for html in ('<script>alert(1)</script>', '<svg onload="alert(1)"></svg>',
                     '<iframe srcdoc="hello"></iframe>', '<form></form>',
                     '<img src="https://example.invalid/a.png">', '<img src="local.png">',
                     '<style>@import "theme.css";</style>',
                     '<style>body{background:url(https://example.invalid/a.png)}</style>',
                     '<meta http-equiv="refresh" content="0;url=https://example.invalid">'):
            with self.subTest(html=html):
                (self.report_dir / 'report.html').write_text(html, encoding='utf-8')
                with self.assertRaises(ValueError):
                    self.export()
                self.assertEqual(self.output_hashes(), before)

    def test_nested_credential_or_customer_fields_are_rejected(self):
        self.export()
        before = self.output_hashes()
        for key in ('access_token', 'client-secret', 'apiKey', 'email', 'phone', 'firstName'):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.sources)
                changed['shopify-logistics.json']['shipments'][0]['unexpected'] = {key: 'synthetic-forbidden-value'}
                self.write_sources(changed)
                with self.assertRaisesRegex(ValueError, 'prohibited'):
                    self.export()
                self.assertEqual(self.output_hashes(), before)

    def test_unready_report_manifest_or_embedded_credential_is_rejected(self):
        self.export()
        before = self.output_hashes()
        manifest = self.report_dir / 'run-manifest.json'
        manifest.write_text(json.dumps({'status': 'ready', 'writes_performed': True}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'manifest'):
            self.export()
        self.assertEqual(self.output_hashes(), before)
        manifest.write_text(json.dumps({'status': 'ready', 'writes_performed': False}), encoding='utf-8')
        (self.report_dir / 'report.html').write_text('<p>shpat_' + '0' * 32 + '</p>', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'credential'):
            self.export()
        self.assertEqual(self.output_hashes(), before)

    def test_unmanaged_destination_is_not_replaced(self):
        self.output.mkdir()
        sentinel = self.output / 'keep.txt'
        sentinel.write_text('unrelated output', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'not created by this exporter'):
            self.export()
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'unrelated output')


if __name__ == '__main__':
    unittest.main()
