# 统一架构执行记录

日期：2026-10-22，Asia/Shanghai。对应[设计](superpowers/specs/2026-10-22-unified-architecture-design.zh-CN.md)、[实施计划](superpowers/plans/2026-10-22-unified-architecture.zh-CN.md)及[英文记录](unified-architecture-execution-2026-10-22.md)。

**P0—P4 的统一运行时候选及 P5 迁移／独立恢复实现已完成本机验证；P5 跨平台与生产资格仍待验收，P6 未执行，完整统一架构尚未 accepted。** 第 1—7 节保留各时点观察，第 8 节及[候选操作指南](unified-runtime-guide.zh-CN.md)为当前状态；没有正式接管或替换安装。

## 1. 隔离与现场基线

- 独立工作树：`unified-architecture/nyaru-clipper`；分支 `codex/unified-architecture-2026-10-22`，基于 `428ba833193db888c6b049ac2983abe1b2ecae17`。没有提交、推送或合并。
- 原工作区的既有未提交文档、索引、输出及其他工作树保留；四份已审阅中英设计／计划复制至候选工作树，执行状态另行记录。
- macOS 27.0.1 / arm64；Python 3.11.16，pytest 8.4.2；按 `uv.lock` 创建独立 `backend/.venv`，没有下载模型。
- 默认 PATH 的 pnpm 为 11.25.0；已验证本机缓存中的 **10.33.2** 可用。未更改全局版本，未运行前端构建／浏览器／原生验收。
- 产品字幕路径实际选择 FFmpeg **7.1.5**（含 libass）；PATH 上的 FFmpeg 9.0.1 不是本夹具渲染器。
- 仅按进程名检查，未发现 Nyaru／uvicorn／worker 运行进程；这不构成未来接管时的进程退出证明。
- 正式根只做计数和 SQLite 只读查询：Companion 12 位任务目录 **0**；工作站登记任务 **1，failed**，对应目录 1；另有 **5 个未登记目录**。未登记目录内容及归属 unknown，保留并等待 P5 清单核对；未把它们当成可清理缓存。来源实例登记尚未验证。

## 2. 本批实现

| 文件 | 实际作用 |
| --- | --- |
| `backend/app/services/task_import.py` | P5 导入器提前拆出的 P0 **只读发现**：外部实例 UUID＋旧 ID、任务文件 generation、主／次级登记产物校验、次级写入状态、单任务拒绝及固定错误码；报告不回显路径、URL、秘密或原异常 |
| `backend/tests/test_unified_import.py` | 31 个发现身份／保护测试；目录改名、同 generation 重入、所有任务文件变化、坏 JSON、缺文件、坏摘要、越界、符号链接、处理中翻译／导出、读取期间变化、秘密诱饵及次级登记文件缺失 |
| `backend/tests/unification_fixtures.py` | 两个实例、重复旧 ID、失败／排队／缺源／孤立文件、实际模板／默认值／工程格式、假授权与 R0／R1／R2 样本；两种冻结字幕格式及词级数据 |
| `backend/tests/unification_media.py` | 可重建的语音媒体、准确时长闭合块、ASS／SRT／PNG／FFV1 参考、固定 RGB 帧及最后写入的摘要 manifest |
| `backend/tests/test_unified_fixtures.py` | 5 个契约与夹具测试，包括 5000 cue、已有输出拒绝、真实模板绑定、两个翻译方向与词级来源 |
| `backend/tests/test_unified_media_fixture.py` | 实际媒体帧数／时长、8 块准确时长、R0／R1／R2 原读取器只读加载、参考帧在固定 ROI 内按边界显隐 |
| `backend/tests/test_unified_platform_preflight.py` | 普通用户临时根上的真实权限探针：拒绝写入／新建／删除／重命名／旧式读写锁打开；杀死持锁进程后只读描述符可重新独占加锁 |

只读发现未接入产品启动、API 或 CLI；不创建锁、不写映射、不改变任务所有权、不启动任务、不授予接管资格。`task_generation` 仅覆盖任务文件，不能当成绑定全局包并在 Supervisor 下复核的 `source_generation`。不同实例重复 ID 的**发现身份**已验证；持久映射幂等及 activated 后冲突处理仍由 P2／P5 完成。

## 3. 兼容覆盖与写入边界

