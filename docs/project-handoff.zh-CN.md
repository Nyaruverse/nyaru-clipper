# 当前交接 — 2026-10-27（Asia/Shanghai）

文档更新于 10 月 27 日；本轮现场状态核对时间为 **10 月 26 日 23:57（Asia/Shanghai）**。

**正式版本为 0.1.21 build 33，已启动进入看片工作台；队列保持暂停。** 本节取代下方历史段落中的“当前／已安装／未安装”描述；历史版本号和 Git 表格只对应其原记录日期。

## 当前状态与接手入口

- 正式 App：`/Users/drm/Applications/Nyaru Clipper.app`。
- 正式运行时：`/Users/drm/Library/Application Support/Nyaru Clipper/unified/runtime.json`。继续沿用原模型、凭据和设置，不重新初始化数据域。
- 已现场只读核对 App 版本、运行中的后端和 API：4 个真实测试任务保留，最终任务及其 4 个操作均成功，队列暂停。API 端口随启动变化，不把先前测试端口当成固定配置。
- 用户选择的产品方向是**看片工作台，以高光审阅为核心**。已修复翻译入口、自动语言保存、无关的默认 30 秒切片、单段／组合成片预览、小窗口布局、标题刷新与空版本提示。
- [修复与真实复测收据](watch-workbench-real-fixes-2026-10-26.zh-CN.md)包含实现、媒体、数据保留和验收边界。较早的 [0.1.20 安装记录](watch-workbench-install-2026-10-26.zh-CN.md)保留为历史。

## 已确认的真实复测

最终任务：`7a69c98888d15620b3aa11e9fba5dbc9`，标题为 `真实高光完整复测 · build30 · 自动日语`。标题中的 build30 是当时的测试标记，**当前安装仍为 build33**。

同一段 328.300 秒真实录播完成：原生导入 → 自动识别为日语／50 条字幕 → 原生按钮调用真实 DeepSeek 翻译 50/50 条 → 4 个高光候选（覆盖 40.15%）→ 倒序 `[2,0]`、调整范围 → 双语导出。两个单段为 42.100 和 63.300 秒，组合为 **105.421333 秒**；三个下载文件均完整解码通过。Web 整段自然播放到结尾，原生画面与正常播放由用户现场确认；原生抓图限制不冒充自动像素验收。

完整链路在 build30 运行，build31–33 只有样式和构建号调整；后端 Python 与前端 JS 内容摘要一致，build33 布局和 Web 播放另行核验。此前前端 365 项、后端相关 139 项、原生／翻译集成 32 项通过；边界调整另有 62 项针对性检查。本次交接刷新没有重新运行这些测试、ASR、翻译或导出。

证据主目录：`/Users/drm/.codex/worktrees/highlight-subtitle-macos/nyaru-clipper/.omo/evidence/watch-workbench-fixes-20261026/`。优先阅读 `final-install-runtime.json`、`final-media-validation.json`、`final-web-playback-later.json`、`native-human-acceptance.json`、`data-preservation.json` 和 `review.md`。本次启动／API 只读核对见 `/Users/drm/project/nyaru-clipper/.omo/evidence/handoff-refresh-20261026-workbench/before.json`。

## 源码位置与版本控制

10 月 27 日用户已授权完整提交和推送。源码、回归测试、生成契约、打包与中英交接文档按职责分组提交；主目录只发布文档。共享前端与契约已同步，Web 后端原有 Windows 差异保留。

| 工作树 | 本地分支 | 发布目标 | 实现里程碑（文档提交之前） |
|---|---|---|---|
| 主目录 | `codex/code-improvement-2026-10-21` | `origin/codex/code-improvement-2026-10-21` | 仅文档；此前 HEAD `da11831cdf976560f642370790847bba647f7ff9` |
| macOS | `codex/highlight-subtitle-macos-2026-10-25` | `origin/codex/local-companion-macos` | `5ffd9a826261e9fb0b405486cde6aae843fcdc79` |
| Web | `codex/highlight-subtitle-web-2026-10-25` | `origin/codex/local-companion-web` | `59688e2b45014c02f79b04c1f36213899824dfc0` |

本次 Git 发布使用明确 ref，原子快进推送到以上三个既有远端分支；不包含合并、强推或 master／协作者分支更新。最终文档提交 HEAD 与远端比对结果记录在 `/Users/drm/project/nyaru-clipper/.omo/evidence/git-publication-20261027/receipt.json`；上表刻意记录文档提交之前的实现里程碑。

发布前重新检查：两套前端各 **365 项测试／45 个文件**、TypeScript 和生产构建通过；macOS 后端／原生检查 **171 项通过，1 项 actual-desktop 用例未选入**，Web 后端 **139 项通过**。最初并行运行两套后端测试争用了共享执行锁，顺序完整重跑后通过。Web 审阅测试补齐逐例清理 localStorage 以及同源重载／空版本号回归。本次发布未重复真实识别、供应商调用、导出或原生界面验收，仍以此前带日期证据为准。

未跟踪的媒体／模板输出、`.DS_Store`、临时 pnpm workspace 配置、测试缓存、运行数据与私有证据不进入 Git，均留在原处。后续从对应平台工作树继续，不要 reset、clean 或覆盖原工作树。

## 保护、回退与剩余事项

- 安装收据已验证 21 个原有活动文件、2 个旧任务上下文、原片及原设置保留。原始媒体、旧封存域、reader／epoch pin、现有任务和失败记录继续保护；本次 Git 发布不替换正式 App、不改写正式数据。
- 回退备份：`/Users/drm/Library/Application Support/Nyaru Clipper Backups/workbench-fixes-20261026-1723/`。保留原 0.1.20 App、真实复测 build30 和安装前 `unified/` 快照。回退先正常退出并保留最新运行时，只切 App；不要用旧快照覆盖后续新数据。
- 审阅草稿支持同源刷新，**不跨原生 App 重启保留**；已导出视频及冻结范围仍在服务端。旧 auto 任务没有实际语言结果时不追溯猜写，应重新识别。
- 中间任务 `f98b6a7d...` 的一次分析失败已保留，不能当作最终复测失败或删除掩盖；最终任务四项操作均成功。
- 待办限已知缺口：按需处理跨重启草稿持久化；人工逐句校对字幕并判断候选质量；另行验证长 VOD／真实直播、Windows／GPU、系统深色模式、故障恢复及公证。现有短片通过不扩展为这些场景的验收。

## 历史交接原文

