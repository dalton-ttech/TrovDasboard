# 静态数据发布

站点为 <https://trov-work.pages.dev/>，Pages 从公开仓库 `dalton-ttech/TrovDasboard` 的 `main` 分支发布 `public/`。用户已明确授权真实业务数据和 HTML 报告公开，无需调整仓库可见性。

Pages 不运行本机 Node / Python，也不会直接访问本地 `data/`。因此必须把成功快照导出并提交到前端目录；只提交前端源码不会更新线上数字。

## 导出并上传

在项目根目录、已配置的 Python 环境中执行：

```powershell
python -B scripts/export_static.py
if ($LASTEXITCODE -ne 0) { throw '静态导出失败，停止发布' }

Copy-Item -LiteralPath .\dist\data.js, .\dist\runtime.js, .\dist\_headers -Destination .\public -Force
New-Item -ItemType Directory -Path .\public\reports -Force | Out-Null
Copy-Item -Path .\dist\reports\* -Destination .\public\reports -Recurse -Force

git add public/data.js public/runtime.js public/_headers public/reports
git commit -m "Update dashboard data snapshots and reports"
git push origin HEAD:main
```

导出目录 `dist/` 包含完整前端、物流与销量快照，以及日报 / 周报 HTML。上述步骤只把数据文件、缓存响应头和报告复制至 `public/`；前端源码保持在原有位置。`dist/` 继续被 Git 忽略。

Pages 保持构建命令 `exit 0`、输出目录 `public`、生产分支 `main`。推送成功后由 Pages Git 集成触发发布，完成后线上页面读取新快照。页面打开和数字动画不会触发 Shopify / Meta 请求。

## 发布范围

- 公开发布：`public/data.js`、`public/runtime.js`、`public/reports/` 下的完整 HTML，以及 `public/_headers`。
- 继续留在本机：API 凭据、原始 API 响应、本地 `data/` 缓存、观测日志、PDF 和预览截图。
- 保留真实读取时间，导出失败保留上一份有效输出，不把旧快照标记为刚读取。
- 静态页面隐藏只能在本机使用的刷新入口；需要更新源数据时，先在本地运行既有只读查询和报告索引流程，再执行上述导出与上传。

每日定时上传尚未启用；目前按以上步骤手动发布。本地定时流程接入后仍应先完成查询和导出，再提交生成文件。
