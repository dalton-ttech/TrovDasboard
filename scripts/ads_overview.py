"""Read complete Pacific 30/7-day commerce and advertising summaries.

Reuses Trov_ADS read helpers. No report generation, remote mutations, source-project
writes, customer details or access credentials are persisted.
"""
from __future__ import annotations
import datetime as dt
import json
import os
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
    ranges = periods(pacific_now().date() - dt.timedelta(days=1))
    shop, token = shopify_token()
    start, stop = shopify_created_at_bounds(ranges['30']['since'], ranges['30']['until'])
    with ThreadPoolExecutor(max_workers=3) as pool:
        order_job = pool.submit(fetch_shopify_orders, shop, token, start, stop)
        metric_jobs = {key: [pool.submit(get_meta_ad_metrics, meta_token, ad, period['since'], period['until']) for ad in ad_ids] for key, period in ranges.items()}
        orders = order_job.result()
        results = {key: summarize(period, orders, [job.result() for job in metric_jobs[key]], config['campaign']['name']) for key, period in ranges.items()}
    result = {
        'status': 'ready', 'syncedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
        'timezone': PACIFIC_NAME, 'completeDaysOnly': True, 'adScope': ['A02', 'A03'],
        'periods': results, 'writesPerformed': False,
    }
    output = ROOT / 'data' / 'ads-overview.json'
    output.parent.mkdir(exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(sync(), ensure_ascii=True))
    except Exception as exc:
        # Deliberately omit raw upstream exception text, payloads and credential values.
        print(json.dumps({'status': 'error', 'errorType': type(exc).__name__, 'message': 'Read failed; previous snapshot retained', 'writesPerformed': False}))
        raise SystemExit(1)
