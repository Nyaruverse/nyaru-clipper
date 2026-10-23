# Nyaru-Clipper 代码与架构改进计划

日期：2026-10-20。对应英文：[Code and Architecture Improvement Plan](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.md)。

本文件将六轮审阅的 **44 项已确认问题**整理为可分工、可验收的改进清单：**高 9 项、中 29 项、低 6 项**。保留原编号 #1–44；相近问题可一起处理，但不得合并编号或省略独立验收条件。

**2026-10-20 整理时状态：文档整理完成，44 项均待修复、待验收。**“已确认”沿用六轮审阅证据；当次没有重新执行全部复现，也没有实施代码修复。下文“验收要求”保留关闭问题的条件；建议顺序本身不构成排期或人员承诺。

**2026-10-21 实施更新：第一阶段 #1–7、#20、#21 已在 `codex/code-improvement-2026-10-21` 实现。**逐项实测、当时状态和限制见[第一阶段实施记录](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.zh-CN.md)。第一阶段结束时其余 35 项待实施，后续进度见下一段；不能据此视为全部 44 项或整体发布已验收。

**第二阶段完成：#32 → #43 → #44 → #12 已按[发布验证入口实施计划](/Users/drm/project/nyaru-clipper/docs/superpowers/plans/2026-10-21-phase2-release-validation.zh-CN.md)实现，并与第一阶段共同重新验收，最终 gate APPROVE、无阻塞项。**总账为 **13 项在记录范围内已验收、31 项待处理**；验收范围、平台限制和新证据见[第二阶段与合并结果](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.zh-CN.md)，主路径仍为宿主机 `uv + pnpm`，不构成全平台发布验收。

**第三阶段完成：#22 → #23 → #8 → #9 → #10 已实施、逐项验证，并与此前 13 项通过该轮合并验收；最终 gate APPROVE，无阻塞项。第三阶段结束时总账为 18 项在记录范围内已验收、26 项待处理。**详见[第三阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase3-improvement-results-2026-10-21.zh-CN.md)：后端 1042、前端 232、工作站浏览器 17 项通过，另有真实 Companion、Docker CPU 与 macOS 构建／冻结后端证据。全部修改保留在当前分支，未提交；平台及真实服务限制仍适用。

**第四阶段完成：#39 → #11 → #28 → #38 → #42 已依序实施、逐项验证，并与此前 18 项重新累计验收；最终 gate APPROVE、无阻塞项，维护债务 WATCH。第四阶段结束时总账为 23 项在记录范围内已验收、21 项待处理。**详见[第四阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase4-improvement-results-2026-10-21.zh-CN.md)：后端 1107、前端 244、工作站浏览器 17 项通过，当轮 CPU Docker、macOS 构建／冻结后端、真实 FFmpeg／API／Companion 场景通过。既有未提交修改与原工作树保留，未提交、推送、合并或安装 App；真实 GPU／供应商与安装版原生退出仍未验收。

**第五阶段完成：#37 → #24 → #19 → #30 → #27 已依序实施、逐项验证，并与此前23项重新累计验收；最终 gate APPROVE、无阻塞项，维护债务 WATCH。第五阶段结束时总账为28项在记录范围内已验收、16项待处理。**详见[第五阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase5-improvement-results-2026-10-21.zh-CN.md)：后端1152、前端285、工作站浏览器17项通过；当轮CPU Docker、macOS构建／冻结后端、真实字幕编辑／旧稿恢复／ASS／ZIP／libass烧录通过。旧稿兼容和历史非空工程缓存的一次身份迁移边界均有记录；既有未提交修改与原工作树保留，未提交或合并，Docker恢复原停止状态。GPU、真实供应商和安装版原生退出仍未验收。

**第六阶段完成：#26 → #31 → #29 → #41 → #33 已依序实施、逐项验证，并与此前28项重新累计验收；最终独立 gate APPROVE、无阻塞项，维护债务 WATCH。第六阶段结束时总账为33项在记录范围内已验收、11项待处理。**详见[第六阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase6-improvement-results-2026-10-21.zh-CN.md)：当轮后端1251、前端308、工作站浏览器17项及21个平台运行命令通过，高光导出、Unicode／八行字幕、5000条预览及平台边界见该历史记录；后续原生退出与最新累计结果见第七阶段。

**第七阶段完成：#17 → #25 → #14 → #18 → #34 已依序实施、逐项验证，并与此前33项累计验收；最终独立gate APPROVE、specCompliance PASS、无阻塞项，维护债务WATCH。第七阶段结束时总账为38项在记录范围内已验收、6项待处理。**详见[第七阶段与累计结果](/Users/drm/project/nyaru-clipper/docs/phase7-improvement-results-2026-10-21.zh-CN.md)：完整后端1329、前端317、工作站浏览器17项及21个平台最终命令通过。实际原生App完成双任务保存／退出／同构建重开，未选中5000条任务也完整保存；上传原子转移、批次容量校准及只读API有界日志均有真实入口证据。355源码冻结、492文件基线／236原状态／原Companion99哈希保护通过，既有未提交修改保留；未提交、推送、合并或替换安装版App，Docker恢复原停止状态。剩余#13、#15、#16、#35、#36、#40；真实GPU／供应商、完整Compose与所有字体仍未验收。