| 能力／数据类别 | P0 证据 | 后续阶段／验收 |
| --- | --- | --- |
| Companion 范围、高光、臊子与直播 | 现有实现静态存在；工作流回归通过；闭合直播块已准备 | P1/P3/P5；A2/A5/A7/A9 |
| WhisperX／whisper.cpp；中译日／日译中 | 两种冻结格式、语种／词级数据；本机两段真实 whisper.cpp 识别 | P1/P5；A2/A9；冻结样本不能认证 GPU |
| 模型缺失、未配置授权 | 现有恢复边界保留；假授权不进入收据 | P3/P4/P5；A6/A11；真实供应商未调用 |
| 引用／复制源、缺源、孤立文件 | 缺源单任务拒绝；孤立文件进入任务 generation；正式未登记目录仅计数 | P1/P5；A1/A11；引用模式仍须实际接入 |
| 旧稿、来源证明、局部样式、5000 cue | R2 revision 1 含 5000 cue；原读取器能读且任务文件摘要不变 | P1/P2；A3；双客户端保存待测 |
| PNG／ASS／烧录／ArcTime | 固定参考与真实模板／工程绑定；未增加 FFV1 产品选项 | P1/P5；A4/A9；产品 burn/下载与 RMSE 待测 |
| 失败／中断／排队与取消 | 发现分类及现有队列回归；不撤销旧资格 | P2/P3/P5；A1/A5/A6 |
| 主数据库、事件、队列、操作状态 | 原有工作站回归通过；未更改 schema | P2/P3/P4；A1/A5/A6/A8 |
| 默认值、模板、工程、标签／归档／历史 | 实际格式与字段夹具；标签／归档为明确合成元数据 | P4/P5；A1/A11；全局包迁移未实现 |
| 授权、模型与工具 | 原位置／原模型不迁移；假授权单独根、0600；只记录模型／字体摘要 | P4/P5；A9/A11；不恢复撤销 token |
| 正常回退、坏新版、多根恢复与跨批次 | R0/R1/R2 原读取器样本＋本机权限探针；未创建恢复启动器 | P2—P5；A1/A6/A10；M15/M16/M23—M27 未通过 |
| 原生退出、浏览器、LAN、CLI、旧核心退役 | 现有边界保留；本批没有更换入口 | P4—P6；A8/A11/A12 |

写入位置已按角色分类：Companion 任务根承载 job/gui、源／切片、ASR 缓存、录制块／closed.csv／直播检查点、翻译、字幕稿／证明、样式结果／收据／日志；工作站数据库承载任务／队列／运行／事件，任务目录的 raw/work/exports/reports/logs 保持现有职责；设置根承载模板／默认／工程，授权根承载 config/.chatgpt，模型／工具及原生 ready 临时文件分别管理。未来 registry／guard／global package 目前只有夹具，不能误称正式运行状态。正式授权根与任务根是否同一保护域仍须 P4 预检，权限探针不能替代该判断。

## 4. 固定证据与测试

私有夹具包别名：`~/.cache/nyaru-clipper/unified-p0-20261022-bilingual-i6mmfdv5/fixture/`。不提交该包、字体、声音、模型、假授权正文或原始日志。

- manifest：`0c4177d7a55825c6cc400ffe93ae5b7d732fceec13f39748fb592a8d032b86fd`。
- contract：`9f86c6878fd5149464d8542c6f877df5755cd283c761e7f1110f67fe9ef31991`。
- **150 个文件**摘要全部复核相等；假授权不进入文件清单。Arial 摘要为 `525979822591a3447cfc49d943d6f7683508e25543407871c0ed8fed05fd2bd9`。
- F-media 为 4501 帧、30fps、1280×720；F-live 实测为 7×20s＋7s。最初 AAC 复制出现约 16ms 漂移，生成器已改为重编码音频；没有放宽时长断言。
- 已实际观察参考帧 60 的文字处于固定 ROI；自动检查 29／90 帧无字幕，30／31／60／88／89 帧有字幕，ROI 外没有该文字差异。没有测产品 MP4 的 RMSE／外接边界，M07/M28 保持未通过。
- 使用既有 whisper.cpp／GGML-small 实际识别两段 AIFF；输出与中日脚本语义一致，日语有标点与汉字写法差异。模型摘要：`1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b`。新包两条音轨与被识别音轨摘要一致。只证明夹具有可识别语音，不代表整片／编辑／导出通过 M17。
- 最终回归 **310 passed / 0 failed / 0 skipped，16.29s**：272 个原有基线测试及 38 个新增检查。JUnit 在夹具包同级 `p0-regression-final.xml`。
- 7 个新增 Python 文件的 no-excuse 规则检查通过。basedpyright/ruff 未安装，未声称静态类型／lint 全通过，也未安装已被用户拒绝的 LSP。

最终回归从 `backend/` 执行：

```bash
.venv/bin/python -m pytest -q tests/test_unified_import.py tests/test_unified_fixtures.py tests/test_unified_media_fixture.py tests/test_unified_platform_preflight.py tests/test_arctime_workflow.py tests/test_subtitle_identity.py tests/test_subtitle_identity_proof.py tests/test_subtitle_document.py tests/test_subtitle_api.py tests/workstation
```

