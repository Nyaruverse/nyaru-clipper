# Nyaru-Clipper 项目交接

核验日期：**2026-10-16，Asia/Shanghai**。本页为当前交接入口；历史快照保留当时的状态，不代表当前 HEAD、安装版或服务状态。

## 本轮开发分支发布

发布范围仅为以下两个开发分支；功能与测试、使用与验收文档分别提交。主目录 `feat/arctime-pro-plugin` 不提交、不推送、不合并；本地及远程 `master` 保持 `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`。

| 开发分支 | 功能提交（后续还有交接文档提交） | 工作目录 |
| --- | --- | --- |
| `codex/local-companion-web` | `edf3777636e0b9f231eb1734ee78dc2f55ec4eb4` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` |
| `codex/local-companion-macos` | `069061bddc0ded8936932dbe6c12d0b786069a22` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` |

使用显式 refspec 原子推送这两个分支。最终 HEAD 包含后续文档提交，不等于上表功能提交；精确远程回执保留在 macOS 工作树 `.omo/evidence/task-sources-build17-2026-10-16/publish-receipt.json`。接手时核验：

```bash
git ls-remote origin refs/heads/codex/local-companion-web refs/heads/codex/local-companion-macos refs/heads/master
git -C /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper status --short
git -C /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper status --short
```

两端前端各 72 项及生产构建通过；本轮发布前后端复测 115 项通过（其中 3 项为 macOS 打包检查），另有一条 Starlette/httpx 依赖弃用警告。冻结后端、本地安装、原生输入和数据保留验收见[三来源与 build17 验收](task-sources-acceptance-2026-10-16.zh-CN.md)。下一步为用户真实房间／BV 使用反馈；更多平台、公开分发、公证和分支合并均未包含在本轮发布。

## 最新本机安装：0.1.9 build17

2026-10-16 已按用户授权重新打包并替换 `~/Applications/Nyaru Clipper.app`，启动验证通过。新建任务提供「实时录播／下载视频／本地视频」，分别直接填写数字直播间号、BV 号或选择文件；下载和本地视频共用切片选项。以下 build16 发布与安装记录保留为历史，不能视为当前安装版。

旧 App 保存在 `~/Applications/Nyaru Clipper Backups/20261016-132441/Nyaru Clipper-build16.app`；完整数据备份在 `~/Library/Application Support/Nyaru Clipper Backups/20261016-132441/Nyaru Clipper/`，备份父目录 0700，含授权配置，仅保留在本机。

替换前后 6,561 个文件、9,935,483,555 字节的内容哈希、权限和符号链接一致；启动及原生界面检查后，20 个历史任务 ID、供应商配置与授权状态一致，全部原有数据文件未变化，仅新增一个启动信息文件。严格签名、冻结后端的编号校验、本地导入／真实识别／3 秒切片导出和 ZIP 完整性通过。原生界面已观察三种来源，没有创建或重跑历史任务；真实 Bilibili 下载／录播和外部 AI 未重新验收。本地签名未公证，仍为 arm64、最低 macOS 27.0。

安装包为 macOS 工作树 `.omo/evidence/task-sources-build17-2026-10-16/Nyaru-Clipper-0.1.9-build17-macOS-arm64.zip`，520,730,841 字节，SHA256 `be1154477eada169d384f61b8f4960bb507095dd48821dd574be38207e89ac11`。同目录的 `installation-receipt.json`、`frozen-smoke-receipt.json`、`package-receipt.json` 与 `installed-{bv,live,local}.jpg` 为本机证据；不提交 App、备份、模型或私密清单。

## build16 发布与分支边界（历史）

本轮交付 Web／macOS 逐条字幕编辑与一致的预览、ASS 和烧录导出。用户随后授权安装 build16，并将本次实现及交接提交、推送到以下两个开发分支，**master 不动**。功能与测试单独提交，使用／验收文档及当前交接在随后的文档提交中。

| 开发分支 | 本次功能提交（交接文档提交之前） | 工作目录 |
| --- | --- | --- |
| `codex/local-companion-web` | `576b538d336cbeaf9c869f049f3b7d063ad9f792` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` |
| `codex/local-companion-macos` | `a132fcc6125380a5451e5cfe2dd335ec55260e81` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` |

使用显式 refspec 原子推送这两个分支；主目录 `feat/arctime-pro-plugin` 和其他分支不推送、不合并。本地／远程 master 基线为 `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`。主目录中的其他未提交工作保留。