**第八阶段完成：#40 → #36 → #13 → #15 → #35 → #16 已依序实施、逐项验证，并与此前38项累计验收；最终独立gate APPROVE、specCompliance PASS、无阻塞项，codeQualityStatus WATCH。最新总账为44项在记录范围内已验收／0项待处理。**详见[第八阶段与44项累计结果](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.zh-CN.md)：当前后端1357、前端327、工作站浏览器17项及22个平台场景通过；最新原生App实际完成双任务保存／退出／同构建重开，5000条完整保留。355文件候选、497基线／249原状态／C99及九项明确删除的源链保护通过；未提交、推送、合并或替换安装版App，Docker恢复停止。上段38／6与剩余编号为第七阶段历史状态，以本段及当前44项矩阵为准；真实GPU／供应商、完整Compose及全站响应式／主题等仍未认证。

主要方向是修复数据保护与恢复边界、统一重复业务规则、缩小不必要的读写范围、移除确认失效的入口。现有证据不要求推倒重写，也不要求引入 Redis、Celery、Prefect 或新的前端状态管理库。

## 1. 适用范围与基线

项目按可信本机／局域网、单用户、单 GPU worker 的现有范围评估，不以公网多租户或横向扩容作为本计划目标。

| 代号 | 工作区与分支 | 审阅基线 HEAD |
| --- | --- | --- |
| W | 主工作站：`/Users/drm/project/nyaru-clipper`，`feat/arctime-pro-plugin` | `e8ea71085cf5c6ff6f671499872f5c166d31f89b` |
| C | macOS Companion／Studio：`/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper`，`codex/local-companion-macos` | `18ea3a0a7ee641cbb46d06d4348ebfa96dfc1dd2` |
| B | Web Companion 对照：`/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper`，`codex/local-companion-web` | `ccfb65176b3dd0451920694c5be17b19d856c0ff` |

审阅对象包含未提交源码，**不能仅凭 HEAD 重建全部审阅内容**。本次整理前，W／C／B 分别有 47／56／53 项既有 Git dirty entries；修复前应保存实际差异并再次确认目标 checkout，不覆盖现有手工改动。

条目中的 W、C 表示主要证据落点。C 的共享逻辑是否同步到 B，应逐文件比较；macOS 打包、日志和退出协商是原生端责任，不能机械复制到 Web。高光实验工作树只在早期审阅中涉及，不是本清单的独立实施目标；安装版 App 也不等同于当前源码。

## 2. 工作包、顺序与依赖

### 2.1 建议工作包

每项问题只归属一个主工作包。包名用于组织责任，不代表已指派人员。

| 工作包 | 责任模块 | 问题编号 | 包级完成条件 |
| --- | --- | --- | --- |
| A：数据保护、恢复与资源释放 | 流水线、worker、Companion 持久化、原生壳 | #1、#2、#3、#4、#5、#17、#20、#21、#22、#23、#25、#37 | 异常不破坏已发布数据；恢复可继续；资源和草稿有明确归属 |
| B：可重复部署与发布验证 | 构建依赖、Docker、安装／发布脚本、健康端点 | #6、#7、#12、#32、#43、#44 | 在目标干净环境构建启动，真实测试被执行，健康信号可信 |
| C：编辑、输出与状态契约 | 两套前端、字幕／高光／导出／报告 | #8、#9、#10、#11、#19、#24、#26、#27、#28、#29、#30、#38、#39、#41、#42 | 输入、草稿、时间轴、产物归属和状态在真实入口中一致 |
| D：长任务开销与读写边界 | 导出记录、上传、直播发布、详情、预览、SSE | #13、#14、#15、#18、#33、#34、#40 | 消除已确认的全量重复工作；保留必要完整性校验 |
| E：规则归一与废弃入口清理 | 供应商选择、ASR、共享导出工具、旧页面 | #16、#31、#35、#36 | 规则只维护一处，真实入口和有效测试保留，删除范围有引用证据 |

### 2.2 实施顺序

1. **先处理 9 项高优先级：#1–7、#20、#21。** A 与 B 可并行；凭据落盘、孤儿进程、旧缓存、成片破坏和拒绝操作副作用优先于一般清理。
2. **并行修通验证入口。** #12、#32、#43、#44 为后续发布提供可信入口；它们不能替代对应功能验收，也不能用“脚本绿了”跳过高优先级问题。
3. **随后处理可见错误和中断恢复。** A 中其余项及 C 的中等项优先；#25 涉及未保存草稿，#37 涉及已保存修订的可访问性，均须保留数据。
4. **再收敛性能与维护成本。** D、E 按实际工作流推进；低优先级项可随相关模块修复，但不得用删行数替代风险消除。

### 2.3 应协调实施但单独验收的组合

| 组合 | 共同边界 | 不能遗漏的区别 |
| --- | --- | --- |
| #11、#20、#21、#28、#39 | 任务、阶段、运行、队列、报告和产物投影 | 状态同步、终态恢复、拒绝无副作用、报告时序、产物种类是五个独立条件 |
| #4、#5、#23、#37 | 发布、检查点与身份 | 旧成片保护、SRT 提交窗口、半写 receipt、旧修订兼容不能由同一个成功重试测试代替 |
| #13、#15、#27 | 导出身份与历史记录 | 缩小状态记录、增量处理历史、格式专属依赖分别验收 |
| #14、#22 | 上传所有权与失败清理 | 减少整片复制不等于释放失败后的任务准入状态 |
| #8、#9、#10、#25、#38、#42 | 编辑／请求状态的归属 | 设置、分页、选择、原生退出、任务产物和新建草稿属于不同生命周期 |
| #29、#33、#41 | 字幕布局与预览 | grapheme 边界、小请求和溢出规则分别验证；不统一整个 UI 状态管理 |
| #34、#40 | 详情读取与事件刷新 | 单次读有界、回放请求合并两端都要改 |
| #2、#35、#36 | pipeline_support 与执行入口 | 先保留异常清理保证，再搬公共工具和删死入口，避免误删实际运行路径 |