## 5. P0 检查点时的阶段状态

P0 本机准备候选 completed。M01/M02/M03/M14/M15/M16/M23/M24/M25/M27 只有部分夹具／预检；其余 M 项仍 planned，全部 M 项均未完整 accepted。Linux CUDA、WSL ROCm、Windows AMF 无本次实测环境；实际录制、真实外部 AI、系统重启、正式迁移、App 替换安装、旧核心删除均未执行。

下一阶段 P1：先写真实工作站布局不能进入旧编辑输入的失败测试，实现明确来源上下文，再打通同一隔离 API 的加载／单条编辑／保存／重开／PNG／ASS／实际 burn 下载，按固定容差验证。不得伪造 job.json、让旧程序打开新 schema 或把冻结格式称为真实 GPU 通过。

本批回退为 R0：保留原产品入口；新模块没有产品调用方，不需还原数据库或业务文件。保留此工作树与夹具供后续验证，不自动删除未登记目录或旧证据。P5 正式切换与 P6 删除继续遵守原计划的独立授权条件。

## 6. P1 已观察互通结果

- 显式登记的工作站产物已进入现有 Companion 编辑器，不伪造 job.json。上下文核验摘要、符号链接祖先、配置内的外部引用媒体根、原始词级信息、两个翻译方向、无译文与短尾片段。冻结布局证明互通，不代表 GPU 推理。
- 实际隔离 API 与 Chrome 完成 5000 条字幕加载、单条编辑／保存／重开；其余 4999 条及样式不变，双语下载正确使用 zh-ja。真实第二标签页的过期自动保存返回 HTTP 409，客户端草稿保留。最终浏览器场景 12.8 秒通过，已查看整页截图。使用缓存 pnpm 10.33.2 安装既有锁定依赖；82 项针对性前端断言及 TypeScript／Vite 构建通过。
- 实际产品 API 生成 PNG、ASS 与 libx264 fast CRF20／AAC／+faststart MP4。下载后的 MP4 可完整解码，时长 5 秒误差不超过一帧，音视频起点误差不超过一帧；源与旧产物摘要不变。重复请求复用同一产物，仅调用一次编码器。
- 固定帧 29／30／31／60／88／89／90 比较：最大 RGB RMSE **0.356518**，最大字形包围框误差 **1 px**，沿用 8 与 2 px 的既定上限。产品 SHA256 为 `15fb189078de3abdc05c7f2209fe01a7929c3206f5127876415016c9fcb058c1`，产物 ID `40133c762a8767e64f4b`。私有证据保存在 `~/.cache/nyaru-clipper/unified-p1-product-20261022-final/` 及相邻 JUnit XML；保留的产品实测 7.05 秒通过。
- P1 本机退出覆盖 A2／A3／A4／A11 的隔离互通部分及 M28 本机产品导出路径；Linux／WSL GPU、原生窗口生命周期及 P5 累计验收仍未完成。回退仍为 R0，新稿／导出单独保留。

## 7. P2／P3／P4 持续实现

以下为已观察的部件检查，不是阶段验收或完整宿主接通：

- 增量 revision `20261022_01` 新增来源绑定、初始暂停的运行状态、操作／attempt／进程组／子步骤／发布与文档索引。downgrade 拒绝丢弃统一历史。既有 schema／回填回归已在临时数据库通过。
- 整组收据先 fsync 再 ready，最终文件与 staging 独立且不可覆盖，整组／事件最后单事务提交。六个崩溃边界、坏／缺收据、staging／产物损坏、取消、旧历史、staging 独立性、磁盘满注入与重复登记检查通过。**144 种 D／E／P／T／F 输入**均只命中 J00—J14 中一条规则；首个子产物提交不会把仍运行的直播父操作变成成功。
- 不可变文档正文＋DB CAS 已通过保存／重开／冲突／孤立正文检查，并接入 activated 绑定的原编辑 API。旧读取器保持独立，gui.json 不能恢复操作 token。
- 统一执行器已验证两个数据库竞争同一主机执行槽、父操作持有槽时发布子产物，以及真实子进程组取消后才认领下一任务。worker、桌面处理／导出与 CLI 已接入主机槽；原 GUI／翻译／CLI／ASR／导出／直播／队列回归按针对性组通过。四类操作的引擎／宿主派发及前端队列仍在接入。
- macOS Supervisor 真实杀进程测试通过：SIGKILL 后，immutable 标志和只读权限仍拒绝旧文件编辑、新建任务与根目录替换；重启可通过只读描述符重取原锁 inode。依赖释放检查为 false 时拒绝解封；测试显式解封可还原原权限，独立假授权正文不变。这不是系统重启或实际旧 App 的 M24 验收。Linux／WSL 需要已验证的只读挂载配置，仅目录权限不能满足保护门槛。
- `/api/v2/operations` 已用真实临时数据库 HTTP 验证初始暂停、修订号排序、过期冲突与取消，公开投影不含 token／配置快照。前端契约生成、完整配置快照、宿主派发、迁移事务和独立恢复仍待完成。

