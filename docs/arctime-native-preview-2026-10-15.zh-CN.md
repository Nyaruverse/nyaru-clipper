# ArcTime 原生预览排查与验收

2026-10-15，Asia/Shanghai。ArcTime Pro 4.5，本机 macOS／Apple Silicon。

结论：合成测试工程的原生视频、双语字幕和样式预览通过。此前“原生播放器未确认”的验收项在本次复查中关闭；无损视觉往返仍不作承诺。

## 原因与处理

ArcTime 的 Java 主窗口和视频窗口分属不同进程：主窗口3845由 Java PID49990持有，播放器窗口4540的名称为 `Mpv-For-Arctime`，由 ArcTime 启动的 mpv PID73082持有。旧 Swift 桥接只枚举 `ArcTime Pro` 所有者；对主窗口使用 `screencapture -l3845`，视频区仍是黑色，无法据此判断播放器失效。

同一运行状态改为捕获独立播放器 `-l4540`，即可看到视频与字幕；通过既有 Swift AX 桥接将 ArcTime 置前，再对播放器实际屏幕区域 `-R323,212,1272,717` 截图也正常。第二次对 Java 主窗口截图仍黑，而播放器和实际屏幕截图正常，复现了捕获对象造成的误判。没有修改 ArcTime 的播放器参数、安装文件或系统配置。旧屏幕区域截图确实曾为黑色，保留为历史观察；本次没有重现，不能将所有旧截图的原因都归于单窗捕获。

修正的是验证方法：同时核对独立播放器和实际屏幕，不能只凭 Java 主窗口截图验收。窗口ID、PID和 IPC 地址属于本次运行，下一次必须重新枚举。

## 实际验证

| 场景 | 观察与结果 |
| --- | --- |
| 暂停1.28秒 | 蓝色视频、白色日文黑底、较小绿色中文、分开的上下位置可见。通过。 |
| 原生 Play／Pause | 既有 Swift 桥接实际点击播放；只读 mpv IPC 确认 `pause=false`，时间推进至3.12和5.52秒，再点击暂停确认 `pause=true`。通过。 |
| 播放3.12秒 | 日文单行、中文两行，背景、颜色、描边和位置均可见且在画内；独立窗口与实际屏幕分别捕获并目视检查。通过。 |
| 播放5.52秒 | 花括号与字面量 `\N` 未被解释成排版命令，双语可见。通过。 |
| 原生时间轴跳转 | 实际点击时间轴，IPC读回3.04秒；暂停预览仍显示日文与两行中文。通过。 |
| 捕获回归 | 同一像素检查对两张 Java 主窗口截图返回退出码1；对七张播放器／屏幕截图返回0，蓝色覆盖98.47%至99.07%，并检测到白色与绿色文字像素。此检查仅针对已知合成素材，目视检查负责文字、换行和布局。 |
| 工程保护 | `input-original.ass`、ArcTime保存的 `clip.ass` 与 `clip.atpj` 的SHA256均与10月14日记录相同；未修改原字幕工程。 |

## 证据与复现

证据目录：`/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/`。

- [实际屏幕：双语多行预览](/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/screen-multiline-playing.png)
- [实际屏幕：特殊字符](/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/screen-literal-playing.png)
- [操作和播放状态回执](/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/playback-receipt.json)
- [排查日志](/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper/.omo/evidence/arctime-player-2026-10-15/journal.md)

`verify-playback.py` 记录原生按钮操作和只读IPC状态；其固定运行标识和1至2秒的暂停前置条件防止直接误用。`check-preview.swift` 可对现存截图独立复查：`swift check-preview.swift <截图路径...>`。原始主窗口截图可能含账户标记，仅作本地证据，分享使用上述播放器区域截图。

本次只有验证脚本和文档更新，未改变产品源码或打包文件，未重跑与此无关的全仓库测试。ArcTime会取整字号、插入淡入淡出并重排层；原生模板同名样式覆盖与不同分辨率仍需检查。本次没有测试扬声器声音、其他字体、其他机器或平台。ArcTime留在合成测试工程3.04秒暂停状态。
