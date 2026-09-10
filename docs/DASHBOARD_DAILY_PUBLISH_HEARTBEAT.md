# Trov Dashboard 每日统一发布 Harness

本文件是固定 Codex 任务执行 Trov Dashboard 数据发布的唯一运行规范。Heartbeat 只运行下列入口，不拆分其内部步骤，不自行指定日报或周报日期，也不创建新的任务、对话或自动安排。

```powershell
python -B scripts\run_daily_publish.py
```

## 安排

- 当前按中国标准时间每天 15:00 执行，对应美国太平洋夏令时当日 00:00。
- 电脑关机时允许错过运行；下次开机并触发时，入口会从线上最后一份有效日报之后开始补齐，默认最多补 31 天。
- 日报使用最近一个已经完整结束的太平洋自然日。
- 周报和日报在同一串行流程内生成。每次检查最近一个已经完整结束的周日，周报覆盖前一周周一至周日。
- 美国切换冬令时前，将本 Harness 与 Heartbeat 一并调整为中国标准时间 16:15，给太平洋自然日结束保留 15 分钟缓冲。

## 固定流程

入口必须完整执行以下流程：

1. 获取文件锁，确认 Git 已跟踪文件无本地修改，并从 `origin/main` 快进更新。
2. 检查最后一份有效日报，补齐截至最近完整太平洋自然日的缺失日期。
3. 检查最近完整周日对应的周报；缺失或无效时重新生成。
4. 在本机生成并校验每份报告的 HTML、PDF 和 PNG。正常成功时不打开图片做视觉审核。
5. 只读刷新 Shopify 物流、Shopify 销量及 Meta A02/A03 数据。不得向 Meta API 请求 A01。
6. 导出 Cloudflare Pages 静态站。公开目录只包含页面需要的 JS、HTTP headers 与报告 HTML；不上传源 JSON、PDF、PNG、凭证或客户明细。
7. 只暂存允许的公开文件，提交到 Git 并推送 `main`。
8. 等待 Cloudflare Pages 部署，并核对线上读取时间、日报、周报和报告页面。

## 完整性规则

- 报告窗口的 `shopify_end_exclusive` 必须已经过去。
- `data.json` 的 `generated_at_utc` 必须大于或等于该窗口结束时间。提前抓取的日报或周报即使 manifest 写着 `ready` 也无效，必须重跑。
- 报告必须保持 `writes_performed: false`，且 Meta 源数据只能包含 A02、A03；出现 A01 时拒绝发布。
- 日报长图必须为 1200 像素宽的连续移动端长图；周报预览必须为 1800 × 2400 的 3:4 图片；PDF 必须有有效文件头。
- 任一步骤失败都停止提交与部署，保留线上上一份有效快照，并报告失败阶段。不得伪造读取时间或把旧数据标记为最新。

## Heartbeat 回复

成功后必须在当前固定任务中呈现报告：

1. 始终呈现 `dailyReports` 中日期最新的日报。调用 `open_in_codex` 打开其 `publicHtml`，并在回复中提供可点击的 HTML 链接。
2. 仅当 `weeklyReport.reused=false`，即本次新生成、修复或补齐周报时，同样打开并链接周报 HTML；普通日期不要每天重复同一份周报。
3. 每份报告的 HTML 链接下方只写一行核心数据，直接使用入口返回的 `metrics`：`投流金额 $metaSpendUsd · 销量 shopifyUnitsSold 件 · ROAS metaRoas×`。ROAS 为 `null` 时显示 `—`。
4. “投流金额”是 A02/A03 Meta spend 合计；“销量”是相同报告窗口的 Shopify 商品件数；ROAS 是 A02/A03 Meta purchase value ÷ spend。不得改成订单数或 Dashboard 的滚动 7/30 日口径。
5. 最后简短列出：完整太平洋日期、销售/物流/报告读取时间、Git commit、Cloudflare 验证结果。没有新增提交时明确写“无需新提交”。

日报回复格式：

```text
日报 · YYYY-MM-DD
[查看日报 HTML](publicHtml)
投流金额 $0.00 · 销量 0 件 · ROAS 0.00×
```

本次有新周报时追加：

```text
周报 · YYYY-MM-DD—YYYY-MM-DD
[查看周报 HTML](publicHtml)
投流金额 $0.00 · 销量 0 件 · ROAS 0.00×
```

失败时只回复：失败阶段、简短错误、线上是否仍保留上一份有效快照、需要人工处理的唯一动作。不得输出 API 密钥、访问令牌、客户资料或完整原始响应。