以上为当时的 **in_progress** 检查点，当前状态见下一节。部件检查不推导真实外部 AI／录制、GPU 平台或重启通过。

## 8. 完整候选实现与当前验收账

用户后续授权执行完整方案 B，并提供 native Linux ROCm 的干净工作站及自由下载授权。实现保留桌面和 GPU 工作站能力；生产切换、覆盖安装、合并／推送及旧核心删除均未执行。

### 8.1 已实现的运行边界

| 范围 | 实现与可检查入口 |
| --- | --- |
| SQLite 唯一事实 | `models_unified.py`、`models_migration.py` 与增量 revision `20261022_01`；显式初始化和 reopen，缺 DB／表／未知 schema 不自动修补 |
| 四类操作 | `unified_cli.py`、`unified_host.py`、`unified_dispatch.py`；统一排队、优先级／排序、暂停、取消、重试、attempt／token／进程组，旧入口共用主机重任务锁 |
| 两引擎与直播 | CPP 真实本机推理；WhisperX 固定配置／模型摘要、300 秒分块和短尾；直播父操作持槽，原文与部分双语／样式产物提前发布，子失败持久化，未知计费结果显式确认 |
| 文档与产物 | 不可变正文＋DB CAS，版本历史、孤稿不接纳；整组收据、逐成员不可覆盖发布、最终单事务；实际产品 ASS／PNG／烧录 MP4 与原件摘要验证 |
| 共用界面／设置 | 真实任务库分页／筛选／标签／归档和元数据 CAS，草稿跨筛选保留；真实队列与生成契约；完整公开配置冻结、模板／工程正文快照；凭据独立引用 |
| 接管 | `migration_*`、`source_seal.py`：外部 UUID、完整根登记／generation、prepare／verify／activate；同一 Supervisor 持续持锁、封锁旧根、复核、事务接管；源变化／事务失败无部分生效 |
| 整组回退 | sticky R2 覆盖任务和全局写入；B 取消不能解冻 A；R0／R1 先提交全组撤销与权限凭据，再恢复旧根；已 thaw 的来源再次登记进入新组，历史版本保留 |
| 新版无法启动 | `build_unified_recovery.py` 冻结独立 Python／依赖／格式／guard／helper／媒体工具；无候选 import、网络或模型调用即可多根 snapshot、read-only、thaw；旧 helper 只写旧格式独立工作副本 |

### 8.2 可复核证据