仓库为 [Nyaruverse/nyaru-clipper](https://github.com/Nyaruverse/nyaru-clipper)，origin 为 `https://github.com/Nyaruverse/nyaru-clipper.git`。最终 HEAD 包含后续交接提交，上表不是最终远程 HEAD。接手时核验：

```bash
git ls-remote origin refs/heads/codex/local-companion-web refs/heads/codex/local-companion-macos refs/heads/master
git -C /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper status --short
git -C /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper status --short
```

本地精确推送回执在 macOS 工作树 `.omo/evidence/subtitle-editor-2026-10-16/publish-receipt.json`，不进入 Git。源码推送和本机安装不代表公证、公开分发或全平台验收。

## 当前功能与使用入口

顶部六入口和独立滚动的右侧抽屉继续保留。打开已完成任务，点击字幕，选择右侧「位置」；X/Y 是输出视频有效画面的像素坐标，不含播放器黑边。红色「＋」可拖动，聚焦后方向键每次移动 1 像素、Shift 为 10；支持九宫格锚点、吸附、安全区、居中、恢复自动位置和中日文联动。多选后按每条字幕自己的原位置移动。

逐条编辑器分为「内容／位置／样式／时间」，支持独立原文／译文、局部强调、字体与高级排版、拆分／合并、帧微调、批量平移、循环播放、样式复制粘贴、撤销／重做和串行自动保存。独立样式为该语言整套覆盖，恢复继承后才跟随全局模板。保存冲突保留草稿；源字幕变化需显式重建并备份旧编辑稿。

编辑稿独立保存为任务目录 `subtitle-document.json`；原始字幕、媒体、识别／翻译记录及旧导出不覆盖。精确预览通过与 ASS／烧录相同的 libass 生成透明图片。切片按源视频绝对时间求交、截断并转换为片段零点；ASS 为百分之一秒精度。烧录仍仅支持完成切片。原 SRT 下载保持原结果，编辑后的 SRT 与 JSON 随 ArcTime ZIP 交付。具体入口和限制见[逐条字幕编辑](subtitle-editor.zh-CN.md)。

## build16 安装、回退与数据保留

本机安装版为 **0.1.8 build16**，位于 `~/Applications/Nyaru Clipper.app`。本轮重新构建前端、冻结后端及工具／模型、编译 Swift 窗口并本地签名；严格签名和 Swift 类型检查通过。安装时无运行任务，正常退出 build15 后替换并成功打开 build16。

- 旧 App：`~/Applications/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper-build15.app`。
- 完整数据备份：`~/Library/Application Support/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper/`，备份目录 0700。包含授权配置，只保留在本机，不提交或共享。
- 替换前后 **6,560 个文件、9,935,471,576 字节**逐文件哈希一致；重启后 **20 个历史任务 ID**全部保留，原有文件再次核验未变化。
- 安装前未另存的自定义样式已保留为「升级前自定义样式 2026-10-16」。原生位置演示 X640→641 后撤销，恢复 X640/Y656；保存第 2 版、各条样式仍继承。演示仅新增该任务的编辑稿及启动文件。
- 本地 ZIP `Nyaru-Clipper-0.1.8-build16-accepted.zip` 位于上述证据目录，514,619,440 字节、3,914 项；SHA256 为 `2badc99dc66bb1cfa44888d3a976ce87a693710e02c9fc6e534d00d89a15ff17`。App／ZIP／模型不进入 Git。

## 本次验证与证据边界

| 范围 | 结果与证据 |
| --- | --- |
| 两端前端 | 各 10 文件／65 项通过，TypeScript／Vite 构建通过；重复覆盖不相加 |
| 后端回归 | 字幕、模板、API、渲染、GUI、翻译和 macOS 共 160 项通过；Web 独立执行其中 50 项编辑稿／字体测试 |
| Web 实际界面 | 1440／1920／390 宽度、两种系统外观偏好、四个页签，共 48 张顶／底截图；无横向溢出，产品仍为浅色主题 |
| 最终冻结后端＋原生 WKWebView | 底部／居中／顶部双语多行、原文／译文分别微调、联动数值定位通过；选中像素边界 +1X/0Y，另一语言不动 |
| 预览／ASS／烧录 | 实际 ASS 坐标与 PNG 对照；烧录帧与预览合成 RMSE 分别 1.355／1.507／1.422（满量程 255，包含有损编码差异） |
| 数据与失败路径 | 样例邻句、源文件、旧导出哈希不变；源变化／版本冲突／无效时间拒绝，草稿保留；缺失字体警告通过 |
| 复核 | 早期 G1 多行自动锚点跳动已修复；新一轮位置代码复核 APPROVE，无阻塞，并独立运行 14 项前端／41 项后端及实际 ASS 过渡对照 |

完整、安全脱敏的摘要见[本轮验收](subtitle-editor-acceptance-2026-10-16.zh-CN.md)。私密原始证据仍在上述 `.omo/evidence/` 目录：`acceptance.md`、`integration-receipt.json`、`native-candidate-*-verification.json`、`native-report.md`、`position-delta-review.md`、`installation-receipt.json`。历史拒绝报告与失败测试保留，不能当作当前仍失败。

本次未重新验收真实下载、ASR、供应商授权／到期／撤销、所有字体／字形与样式组合、原生保存／确认对话框、新机器或 Intel／旧 macOS。用户已授权并完成这台机器的替换升级；构建仍为 arm64、最低 macOS 27.0、本地签名未公证。复杂动画、卡拉 OK、运动关键帧、透视、矢量遮罩及完整视频烧录不在本次范围。

## 保留的真实任务记录（历史验收）

10 月 15 日交接记录以下处理／翻译终态为 completed，本轮未重新处理。build16 安装时已核验当前完整数据目录文件哈希；历史质量结论仍以当时验收为限：

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

本轮已授权开发分支发布、交接更新及本机 build16 替换安装。逐句／切点复核、样式与 ArcTime 使用反馈、更多平台验收、签名公证、公开分发以及分支合并均需另定范围。

另保留[逐条字幕发布前交接](project-handoff-history-2026-10-16-before-subtitle-editor-publish.zh-CN.md)。此前完整保留[工具栏发布前交接](project-handoff-history-2026-10-16-before-toolbar-publish.zh-CN.md)、[10 月 15 日刷新前快照](project-handoff-history-2026-10-15-before-delivery-refresh.zh-CN.md)、[10 月 15 日](project-handoff-history-2026-10-15.zh-CN.md)和[10 月 14 日](project-handoff-history-2026-10-14.zh-CN.md)。历史“未提交／未推送”、build14 及旧分支 HEAD 只适用于对应记录时间。
