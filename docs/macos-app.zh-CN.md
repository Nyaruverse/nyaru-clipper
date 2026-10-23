# macOS App

**Nyaru Clipper.app 0.1.4** 已包含链接下载、本地字幕文字和句子时间轴、指定时间段／高光切片、进度、预览及导出，并支持 DeepSeek 日译中双语字幕。Python、yt-dlp、FFmpeg、whisper.cpp 和多语种 small 模型均内置，运行时无需终端、Homebrew 或 ArcTime 付费服务。

双语字幕复用已完成任务的字幕与时间轴。API Key 可通过界面保存到 `runs/config.json`，重启自动加载；之后可生成完整视频及各切片的双语 SRT，查看翻译进度、切换预览和导出。DeepSeek API 需要网络和账户额度。详见[双语字幕指南](deepseek-bilingual.zh-CN.md)。

0.1.1 修复识别块末尾越界和连续零时长文字片段：末尾区域按实际音频边界裁剪，允许的尾部窗口最多 30 秒，短块最多为块长一半；跨越非末尾区域或超过窗口的异常仍拒绝。普通字幕读取仍执行严格校验。

## 打开和使用

本机已安装到 `~/Applications/Nyaru Clipper.app`，双击打开即可。项目 `dist/Nyaru-Clipper-macOS-arm64.zip` 是可解压的本地构建。

1. 输入可访问的视频链接，选择语种或自动识别。
2. 选择指定起止时间，或高光模式及最多导出数量。
3. 点击「开始处理」，查看下载、识别、导出阶段，一次处理一个任务。
4. 预览视频或切片、点击字幕时间跳转，再通过系统保存面板导出 MP4/SRT 或完整 SRT/TXT。

同名文件确认替换后，下载完成才替换原文件；取消保存保留原文件。首次启动会复制、校验内置模型。数据在 `~/Library/Application Support/Nyaru Clipper/` 的 `models/`、`runs/` 和 `app.log`，更新 App 不会删除任务和模型。请勿手工修改任务清单；旧 CLI 的 `data/local-runs/` 历史不会自动迁入。

关闭窗口或 Cmd-Q 会停止后台和正在处理的工具。重新打开后，已下载的中断任务可以「恢复处理」；未完成下载需重新提交链接。恢复识别应保留原 App 安装位置及模型，避免识别配置变化。站点访问条件仍然适用，界面没有登录或 Cookie 配置。

## 平台与构建

当前为 **Apple Silicon / arm64，最低 macOS 27.0**，已在 macOS 27.0.1 验证。版本下限来自本次打包的原生工具。本地 ad-hoc 签名已验证；尚未做 Developer ID 签名或 Apple 公证。

开发构建才需要 Python 3.11、uv、Corepack、前端依赖、FFmpeg/ffprobe、whisper.cpp 和校验正确的模型。

```bash
uv venv --python 3.11 dist/build-venv
uv pip install --python dist/build-venv/bin/python -r desktop/macos/requirements-build.txt
cd web
corepack pnpm install --frozen-lockfile
cd ..
dist/build-venv/bin/python scripts/build_macos_app.py
```

默认模型为 `~/.cache/nyaru-clipper/models/ggml-small.bin`，可用 `--model /路径/模型文件` 指定。构建器保留已存在的 `dist/Nyaru Clipper.app`，重建前先移走旧构建。产物含依赖许可证和 `Contents/Resources/build-info.json`。

详见 [本次验收记录](macos-app-acceptance-2026-10-13.md)。