## 3. 逐项改进与验收要求

以下逐字保留44项原问题、改进建议和独立验收条件；全部44项的当前限定验收状态以第八阶段累计记录及逐ID矩阵为准，0项待处理。原始证据轮次见第6节，条目中的代码位置属于原审阅证据，部分旧入口已按明确清单退役。每项至少列一个原代码入口，原报告保留完整调用链和复现细节。

### #1 下载凭据进入普通日志（高｜W）

- **问题与证据：** Cookie 进入 BBDown argv 后被完整记录。使用合成值已观察到落盘，未读取真实凭据，也未证明外泄。入口：[downloader.py](/Users/drm/project/nyaru-clipper/backend/app/services/downloader.py:40)、[命令日志器](/Users/drm/project/nyaru-clipper/backend/app/services/pipeline_support.py:62)。
- **改进：** 命令、stdout、stderr 在日志边界统一脱敏；不保存凭据副本作为诊断材料。
- **验收要求：** 合成秘密值经过真实构参及日志链路，所有相关输出均不包含该值；普通错误信息仍可诊断。

### #2 异常出口未回收 ASR 子进程组（高｜W）

- **问题与证据：** 进度回调抛错后，实际无害子进程仍存活，而外层可能清除执行跟踪。入口：[结构化执行器](/Users/drm/project/nyaru-clipper/backend/app/services/pipeline_support.py:194)。
- **改进：** 从 Popen 成功起覆盖登记、回调、日志和持久化异常；先终止并等待进程组，再移除跟踪。
- **验收要求：** 分别注入这些失败，子进程及派生进程均被回收；正常完成、取消和强制终止保持原语义。

### #3 媒体／ASR 缓存缺少内容和参数身份（高｜W）

- **问题与证据：** 同长度换源仍复用旧音频已复现；ASR 模型／语言身份缺口由调用链确认。入口：[media_prep.py](/Users/drm/project/nyaru-clipper/backend/app/services/media_prep.py:96)、[asr_whisperx.py](/Users/drm/project/nyaru-clipper/backend/app/services/asr_whisperx.py:221)。
- **改进：** 媒体绑定源内容；ASR 绑定音频及有效识别、对齐参数；身份变化使依赖它的下游缓存失效。
- **验收要求：** 同长度换源、换模型／语言／对齐参数均触发必要重算；身份未变可恢复；不会混用不同配置的分块结果。

### #4 导出失败破坏旧成片（高｜W）

- **问题与证据：** 编码直接覆盖最终路径；注入部分写入失败后旧成片受损，记录仍存在。入口：[clip_export.py](/Users/drm/project/nyaru-clipper/backend/app/services/clip_export.py:59)。
- **改进：** 同目录唯一临时文件编码、验证后原子发布；明确相同区间并发导出的发布规则。
- **验收要求：** 编码失败时旧文件哈希和可用记录不变；成功才替换；并发不会产生部分文件或互相矛盾的记录。

### #5 翻译 SRT 与检查点提交窗口无法恢复（高｜C）

- **问题与证据：** SRT 已替换、哈希尚未保存时中断，重试用旧哈希拒绝有效新结果。入口：[saozi_translation.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/saozi_translation.py:140)。
- **改进：** 从已验证持久化批次确定性重建期望字幕；只接纳与期望完全一致的磁盘结果，继续检测人工修改。
- **验收要求：** 在发布边界中断后可恢复，不丢翻译批次；任意用户改动不会被错误接纳或静默覆盖。

### #6 macOS 干净构建缺少运行依赖（高｜C）

- **问题与证据：** 构建依赖闭包缺少 httpx、PyJWT 与 crypto 支持，而 GUI 导入和 RS256 验证需要它们；原审阅未重建 App。入口：[requirements-build.txt](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/desktop/macos/requirements-build.txt:1)。
- **改进：** 在真正使用的构建依赖中声明 httpx、PyJWT[crypto]，核对入口依赖闭包。
- **验收要求：** 按文档从干净环境构建并启动冻结程序；认证模块可导入，合成 RS256 验证可执行。真实登录如未做，单列未验收。

### #7 Docker 镜像遗漏迁移配置与版本目录（高｜W）

- **问题与证据：** 镜像复制 app，却未带入 Alembic 文件；隔离缺失配置复现失败，原审阅未构建镜像。入口：[api.Dockerfile](/Users/drm/project/nyaru-clipper/infra/docker/api.Dockerfile:42)。
- **改进：** 将必要配置和迁移版本目录加入镜像，保持 Docker 为备用部署路径。
- **验收要求：** 实际镜像针对全新临时数据库可迁移并启动 API；同时验证已有测试数据库升级，不能仅检查 COPY 文本。

### #8 设置保存清掉请求期间的新编辑（中｜C）

- **问题与证据：** 延迟保存响应无条件清空草稿，后续语言选择丢失且显示已保存。入口：[StudioSettings.tsx](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/StudioSettings.tsx:14)。
- **改进：** 只清除与提交快照一致的草稿；或在保存期间禁用会冲突的输入。
- **验收要求：** 延迟响应期间的新编辑被保留，或按清晰禁用规则不可产生；失败可重试，“已保存”准确。

