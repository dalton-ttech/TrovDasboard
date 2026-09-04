# Cloudflare 与 GitHub 快照发布方案

当前使用 **Cloudflare Pages**，线上站点为 <https://trov-work.pages.dev/>。本地计算数据，GitHub 提交后触发静态发布，无需云端数据库。

用户已授权仓库保持公开，并公开真实业务快照和 HTML 报告。发布文件为 `public/data.js`、`public/runtime.js`、`public/reports/` 及 `public/_headers`；API 凭据、原始 API 响应和本地 `data/` 缓存继续被忽略，不上传。

## 部署参数

Cloudflare → Workers & Pages → Create application → Pages → Import an existing Git repository：

| 字段 | 填写或选择 |
| --- | --- |
| Git provider | GitHub |
| Repository | `dalton-ttech/TrovDasboard` |
| Project name | `trov-work`（现有项目） |
| Production branch | `main` |
| Framework preset | `None` |
| Build command | `exit 0` |
| Build output directory | `public` |
| Root directory | 留空，使用仓库根目录 |
| Environment variables | 无需填写 |

静态入口为 `public/index.html`，没有前端编译步骤。本机 `server.mjs` 和 Python 不会在 Pages 上运行。[静态 HTML 部署指南](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/)、[构建配置](https://developers.cloudflare.com/pages/configuration/build-configuration/)。

## 数据发布流程

本地运行现有 Shopify / Meta 只读查询和报告索引 → 执行 `python -B scripts/export_static.py` → 将 `dist/` 中的 `data.js`、`runtime.js`、`_headers` 和 `reports/` 复制至 `public/` → 提交并推送 GitHub `main` → Pages 自动部署。

具体复制、提交和推送命令见 [静态数据发布](STATIC_DATA_PUBLISH.md)。导出目录 `dist/` 继续被忽略，前端源码仍保存在 `public/`。不需要提交整个 `Trov_ADS` 项目。

Pages Git 集成会在连接的生产分支发生提交时触发部署。[Git 集成](https://developers.cloudflare.com/pages/get-started/git-integration/)。页面读取最新已发布的快照；打开页面和数字动画不会直接请求 Shopify / Meta。线上刷新入口会隐藏，本机仍可使用 `server.mjs` 更新及预览数据。

## 每日更新状态

静态导出与页面适配已经实现，**每日定时上传尚未启用**。当前按上述流程手动更新。后续本地定时流程需要电脑开机、Codex 运行且网络可用；电脑关闭时，线上继续展示最后一次成功发布的快照。

定时流程沿用现有日报生成和只读查询，不重复创建另一套日报任务。更新前核对快照日期、`status=ready`、只读标记、近 30 / 7 天窗口、昨日比较结果和报告完整性。失败时保留上一次成功发布及真实读取时间，不把旧数据标为当天新数据。
