# 本地视频配套工具

输入一个视频链接，自动下载、在本机生成字幕文字和时间轴，再按指定时间段或高光评分导出切片。提供本地浏览器图形界面和命令行；GUI 另支持可选 DeepSeek 双语翻译、[字幕样式、两类模板、ASS、烧录与 ArcTime 精修交接](subtitle-styles.zh-CN.md)。识别和切片在本机进行；ArcTime 采用文件交接，不调用其云转写。

## 图形界面

顶部「新建任务／切片方式／字幕样式／AI 设置／任务记录／导出」点击后在右侧展开，再点同一入口收起；也可点击关闭按钮或按 Escape。切换入口保留已填写内容和本地文件选择。进度与直播停止按钮始终位于主工作区。见[本次界面验证](toolbar-drawer-acceptance-2026-10-16.zh-CN.md)。

双击启动且内置工具及模型的版本见 [macOS 分支的 App 指南](https://github.com/Nyaruverse/nyaru-clipper/blob/codex/local-companion-macos/docs/macos-app.zh-CN.md)。

在项目根目录执行。首次构建界面需要 Node.js 20 以上和项目指定的 pnpm；Corepack 会使用 `web/package.json` 指定的版本。

```bash
cd web
corepack pnpm install --frozen-lockfile
corepack pnpm build
cd ..
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py gui
```

打开 [本地视频工作台](http://127.0.0.1:8787)。本开发机已安装依赖并完成构建。修改前端源码后需重新构建；无需启动原工作站数据库或 GPU 后端。

1. 在「新建任务」选择「实时录播」「下载视频」或「本地视频」：分别输入 Bilibili 直播间号、BV 号或选择本地视频文件。只需填写编号，程序自动生成地址；切换来源保留各自输入。
2. 下载视频和本地视频可在「切片方式」选择指定时间段、高光自动切片或臊子。实时录播固定使用臊子，需先配置 AI；切回视频后恢复此前切片选项。本地视频导入独立副本，原文件不修改。指定时间段和高光不要求 AI 授权。
3. 点击「开始处理」，查看环境检查、下载、字幕识别和逐片导出进度。进度来自实际阶段，不显示估算百分比；一次处理一个任务。
4. 下载结束后可预览原视频。完成的片段会陆续出现；播放器可显示识别字幕，点击完整字幕的时间可跳转原视频，点击切片时间轴可切换预览。
5. 下载完整 SRT／TXT，或每段 MP4 和配套 SRT。任务记录在刷新页面和重启服务后保留。

识别或导出失败时点击「恢复处理」；下载失败需要重新提交链接。关闭浏览器页面不会终止后台任务，运行期间保留启动终端。`gui --port 8788` 可换端口；`--output-dir`、`--model`、`--threads` 可指定目录、模型和线程数。服务仅绑定本机回环地址。

## 本机直接使用

在项目根目录执行。当前开发机的独立 Python 环境和 `small` 多语种模型已准备在用户缓存目录中：

```bash
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py doctor

~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py run '视频链接' --language zh --range 00:01:20 00:02:00 --range 180 210

~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py run '视频链接' --language zh --highlights 3

~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py resume 'data/local-runs/任务目录'
```

`--range` 支持秒数、MM:SS、HH:MM:SS.mmm，可重复。指定片段和高光模式互斥，范围必须落在视频时长内。`--output-dir` 指定任务输出根目录；`--model` 指定本地 GGML 模型；`--language` 默认 `auto`，可设为 `zh`、`en`、`ja` 等 Whisper 语种代码；`--threads` 默认 4。

## 新机器安装

需要 Python 3.11、uv、FFmpeg、yt-dlp 和 whisper.cpp 的 `whisper-cli`。Python 环境独立于后端，不需要 GPU 工作站或数据库。

```bash
uv venv --python 3.11 ~/.cache/nyaru-clipper/companion-venv
uv pip install --python ~/.cache/nyaru-clipper/companion-venv/bin/python 'pydantic-settings>=2.6,<3' 'sqlmodel>=0.0.22,<1' 'anyio>=4,<5' 'httpx>=0.28,<1' 'PyJWT[crypto]>=2.10,<3' yt-dlp 'fastapi>=0.115,<1' 'uvicorn>=0.32,<1'
```

macOS 可用 Homebrew 安装本地工具：

```bash
HOMEBREW_NO_AUTO_UPDATE=1 brew install ffmpeg whisper-cpp
mkdir -p ~/.cache/nyaru-clipper/models
curl -fL --retry 2 -o ~/.cache/nyaru-clipper/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
```

Linux 安装 FFmpeg，并按 [whisper.cpp 官方说明](https://github.com/ggml-org/whisper.cpp)安装或编译 `whisper-cli`，加入 PATH。下载模型只属于安装步骤；处理任务时使用本地权重，不自动联网下载模型。这里的 `small` 是多语种模型，不要用仅英语的 `.en` 模型识别中文。

## 输出与恢复

每次运行创建独立的 `data/local-runs/<id>/`：

- `source.mp4`：下载的视频。
- `subtitles.srt`：完整字幕文字和句级时间轴。
- `transcript.txt`、`transcript.json`：全文，以及含时间戳的结构化字幕。
- `clip-001.mp4`、`clip-001.srt`：切片和从零开始的外挂字幕；GUI 可另导出 `styled-*.mp4` 烧录版本，保留原切片。
- `job.json`：选择方式、处理状态和产物校验和。
- `gui.json`：图形界面的处理消息和失败信息，不存储原链接。
- `clip-001.log`：FFmpeg 导出诊断，失败后仍保留。
- `asr/chunk-*.json`、`asr/chunk-*.log`：分块识别缓存与诊断日志。

下载结束后，失败或 Ctrl+C 中断可用 `resume` 恢复。有效识别块和已完成切片会复用；源视频、模型设置或结果被修改时会拒绝混用。完成后的 `resume` 只校验产物，不重复识别。下载失败时需要用原链接重新建立任务；链接不写入任务记录。旧的 ArcTime 云任务不支持用本地入口恢复。

## 高光规则与范围

当前高光按字幕间隔分窗，综合字幕密度、标点、笑声和兴奋词评分，选择达到 0.55 阈值的最多 N 个非重叠片段。它不调用大模型，也不分析游戏画面；中文直播类素材更符合当前规则。没有合格候选时保留完整字幕并明确报告零切片。

语音识别按五分钟分块，输出句级时间轴；目前不提供词级强制对齐、说话人区分或跨分块连续语境。字幕准确率仍需人工校对。下载覆盖范围由 yt-dlp 决定；需要登录、站点限制、直播或受保护内容的链接不保证可下载，且不会自动索取账号凭据。

## 验证

开发回归使用外部工具替身，不下载模型：

```bash
cd backend
python -m pytest tests/test_companion_gui.py tests/test_local_asr.py tests/test_arctime_workflow.py tests/test_arctime_media.py tests/test_local_companion_cli.py tests/test_highlights.py tests/test_export_encoding.py
```

真实验收需另行运行上述 CLI，并检查 MP4 音视频流、切片时长和 SRT 时间轴；单元测试不等于站点下载或实际模型识别验收。