### #9 切换任务后分页超界（中｜C）

- **问题与证据：** 长任务第二页切到短任务后列表为空且翻页控件消失，实际组件已复现。入口：[CueEditor.tsx](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/CueEditor.tsx:22)。
- **改进：** 页码受当前结果数约束，按任务身份重置必要局部状态。
- **验收要求：** 21 条任务第二页切到 2 条任务、筛选缩减等情况均可见有效条目；普通文字编辑不重置全部状态。

### #10 主动空选被自动选中覆盖（中｜C）

- **问题与证据：** 点击取消选择后，父组件 effect 立即勾选第一条。入口：[Companion.tsx](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/Companion.tsx:108)。
- **改进：** 将加载时的初始选择与用户主动空选分开，只清理不存在的 ID。
- **验收要求：** 取消后保持零选择，批量操作不会误改第一条；切换文档与删除条目后的选择仍有效。

### #11 手动导出的多套状态未同步（中｜W）

- **问题与证据：** 导出失败后重试成功，Task 仍 failed，v2 StageRun 也可能停留旧状态。入口：[状态更新](/Users/drm/project/nyaru-clipper/backend/app/services/pipeline_support.py:569)、[v2 读模型](/Users/drm/project/nyaru-clipper/backend/app/repositories/workstation.py:423)。
- **改进：** 明确手动导出与流水线阶段的关系，用一个转换入口同步任务、阶段、运行和事件。
- **验收要求：** 失败→成功重试后各投影符合选定语义；其他阶段仍有错误时，不能把整个任务强行改为 success。

### #12 发布 smoke 指向已不存在的测试（中｜W）

- **问题与证据：** 当前选择 `e2e/task-flow.spec.ts` 得到 No tests found。入口：[共用 smoke 脚本](/Users/drm/project/nyaru-clipper/scripts/_release_smoke_common.sh:161)。
- **改进：** 对齐真实用户入口和现有测试，纳入 Companion 对应交付流程，检查测试确实被选择和执行。
- **验收要求：** 各支持发布路径运行有效用户场景；零测试必须失败。`--list` 非空只是前置检查，不是完整验收。

### #13 导出历史重复保存整份字幕，进度与轮询放大读写（中｜C）

- **问题与证据：** 5,000 条字幕、20 个输出的隔离样例，响应约 23.48 MB、落盘 JSON 约 38.30 MB；不是线上基准。入口：[subtitle_exports.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_exports.py:30)。
- **改进：** 不可变完整快照保留一次；列表、进度用摘要／引用；完成空闲态停止无效轮询，兼容已有 registry/receipt。
- **验收要求：** 列表不内嵌完整 document，进度不反复重写全部历史快照；旧输出仍能验证、下载和重现，完成态停止轮询。

### #14 自有上传暂存被再次整片复制（中｜C）

- **问题与证据：** 空间检查仅预算一份，但上传后还复制成 source.mp4；双份占用由调用链确认，未实际写满磁盘。入口：[saozi_api.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/saozi_api.py:28)、[workflow.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/workflow.py:64)。
- **改进：** 应用拥有且同文件系统的暂存采用原子移动；外部用户文件保持复制；衍生产物另计空间。
- **验收要求：** 自有上传不再出现第二次整片复制；外部原片不变；空间不足和跨文件系统路径有明确处理。

### #15 直播追加时重复扫描、哈希全部旧输出（中｜C）

- **问题与证据：** N 段约有 `2×Σ(1..N)` 次检查；240 段对应 57,840 次检查的推算，不是重复编码或长直播实测。入口：[saozi_live.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/saozi_live.py:54)。
- **改进：** 只处理新增或翻译／模板输入变化的片段，恢复、下载等边界保留完整验证。
- **验收要求：** 统计真实追加调用，未变历史不再形成平方级检查；修改输入更新正确输出，损坏产物仍被检测。

### #16 旧页面与专属测试没有退出维护范围（中｜W）

- **问题与证据：** TaskDetailPage／NewTaskPage 无生产引用；1,558 行是页面加专属测试候选上限，不是净删行承诺。入口：[真实路由](/Users/drm/project/nyaru-clipper/web/src/router.tsx:11)、[旧 smoke](/Users/drm/project/nyaru-clipper/web/src/test/smoke.test.tsx:65)。
- **改进：** 有效断言迁到真实路由后删除死页面、附属失效包装及专属旧测试。
- **验收要求：** 当前工作站入口承接有效行为检查；无悬空引用；保留仍被消费的 legacy API/types 和 ExistingReviewWorkspace。

### #17 App 启动清空上一次日志（中｜C）

- **问题与证据：** Foundation 临时文件实验确认 createFile 清空原日志；非安装版重启验收。入口：[App.swift](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/desktop/macos/App.swift:52)。
- **改进：** 不存在时才创建并追加，或采用有界轮转。
- **验收要求：** 预置故障日志后重启，旧内容或轮转副本仍在，新日志可继续写入；日志同时满足 #1 的脱敏原则。

### #18 逐个登记产物时反复遍历整个目录（低｜W）

