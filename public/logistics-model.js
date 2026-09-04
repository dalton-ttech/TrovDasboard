/* Source priority, UTC durations, and explicit data gaps. */
(() => {
  const time = value => value ? Date.parse(value) : NaN;
  const delivered = shipment => shipment.status === '派送成功';
  const labels = { DELIVERED: '派送成功', IN_TRANSIT: '运输中', OUT_FOR_DELIVERY: '派送中', ATTEMPTED_DELIVERY: '派送尝试', FAILURE: '配送异常', NOT_DELIVERED: '未能送达', DELIVERY_FAILED: '配送失败', FULFILLED: '状态待核实', UNKNOWN: '状态待核实' };
  function merge(history, snapshot) {
    const rows = new Map(history.map(s => [s.id, { ...s, isLive: false, historyStatus: s.status, cohortAt: s.createdAt }]));
    if (!snapshot || snapshot.status !== 'ready') return [...rows.values()];
    for (const live of snapshot.shipments) {
      const original = rows.get(live.id);
      const confirmed = Boolean(live.deliveredAt) || live.displayStatus === 'DELIVERED';
      rows.set(live.id, {
        id: live.id, order: live.order, carrier: live.carrier, platform: 'Shopify',
        service: null, remote: null, cost: null, currency: null, createdAt: null, pickedAt: null, shippedAt: null,
        ...original, ...live,
        state: live.state || original?.state || null, zip: live.zip || original?.zip || null, zipRaw: live.zipRaw || original?.zipRaw || null,
        quantity: original?.quantity ?? (live.trackingCount === 1 ? live.fulfillmentQuantity : null),
        status: confirmed ? '派送成功' : labels[live.displayStatus] ?? (['CONFIRMED', 'LABEL_PRINTED', 'LABEL_PURCHASED'].includes(live.displayStatus) ? null : '状态待核实'),
        isLive: true, source: 'shopify', historyStatus: original?.historyStatus ?? null,
        dataConflict: !confirmed && original?.historyStatus === '派送成功', cohortAt: live.orderCreatedAt || original?.createdAt,
      });
    }
    return [...rows.values()];
  }
  function age(s, now) {
    if (delivered(s) || s.dataConflict) return null;
    if (s.isLive) { const start = s.inTransitAt || s.fulfillmentCreatedAt; return start && Number.isFinite(time(start)) ? Math.max(0, Math.floor((time(now) - time(start)) / 86400000)) : null; }
    return s.shippedAt ? Math.max(0, Math.round((Date.parse(now.slice(0, 10) + 'T00:00:00Z') - Date.parse(s.shippedAt.slice(0, 10) + 'T00:00:00Z')) / 86400000)) : null;
  }
  function classify(s, now) {
    if (delivered(s)) return { level: 'DELIVERED', reason: s.isLive ? 'Shopify 已确认送达' : 'OMS 历史已送达' };
    if (s.dataConflict) return { level: 'REVIEW', reason: 'OMS 历史已送达，Shopify 尚无送达确认，请核实状态' };
    if (s.isLive && s.status === '状态待核实') return { level: 'REVIEW', reason: 'Shopify 当前状态不足以确认运输或送达，请核实状态' };
    if (!s.isLive) return s.status === '运输中' && age(s, now) > 10 ? { level: 'CRITICAL', reason: `距 OMS 发货 ${age(s, now)} 天，历史状态仍为运输中` } : { level: 'NORMAL', reason: '历史 OMS 快照' };
    if (['FAILURE', 'NOT_DELIVERED', 'DELIVERY_FAILED'].includes(s.displayStatus)) return { level: 'CRITICAL', reason: 'Shopify 返回配送失败状态' };
    const due = time(s.estimatedDeliveryAt), current = time(now);
    if (Number.isFinite(due) && current > due + 86400000) return { level: 'CRITICAL', reason: `超过 Shopify 预计送达 ${Math.floor((current - due) / 86400000)} 天，尚未确认送达` };
    if (Number.isFinite(due) && current > due) return { level: 'WARNING', reason: '已超过 Shopify 预计送达时间' };
    if (s.events?.length > 1 && Number.isFinite(time(s.lastEventAt)) && current - time(s.lastEventAt) > 172800000) return { level: 'WARNING', reason: '超过 48 小时没有新的 Shopify 运输事件' };
    if (Number.isFinite(due) && due - current <= 86400000) return { level: 'WATCH', reason: '预计 24 小时内送达' };
    return { level: 'NORMAL', reason: '暂无预警条件' };
  }
  function duration(s, start, end) {
    if (!s[start] || !s[end]) return null;
    const value = (time(s[end]) - time(s[start])) / 86400000;
    return Number.isFinite(value) && value >= 0 ? value : null;
  }
  function samples(rows, start, end) { return rows.filter(s => s.isLive && delivered(s)).map(s => duration(s, start, end)).filter(v => v !== null); }
  window.TrovLogistics = { merge, age, classify, delivered, duration, samples };
})();
