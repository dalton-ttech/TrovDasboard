/* Local Trov workspace. Shopify queries run on the server; credentials never reach the browser. */
(() => {
  'use strict';
  const DATA = window.TROV_DATA;
  const MODEL = window.TrovLogistics;
  let SYNC = window.TROV_RUNTIME?.logistics || null;
  let ALL = MODEL.merge(DATA.shipments, SYNC);
  let REPORTS = window.TROV_RUNTIME?.reports || { reports: [] };
  const ADS_OVERVIEW = window.TROV_RUNTIME?.adsOverview || null;
  const SERVER_AVAILABLE = window.TROV_RUNTIME?.serverAvailable === true;
  const DATA_UNPUBLISHED = !SERVER_AVAILABLE && SYNC?.status !== 'ready' && ADS_OVERVIEW?.status !== 'ready' && !DATA.shipments.length;
  let syncing = false;
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  const paths = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    box: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="M3 8v9l9 5 9-5V8M12 13v9M7.5 5.5l9 5"/>',
    chart: '<path d="M4 3v17h17M8 15l4-5 4 2 5-7"/>',
    data: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7"/>',
    arrow: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/>',
    bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 8h18s-3-1-3-8M10 20h4"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4M17 3v4M3 11h18M7 15h2M15 15h2"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.1"/>',
    warning: '<path d="M10.3 3.9 2 18.3A1.8 1.8 0 0 0 3.6 21h16.8a1.8 1.8 0 0 0 1.6-2.7L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v5m0 3v.1"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    truck: '<path d="M3 6h11v11H3zM14 10h4l3 4v3h-7"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    filter: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2" fill="currentColor"/><circle cx="15" cy="17" r="2" fill="currentColor"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V3H3v13h5"/>',
    external: '<path d="M14 3h7v7M21 3 10 14M10 4H4v16h16v-6"/>',
    pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.4"/>',
    file: '<path d="M14 2H5v20h14V7zM14 2v6h5M8 13h8M8 17h6"/>',
    shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    link: '<path d="m10 13 4-4M8 16l-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M14 8l2-2a4 4 0 1 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(1 0) scale(.9)"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 3M5 15a8 8 0 0 0 13 3"/>',
    globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
    archive: '<rect x="3" y="3" width="18" height="5" rx="1"/><path d="M5 8v13h14V8M10 12h4"/>',
    bag: '<path d="M5 7h14l2 14H3L5 7ZM8 8V6a4 4 0 0 1 8 0v2"/>',
  };
  const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.box}</svg>`;
  const stateNames = { AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California', CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia', HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa', KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey', NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina', SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont', VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming' };
  const navItems = [['overview', '总览', 'grid'], ['shipments', '包裹', 'box'], ['analytics', '分析', 'chart'], ['reports', '报告', 'file'], ['data', '数据', 'data']];
  const mobileNavLabels = { shipments: '物流', analytics: '时效', reports: '投流', data: '账号' };
  let adsPeriod = '30';
  const store = { page: 'overview', period: 'all', filter: 'active', query: '', state: '', remote: '', service: '', sort: 'priority', expandedFilters: false, chart: 'volume', analytics: SYNC ? 'delivery' : 'handling', reportKind: 'all', reportQuery: '', reportId: null };
  const dateValue = value => value ? Date.parse(value.substring(0, 10) + 'T00:00:00Z') : null;
  let snapshot = dateValue(SYNC?.syncedAt || DATA.snapshotDate);
  const observedAt = () => SYNC?.syncedAt || DATA.snapshotDate + 'T00:00:00Z';
  const daysOld = s => MODEL.age(s, observedAt());
  const isDelivered = MODEL.delivered;
  const alertFor = s => MODEL.classify(s, observedAt());
  const isCritical = s => alertFor(s).level === 'CRITICAL';
  const needsAttention = s => ['CRITICAL', 'WARNING', 'REVIEW'].includes(alertFor(s).level);
  const isActive = s => !isDelivered(s);
  const floatTime = value => value ? Date.parse(value.replace(' ', 'T') + 'Z') : null;
  const hours = (from, to) => from && to ? (floatTime(to) - floatTime(from)) / 3600000 : null;
  const money = value => value === null || !Number.isFinite(value) ? '—' : '$' + value.toFixed(2);
  const mean = list => list.length ? list.reduce((a, b) => a + b, 0) / list.length : null;
  const percentile = (list, p) => {
    if (!list.length) return null;
    const a = [...list].sort((x, y) => x - y), n = (a.length - 1) * p, lo = Math.floor(n);
    return a[lo] + ((a[lo + 1] ?? a[lo]) - a[lo]) * (n - lo);
  };
  const number = (value, precision = 1) => value === null || !Number.isFinite(value) ? '—' : value.toFixed(precision);
  const dateShort = value => value ? value.substring(5, 10).replace('-', '/') : '—';
  const remoteText = value => value === '否' ? '非偏远' : value || '—';
  const serviceText = value => value === 'FEDEX_HOME_DELIVERY' ? 'Home Delivery' : value === 'FEDEX_GROUND' ? 'Ground' : value || '—';
  const datePeriod = () => { const start = store.period === 'all' ? Math.min(snapshot, ...ALL.map(s => dateValue(s.cohortAt)).filter(Number.isFinite)) : snapshot - (Number(store.period) - 1) * 86400000; return new Date(start).toISOString().slice(5,10).replace('-','.') + ' – ' + new Date(snapshot).toISOString().slice(5,10).replace('-','.'); };
  const scoped = () => store.period === 'all' ? ALL : ALL.filter(s => dateValue(s.cohortAt) >= snapshot - (Number(store.period) - 1) * 86400000);
  const stamp = value => value ? new Date(value).toISOString().replace('T',' ').slice(0,16) + ' UTC' : '—';
  const sourceLabel = s => `<span class="source-label">${s.isLive ? 'Shopify' : '历史 OMS'}</span>`;
  const ageLabel = s => s.dataConflict ? '状态待核实' : isDelivered(s) ? (s.deliveredAt ? '已确认送达' : '送达时间未提供') : s.isLive ? (s.inTransitAt ? '观测运输起' : '发货信息建立起') : s.shippedAt ? 'OMS 发货起' : '尚无发货记录';
  const views = window.TrovWorkspace;
  const viewHelpers = { icon, escape, money, number, percentile, mean, sectionHeading, pageHeading, stamp, sourceLabel, statusBadge, MODEL, isDelivered, stateNames };
  function statusBadge(s) {
    const alert = alertFor(s);
    if (alert.level === 'REVIEW') return `<span class="badge review">${icon('info')}状态待核实</span>`;
    if (alert.level === 'CRITICAL') return `<span class="badge critical">${icon('warning')}${s.isLive ? '延误预警' : '历史异常'}</span>`;
    if (alert.level === 'WARNING') return `<span class="badge review">${icon('clock')}需要关注</span>`;
    if (isDelivered(s)) return `<span class="badge delivered"><i></i>已送达</span>`;
    if (s.status) return `<span class="badge transit"><i></i>${escape(s.status)}</span>`;
    return `<span class="badge pending"><i></i>${s.isLive ? '待运输' : '待发货'}</span>`;
  }

  function nav(mobile = false) {
    return `<nav class="${mobile ? 'bottom-nav' : 'desktop-nav'}" aria-label="${mobile ? '移动端' : '主'}导航">${navItems.map(([id, name, symbol]) => `<a href="#${id}" ${store.page === id ? 'aria-current="page"' : ''} class="nav-item ${store.page === id ? 'active' : ''}">${icon(symbol)}<span>${mobile ? mobileNavLabels[id] || name : name}</span>${id === 'shipments' && !DATA_UNPUBLISHED ? `<span class="nav-count">${ALL.filter(isActive).length}</span>` : ''}</a>`).join('')}</nav>`;
  }
  function header() {
    const alerts = ALL.filter(needsAttention).length;
    return `<header class="app-header"><div class="header-inner"><a class="brand official-brand" href="#overview" aria-label="Trov 首页"><img src="assets/trov-logo-transparent.png" alt="Trov" width="600" height="165"></a><span class="brand-divider"></span><span class="brand-caption">Workspace</span>${nav()}<div class="header-actions"><a class="demo-badge ${SYNC ? 'connected' : ''}" href="#data"><i></i>${DATA_UNPUBLISHED ? '数据待发布' : SYNC ? SERVER_AVAILABLE ? 'Shopify · 已接入' : 'Shopify · 已发布快照' : '历史快照 · DEMO'}</a><button class="icon-button notification" data-action="alerts" aria-label="查看 ${alerts} 票需关注包裹">${icon('bell')}${alerts ? '<b></b>' : ''}</button><a class="workspace-avatar" href="#data" aria-label="Trov 工作区数据">T</a></div></div></header>`;
  }

  function periodControl() {
    return `<label class="period-control">${icon('calendar')}<span>${datePeriod()}</span><select id="period" aria-label="${SYNC ? '按 Shopify 下单日期选择统计区间（UTC）' : '按 OMS 创建日期选择统计区间'}"><option value="all" ${store.period === 'all' ? 'selected' : ''}>全部已载入数据</option><option value="30" ${store.period === '30' ? 'selected' : ''}>近 30 天</option><option value="7" ${store.period === '7' ? 'selected' : ''}>近 7 天</option></select>${icon('down')}</label>`;
  }

  function pageHeading(eyebrow, title, subtitle, customActions) {
    const actions = customActions ?? (store.page === 'reports' ? `<span class="snapshot-date">${icon('globe')}America/Los_Angeles</span>` : store.page === 'data' ? '' : periodControl());
    return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${subtitle}</p></div><div class="heading-actions">${actions}</div></div>`;
  }

  function metrics(rows) {
    const active = rows.filter(isActive).length, delivered = rows.filter(isDelivered).length, attention = rows.filter(needsAttention).length;
    const samples = MODEL.samples(rows, 'fulfillmentCreatedAt', 'deliveredAt');
    return `<section class="metrics" aria-label="物流核心指标"><button class="metric" data-action="show-active"><div class="metric-top">${SYNC ? '未确认送达' : '待送达包裹'} ${icon('box')}</div><div class="metric-value">${active}<span>票</span></div><div class="metric-foot"><span class="small-dot blue"></span>${rows.filter(s => s.status === '运输中').length} 运输中 · ${rows.filter(s => !s.status).length} ${SYNC ? '待运输' : '待发货'}${rows.some(s => s.dataConflict) ? ' · ' + rows.filter(s => s.dataConflict).length + ' 待核实' : ''}</div></button><button class="metric" data-action="alerts"><div class="metric-top">需要关注 ${icon('warning')}</div><div class="metric-value ${attention ? 'red-text' : ''}">${attention}<span>票</span></div><div class="metric-foot">${attention ? `<span class="priority-text">${rows.filter(isCritical).length} 延误预警 · ${rows.filter(s => s.dataConflict).length} 状态待核实</span>` : '本统计区间暂无异常'}</div></button><button class="metric" data-action="show-delivered"><div class="metric-top">${SYNC ? '已确认送达' : '历史已送达'} ${icon('checkCircle')}</div><div class="metric-value">${delivered}<span>/ ${rows.length}</span></div><div class="metric-foot"><span class="small-dot green"></span>${SYNC ? 'Shopify' : '历史 OMS'} · 占比 ${rows.length ? (delivered / rows.length * 100).toFixed(1) : '0'}%</div></button>${SYNC ? `<button class="metric" data-action="delivery-analysis"><div class="metric-top">送达周期中位数 ${icon('clock')}</div><div class="metric-value">${number(percentile(samples, .5))}<span>天</span></div><div class="metric-foot">Fulfillment → Delivery · n=${samples.length}</div></button>` : `<button class="metric" data-action="cost"><div class="metric-top">平均运费 ${icon('archive')}</div><div class="metric-value money"><span>$</span>${number(mean(rows.filter(s => s.cost !== null).map(s => s.cost)),2)}</div><div class="metric-foot">USD · 历史 OMS</div></button>`}</section>`;
  }

  function alertBanner() {
    const alerts = sorted(ALL.filter(needsAttention));
    if (!alerts.length) return '';
    return `<div class="attention-banners">${alerts.slice(0,2).map(s => `<button class="alert-banner ${s.dataConflict ? 'review-banner' : ''}" data-detail="${s.id}"><span class="alert-symbol">${icon(s.dataConflict ? 'info' : 'warning')}</span><span class="alert-content"><span class="alert-heading">${s.dataConflict ? '历史状态与当前确认不一致' : '包裹需要优先跟进'}<span class="alert-code">${escape(s.order)}</span></span><span class="alert-description">${escape(alertFor(s).reason)}${store.period === 'all' ? '' : ' · 全部区间预警'}</span></span><span class="alert-cta">查看详情 ${icon('arrow')}</span></button>`).join('')}</div>`;
  }

  function sectionHeading(title, sub = '', action = '') {
    return `<div class="section-heading"><div><h2>${title}</h2>${sub ? `<p>${sub}</p>` : ''}</div>${action}</div>`;
  }
  function listRow(s, compact = false) {
    const age = daysOld(s), due = s.estimatedDeliveryAt ? stamp(s.estimatedDeliveryAt).slice(5,16) : '—';
    const note = s.isLive ? (s.dataConflict ? '历史 OMS：已送达' : '预计 ' + due + (s.estimatedDeliveryAt ? ' UTC' : '')) : serviceText(s.service);
    return `<button class="shipment-row ${isCritical(s) ? 'is-critical' : ''}" data-detail="${s.id}" aria-label="查看订单 ${s.order}，${s.state || '目的州未知'}，${s.status || (s.isLive ? '待运输' : '待发货')}"><span class="row-order"><span class="package-icon">${icon(isDelivered(s) ? 'checkCircle' : 'box')}</span><span><strong>${escape(s.order)}</strong><small class="tracking-number">${escape(s.id)}</small></span></span><span class="row-destination"><strong>${escape(s.state || '—')} <span>${escape(s.zip || '—')}</span></strong><small>${escape(stateNames[s.state] || s.state || '—')}</small></span><span class="row-status">${statusBadge(s)}<small>${escape(note)}</small></span><span class="row-age"><strong class="${isCritical(s) ? 'red-text' : ''}">${age === null ? '—' : age + '<span> 天</span>'}</strong><small>${ageLabel(s)}</small></span>${compact ? '' : `<span class="row-cost"><strong>${money(s.cost)}</strong><small>${remoteText(s.remote)}</small></span>`}<span class="row-chevron">${icon('chevron')}</span><span class="row-mobile-bottom"><span>${sourceLabel(s)} <span class="mobile-age">${s.dataConflict ? '需要人工核实' : isDelivered(s) ? (s.deliveredAt ? '送达 ' + stamp(s.deliveredAt).slice(5,10) : '送达时间未提供') : s.isLive ? '预计 ' + due + (s.estimatedDeliveryAt ? ' UTC' : '') : ageLabel(s) + (age === null ? '' : ' ' + age + ' 天')}</span></span>${icon('arrow')}</span></button>`;
  }

  function sorted(rows) {
    const rank = { CRITICAL:0, WARNING:1, REVIEW:2, WATCH:3, NORMAL:4, DELIVERED:5 };
    return [...rows].sort((a,b) => {
      if (store.sort === 'age') return (daysOld(b) ?? -1) - (daysOld(a) ?? -1);
      if (store.sort === 'cost') return (b.cost ?? 0) - (a.cost ?? 0);
      if (store.sort === 'newest') return dateValue(b.cohortAt) - dateValue(a.cohortAt);
      return rank[alertFor(a).level] - rank[alertFor(b).level] || dateValue(b.cohortAt) - dateValue(a.cohortAt);
    });
  }

  function table(rows, compact = false) {
    return `<div class="shipment-table ${compact ? 'compact' : ''}"><div class="table-head"><span>订单 / 运单号</span><span>目的地</span><span>状态</span><span>${SYNC ? '观测历时' : '发货后历时'}</span>${compact ? '' : '<span>运费</span>'}<span></span></div><div class="shipment-body">${rows.length ? rows.map(s => listRow(s, compact)).join('') : emptyState()}</div></div>`;
  }
  function emptyState() {
    return `<div class="empty-state">${icon('search')}<h3>没有找到匹配的包裹</h3><p>试试订单号、运单号或邮编，或调整筛选条件。</p><button class="button secondary" data-action="clear-filters">清除筛选</button></div>`;
  }
  function statusSummary(rows) {
    const delivered = rows.filter(isDelivered).length;
    const groups = [['已送达',delivered,'green','show-delivered'],['运输中',rows.filter(s=>['运输中','派送中'].includes(s.status)).length,'blue','show-transit'],[SYNC?'待运输':'待发货',rows.filter(s=>!s.status).length,'gray','show-pending']];
    if (SYNC) groups.push(['待核实',rows.filter(s=>s.dataConflict || s.status==='状态待核实').length,'amber','alerts']);
    return `<section class="panel status-panel">${sectionHeading('包裹状态', SYNC ? 'Shopify 最新读取状态' : '按历史快照统计')}<div class="delivery-summary"><span class="delivery-ratio">${number(rows.length?delivered/rows.length*100:0)}<span>%</span></span><span class="delivery-ratio-label">已送达占比<span>按全部已载入包裹统计</span></span></div><div class="status-track" role="img" aria-label="${groups.map(g=>g[0]+' '+g[1]+' 票').join('，')}">${groups.map((g,i)=>`<span style="flex:${g[1]}" class="${['delivered','transit','pending','review'][i]}-segment"></span>`).join('')}</div><div class="status-legend ${SYNC?'four-states':''}">${groups.map(([label,count,color,action])=>`<button data-action="${action}"><span><i class="small-dot ${color}"></i>${label}</span><strong>${count}<small>票</small></strong></button>`).join('')}</div><div class="panel-note">${icon('info')}${SYNC ? `${rows.filter(s=>s.deliveredAt).length} 票有 Shopify 送达时间` : '送达时间待 Shopify 数据补充'}</div></section>`;
  }

  function weeklyChart(rows, handling = false) {
    const min = store.period === 'all' ? dateValue('2026-07-20') : snapshot - (Number(store.period) - 1) * 86400000;
    const buckets = [];
    for (let start = min; start <= snapshot; start += 7 * 86400000) {
      const end = Math.min(start + 6 * 86400000, snapshot);
      const group = rows.filter(s => dateValue(s.createdAt) >= start && dateValue(s.createdAt) <= end);
      const samples = group.filter(s => s.createdAt && s.shippedAt);
      const value = handling ? percentile(samples.map(s => hours(s.createdAt, s.shippedAt)), .5) : group.length;
      buckets.push({ label: new Date(start).toISOString().substring(5, 10).replace('-', '/'), count: group.length, value: value ?? 0, samples: samples.length, end: new Date(end).toISOString().substring(5, 10).replace('-', '/') });
    }
    const max = Math.max(...buckets.map(b => b.value), handling ? 24 : 4);
    const limit = handling ? Math.ceil(max / 12) * 12 : Math.ceil(max / 4) * 4;
    return `<div class="chart-wrap"><div class="chart-scale"><span>${limit}</span><span>${limit / 2}</span><span>0</span></div><div class="bar-chart ${handling ? 'handling-chart' : ''}" role="img" aria-label="${handling ? '每周 OMS 仓内处理时间中位数，单位小时' : '每周 OMS 建单量，单位票'}">${buckets.map((b, i) => `<div class="chart-column"><div class="column-space"><div class="chart-bar ${i === buckets.length - 1 ? 'last' : ''}" style="--bar-height:${Math.max(0, b.value / limit * 100)}%" tabindex="0" aria-label="${b.label} 至 ${b.end}：${handling ? number(b.value) + ' 小时，样本 ' + b.samples : b.count + ' 票'}"><span class="bar-number">${handling ? number(b.value) : b.count}</span><span class="chart-tooltip">${b.label} – ${b.end}<br>${handling ? number(b.value) + ' 小时 · n=' + b.samples : b.count + ' 票建单'}</span></div></div><span class="x-label">${b.label}</span></div>`).join('')}</div></div>`;
  }
  function costGroups(rows) {
    return ['否', '偏远', '超偏远'].map(remote => {
      const group = rows.filter(s => s.remote === remote && s.cost !== null);
      return { name: remoteText(remote), count: group.length, avg: mean(group.map(s => s.cost)) };
    });
  }
  function costComparison(rows) {
    const groups = costGroups(rows);
    const max = Math.max(...groups.map(g => g.avg || 0));
    return `<div class="cost-comparison">${groups.map((g, i) => `<div class="cost-line"><div class="cost-label"><span>${g.name}<small>${g.count} 票</small></span><strong>${money(g.avg)}</strong></div><div class="cost-track"><span style="width:${max ? (g.avg || 0) / max * 100 : 0}%;--cost-color:var(--cost-${i})"></span></div></div>`).join('')}</div>`;
  }
  function coverageMini() {
    const coverage = SYNC?.coverage || {}, total = SYNC?.shipments.length || ALL.length;
    return `<section class="coverage-strip"><div class="coverage-intro">${icon('data')}<span><strong>数据完整度</strong><small>${SYNC ? 'Shopify · ' + stamp(SYNC.syncedAt).slice(5) : '当前来源：历史 OMS'}</small></span></div><div class="coverage-stat"><span>运单号</span><strong class="green-text">100%</strong></div><div class="coverage-stat"><span>预计送达</span><strong>${SYNC ? Math.round(coverage.estimatedDeliveryAt/total*100)+'%' : '—'}</strong></div><div class="coverage-stat"><span>运输事件</span><strong>${SYNC ? Math.round(coverage.events/total*100)+'%' : '—'}</strong></div><a href="#data" class="text-button">查看数据 ${icon('arrow')}</a></section>`;
  }

  function overview() {
    if (DATA_UNPUBLISHED) return `${pageHeading('WORKSPACE OVERVIEW', '数据尚未发布', '销量总览 · 实时物流', '')}<section class="panel delivery-empty" aria-labelledby="unpublished-title"><div class="empty-graphic">${icon('archive')}</div><h2 id="unpublished-title">等待第一份数据快照</h2><p>当前页面尚未载入销量和物流数据。<br>数据发布后，这里将显示实际指标与上次读取时间。</p></section>`;
    const rows = scoped(), active = sorted(rows.filter(isActive));
    return views.adsOverview({ snapshot: ADS_OVERVIEW, period: adsPeriod }, viewHelpers) + `${pageHeading('OPERATIONS OVERVIEW', '实时物流', SYNC ? '上次读取 ' + stamp(SYNC.syncedAt) : '快照截至 2026.09.04 · 历史 OMS')}${metrics(rows)}${alertBanner()}<div class="overview-grid"><section class="panel shipments-panel">${sectionHeading('待送达包裹 <span class="heading-count">' + active.length + '</span>', SYNC ? '异常优先 · Shopify 观测状态' : '异常优先 · 历史 OMS', '<button class="text-button" data-action="show-active">查看全部 ' + icon('arrow') + '</button>')}${table(active.slice(0, 5), true)}<div class="table-footer"><span>${active.length > 5 ? `展示 ${Math.min(active.length, 5)} / ${active.length} 票待送达包裹` : `共 ${active.length} 票待送达包裹`}</span><button class="text-button" data-action="show-active">打开包裹列表 ${icon('arrow')}</button></div></section>${statusSummary(rows)}<section class="panel activity-panel">${sectionHeading(store.chart === 'volume' ? '发货节奏' : '仓内处理', store.chart === 'volume' ? '按 OMS 创建日期分组 · 每周建单量' : 'OMS 创建 → 发货中位数 · 小时', '<div class="segmented"><button data-chart="volume" class="' + (store.chart === 'volume' ? 'selected' : '') + '">建单量</button><button data-chart="handling" class="' + (store.chart === 'handling' ? 'selected' : '') + '">仓内处理</button></div>')}${weeklyChart(rows, store.chart === 'handling')}<div class="chart-caption"><span><i class="small-dot blue"></i>${store.chart === 'volume' ? '历史建单量' : '仓内处理时间'}</span><span>末周截至 09.04</span></div></section><section class="panel cost-panel">${sectionHeading('运费分布', '按目的地偏远程度 · USD', '<button class="icon-button subtle" data-action="cost" aria-label="查看运费分析">' + icon('arrow') + '</button>')}${costComparison(rows)}<div class="panel-note">${icon('info')}仅包含 OMS 记录的历史运费</div></section></div>${coverageMini()}`;
  }
  function filtered() {
    let rows = scoped().filter(s => {
      if (store.filter === 'active' && !isActive(s)) return false;
      if (store.filter === 'critical' && !needsAttention(s)) return false;
      if (store.filter === 'delivered' && !isDelivered(s)) return false;
      if (store.filter === 'transit' && s.status !== '运输中') return false;
      if (store.filter === 'pending' && s.status) return false;
      if (store.state && s.state !== store.state) return false;
      if (store.remote && s.remote !== store.remote) return false;
      if (store.service && s.service !== store.service) return false;
      return !store.query || [s.order, s.id, s.zip, s.state, stateNames[s.state]].some(v => String(v || '').toLowerCase().includes(store.query.toLowerCase().trim()));
    });
    return sorted(rows);
  }
  function filtersMarkup() {
    const states = [...new Set(ALL.map(s => s.state))].sort();
    return `<div class="advanced-filters ${store.expandedFilters ? 'open' : ''}" id="advanced-filters"><label>目的州<select id="state-filter"><option value="">全部州</option>${states.map(s => `<option value="${s}" ${store.state === s ? 'selected' : ''}>${s} · ${stateNames[s] || s}</option>`).join('')}</select></label><label>偏远程度<select id="remote-filter"><option value="">全部地区</option>${['否', '偏远', '超偏远'].map(r => `<option ${store.remote === r ? 'selected' : ''} value="${r}">${remoteText(r)}</option>`).join('')}</select></label><label>物流服务<select id="service-filter"><option value="">全部服务</option>${['FEDEX_HOME_DELIVERY', 'FEDEX_GROUND'].map(s => `<option value="${s}" ${store.service === s ? 'selected' : ''}>${serviceText(s)}</option>`).join('')}</select></label><button class="text-button" data-action="clear-filters">重置筛选</button></div>`;
  }
  function shipmentsPage() {
    const rows = scoped(), results = filtered();
    const filters = [['active', '待送达', rows.filter(isActive).length], ['critical', '需关注', rows.filter(needsAttention).length], ['delivered', '已送达', rows.filter(isDelivered).length], ['all', '全部', rows.length]];
    if (['transit', 'pending'].includes(store.filter)) filters.splice(1, 0, [store.filter, store.filter === 'transit' ? '运输中' : SYNC ? '待运输' : '待发货', rows.filter(store.filter === 'transit' ? s => s.status === '运输中' : s => !s.status).length]);
    return `${pageHeading('SHIPMENT WORKSPACE', '包裹工作台', '从订单到目的地，按优先级跟进每一票。')}<section class="panel workspace-panel"><div class="workspace-tabs">${filters.map(([id, label, count]) => `<button class="filter-tab ${store.filter === id ? 'selected' : ''}" data-filter="${id}">${label}<span>${count}</span></button>`).join('')}<button class="text-button export-button" data-action="export">${icon('download')}导出</button></div><div class="toolbar"><label class="search-field">${icon('search')}<input id="shipment-search" type="search" placeholder="搜索订单、运单或邮编" aria-label="搜索订单号、运单号或邮编" value="${escape(store.query)}" autocomplete="off"><kbd>/</kbd></label><button class="button secondary filter-button ${store.expandedFilters || store.state || store.remote || store.service ? 'on' : ''}" data-action="toggle-filters" aria-expanded="${store.expandedFilters}" aria-controls="advanced-filters">${icon('filter')}筛选${[store.state, store.remote, store.service].filter(Boolean).length ? '<span class="filter-count">' + [store.state, store.remote, store.service].filter(Boolean).length + '</span>' : ''}</button><label class="sort-control"><span class="sr-only">排序</span><select id="sort"><option value="priority" ${store.sort === 'priority' ? 'selected' : ''}>异常优先</option><option value="newest" ${store.sort === 'newest' ? 'selected' : ''}>最新建单</option><option value="age" ${store.sort === 'age' ? 'selected' : ''}>发货历时最长</option><option value="cost" ${store.sort === 'cost' ? 'selected' : ''}>运费从高到低</option></select></label></div>${filtersMarkup()}<div id="results-region" aria-live="polite">${table(results)}<div class="table-footer"><span>共 ${results.length} 票包裹 · ${new Set(results.map(s => s.order)).size} 笔订单</span><span>${SYNC ? 'Shopify · ' + stamp(SYNC.syncedAt) : '状态截至 2026.09.04'}</span></div></div></section><div class="page-footnote">${icon('info')}${SYNC ? 'Shopify 时间以 UTC 展示；优先以进入运输时间计算历时，缺失时采用 Fulfillment 创建时间。状态冲突单独标注。' : '历史快照以 OMS 发货日期计算历时；已送达包裹不累计运输年龄。'}</div>`;
  }
  function analyticsPage() {
    const rows = scoped();
    const samples = rows.filter(s => s.createdAt && s.shippedAt);
    const durations = samples.map(s => hours(s.createdAt, s.shippedAt));
    const costs = rows.filter(s => s.cost !== null).map(s => s.cost);
    const tab = store.analytics;
    let content;
    if (tab === 'handling') {
      content = `<section class="analytics-metrics">${[['仓内处理 P50', number(percentile(durations, .5)), '小时', '50% 的样本在此时间内发货'], ['仓内处理 P75', number(percentile(durations, .75)), '小时', '75% 的样本在此时间内发货'], ['仓内处理 P90', number(percentile(durations, .9)), '小时', '90% 的样本在此时间内发货']].map(([title, value, unit, caption]) => `<div><span class="metric-label">${title}</span><strong>${value}<small>${unit}</small></strong><span class="metric-foot">${caption} · n=${samples.length}</span></div>`).join('')}</section><div class="analytics-grid"><section class="panel">${sectionHeading('仓内处理趋势', '每周 OMS 创建 → 发货中位数 · 小时')}${weeklyChart(rows, true)}<div class="chart-caption"><span><i class="small-dot blue"></i>历史 OMS</span><span>n=${samples.length} · 末周截至 09.04</span></div></section><section class="panel">${sectionHeading('处理环节', '各环节中位数 · OMS 原始时间')}<div class="process-steps">${[['创建 → 拣货', rows.filter(s => s.createdAt && s.pickedAt).map(s => hours(s.createdAt, s.pickedAt)), 'h'], ['拣货 → 发货', rows.filter(s => s.pickedAt && s.shippedAt).map(s => hours(s.pickedAt, s.shippedAt) * 60), 'min'], ['创建 → 发货', durations, 'h']].map(([label, values, unit], i) => `<div><span class="process-number">0${i + 1}</span><span>${label}<small>有效样本 ${values.length} 票</small></span><strong>${number(percentile(values, .5))}<small>${unit}</small></strong></div>`).join('')}</div><div class="panel-note">${icon('info')}仓内处理时间与承运商运输时间独立统计</div></section></div>`;
    } else if (tab === 'cost') {
      const groups = [...new Set(rows.map(s => s.state))].map(state => { const s = rows.filter(r => r.state === state); return { state, n: s.length, avg: mean(s.filter(r => r.cost !== null).map(r => r.cost)), delivered: s.filter(isDelivered).length }; }).sort((a, b) => b.n - a.n || a.state.localeCompare(b.state));
      content = `<section class="analytics-metrics">${[['平均运费', money(mean(costs)), 'USD', `${costs.length} 票有费用记录`], ['运费中位数', money(percentile(costs, .5)), 'USD', `P50 · n=${costs.length}`], ['历史运费合计', money(costs.reduce((a, b) => a + b, 0)), 'USD', '当前日期区间']].map(([title, value, unit, caption]) => `<div><span class="metric-label">${title}</span><strong>${value}<small>${unit}</small></strong><span class="metric-foot">${caption}</span></div>`).join('')}</section><div class="analytics-grid"><section class="panel state-panel">${sectionHeading('目的州分析', '按历史包裹数量排序 · 时效基线待补充')}<div class="state-table"><div class="state-head"><span>目的州</span><span>样本</span><span>平均运费</span><span>时效基线</span></div>${groups.map(g => `<button data-state-link="${g.state}" class="state-row"><span><strong>${g.state}</strong><small>${stateNames[g.state]}</small></span><span>${g.n}<small>票</small></span><strong>${money(g.avg)}</strong><span class="low-sample">样本不足</span></button>`).join('')}</div></section><div class="analytics-side"><section class="panel">${sectionHeading('偏远程度与运费', '原始费用 · USD')}${costComparison(rows)}<div class="panel-note">${icon('info')}原始物流服务类型分别保留</div></section><section class="panel">${sectionHeading('物流服务')}<div class="service-list">${['FEDEX_HOME_DELIVERY', 'FEDEX_GROUND'].map(service => { const group = rows.filter(s => s.service === service); return `<div><span>${serviceText(service)}<small>FedEx · ${group.length} 票</small></span><strong>${money(mean(group.filter(s => s.cost !== null).map(s => s.cost)))}</strong></div>`; }).join('')}</div></section></div></div>`;
    } else if (SYNC) {
      content = views.deliveryAnalytics({ rows, sync: SYNC }, viewHelpers);
    } else {
      content = `<section class="panel delivery-empty"><div class="empty-graphic">${icon('clock')}<span></span>${icon('checkCircle')}</div><div class="eyebrow">DELIVERY PERFORMANCE</div><h2>让真实的运输数据，给出答案。</h2><p>历史表单记录了送达状态，但没有送达时间。<br>接入 Shopify 后，有效样本将用于时效分析。</p><div class="missing-metrics">${['Fulfillment → Delivery', 'Observed Transit', '准时送达率'].map(label => `<div><span>${label}</span><strong>—</strong><small>有效样本 0 / ${rows.length}</small></div>`).join('')}</div><a href="#data" class="button primary">查看数据覆盖 ${icon('arrow')}</a><p class="empty-fineprint">州级时效基线需至少 5 个有效样本。</p></section>`;
    }
    return `${pageHeading('PERFORMANCE & INSIGHTS', '物流分析', '从已知数据出发，看清效率与成本。')}<div class="analysis-tabs" role="group" aria-label="分析维度">${[['handling', '仓内处理'], ['cost', '运费与目的地'], ['delivery', '运输时效']].map(([id, name]) => `<button data-analysis="${id}" class="${tab === id ? 'selected' : ''}" aria-pressed="${tab === id}">${name}</button>`).join('')}</div>${content}<div class="page-footnote">${icon('info')}${SYNC ? '统计区间按 Shopify 下单日期（UTC）筛选。运输时效仅计算有效时间样本；OMS 仓内处理独立统计。' : '统计区间按 OMS 创建日期筛选；仓内耗时按同表原始时间差计算。'}</div>`;
  }
  function dataPage() {
    return views.dataPage({ sync: SYNC, history: DATA, rows: ALL, syncing, reports: REPORTS, serverAvailable: SERVER_AVAILABLE }, viewHelpers);
  }

  function footer() {
    return `<footer class="app-footer"><span><img class="footer-logo" src="assets/trov-logo-transparent.png" alt="Trov"> Operations Workspace</span><span>${DATA_UNPUBLISHED ? '等待数据发布' : store.page==='reports' ? 'Meta × Shopify · 投流报告' : SYNC ? 'Shopify · '+stamp(SYNC.syncedAt) : '历史快照 · '+DATA.snapshotDate}</span></footer>`;
  }
  let returnFocus = null;
  let reportSizeObserver = null;

  function render(keepScroll = false) {
    reportSizeObserver?.disconnect();
    const oldScroll = window.scrollY;
    const route = location.hash.slice(1) || 'overview';
    const page = route.startsWith('report/') ? 'reports' : route;
    store.reportId = route.startsWith('report/') ? route.slice(7) : null;
    store.page = navItems.some(([id]) => id === page) ? page : 'overview';
    document.title = `Trov · ${{ overview: '实时物流', shipments: '包裹工作台', analytics: '物流分析', data: '数据与来源', reports: '投流报告' }[store.page]}`;
    $('#app').innerHTML = `${header()}<main id="main" class="main-container" tabindex="-1"><div class="time-strip"><time class="pacific-clock" data-pacific-clock aria-label="当前太平洋日期与时间"><span class="pacific-date" data-pacific-date></span><span class="pacific-time"><strong data-pacific-time></strong><small data-pacific-zone></small></span></time></div>${({ overview, shipments: shipmentsPage, analytics: analyticsPage, data: dataPage, reports: () => views.reportsPage({ catalog: REPORTS, kind: store.reportKind, query: store.reportQuery, reportId: store.reportId, serverAvailable: SERVER_AVAILABLE }, viewHelpers) })[store.page]() }${footer()}</main>${nav(true)}`;
    window.TrovClock.update(document);
    window.TrovAdsMotion.mount(document, store.page === 'overview' ? `${adsPeriod}:${ADS_OVERVIEW?.syncedAt || ''}` : null, { replay: !keepScroll });
    bind();
    bindWorkspace();
    if (keepScroll) window.scrollTo(0, oldScroll);
  }
  function go(page) {
    if (location.hash === '#' + page) render();
    else location.hash = page;
  }
  function openList(filter) {
    store.filter = filter;
    store.query = store.state = store.remote = store.service = '';
    if (filter === 'critical') store.period = 'all';
    go('shipments');
  }
  function resetFilters() {
    store.query = store.state = store.remote = store.service = '';
    store.filter = 'all';
    render(true);
  }
  function bind() {
    $$('[data-detail]').forEach(el => el.addEventListener('click', () => openDetail(el.dataset.detail, el)));
    $$('[data-filter]').forEach(el => el.addEventListener('click', () => { store.filter = el.dataset.filter; render(true); }));
    $$('[data-chart]').forEach(el => el.addEventListener('click', () => { store.chart = el.dataset.chart; render(true); }));
    $$('[data-analysis]').forEach(el => el.addEventListener('click', () => { store.analytics = el.dataset.analysis; render(true); }));
    $$('[data-state-link]').forEach(el => el.addEventListener('click', () => { store.state = el.dataset.stateLink; store.filter = 'all'; store.query = store.remote = store.service = ''; go('shipments'); }));
    $$('[data-action]').forEach(el => el.addEventListener('click', () => {
      const action = el.dataset.action;
      if (action.startsWith('show-')) return openList(action.substring(5));
      if (action === 'alerts') return openList('critical');
      if (action === 'delivery-analysis') { store.analytics = 'delivery'; return go('analytics'); }
      if (action === 'cost') { store.analytics = 'cost'; return go('analytics'); }
      if (action === 'toggle-filters') { store.expandedFilters = !store.expandedFilters; render(true); }
      if (action === 'clear-filters') resetFilters();
      if (action === 'export') exportCsv();
    }));
    $('#period')?.addEventListener('change', event => { store.period = event.target.value; render(true); });
    for (const [id, key] of [['state-filter', 'state'], ['remote-filter', 'remote'], ['service-filter', 'service'], ['sort', 'sort']]) {
      $('#' + id)?.addEventListener('change', event => { store[key] = event.target.value; render(true); });
    }
    $('#shipment-search')?.addEventListener('input', event => {
      store.query = event.target.value;
      const rows = filtered();
      $('#results-region').innerHTML = table(rows) + `<div class="table-footer"><span>共 ${rows.length} 票包裹 · ${new Set(rows.map(s => s.order)).size} 笔订单</span><span>${SYNC ? 'Shopify · ' + stamp(SYNC.syncedAt) : '状态截至 2026.09.04'}</span></div>`;
      $$('[data-detail]', $('#results-region')).forEach(el => el.addEventListener('click', () => openDetail(el.dataset.detail, el)));
      $('[data-action="clear-filters"]', $('#results-region'))?.addEventListener('click', resetFilters);
    });
  }
  function timelineEntry(title, time, note, kind = '') {
    return `<li class="timeline-entry ${kind}"><span class="timeline-node">${time ? icon('check') : ''}</span><div class="timeline-entry-content"><strong>${title}</strong><time>${time ? escape(time.substring(0, 16)) : '—'}</time><p>${note}</p></div></li>`;
  }
  function openDetail(id, trigger) {
    const s = ALL.find(row => row.id === id);
    if (!s) return;
    returnFocus = trigger;
    const age = daysOld(s);
    const orderShipments = ALL.filter(row => row.order === s.order);
    $('#detail-root').innerHTML = `<div class="detail-backdrop"></div><aside class="detail-panel" role="dialog" aria-modal="true" aria-labelledby="detail-title"><div class="detail-top"><span class="eyebrow">SHIPMENT DETAILS</span><button class="icon-button close-detail" aria-label="关闭包裹详情">${icon('close')}</button></div><div class="detail-header"><span class="detail-package-icon">${icon('box')}</span><div><h2 id="detail-title">订单 ${escape(s.order)}</h2><span>${orderShipments.length} 票包裹 · ${s.quantity ?? '—'} 件商品</span></div>${statusBadge(s)}</div><div class="tracking-copy"><span><small>TRACKING NUMBER</small><strong>${escape(s.id)}</strong></span><button class="icon-button" id="copy-tracking" aria-label="复制运单号">${icon('copy')}</button></div>${orderShipments.length > 1 ? `<div class="sibling-shipments">${orderShipments.map(item => `<button data-sibling="${item.id}" class="button secondary">${item.id}</button>`).join('')}</div>` : ''}${isCritical(s) ? `<div class="detail-alert">${icon('warning')}<div><strong>历史状态需要核实</strong><p>截至 2026.09.04，距 OMS 发货已 ${age} 个日历日，历史快照仍为运输中。此为历史预警，当前状态待核实。</p></div></div>` : ''}<section class="detail-section"><h3>配送信息</h3><div class="route-summary"><span><small>发货地</small><strong>CA</strong><span>California</span></span><div class="route-line">${icon('truck')}</div><span><small>目的地</small><strong>${escape(s.state)}</strong><span>${escape(stateNames[s.state])} · ${escape(s.zip)}</span></span></div><dl class="detail-fields"><div><dt>物流服务</dt><dd>FedEx ${serviceText(s.service)}</dd></div><div><dt>原始服务类型</dt><dd class="raw-service">${escape(s.service)}</dd></div><div><dt>历史运费</dt><dd>${money(s.cost)} <span>USD</span></dd></div><div><dt>偏远程度</dt><dd>${remoteText(s.remote)}</dd></div><div><dt>预计送达 · Shopify</dt><dd>—</dd></div><div><dt>最近观测位置 · Shopify</dt><dd>—</dd></div><div><dt>状态来源</dt><dd>历史 OMS · 09.04 快照</dd></div></dl></section><section class="detail-section timeline-section"><div class="section-heading"><h3>包裹时间线</h3><span class="source-label">原始 OMS 时间</span></div><ol class="timeline">${timelineEntry('OMS 创建', s.createdAt, '历史 OMS · 建立出库记录')}${timelineEntry('OMS 拣货', s.pickedAt, s.pickedAt ? '历史 OMS · 仓内拣货完成' : '历史表单暂无记录', !s.pickedAt ? 'unavailable' : '')}${timelineEntry('OMS 发货', s.shippedAt, s.shippedAt ? '历史 OMS · 系统发货记录' : '历史表单暂无记录', !s.shippedAt ? 'unavailable' : '')}${timelineEntry(isDelivered(s) ? '历史快照：派送成功' : 'Shopify 运输与送达', null, isDelivered(s) ? '仅有状态，送达时间未提供。' : '尚未接入 · 暂无可展示的运输事件', 'unavailable')}</ol><p class="detail-caption">OMS 发货时间不代表承运商揽收时间。时区待确认，按源表原样展示。</p></section><section class="detail-section"><h3>时间效率</h3><div class="duration-list"><div><span>OMS 创建 → 发货</span><strong>${number(hours(s.createdAt, s.shippedAt))} ${s.shippedAt ? '<small>小时</small>' : ''}</strong></div><div><span>Order → Fulfillment</span><strong>—</strong></div><div><span>Fulfillment → Delivery</span><strong>—</strong></div><div><span>Observed Transit</span><strong>—</strong></div></div><p class="detail-caption">Shopify 时间字段待补充，缺失值不参与时效计算。</p></section><div class="detail-bottom"><a class="button primary" href="https://www.fedex.com/fedextrack/?trknbr=${encodeURIComponent(s.id)}" target="_blank" rel="noopener noreferrer">在 FedEx 官网查询 ${icon('external')}</a><p>将打开承运商网站，自行核实最新状态。</p></div></aside>`;
    if (s.isLive) $('#detail-root').innerHTML = views.liveDetail({ shipment: s, sync: SYNC, alert: alertFor(s) }, viewHelpers);
    document.body.classList.add('detail-open');
    $('#app').inert = true;
    $('.close-detail').focus();
    $('.close-detail').addEventListener('click', closeDetail);
    $('.detail-backdrop').addEventListener('click', closeDetail);
    $$('[data-sibling]').forEach(el => el.addEventListener('click', () => openDetail(el.dataset.sibling, returnFocus)));
    $('#copy-tracking').addEventListener('click', async () => {
      try {
        if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(s.id);
        else { const input = document.createElement('textarea'); input.value = s.id; $('.detail-panel').append(input); input.select(); const copied = document.execCommand('copy'); input.remove(); if (!copied) throw new Error('copy failed'); }
        toast('运单号已复制');
      } catch { toast('复制失败，请长按运单号选择并复制'); }
    });
  }
  function closeDetail() {
    $('#detail-root').innerHTML = '';
    document.body.classList.remove('detail-open');
    $('#app').inert = false;
    returnFocus?.focus();
  }
  let toastTimer;
  function toast(message) {
    clearTimeout(toastTimer);
    $('#toast').textContent = message;
    $('#toast').classList.add('visible');
    toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 3000);
  }
  function exportCsv() {
    const rows = filtered();
    const csvCell = value => '"' + String(value ?? '').replace(/^[=+@-]/, "'$&").replace(/"/g, '""') + '"';
    const columns = [['订单号', s => s.order], ['运单号', s => s.id], ['州', s => s.state], ['ZIP5', s => s.zip], ['物流状态', s => s.status || ''], ['OMS 单据状态', s => s.omsStatus], ['物流服务', s => s.service], ['费用 USD', s => s.cost], ['偏远程度', s => remoteText(s.remote)], ['OMS 创建时间', s => s.createdAt], ['OMS 发货时间', s => s.shippedAt], ['状态来源', s => s.isLive ? 'Shopify' : '历史 OMS'], ['数据读取时间', () => observedAt()]];
    const csv = '\uFEFF' + [columns.map(([name]) => csvCell(name)).join(','), ...rows.map(s => columns.map(([, fn]) => csvCell(fn(s))).join(','))].join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a'); a.href = url; a.download = 'trov-shipments-2026-09-04.csv'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast(`已导出当前筛选的 ${rows.length} 票包裹`);
  }

  function bindWorkspace() {
    $('#ads-period')?.addEventListener('change', event => { adsPeriod = event.target.value; render(true); $('#ads-period')?.focus({ preventScroll: true }); });
    $$('[data-report-kind]').forEach(el => el.addEventListener('click', () => { store.reportKind = el.dataset.reportKind; render(true); }));
    $('#report-search')?.addEventListener('input', event => {
      store.reportQuery = event.target.value;
      $('#report-archive').innerHTML = views.reportArchive(REPORTS.reports || [], store.reportKind, store.reportQuery, viewHelpers);
    });
    $('[data-sync-shopify]')?.addEventListener('click', syncShopify);
    $('[data-refresh-reports]')?.addEventListener('click', async () => {
      if (!SERVER_AVAILABLE) return;
      try { const res = await fetch('/api/reports'); if (!res.ok) throw new Error(); REPORTS = await res.json(); render(true); toast('报告索引已更新'); }
      catch { toast('无法更新报告索引，保留已载入报告'); }
    });
    const frame = $('.report-document');
    if (frame) {
      const resize = () => {
        try {
          const doc = frame.contentDocument;
          if (!doc?.body) return;
          frame.style.height = '1px';
          frame.style.height = Math.max(600, doc.documentElement.scrollHeight, doc.body.scrollHeight) + 'px';
        } catch {}
      };
      frame.addEventListener('load', () => {
        resize();
        try {
          frame.contentDocument.fonts?.ready.then(resize);
          frame.contentDocument.querySelectorAll('img').forEach(img => { if (!img.complete) img.addEventListener('load', resize, { once: true }); });
        } catch {}
      });
      let lastWidth = 0;
      reportSizeObserver = new ResizeObserver(entries => {
        const width = entries[0].contentRect.width;
        if (width !== lastWidth) { lastWidth = width; resize(); }
      });
      reportSizeObserver.observe(frame.parentElement);
    }
  }
  async function syncShopify() {
    if (!SERVER_AVAILABLE) return;
    if (syncing) return;
    syncing = true; render(true);
    try {
      const response = await fetch('/api/logistics/sync', { method: 'POST', headers: { 'X-Trov-Request': 'local' } });
      if (!response.ok) throw new Error('启动同步失败');
      for (let i=0; i<125; i++) {
        await new Promise(resolve => setTimeout(resolve,2000));
        const status = await (await fetch('/api/logistics/sync-status')).json();
        if (status.status === 'error') throw new Error(status.message);
        if (status.status === 'ready') {
          const next = await (await fetch('/api/logistics')).json();
          if (next.status !== 'ready') throw new Error('尚无新的成功数据');
          SYNC = next; ALL = MODEL.merge(DATA.shipments, SYNC); snapshot = dateValue(SYNC.syncedAt);
          toast('Shopify 物流数据已更新'); return;
        }
      }
      throw new Error('同步仍在进行，请稍后刷新页面查看');
    } catch (error) { toast(error.message || '同步失败，保留上次成功数据'); }
    finally { syncing = false; render(true); }
  }
  window.addEventListener('hashchange', () => { closeDetail(); render(); window.scrollTo(0, 0); });
  document.addEventListener('keydown', event => {
    const panel = $('.detail-panel');
    if (event.key === 'Escape' && panel) closeDetail();
    if (event.key === 'Tab' && panel) {
      const focusable = $$('a[href], button, input, select, summary, [tabindex="0"]', panel);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    if (event.key === '/' && !panel && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
      event.preventDefault();
      if (store.page !== 'shipments') { go('shipments'); setTimeout(() => $('#shipment-search')?.focus(), 80); }
      else $('#shipment-search')?.focus();
    }
  });
  render();
  setInterval(() => window.TrovClock.update(document), 1000);
})();