- **问题与证据：** N 个分块引发约 N 次全目录计量；静态调用链确认，未测实际延迟。入口：[storage.py](/Users/drm/project/nyaru-clipper/backend/app/services/storage.py:85)。
- **改进：** 一批登记结束后统一刷新容量，复用单一计量逻辑。
- **验收要求：** 批量登记及恢复旧产物时扫描次数按批次有界，最终容量正确。

### #19 时间格式化产生自身无法解析的秒数（低｜C）

- **问题与证据：** 59.99→00:60.0、3599.99→59:60.0，现有解析器拒绝。入口：[companionApi.ts](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/companionApi.ts:74)。
- **改进：** 先将总时长舍入到整数十分之一秒，再拆分分钟与秒。
- **验收要求：** 分钟／小时进位边界不产生秒数 60；格式化结果可以按既有支持范围重新解析，误差符合显示精度。

### #20 任务终态与队列收尾之间中断后永久堵队列（高｜W）

- **问题与证据：** 隔离数据库中保留 success job＋running 队列项，后续领取返回 None。入口：[task_runner.py](/Users/drm/project/nyaru-clipper/backend/app/services/task_runner.py:523)、[worker.py](/Users/drm/project/nyaru-clipper/backend/app/worker.py:264)。
- **改进：** 将终态与队列完成纳入同一受锁事务，为历史不一致组合提供幂等恢复；缩短超时不能代替修复。
- **验收要求：** 在终态边界中断后，新 worker 会话能领取下一项，原任务终态、队列与运行历史一致，重复恢复安全。

### #21 被拒绝的重新排队已删除文件并提交状态（高｜W）

- **问题与证据：** 真实批量处理得到 rejected，但 task/job 已 pending、字幕已删除且新增运行记录。入口：[retry 副作用](/Users/drm/project/nyaru-clipper/backend/app/repositories/tasks.py:452)、[批量提交](/Users/drm/project/nyaru-clipper/backend/app/api/routes/workstation_tasks.py:172)。
- **改进：** 队列锁内先验证拒绝条件；逐项回滚数据库变更，文件清理放在可恢复的接受后步骤。savepoint 无法撤销 unlink。
- **验收要求：** rejected 前后任务、阶段、job、运行、产物记录和文件均不变；混合批量中合法项正常接受。

### #22 错误处理再次写盘失败，任务准入状态不释放（中｜C）

- **问题与证据：** 上传和错误记录同时注入 ENOSPC，首次 500；恢复写盘后下一任务仍 409。入口：[上传异常处理](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/saozi_api.py:52)。
- **改进：** finally 无条件释放 active；错误日志持久化和暂存删除不得阻止释放，检查 manager.run 同类清理。
- **验收要求：** 上述双重失败及删除失败后，恢复写盘即可接收下一任务，不依赖重启；失败证据尽可能保留。

### #23 半写 receipt 让同一导出永久失败（中｜C）

- **问题与证据：** receipt 写入 10 字节后注入 ENOSPC，成品未发布；后续重试仍因坏 JSON 失败。入口：[receipt 恢复](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_exports.py:230)。
- **改进：** 同目录临时完整写入后原子且排他发布；保留坏证据后恢复尚未发布的输出。
- **验收要求：** 半写中断可重试成功，源文件不变；已存在且无法验证的成品仍拒绝覆盖，不能一律忽略校验失败。

### #24 合并字幕依赖未保证的时间排序（中｜C）

- **问题与证据：** `[1,5]` 与编辑为 `[0,8]` 的下一条合并成 `[1,8]`，丢失早段显示。入口：[mergeCues](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/subtitleDocument.ts:104)。
- **改进：** 合并起点取所选条目最小值，终点取最大值；保留原有文字、样式顺序。
- **验收要求：** 先改时间顺序再合并得到 `[0,8]`，0.5 秒仍显示字幕；保存和导出使用相同时间范围。

### #25 原生退出未与未保存草稿协商（中｜C）

- **问题与证据：** 650 ms 自动保存前或保存 409 后退出，内存草稿可丢失。真实 hook＋独立 WKWebView 宿主已复现，非安装版完整闭环。入口：[useSubtitleDocument](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/useSubtitleDocument.ts:69)、[原生退出](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/desktop/macos/App.swift:111)。
- **改进：** 停后端前询问 dirty 状态，等待保存成功，或明确放弃；保存失败允许取消退出。
- **验收要求：** 快速退出、保存失败、取消退出和明确放弃均覆盖；安装版编辑→退出→重开保留已选择保存的修订。单纯增加等待时间不算完成。

### #26 高光默认范围错误采用字幕终点（中｜W）

- **问题与证据：** 60 秒媒体、10–30 秒镜头、字幕 20 秒结束，默认输出 8–20 而非 8–32。入口：[highlights.py](/Users/drm/project/nyaru-clipper/backend/app/services/highlights.py:93)。
- **改进：** 采用可信媒体探测时长作为上界；缺少时长时保留明确缺失语义。
- **验收要求：** 原场景得到 8–32；覆盖尾部静音、无字幕、缺少时长；前端提交范围与展示一致。

### #27 ASS／烧录被无关 ArcTime 模板绑定（中｜C）

- **问题与证据：** 删除 ATPJ 后旧任务 ASS 请求 409；去掉无关工程 ID 后成功且内容相同。烧录共用预检查，但原审阅未实际编码。入口：[subtitle_exports.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_exports.py:173)。
- **改进：** 仅 ArcTime ZIP 读取工程模板并计入输出身份；前端按格式发送适用字段。
- **验收要求：** 删除／切换 ATPJ 不阻断或重复生成相同 ASS／烧录输出；ArcTime 仍验证模板完整性，补实际烧录链路检查。

