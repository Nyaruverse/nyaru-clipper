# 第二阶段实施与两阶段合并验收

日期：2026-10-21。对应英文：[Phase-two results](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.md)。

状态：**四项已实施，第一、第二阶段共 13 项在本文观察范围内通过本轮合并验收，最终 gate APPROVE，无阻塞项；其余 31 项待处理。**执行顺序为 #32 → #43 → #44 → #12；所有条目仍沿用[原 44 项计划](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.zh-CN.md)编号。第一阶段 #1–7、#20、#21 与本阶段四项共同重新验证，没有用历史第一阶段结论替代本轮证据。

## 源码与数据边界

继续使用 `/Users/drm/project/nyaru-clipper` 的 `codex/code-improvement-2026-10-21`，HEAD 为 `e8ea71085cf5c6ff6f671499872f5c166d31f89b`。本轮开始时 183 个 dirty entries 已保存状态及完整 tracked patch；未提交、推送、合并或安装 App。原 Companion 工作树不改写，运行验证使用临时数据、数据库、媒体及任务自有浏览器 profile。

主路径仍是宿主机 `uv + pnpm`，Docker 是备用路径，macOS Companion 有独立入口。验证未使用真实凭据、供应商或业务任务。

证据目录：[phase2-release-validation-2026-10-21](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/)。其中 `ledger.md`、`combined-acceptance.md` 记录逐项进度，red/green、JUnit、浏览器 trace、源码／产物哈希及审阅报告保留在同目录。

## 本阶段修改

| 编号 | 实现与实际观察 | 状态 |
| --- | --- | --- |
| #32 | 校验与普通生成受既有权威运行 pin 约束；只有 `--upgrade` 可改变 pin 集。按目标 profile 隔离求解，基础 pin 变化要求三配置一起生成。安装 helper 传当前 profile，解释器优先级测试改为临时 checkout。40 项专项通过；真实 base／CUDA／ROCm `--check` 全通过，三份 requirements 哈希不变；实际新增未固定依赖被拒绝。 | 分项审阅通过 |
| #43 | 独立只读 SQLite 连接查询任务表，1 秒等锁上限；失败 503，正常 JSON 保持，GPU warning 不阻塞。开发启动与 smoke 共用 HTTP／字段判断，Compose 改探测 `/api/health`。28 项专项及 shell 语法通过；真实宿主机／容器均完成 200 → 排他锁 503／任务 500 → 恢复 200，故障探测约 1.05／1.11 秒。 | 分项审阅通过 |
| #44 | 将路径移入 `use.launchOptions.executablePath`。真实指定 Chrome／默认 Chromium 均成功；无效路径明确失败、不回退。另用继承实际候选的临时配置开启 `chromiumSandbox`，两种浏览器再次通过，启动日志不含 `--no-sandbox`。 | 分项复审通过 |
| #12 | 共用入口使用准备好的 Python 与当前五个工作站 spec；Companion 独立同源配置／入口。最终 9 项行为专项验证成功、阶段失败、启动失败、浏览器失败及 TERM 清理；实际下游套件、CLI 与冻结后端入口均退出 0，零测试选择退出 1。 | 分项审阅通过 |

#32 的首次审阅复现了“普通生成可增加未固定依赖”的缺口，已用 red/green 和真实 uv 重现修复。#44 首次审阅指出默认 Playwright 带 `--no-sandbox`，补充沙箱开启验证；产品默认策略没有扩写。这些原始失败与审阅记录均保留。

## 合并验证

验证环境是新建的独立 Python 3.11.16 venv，安装实际基础 requirements 后，仅增加固定测试依赖及 Companion 已声明的 yt-dlp。51 个运行 pin 全部匹配，`uv pip check` 通过；不以版本不同的开发环境冒充运行依赖验收。

