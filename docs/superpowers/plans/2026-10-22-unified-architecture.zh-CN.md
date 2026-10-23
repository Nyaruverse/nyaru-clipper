# 方案 B：统一架构分阶段实施计划

> **For agentic workers:** 后续获得实现授权后使用 `executing-plans` 逐任务执行；仅在用户另行选择委派时使用 `subagent-driven-development`。所有复选框仅在保存匹配证据后勾选。本文件不授权启动实现或委派。

**Goal:** 保留桌面创作与 Linux／WSL GPU 工作站能力，最终以同一界面、任务契约与业务核心承载现有流程。

**Architecture:** Companion 为产品主线；先打通工作站产物进入现有字幕编辑与导出的完整链路，再统一调度和状态。引擎与录播／直播流程保留，历史数据按任务接管，旧系统最终退出写入。

**Tech Stack:** Python `>=3.11,<3.12`、FastAPI、SQLModel／SQLite／Alembic、React／TypeScript／Vite、Node `>=20`、pnpm `10.33.2`、Swift／AppKit／WebKit、现有 FFmpeg／libass、whisper.cpp／WhisperX。

整理日期：2026-10-22（Asia/Shanghai）；最新执行观察：2026-10-22。状态：**P0—P4 及 P5 迁移／独立恢复实现已完成本机候选验证；P5 平台／生产资格待验收，P6 未执行；累计架构验收未完成**。对应[架构设计](../specs/2026-10-22-unified-architecture-design.zh-CN.md)、[英文计划](2026-10-22-unified-architecture.md)、[实际执行记录](../../unified-architecture-execution-2026-10-22.zh-CN.md)及[候选操作指南](../../unified-runtime-guide.zh-CN.md)。以下审阅索引中的“本轮仅文档”描述此前设计修订，不代表本次执行状态。

## 审阅修订索引（2026-10-22）