### #28 最终报告仍显示 running（低｜W）

- **问题与证据：** 真实 runner 已 success，下载报告仍写任务及 report 阶段 running。入口：[reporting.py](/Users/drm/project/nyaru-clipper/backend/app/services/reporting.py:31)。
- **改进：** 终态确定后发布最终报告；若保留运行快照，清楚区分它与最终报告。
- **验收要求：** 通过真实 runner 检查成功、失败场景的报告与最终状态；只测模板函数不足以覆盖时序。

### #29 自动换行拆开组合字符（低｜C）

- **问题与证据：** ZWJ emoji／旗帜被拆成不同 ASS 行，原审阅未检查最终字体像素。入口：[subtitle_render.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_render.py:18)。
- **改进：** 按完整 grapheme 边界换行，前端估行同步；强调范围继续保持约定的 codepoint 索引。
- **验收要求：** `👩‍💻`、`A🇨🇳` 等窄区域样例不拆字符组合，强调索引正确，并用实际字体渲染检查。

### #30 四位切片编号被导出模型拒绝（低｜C）

- **问题与证据：** 生成器可产生 clip-1000.mp4，输入只接受三位；真实模型已验证，未录制千段。入口：[live_state.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/live_state.py:149)、[subtitle_inputs.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_inputs.py:26)。
- **改进：** 文件名约束与生成器最小三位规则一致，继续限制为当前任务的完成切片。
- **验收要求：** 999／1000 均能经过手动和自动导出；非法路径、未完成或不属于任务的文件仍拒绝。

### #31 CLI／GUI 重复解释供应商配置并产生分歧（中｜C）

- **问题与证据：** GUI 选择 ChatGPT、保留旧 DeepSeek 配置时，CLI 新任务选旧供应商，ChatGPT resume 失败。已验证选择及 CLI 分支，未请求真实供应商。入口：[cli.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/cli.py:17)、[companion_llm.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/companion_llm.py:13)。
- **改进：** 共用“已有任务优先固定供应商／模型，否则读取当前配置”的规则；不支持时明确拒绝，不静默换供应商。
- **验收要求：** 两入口在相同配置下选择一致；resume 尊重任务记录；有效旧 Key 不导致隐式回退。

### #32 锁定依赖校验混入最新版本解析（中｜W）

- **问题与证据：** 真实检查脚本配受控解析输出，只改变可见版本即从成功变失败；不是今天在线解析失败的证明。入口：[export_backend_requirements.sh](/Users/drm/project/nyaru-clipper/scripts/export_backend_requirements.sh:186)。
- **改进：** 确定性校验与显式升级分开，指定权威锁定来源；保留 CUDA／ROCm 平台契约，不手改生成 requirements。
- **验收要求：** 仓库固定时，可见新版本不影响校验；真实声明漂移仍可发现；本平台安装不受无关平台重新求解阻断。

### #33 单场景预览每次发送并校验整份字幕稿（中｜C）

- **问题与证据：** 5,000 条字幕切换两个场景，各发送约 1.53 MB；完整观看约 7.67 GB 是推算，不是实测，更不是每帧请求。入口：[DocumentOverlay.tsx](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/web/src/companion/DocumentOverlay.tsx:35)。
- **改进：** 只传当前活跃字幕、全局样式、时刻／尺寸及来源身份；来源校验避免重建整稿；保存、导出继续用完整文档。
- **验收要求：** 请求规模随活跃字幕数变化，而非全稿长度；重叠字幕和样式显示正确，源校验不削弱，切场景缓存仍有效。

### #34 详情查询全量读日志并创建目录（中｜W）

- **问题与证据：** 为 11 字符摘要两次各读约 10 MB，详情查询还重建缺失目录；未模拟只读磁盘故障。入口：[summarize_stage_log](/Users/drm/project/nyaru-clipper/backend/app/services/storage.py:49)。
- **改进：** 分离纯路径定位与 mkdir，摘要使用有明确上限的尾读或已持久化摘要。
- **验收要求：** 10 MB 日志的读取字节有界；空日志、尾部空行、超长行有明确处理；任何详情读取都不创建目录。

### #35 已替代 ASR 入口、专属测试和地图仍保留（中｜W）

- **问题与证据：** 全树引用确认旧直接执行、manifest 发布入口和非结构化 runner 无产品调用；相关声明体 224 行不是最终净删行量。入口：[asr_whisperx.py](/Users/drm/project/nyaru-clipper/backend/app/services/asr_whisperx.py:723)、[旧 runner](/Users/drm/project/nyaru-clipper/backend/app/services/pipeline_support.py:86)。
- **改进：** 迁移有效断言到现用分块执行和发布路径，删除失效入口及专属辅助，更新 AGENTS 地图。
- **验收要求：** 无悬空源码／动态／测试／文档引用；现用推理、恢复和发布仍受有效测试覆盖；共享 manifest 和 `_persist_asr_artifacts` 保留。附带清理见第 5 节，不新增编号。

### #36 通用文件导出反向依赖旧工作站 ORM／调度（中｜C）

- **问题与证据：** 只复用普通日志／进程函数却导入 SQLModel、数据库和事件层；模块加载已实测，不证明访问数据库或包大小。入口：[export_encoding.py](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/services/export_encoding.py:7)。
- **改进：** 公共工具移到不依赖调度／DB 的模块；编码接收窄配置；完整验证后才移除不再必要的 Companion 依赖。
- **验收要求：** 干净进程导入通用导出不加载旧 ORM／DB／事件模块；Windows AMF 回退、路径替换、错误处理保留，冻结包实际可用。

