# 猫雷内置默认字幕与 build18 本机安装

核验：2026-10-16，Asia/Shanghai。0.1.10 build18 已打包、替换安装并启动；功能及打包提交见[当前交接](project-handoff.zh-CN.md)，本轮只发布 Web／macOS 开发分支，master 不变。

## 行为与验证

- 内置模板 `nyaru` 与用户已确认的「薄荷电波」JSON 完全一致；日文 Hiragino Maru Gothic ProN 44、中文 Noto Sans CJK SC 64，薄荷青绿／淡紫白／深紫描边。字体在本机可用，不额外下载或捆绑字体。
- 未保存默认配置时使用猫雷样式；已有用户自定义默认不由软件静默覆盖。本机按本轮明确授权，经安装版设置 API 将默认改为猫雷样式。旧值保存在完整备份中。
- 实时录播默认选择猫雷内置模板，可取消自动套用；包含此前 ASS 样式导入、任务快照和逐段样式导出。旧模板、字幕编辑稿及历史输出保留。
- macOS 相关后端 231 项通过；两端前端各 77 项与生产构建通过，默认选择最终调整后另跑 macOS 28 项任务界面测试。Web 后端另跑 24 项模板／输入测试。重复覆盖不相加；原有 Starlette/httpx 弃用警告保留。
- 最终冻结运行时完成真实本地 ASR 和 1–4 秒切片，产生 3 条字幕，ffprobe 确认切片 3.000000 秒且含音视频。另通过内置默认、ASS 读取、ASS／烧录输出、libass PNG 预览及字体检查，均使用隔离数据。
- 安装版原生 WKWebView 已观察「实时切片字幕模板」默认值为「猫雷 Nyaru｜薄荷电波·中日双语」，未提交直播或下载任务。

## 安装、备份与保留

安装位置：`/Users/drm/Applications/Nyaru Clipper.app`。

旧 App：`/Users/drm/Applications/Nyaru Clipper Backups/20261016-174807/Nyaru Clipper-build17.app`。

完整数据备份：`/Users/drm/Library/Application Support/Nyaru Clipper Backups/20261016-174807/Nyaru Clipper/`。备份父目录 0700，含配置与授权信息，仅保存在本机。

替换前后 6,561 个文件、9,935,483,555 字节的内容哈希、权限及符号链接完全一致。启动及原生检查后，原有文件仅 `runs/templates/defaults.json` 按用户要求改变，另新增一个启动信息文件；20 个历史任务 ID、供应商配置、授权状态、任务媒体及模型均保留。

## 包与边界

包：macOS 工作树 `.omo/evidence/nyaru-default-build18-2026-10-16/Nyaru-Clipper-0.1.10-build18-macOS-arm64.zip`，520,742,043 字节，3,877 个条目，完整性通过。

SHA-256：`534b9e4bf176923483f2fdc20b1a9f368ebbb9d2b7769c187a8bc67b5ec2bc41`。

严格本地签名通过；仍为 arm64、最低 macOS 27.0、未公证。真实 Bilibili 长时直播／下载和外部 AI 本轮未重验。旧任务保留其已保存编辑样式；改默认不会重写旧字幕或重新烧录。详细回执位于同一本机证据目录，不纳入 Git。
