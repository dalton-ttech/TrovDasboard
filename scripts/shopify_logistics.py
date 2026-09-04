"""Read Shopify logistics using the existing Trov_ADS credentials and auth helper.

Only GraphQL queries are permitted. No raw payloads, credentials, customer names,
contact fields or street addresses are written to disk.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ADS = Path(os.environ.get('TROV_ADS_ROOT', str(ROOT.parent / 'Trov_ADS'))).resolve()
sys.path.insert(0, str(ADS / 'scripts'))
from monitor_restart_v2 import shopify_token
from analyze_shopify_ads_context import API_VERSION, request_json

OUTPUT = ROOT / 'data' / 'shopify-logistics.json'
UTC = dt.timezone.utc

class SyncError(RuntimeError):
    pass

def iso_now():
    return dt.datetime.now(UTC).isoformat()

def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)

def read_history():
    source = ROOT / 'data' / 'history.json'
    return json.loads(source.read_text(encoding='utf-8')) if source.is_file() else {'shipments': []}

def graphql(shop, token, query, variables=None):
    if not query.lstrip().startswith('query ') or re.search(r'\bmutation\b', query):
        raise SyncError('Only named read-only GraphQL queries are permitted')
    for attempt in range(3):
        try:
            result = request_json(
                f'https://{shop}.myshopify.com/admin/api/{API_VERSION}/graphql.json',
                data={'query': query, 'variables': variables or {}},
                headers={'Content-Type': 'application/json', 'X-Shopify-Access-Token': token},
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise SyncError(f'Shopify HTTP {exc.code}') from None
        if any(error.get('extensions', {}).get('code') == 'THROTTLED' for error in result.get('errors', [])) and attempt < 2:
            time.sleep(2 * (attempt + 1))
            continue
        return result
    raise SyncError('Shopify throttling limit reached')

def errors_message(result):
    return '; '.join(str(e.get('message', 'GraphQL query failed'))[:350] for e in result.get('errors', []))

def zip5(value):
    if not value:
        return None
    raw = str(value).strip()
    part = raw.split('-')[0]
    return part.zfill(5) if part.isdigit() and len(part) <= 5 else part

def sync():
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9-]*', os.getenv('SHOPIFY_SHOP', '').strip().removesuffix('.myshopify.com')):
        raise SyncError('Existing Shopify shop configuration is unavailable')
    shop, token = shopify_token()
    scopes_query = (ROOT / 'queries/scopes.graphql').read_text(encoding='utf-8')
    scope_response = graphql(shop, token, scopes_query)
    if scope_response.get('errors'):
        raise SyncError(errors_message(scope_response))
    scope_names = {s['handle'] for s in scope_response['data']['currentAppInstallation']['accessScopes']}
    if not {'read_orders', 'write_orders'} & scope_names:
        raise SyncError('Existing Shopify app does not have order read access')

    observed_at = iso_now()
    today = dt.datetime.now(UTC).date()
    since = today - dt.timedelta(days=59)
    until = today + dt.timedelta(days=1)
    search = f'created_at:>={since.isoformat()} created_at:<{until.isoformat()}'
    query = (ROOT / 'queries/logistics.graphql').read_text(encoding='utf-8')
    event_query = (ROOT / 'queries/fulfillment-events.graphql').read_text(encoding='utf-8')
    orders, after, address_access = [], None, True
    for page in range(100):
        response = graphql(shop, token, query, {'query': search, 'after': after})
        if response.get('errors'):
            message = errors_message(response)
            if address_access and any('shippingAddress' in str(e.get('path', [])) or 'shippingAddress' in e.get('message', '') or 'protected customer' in e.get('message', '').lower() for e in response['errors']):
                query = query.replace('shippingAddress { provinceCode zip }', '')
                address_access = False
                response = graphql(shop, token, query, {'query': search, 'after': after})
            if response.get('errors'):
                raise SyncError(errors_message(response))
        connection = response['data']['orders']
        orders.extend(connection['nodes'])
        if not connection['pageInfo']['hasNextPage']:
            break
        after = connection['pageInfo']['endCursor']
    else:
        raise SyncError('Order pagination exceeded the safe limit; snapshot was not replaced')

    history = read_history()['shipments']
    historical_ids = {s['id'] for s in history}
    previous = {}
    if OUTPUT.is_file():
        previous = {s['id']: s for s in json.loads(OUTPUT.read_text(encoding='utf-8')).get('shipments', [])}
    shipments, pending_orders, event_pages = {}, [], 0
    live_order_numbers = set()
    for order in orders:
        if order.get('test') or order.get('cancelledAt'):
            continue
        live_order_numbers.add(order['name'])
        destination = order.get('shippingAddress') or {}
        trackings = 0
        for fulfillment in order.get('fulfillments') or []:
            if fulfillment.get('status') == 'CANCELLED':
                continue
            infos = [t for t in fulfillment.get('trackingInfo', []) if t.get('number')]
            trackings += len(infos)
            relevant = [t for t in infos if 'fedex' in str(t.get('company', '')).lower().replace(' ', '') or str(t['number']).strip() in historical_ids]
            if not relevant:
                continue
            event_connection = fulfillment.get('events') or {'nodes': [], 'pageInfo': {}}
            raw_events = list(event_connection.get('nodes') or [])
            cursor = event_connection.get('pageInfo', {})
            for event_page in range(30):
                if not cursor.get('hasNextPage'):
                    break
                response = graphql(shop, token, event_query, {'id': fulfillment['id'], 'after': cursor['endCursor']})
                if response.get('errors'):
                    raise SyncError(errors_message(response))
                extra = response['data']['node']['events']
                raw_events.extend(extra['nodes'])
                cursor = extra['pageInfo']
                event_pages += 1
            else:
                raise SyncError('Event pagination exceeded the safe limit; snapshot was not replaced')
            events = sorted({e['id']: {k: e.get(k) for k in ('id', 'status', 'happenedAt', 'city', 'province', 'zip')} for e in raw_events}.values(), key=lambda e: e.get('happenedAt') or '')
            first_transit = next((e['happenedAt'] for e in events if e.get('status') == 'IN_TRANSIT'), None)
            last_delivered = next((e['happenedAt'] for e in reversed(events) if e.get('status') == 'DELIVERED'), None)
            located = next((e for e in reversed(events) if e.get('city') or e.get('province')), None)
            for info in relevant:
                tracking = str(info['number']).strip()
                old = previous.get(tracking, {})
                item = {
                    'id': tracking, 'order': order['name'], 'carrier': 'FEDEX',
                    'state': destination.get('provinceCode'), 'zipRaw': destination.get('zip'),
                    'zip': zip5(destination.get('zip')),
                    'orderCreatedAt': order.get('createdAt'),
                    'fulfillmentCreatedAt': fulfillment.get('createdAt'),
                    'fulfillmentUpdatedAt': fulfillment.get('updatedAt'),
                    'shopifyStatus': fulfillment.get('status'),
                    'displayStatus': fulfillment.get('displayStatus'),
                    'inTransitAt': fulfillment.get('inTransitAt') or first_transit,
                    'deliveredAt': fulfillment.get('deliveredAt') or last_delivered,
                    'estimatedDeliveryAt': fulfillment.get('estimatedDeliveryAt'),
                    'trackingFirstSeenAt': old.get('trackingFirstSeenAt') or observed_at,
                    'lastEventAt': events[-1].get('happenedAt') if events else None,
                    'latestLocation': {'city': located.get('city'), 'state': located.get('province'), 'zip': located.get('zip')} if located else None,
                    'events': events, 'eventScope': 'fulfillment',
                    'trackingCount': len(infos), 'fulfillmentQuantity': fulfillment.get('totalQuantity'),
                    'observedAt': observed_at, 'source': 'shopify',
                }
                # A tracking number can occur in updated fulfillment records; newest record wins.
                if tracking not in shipments or (item['fulfillmentUpdatedAt'] or '') > (shipments[tracking]['fulfillmentUpdatedAt'] or ''):
                    shipments[tracking] = item
        if trackings == 0:
            pending_orders.append({'order': order['name'], 'createdAt': order.get('createdAt'), 'state': destination.get('provinceCode'), 'zip': zip5(destination.get('zip'))})
    values = list(shipments.values())
    result = {
        'status': 'ready', 'source': 'shopify', 'apiVersion': API_VERSION,
        'syncedAt': observed_at, 'window': {'since': since.isoformat(), 'untilExclusive': until.isoformat()},
        'access': {'ordersReadable': True, 'allOrdersReadable': 'read_all_orders' in scope_names, 'addressReadable': address_access},
        'ordersRead': len(orders), 'shipments': values, 'ordersWithoutTracking': pending_orders,
        'historicalMatches': len(historical_ids & shipments.keys()),
        'historicalTotal': len(historical_ids),
        'historicalOrdersMatched': sum(s['order'] in live_order_numbers for s in history),
        'coverage': {field: sum(bool(s.get(field)) for s in values) for field in ['orderCreatedAt', 'fulfillmentCreatedAt', 'inTransitAt', 'deliveredAt', 'estimatedDeliveryAt', 'events', 'latestLocation']},
        'eventPaginationRequests': event_pages, 'writesPerformed': False,
    }
    # Store observations separately from events: observed time is not a carrier scan time.
    observation_path = ROOT / 'data' / 'logistics-observations.jsonl'
    with observation_path.open('a', encoding='utf-8') as handle:
        for shipment in values:
            handle.write(json.dumps({'tracking': shipment['id'], 'observedAt': observed_at, 'displayStatus': shipment['displayStatus'], 'inTransitAt': shipment['inTransitAt'], 'deliveredAt': shipment['deliveredAt']}, ensure_ascii=False) + '\n')
    atomic_json(OUTPUT, result)
    return {key: value for key, value in result.items() if key not in ('shipments', 'ordersWithoutTracking') } | {'shipmentCount': len(values), 'ordersWithoutTrackingCount': len(pending_orders)}

def main():
    try:
        print(json.dumps(sync(), ensure_ascii=True))
    except Exception as exc:
        if isinstance(exc, SyncError):
            detail = str(exc)
        elif isinstance(exc, urllib.error.URLError):
            detail = 'Shopify network request failed; check network permission or connectivity'
        else:
            detail = 'Shopify sync failed: ' + type(exc).__name__
        print(json.dumps({'status': 'error', 'message': detail, 'writesPerformed': False}, ensure_ascii=True))
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
