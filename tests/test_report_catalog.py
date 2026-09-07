"""Regression check for the daily report preview attribution fields."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
import report_catalog


class ReportCatalogTests(unittest.TestCase):
    def test_incomplete_source_window_is_rejected(self):
        manifest = {'window': {'shopify_end_exclusive': '2099-01-01T00:00:00-08:00'}}
        self.assertFalse(report_catalog.completed_window(manifest))

    def test_preview_prefers_current_meta_attribution_fields(self):
        with tempfile.TemporaryDirectory(dir=PROJECT / '.tmp') as folder:
            root = Path(folder)
            report = root / 'audits/automation/meta-shopify-daily/2026-09-03'
            report.mkdir(parents=True)
            (report / 'run-manifest.json').write_text(json.dumps({
                'status': 'ready', 'writes_performed': False, 'report_date': '2026-09-03',
                'timezone': 'America/Los_Angeles', 'window': {'since': '2026-09-03', 'until': '2026-09-03'},
            }), encoding='utf-8')
            (report / 'data.json').write_text(json.dumps({
                'generated_at_utc': '2026-09-04T08:00:00Z',
                'meta': {'ads': {'A02': {'spend': 38.6, 'purchases': 0, 'purchase_value': 0},
                                 'A03': {'spend': 0, 'purchases': 0, 'purchase_value': 0}}},
                'shopify': {'all_orders': 1, 'meta_attributed_orders': 1, 'meta_net_sales': 127.5,
                            'campaign_utm_orders': 0, 'campaign_net_sales': 0},
            }), encoding='utf-8')
            (report / 'report.html').write_text(
                '<!doctype html><section class="summary"><p>当日 Meta 投流获得 1 单。</p></section>', encoding='utf-8')
            with patch.object(report_catalog, 'ADS', root):
                item = report_catalog.catalog()['reports'][0]
            self.assertEqual(item['metaPurchases'], 1)
            self.assertEqual(item['campaignOrders'], 1)
            self.assertEqual(item['metaPurchaseValue'], 127.5)
            self.assertAlmostEqual(item['metaRoas'], 127.5 / 38.6)
            self.assertEqual(item['platformMetaPurchases'], 0)


if __name__ == '__main__':
    unittest.main()
