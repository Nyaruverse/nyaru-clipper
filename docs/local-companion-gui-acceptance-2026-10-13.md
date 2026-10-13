# 本地配套工具图形界面验收

日期：2026-10-13。分支：`feat/arctime-pro-plugin`。本轮新增独立的 localhost 浏览器界面，复用已有 yt-dlp、whisper.cpp 和 FFmpeg 本地流水线；改动尚未提交。

## 已交付

- 链接输入、语种选择、多个指定时间段或高光自动切片。
- 后台串行处理，实际阶段及逐片导出消息；失败恢复和持久化任务记录。
- 原视频／切片播放器、WebVTT 字幕、点击字幕跳转原视频、切片时间轴。
- 完整 SRT／TXT 和逐片 MP4／SRT 下载；支持视频 Range 请求。
- 本机回环绑定、同源与 Host 校验、结果文件白名单及目录／符号链接检查。

运行方式见 [中文使用指南](local-companion.zh-CN.md)。前端是 `web/companion.html` 独立构建入口，服务是 `backend/app/arctime/gui.py`，启动命令是 `scripts/local_companion.py gui`。不启动旧工作站数据库，不调用 ArcTime 付费功能或外部推理接口。

## 自动回归

后台所选 **99 tests passed**，包含 GUI 新增 19 个用例和已有本地流水线／导出回归。前端全部 **137 tests passed（21 files）**，含 GUI 新增 5 个用例。在 `web` 目录执行 `corepack pnpm build` 的 TypeScript 检查和双入口 Vite 构建通过。

```bash
cd backend
/tmp/nyaru-arctime-tests/bin/python -m pytest tests/test_companion_gui.py tests/test_local_companion_cli.py tests/test_arctime_workflow.py tests/test_local_asr.py tests/test_arctime_media.py tests/test_arctime_desktop.py tests/test_highlights.py tests/test_export_encoding.py -q
```

```bash
cd web
corepack pnpm test --run
corepack pnpm build
```

先红后绿覆盖了坏目录导致历史接口失败、超时异常泄露下载链接、首次详情失败不重试、环境错误丢失、CLI 恢复后残留 GUI 错误，以及任务列表轮询滞后导致表单继续禁用的问题。独立只读审阅结论 **WATCH / APPROVE，blockers: []**；非阻断项为进一步收紧手写类型契约。

## 真实浏览器与媒体验收

使用本机 HTTP 提供的 20.4 秒合成中文语音视频，运行真实 yt-dlp、已安装的多语种 small GGML 模型和 FFmpeg；没有替换下载、ASR 或导出函数。使用 Chrome + Python Playwright，最终两个任务均观察到 `preparing → downloading → transcribing → exporting → completed`。

| 模式 | 最终任务目录 | 结果 |
|---|---|---|
| 指定 2–8 秒、10–16 秒 | `data/local-runs/e42790586570` | 两个 6 秒 MP4 和从零计时的配套 SRT |
| 最多两个高光 | `data/local-runs/2b46c356913c` | 一个 20.4 秒片段，评分 0.77 |

浏览器实际操作通过：反向时间段拒绝、提交两种模式、阶段更新、切片切换、WebVTT cues 加载、视频静音播放时间推进、字幕时间跳转、MP4／SRT 下载、刷新后查看历史、切换历史任务，以及 390px 布局无横向溢出。未出现 JavaScript pageerror。

前一轮同素材任务 `4beb340e0219`／`061b0ecce533` 的全部切片经过 FFprobe 音视频流与时长检查、FFmpeg 完整解码；格式为 H.264 + AAC。浏览器下载文件也成功保存并检查内容。验收脚本在 `.omo/evidence/local-gui-browser-qa.py`；截图为 `.omo/evidence/gui-ranges-desktop.png`、`gui-highlights-desktop.png`、`gui-mobile.png`。本机 headless Chrome 出现非静音播放停滞，静音后时间正常推进；因此播放验收使用静音，音频编码和解码另行核验，未验收扬声器输出。窄屏截图用独立的 390px 浏览器页面采集，避免缩放已有视频页面的全页截图采集伪影。

## 边界

这是本机短样例的完整流程验收，尚未覆盖公共站点登录／下载限制、真实长视频识别质量、长素材资源使用或 Linux 执行。高光依旧基于字幕规则，不是画面分析或大模型语义筛选。句级识别字幕仍需人工校对。没有新增暂停／取消或批量排队功能。旧工作站的其他未提交改动未在本轮重做或发布。
