# 高光流程修复与真实复测 — 2026-10-26

当前正式安装：`/Users/drm/Applications/Nyaru Clipper.app`，**0.1.21 build 33**。沿用原 `unified/runtime.json`、凭据路径、模型和数据。处理、Web 媒体复测通过；原生 App 的视频画面与正常播放已由用户在本对话中现场确认。验收证据区分自动检查与用户目视确认。

## 已完成的修复

- 翻译就绪判断区分 `saved-document` / `existing-result` 来源标记与真实供应商模型，保留实际授权、Key 错误及旧任务供应商约束。
- whisper.cpp 输出实际语言 JSON，按有效语音时长汇总、随分块缓存校验并绑定原片摘要；识别请求 `auto` 保持原样，已校验字幕结果中的实际 `ja` 进入后续翻译上下文。
- 增加明确的 `recognition_only` 处理入口。统一工作台新建录像先识别、再审阅高光，不再无关地提前生成 00:00–00:30 切片；手动范围、旧兼容与实时流程保留。
- 高光指令从完整话题划分改为挑选精彩瞬间，目标约 40% 时长；允许完整字幕句边界，超过 max(60 秒, 所选范围 50%) 的整段覆盖结果被拒绝。此策略不代表主观高光质量已普遍验收。
- 单段／组合成片可直接在工作台预览，使用成片本身的字幕与时间；原片循环、编辑层和时间轴不叠到成片上。可返回原片。
- 760×560 下固定可见的视频、输入滚动留白与完整工具文案；390×844 下成片不再被容器裁切。
- 页头显示保存的任务标题与安全来源标签；修改任务标题立即刷新页头；空编辑版本不再显示 vnull；识别后的空导出状态不再误报“未达到高光阈值”。
- 按任务保存同源浏览器审阅草稿，覆盖刷新／页面往返；损坏及配额失败有回退／提示，新分析会清理旧范围。

## 实际复测

沿用同一段真实录播 `直播-1276274cd22d.mp4`，时长 **328.300 秒**、1280×720。不是合成视频、假字幕或模拟供应商。

最终任务：`7a69c98888d15620b3aa11e9fba5dbc9`，界面标题 `真实高光完整复测 · build30 · 自动日语`。

1. 原生文件选择器导入原片，保持自动语言，点击加入／启动队列。
2. 实际本地 ASR 生成 **50 条**字幕，保存语种 **ja**，没有提前切片。
3. 直接点击原生翻译入口，使用现有 DeepSeek / deepseek-flash 配置，真实翻译 **50/50 条**，保存编辑稿 v1；没有接口补译绕过。
4. 点击原生分析按钮，完整覆盖 50 条字幕，得到 **4 个候选，共 131.800 秒（40.15%）**，没有凑满 5 段。无弹幕时评分仍诚实显示不可用。
5. 倒序选择 `[2, 0]`，确认范围 `272.9–315.0` 与 `141.4–204.7`，选择组合／双语后点击加入生成队列。四项操作均 `succeeded`。
6. Web 页面实际播放、下载两个单段和组合视频；完整 FFmpeg 解码均通过。两段为 **42.100 / 63.300 秒**，组合为 **105.421333 秒**，H.264 + AAC、1280×720。帧检查确认先 N2 听力话题、后未读消息，字幕已烧录。
7. 成片计时从零开始；没有原片字幕层或循环干扰。原片 300–303.2 秒循环仍有效，关闭循环后恰在 303.2 秒暂停。同源刷新可恢复勾选及调整范围。
8. 最终 build 33 复核 760×560、390×844、桌面播放。build 30 完成上述真实处理；后续 build 31–33 只有样式和构建号微调，后端 Python 源码与前端 JS 内容摘要相同，最终布局重新抓图确认。

本次保留了中间任务 `f98b6a7d...` 的失败分析：初版严格 40% 上限误拒绝完整句边界。没有删除失败记录或把它算为通过。

## 验证收据

证据目录：`/Users/drm/.codex/worktrees/highlight-subtitle-macos/nyaru-clipper/.omo/evidence/watch-workbench-fixes-20261026/`。

| 验证 | 证据 |
|---|---|
| 前端全套 365 项通过；类型／构建通过 | frontend-final.txt；build-33.log |
| 后端相关 139 项通过，原生／翻译集成 32 项通过；边界修正另 62 项 | web-backend-final.txt；integration-tests.txt；cue-budget-green.txt |
| 实际任务、供应商、队列与版本 | final-install-runtime.json；final-operations.json |
| 完整媒体解码、冻结范围／顺序 | final-media-validation.json；real-bilingual-*.mp4；first-frame.jpg；second-frame.jpg |
| 布局、播放及刷新 | compact-build33.json；phone-build33.json；final-web-playback.json；review-reload.json；source-loop-*.json |
| 保护原数据和设置 | data-preservation.json；before-install.json；final-install-runtime.json |
| 代码审阅及平台差异保留 | review.md；frontend-report.md；shared-fix.patch；source-sync.json；polish-equivalence-final.json |

## 数据、回退及边界

**21 个原有活动文件**、**2 个旧任务上下文**及原片摘要均未变；默认字幕样式、模板／工程、工作流设置响应摘要与安装前一致，运行时清单字节一致，SQLite quick_check 为 ok。队列已暂停。当前保留 4 个真实测试任务，未删除旧数据、修改凭据、下载模型、触碰旧封存来源或恢复 pin，也未提交／推送。

安装前备份：`/Users/drm/Library/Application Support/Nyaru Clipper Backups/workbench-fixes-20261026-1723/`，保留 `Original installed App.app`（0.1.20）及 `unified/` 快照。回退时先正常退出并保留最新运行时；只切换 App，不用旧快照覆盖后续新数据。

- **原生媒体已由用户目视验收**：用户直接回复“可以看到并正常播放”（`native-human-acceptance.json`）。自动化能够操作生成／播放入口并观察 Play→Pause，HTTP 范围请求为 206；原生抓图仍为黑屏且坐标工具报 noWindowsAvailable，因此原生画面结论来自用户确认，不冒充自动像素检查通过。Web 画面、整段自然播放结束和完整文件解码由自动检查确认。
- 原生每次启动使用不同端口，同源 localStorage 草稿不会跨 App 重启恢复；已导出的范围和成片仍保留在服务端。旧 `auto` 任务缺少语言结果时不猜测或追溯改写，应重新识别；新复测任务可直接使用。
- 未逐句验收 ASR／译文、长期直播／长 VOD、系统深色模式、Windows／GPU、故障恢复或公证。字幕仍需人工校正，候选仍需看片确认。