以下正文保留原样；其中“当前”均仅指相应历史日期。

# 2026-10-26：看片工作台已正式安装

正式 App 现为 **0.1.20 build 28**。原活动数据／配置已备份并核对未改写，正常重开使用已登记的正式运行时。详见[安装、保留与回退记录](watch-workbench-install-2026-10-26.zh-CN.md)。下方“候选未安装”等记录属于历史状态。

---

# Nyaru-Clipper 项目交接

## 当前交接：2026-10-25（Asia/Shanghai）

统一架构已合并并推送到 Web 与 macOS 开发分支，此后已完成远端及本地提交身份改写。本节取代下方较早的发布状态与提交编号；带日期的旧记录继续作为历史证据保留。本次只修改两份交接文档，不提交、推送、合并、安装、启动 App、恢复监控或切换数据域。

### 当前远端分支与原工作树

2026-10-25 只读执行 `git ls-remote --heads --tags origin`，结果如下：

| 远端分支 | 当前 HEAD |
| --- | --- |
| `codex/code-improvement-2026-10-21` | `da11831cdf976560f642370790847bba647f7ff9` |
| `codex/unified-architecture-2026-10-22` | `0468740a717a7fdcf66e74b7295e4e0501625515` |
| `codex/local-companion-web` | `3e0582b47577b1fa7f26466fef7b78f7088c1fd7` |
| `codex/local-companion-macos` | `73aa14b6def9e7e9b970a42621844e7c62f702f2` |
| `feat/arctime-pro-plugin` | `ef9ea33d3d08f2ee1472b660179a52d8f40d7813` |
| `feat/companion-topic-subtitle-updates` | `69d3fa0dea30a73ef0f0ef27591bc1abda9080f1` |
| `master` | `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6` |

master 与四个标签对象编号仍符合此前基线。topic/subtitle 分支已从 10 月 24 日清理收据中的 `39911f1a24775d2e8fd4cb3a98a8165fa70880e4` 继续前进，本次未审计或修改新增提交；不能把此前历史清理通过的结论推广到当前所有远端提交。

五个原工作树在身份改写后仍保留原来的代码版本：

| 工作树 | 本地 HEAD | 本次刷新前未提交路径数 |
| --- | --- | --- |
| `/Users/drm/project/nyaru-clipper` | `da11831cdf976560f642370790847bba647f7ff9` | 13 |
| `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` | `8f495b8073f64a257da2bc5e68fa74b1e0db1a94` | 53 |
| `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` | `f47e868aeab61b272597810cff21ef2e83220578` | 56 |
| `/Users/drm/.codex/worktrees/streamer-highlight-framework/nyaru-clipper` | `ee441022f8f41613c5e48e6fdd5ead2b69361b0c` | 12 |
| `/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper` | `0468740a717a7fdcf66e74b7295e4e0501625515` | 0 |

原 Web／macOS 本地分支分别落后对应远端跟踪分支 **19／17 个提交**，因此已发布的合并结果并不是这两个脏工作树当前的源码基线。本地辅助分支 `codex/merge-unified-web-2026-10-23`、`codex/merge-unified-macos-2026-10-23` 指向已发布的合并 HEAD；远端当前没有公布 streamer 分支。本次刷新后主目录在原有 13 个未跟踪路径外增加两份交接文档修改，暂存区为空。

### 合并结果与历史验证

改写后的统一架构实现提交为 `fc1e0405faafe9858569cfbb81acb3b179a69ca5`。10 月 23 日的 Web 合并保留 Windows PowerShell 启动器、CUDA whisper.cpp 路径、Windows 锁／JSON 重试／可执行程序发现及凭据可用性边界；macOS 合并保留原生窗口／系统保存／退出桥接、冻结后端、工具／模型、构建依赖、许可与平台文档。

[合并收据](/Users/drm/project/nyaru-clipper/.omo/evidence/unified-merge-20261023/receipt.json)记录 Web 后端 **1558 passed／3 skipped**、macOS 后端定向 **10 passed**、两侧前端各 **332 passed／40 文件**，两侧 TypeScript／Vite 构建、Swift 类型检查及三份 requirements profile 检查通过。这些是 10 月 23 日的观察：三项 Windows 原生用例在 macOS 跳过，没有新增 Windows 真机资格、正式 App 安装或数据切换。身份改写保留提交文件树，本次文档刷新不重跑上述测试。

### 提交身份与后续新提交

- 10 月 24 日远端清理使用 `git-filter-repo 2.47.0 --sensitive-data-removal`：替换 57 个 author 与 57 个 committer 字段，214 个提交中 62 个编号改变，以精确 lease 原子推送六个分支。当时重新克隆的镜像中，可达对象没有旧身份匹配；文件树、合并关系、日期、提交说明及其他贡献者身份保留。[远端清理收据](/Users/drm/project/nyaru-clipper/.omo/evidence/identity-cleanup-20261024/receipt.json)。
- 本地清理核验 211 个提交、改变 59 个提交编号、更新 15 个引用；五个工作树的文件／权限、索引、暂存及未暂存修改均保留，可达提交元数据旧身份匹配为零，严格 `git fsck` 通过。[本地清理收据](/Users/drm/project/nyaru-clipper/.omo/evidence/local-identity-cleanup-20261024/receipt.json)。
- 仓库级及全局默认配置为 `user.name=damin93381`、`user.email=damin7512476@gmail.com`、`user.useConfigOnly=true`。10 月 25 日再次核对两个配置作用域及五个工作树实际 author／committer，均符合。该身份为用户选择的公开身份，邮箱会写入公开提交元数据。
- 10 月 24 日本机审计覆盖 7,144 个候选位置／7,141 个有效 Git 位置，未发现匹配旧真名／旧邮箱的配置项，没有改动其他仓库配置。298 个位置仍有其他身份，包括 `blogging`、`bot`、`qwen` 与测试仓库。仓库／工作树配置、条件包含、环境变量、显式作者及保留原作者的操作仍可覆盖全局默认值；三个失效临时 Git 标记及排除的备份不在该审计的已核验范围。[私有配置审计](/Users/drm/.cache/git-identity-audit-20261024-UVTrVn/audit.json)。

私有回滚副本与本地 reflog／不可达对象仍有意保留旧历史。不要上传它们、盲目恢复旧引用、合并旧克隆的历史或镜像推送回已清理远端。本次完成的是身份改写，不是删除本地全部恢复副本。

### GitHub 缓存与 Support 边界

