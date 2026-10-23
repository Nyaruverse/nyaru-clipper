# 文档目录说明

最新本机候选：[App02 两项历史任务修复、重打包与实包复验](candidate-fixes-2026-10-23.zh-CN.md)，含新包摘要、25/25 历史副本场景、真实原片／原生保存重开和独立恢复证据；未替换正式 App、未切换正式数据。

本目录存放项目的操作手册、用户手册、线框图和流程说明。

此前 App01 候选：[2026-10-23 App／独立恢复包与隔离验收](candidate-package-2026-10-23.zh-CN.md)，保留原包接管／回退证据；最新修复包见上方 App02。

统一架构方案 B：[设计](superpowers/specs/2026-10-22-unified-architecture-design.zh-CN.md)、[分阶段计划](superpowers/plans/2026-10-22-unified-architecture.zh-CN.md)、[执行与 M01—M28 证据](unified-architecture-execution-2026-10-22.zh-CN.md)、[候选运行时／恢复指南](unified-runtime-guide.zh-CN.md)。本机实现已验证，平台／生产资格与 P6 仍待完成。[English execution record](unified-architecture-execution-2026-10-22.md)。

如果你要先完成部署或本地启动，请优先阅读：

- `deployment-guide.zh-CN.md`：中文部署指南，包含专用 WSL + ROCm 安装、自检、共用运行时入口与 smoke 路径
- `deployment-guide.md`：English deployment guide，包含专用 WSL + ROCm 安装、自检、共用运行时入口与 smoke 路径

当前中文文档对应关系如下：

- [八阶段累计修改与提交交接](/Users/drm/project/nyaru-clipper/docs/code-improvement-rollup-2026-10-21.zh-CN.md)与[对应英文](/Users/drm/project/nyaru-clipper/docs/code-improvement-rollup-2026-10-21.md)：44／44限定验收、累计修改、可携带证据摘要与明确提交排除项

- [project-handoff.zh-CN.md](project-handoff.zh-CN.md)：当前项目交接，含本地工具／macOS App、验收、运行状态及待办
- [project-handoff.md](project-handoff.md)：对应英文交接

- [代码与架构改进计划（2026-10-20）](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.zh-CN.md)：六轮审阅 44 项问题、优先级、工作包、逐项验收、清理边界及当前实施状态
- [对应英文改进计划](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.md)
- [第一阶段结果](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.zh-CN.md)与[对应英文](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.md)
- [第二阶段与合并结果](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.zh-CN.md)与[对应英文](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.md)：当前实现、验收证据和平台限制
- [第三阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase3-improvement-results-2026-10-21.zh-CN.md)与[对应英文](/Users/drm/project/nyaru-clipper/docs/phase3-improvement-results-2026-10-21.md)：第三阶段历史总账 18 项已验收／26 项待处理
- [第四阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase4-improvement-results-2026-10-21.zh-CN.md)与[对应英文](/Users/drm/project/nyaru-clipper/docs/phase4-improvement-results-2026-10-21.md)：第四阶段历史总账23项已验收／21项待处理
- [第五阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase5-improvement-results-2026-10-21.zh-CN.md)与[对应英文](/Users/drm/project/nyaru-clipper/docs/phase5-improvement-results-2026-10-21.md)：第五阶段历史总账28项已验收／16项待处理，含旧稿兼容和平台限制
- [第六阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase6-improvement-results-2026-10-21.zh-CN.md)与[对应英文](/Users/drm/project/nyaru-clipper/docs/phase6-improvement-results-2026-10-21.md)：第六阶段历史总账33项已验收／11项待处理，八行字幕／5000条预览和平台限制
- [第七阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase7-improvement-results-2026-10-21.zh-CN.md)与[对应英文](/Users/drm/project/nyaru-clipper/docs/phase7-improvement-results-2026-10-21.md)：该阶段结束时38项已验收／6项待处理，保留当轮累计与原生验收证据
- [第八阶段与44项累计结果](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.zh-CN.md)与[对应英文](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.md)：最新总账44项在记录范围内已验收／0项待处理，六项收尾、当前累计检查、最新原生App双任务保存／退出／重开、最终gate与限制

- `macos-app.zh-CN.md`：本地工具的 macOS App、数据目录与构建说明
- `macos-app.md`：对应英文说明

- `local-companion.zh-CN.md`：本地链接下载、字幕识别、时间轴、指定片段／高光切片及恢复
- `local-companion.md`：对应英文说明

- `user-manual.zh-CN.md`：用户手册（中文）
- `operator-manual.zh-CN.md`：运维/操作手册（中文）
- `deployment-guide.zh-CN.md`：部署指南（中文）
- `wsl-rocm-investigation.zh-CN.md`：WSL + ROCm 调查记录与结论（中文）
- `wireframes.zh-CN.md`：MVP 页面线框图（中文）
- `processing-flow.zh-CN.md`：处理流程与产物目录说明（中文）

英文原版文档仍保留，便于双语对照和后续维护。如果你的目标环境是 WSL + ROCm，请先看部署指南里的专用路径，再继续阅读运维手册和用户手册。

当前运维手册和部署指南也已经补充了 ASR 生命周期可观测性说明，包括活动 phase 耗时显示、`cancel_requested` 的叠加语义、`force-kill` 的受限可用条件、阶段状态更新的 worker execution token 边界，以及后端/前端任务状态改动后的开发者回归命令。
