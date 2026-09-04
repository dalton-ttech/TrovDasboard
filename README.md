# Trov Operations Workspace

移动端优先的 Trov 工作区：销量总览、Shopify 物流观测、运输时效，以及独立的投流日报 / 周报。使用原生 HTML / CSS / JavaScript，无前端构建依赖。

## 本机启动

```powershell
npm run dev
```

- Dashboard：<http://127.0.0.1:4173/>
- 手机 / 桌面预览：<http://127.0.0.1:4173/preview.html>

需要 Node.js 18+ 和 Python 3.10+。默认检测本机 Codex bundled Python，也可用 `TROV_PYTHON` 指定 Python 可执行文件。服务仅监听 `127.0.0.1`，其他设备不能直接访问这个地址。字体及用户提供的 Logo 保存在 `public/assets`。

**当前提交尚未部署到 Cloudflare。** 按本地计算、GitHub 每日同步快照的方式，选择 Cloudflare Pages。当前可先部署前端，真实数据的私有同步仍待接入；填写参数见 [Cloudflare 部署说明](docs/CLOUDFLARE_DEPLOYMENT.md)。

## 界面

- 顶部显示实时太平洋日期、时间，采用 `America/Los_Angeles`，自动切换 PDT / PST。
- 销量总览和物流实况共用标题、时间说明及日期选择样式，标题位于指标卡片外。
- 销量总览默认最近 30 个完整太平洋自然日，可切换近 7 天，截至昨日；与物流区间独立，仅显示上次读取时间。
- 每次打开或刷新总览，销售额、订单量和 ROAS 从 0 快速计数至当前值。复用本地 CountUp.js 2.9.0，时长 0.8 秒；切换投流区间也会播放，减少动态效果设置下直接显示最终值。
- 后台对比前一天的同长度滚动区间：提升显示红色向上角标，下降显示绿色向下角标，持平或数据缺失不显示角标。
- 日报 / 周报支持归档筛选、搜索和原始 HTML 阅读，不提供 PDF 下载。
- 底部导航：总览、物流、时效、投流、账号。

## 本地数据

复用相邻项目 `Trov_ADS` 的现有只读接入及已生成报告。可通过 `TROV_ADS_ROOT` 指定其位置；新电脑需要单独配置该项目及其 Python 依赖。此仓库不包含该项目或其凭据。

`SHOPIFY_SHOP`、`SHOPIFY_CLIENT_ID`、`SHOPIFY_CLIENT_SECRET`、`META_ACCESS_TOKEN` 由服务端使用，令牌不进入浏览器。打开页面读取上次成功快照，不自动请求店铺或广告平台。

```powershell
# 使用配置好的 Python 环境；导入历史表时需要 openpyxl
python -B scripts/extract_history.py "<工作簿完整路径>"
python -B scripts/shopify_logistics.py
python -B scripts/ads_overview.py
python -B scripts/report_catalog.py
```

「账号」页可手动读取 Shopify，报告中心可刷新归档。销量总览在服务端更新快照后重新打开页面即可看到新数据，没有前端刷新按钮。

| 本地文件 | 用途 |
| --- | --- |
| `data/history.json` | 原始 OMS 历史字段 |
| `data/shopify-logistics.json` | Shopify 物流快照 |
| `data/logistics-observations.jsonl` | 历次观测记录 |
| `data/ads-overview.json` | 近 30 / 7 天投流汇总 |
| `data/ads-overview-history/YYYY-MM-DD.json` | 每个太平洋日期实际计算的汇总，供次日比较 |
| `data/reports.json` | 已完成报告索引 |

公开仓库仅包含代码、字体和品牌素材，不包含订单、运单、真实报告、API 缓存或凭据。`data/` 已忽略；`public/data.js` 是空数据回退，本地服务从 `data/history.json` 动态提供相同 URL。新克隆没有业务数据，需配置来源后才能显示真实结果。

## 统计口径

投流销售额采用现有监测脚本的 `all_net_sales`（调整后不含税订单小计），订单量为 `all_orders`（非测试、未取消、已付款或部分退款订单）。ROAS 为 Meta A02 / A03 总归因购买价值 ÷ 总花费，属于 Meta 平台归因；无花费时显示 —。不累加日报 / 周报，也不平均广告 ROAS。

比较区间向前平移一个太平洋日期，例如 8 月 5 日—9 月 3 日对比 8 月 4 日—9 月 2 日。优先采用前一天保存的实际汇总，`comparison.basis=previous_day_snapshot`。首次缺少该快照时，重新查询前一天对应区间，标记为 `recomputed_previous_window`，不会将补算结果声称为昨天实际保存的数据。三项指标分别比较，前端只使用 `comparison.directions`，不展示差值或百分比。

Shopify 时间按 UTC 展示和计算。OMS 时区未确认，仓内耗时仅按同表原始时间差计算。运输状态优先使用 Shopify 观测；`FULFILLED` 不等于送达，历史送达与当前确认冲突时标为待核实。耗时仅采用完整、有效的时间戳，缺失和负值不参与。首次看到运单的系统时间与物流扫描时间分开保存。

查询采用 Shopify Admin API `2026-07`，只允许命名的 GraphQL query。订单、运输事件分页查询，失败保留成功快照。目的地仅读取州及邮编，不读取客户姓名、联系方式和街道地址。原始查询位于 `queries/`。

报告来自 `Trov_ADS/audits/automation/meta-shopify-daily` 和 `meta-shopify-weekly`，只纳入 `status=ready`、`writes_performed=false` 的完成产物。Dashboard 负责索引和呈现，既有工作流继续生成原始报告。详见 [REPORT_CENTER_PLAN.md](docs/REPORT_CENTER_PLAN.md)。

## 验证

```powershell
npm run check
python -B tests/test_ads_overview.py
# 需启动本地服务，并准备好真实快照、历史记录和报告来源
node scripts/verify_local.mjs
```

自动检查覆盖语法、物流状态优先级、时效、太平洋日期与夏令时切换、有效订单、合并 ROAS、比较窗口、计数动画及减少动态效果设置。本地集成检查核对历史数据保留、报告全文字节一致、PDF 路由关闭、私有文件访问及只读调用边界。

目录：`public/` 前端与品牌素材；`queries/` 查询；`scripts/` 本地适配；`tests/` 测试；`docs/` 方案；`data/` 未提交的本地数据；`server.mjs` 本地服务。