| 审阅项 | 本计划修订位置 | 规范约束位置 |
| --- | --- | --- |
| U1 接管前复核 | [P0／P5执行补充](#rev-u1) | [设计6.1](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-u1) |
| U2 整组发布与收据 | [P2执行补充](#rev-u2) | [设计5.1](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-u2) |
| U3 独立恢复入口 | [P4／P5执行补充](#rev-u3) | [设计7.1](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-u3) |
| U4 全局状态迁移 | [P0／P4／P5执行补充](#rev-u4) | [设计6.2](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-u4) |
| U5 直播子步骤 | [P3执行补充](#rev-u5) | [设计4.1](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-u5) |
| U6 实例身份／冲突 | [P0／P2／P5执行补充](#rev-u6) | [设计6.3](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-u6) |
| U7 固定验收矩阵 | [全部阶段执行补充](#rev-u7) | [设计8.1](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-u7) |

本索引只关闭文档缺口；新增工具、协议和所有M项仍待实现／执行。第12节补充与原阶段一起执行，不能只完成旧复选框便宣布阶段通过。

## 第二轮修订定位（Rv1—Rv5）

| 残余项 | 本计划位置 | 设计规范 |
| --- | --- | --- |
| Rv1 跨批次回退 | [P2／P5执行补充](#rev-rv1) | [设计7.2](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-rv1) |
| Rv2 锁与崩溃保护 | [P0／P3／P4／P5执行补充](#rev-rv2) | [设计6.4](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-rv2) |
| Rv3 多根恢复 | [P4／P5执行补充](#rev-rv3) | [设计7.3](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-rv3) |
| Rv4 互斥恢复判定 | [P2执行补充](#rev-rv4) | [设计5.1](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-rv4) |
| Rv5 产品导出验收 | [P0／P1／P5执行补充](#rev-rv5) | [设计8.2](../specs/2026-10-22-unified-architecture-design.zh-CN.md#rev-rv5) |

本轮只修订文档；第13节与原阶段、第12节共同构成执行门槛。M23—M28不能因为旧M项已通过而跳过。

## Global Constraints

- 用户已于2026-10-22授权开始实施；下文未勾选项仍是计划，实际结果以执行记录为准。实施授权不替代正式切换、安装与删除授权。
- 可信单机／LAN、单用户、单 GPU重处理执行者；宿主机 uv＋pnpm为主、Docker备用。不引入调度框架或额外依赖。
- 保留两种 ASR、既有翻译方向与供应商、人工确认导出策略、直播停止与恢复语义、模板快照、原生退出保存。
- 不启动或恢复正式录制／监控，不自动重连直播，不迁移运行中任务，不调用真实外部 AI／下载模型，除非后续范围明确包含这些动作。
- 保留所有既有未提交内容。未来先核验分支／HEAD／dirty状态；逐路径提交须另获授权，不批量暂存，不reset／clean，不推送／合并。
- 不手改生成 requirements、OpenAPI 或 TypeScript契约。变更契约时通过现有生成器产生候选并核对差异。
- 迁移、验证和回退先使用独立临时根、数据库、端口与脱敏夹具。正式数据、模型、授权、媒体、备份和原始证据不进Git。
- 一个任务同一时刻只归一个系统写入；同主机／同GPU的旧、新系统不能并发执行重任务；新队列初始暂停；不得让旧程序连接新schema。
- 文档、操作说明与验收ID中英同步。历史44项修正不因此重计或变成统一架构验收。

## 1. 执行总账与依赖

| 阶段 | 交付 | 前置 | 验收ID | 当前状态 |
| --- | --- | --- | --- | --- |
| P0 | 基线、兼容矩阵与隔离回退夹具 | 实现授权 | A1／A10准备条件 | completed：本机准备候选 |
| P1 | 工作站结果进入现有编辑／导出完整链路 | P0通过 | A2／A3／A4／A11 | completed：本机互通候选 |
| P2 | 统一持久任务／操作状态与产物发布协议 | P1通过 | A1／A3／A6／A11 | 实现与本机候选验证完成；累计资格待验收 |
| P3 | 单执行核心、队列、取消恢复与两类流程接入 | P2通过 | A5／A6／A7 | 实现与本机候选验证完成；真实直播／GPU资格待验收 |
| P4 | 统一API、创作界面、配置与原生／CLI入口 | P3通过 | A8／A11 | 实现与本机候选验证完成；重启保护资格待验收 |
| P5 | 分批历史迁移、平台实测与回退演练 | P4通过；正式切换需单独授权 | A1—A11 | 迁移／独立恢复本机验证完成；跨平台验收进行中 |
| P6 | 退役重复入口与旧写入核心 | P5全部必需门槛通过；删除范围需明确授权 | A12及累计复核 | planned |

每阶段独立形成可审阅候选；失败即停止晋级，保留证据与上一个可用入口。某阶段单测通过不替代后续真实平台验收。没有真实GPU环境时可以继续获准的隔离开发，但不能激活正式迁移或删除旧核心。

## 2. 文件与接口规划

以下仓库根相对路径描述各阶段目标，不能先创建空模块。P0 已提前实现 `task_import.py` 的只读发现切片，以支持身份／保护测试；P5 prepare／verify／activate 仍未实现。其余现有接入点执行前仍需阅读适用AGENTS并核验调用方。

| 责任 | 既有接入点 | 拟新增最小边界 |
| --- | --- | --- |
| 产物解析与编辑输入 | `backend/app/arctime/subtitle_inputs.py`、`subtitle_document.py`、`subtitle_api.py`、`subtitle_exports.py`；`backend/app/repositories/tasks.py`、`services/subtitles.py` | P1新增 `backend/app/services/task_artifacts.py`，显式解析两种来源到相同编辑输入 |
| 持久状态与发布 | `backend/app/models.py`、`db_migrations.py`、`backend/alembic/versions/`、`arctime/companion_projection.py` | P2新增 `backend/app/services/task_operations.py`；迁移revision按届时Alembic head生成，禁止预猜编号 |
| 调度与执行 | `backend/app/worker.py`、`services/workstation_queue.py`、`workstation_runs.py`、`task_runner.py`、`pipeline_support.py`、`task_control.py`；`arctime/companion_manager.py`、`workflow.py`、`saozi_live.py` | P3共用claim／终态逻辑；拟新增 `backend/app/services/runtime_guard.py`管理同一Supervisor、旧根锁及持久封锁，P4接入各宿主，不新建调度框架 |
| API与前端 | `backend/app/main.py`、`api/routes/`、`arctime/gui.py`、`arctime/*_api.py`；`web/src/companion/`、`workstation/`、`router.tsx`、`vite.config.ts` | P4新增 `backend/app/api/routes/operations.py`及 `api/schemas/operations.py`，新操作采用 `/api/v2/operations`；旧路由过渡期仅适配同一服务 |
| 原生、配置与CLI | `desktop/macos/App.swift`、`arctime/macos.py`、`cli.py`、`companion_llm.py`、`chatgpt_credentials.py`、`subtitle_templates.py`、`backend/app/settings.py`、`scripts/build_macos_app.py` | P4解耦task／settings／credential根；新增 `scripts/unified_recovery.py`及冻结恢复资源，只用于设计7.1的本机恢复，不增加远程连接／凭据同步 |
| 历史导入 | 以上产物／操作服务及原目录锁 | P5新增 `backend/app/services/task_import.py`，仅实现prepare／verify／activate与只读回退清单；不提供隐式启动导入 |

公共输入的字段约束、状态与权威来源以设计第4—6节为准。P1由 `task_artifacts.py`解析可信根内产物，返回原文、译文、词级来源、语种、时长、时间原点、摘要与编辑文档所需上下文；渲染层不读取旧任务清单。P2—P3由 `task_operations.py`负责操作身份、快照、执行权与发布登记；引擎只接收明确输入与回报进度。P5的稳定来源映射不能通过目录名推断归属。

## 3. P0：基线与兼容夹具

**文件：** 已新增 `backend/tests/fixtures/unification/README*.md`、固定契约、`test_unified_import.py`、夹具生成／验证与权限预检测试；提前拆出 `task_import.py` 的只读发现切片。现场兼容矩阵和完整证据在[执行记录](../../unified-architecture-execution-2026-10-22.zh-CN.md)。

- [x] 核验源码／dirty、解释器、pnpm、进程和根计数；工作站1个failed登记任务与5个未登记目录分开记录，后者保留且归属unknown。
- [x] 建立覆盖表与写入根分类，映射所有上述能力／数据类别到后续阶段和A项；区分静态存在、实际运行与已验收。
- [x] 先写并通过只读身份／保护测试：不同实例同旧ID身份不同；同实例同generation发现结果相等；任务文件变化改变generation；坏JSON／缺源单项拒绝；秘密不进入报告。**持久导入映射、重复导入及U6激活后冲突仍按P2／P5原门槛执行，不能据此关闭M01／M02。**
- [x] 构造R0／R1／R2样本并固定媒体／稿件／参考输出摘要；旧原格式读取器只读加载实测通过。新版schema与工作站格式不得直接降级回写；独立恢复启动器仍待P4。
- [x] 保存双语矩阵、发现边界、平台缺口与夹具结果；310项回归通过，仅代表本机准备／既有回归，不代表M项完整通过。

**退出标准：** 每个支持能力和数据类别都映射到后续阶段／验收ID；无未分类写入路径，源夹具摘要不变。**回退：R0**，保留夹具和证据，不触碰正式根。

## 4. P1：完整链路先行

**文件：** 新增 `backend/app/services/task_artifacts.py`、`backend/tests/test_unified_artifacts.py`；修改既有 `subtitle_inputs.py`、`subtitle_document.py`、`subtitle_api.py`、`subtitle_exports.py`、必要的Companion客户端与编辑器接线；新增 `web/e2e/unified-edit-export.spec.ts`。按职责处理调用方，不整文件覆盖平台分支。

- [x] 先写失败用例：真实工作站产物结构不能被Companion清单解析；正向预期是通过显式来源解析进入编辑，缺文件／摘要错误／路径越界／符号链接直接拒绝，不创建伪job.json。
- [x] 实现最小产物上下文，保留绝对时间、片段零点、语种和词级来源；分别覆盖日译中、中译日、无译文及短尾片段。不改变两种ASR内部缓存或模型配置。
- [x] 把编辑文档的构建／源身份校验与旧清单读取分开；现有旧指纹兼容证明继续有效，revision冲突保留客户端草稿。
- [x] 用同一个工作站结果完成加载视频、编辑一条、保存、同一后端重开、PNG预览、ASS、片段烧录；对比两种ASR真实或冻结来源样本，记录样本来源。冻结样本只证明互通，不证明GPU推理。
- [x] 新增浏览器链路使用实际隔离API；不能只用前端mock。按A4固定样式／时间与编码容差，检查4999条未编辑字幕、源媒体和旧导出摘要不变。

**退出标准：A2／A3／A4／A11的隔离互通部分通过**。**回退：R0**，恢复旧入口，保留隔离新稿和导出；不反向覆盖原任务。GPU平台A9仍待P5。

## 5. P2：持久状态与文件发布

**文件：** 修改models、Alembic升级／回填、仓库投影与产物服务；新增 `task_operations.py`、`backend/tests/test_unified_operations.py`、`backend/tests/test_unified_publication.py`；扩展既有schema／字幕冲突测试。

- [ ] 先写状态／映射约束测试：来源与旧ID唯一；操作重试新增attempt；视频成功而翻译失败分别可见；重启不能从旧gui.json恢复为running；旧schema数据库在临时副本升级后旧数据完整。
- [ ] 实现任务／操作／执行token及产物登记的最小增量schema；迁入任务仅由统一库决定调度状态。原TaskStage／StageRun过渡期为旧任务契约，不能给新任务再维持两份可写权威。
- [ ] 按设计5.1持久化每attempt完整必需组及准备收据，再发布各文件，最后单事务提交整组与事件；编辑revision采用不可变正文＋DB CAS。相同导出复用已验证结果；变化生成新结果，不覆盖旧文件。
- [ ] 逐个执行M06／M08／M09故障点，包含每项输出发布后、ready提交前、DB终态前后及ENOSPC；按收据恢复，不接纳旧attempt，不把部分输出标成功。
- [ ] 对外部请求未知结果写明确interrupted及重试提示；正常已验证翻译检查点继续复用，不承诺无法证明的恰好一次计费。
- [ ] 检查升级可重入、失败原副本不损坏、队列未自动启动；保存schema差异、故障点结果和数据摘要。

**退出标准：A1／A3／A6／A11相关测试及升级副本通过**。**回退：R0或R2**；旧版本连接迁移前独立副本，新schema保留，不执行downgrade。

## 6. P3：一个执行核心

**文件：** 修改worker、queue／runs／task_runner／pipeline_support／task_control、Companion manager、录播与直播流程；扩展 `backend/tests/test_unified_operations.py`、新增 `backend/tests/test_unified_execution.py`，复用现有队列／子进程／直播回归。

- [ ] 先写两个执行者竞争同队列、旧token写入、取消后子进程未退出等失败场景；预期只有一个有效claim，旧执行者不能更新状态或发布文件。
- [ ] 共用调度／执行权逻辑；桌面helper和独立worker仅是宿主差异。移除迁入任务绕过调度的ThreadPool路径；旧未迁入任务继续由原入口管理，不能两个调度器共享同一任务。
- [ ] 按四类顶层操作接入既有函数；直播内部翻译／导出作为共享父attempt／token的顺序子步骤，禁止再次入队领取槽。保留录播顺序、人工确认、臊子策略、部分失败及快照，不改成固定七阶段。
- [ ] 3任务验证排序、优先级、暂停／恢复；运行中任务不因队列重排中断。直播占槽时录播等待，停止直播完成尾段并释放进程后才处理下一项。
- [ ] 注入采集中断、ASR中断、翻译失败、导出失败；恢复只处理已录内容与有效检查点。断流缺口保留标记，不拼成虚假连续源时间，不自动重连。
- [ ] 桌面与工作站宿主分别重启并验证同一状态／恢复语义；事件与状态同事务，SSE使用短会话，不把长任务放在HTTP请求生命周期内。

**退出标准：A5／A6／A7通过**。**回退：R0／R1／R2按任务分类**；先停新执行者并核对锁／进程，再切原入口，不重新授予已变更任务的旧执行权。

## 7. P4：统一产品入口

**文件：** 修改FastAPI组装、既有routes与schema；新增operations路由／schema；修改Companion界面与工作站任务库／队列接线、React路由、API客户端、Vite入口；修改原生／CLI启动和配置接线。扩展 `web/e2e/unified-edit-export.spec.ts`、新增 `web/e2e/unified-task-queue.spec.ts`，复用原生退出／设置测试。

- [ ] 先写桌面和浏览器同一任务事实、旧路由兼容、两标签保存冲突、配置草稿隔离、SSE断线与游标恢复测试。
- [ ] `/api/v2/operations`接收四类操作；任务库／队列保留v2语义，编辑／模板接口迁到同一服务。旧 `/companion-api` 与 `/api/tasks`暂作适配，禁止各自执行业务分支；OpenAPI类型经生成器更新。
- [ ] Companion创作界面纳入任务库与可排序队列，复用现有组件；统一查询key和事件刷新，保留轮询兜底，不同时维持两套业务页面。
- [ ] 按设计6.2接线独立task_root／settings_root／credential_root并迁全局包；保留默认优先级、模板与ArcTime绑定、标签／归档／历史。授权引用原受保护位置，无重新登录和秘密复制；M14全部通过才接入激活。
- [ ] 保留桌面动态回环端口、原生文件保存、未保存退出确认和helper清理；CLI经同一任务服务获取锁与执行权，不能成为第三个独立调度器。远程GPU连接界面不在范围内。
- [ ] 实际浏览器与原生窗口验证新建、队列、编辑、设置、保存／退出／同构建重开；窄窗口、键盘焦点、错误提示与长字幕操作保留。更新安装／smoke路径及双语说明，但不安装正式App。

**退出标准：A8／A11通过**。**回退：按R0—R2选择独立根与旧入口**；HTTP适配层可暂留，不回滚新数据为旧schema。

## 8. P5：迁移与平台验收

**文件：** 新增 `backend/app/services/task_import.py`；完善 `backend/tests/test_unified_import.py`及回退夹具；维护独立本机迁移收据与双语验收摘要。收据不得包含秘密，私有路径／原始日志不进入可分享摘要。

- [ ] 先在复制夹具运行prepare／verify／activate，验证重入、同ID不同来源、缺源、坏稿、孤立导出、旧指纹、取消批次、磁盘空间不足及授权不复制；迁移器默认只发现，不启动操作。
- [ ] 读取现有根并生成只读清单；分类正在运行／排队／终止任务，列出引用媒体和所需空间。运行中任务排除；排队任务须明确暂停／撤销旧资格后另行接管。
- [ ] 由同一Supervisor按设计6.1／6.4停旧入口、持锁并验证持久封锁后重算source_generation；变化返回prepared。激活事务绑定全局包、root_group与任务所有权；未迁任务只读，取消当前批次不得解冻其他批次的依赖根。
- [ ] 在macOS做实际whisper.cpp任务并编辑／导出；Linux CUDA、WSL ROCm各做实际WhisperX任务并编辑／导出，记录硬件／引擎／模型／版本和产物。外部AI或真实直播验收仅在获准范围内执行；未获准不冒充已验证。
- [ ] 按M15／M16／M23—M27演练整个根依赖组的正常及坏版本回退，覆盖部分批次取消和仅全局设置变化；全部新版根同epoch封存，旧业务只用独立副本，原生旧App不得直接打开默认根。
- [ ] 获得明确正式迁移／安装授权后，先做一致备份、停止旧写入者并核对任务／进程；以首个小批次切换，队列保持暂停，人工核对通过后才扩大批次。任何摘要／版本／所有权不符立即停止批次并按回退等级处置。

**退出标准：A1—A11全部满足且平台分别有真实证据**。CUDA／ROCm任一缺环境保持blocked／unknown，不能批准P6退役。**回退：严格执行设计第7节**；不得全量覆盖升级后数据或恢复历史清理内容。

## 9. P6：退役重复核心

**文件：** 仅按届时调用图清理旧路由／入口、调度分支、未使用页面；更新Vite、构建／smoke、生成契约、双语指南、AGENTS与交接。不要预先把整个 `arctime/` 或 `workstation/`列为删除目标。

- [ ] 逐个入口记录调用方、旧任务剩余数量、兼容读取依赖、回退版本与最小保留文件；删除边界经明确审阅后执行。
- [ ] 先禁止创建新的旧格式任务；所有受支持启动路径均使用统一服务，再退役旧写入核心。仍需读旧数据的解析器保持只读，不能借兼容名义继续新增旧写入路径。
- [ ] 清理只涉及确认无人调用的源码；保留历史测试的有效行为断言、迁移／失败证据、旧任务、模型、授权、备份与媒体。不因移除旧入口跳过失败测试。
- [ ] 运行累计专项、实际浏览器／原生与必需平台流程，核对全新安装及历史升级；更新中英状态为实际completed／accepted及明确限制。
- [ ] 输出最终映射：“能力→唯一入口→测试／实际产物→回退分类”；无未完成必需项才标统一架构accepted。

**退出标准：A12及累计A1—A11通过**。退役后有新版数据时只允许R2方式保留结果并切独立快照；旧程序不得写新库。正式清理备份或历史媒体不属于本计划。

## 10. 验证命令与证据格式

以下保留**设计评审时的命令示例**；本次实际命令、退出码和范围以[执行记录第 8 节](../../unified-architecture-execution-2026-10-22.zh-CN.md#8-完整候选实现与当前验收账)为准。从仓库根使用已核验的Python3.11后端环境；`.venv`不存在时先在获准隔离目录准备运行环境，不替换全局配置或假称命令已通过。

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_subtitle_document.py backend/tests/test_subtitle_api.py backend/tests/test_subtitle_export_snapshots.py backend/tests/test_subtitle_renderer.py -q
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/workstation/test_queue_service.py backend/tests/workstation/test_terminal_process_boundaries.py backend/tests/test_pipeline_support.py backend/tests/test_saozi_live.py -q
cd web
./node_modules/.bin/vitest run src/companion
./node_modules/.bin/tsc -b
./node_modules/.bin/vite build
```

未来新增的 `test_unified_artifacts.py`、`test_unified_operations.py`、`test_unified_publication.py`、`test_unified_execution.py`、`test_unified_import.py`须在对应阶段实际创建后单独执行；新增e2e必须访问隔离API并声明独立webServer／数据根，不能直接套用mock工作站环境冒充完整链路。

每次证据收据至少包括：阶段／A编号、源码候选身份、实际命令及退出码、夹具／平台／数据根别名、前后摘要与数量、观察结果、失败与未覆盖项、当前所有者及回退等级。只读发现不等于迁移，schema升级不等于运行验收，测试通过不等于目标GPU或正式发布通过。

## 11. 设计评审时的文档交付检查（历史）

- [ ] 中英设计与计划相互链接；A1—A12、P0—P6、R0—R2对应一致。
- [ ] 所有既有源码／测试引用存在；拟新增文件明确标注，不伪装为可运行工具。
- [ ] 每阶段含文件责任、依赖、失败场景、退出条件和回退；无隐含双写、无自动调度旧任务。
- [ ] 本轮应用源码、测试、构建脚本与部署配置未变化；未运行迁移／安装／业务验证。

以上保留设计评审时的检查表，不作为当前源码未变或实现未授权的声明。后续已获完整实现授权，实际交付以执行记录和候选操作指南为准，阶段资格仍须单独匹配证据。

## 12. 七项审阅意见的执行补充

以下字段／工具是拟实现契约，当前不存在可运行的新迁移或回退命令。测试只在后续对应阶段创建；每项包含失败用例、最小改动与退出证据。

<a id="rev-u1"></a>
### U1：P0定义快照，P5停写后复核

- [ ] 在 `backend/tests/test_unified_import.py`先写M03：verified后把旧字幕r改为r+1，原样activate应拒绝；复核后／事务前退出，重开不得出现半激活。
- [ ] `task_import.py`实现设计6.1顺序与稳定锁顺序，source_generation覆盖任务和全局包；激活失败事务回滚，新队列保持暂停。执行后保留实际持锁者、旧进程停机证据、generation差异与唯一映射。
- [ ] M03通过且旧根重启写入被阻止才退出。锁不能阻止工作站旧API时必须撤下旧入口；不得把“已写owner字段”当排他证明。

<a id="rev-u2"></a>
### U2：P2实现可恢复的产物组

- [ ] `test_unified_publication.py`按M08每个组成员故障点及M09注入失败；`test_unified_operations.py`按M06测试revision持久化／CAS中断，先确认旧发布逻辑不能满足断言。
- [ ] `task_operations.py`与产物服务实现不可变准备收据、ready登记、逐文件发布、整组结果事务；收据含publication_id／子步骤／attempt／token及集合摘要。直播片段发布只完成子结果，不能提前完成父操作；模板与编辑稿只登记已持久正文，孤稿只隔离。
- [ ] M06／M08／M09逐点通过；审阅收据与重开后的全组文件／数据库，不仅检查最终退出码。失败不能通过重跑模型或AI掩盖。

<a id="rev-u3"></a>
### U3：P4交付恢复入口，P5验证坏版本场景

- [ ] 新增拟定 `scripts/unified_recovery.py`、`backend/tests/test_unified_recovery.py`；扩展macOS构建测试以验证恢复资源独立封存。测试先禁止导入候选app包／启动候选二进制，要求旧界面仍能启动且新已保存稿可读。
- [ ] 未来工具接口固定为 `--manifest PATH --mode legacy-browser|read-only --output-root PATH`；清单按设计7.3限定全部根／epoch、helper、运行环境和schema，拒绝输出到任何来源／快照根或hash不匹配。legacy-browser仅用独立旧工作副本；read-only读取同epoch多根快照并输出任务／设置／模板／登记清单；不是当前命令。
- [ ] Launcher作为旧helper的存活parent，使用动态回环端口和独立ready／log；冻结读取器／渲染依赖资源与环境，禁止从候选目录加载。旧工作副本排除授权／配置秘密，仅本地编辑恢复，不倒退恢复授权。候选无法启动时按设计7.1取得一致SQLite／WAL快照，不依赖候选flush或导出。
- [ ] M15／M16通过并记录旧helper／恢复工具hash、根角色和最后登记revision；不把浏览器未落盘输入列为崩溃后保留承诺。该恢复包是P5正式激活的硬前置。

<a id="rev-u4"></a>
### U4：P0盘点全局包，P4接线，P5绑定generation

- [ ] P0输出设计6.2逐字段保留表；P4在 `backend/tests/test_unified_import.py`和既有配置／模板测试中先验证切task_root时授权状态、默认值和工程绑定不会丢失；实际凭据不用于测试。
- [ ] 修改LLMConfig／CredentialStore／TemplateStore接线并引入显式根角色；新设置中只存公开默认值和授权引用，读取原私有配置中的秘密不改变它的字节，沿用原锁／权限。模板冲突按来源实例映射，绑定必须可解析。
- [ ] M14字段、数量／摘要、零网络断言全通过；全局包generation不符即禁止依赖任务激活。全局新写入按整个回退组计R2，授权刷新／撤销不能被回退恢复。

<a id="rev-u5"></a>
### U5：P3明确父操作持槽

- [ ] `test_unified_execution.py`先写M11：父直播未完成时已有首片双语／样式结果；计数器验证子步骤claim=0、外排顶层claim须等父释放。
- [ ] live流程内子步骤顺序调用现有函数，记录parent_operation_id／块／片及部分失败，不经顶层提交接口。停止收尾失败时保存失败结果并释放进程，不能等队列中的子操作再结束父操作。
- [ ] M11／M12通过，证据包含首片早于父终态、翻译失败后采集继续及恢复零重连；实际直播M19仍须P5另验。

<a id="rev-u6"></a>
### U6：P0登记实例，P2约束映射，P5处理冲突

- [ ] `test_unified_import.py`先写M01／M02的确定计数与冲突结果；加入同根改名、克隆作恢复与克隆作独立分支三个来源登记场景。
- [ ] 在隔离迁移登记册保存source_instance_id，不写原任务根、不把路径／类型作为身份；DB唯一约束使用 `(source_instance_id, legacy_id)`，source_generation单独判断内容是否变化。
- [ ] 不同实例同ID均导入；同实例相同内容零重复；激活后内容变化明确conflict，原统一稿不变。中英行为与M01／M02完全一致才退出。

<a id="rev-u7"></a>
### U7：每阶段按矩阵出证据

- [ ] P0冻结F-media／F-edit／F-live／F-state和V清单，确认M17／M18使用的F-media含可识别固定语音；缺真实GPU、直播源或支持编码器记blocked，不能拿替身补通过。
- [ ] P1执行M04／M05／M07／M20／M28；P2执行M02／M05／M06／M08／M09／M20／M26；P3执行M10／M11／M12及guard核心探针；P4执行M13／M14／M15／M16／M20／M24／M25／M27；P5累计全部M项但不含P6的M21；P6执行M21并复核全部保留能力门槛。
- [ ] M07只判无损参考（边界≤1px、RGB RMSE≤3.0）；M28通过真实API取得libx264 CRF20产品（边界≤2px、RGB RMSE≤8.0），两者均固定ROI和0—255刻度。实际视频时间边界≤1输出帧，SRT／ASS量化≤1ms／10ms，保存原始测值和HTTP产物身份，不只写“视觉一致”。
- [ ] A验收记录引用对应M收据，分清冻结逻辑、实际GPU、真实采集与供应商；任何必需M项unknown／blocked阻止退役。新增 `test_unified_recovery.py`与恢复包隔离运行测试纳入P4／P5门槛。

## 13. 五项残余问题的执行补充

本节保留新增模块／测试／入口的设计约束；实际状态以执行记录为准，文档修改本身不构成执行或验收。Rv 测试与 U 测试共同适用。

<a id="rev-rv1"></a>
### Rv1：P2登记依赖组，P5整组回退

- [ ] `test_unified_import.py`新增M23：A激活并编辑、B取消，再请求解冻必须拒绝；另测全组R0、无新版写入的全组R1、未知外部引用。逐字段断言A稿、映射和封锁未变化。
- [ ] `task_import.py`／`task_operations.py`持久化root_group_id与批次／任务／全局包／媒体引用边；在组锁与事务内按最严格R级分类。取消批次只撤销其准备资格，解冻收据须列出全部已撤销资格与零剩余依赖，方可通知guard恢复权限。
- [ ] M23和R0／R1／R2整组演练通过才可扩大正式批次；存在R2成员时只能用独立旧快照，不能解冻原根。

<a id="rev-rv2"></a>
### Rv2：P0固定保护profile，P3／P4同一Supervisor

- [ ] P0在各目标平台验证旧根／锁／DB只读保护与credential_root例外可同时成立，封存原ACL／权限及探针步骤；缺权限、文件系统能力或根布局不满足则blocked，不能用标记文件替代。
- [ ] 拟新增 `backend/app/services/runtime_guard.py`、`backend/tests/test_unified_runtime_guard.py`；修改macOS helper、worker及启动脚本接线，使同一Supervisor从复核前持续持锁到依赖组结束，不在激活后启动另一个独立持锁宿主。
- [ ] 按设计6.4实现preparing／sealed记录、持久OS封锁、只读描述符重获锁及启动前实际探测；子进程死亡不释放监督锁，监督进程死亡不自动撤销OS保护。旧入口、旧锁inode或权限变化使重启blocked。
- [ ] M24逐中断点尝试实际旧GUI／CLI／DB写入并验证拒绝；在获准隔离平台受控重启，验证保护先于旧入口；无授权则blocked，不擅自重启宿主机。同时验证凭据夹具仍可用、不进恢复包。封锁失败零activated，未经7.2收据不得恢复权限。

<a id="rev-rv3"></a>
### Rv3：P4实现多根恢复，P5禁候选演练

- [ ] `test_unified_recovery.py`增加M25／M27：只有新模板／默认值／工程绑定变化，没有新任务；禁候选启动，离线恢复仍列出最新字段。删任一根、改generation、复制中退出或ENOSPC必须拒绝complete且原集合不变。
- [ ] Recovery Launcher／只读读取器按设计7.3枚举DB、task、settings、global_package、registry、guard和媒体引用；同一停写屏障取得全组锁，生成recovery_epoch，使用一致DB副本并逐根核对前后摘要。credential_root仅作受保护引用，不复制秘密。
- [ ] 读取器导出任务稿以及原生模板／默认JSON、ArcTime工程与可读绑定清单、全局generation和来源登记摘要，不回写旧版；原始私有guard记录只留本机。M25／M27及坏版本M16均通过才允许正式激活。

<a id="rev-rv4"></a>
### Rv4：P2使用唯一J判定

- [ ] `test_unified_publication.py`参数化枚举D／E／P／T／F的144个逻辑组合，验证每项恰好匹配一个J00—J14条件；非法schema另测blocked。对实际可达的每个J动作再运行真实临时DB／文件故障验证，枚举逻辑不能代替故障执行。
- [ ] 恢复器先排他停止原进程，再核对当前或历史执行证明；未提交组不先运行旧stale-job撤销逻辑。允许原attempt的文件对账，不允许恢复器调用模型／AI；取消或新attempt生效后旧组不能接纳。
- [ ] M08／M09／M26保存J编号、DB快照、receipt_digest、attempt／token及发布集合；心跳过期、取消、历史C组和部分文件分别有确定动作，不能按“无ready就隔离”覆盖所有分支。

<a id="rev-rv5"></a>
### Rv5：P0封存预期，P1／P5走真实导出入口

- [ ] P0封存M07／M28共用文档、输入帧、字体／工具版本、色彩转换、采样帧号和固定ROI；产品参数为现有libx264 fast CRF20／AAC／MP4，不新增FFV1产品选项。
- [ ] `web/e2e/unified-edit-export.spec.ts`通过真实隔离API保存文档、提交kind=burn并下载返回产物；用实际MP4计算M28时序／边界／ROI指标，保存operation／artifact ID、HTTP和真实FFmpeg argv。禁止用参考命令／测试桩代替产品调用。
- [ ] M07参考与M28产品分别判定并记录原始测值；产品超过≤1帧／≤2px／RMSE≤8.0即失败，不在看结果后调整阈值或ROI。P5在真实平台重复M28，M22编码器fallback不能替代字幕烧录证据。
