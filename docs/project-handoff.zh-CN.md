# Nyaru-Clipper 项目交接

核验日期：**2026-10-16，Asia/Shanghai**。本页为当前交接入口；历史快照保留当时的状态，不代表当前 HEAD、安装版或服务状态。

## 本次发布与分支边界

用户授权将“顶部选项＋右侧抽屉”提交并推送到以下两个开发分支，**master 不动**。实现、测试及双语使用／验收文档随功能提交发布，当前交接与历史快照位于其后的文档提交。

| 开发分支 | 本次功能提交（交接文档提交之前） | 工作目录 |
| --- | --- | --- |
| `codex/local-companion-web` | `cf2cfd0fefc2bd3f7e9925fb5f2be747c088daaa` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` |
| `codex/local-companion-macos` | `b0dee61d4112a2ce965dec9d92a779ca0b8e2361` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` |

两分支使用显式 refspec 原子推送；不会推送主目录的 `feat/arctime-pro-plugin` 或其他分支。本地／远程 `master` 基线均为 `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`，未合并。主目录仍为旧工作站源码与文档，其余未提交工作保留。

仓库地址为 [Nyaruverse/nyaru-clipper](https://github.com/Nyaruverse/nyaru-clipper)，origin 为 `https://github.com/Nyaruverse/nyaru-clipper.git`。10 月 15 日完成转移，历史账号权限记录见快照；不要把旧权限查询当作永久权限。

最终分支 HEAD 包含当前交接提交，因此不要把上表功能提交误作最终 HEAD。接手时现场核验：

```bash
git ls-remote origin refs/heads/codex/local-companion-web refs/heads/codex/local-companion-macos refs/heads/master
git -C /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper status --short
git -C /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper status --short
```

本地精确推送回执在 macOS 工作树 `.omo/evidence/toolbar-drawer-2026-10-16/publish-receipt.json`，不进入 Git。此交接记录开发分支源码发布，不代表 Developer ID／公证／公开安装包发布。

## 当前界面与本机安装

顶部六个入口为「新建任务」「切片方式」「字幕样式」「AI 设置」「任务记录」「导出」。初始收起；点击展开右侧抽屉，再点同一入口收起；切换仅显示一项。关闭按钮与 Escape 也可收起并返回键盘焦点。表单保持挂载，链接／时间段、本地录像选择、字幕模板和供应商草稿在切换时保留。

创建与切片共用提交表单，必填项校验会定位对应分区。桌面抽屉位于视频右侧并独立滚动；窄窗口使用右侧覆盖面板。进度、任务错误、恢复及直播停止操作保留在主工作区。原有识别、翻译、切片、样式／模板、ASS／烧录／ArcTime 文件交接调用契约保持。

本机安装版为 **0.1.8 build15**，位于 `~/Applications/Nyaru Clipper.app`。本轮 UI 更新复用 build14 的原生窗口、冻结后端、工具和模型，仅更新构建后的前端与构建号并重新本地签名，未重新冻结后端。严格签名验证通过，所引用 HTML／JS／CSS 的 SHA256 与生产构建一致。旧版位于：

`~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-16-before-toolbar-build15/Nyaru Clipper.app`

## 本次验证与证据边界

- 本次提交前，两工作树各运行 Companion 前端 **5 文件、47 项测试通过**，并通过 TypeScript／Vite 生产构建；范围重叠，不相加。`git diff --check` 和暂存范围检查通过。
- 前一实现阶段已通过本地 HTTP／短视频夹具驱动生产前端，覆盖六个入口、草稿、文件选择、校验、Escape 焦点、抽屉滚动、播放连续性、空任务和录制状态，及 1440／1920／390 宽度。系统外观偏好均检查，产品仍沿用原浅色主题。
- 安装版原生窗口已逐项验证六个入口点击开合、跨面板链接草稿及 Escape；安装前后历史任务均为 20 项，更新时无活动任务。本次 Git 发布阶段没有重新处理媒体、调用模型或改变授权。
- 私密证据位于 macOS 工作树 `.omo/evidence/toolbar-drawer-2026-10-16/`，包括 `browser-qa.json`、`native-qa.json`、`install-assets.json` 和窗口截图；不提交运行数据、媒体、凭据或私密截图。

见[本轮界面验收](toolbar-drawer-acceptance-2026-10-16.zh-CN.md)。本轮未重新执行真实下载、ASR、翻译、录制、烧录、导出或原生保存权限验收。Developer ID、公证、公开分发、新机器、Intel／旧 macOS 兼容性及真实授权到期／撤销仍未验收。构建为 arm64／最低 macOS 27.0。

## 保留的真实任务记录（历史验收）

10 月 15 日交接记录以下处理／翻译终态为 completed，本轮未重新处理或重算全部媒体哈希：

| 场景 | 任务 | 记录结果 |
| --- | --- | --- |
| 原全片臊子 | `1bd089ad75b3` | 3275.299 秒／35 片，Flash 658/658；原任务保留 |
| 用户要求的 OpenAI 重跑 | `3a01f1263649` | 34 片，GPT-6-Luna 658/658；重新切点／翻译，无 Flash 缓存复用 |
| 本地录像 | `73fbcd311737` | 150.033333 秒／2 片，ChatGPT 21/21 |
| Bilibili 直播 | `68faca68e130` | 181.105 秒／2 片，ChatGPT 40/40；停止前已输出首片双语 |
| Web 本地任务 | `472c1adbd0d1` | 150.033333 秒／2 片，ChatGPT 21/21；保留短尾段 |

此前网络中断与续跑证据保留；恢复通过不等于供应商持续可用。译文／切点仅作样本核对，未逐句人工验收。原生 build14 播放及 NSSavePanel 保存曾通过；用户未授予 WKWebView Downloads 权限并明确接受该部分，不得写成权限已授予或技术验收通过。详见[Web 验收](web-app-acceptance-2026-10-15.zh-CN.md)、[订阅验收](openai-subscription-acceptance-2026-10-15.zh-CN.md)、[臊子验收](saozi-acceptance-2026-10-15.zh-CN.md)及[双语补齐](saozi-bilingual-acceptance-2026-10-15.zh-CN.md)。

## 运行、源码和保护规则

App 数据在 `~/Library/Application Support/Nyaru Clipper/`，包含 `runs/`、`models/`、`app.log`；供应商配置在 `runs/config.json`，ChatGPT 授权在 `runs/.chatgpt/`（目录 0700／文件 0600）。不读取、复制、提交或输出秘密值。模板位于 `runs/templates/`；保留任务清单、源媒体、旧导出、失败和恢复证据。CLI 的 `data/local-runs/` 不自动迁入 App。

App 重启后回环端口会变，使用运行中的 startup 信息；不要硬编码旧端口，也不要启动第二个服务写同一任务根目录。不得暴露公网、增加多 worker、恢复 ArcTime 付费／云调用或使用 **DeepSeek Pro**。AI 可选 DeepSeek Flash／ChatGPT 订阅；新默认仅影响新任务，重试沿用任务记录的供应商和模型，不自动切换。

共享代码位于功能工作树的 `backend/app/arctime/` 与 `web/src/companion/`。macOS 专属为 `desktop/macos/`、`backend/app/arctime/macos.py`、`scripts/build_macos_app.py`；不得用 Web 的 `media.py` 整文件覆盖冻结工具逻辑。主目录旧工作站 `backend/app/main.py`／worker 不是 Companion 启动入口。

```bash
cd /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/web
corepack pnpm exec vitest run src/companion
corepack pnpm build
```

macOS 工作树同样在其 `web/` 目录运行上述命令。安装版双击启动；浏览器／CLI 启动见[本地工具](local-companion.zh-CN.md)，供应商见[ChatGPT 订阅](openai-subscription.zh-CN.md)，切片见[臊子](saozi.zh-CN.md)。

## 后续与历史

本轮授权范围是开发分支发布与交接更新。逐句／切点复核、样式与 ArcTime 使用反馈、更多平台验收、签名公证、公开分发以及分支合并均需另定范围。

完整保留[本次发布前交接](project-handoff-history-2026-10-16-before-toolbar-publish.zh-CN.md)、[10 月 15 日刷新前快照](project-handoff-history-2026-10-15-before-delivery-refresh.zh-CN.md)、[10 月 15 日](project-handoff-history-2026-10-15.zh-CN.md)和[10 月 14 日](project-handoff-history-2026-10-14.zh-CN.md)。历史“未提交／未推送”、build14 及旧分支 HEAD 只适用于对应记录时间。
