# 第一阶段改进实施记录

日期：2026-10-21。对应英文：[Phase-one results](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.md)。

本文保留第一阶段结束时的历史结果。随后 #32 对解释器测试和导出脚本的修复，以及两阶段共同重新验证的最新状态，见[第二阶段与合并结果](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.zh-CN.md)；下文 970／1 是当时结果。

范围来自[改进计划](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.zh-CN.md)：#1–7、#20、#21，共 9 项。分支为 `codex/code-improvement-2026-10-21`，HEAD 仍为 `e8ea71085cf5c6ff6f671499872f5c166d31f89b`；改动未提交。

当前状态：**9 项已实现并在下表记录的观察范围内通过验收，最终复核 APPROVE，无阻塞项。**[验收复核报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/final-gate-review.md)保留逐项判断与限制；其余 35 项仍待实施，不构成整体发布验收。

| 条目 | 实现与观察到的行为 | 证据 |
| --- | --- | --- |
| #1 凭据脱敏 | 下载构参、日志、错误和返回元数据按需脱敏；转义 JSON 中的秘密值被清除，数值字段保持原值 | [日志／进程报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/logs-processes-report.md) |
| #2 进程回收 | 启动后的登记、回调、日志、持久化及取消异常先回收并等待进程组；回收失败保留跟踪和 GPU 占用；恢复路径有界重试短暂 EPERM | [进程报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/logs-processes-report.md)、[队列报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/queue-report.md) |
| #4 成片保护 | 同目录临时文件编码后原子发布；失败、空结果及数据库持久化异常保留旧成片，并排斥并发写入 | [实际 API／FFmpeg 工作流](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/clip-export-workflow.txt) |
| #20 队列终态 | 任务、job、run 和队列终态一并提交；真实子进程中断后下一任务可被领取，旧状态修复兼容缺失／已结束 run | [队列报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/queue-report.md)、[复核](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/queue-final-review.md) |
| #21 拒绝无副作用 | 先加锁验证再变更；批量拒绝、外层回滚保持原记录及文件；已接受重试的清理由持久状态驱动，延迟回调不删除新输出 | [事务与文件证据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/queue-report.md) |
| #3 缓存身份 | 校验源媒体、音频、转换参数及本地模型内容；旧无身份缓存重建，恢复时回退至失效依赖；字幕文档和旧导出保留 | [真实换源结果](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/cache-live/result.json)、[报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/cache-report.md) |
| #5 翻译发布恢复 | 发布先于 checkpoint 中断后，根据已验证输入和批次重建预期精确字节；只接受一致产物，继续拒绝损坏、身份不符及未知文件 | [恢复与旧格式回归](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/translation-recovery-report.md)、[独立复核](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/translation-final-review.md) |
| #6 macOS 依赖 | 声明 httpx 和 PyJWT 的 crypto extra；仅声明构建依赖的独立环境完成 App 构建，实际冻结后端启动，独立冻结探针验证 RS256 正反例 | [构建报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/macos-build-report.md)、[独立复核](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/macos-final-review.md) |
| #7 Docker 迁移 | 镜像带上 Alembic 配置和版本目录；实际镜像启动新库和旧库，HTTP 可用、迁移到 head，保留旧记录 | [实际镜像结果](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/docker-integrated-migrations.log)、[复核](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/docker-review.md) |

## 验证与既有环境限制

最终第一阶段合并检查为 **290 通过**；[完整后端回归](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/backend-final.log)为 **970 通过、1 失败**，有一项既有 Starlette 弃用警告。Linux 容器中的下载／进程测试为 38 通过；恢复权限修复的 60 项检查及 5 轮重复检查均通过。独立复核另验证缓存 67 项、翻译恢复 31 项、旧队列阶段修复 36 项。计数对应各自测试集，不能相加视为唯一测试总数。

完整回归中的 requirements 导出测试假定存在 `backend/.venv`，该目录在实施前即不存在；本次使用独立证据环境，该测试和导出脚本保持原样。生成文件另经保留旧版本约束、显式 Linux 目标的导出检查通过，锁文件检查通过。不可将这两个事实合并表述为“完整回归全绿”。

## 源码协调与保护

为在同一新分支承载 #5／#6，同步当前 macOS Companion 的 99 个基线条目及 1 个 ASS 测试辅助文件；这些基线内容须与本次修复差异分开审阅。[SHA256 清单](/Users/drm/project/nyaru-clipper/.omo/evidence/phase1-improvement-2026-10-21/companion-baseline-manifest.json)记录原始内容。原 C／B 工作树保持原分支、HEAD 和 56／53 个 dirty entries；原 C 的 99 项校验和仍全部一致。原主工作树既有文档和未跟踪内容已保留，计划原文亦有备份。

未提交、推送、合并或安装 App；未使用真实凭据、业务数据库或真实供应商。构建产物、临时库、媒体和测试日志位于证据目录。Docker Desktop 为实际镜像验证启动，临时验证镜像及构建缓存保留。

## 验收边界与后续

没有验证真实 GPU、CUDA／ROCm／AMF、真实下载与登录、原生窗口交互或断电耐久性。远端模型引用未解析到固定修订时，不能离线识别同名仓库更新；FFmpeg 原路径替换也未按二进制内容固定。完整哈希增加磁盘读取。新身份字典的静态类型约束仍有维护空间。

保留其余 35 项原编号和验收条件，下一批可按原计划处理验证入口及其余恢复／可见行为问题。当前候选和证据可供审阅，整体发布需另做目标平台验收。