- 后端最终全量：**1512 passed，17 项既有 JUnit record_property 警告，231.20 秒**；证据 `~/.cache/nyaru-clipper/unified-backend-20261022-r5.xml`。按后端 cwd、`PATH="$PWD/.venv/bin:$PATH" TMPDIR=/tmp` 执行；之前缺少该环境时的临时路径／子进程解释器失败不算干净结果。
- 清理新模块未使用导入后，统一架构针对性回归 **153 passed，77.31 秒**，证据 `unified-focused-20261022-final.xml`；后续新增断句资产检查已纳入最终全量。新 Python 文件规范检查 **115 个文件零违规**。LSP 未安装，未声称完成 LSP 诊断。
- 前端最终完整 **332 passed / 40 文件，12.40 秒**；TypeScript／Vite 构建通过；生成的 OpenAPI 与重导出文件逐字节相同。SSE 轮询补齐后的相关 7 项传输测试及完整前端均通过，浏览器真实断线验证单独记录。
- Chrome r5 真实场景通过：键盘／触屏排序、过期队列 409、两端元数据 CAS 和保留草稿、暂停／重开、两份真实 ASS 导出和点击下载；八份桌面／手机明暗截图已逐张查看，两位独立 UI 检查均 PASS（仅此范围）。r6 扩展测试发现测试等待竞态和离线模拟不关闭已有流，失败证据保留；r7 等待实际确认并由夹具关闭真实 SSE 传输，**2 passed，54.3 秒**，覆盖五次连接失败后的任务库轮询、恢复 SSE 更新、游标重连与后续修改。证据位于 `unified-queue-20261022-1_md6l57/browser-r7/`。
- 原生候选 `unified-native-build-20261022-02/Nyaru Clipper.app` 实际加载同一 SQLite：150.033333 秒媒体经 CPP 生成 6 条字幕、0—30 秒片段及烧录结果；已保存稿 revision 1 保留。正常退出的主进程／helper 均结束；同构建显式重开由端口 59313 改为 59678，仍选中较早任务 `8cb8f1980a815e9696728c36545ebfd6`、保留字幕“原生候选验收：今日は、いい天気です。”及暂停状态。另一个坏媒体测试任务按预期保留失败；不是模型结果。
- 首次原生退出发现 Uvicorn 等待 SSE 的死锁，修复后真实 HTTP 流 SIGTERM 检查通过且无 CancelledError。自动化在旧候选退出后曾误拉起默认兼容入口，立即结束；该时段检查只发现新增 `startup-*.json`，未发现业务文件改写，保留启动记录。没有替换已安装 App，不能把这次观察写成“正式根完全零写入”。
- 独立 thaw 的 **7 种组合**覆盖 R0／R1／R2、封锁快照前后及部分旧权限恢复失败。失败后 group=`withdrawing`、activated 绑定清零、新 DB 再封锁；以原 `controls-resealed.json`、新完整快照和新输出目录离线续跑成功。导出的真实操作配方还走完全部 6 根／3 锁快照与冻结入口 thaw。
- 最终 `unified-native-build-20261022-05` 的冻结 CLI 显式初始化新根、实际原生启动和正常退出通过，签名与固定恢复包验证通过；该包 SHA `ae41b563b591a0fa89072ea9d2b616eafd452ce4a64852bbf6166ff3038f4888`。真实处理样本另在 build-04 的固定恢复包下完成独立 6 根快照和只读导出，`complete=true`、revision 1／6 cue／4 个登记发布全等；不能用较新的 reader 替换这个已固定包。build-04 bundle SHA `1fbeb3c8f87145d1c78e1d41b4ac5670d24fbc8f9b6f22038389eab69fbe7731`，快照 SHA `8859a044a485b6dec4476c2809b96c1ffda7cc77af16459844aa8b5092ab18a7`，恢复核验 SHA `e74d5f452b633034f4c126228e6e9e65441f3372ecf108ecaa1ef0fe2ba54b2a`。
- 真实 OS immutable 下的源 generation 变化、写入 DB 事务中断、错误 group 3 项均保留 verified batch／prepared binding，零 document/global head 暴露，旧写入被拒；外部 media 显式登记测试不依赖当前主机 catalog，归一化产物来自登记媒体，原数据库字节不变。

### 8.3 M01—M28 状态与边界

`local_passed` 是相应本机证据通过；`partial` 是仅实现或限定场景；`blocked` 是缺目标环境／真实来源／另行授权。它们都不等于整项跨平台 accepted。

| 验收 | 当前状态 | 证据或剩余门槛 |
| --- | --- | --- |
| M01 | local_passed | 来源身份、重复导入、缺件／坏摘要、零重复与原件哈希测试；正式清单未接管 |
| M02 | local_passed | 未激活变化生成新候选；已激活冲突、新稿保留；thaw 后同 UUID 新组 |
| M03 | local_passed | 10 月 23 日补齐 8 个真实 SIGKILL 边界、旧稿 r1→r2 后重新验证及唯一激活、实际 guarded HTTP 接管／重开；平台重启保护仍见 M24／第 9 节 |
| M04 | local_passed | 两种冻结 ASR 格式、双向翻译与词级哈希；真实 WhisperX GPU 另见 M18 |
| M05 | local_passed | 真实 5000 cue 双客户端保存、409 草稿及其余 4999 条全等 |
| M06 | local_passed | 文档正文／CAS 故障与孤稿不接纳、版本历史 |
| M07 | local_passed | 固定无损参考与预设 ROI／阈值；不替代产品烧录 |
| M08 | local_passed | 六个发布故障边界及 reopen 对账，父操作不因首片假成功 |
| M09 | local_passed | 实际文件 ENOSPC 注入、DB 提交前后失败、旧 attempt、缺／坏文件 |
| M10 | local_passed | 两执行者真实子进程组、单槽／取消、浏览器排序与优先级／暂停 |
| M11 | local_passed | 父操作持槽与运行时读取部分视频／双语文件；模型／AI 使用受控替身 |
| M12 | partial | 120＋27 秒受控分块、停止／断流、翻译／样式失败保留原文；真实采集见 M19 |
| M13 | local_passed | 原生实际退出／重开和选择、保存稿；r7 真实浏览器 fallback 与游标重连通过 |
| M14 | local_passed | 完整公开设置、模板／默认／工程、独立 credentials 诱饵原字节保持 |
| M15 | local_passed | 独立旧 helper 实际 HTTP 改稿与重开、只写工作副本、禁止在线接口 |
| M16 | local_passed | 冻结入口 -I -S -B，审计禁止候选 import／网络／子进程的读取与 thaw |
| M17 | local_passed | macOS 实际 small 模型、原生编辑／烧录／重开；不是语义质量全验收 |
| M18 | blocked | 缺 Linux CUDA／WSL ROCm；native Linux ROCm 补充实机链路已通过，不能替代目标平台 |
| M19 | blocked | 无受控真实直播来源／完整首片与短尾实录证据 |
| M20 | local_passed | 路径／符号链接／Origin／Host／体积限制、公开投影秘密诱饵拒绝 |
| M21 | blocked | P6 前提未满足，保留旧入口与兼容读取 |
| M22 | partial | CPU 真实烧录通过；windows-amf 目标路径及硬件失败资格未执行 |
| M23 | local_passed | 实际同根 A 编辑＋B 取消仍 R2，旧写入拒绝；全组 R0／R1 与续跑通过 |
| M24 | partial | 10 月 23 日补齐旧 GUI／CLI／DB 拒写、guarded 宿主强杀／重开、独立 thaw 关键强杀边界续跑；受控 OS 重启及其他平台保护 profile 未验收，有限边界不等于任意时刻崩溃证明 |
| M25 | local_passed | 只改全局设置、多根同 epoch、完整历史与 registry、缺根拒绝 |
| M26 | local_passed | 144 合法组合唯一 J00—J14；非法／缺／坏收据及历史 attempt 拒绝 |
| M27 | local_passed | 多根复制／封锁中断、ENOSPC 和 generation 变化不签 complete，原权限日志续跑 |
| M28 | local_passed | 真实 API 下载 MP4，既定参数、最大 RMSE 0.356518／bbox 1 px，原件摘要不变 |

