import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

from scripts import run_daily_publish as publisher


class DailyPublishTests(unittest.TestCase):
    def test_complete_pacific_date_observes_daylight_and_standard_time(self):
        daylight = dt.datetime(2026, 9, 8, 7, 5, tzinfo=dt.timezone.utc)
        standard = dt.datetime(2026, 12, 7, 7, 5, tzinfo=dt.timezone.utc)

        self.assertEqual(publisher.latest_complete_pacific_date(daylight), dt.date(2026, 9, 7))
        self.assertEqual(publisher.pacific_now(daylight).tzname(), 'PDT')
        self.assertEqual(publisher.latest_complete_pacific_date(standard), dt.date(2026, 12, 5))
        self.assertEqual(publisher.pacific_now(standard).tzname(), 'PST')

    def test_backfill_and_latest_complete_week(self):
        self.assertEqual(
            publisher.dates_after(dt.date(2026, 9, 4), dt.date(2026, 9, 7), limit=31),
            [dt.date(2026, 9, 5), dt.date(2026, 9, 6), dt.date(2026, 9, 7)],
        )
        self.assertEqual(publisher.latest_sunday(dt.date(2026, 9, 7)), dt.date(2026, 9, 6))
        self.assertEqual(publisher.latest_sunday(dt.date(2026, 9, 6)), dt.date(2026, 9, 6))

    def test_weekly_bundle_must_be_generated_after_window_end(self):
        with tempfile.TemporaryDirectory() as temporary:
            ads_root = Path(temporary)
            folder = ads_root / 'audits' / 'automation' / 'meta-shopify-weekly' / '2026-09-06'
            folder.mkdir(parents=True)
            html = folder / 'report.html'
            html.write_text('<html>' + ('complete report ' * 100) + '</html>', encoding='utf-8')
            manifest = {
                'status': 'ready',
                'writes_performed': False,
                'report_type': 'trov_meta_shopify_weekly_overview',
                'period_start': '2026-08-31',
                'period_end': '2026-09-06',
                'window': {
                    'since': '2026-08-31',
                    'until': '2026-09-06',
                    'shopify_end_exclusive': '2026-09-07T00:00:00-07:00',
                },
                'html': str(html),
            }
            data = {
                'status': 'ready',
                'writes_performed': False,
                'generated_at_utc': '2026-09-07T06:19:00+00:00',
                'meta': {'ads': {
                    'A02': {'spend': 10, 'purchase_value': 20},
                    'A03': {'spend': 5, 'purchase_value': 5},
                }},
                'shopify': {'shopify_units_sold': 3},
            }
            (folder / 'run-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            (folder / 'data.json').write_text(json.dumps(data), encoding='utf-8')
            now = dt.datetime(2026, 9, 7, 8, tzinfo=dt.timezone.utc)

            with self.assertRaisesRegex(publisher.PublishError, 'before its source window ended'):
                publisher.validate_report_bundle(
                    ads_root, 'weekly', dt.date(2026, 9, 6), now_utc=now, require_render=False
                )

            data['generated_at_utc'] = '2026-09-07T07:01:00+00:00'
            (folder / 'data.json').write_text(json.dumps(data), encoding='utf-8')
            result = publisher.validate_report_bundle(
                ads_root, 'weekly', dt.date(2026, 9, 6), now_utc=now, require_render=False
            )
            self.assertEqual(result['date'], '2026-09-06')
            self.assertEqual(result['metrics'], {
                'metaSpendUsd': 15.0,
                'shopifyUnitsSold': 3,
                'metaRoas': 1.67,
            })
            self.assertEqual(
                result['publicHtml'],
                'https://trov-work.pages.dev/reports/weekly/2026-09-06/report.html',
            )

            data['meta']['ads']['A01'] = {}
            (folder / 'data.json').write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(publisher.PublishError, 'only A02/A03'):
                publisher.validate_report_bundle(
                    ads_root, 'weekly', dt.date(2026, 9, 6), now_utc=now, require_render=False
                )

    def test_public_report_directory_is_updated_in_place(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dist = root / 'dist'
            public = root / 'public'
            (dist / 'reports' / 'daily' / '2026-09-09').mkdir(parents=True)
            (public / 'reports' / 'daily' / '2026-09-08').mkdir(parents=True)
            (dist / '.trov-static-export.json').write_text('{}', encoding='utf-8')
            for name in ('data.js', 'runtime.js', '_headers'):
                (dist / name).write_text(f'new {name}', encoding='utf-8')
                (public / name).write_text(f'old {name}', encoding='utf-8')
            expected = dist / 'reports' / 'daily' / '2026-09-09' / 'report.html'
            expected.write_text('new report', encoding='utf-8')
            stale = public / 'reports' / 'daily' / '2026-09-08' / 'report.html'
            stale.write_text('stale report', encoding='utf-8')
            reports_identity = (public / 'reports').stat().st_ino

            publisher.copy_export_to_public(dist, public)

            self.assertEqual((public / 'reports').stat().st_ino, reports_identity)
            self.assertEqual(
                (public / 'reports' / 'daily' / '2026-09-09' / 'report.html').read_text(encoding='utf-8'),
                'new report',
            )
            self.assertFalse(stale.exists())
            self.assertEqual((public / 'runtime.js').read_text(encoding='utf-8'), 'new runtime.js')


if __name__ == '__main__':
    unittest.main()