10 月 25 日，通过 GitHub API 仍能访问此前定位的旧提交。当前分支／标签历史清理不等于服务器缓存已删除。已准备私有[Support 文案](/Users/drm/project/nyaru-clipper/.omo/evidence/identity-cleanup-20261024/github-support-request.md)，并协助操作虚拟助手向导；本交接没有工单编号、正式提交回执或缓存清理成功回复，用户是否完成正式提交为 **unknown／待验证**。本次刷新未向 Support 发送消息。

如用户选择继续，剩余请求是清除旧缓存／不可达提交，同时保留仓库与当前分支／标签。是否符合清理政策由 GitHub 判断；真名暴露不是密码／令牌泄漏。参照[官方清理手册](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)。旧提交链接与原身份只放在私有支持证据中，不再加入公开文档。

### 接手顺序与保护边界

1. 后续源码整合前重新核对远端 HEAD 和相关工作树，保留未提交文件及索引，从所需的当前已清理远端版本隔离开展工作。不要盲目 pull／reset／clean、批量暂存，也不要为对齐表格而直接推进脏 Web／macOS 分支。
2. 产品后续验证仍为新的独立数据域 App02 R0／R1 接管／回退／重开，再补获准的 M24 系统重启／开机保护。CUDA、WSL ROCm、Windows AMF、外部供应商及真实直播缺口保留；本轮工作没有执行 P6／正式安装／数据切换。
3. 正式 App／数据、原始媒体、封存测试根、未知任务目录、reader／epoch pin 与私有证据继续保护，10 月 25 日没有重新审计它们的运行或内容状态。下方旧包摘要与功能验收保留各自观察日期。

在 `/Users/drm/project/nyaru-clipper` 中可执行的只读核对：

