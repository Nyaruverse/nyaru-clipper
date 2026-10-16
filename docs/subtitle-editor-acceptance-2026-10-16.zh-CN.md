# 逐条字幕编辑与 build16 验收

核验日期：2026-10-16。

功能提交：Web `576b538d336cbeaf9c869f049f3b7d063ad9f792`; macOS `a132fcc6125380a5451e5cfe2dd335ec55260e81`.

| 范围 | 结果与证据 |
| --- | --- |
| 两端前端 | 各 10 文件／65 项通过，TypeScript／Vite 构建通过；重复覆盖不相加 |
| 后端回归 | 字幕、模板、API、渲染、GUI、翻译和 macOS 共 160 项通过；Web 独立执行其中 50 项编辑稿／字体测试 |
| Web 实际界面 | 1440／1920／390 宽度、两种系统外观偏好、四个页签，共 48 张顶／底截图；无横向溢出，产品仍为浅色主题 |
| 最终冻结后端＋原生 WKWebView | 底部／居中／顶部双语多行、原文／译文分别微调、联动数值定位通过；选中像素边界 +1X/0Y，另一语言不动 |
| 预览／ASS／烧录 | 实际 ASS 坐标与 PNG 对照；烧录帧与预览合成 RMSE 分别 1.355／1.507／1.422（满量程 255，包含有损编码差异） |
| 数据与失败路径 | 样例邻句、源文件、旧导出哈希不变；源变化／版本冲突／无效时间拒绝，草稿保留；缺失字体警告通过 |
| 复核 | 早期 G1 多行自动锚点跳动已修复；新一轮位置代码复核 APPROVE，无阻塞，并独立运行 14 项前端／41 项后端及实际 ASS 过渡对照 |


## build16 安装、回退与数据保留

本机安装版为 **0.1.8 build16**，位于 `~/Applications/Nyaru Clipper.app`。本轮重新构建前端、冻结后端及工具／模型、编译 Swift 窗口并本地签名；严格签名和 Swift 类型检查通过。安装时无运行任务，正常退出 build15 后替换并成功打开 build16。

- 旧 App：`~/Applications/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper-build15.app`。
- 完整数据备份：`~/Library/Application Support/Nyaru Clipper Backups/20261016-114616/Nyaru Clipper/`，备份目录 0700。包含授权配置，只保留在本机，不提交或共享。
- 替换前后 **6,560 个文件、9,935,471,576 字节**逐文件哈希一致；重启后 **20 个历史任务 ID**全部保留，原有文件再次核验未变化。
- 安装前未另存的自定义样式已保留为「升级前自定义样式 2026-10-16」。原生位置演示 X640→641 后撤销，恢复 X640/Y656；保存第 2 版、各条样式仍继承。演示仅新增该任务的编辑稿及启动文件。
- 本地 ZIP `Nyaru-Clipper-0.1.8-build16-accepted.zip` 位于上述证据目录，514,619,440 字节、3,914 项；SHA256 为 `2badc99dc66bb1cfa44888d3a976ce87a693710e02c9fc6e534d00d89a15ff17`。App／ZIP／模型不进入 Git。


## 限制与复现

本机私密证据目录为 macOS 工作树 `.omo/evidence/subtitle-editor-2026-10-16/`，包含 `acceptance.md`、`integration-backend.log`、`native-report.md`、`position-delta-review.md`、`installation-receipt.json` 及本地候选 ZIP；这些原始产物不提交。

具体操作见[使用说明](subtitle-editor.zh-CN.md)，分支、备份和接续规则见[当前交接](project-handoff.zh-CN.md)。前端测试命令为各工作树 `web/` 下的 `corepack pnpm exec vitest run src/companion`，生产构建为 `corepack pnpm build`。代码与已验收版本哈希一致，发布阶段不重新运行识别／翻译，也不停止已打开的 App。后端 160 项的准确文件选择和原始日志保存在本机证据目录。

原始媒体、窗口截图、授权配置、App／模型、完整备份和私密测试日志不进入 Git。源码发布仅限两个开发分支，master 基线保持 `0bcd8d503ac33f89c8e1cd526de5d7a44f6668b6`。尚未验收 Developer ID／公证／公开分发、新机器、Intel／旧 macOS、真实供应商到期／撤销、所有字体与高级样式组合。烧录只支持完成切片。
