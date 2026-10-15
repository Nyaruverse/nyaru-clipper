# 本地工具网页版交接

## 2026-10-16 · 顶部选项与右侧抽屉

本次已按用户选定方案完成：顶部六个入口点击展开右侧抽屉，再点同一项收起；关闭按钮／Escape 可收起，切换保留草稿和本地文件选择。进度、任务失败与直播停止保留在主工作区。

本机已更新并启动 **0.1.8 build15**，复用 build14 的原生窗口／冻结后端／工具与模型，仅更新构建后的界面和构建号并重新本地签名。严格签名及引用前端资源哈希一致性检查通过，原生六个入口逐项开合验证通过；历史任务更新前后均为 20 项。build14 保存在 `~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-16-before-toolbar-build15/Nyaru Clipper.app`。

Web／macOS 工作树各 47 项前端测试及 TypeScript／Vite 构建通过，范围重叠不相加。源码与文档仍为本地未提交／未推送改动，分支 HEAD 未变化；原有交接改动保留。本次未重新执行真实处理或供应商调用。见[界面更新验收](toolbar-drawer-acceptance-2026-10-16.zh-CN.md)。下文 10 月 15 日内容作为前次快照，安装版及界面以本节为准。

本工作树负责共享 CLI／浏览器处理流程与界面，不包含原生 App 打包。

核验日期：**2026-10-15，Asia/Shanghai**。本文件是当前交接入口；旧版本、“未推送”和旧测试数量保存在历史快照，不再作为当前状态。

## 仓库转移与开发权限（2026-10-15 复核）