```bash
git worktree list --porcelain
git status --short
git ls-remote --heads --tags origin
git config --global --get-regexp '^user\.'
git config --local --get-regexp '^user\.'
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

`git ls-remote` 不会更新本地 `origin/*` 引用；新提交前应在实际使用的工作树中单独核对有效身份。[本次刷新保护收据](/Users/drm/project/nyaru-clipper/.omo/evidence/handoff-refresh-20261025-git-identity.json)。更新交接不代表已提交或推送。

## 历史版本控制更新：2026-10-23（Asia/Shanghai）

统一架构实现、恢复工具、直接测试与 App02 修复已提交为 `f8484d5560e971fb4a736e6296d876333cb5b7c6`（`feat: unify task execution, migration and recovery`），位于 `codex/unified-architecture-2026-10-22`。主目录文档归入 `codex/code-improvement-2026-10-21`；这两条分支是本轮明确推送目标，master 与其他开发分支不变。下文“尚未提交／未推送”的描述保留为原观察时点的历史，发布结果以[本轮 Git 收据](/Users/drm/project/nyaru-clipper/.omo/evidence/git-publication-20261023.json)及远端分支编号为准。

提交前在统一候选工作树重新执行：后端全量 **1551 passed**，前端 **332 passed／40 文件**，TypeScript／Vite 构建及三份 requirements 导出检查通过。App02 构建输入中的程序源码与此次提交内容一致，构建后仅索引／交接文档有变化；四处既有文件末尾空行提示保留。本轮只发布版本控制内容，不重新打包或安装，不切换正式数据，不补授平台资格。封存域、旧 epoch／reader pin、原始媒体和私有证据继续保留。

## 历史候选接手入口：2026-10-23（Asia/Shanghai）

### 交接刷新核对：2026-10-23 13:36（Asia/Shanghai）

本次仅更新交接文档并只读复核：App02 两个 ZIP、原生程序／冻结后端、固定恢复 bundle 的 SHA256 与上轮收据一致；真实测试域六根仍 immutable，未发现匹配的候选 App／后端进程。[本次核对收据](/Users/drm/project/nyaru-clipper/.omo/evidence/handoff-refresh-20261023-app02.json)。下方功能验收来自上轮实测，本次没有启动 App、重打包、重跑功能测试、连接远端或重新全量核验正式数据。

| 接手对象 | 当前入口与边界 |
| --- | --- |
| 最新候选 App02 | [App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-02/Nyaru-Clipper-unified-candidate-20261023-02.zip)；解包 App 位于 `/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-02/Nyaru Clipper.app`。显示 0.1.19／build 27，必须按下方摘要识别，不双击。 |
| 固定独立恢复包 | [恢复 ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02.zip)；固定 reader 目录 `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02`，不得移动或改绑既有 epoch。 |
| 最新真实任务与恢复证据 | 任务 `ad3ad70afddf5287b5d1b4f797665a2a`：21 条字幕，手工译文 2 条，第 2 版。[R2 清单](/Users/drm/.cache/nyaru-clipper/historical-fixed-native-20261023-01/R2/complete.json)／[独立恢复核验](/Users/drm/.cache/nyaru-clipper/historical-fixed-native-20261023-01/recovered-readonly/verification.json)：3 文档，无错误；本次核对的是保存的收据，未重新执行恢复。 |
| 禁止复用的测试入口 | `historical-fixed-native-20261023-01/runtime` 六根已封存，不能用上轮 launch argv 直接重开。历史 API 域 `historical-fixed-api-20261023-01` 和所有旧 R2／reader pin 保留；旧 App01 空根不作为 App02 默认入口。 |
| 正式环境 | 正式 App 未被候选替换、正式数据未切换。上轮正式 App 内容／元数据、正式数据元数据及选用原任务／原片保护核验见[最终审计](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/final-audit.json)；本次未重做正式数据正文核验。 |

**下一步顺序**：先用新的独立数据域和 App02 固定 reader 重跑 R0／R1 的接管、回退与重开，核对文档版本／全文及显式重试边界；再在获准的隔离平台补 M24 系统重启／开机保护。缺硬件的 CUDA／WSL ROCm／Windows AMF、外部翻译、真实直播等继续待验收，不能用旧包或本机结果代替。原 Workstation 的旧 Linux 绝对路径准备失败未在本轮处理；五个未知目录继续保护。P6、正式安装及数据切换均未启动，不能由“更新交接”推定授权。

### 历史任务修复候选 App02（最新）

F01／F02 已修复并用**新冻结包**复验：历史副本 25/25 场景组通过；真实 150 秒原片识别 21 条，手动译文显示 partial 2/21；原生播放、编辑第 2 版保存、CmdQ 重开、真实 15 秒烧录和系统保存通过。后端相邻回归 82 passed（包含 8 项专项）、前端 332 passed。新包与新独立恢复包均已校验；显示版本仍为 0.1.19／build 27，按摘要识别。

[App02 包与完整中英验收报告](candidate-fixes-2026-10-23.zh-CN.md) · [权威收据](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/receipt.md)。新 App ZIP SHA256 `914e36a0b7cf97ad864cedf9d87abfcfcb1b0ae76248b5ec5da2eb7272eff14b`；独立恢复 ZIP `31e364935d925993b6a849d8c1f7df21b325731c29a39e3e298774153a339c42`；新 epoch bundle `52342c6a998c6241a5381db6a778bb792ae38a0e197989d166da79da73016b54`，旧 pin 不变。

正式 App 内容／元数据、正式数据元数据及选用原始任务／原片核验一致；未替换、未切换、未提交。自建 App/helper／后端已停止，队列暂停。真实测试域 `historical-fixed-native-20261023-01` 六根 immutable、新 R2 已封存，独立恢复导出全部 3 文档并保留真实任务第 2 版。不得双击候选、直接重开／解封 R2 或替换旧 epoch 的 reader pin。新包 R0／R1、M24 系统重启／开机保护及缺硬件／供应商项目仍待验收，不启动 P6 或正式切换。

### 历史任务功能验收（App01 失败快照，已由上方新包闭环）

按用户要求使用历史任务的独立副本验证：冻结接口21组 **19通过／2失败**；150秒真实归档原片新建回放任务，识别21条、15秒切片／字幕烧录通过，浏览器编辑保存至第5版、重载保留。两项未修复问题为**部分译文误报整稿完成**与**迁移高光模式／评分／理由丢失**，不能据此宣布整体验收通过。原工作站因旧Linux绝对产物路径拒绝准备，零激活；五个未知目录保留。

原生界面受macOS锁屏阻挡，CmdQ／系统保存面板／连续播放仍待验收；浏览器结果不替代WKWebView资格。远端ROCm仅只读复核历史1条字幕、4组产物及30秒成片、模型与设备可见性，未重新推理。正式数据元数据、五个原历史任务与14个归档原片核验不变，所有自建候选／helper已停止；未改产品源码／重打包／安装／正式切换。详情与后续修复门槛见[中英验收文档](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/historical-task-acceptance-2026-10-23.zh-CN.md)，[权威证据](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/receipt.md)。

### 打包后交接检查（此前快照）

此前交接刷新仅更新文档并只读复核：压缩包存在、两处 bundle 摘要一致、两套 R2 数据库仍 immutable，未发现该候选的运行进程。当时未重跑应用测试、启动 App、重新构建或连接远端；以下打包验收来自保存的[打包收据](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-receipt.md)，后续功能验证以上方最新章节为准。

| 接手项 | 最新记录 |
| --- | --- |
| [候选 App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-01/Nyaru-Clipper-unified-candidate-20261023-01.zip) | SHA256 `7a5c3cad144c57dc74bda2391e157452b69418d1476fdd40e2895f3b310ad6a9`；5406 文件／权限解包全等，严格签名通过 |
| [独立恢复 ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01.zip) | SHA256 `47f34e5b0d577b20be6d4990bdfd6e093c946159581b4cd1a6035b548b969082`；固定目录 `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01` 不移动 |
| 本次实核 bundle | App 内与独立包均为 `1ce64b4effcc38a592d90b12e879dcc02a990a62316af8fbdc8e23e16b31ff12`；3619 资源完整检查属于打包验收记录 |
| 已验收的本机链路 | 冻结接管、R0／R1 解冻、R1 强杀续跑、旧 helper 重开、原生 r3 保存／退出／重开与独立导出全文一致；R2 解冻正确拒绝 |
| 审阅与正式环境 | [独立审阅](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-review.md) CLEAR／APPROVE／无阻塞；打包前后正式 App 1496 文件内容摘要、正式数据 6815 项元数据一致，未声称正式数据正文全量哈希 |
| 当前门槛 | M03 本机 local_passed，M24 partial；总表 22 local_passed／3 partial／3 blocked，P6 planned；不是全平台 accepted |
| 历史回归边界 | 10 月 23 日全量后端 1538 passed、最终专项 46 passed；最后 5 个终态反例在专项内覆盖，计数不相加；打包验收及此次文档刷新未重跑全套 |

以上为 App01 的历史入口：[当时运行与验收文档](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/candidate-package-2026-10-23.zh-CN.md)及空根 `/Users/drm/.cache/nyaru-clipper/packaged-native-empty-20261023-01/runtime.json`仅作旧记录保留，不是 App02 启动指令。新一轮试用须按顶部 App02 边界建立独立新域，显式指定绝对 `--unified-runtime` 与匹配 `--migration-guard`；不要双击、复用旧端口／PID或改绑 reader pin。

两套新封存域 `/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-recovery-03/R2`、`/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-native-guarded-01/R2` 仅作恢复证据，不直接启动或解封；旧 build-04 样本封存同样保留。下一步仍是获准隔离平台上的 M24 系统重启／开机保护资格，以及缺环境的 CUDA／WSL ROCm、Windows AMF 和真实直播验收，不能据此启动正式切换或 P6。


**此前 App01 包**：[2026-10-23 App 与独立恢复包](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/candidate-package-2026-10-23.zh-CN.md)的隔离启动、冻结接管、R0／R1 回退、强杀续跑、原生 r3 保存／重开及只读恢复证据继续保留；这些结果属于 App01，最新修复包 App02 与其验收边界见上方章节。正式 App 未替换、正式数据未切换。

**统一架构方案 B 的实现与验收进展现位于独立候选工作树。** 请先读[最新中英交接：中文](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/project-handoff.zh-CN.md)、[英文](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/project-handoff.md)，再按其中的执行记录和运行／回退指南继续。候选分支 `codex/unified-architecture-2026-10-22` 基于 `428ba833193db888c6b049ac2983abe1b2ecae17`，实现尚未提交，不能仅凭 HEAD 重建。

候选此前的本机后端 1512 项、前端 332 项、真实浏览器 2 项及 macOS／native Linux ROCm 限定链路已有证据。10 月 23 日进一步完成本机 M03 接管／强杀／HTTP 重开，并修复独立 thaw 中断续跑；新后端全量 1538 项通过，新增终态反例另做最终专项复验。验收矩阵现为 22 项 `local_passed`、3 项 `partial`、3 项 `blocked`；M24 的受控系统重启／开机保护／其他平台 profile，以及 CUDA、WSL ROCm、真实直播、Windows AMF 和 P6 仍未闭环。详见[执行记录第 9 节](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/unified-architecture-execution-2026-10-22.zh-CN.md#9-2026-10-23m03m24-接管与崩溃回退补验收)。未进行统一候选的正式安装替换、正式任务迁移或提交／推送／合并。

本目录仍为 `codex/code-improvement-2026-10-21`、同一 HEAD，保留既有未提交内容；**不要在这里覆盖复制候选代码或清理工作区**。本轮代码与演练均在独立候选／新副本进行，本目录仅新增交接及 `.omo` 验收证据。没有重启主机、连接远端或切换正式数据。下方 10 月 21 日记录说明此前正式安装来源，不代表统一候选已交付正式环境；运行状态和数据数量保留原观察日期。build-04 样本 reader／build-05 App 未替换，不含本次恢复修复，已有 epoch 的固定包不可静默改绑。

---

## 历史交接：2026-10-21（Asia/Shanghai）

**八阶段44项修正已在记录范围内累计验收、提交到改进分支，并已安装到正式App、重新打开；尚未合并或推送。**本节取代下方旧记录中的“当前”状态；旧记录保留原观察日期。此次只更新交接并只读复核，不重新安装、改配置、调用外部AI或重跑完整套件。

### 当前源码与提交

主目录 `/Users/drm/project/nyaru-clipper`，分支 `codex/code-improvement-2026-10-21`，HEAD `428ba833193db888c6b049ac2983abe1b2ecae17`。

| 提交 | 内容 |
| --- | --- |
| `2d6091ee5af1a82310c0d372c6ea02ac7d1b2d15` | `fix: complete workstation and companion improvement plan`：实现、必要Companion基线、直接测试与平台配置；210个明确路径，Git识别一项测试迁移为rename。 |
| `428ba833193db888c6b049ac2983abe1b2ecae17` | `docs: consolidate eight-phase improvement acceptance`：八阶段双语记录、累计汇总、验收摘要及文档；29路径。 |

[八阶段累计修改与提交边界](/Users/drm/project/nyaru-clipper/docs/code-improvement-rollup-2026-10-21.zh-CN.md)、[原44项计划](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.zh-CN.md)、[最终累计结果](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.zh-CN.md)及[可携带验收摘要](/Users/drm/project/nyaru-clipper/docs/validation/code-improvement-acceptance-2026-10-21.json)是当前接手入口。355文件候选摘要 `7702e7f6e0c23172326dc62ddd604729b09062c27a299d94404808c77410fae4`；提交后源码与候选逐一匹配，原中英88个问题块、115份冻结gate证据和原Companion99哈希保持。原功能工作树及其未提交内容继续保留；当前安装来源已经是主目录的改进分支，不能再沿用下方旧分支表推断来源。

提交时排除了运行data、原始.omo证据、App包、媒体、测试报告／截图、凭据及无关文档。提交后保留59条本地未提交路径，包括旧交接／功能文档、两个索引的既有差异、outputs、.DS_Store及带占位值的web/pnpm-workspace.yaml；暂存区为空。**本次这两份交接更新也留在工作区，未新增提交。**不执行reset、clean或批量暂存。

### 正式App与数据保护

| 项目 | 安装结果与本轮只读复核 |
| --- | --- |
| 安装位置 | [正式App](</Users/drm/Applications/Nyaru Clipper.app>)；1496个文件与已验收候选一致，深度／严格本地签名通过。 |
| 显示版本 | 仍为 **0.1.19 build27**，不能凭版本字符串区分新旧；当前native二进制SHA256为 `b7e5e0306fe9e44d413d6d9c916d46e5d2b60437187d3763cb46246e7f2d819f`。 |
| 安装来源 | 主目录证据中的 [phase8候选App](</Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/platform-qa/macos-clean-build/Nyaru Clipper.app>)；不是下方历史package-build27-final。 |
| 正式数据 | `/Users/drm/Library/Application Support/Nyaru Clipper/` 原地保留。安装时完整备份5793文件；重开后5792个非日志原文件字节不变，app.log旧前缀保持，只有一个新的startup就绪文件。配置、授权、模型及已有任务相关文件未覆盖，未导入隔离预览夹具。 |
| 运行状态 | 2026-10-21 **22:21 Asia/Shanghai**只读复核：正式native／helper运行，config与jobs HTTP200，runtime ready。任务列表**0**，与安装前一致；这不是安装丢失任务。 |
| 配置与授权 | 本地API报告translation／LLM已配置、ChatGPT connected；授权文件按字节保留，没有读取／输出秘密明文，没有重新登录、刷新授权或请求外部AI。此状态不等于已验证远程供应商可用性。 |
| 监控 | 本次未启动、恢复或修改录制／持续监控。此前nyaru的PAUSED属于旧记录，本轮未确认调度器当前状态；不得从缺少匹配本地配置推断其不存在或已恢复。 |

安装前正常退出了使用正式数据的旧构建和隔离预览，再备份／替换／重开；目前仅正式App留给用户查看。端口与PID是运行时状态，重开后应从当前helper的 `--ready` 文件重新发现，不复用旧验收端口。

### 备份与安装证据

私有备份：[20261021-221748-eight-phase-install](</Users/drm/Library/Application Support/Nyaru Clipper Backups/20261021-221748-eight-phase-install>)。

- `Nyaru Clipper-before.app`：本次替换前正式App，文件清单精确匹配。
- `data/`：停机后一致的完整Application Support快照，包含配置／授权；保持私有，不放入Git或分享。
- 如需回退，先退出全部Nyaru窗口与helper，仅在获准范围内恢复App。**不要用整份旧data覆盖后续新配置／任务，不恢复历史已永久清理的数据。**

[安装收据](/Users/drm/project/nyaru-clipper/.omo/evidence/formal-app-install-2026-10-21/installation.json)、[安装后核验](/Users/drm/project/nyaru-clipper/.omo/evidence/formal-app-install-2026-10-21/post-install.json)、[本轮运行快照](/Users/drm/project/nyaru-clipper/.omo/evidence/formal-app-install-2026-10-21/handoff-runtime-check.json)、[正式窗口重开截图](/Users/drm/project/nyaru-clipper/.omo/evidence/formal-app-install-2026-10-21/installed-reopened.png)及[提交保护收据](/Users/drm/project/nyaru-clipper/.omo/evidence/commit-eight-phases-2026-10-21/commit-final.json)均为本机证据，不随clone分发。下方build26／旧build27备份及原片归档记录仍作为历史保留，本次未重新核验其全部内容。

### 验收范围与接手事项

八阶段总账**44已验收／0待处理**，最终独立gate **APPROVE、specCompliance PASS、blockers=[]、codeQualityStatus WATCH**。同一冻结候选的最终记录：后端1357通过、前端327通过、TypeScript／Vite通过、工作站浏览器17项及平台22／22命令通过，另有真实HTTP／FFmpeg、CPU Docker、当前Mac构建及实际原生双任务保存／退出／同构建重开。5000条字幕完整保存，其余4999条精确不变；不同套件与历史阶段的计数不相加。提交与安装期间仅核对同一候选身份／数据及实际运行入口，未冒充又运行一轮完整套件。

真实GPU／CUDA／ROCm／AMF、模型推理、外部供应商／登录、完整Compose、掉电、全部字体、长时直播及全站响应式／深色／HIG仍未认证。既有维护债务、工具警告与 `db_migrations.py:107`／`test_subtitle_identity.py:216` 两处末尾空行保留WATCH。用户整体审美反馈仍待收集。

接手时先查看用户对正式App的反馈，再做明确范围的调整。暂不合并、不推送，不自动录制、重连直播、恢复监控或清空数据；任何新发布／真实外部AI验收均需另行明确范围。后续构建以主目录已提交实现为准，宿主机uv＋pnpm仍为主路径、Docker备用。检查Git状态后只处理明确文件，保留所有无关未提交内容和私有备份。

---

## 历史交接：2026-10-20（Asia/Shanghai）

本次仅更新文档并做只读核验；未启动 App、后端、录制或监控，未重跑测试、模型或外部 AI，也未提交／推送。下方带日期的旧记录仅说明当时状态，不能作为当前运行证据。

### 当前状态

| 项目 | 本次核验结果 |
| --- | --- |
| 安装版 | `/Users/drm/Applications/Nyaru Clipper.app` 为 **0.1.19 build27**；深度／严格本地签名校验通过。 |
| 运行状态 | 未发现该安装路径对应的运行后端，因此本次没有可查询的任务 API；`runs/` 下任务目录为 **0**。不把 10 月 17 日的“已启动”沿用为当前运行状态。 |
| 录制监控 | `nyaru` 状态为 **PAUSED**；继续保持暂停。 |
| 源码 | Studio 与此前采集／ASR 修复仍在功能工作树的未提交内容中；42 个共享前端／后端／测试文件逐字节一致。未查询远程 HEAD，不承诺远程已发布。 |
| 数据与回退 | build26 App 备份、对应数据备份及原片归档清单仍存在；本次未重新计算完整数据／媒体哈希。 |
| 验收边界 | 技术交付与安装已完成；整体审美仍待用户确认，真实直播下播、长期稳定性及 AI 语义质量未新增验收。 |

### 已实现与已有证据

- 日常模式：视频、时间轴、完整字幕、精简逐条编辑及导出；已完成任务状态区压缩，模式／设置往返保留任务输入和播放位置。
- 模板设计：独立草稿、实际 libass 样例预览、主播／工作系列、处理与导出默认值；自建模板同 ID 更新并增加版本，陈旧草稿报告冲突。
- 设置中心：通用、AI 与翻译、识别与处理、字幕与模板、文件与导出、运行环境六类；原生“设置…”菜单及 ⌘,。默认优先级为软件设置 → 模板默认 → 本次任务调整。
- 保留任务创建时的模板快照、独立字幕编辑稿和任务 ArcTime 工程绑定；设置／设计草稿互不串写。配置与授权继续使用既有路径，不输出凭据。

**以下均为 2026-10-17 的已完成验证，本次未复跑：**前端 86 项及类型检查／构建，macOS 后端 145 项、Web 后端 141 项；6 条真实界面／API 场景和 156 张最终截图；原生三页、随包 libass 预览与设置重启持久化。安装时 1519 个 App 文件与候选一致，5793 个原有数据文件完成保留校验。这些结果不等于今天重新核验全部数据，也不等于真实直播／模型质量验收。

使用说明：[创作工作台](companion-studio.zh-CN.md)；详细历史验收：[build27 交付与回退](companion-studio-acceptance-2026-10-17.zh-CN.md)。权威本机证据位于 [Studio 证据目录](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/studio-app-2026-10-17/)，包括 `final-receipt.md`、测试日志、`browser-qa.json`、两份 UI 审阅、`frozen-check.json`、`installation.json`、`post-install.json` 和原生截图。实际安装来源为 `package-build27-final/Nyaru Clipper.app`。

### 接手目录与复核

| 用途 | 分支／本次核验本地 HEAD |
| --- | --- |
| macOS 源码：`/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` | `codex/local-companion-macos` / `18ea3a0a7ee641cbb46d06d4348ebfa96dfc1dd2` |
| Web 源码：`/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` | `codex/local-companion-web` / `ccfb65176b3dd0451920694c5be17b19d856c0ff` |
| 主目录：`/Users/drm/project/nyaru-clipper`，保留旧工作站及其他改动 | `feat/arctime-pro-plugin` / `e8ea71085cf5c6ff6f671499872f5c166d31f89b` |

先检查功能工作树的 `git status --short` 和明确文件差异；不能只凭 HEAD 重建当前安装版，新增／未跟踪源码也必须保留。主目录不是已安装 Companion 的实现入口。

需要复跑时，在 macOS 工作树执行以下现有环境命令；本次没有执行：

```bash
cd /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper
PYTHONPATH=backend /Users/drm/.cache/nyaru-clipper/companion-venv/bin/python -m pytest -q backend/tests/test_studio_settings.py backend/tests/test_subtitle_templates.py backend/tests/test_subtitle_api.py backend/tests/test_subtitle_document.py backend/tests/test_companion_gui.py backend/tests/test_saozi_live.py backend/tests/test_macos_companion.py
cd web
./node_modules/.bin/vitest run src/companion
./node_modules/.bin/tsc -b
./node_modules/.bin/vite build
```

### 下一步与保护边界

1. 先由用户检查日常模式、模板设计和设置中心的整体效果；按反馈做有范围的调整。手机小字号和少量 token 命名为非阻塞整理项。
2. 如需真实直播／外部 AI 验收，另获授权后定义短时、有边界的场景；当前不得启动录制、重连直播或恢复持续监控。
3. 如需发布，另获授权后仅提交明确的 Web／macOS 功能文件及成对文档，再核对远程分支；不自动提交、合并或修改 master。

私有回退目录：`/Users/drm/Library/Application Support/Nyaru Clipper Backups/20261017-033319-before-build27/`，包含 `Nyaru Clipper-build26.app` 与 `data/`。回退前退出 App，仅按批准范围替换 App；不要用整份旧数据覆盖当前配置／模板，也不要恢复已永久清理的任务。原片归档入口仍为 `/Users/drm/Movies/Nyaru Clipper/原始录播/20261017-014802/`。备份中的配置／授权、日志与模型／媒体不进入 Git，不读取或输出 `runs/config.json`、`runs/.chatgpt/` 中的秘密值。

---


## 2026-10-17 build26 核验与清理记录（历史）

以下内容核验于 **2026-10-17，02:08 Asia/Shanghai**。保留清理来源与修复证据；其中“当前／本次／已安装”均限于该历史时点，今天状态以上方 2026-10-20 交接为准。旧任务路径和“完整数据备份”描述已被本节清理结果取代。

### build26 时点状态与边界

- 已安装并运行 **0.1.18 build26**：`/Users/drm/Applications/Nyaru Clipper.app`。本次从运行后端的 `--ready` 文件发现回环地址，查询 `/companion-api/jobs` 返回空列表；App 的 `runs/` 中没有任务目录，也没有采集／Whisper 进程。
- 持续监控 `nyaru` 为 **PAUSED**。用户明确要求不重新开启录制或持续监控；本次仅更新文档并做一次只读核验。
- 历史任务、识别／翻译、切片、样式导出和任务备份已按用户授权清理；只保留下述归档原片。**不得根据历史交接自动恢复任务、重连直播或重新生成派生产物。**
- build26 已在本机安装，后续修复源码尚未提交／推送。构建、安装、真实尾段补全和公开发布是不同状态；本轮没有提交、推送、合并或公证。

### 原片归档与永久清理

归档入口：[原始录播目录](</Users/drm/Movies/Nyaru Clipper/原始录播/20261017-014802>)；[原片清单及 SHA256](</Users/drm/Movies/Nyaru Clipper/原始录播/20261017-014802/原片清单.json>)。

共 **14 个媒体文件、3,026,261,061 字节**：`完整原片/` 下 13 个整段源文件，以及 `未列入封口清单的原始块/` 下 1 个原始块。重复源按 SHA256 去重，清单保留来源映射。任务 `4be6301526e0` 的 15 个已关闭块通过 stream copy 合成整段文件，没有转码；当时逐个核对视频／音频编码包哈希序列一致。额外原始块来自 `64a7f4accfed`，原先未列入 `closed.csv`，仅按原样保留，不宣称它完整或解码正常。

已永久删除刚移入废纸篓的 **27 个任务**，及 10 批旧数据备份中的 **226 份任务副本**；只针对这些任务目录，其他废纸篓文件、备份中的配置／模板／授权等非任务内容、App 与安装包备份保留。逻辑删除 109,335,161,117 字节，实际观察可用空间增加约 9.31 GB；APFS 共享数据使两者不同。

本次重新核对全部 14 个归档媒体的大小／SHA256 和清单哈希，均一致；上述废纸篓目标及 226 份备份任务路径均不存在。权威清理回执：[permanent-cleanup.json](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/task-cleanup-2026-10-17/permanent-cleanup.json)。此前安装／补全回执只描述当时保留情况，其中的 `runs/<任务ID>` 链接已失效；证据目录不是完整任务备份，不能据此承诺可恢复。

### 已安装修复与限制

| 范围 | 实现、结果及边界 |
| --- | --- |
| 第 8 片字幕／样式 | 使用原始精度 cue 决定切片归属，避免 SRT 毫秒舍入造成 18／19 条不一致；确定为旧生成器产物且哈希匹配时才备份并修复，用户改动冲突仍拒绝。单片样式失败后继续后续片段，保留错误汇总。 |
| 花屏与解码检测 | 旧 HEVC 录制源本身缺失参考图像，FFmpeg 即使退出 0 也会报告解码错误。新采集严格选择 `best[vcodec=avc][protocol=https][ext=flv]`，不静默回退 HEVC/HLS；AVC/FLV 实测 150.095 秒／8 块完整解码通过。新增 `video_integrity.py` 对已关闭块完整解码，同时检查退出码和错误输出，在任务记录 `video_decode_error`／`capture_warning`。检测用于告警，不能修复旧源；归档中保留的旧 HEVC 花屏仍可能存在。上游丢包与 HLS 解复用跳过的贡献尚未完全分离。 |
| 直播正常结束 | 采集退出或解析失败后，在现有有限重连尝试中查询房间状态；仅明确整数 `live_status=0/2` 记为 `live_ended`。未知／异常／仍开播不冒充正常结束，用户停止优先。保存 `capture_end_reason` 并保留既有警告；独立 ASR／导出失败仍为 failed。真实 FFmpeg EOF 场景和当时房间离线查询通过，修复后未观察到新的真实下播事件，不能倒推旧任务失败原因。 |
| ASR 尾段越界 | 保留时间戳校验；仅初次结果越界时，以同一 WAV、Whisper small、语言及线程配置做一次 VAD 重试，要求新产生有效字幕，允许经检测的无语音空结果。缺输出、进程失败、再次越界或 VAD 模型校验失败仍报错，不缓存假成功。macOS 子进程固定使用随包 OpenMP 库，解决 VAD 时混载系统／随包库导致的崩溃。 |
| 模型／打包 | 主 Whisper small 与 DeepSeek Flash 不变。辅助 `ggml-silero-v6.2.0.bin` 为 885,098 字节，SHA256 `2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987`，来自官方模型仓库固定版本并附 MIT 许可；打包消费已验证本地文件，不下载模型，输入文件名可变但包内名称固定。 |

### 尾段补全结果（已清理的历史任务）

| 原任务 → 补全副本 | 清理前验证结果 |
| --- | --- |
| `34c7512544cd` → `7dcf0cb825d2` | completed，270 块、5390.152233 秒、63 片、翻译 1417/1417；保留原 1369 条翻译并补 48 条。仅恢复副本移除旧样式配置，未对全部旧片重新烧录；旧源花屏未修复。 |
| `4be6301526e0` | 曾因 ASR 时间戳失败，未完成识别补跑；其 15 个已关闭录制块已无转码合并归档，不能写成识别／翻译已补齐。 |
| `bc4572ea33da` → `934c984a3d33` | completed，140 块、2788.007993 秒、31 片、翻译 772/772；原 138 块、29 片和 761 条翻译未覆盖，并补全此前 10 条已识别未发布翻译。倒数第二块 VAD 无语音，最后一块音乐提示正常翻译。 |

最近补全时所有双语条数、登记哈希及 62 个样式产物哈希通过；新增两片与对应两份烧录视频完整解码通过，音乐字幕帧已目视核对。**这些任务目录、字幕和派生视频随后已按清理要求永久删除，目前只保留原片及脱敏验收记录。** 以上是清理前完成结果，不代表当前 App 中仍有可打开任务；译文没有逐句人工校对。

### 源码、验证与接手入口

| 工作目录 | 当前分支／本次核验本地 HEAD |
| --- | --- |
| `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper` | `codex/local-companion-macos` / `18ea3a0a7ee641cbb46d06d4348ebfa96dfc1dd2` |
| `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper` | `codex/local-companion-web` / `ccfb65176b3dd0451920694c5be17b19d856c0ff` |
| `/Users/drm/project/nyaru-clipper` | `feat/arctime-pro-plugin` / `e8ea71085cf5c6ff6f671499872f5c166d31f89b`，仅同步交接；保留其他未提交内容 |

修复位于两功能工作树的 `backend/app/arctime/`、相关测试与 `web/src/companion/companionApi.ts`；macOS 另含 `scripts/build_macos_app.py` 和 `desktop/macos/silero-vad-LICENSE.txt`。两端共享 ASR 源码／测试一致；主目录旧工作站代码不是已安装 Companion 的源码入口。上表 HEAD 不包含这些未提交修复；本次未查询远程 HEAD，不引用旧发布记录作为当前远程状态。

最近 ASR 套件两端各 **31 项通过**；相关七文件套件此前 **124 项通过**，之后补充了 3 项错误路径用例，覆盖数不相加。最终冻结包代码与验证源码一致，深度／严格签名通过，真实 CLI 音乐负例 0 条、语音正例 4 条。仅 `package-build26-final` 已安装，早期候选不是交付包；现有 Starlette/httpx 弃用警告保留，LSP 未按用户选择安装。本次文档更新不重跑模型／完整回归，不创建任务。

本机证据入口（历史回执中的运行任务路径须结合上述清理状态阅读）：

- [HEVC 诊断与 AVC 对照](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/hevc-root-cause-2026-10-16/README.md)、[字幕边界修复](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/subtitle8-decode-fix-2026-10-16/README.md)、[旧尾段补全](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/old-tail-recovery-2026-10-16/README.md)。
- [下播识别实现／验收](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/live-end-recognition-2026-10-17/README.md)、[ASR/VAD 实现／验收](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/asr-tail-recovery-2026-10-17/README.md)、[最终包验证](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/asr-tail-recovery-2026-10-17/package-verification.json)、[补全回执](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/asr-tail-recovery-2026-10-17/recovery-completion.json)、[媒体验证](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/.omo/evidence/asr-tail-recovery-2026-10-17/media-verification.json)。

接手先读本节和清理回执，再检查功能工作树未提交差异。若另获授权发布，按明确文件范围提交和推送开发分支，保留主目录其他改动；不自动安装／回退旧候选、不利用旧备份恢复已清理任务。App 端口从当前后端 `--ready` 文件发现，不启动第二个服务。供应商配置／授权仍为秘密，不读取或输出其值。后续真实直播下播与长期稳定性验收需用户另行授权，**当前无录制、无持续监控**。

## 2026-10-16 及更早交付记录（历史）

以下正文保留当时的发布、安装和验收记录；其中“本轮／当前／保留”均限于记录时点，不覆盖上方 2026-10-17 状态。旧数据备份现仅保留非任务内容，不再是完整任务备份。

## ASS 模板与 build18 开发分支发布（历史）

本轮包含 ASS 样式导入、直播模板快照、逐段样式导出与猫雷内置／默认样式。只发布 `codex/local-companion-web`、`codex/local-companion-macos`；主目录其他未提交内容保留。本地及远程 master 基线为 `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`。

| 开发分支 | 功能提交 | 打包提交 |
| --- | --- | --- |
| `codex/local-companion-web` | `09acdc420ed7f0b8ecd10a84672d3613770281ed` | 不适用 |
| `codex/local-companion-macos` | `6040ca9415e07357993eba3f5b3ee21c5ec47182` | `fbd7d5b2df40cba1619a99c6cdac1c56727494ee` |

双语交接、使用说明、计划与验收记录随后作为文档提交，因此上表不是最终分支 HEAD。使用显式 refspec 与 `--atomic` 推送；最终远程比对回执保留在 macOS 工作树 `.omo/evidence/nyaru-default-build18-2026-10-16/publish-receipt.json`。接手时运行 `git ls-remote origin refs/heads/codex/local-companion-web refs/heads/codex/local-companion-macos refs/heads/master` 核验。

发布前复测：macOS 相关后端 231 项、Web 前端 77 项与生产构建通过；两端 27 个共用源码／测试文件逐字节一致。此前 macOS 前端、冻结运行时、原生界面与数据保留验收见下文。任务数据、媒体、模型、凭据、备份和二进制安装包均不进入 Git。本次未重跑真实 Bilibili／外部 AI，不包含公证或分支合并。

## 此前本机版本：0.1.10 build18（历史）

猫雷「薄荷电波」已内置并设为本机默认样式；实时录播默认选择该模板，可取消自动套用。新版已打包、替换安装并启动，包含 ASS 样式导入与逐段样式导出。20 个历史任务保留，供应商配置与授权状态不变；启动后原有数据仅默认字幕文件按要求改变。旧 build17 与完整数据备份位于 20261016-174807 目录。详见[build18 验收与备份](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/docs/nyaru-default-build18-acceptance-2026-10-16.zh-CN.md)。

本轮功能提交及发布核验见上文；master 不变。以下 build17 发布与安装记录为历史。

## 此前 build17 开发分支发布（历史）

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

## 此前本机安装：0.1.9 build17（历史）

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

## build16 安装、回退与数据保留（历史）

当时安装版为 **0.1.8 build16**，位于 `~/Applications/Nyaru Clipper.app`。该轮重新构建前端、冻结后端及工具／模型、编译 Swift 窗口并本地签名；严格签名和 Swift 类型检查通过。安装时无运行任务，正常退出 build15 后替换并成功打开 build16。

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
