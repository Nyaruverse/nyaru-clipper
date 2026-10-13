# macOS App 验收记录

日期：2026-10-13。平台：Apple Silicon arm64 / macOS 27.0.1。
范围：用户选择的当前本地工具，不含旧工作站翻译、校对及 GPU 队列。

## 构建

- `dist/Nyaru Clipper.app`，安装副本 `~/Applications/Nyaru Clipper.app`，ZIP 在 `dist/Nyaru-Clipper-macOS-arm64.zip`。
- Swift/AppKit/WKWebView 窗口，PyInstaller 6.22.3 / Python 3.11.16 后台。
- 前端 TypeScript/Vite 构建、Swift 编译及严格 ad-hoc 签名验证均通过。
- 88 项相关后端回归通过，有上游 Starlette/httpx 弃用提醒。
- 从仓库移到用户应用目录后真实运行，后台 PATH 只有 `/usr/bin:/bin`。42 个 Mach-O 没有非系统绝对依赖。
- 模型 SHA-256：`1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b`。

## 实际工作流

通过真实 HTTP 链接处理已有本地 20.4 秒中文测试视频，使用包内下载器、ASR 和编码器，未使用桩。

| 场景 | 观察结果 |
| --- | --- |
| 原生指定时间段 | `a75507568f4f`：2–8 秒，生成 6 秒 H.264/AAC MP4 和从零开始的 SRT |
| 文字和时间轴 | 识别出两条中文句子，0–14.3 秒及 14.3–20.1 秒，完整 SRT/TXT/JSON 保留 |
| 原生视频预览 | WebKit Play/Pause 可用，Elapsed 从 0 增到 6 秒，Duration 为 6 秒，有真实视频画面 |
| 首次保存 | 系统保存面板实际导出 626625 字节 MP4，SHA-256 与任务文件一致 |
| 新版同名替换 | Save → Replace 成功，修改时间从 1791900317 增至 1791900933，哈希与任务文件一致，没有错误提示 |
| 字幕保存 | 原生导出的 SRT 与任务 SRT 哈希一致 |
| 取消保存 | 在已有视频文件名下取消，旧文件大小、修改时间和哈希均保持，无临时下载文件残留 |
| 高光运行时 | `fc8485fb60db`：20.4 秒片段，高光评分 0.77 |
| 原生高光表单 | 选择高光及上限 2，`902280ee4039` 完成；界面显示 20.4 秒、0.77 分及 MP4/SRT 下载 |
| 正常退出 | Cmd-Q 后原生程序、后台与端口退出，启动文件清理 |
| 强制退出 | `8117f9b0fa45` 的 whisper-cli 正在运行时强杀测试 App；后台及整个识别进程组退出，端口关闭，模型和已有导出哈希不变 |
| 重启恢复 | 原生界面保留历史并显示中断任务；点击恢复处理后 `8117f9b0fa45` 完成，生成 6 秒片段 |
| 媒体完整性 | 包内 ffprobe 正确读取两种片段，包内 ffmpeg 完整解码视频与音频无错 |

运行时证据：`.omo/evidence/macos-runtime-qa.py` 和 `macos-runtime-qa.json`。
原生操作与截图由本次 CUA 会话观察；导出文件为 `.omo/evidence/macos-export.mp4`、`.srt`。
独立审阅 `.omo/evidence/macos-app-review.md`：三个发现已修复，无代码阻断项。

## 失败与验收边界

首版启动因 Foundation Process 已是进程组 leader，重复 setsid 返回 EPERM；已修复并重建。审阅发现同名保存及退出升级信号边界，均已修复。CUA 一度报 ScreenCaptureKit -3811，后续 App 重启后恢复，恢复后实际验证了新版替换、取消及高光表单。

完成主要验收后的额外退出复查遇到 CUA ScreenCaptureKit -3812，未执行退出动作，未把该失败调用记为成功。此前正常退出及修复版父进程强杀清理的成功记录保留。

未验证 Intel、旧 macOS、其他设备首次安装、任意公共平台登录／反爬、长视频负载或实际扬声器输出。本地签名不是 Developer ID 公证分发。没有提交或推送 Git，也没有改动原 GPU 工作站流程。
