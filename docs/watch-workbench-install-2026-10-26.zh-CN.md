# 看片工作台正式安装 — 2026-10-26

按用户明确指令，已将 **0.1.20 build 28** 安装到 `/Users/drm/Applications/Nyaru Clipper.app`。正常打开及正常退出重开均进入看片工作台，使用 `/Users/drm/Library/Application Support/Nyaru Clipper/unified/runtime.json`。

## 数据与设置保留

- 原桌面目录当前有 **0 个已登记的 12 位任务目录**，安装前后任务数量均为 0；没有将测试任务或测试媒体带入正式环境。
- 原有 **21 个活动数据／配置文件** 已备份，安装及重开后字节校验一致，包括模型、配置和凭据。原有 app-backups 目录未移动或覆盖。
- 5 个原有公共模板／工程文件通过统一设置存储按原字节登记。重开后的默认字幕样式、全部样式／工程模板、工作流默认值、供应商及模型选择均与原设置一致。凭据仍使用原 `runs` 路径，模型沿用原路径。
- 队列保持暂停。未发起录制、识别、导出或外部 AI 调用，未下载模型、接管／封存旧来源、改变旧恢复 pin、提交或推送源码。

## 安装包与验证

后端、媒体工具和 Web 资源来自已验证的 `watch-workbench-macos-20261026-04` 候选包；仅更新原生启动入口及版本号。未传 `--unified-runtime` 时，原生入口选择标准 Application Support 目录中已登记的 `unified/runtime.json`；不存在时仍使用旧兼容入口。显式运行时优先；已登记清单损坏会拒绝启动，不会静默重建或清空数据。

Swift 类型检查及 **8 项原生相关测试** 通过，覆盖已登记／缺省／显式运行时选择和原有退出、日志、模型、进程行为。深度严格签名检查通过；正式原生窗口和本地 API 在正常退出前后、从 App 入口重新打开后均核验。收据位于 macOS 源码目录 `.omo/evidence/watch-workbench-install-20261026/after.json`。

## 备份与回退

备份位置：`/Users/drm/Library/Application Support/Nyaru Clipper Backups/watch-workbench-20261026-085605`。内含 `data/` 原活动数据、已验证的旧 App 副本，以及通过重命名保留的 `Original installed App.app` 原安装包。

如需回旧版，先退出 Nyaru Clipper，保留现安装包及新 `unified/` 运行时，再将 `Original installed App.app` 复制回 `/Users/drm/Applications/Nyaru Clipper.app`。旧原生入口继续读取未改写的旧数据根；不要用较旧备份覆盖后续新数据。回退只切回旧界面，不会导入此后在统一运行时中新建的任务。

本次安装不增加真实直播高光质量、外部供应商、GPU／WSL、系统重启保护或公证的验收资格。此前“候选未安装”的记录属于历史状态，以本收据为准。