### 8.4 工作站下载与平台资格

native Linux ROCm 的隔离环境为 Rocky 9.8／ROCm 7.2.4／RX 7900 GRE，uv／Python 3.11.16。固定 CTranslate2 4.8.1 及完整 gitlink 来自提交 `0d8bcd362ac75ef860ef161d6f0efad0ae439ff0`，实际编译与 float16 GPU 能力检查通过。Rocky 默认 lib64 问题已用 `-DCMAKE_INSTALL_LIBDIR=lib` 修复并加入 dry-run 回归。AMD 官方 torch／triton 固定 wheel 通过直连分段下载、完整 ZIP CRC 和摘要校验后本地安装；其余依赖沿用原平台清单，`uv pip check` 的 132 个包全部兼容。

真实 API 已完成：150.033333 秒固定语音媒体 → WhisperX small 的 GPU 识别／日语对齐 → 保存 revision 1 → PNG 预览 → 30 秒产品烧录／下载／完整解码。模型元数据明确 `device=cuda`、`compute_type=float16`，requested 与实际一致，没有 CPU fallback。一个识别 cue 的语义质量不由这次链路验收背书。任务 `8333059829bd563b9094d3065a87355c` 的处理操作 `5eb991661cc34db897bc16a2b49764e3` 为 attempt 2，导出 `691950408978455d93c22d80ed727c61` 为 attempt 1；首次缺 `punkt_tab` 的 attempt 保留，补齐后对同一任务重试。

浏览器实际打开同一编辑器，显示保存的第 1 版及正文，并点击下载烧录结果；浏览器下载与 API 下载的 SHA 均为 `a88627da42b28bad83af40a2d2c1e16330d4fc8458e0e4f3cbb3d3f7777a5866`。服务重启的端口 54107→56439，暂停队列、两个操作的 ID／attempt、保存稿与产物摘要全等，零重新识别／编码。证据副本 `~/.cache/nyaru-clipper/unified-gpu-result-20261022-r4/`，服务器另保留各次失败日志、receipt 和 `gpu-reopen-receipt.json`。临时服务在验收后停止，模型与资格数据保留。

资格环境单独固定 `FONTCONFIG_FILE` 和 Noto CJK 字体；默认模板所用字体有记录的替代，因此不能将它冒充 macOS V 的同字体／同 FFmpeg RMSE 验收。离线资格进程仅清除继承的代理变量，未改系统代理；保留 SOCKS 代理的 HTTPX 扩展兼容性未验收。`NLTK_DATA` 指向显式下载的 `punkt_tab`；能力检查现会提前显示该项缺失，不再显示完整缓存已就绪。`yt-dlp==2026.8.19` 已作为共用入口的安装依赖进入 pyproject／uv.lock／生成的 base requirements，所有原有 GPU 依赖 pin 保持不变，requirements `--check` 与 40 项相关测试通过。

