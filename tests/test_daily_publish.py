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
                'meta': {'ads': {'A02': {}, 'A03': {}}},
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


if __name__ == '__main__':
    unittest.main()
