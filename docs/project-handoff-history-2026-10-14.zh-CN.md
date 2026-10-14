# 历史交接快照 · 2026-10-14

以下完整保留整理前的交接原文，仅用于追溯各阶段观察。当前状态请阅读[当前交接](project-handoff.zh-CN.md)。

---

# 本地工具网页版交接

**本轮 Git 提交范围（2026-10-14）**：本次将双语翻译、Key／模型持久配置、App 0.1.4 打包及配对技术验收记录提交到三个既有开发分支。较早段落的未提交／未推送保留其观察日期；准确当前源码及远程 HEAD 以 `git log -1`、`git ls-remote origin` 为准。私密配置、媒体、模型、构建包及 `.omo` 证据留在本机。

**双语字幕补充（2026-10-14）**：共享配套工具已支持 DeepSeek 日译中双语字幕、Key／模型私密持久配置、Flash／V4 Pro 选择、批次续传及完整／切片预览导出。安装版 App 0.1.4 已翻译既有 658 和 1448 条字幕，86 个原文件保持不变；原时间轴、6 个切片偏移、8 份下载／预览、原生完整视频／切片播放及 SRT 导出通过。见[真实验收](deepseek-real-translation-acceptance-2026-10-14.zh-CN.md)和[指南](deepseek-bilingual.zh-CN.md)。较早记录中的真实翻译待验收保留其历史范围；全部译文仍未逐句校对。

**远程同步补充（2026-10-14）**：当前源码及文档已提交并推送至 `origin` 的三个开发分支：`feat/arctime-pro-plugin`（包含原目录工作站改动及完整开发记录）、`codex/local-companion-web`、`codex/local-companion-macos`。本次功能提交已远程核验为 `d4f28f9`、`5baf166`、`1366686`；后续交接文档提交的最新 HEAD 以 `git log -1`／`git ls-remote origin` 为准。下文“未提交／未推送”、旧分支 HEAD 与原目录脏工作区说明均为较早快照，以本段为当前 Git 状态。App 保留网页版的共享修复；`master` 未修改。

本次同步前复核：原目录 143 项所选后台、137 项前端测试和 7 项浏览器端到端测试通过，前端构建通过；网页版 95 项、App 版 99 项后台回归通过，0.1.1 包严格签名及旧适配器 Swift 编译通过。16 个脚本的原有可执行权限已恢复，Shell 语法检查通过。模型、媒体、构建包、私密配置和自动化临时证据留在本机。未重跑真实媒体／原生按钮验收，也不代表已完成公证或正式发布。

更新：2026-10-14。当前开发已按运行方式分为两个分支：

| 分支 | 范围 |
| --- | --- |
| `codex/local-companion-web` | 本地 CLI、浏览器界面、下载、字幕与句级时间轴、指定／高光切片、进度、预览、导出和恢复 |
| `codex/local-companion-macos` | 继承网页版核心，增加 AppKit/WKWebView、原生保存、进程清理、内置模型与工具、自包含 App 构建 |

两个分支以 `0bcd8d5` 为共同原始基线；App 分支基于网页版提交。共享功能修复先在网页版完成，再同步到 App 分支。不会调用 ArcTime 付费服务。原目录 `feat/arctime-pro-plugin` 的未提交快照及更早工作站改动保留；模型、视频、任务、配置和构建产物不纳入提交。当前只整理本地 Git，未推送远程。

## 运行与源代码

按 [本地使用指南](local-companion.zh-CN.md) 安装独立 Python 环境、FFmpeg、yt-dlp、whisper.cpp 和多语种 small 模型。在本分支根目录执行：

```bash
cd web
corepack pnpm install --frozen-lockfile
corepack pnpm build
cd ..
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py doctor
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py gui
```

打开 `http://127.0.0.1:8787/`。构建后本地服务提供独立 `companion.html`；原工作站不用启动。默认任务在当前分支目录的 `data/local-runs/`，不会自动迁移原目录或 App 历史。可用 `gui --output-dir /原任务根目录` 指定已有历史；切勿同时启动两个服务写同一任务。

```mermaid
flowchart LR
    U[视频链接] --> D[yt-dlp 下载]
    D --> A[FFmpeg 提取音频]
    A --> W[whisper.cpp 本地识别]
    W --> T[完整字幕和句级时间轴]
    T --> R[指定时间段或字幕规则高光]
    R --> E[MP4 和从零计时的 SRT]
    E --> P[浏览器预览和下载]
```

入口在 `scripts/local_companion.py`；核心在 `backend/app/arctime/{cli,workflow,local_asr,media,gui}.py`，前端在 `web/src/companion/`。`arctime` 是沿用的目录名；早期桌面适配器没有进入本分支。复用已有高光、字幕和 CPU 导出服务，不包含旧工作站新增改动，也不包含 App 专用源码。

## 验证与边界

2026-10-14 在本分支独立工作目录验证：后台所选 **84 passed**，前端 **154 passed（21 files）**，TypeScript／双入口 Vite 构建成功，CLI `doctor` 返回 ready。前端数量与历史报告不同，因为没有合入原目录更早的工作站修改。后台出现 Starlette/httpx 弃用提示，未导致失败。复现命令：

```bash
PYTHONPATH=backend ~/.cache/nyaru-clipper/companion-venv/bin/python -m pytest \
  backend/tests/test_arctime_media.py backend/tests/test_arctime_workflow.py \
  backend/tests/test_local_asr.py backend/tests/test_local_companion_cli.py \
  backend/tests/test_companion_gui.py -q
cd web
corepack pnpm test --run
corepack pnpm build
```

[CLI 验收](local-companion-acceptance-2026-10-12.md) 和 [GUI 验收](local-companion-gui-acceptance-2026-10-13.md) 保留其历史分支、测试选择和观察日期，不代表新分支已重跑真实媒体操作。历史 `.omo/evidence/`、模型和任务是原开发目录本机产物，不随 Git 提交分发。

下载失败须重新提交链接；下载后识别／导出中断可以恢复。保留模型、任务清单、输出和失败日志。当前高光是字幕规则，字幕是句级识别；未提供词级对齐、说话人区分、画面或大模型语义高光。公共站点受限下载、真实长视频、Linux 和跨机器表现尚未验收。禁止恢复付费 ArcTime 调用、手改运行数据或把服务公开到互联网。