仓库已由 `damin93381` 转移至 [Nyaruverse/nyaru-clipper](https://github.com/Nyaruverse/nyaru-clipper)，对方已接受，转移完成。GitHub 仓库 ID 仍为 `1220984295`；`master` 和下表三个开发分支的 HEAD 均与转移前一致。本次未修改提交历史、GPL-3.0-only 许可证或现有 `Copyright (c) 2026 damin93381` 声明。

- 当前开发账号仍为 `damin93381`，GitHub 实查角色为 **write**，`pull: true`、`push: true`、`admin: false`；可继续开发和推送，不再拥有仓库管理权限。协作者权限由新所有者管理，并非永久不可撤销。
- 主目录、Web 工作树和 macOS 工作树的 `origin` 拉取／推送地址均已更新为 `https://github.com/Nyaruverse/nyaru-clipper.git`。它们共用主仓库的 Git 配置，其他关联工作树也会继承新地址。
- 三个目录分别对当前分支执行 `git push --dry-run origin HEAD:refs/heads/<当前分支>`，均返回 `Everything up-to-date`；仅作推送预演，没有创建提交或实际推送。

本次只更新 Git 远程配置与转移记录。三个目录的交接文档均保留为本地未提交改动；下文 App、供应商、真实任务与测试结果沿用此前验收记录，本次未重新运行。


## 当前结果

已安装 **Nyaru Clipper0.1.8 build14**，包含链接下载、whisper.cpp本地识别、指定时间段／规则高光、字幕样式与模板、ASS／烧录／ArcTime文件交接，以及**臊子**回放／本地录像／Bilibili实时切片。臊子按字幕段落连续选择约60–120秒切片，完整保留不足一分钟的尾段，并自动生成中日双语SRT。

AI供应商可选 **DeepSeek Flash／ChatGPT订阅**。用户已完成官方授权；本轮安全配置接口核验显示已连接、订阅共享有效，默认模型为 `gpt-6-luna`，辅助服务ready。**DeepSeek Pro已禁用，严禁使用。** 新默认仅影响新任务；重试沿用任务／检查点记录的供应商与模型，失败不自动切换供应商。

## 提交、推送与工作树

以下本地HEAD已在本次文档更新中与最新 `git ls-remote` 核对一致。

| 分支 | 本地与远程HEAD | 工作目录 |
| --- | --- | --- |
| `codex/local-companion-web` | `df66540a352328aeaf2a644bb3272210ecb60c85` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` |
| `codex/local-companion-macos` | `fbb81ff1ca22db06180051e741beef6c1ddcee8b` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` |
| `feat/arctime-pro-plugin` | `e8ea71085cf5c6ff6f671499872f5c166d31f89b` | `/Users/drm/project/nyaru-clipper` |

Web／App功能、测试与验收文档均已**提交并推送**。远程 `master` 仍为 `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`，未合并或公开发布。此前功能交接刷新前，两个功能工作树干净；目前三个目录均有未提交的交接更新，主目录另保留此前文档／设计改动。**交接刷新、转移记录及快照均为本地未提交文档改动。** 不要reset或清理其他工作.

提交：[Web df66540](https://github.com/Nyaruverse/nyaru-clipper/commit/df66540a352328aeaf2a644bb3272210ecb60c85)、[App fbb81ff](https://github.com/Nyaruverse/nyaru-clipper/commit/fbb81ff1ca22db06180051e741beef6c1ddcee8b)。

## 真实任务与验收

本轮从当前辅助服务读取，下表处理与翻译均为completed。媒体、哈希和字幕条目检查来自既有验收回执；本次只回读终态，没有重新处理或遍历重算全部哈希。

| 场景 | 任务 | 时长／切片数 | 翻译与结果 |
| --- | --- | --- | --- |
| 原全片臊子 | `1bd089ad75b3` | 3275.299秒／35片 | Flash，658/658；既有译文原从40c0c9复用，原任务保留 |
| 用户要求的OpenAI重跑 | `3a01f1263649` | 3275.299秒／34片 | ChatGPT GPT-6-Luna，658/658；重新判断切点、重新翻译，未复用Flash切点／译文缓存 |
| 新本地录像 | `73fbcd311737` | 150.033333秒／2片 | ChatGPT，21/21；73／77.033333秒 |
| 真实Bilibili直播 | `68faca68e130` | 181.105秒／2片 | ChatGPT，40/40；107.705／73.4秒，停止前已有首片双语输出 |
| Web页面创建本地任务 | `472c1adbd0d1` | 150.033333秒／2片 | ChatGPT，21/21；114秒及保留的36.033333秒尾段 |

OpenAI重跑产出34份原文切片SRT、34份双语切片SRT及完整双语SRT；各片64–118.4秒，连续覆盖全片。此前ffprobe核验的最大时长偏差为0.059675秒；原任务150项文件哈希保持一致。翻译在120条后发生一次网络中断，同任务续跑后完成；原生App已显示34片、658/658。

Web实测覆盖供应商保存／恢复、文件选择与本地上传、识别／语义切片、网络失败继续、双语播放、SRT下载与刷新持久性，使用安装版辅助服务。Web新任务首次在0/21网络中断，一次页面重试后完成；播放时间正常推进，下载SRT与任务文件SHA256一致。这是恢复通过，不代表供应商始终可用；模型目录也在刷新后从网络失败恢复。最终浏览器控制台无警告／错误记录。

原生build14播放与通过NSSavePanel保存到项目目录均通过。**用户误点后没有授予WKWebView的Downloads权限，并明确要求该部分按用户接受处理。** 不要写成权限已授予或技术验收通过；独立浏览器SRT下载已单独通过。

## 验证证据与边界

- 最近功能验证：App所选后端 **382项通过**、Web所选后端 **375项通过**、Companion前端 **5文件41项通过**、TypeScript／Vite生产构建通过；后端范围重叠，不相加。
- 提交前暂存检查通过，未包含运行状态、凭据、媒体或私密截图。保留一条既有Starlette HTTPX弃用警告。
- 本轮重新读取安装Info.plist确认0.1.8／build14，并确认现有辅助服务ready。严格签名／安装哈希、登录保留与原生保存属于既有功能验收，本轮未重跑。
- 本轮仅更新文档并只读核验，未运行测试、新供应商调用、直播录制、媒体导出或App构建，未新增Git提交／推送。
- 译文与切点只作样本核对，未逐句人工校对；ASR专名、游戏术语仍可能有错。此前Flash503／超时证据保留，本轮未重测Flash可用性，不得以Pro绕过。
- Developer ID／公证／公开分发、Intel／旧macOS、手机／其他浏览器、全新机器安装未验收；未通过等待令牌到期或撤销用户现有授权来验收真实到期续期及远程撤销。

[Web复测](web-app-acceptance-2026-10-15.zh-CN.md)、[ChatGPT订阅验收](openai-subscription-acceptance-2026-10-15.zh-CN.md)、[臊子验收](saozi-acceptance-2026-10-15.zh-CN.md)、[双语补齐验收](saozi-bilingual-acceptance-2026-10-15.zh-CN.md)。

重跑私密回执：`/Users/drm/project/nyaru-clipper/.omo/evidence/rerun-1bd089-openai-result.md` 及 `rerun-1bd089-openai.json`。其他本地证据含 `openai-native-final.json`、`openai-install-hashes.json`、`openai-online-local.json`、`openai-online-live.json` 和 `web-release-2026-10-15/`；均不进入Git。

## 运行、数据与保护边界

| 项目 | 位置／规则 |
| --- | --- |
| 安装版 | `~/Applications/Nyaru Clipper.app`，0.1.8 build14 |
| 任务／模型／日志 | `~/Library/Application Support/Nyaru Clipper/` 下的 `runs/`、`models/`、`app.log` |
| DeepSeek及供应商配置 | `runs/config.json`；不得在接口、文档或日志中输出私密值 |
| ChatGPT授权存储 | `runs/.chatgpt/`；目录0700、文件0600，不读取／复制／分享凭据 |
| 模板 | `runs/templates/styles/`、`runs/templates/projects/`、`runs/templates/defaults.json` |
| 输出 | 各任务MP4、原文SRT、`subtitles.ja-zh.srt`／`clip-NNN.ja-zh.srt` |
| 浏览器／CLI历史 | 显式指定输出目录，通常是工作树 `data/local-runs/`；不自动迁入App |

App重启后回环端口会变，从运行中的App／startup状态获取，不硬编码旧端口，也不启动第二个服务写同一任务根目录。保留模型、任务／翻译清单、原媒体、旧导出与失败证据，包括35b20d已修复的SSE格式失败和Issue#1历史恢复记录。不得暴露公网、增加多worker、提交凭据／媒体／私密证据或恢复ArcTime付费调用。

## 源码入口与后续

共享源码在 `backend/app/arctime/`：`saozi*.py`、`live_capture.py`、`live_state.py`、`companion_*.py`、`translation.py`、`chatgpt_*.py`；界面在 `web/src/companion/`。App专属入口是 `desktop/macos/`、`macos.py` 与 `scripts/build_macos_app.py`。主目录 `backend/app/main.py`／worker仍属旧工作站，勿用Web版 `media.py` 整文件覆盖App的冻结工具逻辑。

操作参考[臊子](saozi.zh-CN.md)、[ChatGPT订阅](openai-subscription.zh-CN.md)、[本地工具](local-companion.zh-CN.md)。前端在 `web/` 运行 `corepack pnpm exec vitest run src/companion` 和 `corepack pnpm build`。共享后端使用Python3.11及 `PYTHONPATH=backend`，选择 `test_chatgpt*`、`test_companion*`、`test_saozi*`、`test_live_capture.py`、`test_arctime*`、`test_local_companion_cli.py`、`test_subtitle*`；App再包含 `test_macos*`。

当前没有因实现未完成而阻塞的用户请求。后续逐句／切点质量复核、样式与ArcTime试用反馈、更广主机／平台验证、签名公证或开发分支合并需另定范围，均仍为待办。当前构建为arm64／最低macOS27.0，不得仅修改Info.plist就宣称兼容旧系统。

本轮更新前交接见[完整快照](project-handoff-history-2026-10-15-before-delivery-refresh.zh-CN.md)；更早记录保留在[10月14日](project-handoff-history-2026-10-14.zh-CN.md)和[10月15日](project-handoff-history-2026-10-15.zh-CN.md)快照。旧版本、Pro与“未推送”描述只适用于当时观察。
