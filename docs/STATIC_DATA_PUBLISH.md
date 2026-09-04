# 静态数据发布

`public/data.js` 和 `public/runtime.js` 原先是空回退文件，真实数据仅由本机 Node 服务动态提供。直接把 `public/` 部署到 Pages 不会运行 Node / Python，也不会自动带上本地数据。

## 导出完整页面

运行已配置 Python 环境：

```powershell
python -B scripts/export_static.py
```

导出到 `dist/`，包含完整前端、物流与销量快照、日报/周报 HTML。保留真实读取时间；不包含 API 凭据、原始订单响应、观测日志、PDF 或预览截图。导出失败会保留上一份有效输出。静态页面不显示只能在本机使用的刷新按钮。

导出产物含真实业务数据，`dist/` 默认被 Git 忽略。此命令仅在本机生成文件，不上传，不改变仓库可见性。

## 接入现有 Pages 项目

当前站点为 `https://trov-work.pages.dev/`，Pages 从 GitHub 的 `public/` 发布。

选择将现有 GitHub 仓库设为私有后，可把本次 `dist/data.js`、`dist/runtime.js` 和 `dist/reports/` 同步到 `public/` 对应位置并提交 `main`。前端文件继续使用仓库中的源码。这样现有 Pages 构建命令 `exit 0`、输出目录 `public` 均不用修改。

若采用独立私有发布仓库，则推送整个 `dist/` 内容并将 Pages 连接该仓库，输出目录改为其根目录。不要将这些快照推送到公开仓库。

私有 GitHub 仅限制仓库访问，网站访问权限需要单独设置。定时工作流应在现有本地只读查询成功后运行导出、校验仓库可见性、提交并推送；不应把旧读取时间改成当前时间。

本次已实现导出与静态页面适配，私有仓库确认和数据上线尚未执行，定时发布尚未启用。
