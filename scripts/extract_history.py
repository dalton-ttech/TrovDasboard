"""Read the supplied workbook and export logistics-only data for the local UI demo."""
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "历史表单.xlsx"
wb = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
ws = wb["1"]
rows = iter(ws.iter_rows(values_only=True))
headers = list(next(rows))

def string(value):
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()

def timestamp(value):
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    return str(value).strip()

shipments = []
for number, row in enumerate(rows, start=2):
    raw = dict(zip(headers, row))
    tracking = string(raw.get("追踪号"))
    if not tracking:
        continue
    cost = re.fullmatch(r"\s*([\d.]+)\s*([A-Za-z]+)\s*", string(raw.get("费用")) or "")
    zip_raw = string(raw.get("邮编"))
    order = string(raw.get("平台订单号"))
    shipments.append({
        "id": tracking,
        "order": order if (order or "").startswith("#") else "#" + (order or ""),
        "state": string(raw.get("州/省")),
        "zipRaw": zip_raw,
        "zip": (zip_raw or "").split("-")[0].zfill(5),
        "platform": string(raw.get("平台")),
        "carrier": string(raw.get("物流服务商")),
        "service": string(raw.get("物流产品")),
        "remote": string(raw.get("是否偏远")),
        "cost": float(cost.group(1)) if cost else None,
        "currency": cost.group(2).upper() if cost else None,
        "status": string(raw.get("物流状态")),
        "omsStatus": string(raw.get("单据状态")),
        "createdAt": timestamp(raw.get("创建时间")),
        "pickedAt": timestamp(raw.get("拣货时间")),
        "shippedAt": timestamp(raw.get("发货时间")),
        "quantity": raw.get("商品数量"),
        "sourceRow": number,
        "source": "oms",
    })

data = {
    "sourceFile": SOURCE.name,
    "sheet": "1",
    "snapshotDate": "2026-09-04",
    "timeBasis": "OMS original timestamp; timezone unspecified",
    "shipments": shipments,
}
out = ROOT / "data" / "history.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "rows": len(shipments),
    "uniqueTracking": len({s['id'] for s in shipments}),
    "statuses": dict(Counter(s['status'] for s in shipments)),
    "services": dict(Counter(s['service'] for s in shipments)),
    "remote": dict(Counter(s['remote'] for s in shipments)),
    "avgCost": sum(s['cost'] for s in shipments if s['cost'] is not None) / len(shipments),
    "active": [s for s in shipments if s['status'] != '派送成功'],
}, ensure_ascii=True, indent=2))
