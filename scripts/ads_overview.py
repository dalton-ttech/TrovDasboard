"""Read complete Pacific 30/7-day commerce and advertising summaries.

Reuses Trov_ADS read helpers. No report generation, remote mutations, source-project
writes, customer details or access credentials are persisted.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import math
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ADS = Path(os.environ.get('TROV_ADS_ROOT', str(ROOT.parent / 'Trov_ADS'))).resolve()
sys.path.insert(0, str(ADS / 'scripts'))
from monitor_restart_v2 import (
    DEFAULT_CONFIG, DEFAULT_STATE, fetch_shopify_orders, get_meta_ad_metrics,
    shopify_created_at_bounds, shopify_token, summarize_shopify_orders,
)
from sync_meta_ads import api_request
from trov_time import pacific_now, PACIFIC_NAME


def periods(end: dt.date):
    return {str(days): {'days': days, 'since': (end - dt.timedelta(days=days-1)).isoformat(), 'until': end.isoformat()} for days in (30, 7)}


METRICS = ('shopifyNetSales', 'shopifyOrders', 'metaRoas')


def direction(current, previous):
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (current, previous)):
        return None
    if math.isclose(current, previous, rel_tol=0, abs_tol=1e-9):
        return 'flat'
    return 'up' if current > previous else 'down'


def compare(current, previous, *, basis, observed_at):
    # One-day-shifted rolling window, never the preceding non-overlapping 7/30 days.
    if current['days'] != previous['days'] or any(
        dt.date.fromisoformat(current[key]) - dt.date.fromisoformat(previous[key]) != dt.timedelta(days=1)
        for key in ('since', 'until')
    ):
        raise ValueError('The comparison must be the same window shifted by one Pacific date')
    return {
        'since': previous['since'], 'until': previous['until'], 'basis': basis,
        'observedAt': observed_at,
        'values': {key: previous.get(key) for key in METRICS},
        'directions': {key: direction(current.get(key), previous.get(key)) for key in METRICS},
    }


def previous_snapshot(today, ranges):
    source = ROOT / 'data' / 'ads-overview-history' / f'{today - dt.timedelta(days=1)}.json'
    try:
        saved = json.loads(source.read_text(encoding='utf-8'))
        if saved.get('status') != 'ready' or saved.get('timezone') != PACIFIC_NAME or saved.get('adScope') != ['A02', 'A03']:
            return None
        for key, window in ranges.items():
            record = saved['periods'][key]
            if record.get('status') != 'ready' or record.get('currency') != 'USD' or any(record.get(field) != window[field] for field in ('days', 'since', 'until')):
                return None
        return saved
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_json(output, result):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)


def summarize(period, orders, metrics, campaign):
    start, stop = shopify_created_at_bounds(period['since'], period['until'])
    start_dt, stop_dt = dt.datetime.fromisoformat(start), dt.datetime.fromisoformat(stop)
    subset = [o for o in orders if start_dt <= dt.datetime.fromisoformat(o['createdAt'].replace('Z', '+00:00')) < stop_dt]
    summary = summarize_shopify_orders(subset, campaign)
    spend = round(sum(m['spend'] for m in metrics), 2)
    value = round(sum(m['purchase_value'] for m in metrics), 2)
    return {
        **period, 'status': 'ready', 'currency': 'USD',
        'shopifyNetSales': summary['all_net_sales'], 'shopifyOrders': summary['all_orders'],
        'metaSpend': spend, 'metaPurchaseValue': value,
        'metaPurchases': sum(m['purchases'] for m in metrics),
        'metaRoas': value / spend if spend > 0 else None,
        'shopifyStartInclusive': start, 'shopifyEndExclusive': stop,
        'salesBasis': summary['net_sales_basis'],
    }


def sync():
    meta_token = (os.environ.get('META_ACCESS_TOKEN') or '').strip()
    if not meta_token:
        raise RuntimeError('Existing Meta read credentials are unavailable')
    config = json.loads((ADS / DEFAULT_CONFIG).read_text(encoding='utf-8-sig'))
    state = json.loads((ADS / DEFAULT_STATE).read_text(encoding='utf-8-sig'))
    account = api_request(meta_token, str(config['account_id']), {'fields': 'timezone_name,currency'})
    if account.get('timezone_name') != PACIFIC_NAME or account.get('currency') != 'USD':
        raise RuntimeError('Account timezone or currency does not match the existing reporting basis')
    ad_ids = [str((state.get('ads', {}).get(key) or {}).get('ad_id') or '') for key in ('A02', 'A03')]
    if not all(ad_ids):
        raise RuntimeError('A02/A03 configuration is incomplete')
    today = pacific_now().date()
    ranges = periods(today - dt.timedelta(days=1))
    previous_ranges = periods(today - dt.timedelta(days=2))
    saved = previous_snapshot(today, previous_ranges)
    requested = {f'current-{key}': value for key, value in ranges.items()}
    if not saved:
        requested.update({f'previous-{key}': value for key, value in previous_ranges.items()})
    shop, token = shopify_token()
    start, stop = shopify_created_at_bounds(min(p['since'] for p in requested.values()), ranges['30']['until'])
    with ThreadPoolExecutor(max_workers=3) as pool:
        order_job = pool.submit(fetch_shopify_orders, shop, token, start, stop)
        metric_jobs = {key: [pool.submit(get_meta_ad_metrics, meta_token, ad, period['since'], period['until']) for ad in ad_ids] for key, period in requested.items()}
        orders = order_job.result()
        summaries = {key: summarize(period, orders, [job.result() for job in metric_jobs[key]], config['campaign']['name']) for key, period in requested.items()}
    synced_at = dt.datetime.now(dt.timezone.utc).isoformat()
    results = {}
    for key in ranges:
        current = summaries[f'current-{key}']
        previous = saved['periods'][key] if saved else summaries[f'previous-{key}']
        results[key] = {**current, 'comparison': compare(current, previous,
            basis='previous_day_snapshot' if saved else 'recomputed_previous_window',
            observed_at=saved['syncedAt'] if saved else synced_at)}
    result = {
        'status': 'ready', 'syncedAt': synced_at, 'calculatedForDate': today.isoformat(),
        'timezone': PACIFIC_NAME, 'completeDaysOnly': True, 'adScope': ['A02', 'A03'],
        'periods': results, 'writesPerformed': False,
    }
    # Keep daily calculation results so future arrows compare with yesterday's actual snapshot.
    archive = {**result, 'periods': {key: {field: value for field, value in period.items() if field != 'comparison'} for key, period in results.items()}}
    save_json(ROOT / 'data' / 'ads-overview-history' / f'{today}.json', archive)
    save_json(ROOT / 'data' / 'ads-overview.json', result)
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(sync(), ensure_ascii=True))
    except Exception as exc:
        # Deliberately omit raw upstream exception text, payloads and credential values.
        print(json.dumps({'status': 'error', 'errorType': type(exc).__name__, 'message': 'Read failed; previous snapshot retained', 'writesPerformed': False}))
        raise SystemExit(1)
