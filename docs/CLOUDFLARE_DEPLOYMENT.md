# Cloudflare 与 GitHub 快照发布方案

当前选择 **Cloudflare Pages**。数据计算由本地完成，GitHub 提交后触发静态发布，Pages 可以直接托管本项目，无需云端数据库。

## 当前部署参数

进入 Cloudflare → Workers & Pages → Create application → Pages → Import an existing Git repository，连接 GitHub 后选择下列仓库。

| 字段 | 填写或选择 |
| --- | --- |
| Git provider | GitHub |
| Repository | `dalton-ttech/TrovDasboard` |
| Project name | 建议 `trov-dashboard`，若已占用则加后缀 |
| Production branch | `main` |
| Framework preset | `None` |
| Build command | `exit 0` |
| Build output directory | `public` |
| Root directory | 留空，使用仓库根目录 |
| Environment variables | 当前无需填写 |

本项目的静态入口是 `public/index.html`，没有前端编译步骤。以上命令按 Cloudflare 静态 HTML 部署方式配置。[静态 HTML 部署指南](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/)、[构建配置](https://developers.cloudflare.com/pages/configuration/build-configuration/)。

**当前 GitHub 仅有代码和空数据回退，因此这组参数先部署前端页面，不会带上本机的真实数字或报告。** 真实数据上线前，需要接入下述私有快照导出和同步流程。本机 `server.mjs` 和 Python 不会在这个静态部署中运行。

针对每日更新的内部 Dashboard，**可以用私有 GitHub 仓库存放 JSON 快照和 HTML 报告，无需云端数据库，也不必先接 R2**。GitHub 为文件保留版本，Cloudflare 负责页面访问；本地继续执行已验证的 Shopify / Meta 查询和报告流程。

## 推荐流程

本地 Codex 定时运行 → 读取 Shopify / Meta、索引已完成报告 → 校验快照 → 导出 JSON / HTML → 提交私有 GitHub → Cloudflare 自动构建发布。

Cloudflare Pages 连接 GitHub 后，可在仓库提交时自动构建与部署。[Git 集成](https://developers.cloudflare.com/pages/get-started/git-integration/)。

页面读取已经发布的快照，页面打开或数字动画本身不会触发 Shopify / Meta 查询。

## 对代码的影响

改动集中在数据交付层，前端布局、物流模型、投流指标及报告阅读器基本保留。

| 部分 | 处理方式 |
| --- | --- |
| 现有 Python 查询和报告流程 | 保留，在本地运行 |
| 前端页面和业务模型 | 基本保留，包括数字动效和趋势角标 |
| 新增快照导出步骤 | 将当前历史、物流、投流、归档分别导出成前端已使用的 `data.js`、`runtime.js` 及报告文件 |
| HTML 报告路径 | 保留 `/reports/daily或weekly/日期/report.html` |
| 云端刷新行为 | 浏览器读取最新已发布快照；本地 API 刷新入口在静态发布版本中隐藏 |
| 发布配置 | 当前按上表发布 `public`；接入私有快照后新增导出与构建校验 |

可以继续保留 `server.mjs` 供本机预览。正式静态构建应输出独立目录，不覆盖源代码中的空数据回退。将生成后的少量 JSON / HTML 纳入私有数据目录即可，不需要提交整个 `Trov_ADS` 项目或其原始 API 返回值。

## 私有数据位置

目前 `dalton-ttech/TrovDasboard` 是公开代码仓库，尚未上传业务数据。

最简方案是将现有仓库改为私有，代码和导出快照放在同一个仓库，Cloudflare 连接该私有仓库进行构建。这样不需要额外的跨仓库访问令牌。

如果代码需要继续公开，则新建私有数据仓库。在 Cloudflare 构建时使用仅有该仓库读取权限的服务端令牌拉取快照，或由本地将静态构建输出推送至私有发布仓库。令牌不会发送给浏览器。

私有 GitHub 仓库控制的是源码访问。部署网站还需要独立的登录保护，例如 Cloudflare Access，才能限制订单、运单及投流报告的访问范围。

## 每日任务与校验

- 定时读取应安排在太平洋日期结束后，日报仍由现有流程生成；不要重复创建第二套日报任务。
- 发布前验证快照日期、`status=ready`、只读标记、近 30 / 7 天窗口、昨日对比结果和报告文件完整性。
- 凭据只留在本地；只提交白名单 JSON / HTML，不提交原始客户资料、PDF、截图、调试日志和整个观测日志。
- 失败时保留上一次成功发布，保留真实的读取时间；不要把旧数据标为当天新数据。
- 本机任务需要电脑开机、Codex 运行且网络可用。电脑关闭时，线上仍显示上一次成功发布的快照。
- 每天的汇总和 HTML 适合这个方案；图片和大体积二进制文件不纳入日常 Git 提交。GitHub 有单文件及仓库体积方面的限制。[文件体积说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

当前提交已完成界面、比较计算和本地每日汇总保存。静态导出、私有仓库调整、定时上传和 Cloudflare 发布仍待接入；尚未改变仓库可见性，也未启用自动上传业务数据。