已下载并在两端核对：faster-whisper small revision `536b0662742c02347bc0e980a01041f333bce120`、模型 SHA `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`；日语对齐 revision `cf031e020336460d15a417eba710bbc5bb43be9a`、模型 SHA `4f6821dcd79770fcd4c11487c4ee5c040b3a7e1863425224014ba5ea8fbc1b67`；FFmpeg archive SHA `70f6754495d22213ba26544810fc6bc3e4e4dfd8d5cd7a3489c810bb2a4364d8`，实际版本 `n8.1.3-23-g5c4f5744cd-20261022`，不能写成固定 V 的 7.1.5。配置文件与下载残片保留，没有把残片当成可用模型。

补充摘要：torch wheel `0c361dda89b2a31f287bf816fe9007e28e7aa7765d1e87ab66bb5679772157e8`；triton wheel `5d6c9cd253f311de473570450840f901460a87a3aec26cbdcb22dd8b06e1e94c`；Noto 字体 `68a3fc98800b2a27b371f2fb79991daf3633bd89309d4ffaa6946fd587f375b5`；punkt_tab archive `e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106`。torch/triton/字体/断句数据的摘要为实际下载后计算，不能称为发布方签名。

### 8.5 交付与保护

继续在独立候选工作树检查和交付；原工作区既有 dirty 变更、正式任务数据库／产物、5 个未知目录、授权和已安装 App 均不能被候选覆盖。临时 QA 根、native build、GPU 缓存、独立恢复包和失败收据在用户缓存中保留。P5 未验收的项目不能借 1512 项回归通过晋级，P6 不通过删除兼容入口来伪造完成。操作与回退命令见[中英指南](unified-runtime-guide.zh-CN.md)。

## 9. 2026-10-23：M03／M24 接管与崩溃回退补验收

所有演练使用新独立副本、授权占位目录与回环端口；没有切换正式数据、替换 App、连接 GPU 主机、提交／推送或重启宿主系统。§8 的旧收据和固定恢复包原样保留。矩阵现为 **22 项 local_passed／3 项 partial／3 项 blocked**；M03 本机范围闭环，M24 平台门槛保留。

### 9.1 接管与旧入口

- 新增接管测试 10 例，连同 5 项既有 activation／guard 回归共 **15 passed**。8 个真实 SIGKILL 边界：取锁前、封锁前、OS 封锁完成但 sealed 记录前、sealed 后、事务前、最终 generation 复核后、提交前、提交后且 worker 未启动。握手只定位源码边界，不用异常替身代替进程死亡。
- 逐例核对源摘要／inode、原锁重新取得、队列暂停且无可认领操作。提交前 DocumentHead／8 个 GlobalHead 全无，提交后完整出现；重复恢复只有 1 个文档版本和 1 个 `task.created`。实际旧稿 r1→r2 保存新文字后，旧批次 generation 被拒，重新 prepare／verify 后只迁入一次 r2。旧锁 inode 替换在持锁复核和重开时均拒绝。
- 封锁后真实旧 GUI `create_app`／TestClient lifespan、字幕保存服务、CLI `resume`、原任务锁与 SQLite INSERT 五种入口拒写；未启动正式原生 App。
- 额外完成真实 `initialize/pin-recovery/takeover` → 6 路 HTTP → 同一 Supervisor／API PID 被 SIGKILL → 旧入口拒写 → 同一 runtime／guard `serve-guarded` → HTTP、暂停状态、原锁 inode 与 DB 计数一致。SIGTERM 后端口关闭、锁释放；Uvicorn 重放信号使退出码为 **-15**，未冒充 exit 0。

证据：[实际宿主收据](/Users/drm/project/nyaru-clipper/.omo/evidence/guarded-startup-20261023/receipt.md)、[接管专项复验](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/.omo/evidence/takeover-crash-20261023/recheck/receipt.md)。完整宿主现场 `/Users/drm/.cache/nyaru-clipper/guarded-startup-20261023-03`。接管测试清理仅解除自建旧根的封锁，收据证明的是观察时点的保护。

### 9.2 独立恢复的强杀缺口与修复

首轮 9 个 R1 边界 **2 passed／7 failed**：SQLite 日志、部分旧权限恢复、group 已 `thawed` 而最终收据缺失，使旧快照直接重试失败。RED 保留于 `~/.cache/nyaru-clipper/m24-sigkill-nzuuarzr/{junit.xml,pytest.log}`。

修复限定独立恢复及冻结资源：解封前 fsync `thaw-intent.json`，显式 `interrupted_thaw={path,sha256}` 固定原配方／快照／包／原权限日志，在锁屏障内复核原 inode。非控制根与旧原件变化拒绝；控制区只允许 DB／SQLite 辅助文件和两份 guard thaw 凭证的预期变化。当前 DB 再检查暂停、无执行权、无 R2、完整整组撤销集合；终态必须匹配 DB／guard 收据、原件字节和原权限才能补最终收据，不重新激活映射。验证失败统一以恢复拒绝退出。

