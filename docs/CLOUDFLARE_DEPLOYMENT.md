# Cloudflare 部署方案

建议选择 **Workers + Static Assets**。Dashboard 既要呈现页面，也要读取 Shopify / Meta 汇总和私有报告，使用一个 Worker 管理页面与接口更直接。Workers 可把静态资源与服务端逻辑一起部署，并支持 Cron Triggers 等能力。[静态资源文档](https://developers.cloudflare.com/workers/static-assets/)、[Workers / Pages 能力对照](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/)。

## 当前边界

当前入口 `server.mjs` 使用本机 HTTP 服务、Python 子进程、本地缓存和相邻 `Trov_ADS` 文件。将仓库连接 Cloudflare 不会自动迁移这些依赖，不能把 `npm start` 直接当作 Worker 入口。

`public/` 可以作为静态前端，但仓库中的数据回退为空。单独部署它只会得到界面，真实销售、物流和报告需要完成云端适配。本次提交没有创建云资源、上传真实数据、配置密钥或部署线上站点。

## 实施结构

| 部分 | Cloudflare 方案 | 改动 |
| --- | --- | --- |
| 页面、字体、Logo | Worker Static Assets | `public/` 作为资源目录 |
| `/runtime.js`、`/data.js`、读取 API | Worker `fetch` 入口 | 读取云端快照，保留现有前端数据协议 |
| JSON 快照、原始 HTML 报告 | 私有 R2 bucket | 生成流程上传完成产物，Worker 校验后提供；保留报告 CSP |
| Shopify / Meta 凭据 | Workers Secrets | 服务端使用，不进入仓库和静态资源 |
| 内部访问 | Cloudflare Access | 在真实经营数据上线前限制授权用户访问 |
| 更新 | 既有流程，后续迁移云端调度 | 第一阶段复用已有计算口径，后续迁移自动读取 |

第一阶段保留已验证的 `Trov_ADS` 计算及报告生成流程，将完成的 JSON / HTML 同步到 R2。Worker 提供只读浏览，页面呈现快照的真实更新时间。原生成流程在本机关机时不会继续运行；如需全天更新，再将查询与生成流程迁到持续运行的云端任务。

第二阶段可将 Shopify / Meta 查询改写为 Worker 的 HTTP 请求，用 Cron Triggers 更新快照。必须保留 Pacific 完整自然日、有效订单、退款、加权 ROAS、物流状态冲突等口径。日报 / 周报完整生成流程另行迁移，简单指标查询不能代替原报告。

## 上线顺序

1. 创建 Worker `fetch` 入口和 Wrangler 配置，接入 Static Assets。
2. 配置私有 R2 和访问控制，将数据接口改为读取云端对象。
3. 为既有生成流程加入完成产物上传，失败保留上一份成功快照。
4. 将 GitHub `main` 连接 Workers Builds，完成本地检查和部署预检后发布。
5. 验证手机端、近 30 / 7 天切换、HTML 报告、未授权访问及更新时间。

Workers 和 Pages 都能承载静态页面；本项目选择 Workers 是为了后续的数据接口和定时更新，无需另建 Pages 项目。
