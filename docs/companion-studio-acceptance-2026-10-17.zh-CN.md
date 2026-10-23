# Studio 界面交付记录

2026-10-17，macOS 本机安装版为 **0.1.19 build27**，位置 `/Users/drm/Applications/Nyaru Clipper.app`。状态为已实现、已验证、已安装；整体审美仍待用户验收。本轮未提交、推送、合并或公证。

## 交付内容

- 浅色工作台、薄荷色重点和顶部日常／模板设计滑块。日常模式保留视频、时间轴、完整字幕与精简逐条编辑；已完成任务状态收为紧凑行。
- 独立模板设计草稿、真实 libass 样例画布、主播／工作系列、处理与导出默认值、模板版本。更新已有模板保留同一身份并增加版本，过期草稿报告冲突。
- 六类统一设置和原生“设置…”菜单（⌘,）。设置中心草稿与模板设计草稿隔离；任务保持创建时的模板快照。默认优先级为软件设置、模板、任务调整。
- 已有 AI 授权与配置、任务编辑稿、ASS／字幕 MP4／ArcTime 路径复用。任务的 ArcTime 工程绑定独立于设计草稿。

使用说明：[创作工作台](companion-studio.zh-CN.md)。macOS 源码在 `codex/local-companion-macos` 工作树；共享功能已同步到 `codex/local-companion-web`，保留两端此前未提交的采集／ASR 修复。

## 验证

| 范围 | 已观察结果 |
| --- | --- |
| 前端 | 最终 86 项 Companion 测试、TypeScript 和生产构建通过；Web 工作树同步后同套 86 项通过，最终布局的类型检查／构建再次通过。 |
| 后端 | macOS 相关七文件 145 项通过；Web 同步后六文件 141 项通过。保留 Starlette/httpx 弃用警告。 |
| 真实界面与 API | 隔离目录中创建模板、同 ID 版本更新、预览随样式变化、模式往返保留输入和播放位置、默认设置保存重载、字幕自动保存及实际 ASS 导出、原生设置事件通过。 |
| 画面 | 13 个状态，390／1440／1920 宽，明／暗系统偏好，顶部／底部共 156 张新截图；文档与侧栏无横向溢出。界面按用户选择保持浅色；390 为辅助 Web 回归，不是移动端原生字号验收。 |
| 安装包 | 最终冻结包真实启动、libass 返回 1920×1080 PNG、设置重启持久化、8 个 Web 资源逐文件哈希一致；深度／严格本地签名通过。 |
| 原生 App | 安装后日常空态、模板样例 PNG、⌘, 设置中心、运行环境就绪均在实际 WKWebView 验证。 |
| 数据 | 替换前完整备份，安装副本 1519 个文件与最终候选一致；原有 5793 个数据文件校验，仅运行日志／启动文件允许变化。配置、授权、模板与模型未改变；生产任务仍为 0。录制监控仍为 PAUSED。 |

证据位于 macOS 工作树 `.omo/evidence/studio-app-2026-10-17/`：`browser-qa.json`、`screens/`、`frontend-compact-verification.log`、`backend-parent-final.txt`、`frozen-check.json`、`installation.json`、`post-install.json`、`ui-integrity-review.md`、`ui-visual-review.md`，以及 `native-daily.png`、`native-design.png`、`native-settings.png`。最终候选是 `package-build27-final/Nyaru Clipper.app`，早期候选不是安装来源。

## 备份与边界

私有备份目录：`/Users/drm/Library/Application Support/Nyaru Clipper Backups/20261017-033319-before-build27/`，含 `Nyaru Clipper-build26.app` 与 `data/`，目录权限 0700。回退前退出 App，仅替换 App 即可；不要把整个旧数据目录覆盖回去。`data-manifest.json` 留在私有目录中，不纳入仓库。

历史任务的永久清理仍有效，未恢复或创建生产任务，未启动录制。隔离 QA 的合成短视频仅用于编辑／导出链路。没有重新运行真实直播、外部 AI 或完整模型推理；不据此宣称识别／翻译质量或其他平台已验收。保留少量非阻塞样式 token 命名整理事项，不影响本版操作。