### #37 字幕来源身份误包含运行诊断（中｜C）

- **问题与证据：** 自动导出成功清除错误字段后，源与编辑稿字节均未变，但修订 GET／POST 变为 409。入口：[base_document](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_document.py:86)。
- **改进：** 指纹只涵盖媒体、字幕及必要时轴／画布信息，排除诊断和导出状态；为旧指纹保存稿设计兼容或迁移。
- **验收要求：** 导出失败→保存修订→成功重试后修订仍可读写；真正源变化仍拒绝；已有稿不会因修复被作废。此项是访问失效，不是文件删除。

### #38 新导出结果丢失任务归属（中｜W）

- **问题与证据：** A 导出后切回缓存 B，B 标题下仍显示 A 下载链接，真实组件已复现。入口：[ExistingReviewWorkspace.tsx](/Users/drm/project/nyaru-clipper/web/src/workstation/features/task-overview/ExistingReviewWorkspace.tsx:338)。
- **改进：** 以 taskId 定义工作区生命周期，或将结果写入对应任务的查询缓存；减少无归属的重复本地状态。
- **验收要求：** A→已缓存 B 不出现 A 的产物；异步导出跨任务完成仍写回 A，正常 A 结果可见。

### #39 产物生产者与两版就绪映射不一致（中｜W）

- **问题与证据：** 真正登记的 clip_export 不被两套读模型识别；全部任务状态 success 仍 missing。入口：[生产登记](/Users/drm/project/nyaru-clipper/backend/app/services/clip_export.py:251)、[v2 映射](/Users/drm/project/nyaru-clipper/backend/app/repositories/workstation.py:63)。
- **改进：** 共用存储种类与对外语义映射，贯通两版详情和列表 SQL；不必合并整个 repository。
- **验收要求：** 用真实登记函数产生 fixture；已有文件正确显示 ready，ready 筛选命中、missing 不命中；移除文件后各读模型一致转为不可用。

### #40 历史事件回放逐条触发重复快照查询（中｜W）

- **问题与证据：** 已缓存查询＋延迟响应下，100 条事件启动 100 次摘要 fetch；未测全系统负载。入口：[useWorkstationEvents.ts](/Users/drm/project/nyaru-clipper/web/src/workstation/api/useWorkstationEvents.ts:52)。
- **改进：** 短回放窗口按 queryKey／taskId 合并失效，AbortSignal 贯通 HTTP；保留持久事件和断线游标。
- **验收要求：** 同样 100 条回放时，请求按合并窗口有界，过时请求收到取消；最终快照正确且断线恢复不丢事件语义。

### #41 两套字幕自动布局的溢出保护分叉（中｜C）

- **问题与证据：** 同一 8 行大字号字幕，开启粗体后从拒绝变成功但首行完全不可见；真实 libass／PNG 已证实，未烧录最终视频。入口：[样式分流](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_style.py:134)、[文档布局](/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/backend/app/arctime/subtitle_render.py:90)。
- **改进：** 基础样式、高级样式、编辑文档共享自动布局及溢出规则，保留输入适配和自由坐标的独立语义。
- **验收要求：** 原溢出样例在各入口一致拒绝或按明确规则处理；预览、ASS 和实际烧录一致；不会静默裁去文本，自由定位仍符合约定。

### #42 旧来源检查响应覆盖新的任务草稿（中｜W）

- **问题与证据：** 检查 B 站 A 期间切本地，迟到 A 响应把页面切回旧来源；真实组件已复现，未创建实际任务。入口：[NewTaskDrawer.tsx](/Users/drm/project/nyaru-clipper/web/src/workstation/features/task-create/NewTaskDrawer.tsx:150)。
- **改进：** 检查动作携带来源、URL 与草稿代次，reducer 仅接纳当前有效结果；取消请求不能代替身份守卫。
- **验收要求：** 切本地、改 URL、放弃再打开后，迟到旧响应均不能改新草稿；当前有效检查仍正常生效。

### #43 健康端点未探测数据库却宣称正常（中｜W）

- **问题与证据：** 运行期间临时数据库不可连接，tasks=500 而 health=200/database=ok。入口：[health.py](/Users/drm/project/nyaru-clipper/backend/app/api/routes/health.py:12)。
- **改进：** readiness 做有界的真实 DB 探测；若另设 liveness，明确含义并同步启动、smoke 和文档。
- **验收要求：** 正常→故障→恢复期间健康信号与实际依赖一致，失败不报成功；调用方遵守契约。原证据不覆盖存储写能力，不另计此类缺陷。

### #44 指定 Chrome 路径未进入启动选项（低｜W）

- **问题与证据：** 环境变量写入 use.executablePath，真实 runner 的有效 launchOptions 不含它；未启动浏览器。入口：[playwright.config.ts](/Users/drm/project/nyaru-clipper/web/playwright.config.ts:8)。
- **改进：** 放入 `use.launchOptions.executablePath`，保留未设置时的默认行为。
- **验收要求：** runner 解析到指定路径，并实际启动选定的可用浏览器；无环境变量时默认路径仍正常。

## 4. 关闭问题的证据与记录

