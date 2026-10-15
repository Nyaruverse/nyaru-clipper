# 顶部选项与右侧抽屉 · 2026-10-16

用户已选择会话预览中的“顶部选项 · 右侧抽屉”。六个入口为「新建任务」「切片方式」「字幕样式」「AI 设置」「任务记录」「导出」。初始收起；点击展开，再点同一入口收起，切换入口仅显示一项。关闭按钮与 Escape 同样可收起，并将键盘焦点送回入口。

表单保持挂载，链接、时间段、本地录像选择、字幕模板名称和供应商草稿在开合／切换时保留。新建任务与切片方式共享提交表单；未填写的必填项会展开到对应位置。桌面抽屉位于预览右侧，长内容单独滚动；窄窗口使用右侧覆盖面板。进度、连接错误、任务错误、恢复和直播停止保留在主工作区。

## 本轮证据

- macOS 与 Web 工作树分别执行 `corepack pnpm exec vitest run src/companion`，各 **5 文件、47 项通过**，范围重叠不相加。修改前基线为 41 项通过。新增开合、草稿、本地文件、Escape 焦点和跨区输入校验测试。
- 两个工作树均通过 `corepack pnpm build` 的 TypeScript 和 Vite 生产构建；`git diff --check` 通过。
- 生产前端使用本地 HTTP 与短视频夹具，覆盖全部六个入口在 1440／1920／390 宽度及两种系统外观偏好下的展开和收起、长内容滚动、空任务、录制状态、播放连续性与减少动态效果。应用保持现有浅色主题；这不代表新增深色主题。浏览器无 JavaScript 错误，测试没有向真实任务／供应商提交请求。
- 已在安装版原生窗口逐项验证六个入口再次点击收起、跨面板链接草稿保留及 Escape 收起。更新前后任务列表均为 20 项，更新时没有活动任务。
- 当前安装为 **0.1.8 build15**，路径 `~/Applications/Nyaru Clipper.app`。本次复用已安装 build14 的原生窗口、冻结后端、工具与模型，仅更新构建后的前端资源及构建号，再执行本地签名和严格签名验证；未重新冻结后端。安装资源与生产构建的 HTML、引用 JS／CSS SHA256 一致。
- build14 保留在 `~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-16-before-toolbar-build15/Nyaru Clipper.app`。模型、任务目录、供应商与授权配置未迁移或清理。

本地证据位于 macOS 工作树 `.omo/evidence/toolbar-drawer-2026-10-16/`：`browser-qa.json`、`native-qa.json`、`install-assets.json`、各窗口尺寸截图、`native-style-open.png` 和 `native-closed.png`。私密证据与候选安装包不进入 Git。

## 边界

本轮验证界面与原有调用契约，没有重新执行真实下载、识别、翻译、直播录制、烧录或导出，也没有重新验收原生保存权限。未增加依赖、修改 API／数据库、调用 DeepSeek Pro、合并 master 或公开分发。工具栏实现、测试与本验收记录发布到 Web／macOS 开发分支；提交及推送状态见[当前交接](project-handoff.zh-CN.md)。此前交接内容保存在历史快照中。
