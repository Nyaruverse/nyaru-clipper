# macOS App

当前安装版为 **0.1.9 build17**，2026-10-16 已替换并验证启动。新建任务直接填写 Bilibili 直播间号、BV 号或选择本地视频，20 个历史任务及原有数据／配置全部保留；备份与证据见[当前交接](project-handoff.zh-CN.md)。支持[臊子](saozi.zh-CN.md)实时切片、自动双语字幕和[ChatGPT订阅供应商](openai-subscription.zh-CN.md)，AI 可选择 DeepSeek Flash 或 ChatGPT。下文旧版本安装记录均为历史。

2026-10-16 的 build15 将功能入口收为顶部选项与右侧抽屉：点击展开，再点同一项收起。草稿保留，进度与停止操作保持可见。此次复用 build14 运行时，仅更新前端及构建号并重新本地签名；原生开合验证与旧版备份见[界面验收](toolbar-drawer-acceptance-2026-10-16.zh-CN.md)。

**Nyaru Clipper.app 0.1.5** 已包含链接下载、本地字幕文字和句子时间轴、指定时间段／高光切片、进度、预览及导出，并支持 DeepSeek 日译中双语字幕和[自定义字幕样式、两类模板、ASS、切片烧录及 ArcTime 精修交接](subtitle-styles.zh-CN.md)。Python、yt-dlp、含 libass 的 FFmpeg、whisper.cpp 和多语种 small 模型均内置，运行时无需终端、Homebrew 或 ArcTime 付费服务。

双语字幕复用已完成任务的字幕与时间轴。API Key 可通过界面保存到 `runs/config.json`，重启自动加载；之后可生成完整视频及各切片的双语 SRT，查看翻译进度、切换预览和导出。DeepSeek API 需要网络和账户额度。详见[双语字幕指南](deepseek-bilingual.zh-CN.md)。

0.1.1 修复识别块末尾越界和连续零时长文字片段：末尾区域按实际音频边界裁剪，允许的尾部窗口最多 30 秒，短块最多为块长一半；跨越非末尾区域或超过窗口的异常仍拒绝。普通字幕读取仍执行严格校验。

## 打开和使用

2026-10-15 已将验证通过的 0.1.5 build 9 安装到 `~/Applications/Nyaru Clipper.app` 并启动。旧版 0.1.4 build 5 保存在 `~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-15-0.1.4-build5/Nyaru Clipper.app`；任务数据和模型保留。安装副本1498个文件的SHA256与验证构建一致，严格签名验证通过；实际界面读取7个历史任务、3个样式模板和1个ArcTime模板。新包为 `dist/Nyaru-Clipper-0.1.5-build9-macOS-arm64.zip`。见[本次功能验证记录](subtitle-styles-acceptance-2026-10-14.zh-CN.md)。

1. 选择实时录播、下载视频或本地视频，填写直播间号、BV 号或选择文件，再选择语种或自动识别。
2. 选择指定起止时间，或高光模式及最多导出数量。
3. 点击「开始处理」，查看下载、识别、导出阶段，一次处理一个任务。
4. 预览视频或切片、点击字幕时间跳转，再通过系统保存面板导出 MP4/SRT 或完整 SRT/TXT。

同名文件确认替换后，下载完成才替换原文件；取消保存保留原文件。首次启动会复制、校验内置模型。数据在 `~/Library/Application Support/Nyaru Clipper/` 的 `models/`、`runs/` 和 `app.log`，更新 App 不会删除任务和模型。请勿手工修改任务清单；旧 CLI 的 `data/local-runs/` 历史不会自动迁入。

关闭窗口或 Cmd-Q 会停止后台和正在处理的工具。重新打开后，已下载的中断任务可以「恢复处理」；未完成下载需重新提交链接。恢复识别应保留原 App 安装位置及模型，避免识别配置变化。站点访问条件仍然适用，界面没有登录或 Cookie 配置。

## 平台与构建

当前为 **Apple Silicon / arm64，最低 macOS 27.0**，已在 macOS 27.0.1 验证。版本下限来自本次打包的原生工具。本地 ad-hoc 签名已验证；尚未做 Developer ID 签名或 Apple 公证。

开发构建才需要 Python 3.11、uv、Corepack、前端依赖、含 libass 的 FFmpeg/ffprobe、whisper.cpp 和校验正确的模型。默认选择 Homebrew `ffmpeg@7`；SDL2 compatibility 的 SDL3 动态依赖会显式打包。构建器同时验证宿主和冻结后的字幕滤镜，冻结工具不可运行时构建失败。

```bash
uv venv --python 3.11 dist/build-venv
uv pip install --python dist/build-venv/bin/python -r desktop/macos/requirements-build.txt
cd web
corepack pnpm install --frozen-lockfile
cd ..
dist/build-venv/bin/python scripts/build_macos_app.py --output-dir dist/new-build
```

默认模型为 `~/.cache/nyaru-clipper/models/ggml-small.bin`，可用 `--model /路径/模型文件` 指定。构建器保留已存在的 `dist/Nyaru Clipper.app`，重建前先移走旧构建。产物含依赖许可证和 `Contents/Resources/build-info.json`。

详见 [本次验收记录](macos-app-acceptance-2026-10-13.md)。