| 范围 | 本轮证据与边界 |
| --- | --- |
| 第一阶段 290 项专项 | 本轮当前后端再次 290 通过，覆盖凭据脱敏、进程组回收、缓存身份、导出保护、SRT 提交恢复、依赖、终态与重试清理；不与全量套件重复累加计数。 |
| 完整后端、前端、发布 smoke | 最终完整后端 **1030 通过**（99.15 秒）；实际共用入口依次完成后端 smoke 2 项、前端 **218 项／32 文件**、项目 TypeScript／Vite 构建和工作站真实浏览器 **17 项**，整体退出 0。CLI 与新冻结后端各通过 1 项真实同源 Companion 浏览器场景；零选择明确退出 1。各套件计数存在重叠，不相加。 |
| 缓存与导出实际工作流 | 同长度／同时间媒体换源、真实 FFmpeg／ffprobe、SQLite、子进程发布和用户文档保护通过；WhisperX 为受控替身。真实 API 导出／下载／解码、失败保留旧 SHA256、重试通过。未声称注入真实 DB commit 故障。 |
| Docker | 本轮新镜像针对全新／旧临时数据库迁移至 `20260714_01` 并提供 HTTP，旧任务／阶段诊断／队列行保留；独立数据库 readiness 故障与恢复通过。仅最小源码上下文参与构建，没有挂载业务 `data/`。 |
| macOS 依赖与冻结后端 | 在已验证的 32 包构建依赖闭包环境中新构建当前 App；声明 pin 和 `uv pip check` 通过。新冻结后端的实际根页面／空 jobs API 200、deep strict 签名通过；同环境的独立冻结探针完成 GUI 导入和合成 RS256 正确／错误签名验证。探针不等于实际登录。 |
| 既有修改保护 | 原完整 tracked patch 和状态已保存；文档索引更新前，完整 patch 的只读 reverse-apply 检查通过。最终对源码及其他既有文档再次检查通过，仅排除本轮主动更新实施状态／链接的两份 README 索引。原 Companion C 的 99 个来源文件哈希全部一致。未删除或重置原工作树。 |

## 平台与未验收范围

macOS 宿主机、Docker CPU 容器及本轮独立冻结后端有上述实际观察。Linux CUDA／WSL ROCm 安装入口仅 dry-run，依赖 profile 仅实际求解校验；未执行 GPU 安装、doctor、真实下载／ASR／供应商任务。macOS 缺少 `setsid`，不将受支持组件或 Docker 验证冒充完整 Linux／WSL 发布栈通过。

已有 Starlette/httpx 弃用提示及浏览器／工具诊断保留。额外独立检查 Playwright 配置的 tsc 命令因缺少 `@types/node` 未通过；该命令不属于项目 tsconfig，未为此增加依赖。构建闭包没有 pip 的一次 pip check 失败也保留，改用实际可用的 `uv pip check` 通过。LSP 不可用，未安装。

真实入口与退出码见 [QA 记录](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/manual-qa-report.md)和 [退出码清单](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/qa-exit-receipts.json)。另保存并人工查看了实际 Companion 空工作区[截图](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/companion-root.png)，截图服务已停止。

[最终 gate 报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-release-validation-2026-10-21/final-gate-review.md)：**APPROVE，blockers=[]，codeQualityStatus=WATCH**。独立核对了 339 个候选源码哈希、原 Companion 99 个文件及最终 JUnit；冻结候选摘要为 `4495d58d03df828b1e3aba8d532911305ce5c0c5ee5edd8feb2fc854e00142b7`。WATCH 保留缓存身份字典的静态类型维护建议及既有工具警告，未认定观察范围内的行为失败。

#12 审阅的冗余存在性测试和精确命令断言两项测试质量建议已清理；初次 10 项专项／1031 项完整后端的全通过记录保留，随后仅删除新加的重复检查，最终 9 项行为专项／1030 项完整后端仍全部通过，未删除既有失败用例。生产源码未变，相关实际入口证据继续适用。未经目标平台验证，不宣称整个产品可发布。
