import datetime as dt
from pathlib import Path
import sys
import unittest
import json
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ads_overview import periods, summarize, shopify_created_at_bounds, compare, direction, previous_snapshot


def order(key, created, amount='20.00', **extra):
    return {'id': key, 'createdAt': created, 'test': False, 'cancelledAt': None,
            'displayFinancialStatus': 'PAID', 'taxesIncluded': False,
            'currentSubtotalPriceSet': {'shopMoney': {'amount': amount, 'currencyCode': 'USD'}},
            'currentTotalPriceSet': {'shopMoney': {'amount': amount, 'currencyCode': 'USD'}},
            'lineItems': {'nodes': []}, **extra}


class AdsOverviewTests(unittest.TestCase):
    def test_exact_completed_calendar_windows_and_dst(self):
        ranges = periods(dt.date(2026, 9, 3))
        self.assertEqual(ranges['30']['since'], '2026-08-05')
        self.assertEqual(ranges['7']['since'], '2026-08-28')
        self.assertEqual(ranges['7']['until'], ranges['30']['until'])
        start, stop = shopify_created_at_bounds('2026-10-26', '2026-11-01')
        self.assertEqual((dt.datetime.fromisoformat(stop)-dt.datetime.fromisoformat(start)).total_seconds()/3600, 169)

    def test_shared_order_cohort_respects_pacific_midnight_and_eligible_orders(self):
        window = periods(dt.date(2026, 9, 3))['7']
        orders = [order('before','2026-08-28T06:59:59Z'), order('start','2026-08-28T07:00:00Z'),
                  order('end','2026-09-04T06:59:59Z'), order('outside','2026-09-04T07:00:00Z'),
                  order('test','2026-09-01T10:00:00Z',test=True),
                  order('cancelled','2026-09-01T10:00:00Z',cancelledAt='2026-09-01T11:00:00Z'),
                  order('unpaid','2026-09-01T10:00:00Z',displayFinancialStatus='PENDING')]
        result = summarize(window,orders,[],'example')
        self.assertEqual(result['shopifyOrders'],2)
        self.assertEqual(result['shopifyNetSales'],40)

    def test_roas_is_total_value_over_total_spend_not_average_ad_roas(self):
        window = periods(dt.date(2026,9,3))['30']
        metrics = [{'spend':10,'purchase_value':100,'purchases':1}, {'spend':90,'purchase_value':90,'purchases':1}]
        result = summarize(window,[],metrics,'example')
        self.assertEqual(result['metaRoas'],1.9)
        self.assertEqual(result['metaSpend'],100)
        self.assertIsNone(summarize(window,[],[],'example')['metaRoas'])

    def test_comparison_is_one_day_shifted_with_independent_metric_directions(self):
        for key in ('7', '30'):
            current = {**periods(dt.date(2026,9,3))[key], 'shopifyNetSales':120, 'shopifyOrders':3, 'metaRoas':1.5}
            previous = {**periods(dt.date(2026,9,2))[key], 'shopifyNetSales':100, 'shopifyOrders':3, 'metaRoas':2}
            result = compare(current, previous, basis='previous_day_snapshot', observed_at='2026-09-03T12:00:00Z')
            self.assertEqual(result['directions'], {'shopifyNetSales':'up', 'shopifyOrders':'flat', 'metaRoas':'down'})
            self.assertEqual(result['since'], previous['since'])
            with self.assertRaises(ValueError):
                compare(current, {**previous, 'until':'2026-08-03'}, basis='example', observed_at='')

    def test_missing_and_zero_baselines_do_not_invent_progress(self):
        self.assertIsNone(direction(None, 1))
        self.assertIsNone(direction(1, None))
        self.assertIsNone(direction(float('nan'), 1))
        self.assertEqual(direction(1, 0), 'up')
        self.assertEqual(direction(0, 1), 'down')
        self.assertEqual(direction(0, 0), 'flat')

    def test_only_an_exact_previous_day_snapshot_is_reused(self):
        today = dt.date(2026,9,4)
        windows = periods(today - dt.timedelta(days=2))
        saved = {'status':'ready', 'timezone':'America/Los_Angeles', 'adScope':['A02','A03'],
                 'syncedAt':'2026-09-03T12:00:00Z',
                 'periods':{key:{**window, 'status':'ready', 'currency':'USD'} for key,window in windows.items()}}
        with tempfile.TemporaryDirectory() as folder, patch('ads_overview.ROOT', Path(folder)):
            source = Path(folder)/'data/ads-overview-history/2026-09-03.json'
            source.parent.mkdir(parents=True)
            source.write_text(json.dumps(saved), encoding='utf-8')
            self.assertEqual(previous_snapshot(today,windows)['syncedAt'],saved['syncedAt'])
            saved['periods']['7']['until'] = '2026-09-01'
            source.write_text(json.dumps(saved), encoding='utf-8')
            self.assertIsNone(previous_snapshot(today,windows))


if __name__ == '__main__':
    unittest.main()