修复时先确认当前代码仍有该问题，再在独立分支／工作区实施所选范围。对涉及旧数据格式的 #3、#5、#13、#20、#23、#37，必须处理已有状态；不能只让新任务成功。

每个问题关闭前保留以下记录。负责人未指定、提交未产生时写“未指派／无”，不得填写推测值。

| 字段 | 必填内容 |
| --- | --- |
| 问题 | 原 ID、目标 checkout、实际 HEAD 与工作区差异范围 |
| 责任与状态 | 负责人；待修复 → 修复中 → 待验收 → 已验收，阻塞时写明实际条件 |
| 变更 | 实现提交／补丁、兼容与迁移策略、涉及的其他 ID |
| 回归 | 原缺陷场景在修复前的证据；修复后逐项预期结果；必要的相邻功能检查 |
| 实际工作流 | 对应 UI／API／原生／打包路径的观察结果，明确模拟了哪些外部边界 |
| 数据保护 | 源媒体、字幕修订、已发布成片和凭据是否按约定保留；不得把秘密写入证据 |
| 结论 | 验收日期、证据位置、尚未覆盖的环境及回退方式 |

仅修改函数、测试变绿、构建成功、生成新安装包都不自动等于“已验收”。尤其是缺陷复现测试，其通过通常表示**缺陷仍存在**；修复后的断言必须验证期望行为。验收范围限定到实际执行的平台，不把本机结果扩大为全部 CUDA／ROCm／Docker／macOS 环境通过。

## 5. 精简范围与应保留的能力

可以与主条目一起处理、但不增加 44 项计数的备注：

- **#16 附属旧包装：** 真实路由与有效断言迁移后，核对旧 AppShell／WorkspacePage 包装的引用再删除。
- **#35 的 cleanup 入口：** 约 39 行入口只有测试调用，应明确保留意图或移除；不能为了接线而在成功流程自动删除恢复材料。
- **#35 的 orjson 直接声明：** 当前源码／配置没有消费点，可在再次核对依赖后删除直接声明，并用生成器更新产物；不手改锁定 requirements。
- **未消费的 translation_fallback_model_name：** 上一轮仅为单行清理备注。可移除无效选项，不借此新增未要求的供应商自动回退。
- **#36 的 SQLModel／pydantic-settings：** 只有解耦、全树依赖核对和打包验收之后，才能移除 Companion 不再需要的依赖。

应保留：现用 legacy API 与 types、ExistingReviewWorkspace、工作站／Companion 两个入口、VOD／live 不同生命周期、StageRun 的历史职责、共享 ASR 推理和发布工具、录制中 CSS 降级预览、完成后的 libass 预览，以及路径、来源、模型输出的边界校验。

第 #41 项的两个渲染入口都有生产消费者，应先归一规则，不能按相似代码直接删除。没有证据的循环导入、runtime 缓存、迁移猜测，以及已公开说明的安装路径限制不属于新增确认项。现有隔离体积／调用计数和静态复杂度不等于真实延迟、包体积或线上故障率。

## 6. 审阅来源与证据边界

| 轮次 | 原编号 | 高／中／低 | 原始报告 |
| --- | --- | --- | --- |
| R1 | #1–19 | 7／10／2 | [全项目审阅](/Users/drm/project/nyaru-clipper/.omo/evidence/full-project-code-audit-2026-10-20.zh-CN.md) |
| R2 | #20–24 | 2／3／0 | [第二轮](/Users/drm/project/nyaru-clipper/.omo/evidence/second-pass-code-audit-2026-10-20.zh-CN.md) |
| R3 | #25–30 | 0／3／3 | [第三轮](/Users/drm/project/nyaru-clipper/.omo/evidence/third-pass-code-audit-2026-10-20.zh-CN.md) |
| R4 | #31–36 | 0／6／0 | [第四轮架构审阅](/Users/drm/project/nyaru-clipper/.omo/evidence/fourth-pass-architecture-audit-2026-10-20.zh-CN.md) |
| R5 | #37–40 | 0／4／0 | [第五轮架构审阅](/Users/drm/project/nyaru-clipper/.omo/evidence/fifth-pass-architecture-audit-2026-10-20.zh-CN.md) |
| R6 | #41–44 | 0／3／1 | [第六轮架构审阅](/Users/drm/project/nyaru-clipper/.omo/evidence/sixth-pass-architecture-audit-2026-10-20.zh-CN.md) |
| 合计 | #1–44 | **9／29／6** | 原编号不变，未编号清理备注不计入 |

本文件已给出每项影响、改进方向和验收要求，可独立用作实施清单。原始报告和复现材料位于本机被 Git 忽略的 `.omo/evidence/`；链接采用本机绝对路径。共享给合作者时，应按目标 checkout 映射代码路径，并为所选修复另行归档必要的脱敏复现材料；不能假定对方具备本机工作树、临时目录或虚拟环境，也不应整包公开运行数据。

六轮证据包括调用链核对、真实组件／路由的隔离复现、故障注入、局部渲染和数据量测量；**没有覆盖全部真实 GPU／模型、外部供应商、长直播、干净安装矩阵或安装版完整流程**。部分 Python 检查沿用 pytest 9.1.1，超过主后端 `<9` 声明；不能当作其干净依赖验收。第 #25 的原生证据、第 #41 的像素证据等适用范围已在条目中注明。

本次只整理文档与索引，未改变实现、真实任务、录制／监控状态、依赖或 Git 分支。44 项是六轮已确认的清单，不是“已经穷尽所有问题”的保证。