新增 **21 场景**：9 个 R1 强杀边界、1 个 R0 中断、5 个变化拒绝、R2 提前拒绝、5 个终态缺失／损坏拒绝；与原 7 例共同复验。冻结 Python `-I -S -B` 审计禁止候选／模型 import、网络和子进程。收据保留握手、-9、锁、权限、inode、原件摘要、DB 状态和续跑／拒绝结果。终态反例覆盖缺失／损坏 `thawed.json`、空 DB 撤销收据、被改回 activated 的 binding／member；不产成功收据，也不自动修复注入的损坏。

**权限恢复非原子**：部分恢复时旧根可能已可创建，子目录／锁仍封锁；全部权限恢复后强杀会释放旧锁。旧权限恢复前已提交整组映射撤销，不能声称这段时间所有旧写入都拒绝。如果旧入口随后写入新数据，续跑应因原件变化停止并保留新数据。有限边界不代表任意指令点或真实重启资格。

最终报告、JUnit、源码检查和包身份见[恢复专项证据](/Users/drm/project/nyaru-clipper/.omo/evidence/recovery-crash-20261023-hook-verification.txt)及[详细报告](../.omo/evidence/recovery-crash-20261023/report.md)；用法见[回退指南](unified-runtime-guide.zh-CN.md)。新演练冻结包 SHA `4f86fc35cfbd1d6fd88adff49f975b37f4752d46badc5724a0a92abe39165fec`，完整现场 `/Users/drm/.cache/nyaru-clipper/m24-sigkill-rvee2gfr`，304 份非空收据摘要已核对。修复只进入新冻结包／新演练 epoch；10 月 22 日 build-04 样本 reader 和 build-05 App 均未替换，不能将新资格追溯授予旧包。

### 9.3 剩余门槛

M24 的受控 OS 重启、开机保护先于旧入口生效、Linux／WSL 只读挂载 profile 仍未验收。当前主机与远端既有进程没有重启授权；进程强杀不能替代系统重启。CUDA／WSL ROCm、真实直播、Windows AMF 保持原状态，P6 仍 planned。正式任务、旧源码工作区、固定包、原片、授权、未知目录和失败现场继续保护。

### 9.4 最终验证与源码身份

主会话在 backend cwd、`PATH="$PWD/.venv/bin:$PATH" TMPDIR=/tmp` 下实际执行：

- 全量 `python -m pytest -q`：**1538 passed，17 条既有 JUnit 警告，362.86 秒**；[JUnit](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-full-backend.xml)。该次 collection 后才补入最后 5 个终态反例，不能写作当前 1543 项的全量重跑。
- 最终稳定源码专项：guard、activation_failures、independent_thaw、migration_groups、recovery_recipes、takeover_crash_drills、recovery_crash_drills 共 **46 passed，149.82 秒**，包含上述 5 个终态反例；[JUnit](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-focused.xml)。不同执行计数不相加。
- 8 个本轮 Python 文件 AST 解析、无尾部空白，配对文档链接／验收 ID／摘要及 22／3／3 矩阵复核通过。独立代码审阅 **APPROVE／CLEAR／blockers=[]**，见[报告](../.omo/evidence/m03-m24-code-review.md)。无前端改动，未重复前端／GPU／原生媒体／LSP 验收。

本轮候选源码清单与测试收据关联见[源码封存](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-source.json)和[主会话收据](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-receipt.md)。仍未提交／推送／合并，旧 197 文件封存保持历史身份。

## 10. 2026-10-23：新 App 与独立恢复包

按用户后续授权，已将上述修复构建为新候选并完成隔离启动、冻结接管、R0／R1 回退、独立读取器强杀续跑、旧 helper 重开、R2 拒绝解冻，以及真实原生 r3 保存／退出／重开／独立恢复全文一致；[新包交付与验收](candidate-package-2026-10-23.zh-CN.md)为本轮入口。

新 App 为 `unified-native-build-20261023-01/Nyaru Clipper.app`；内置／独立 bundle SHA `1ce64b4effcc38a592d90b12e879dcc02a990a62316af8fbdc8e23e16b31ff12`。App ZIP 解包 5406 文件／权限一致、严格签名通过，恢复包 3619 资源摘要一致。正式 App 1496 文件内容摘要和正式数据 6815 项元数据前后全等；正式数据正文未读，不声称正文全量哈希。没有新增应用源码修改、正式替换／切换或提交推送。

全部自建进程结束，新 R2 域保持封锁，旧 build-04／05 和 epoch pin 不变。矩阵仍 22 local_passed／3 partial／3 blocked；未重复全套／GPU／ASR／供应商／OS 重启验收，不因此提升 M24 或启动 P6。
