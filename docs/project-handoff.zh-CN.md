# Nyaru-Clipper 项目交接

最新整合：[2026-10-26 高光算法与字幕编辑定向整合](highlight-subtitle-integration-2026-10-26.zh-CN.md)。统一队列高光分析／导出、字体搜索收藏与三层描边；正式 App 和数据未替换。

## 统一架构合并记录：2026-10-23（Asia/Shanghai）

本分支从远端 Web 提交 `13f7f6c27b7f506529c899691de83393de0ec5a4` 合并统一架构 `eda736bd905fffcf321642cbd94823e4aacd7be5`。保留原 Windows PowerShell 启动器、CUDA whisper.cpp 部署、锁、JSON 发布与读取、`.exe` 发现和 ChatGPT 私有凭据不可用边界；将 Windows 清理后发布终态的行为接入新的 OwnedUpload，并补执行槽互斥、异常传播与清理顺序回归。Windows 原生系统专属测试不能由本机模拟分支测试替代。

原 Web／macOS 工作树分别保留 53／56 项未提交内容，已按文件摘要、权限、暂存差异及 HEAD 进行前后核对。本轮在独立合并工作树提交并推送远端；原本地分支与工作树不前移，以免改变既有未提交修改的基线。最新测试、合并编号与远端核验见[合并收据](/Users/drm/project/nyaru-clipper/.omo/evidence/unified-merge-20261023/receipt.json)。下方“不合并／不推送”为此前时点的约束，已被本轮明确授权替代；正式 App、正式数据、封存域、旧 reader pin 和未闭环的平台门槛继续保留原边界。

## 版本控制更新：2026-10-23（Asia/Shanghai）

统一架构实现、恢复工具、直接测试与 App02 修复已提交为 `f8484d5560e971fb4a736e6296d876333cb5b7c6`（`feat: unify task execution, migration and recovery`），位于 `codex/unified-architecture-2026-10-22`。主目录文档归入 `codex/code-improvement-2026-10-21`；这两条分支是本轮明确推送目标，master 与其他开发分支不变。下文“尚未提交／未推送”的描述保留为原观察时点的历史，发布结果以[本轮 Git 收据](/Users/drm/project/nyaru-clipper/.omo/evidence/git-publication-20261023.json)及远端分支编号为准。

提交前在统一候选工作树重新执行：后端全量 **1551 passed**，前端 **332 passed／40 文件**，TypeScript／Vite 构建及三份 requirements 导出检查通过。App02 构建输入中的程序源码与此次提交内容一致，构建后仅索引／交接文档有变化；四处既有文件末尾空行提示保留。本轮只发布版本控制内容，不重新打包或安装，不切换正式数据，不补授平台资格。封存域、旧 epoch／reader pin、原始媒体和私有证据继续保留。

## 当前交接：2026-10-23（Asia/Shanghai）

### 交接刷新核对：2026-10-23 13:36（Asia/Shanghai）

本次仅更新交接文档并只读复核：App02 两个 ZIP、原生程序／冻结后端、固定恢复 bundle 的 SHA256 与上轮收据一致；真实测试域六根仍 immutable，未发现匹配的候选 App／后端进程。[本次核对收据](/Users/drm/project/nyaru-clipper/.omo/evidence/handoff-refresh-20261023-app02.json)。下方功能验收来自上轮实测，本次没有启动 App、重打包、重跑功能测试、连接远端或重新全量核验正式数据。

| 接手对象 | 当前入口与边界 |
| --- | --- |
| 最新候选 App02 | [App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-02/Nyaru-Clipper-unified-candidate-20261023-02.zip)；解包 App 位于 `/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-02/Nyaru Clipper.app`。显示 0.1.19／build 27，必须按下方摘要识别，不双击。 |
| 固定独立恢复包 | [恢复 ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02.zip)；固定 reader 目录 `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02`，不得移动或改绑既有 epoch。 |
| 最新真实任务与恢复证据 | 任务 `ad3ad70afddf5287b5d1b4f797665a2a`：21 条字幕，手工译文 2 条，第 2 版。[R2 清单](/Users/drm/.cache/nyaru-clipper/historical-fixed-native-20261023-01/R2/complete.json)／[独立恢复核验](/Users/drm/.cache/nyaru-clipper/historical-fixed-native-20261023-01/recovered-readonly/verification.json)：3 文档，无错误；本次核对的是保存的收据，未重新执行恢复。 |
| 禁止复用的测试入口 | `historical-fixed-native-20261023-01/runtime` 六根已封存，不能用上轮 launch argv 直接重开。历史 API 域 `historical-fixed-api-20261023-01` 和所有旧 R2／reader pin 保留；旧 App01 空根不作为 App02 默认入口。 |
| 正式环境 | 正式 App 未被候选替换、正式数据未切换。上轮正式 App 内容／元数据、正式数据元数据及选用原任务／原片保护核验见[最终审计](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/final-audit.json)；本次未重做正式数据正文核验。 |

**下一步顺序**：先用新的独立数据域和 App02 固定 reader 重跑 R0／R1 的接管、回退与重开，核对文档版本／全文及显式重试边界；再在获准的隔离平台补 M24 系统重启／开机保护。缺硬件的 CUDA／WSL ROCm／Windows AMF、外部翻译、真实直播等继续待验收，不能用旧包或本机结果代替。原 Workstation 的旧 Linux 绝对路径准备失败未在本轮处理；五个未知目录继续保护。P6、正式安装及数据切换均未启动，不能由“更新交接”推定授权。

### 历史任务修复候选 App02（最新）

F01／F02 已修复并用**新冻结包**复验：历史副本 25/25 场景组通过；真实 150 秒原片识别 21 条，手动译文显示 partial 2/21；原生播放、编辑第 2 版保存、CmdQ 重开、真实 15 秒烧录和系统保存通过。后端相邻回归 82 passed（包含 8 项专项）、前端 332 passed。新包与新独立恢复包均已校验；显示版本仍为 0.1.19／build 27，按摘要识别。

[App02 包与完整中英验收报告](candidate-fixes-2026-10-23.zh-CN.md) · [权威收据](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/receipt.md)。新 App ZIP SHA256 `914e36a0b7cf97ad864cedf9d87abfcfcb1b0ae76248b5ec5da2eb7272eff14b`；独立恢复 ZIP `31e364935d925993b6a849d8c1f7df21b325731c29a39e3e298774153a339c42`；新 epoch bundle `52342c6a998c6241a5381db6a778bb792ae38a0e197989d166da79da73016b54`，旧 pin 不变。

正式 App 内容／元数据、正式数据元数据及选用原始任务／原片核验一致；未替换、未切换、未提交。自建 App/helper／后端已停止，队列暂停。真实测试域 `historical-fixed-native-20261023-01` 六根 immutable、新 R2 已封存，独立恢复导出全部 3 文档并保留真实任务第 2 版。不得双击候选、直接重开／解封 R2 或替换旧 epoch 的 reader pin。新包 R0／R1、M24 系统重启／开机保护及缺硬件／供应商项目仍待验收，不启动 P6 或正式切换。

### 历史任务功能验收（App01 失败快照，已由上方新包闭环）

按用户要求使用历史任务的独立副本验证：冻结接口21组 **19通过／2失败**；150秒真实归档原片新建回放任务，识别21条、15秒切片／字幕烧录通过，浏览器编辑保存至第5版、重载保留。两项未修复问题为**部分译文误报整稿完成**与**迁移高光模式／评分／理由丢失**，不能据此宣布整体验收通过。原工作站因旧Linux绝对产物路径拒绝准备，零激活；五个未知目录保留。

原生界面受macOS锁屏阻挡，CmdQ／系统保存面板／连续播放仍待验收；浏览器结果不替代WKWebView资格。远端ROCm仅只读复核历史1条字幕、4组产物及30秒成片、模型与设备可见性，未重新推理。正式数据元数据、五个原历史任务与14个归档原片核验不变，所有自建候选／helper已停止；未改产品源码／重打包／安装／正式切换。详情与后续修复门槛见[中英验收文档](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/historical-task-acceptance-2026-10-23.zh-CN.md)，[权威证据](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/receipt.md)。

### 打包后交接检查（此前快照）

此前交接刷新仅更新文档并只读复核：压缩包存在、两处 bundle 摘要一致、两套 R2 数据库仍 immutable，未发现该候选的运行进程。当时未重跑应用测试、启动 App、重新构建或连接远端；以下打包验收来自保存的[打包收据](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-receipt.md)，后续功能验证以上方最新章节为准。

| 接手项 | 最新记录 |
| --- | --- |
| [候选 App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-01/Nyaru-Clipper-unified-candidate-20261023-01.zip) | SHA256 `7a5c3cad144c57dc74bda2391e157452b69418d1476fdd40e2895f3b310ad6a9`；5406 文件／权限解包全等，严格签名通过 |
| [独立恢复 ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01.zip) | SHA256 `47f34e5b0d577b20be6d4990bdfd6e093c946159581b4cd1a6035b548b969082`；固定目录 `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01` 不移动 |
| 本次实核 bundle | App 内与独立包均为 `1ce64b4effcc38a592d90b12e879dcc02a990a62316af8fbdc8e23e16b31ff12`；3619 资源完整检查属于打包验收记录 |
| 已验收的本机链路 | 冻结接管、R0／R1 解冻、R1 强杀续跑、旧 helper 重开、原生 r3 保存／退出／重开与独立导出全文一致；R2 解冻正确拒绝 |
| 审阅与正式环境 | [独立审阅](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-review.md) CLEAR／APPROVE／无阻塞；打包前后正式 App 1496 文件内容摘要、正式数据 6815 项元数据一致，未声称正式数据正文全量哈希 |
| 当前门槛 | M03 本机 local_passed，M24 partial；总表 22 local_passed／3 partial／3 blocked，P6 planned；不是全平台 accepted |
| 历史回归边界 | 10 月 23 日全量后端 1538 passed、最终专项 46 passed；最后 5 个终态反例在专项内覆盖，计数不相加；打包验收及此次文档刷新未重跑全套 |

以上为 App01 的历史入口：[当时运行与验收文档](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/candidate-package-2026-10-23.zh-CN.md)及空根 `/Users/drm/.cache/nyaru-clipper/packaged-native-empty-20261023-01/runtime.json`仅作旧记录保留，不是 App02 启动指令。新一轮试用须按顶部 App02 边界建立独立新域，显式指定绝对 `--unified-runtime` 与匹配 `--migration-guard`；不要双击、复用旧端口／PID或改绑 reader pin。

两套新封存域 `/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-recovery-03/R2`、`/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-native-guarded-01/R2` 仅作恢复证据，不直接启动或解封；旧 build-04 样本封存同样保留。下一步仍是获准隔离平台上的 M24 系统重启／开机保护资格，以及缺环境的 CUDA／WSL ROCm、Windows AMF 和真实直播验收，不能据此启动正式切换或 P6。


**方案 B 的统一架构候选已实现，本机与 native Linux ROCm 的限定工作流通过；跨平台资格及正式切换未完成。** 10 月 23 日按用户授权补验收 M03／M24，新增真实接管／恢复强杀演练并修复独立 thaw 续跑，见[执行记录第 9 节](unified-architecture-execution-2026-10-22.zh-CN.md#9-2026-10-23m03m24-接管与崩溃回退补验收)。没有切换正式数据、替换 App 或重启主机。下方历史记录只属于原观察时点。

### 1. 接手目录与阶段状态

**最新候选为顶部 App02**：[修复包与验收](candidate-fixes-2026-10-23.zh-CN.md)。[App01 包](candidate-package-2026-10-23.zh-CN.md)的接管、R0／R1 回退、R2 拒绝解冻及原生 r3 证据仅属于该旧包，不自动升级为 App02 资格。正式安装仍未替换。

| 项目 | 当前边界 |
| --- | --- |
| 候选源码 | `/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper`，分支 `codex/unified-architecture-2026-10-22`；继续实现和验收从这里开始 |
| 基线 HEAD | `428ba833193db888c6b049ac2983abe1b2ecae17`；统一架构实现仍未提交，不能仅凭 HEAD 重建候选 |
| 主目录 | `/Users/drm/project/nyaru-clipper`，分支 `codex/code-improvement-2026-10-21`、同一 HEAD；含既有未提交改动，不是统一实现目录 |
| P0／P1 | `completed`：隔离基线、产物进入共享编辑／产品导出链路已有本机证据 |
| P2—P4 | 实现与本机候选验证完成；累计平台资格仍待验收 |
| P5 | 本机迁移、整组回退与独立恢复已验证；目标平台及崩溃／重启资格未闭环 |
| P6 | `planned`；旧写入核心和兼容入口保留，不以删除代码代替验收 |
| 正式环境 | 未替换已安装 App、未迁移正式任务，未提交／推送／合并；正式安装来源的历史记录见[主目录交接](/Users/drm/project/nyaru-clipper/docs/project-handoff.zh-CN.md)的 10 月 21 日章节 |

实施前的[设计](superpowers/specs/2026-10-22-unified-architecture-design.zh-CN.md)与[分阶段计划](superpowers/plans/2026-10-22-unified-architecture.zh-CN.md)定义门槛；[执行记录第 8 节](unified-architecture-execution-2026-10-22.zh-CN.md#8-完整候选实现与当前验收账)记录实际证据；[运行／回退指南](unified-runtime-guide.zh-CN.md)提供可执行命令。阶段历史和测试通过均不能替代整项 `accepted`。

### 2. 已落地的架构与迁移边界

- **统一状态与执行**：SQLite 任务／操作／文档／发布为共同事实源；`models_unified.py`、`models_migration.py` 和增量 revision `20261022_01`；`unified_host.py`、`unified_cli.py`、`unified_dispatch.py` 承载单执行器及 `process_recording/process_live/translate/export` 四种操作。CPP 与 WhisperX 保留，排队、优先级／排序、暂停、取消、重试、attempt／token／进程组共用契约。
- **编辑与产物**：不可变正文＋CAS、版本历史和配置／模板快照；先持久化暂存和收据，再逐成员不可覆盖发布，最后整组提交。首片可用不代表父操作成功；重开按互斥判定表对账，不接纳孤稿或旧 attempt。
- **接管与锁**：`migration_*` 与 `source_seal.py` 使用外部来源 UUID、完整多根登记和 generation；`prepare/verify` 不授予写入权。同一 Supervisor 持续持锁、封锁旧根、复核并事务接管，接管后继续托管 API；不能退出它再另开未保护服务。Linux 保护要求另行验证的只读挂载，ROCm 推理通过不等于接管保护通过。
- **回退边界**：按整组判定 R0／R1／R2；任一任务或全局设置／模板／工程新写入使整组 sticky R2，取消另一批次不能降级。R0／R1 先提交全组撤销凭据再恢复旧权限；R2 保持封锁，走多根同 epoch 快照、只读导出或独立旧格式工作副本。不得 downgrade 新 DB、覆盖新稿或把统一根直接交给旧入口。
- **新版不能启动**：预先固定的独立 Python／reader／guard／旧 helper／媒体工具提供恢复，不依赖候选源码、虚拟环境、模型或网络；凭据只保存外部引用。部分封锁／thaw 失败保留原权限日志与 `controls-resealed.json`，按指南用新输出目录续跑，不从当前只读权限猜测原模式。

### 3. 验收证据与未完成项

完整 M01—M28 表保留在执行记录 §8.3：**22 项 `local_passed`、3 项 `partial`、3 项 `blocked`**。M03 本机范围已闭环，M24 仍有平台门槛；这些状态不等于跨平台全部已验收。下表保留 10 月 22 日结果，本轮新增回归／强杀／实际 HTTP 证据另见执行记录 §9。

| 已观察结果 | 可复核证据与限制 |
| --- | --- |
| 后端／前端／构建 | 后端 **1512 passed、0 failed／skipped**，17 项既有 JUnit 警告；前端 **332 passed／40 文件**、TypeScript／Vite 通过。后端收据 [r5.xml](/Users/drm/.cache/nyaru-clipper/unified-backend-20261022-r5.xml)；本轮重读该收据，没有重跑 |
| 实际浏览器 | Chrome **2 passed**；队列键盘／触屏排序、优先级／暂停、CAS 409 草稿保留、真实 ASS 下载、SSE 失败转轮询及游标重连；证据 [browser-r7](/Users/drm/.cache/nyaru-clipper/unified-queue-20261022-1_md6l57/browser-r7) |
| macOS 实际媒体 | 150.033333 秒媒体经 whisper.cpp 得到 6 cue，编辑保存 revision 1、0—30 秒烧录、正常退出／同构建重开保留选择与暂停状态；坏媒体测试任务保留失败。最终 build-05 另验证空根初始化／启动／退出，不冒充重跑了全部媒体验收 |
| 实际产品导出 | 5000 cue 编辑保留其余 4999 条；真实产品 API 下载 MP4，既定参数与原件摘要通过，固定 V 最大 RMSE **0.356518**、bbox **1 px**；[产品证据](/Users/drm/.cache/nyaru-clipper/unified-p1-product-20261022-final) |
| native Linux ROCm | Rocky 9.8／ROCm 7.2.4／RX 7900 GRE；真实 WhisperX GPU float16→日语对齐→编辑 revision 1→PNG→30 秒 CPU 烧录／浏览器下载／完整解码，重开保留操作与产物；[收据目录](/Users/drm/.cache/nyaru-clipper/unified-gpu-result-20261022-r4)。一个识别 cue 不构成识别语义质量验收 |
| 独立恢复 | 冻结入口 `-I -S -B` 的 6 根快照／只读导出；1 文档、6 cue、4 登记发布一致，`complete=true`、零错误；另有 7 种 thaw 组合及失败续跑证据 |

剩余门槛：M12 真实直播补充、M22 Windows AMF、M24 受控系统重启／开机保护顺序及其他平台 profile 仍 `partial`；有限 SIGKILL 边界不代表所有时刻。M18 Linux CUDA 与 WSL ROCm 缺对应环境、M19 缺受控真实直播来源、M21 缺 P6 前提而 `blocked`。native Linux ROCm 不能替代 CUDA／WSL。其 Noto 字体替代和 FFmpeg 版本不同，不能替代 macOS 固定 V 同字体图像指标；保留 SOCKS 代理时的 HTTPX 兼容性未验收。外部供应商／付费调用、公证及正式发布未新增验收。

### 4. 构建、恢复包与必须保留的数据

以下缓存均为本机私有证据，不随 clone 分发，不清理、不把凭据加入 Git。以 `/Users/drm/.cache/nyaru-clipper/` 为前缀：

| 用途 | 精确位置与注意事项 |
| --- | --- |
| 最新候选 App02 | `unified-native-build-20261023-02/Nyaru Clipper.app`；5407 文件及包摘要见顶部。仅在新独立域按显式 runtime／guard 运行，真实测试域已封存。 |
| 最新 App02 独立恢复包 | `unified-recovery-20261023-02/bundle.json`，SHA `52342c6a998c6241a5381db6a778bb792ae38a0e197989d166da79da73016b54`；3620 资源核对，固定路径不可移动。 |
| 历史 App01 与固定恢复包 | `unified-native-build-20261023-01/Nyaru Clipper.app`、`unified-recovery-20261023-01/bundle.json`，旧 bundle SHA `1ce64b4effcc38a592d90b12e879dcc02a990a62316af8fbdc8e23e16b31ff12`；5406／3619 文件属旧包，旧空根 `packaged-native-empty-20261023-01/runtime.json` 不作为 App02 启动入口。保留既有 epoch 固定路径。 |
| 旧候选 App | `unified-native-build-20261022-05/Nyaru Clipper.app` 保留历史身份，不包含本次恢复修复，不覆盖或原地升级 |
| 真实 CPP 样本根 | `unified-native-runtime-20261022-01`，任务 `8cb8f1980a815e9696728c36545ebfd6`；六根已安装只读／immutable 封锁，不直接启动或随意解封 |
| 样本固定 reader | **`unified-native-build-20261022-04/Nyaru Clipper.app/Contents/Resources/recovery/bundle.json`**，SHA `1fbeb3c8f87145d1c78e1d41b4ac5670d24fbc8f9b6f22038389eab69fbe7731`；不可替换成 build-05 的包 |
| 配方／完整快照 | `unified-native-recovery-recipe-20261022-04.json`；`unified-native-snapshot-20261022-04/complete.json`，SHA `8859a044a485b6dec4476c2809b96c1ffda7cc77af16459844aa8b5092ab18a7` |
| 独立恢复核验 | `unified-native-recovered-20261022-04/verification.json`，SHA `e74d5f452b633034f4c126228e6e9e65441f3372ecf108ecaa1ef0fe2ba54b2a` |
| App02 打包输入 | [准确输入清单](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/source-input.json)与[构建后审计](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/final-audit.json)；后续交接编辑不属于包内输入身份。 |
| App01 历史打包输入 | [202 文件清单](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-source.json)，摘要 `1e10e6b3d72ea396b8b0223c1dea3251cfbbf807c51062407b1e31e2078df7ba`；仅对应此前包，不标识 App02。 |
| 10 月 22 日历史封存 | `unified-source-manifest-20261022-final.json`，197 文件摘要 `6ba9d792c80b08523b1ab1beb3d2497a46b2346072778502cf321abfb1e8e002`；早于后续恢复修复，不代表当前源码或本轮新包 |

GPU 工作站使用用户授权的 SSH 别名 `server-194`；隔离根 `/home/drm/nyaru-unified-20261022-4eE6Qm` 内保留 `repo`、`models/faster-whisper-small`、`models/alignment-ja`、`gpu-runtime/runtime.json`、`gpu-env.sh`、失败 attempt 与全部下载收据。进程环境限定了设备、离线模型、NLTK、字体与代理；复测前先读环境配方和执行记录 §8.4，不能只启动裸环境。任务 `8333059829bd563b9094d3065a87355c` 的处理为 attempt 2（第一次缺 punkt_tab），导出为 attempt 1。产物 SHA `a88627da42b28bad83af40a2d2c1e16330d4fc8458e0e4f3cbb3d3f7777a5866` 属于此前 GPU 资格与本地收据核验；本次文档刷新未重做 GPU 或产物哈希验收。

验收结束时，自建临时 App／API／SSH 转发已停止，远端无关 `uv` 进程未处理；**本轮没有重查远端或当前服务，不沿用旧 PID／端口为在线状态**。正式数据库、原片、授权、App 备份以及历史清单中 5 个未归属目录继续保护，目录数量是旧清单，不能推断当前数量。一次自动化误开默认兼容入口曾新增正式根 `startup-*.json`，当时未观察到业务文件改写；不可声称正式根完全零写入。

### 5. 下一位接手者的执行顺序

1. 在候选工作树只读核对 branch／HEAD／dirty 和本节证据，保留主目录既有改动。使用新独立根，按运行指南初始化；原生启动和重开必须显式传 `--unified-runtime /absolute/runtime.json`，省略参数会走兼容默认路径。已接管运行时另需同一 pinned runtime 与 `--migration-guard`／`serve-guarded`。
2. 先用 App02、新独立副本与本包固定 reader 重跑 R0／R1 接管、回退及重开，核对文档版本／全文和显式重试边界，再补 P5 M24 受控重启／开机保护与目标平台 profile。此前 M03 本机接管／重开证据属于原包，不能代替 App02 复验。使用多根配方与暂停队列；SIGKILL 续跑保留原 `thaw-intent.json`。已封存真实／CPP 样本只读，不作为新测试根。
3. 分别补齐 CUDA、WSL ROCm、Windows AMF 和获准的真实直播环境／来源，按原矩阵留真实收据；拿不到环境时保持原状态。依赖清单按生成脚本维护，不能借补验收重锁原 GPU pins。
4. 必选资格全部通过后，再审核提交范围和正式切换方案；正式安装／迁移需单独明确授权。P6 还须调用清单清零并审核具体删除范围。在此之前保留兼容入口、旧数据和所有失败证据，不 reset／clean／批量暂存／推送／合并，不用旧快照覆盖较新数据。

---

## 历史交接：2026-10-14（保留原观察时点）

**本轮 Git 提交范围（2026-10-14）**：本次将双语翻译、Key／模型持久配置、App 0.1.4 打包及配对技术验收记录提交到三个既有开发分支。较早段落的未提交／未推送保留其观察日期；准确当前源码及远程 HEAD 以 `git log -1`、`git ls-remote origin` 为准。私密配置、媒体、模型、构建包及 `.omo` 证据留在本机。

**真实翻译验收补充（2026-10-14）**：用户设置 Key 后，App 0.1.4 使用 Flash 完成既有 40c0c9 的 658 条及 7fe886 的 1448 条翻译，生成 2 份完整和 6 份切片双语 SRT。全部时间轴、偏移、输出校验和及 86 个原文件保持不变；八份下载／预览接口、原生完整视频／切片双语播放及两次系统 SRT 导出通过。未重新下载、识别或编码。24 条语义抽查不能替代逐句校对，识别误字与含混句仍需人工复核。见[真实翻译验收](deepseek-real-translation-acceptance-2026-10-14.zh-CN.md)。下文尚未输入 Key／真实翻译待验收为历史状态。

**模型选择补充（2026-10-14）**：App 0.1.4 build 5 新增 Flash／V4 Pro 翻译模型选择，保存到现有配置并在重启加载，保留 Key。已开始的任务恢复时沿用原模型。121 项相关后端、7 项界面测试、冻结后台保存／重启、安装版浏览器实测、签名及 ZIP 通过，86 个原任务文件保持不变。真实翻译仍待 Key，源码未提交／推送。见[模型选择验收](model-selection-acceptance-2026-10-14.zh-CN.md)。

**Key 持久配置补充（2026-10-14）**：按用户新要求，App 0.1.3 build 4 将 Key 保存到 `runs/config.json` 并在重启时加载，替代下文的会话方案。117 项相关后端、6 项界面测试、构建和隔离冻结后台重启验证通过；真实 Key 尚未输入。详见[持久配置验收](persistent-key-acceptance-2026-10-14.zh-CN.md)。源码仍未提交／推送。

**双语字幕补充（2026-10-14）**：App 已升级安装为 0.1.2 build 3，新增 DeepSeek 日译中、原时间轴的完整／切片双语 SRT、预览切换、翻译进度和续传。Key 仅用于本次会话。111 项 App 后端回归、155 项共享前端测试、构建／签名／ZIP 校验通过，两个已有任务的 86 个原文件校验和保持不变。用户选择稍后输入 Key，真实翻译与原生双语播放／保存待验收；本功能的新增修改尚未提交或推送。详见[阶段记录](deepseek-bilingual-acceptance-2026-10-14.zh-CN.md)及[使用指南](deepseek-bilingual.zh-CN.md)。下文远程同步状态和首版功能范围为此前快照。

**远程同步补充（2026-10-14）**：当前源码及文档已提交并推送至 `origin` 的三个开发分支：`feat/arctime-pro-plugin`（包含原目录工作站改动及完整开发记录）、`codex/local-companion-web`、`codex/local-companion-macos`。本次功能提交已远程核验为 `d4f28f9`、`5baf166`、`1366686`；后续交接文档提交的最新 HEAD 以 `git log -1`／`git ls-remote origin` 为准。下文“未提交／未推送”、旧分支 HEAD 与原目录脏工作区说明均为较早快照，以本段为当前 Git 状态。App 保留网页版的共享修复；`master` 未修改。

本次同步前复核：原目录 143 项所选后台、137 项前端测试和 7 项浏览器端到端测试通过，前端构建通过；网页版 95 项、App 版 99 项后台回归通过，0.1.1 包严格签名及旧适配器 Swift 编译通过。16 个脚本的原有可执行权限已恢复，Shell 语法检查通过。模型、媒体、构建包、私密配置和自动化临时证据留在本机。未重跑真实媒体／原生按钮验收，也不代表已完成公证或正式发布。

更新及 Git／文档核验：**2026-10-14，Asia/Shanghai**。本文是原目录的综合交接入口；已补齐网页版／App 分支拆分。历史媒体验收和服务状态保留其观察日期，本次没有重跑功能测试或启动服务。

## 当前结论与授权范围

最新复测：同日当前任务再次以 2.040 秒末尾越界失败，初次两秒容差覆盖不足。已改为有界末尾窗口裁剪，从 App 分支重建并安装 0.1.1（build 2），复用已下载视频恢复完成：658 条字幕、2 个切片；网页版 95 项、App 版 99 项所选回归通过。详见[Issue #1 复测记录](macos-app-issue1-retest-2026-10-14.zh-CN.md)。源码未提交／推送，历史记录中的两秒策略已被替换。

2026-10-14 后续修复：已安装 App 中失败的 81 分钟任务已恢复完成，生成 1448 条字幕和 4 个高光切片。94 项所选回归、原生完成／播放、输出校验通过。原目录构建／ZIP 已更新，两个独立工作目录同步了未提交修复，独立目录旧构建未重建。详见[失败任务恢复记录](macos-app-recovery-2026-10-14.zh-CN.md)。以下分支提交和历史验收快照保留其原观察范围；两个独立工作目录目前有这次修复的未提交修改。

当前交付方向是独立本地配套工具及 macOS App：**只提供视频链接，自动下载、识别字幕文字和句子时间轴，再按指定时间段或字幕规则高光导出切片**。已经提供进度、预览、导出和中断恢复。

用户已选择本地开源路线。当前处理不启动 ArcTime，不调用其付费自动打轴或云服务；`arctime` 仍是代码目录名。macOS 首版只封装当前配套工具，旧 GPU 工作站的翻译、校对、任务库及队列不在本次 App 范围内。后续不能把目录名理解为需要重新接入付费服务。

| 项目 | 状态 | 证据与边界 |
| --- | --- | --- |
| 本地 CLI 流水线 | 已完成，短样例已验收 | 2026-10-12 真实下载／ASR／导出及恢复；80 项所选回归 |
| 浏览器 GUI | 已完成，短样例已验收 | 2026-10-13 两种模式、预览、字幕跳转、下载、历史和窄屏；99 项所选后端、137 项前端回归 |
| macOS App 0.1.0 | 已完成，本机原生流程已验收 | 88 项相关回归；真实原生表单、播放、保存／替换／取消、中断恢复；arm64，最低 macOS 27.0 |
| 旧 GPU 工作站 | 原有代码保留，本轮未重验收 | FastAPI/SQLModel、React、WhisperX、翻译／校对、队列；部署见旧手册 |
| 分支拆分 | 已完成并本地提交 | 网页版 `74e600b`；App 版 `ca0e413`，继承网页版；两工作目录当前干净 |
| 对外正式发布 | 未完成 | 已有本地提交，未推送远程；仅 ad-hoc 签名，无 Developer ID、公证或跨机器验收 |

以上测试数字属于对应阶段的历史验收，所选文件不同，不能相加或视作全仓库通过。2026-10-14 分支拆分时，网页版独立目录通过 **84 个后台、154 个前端测试（21 files）**和双入口构建；App 独立目录通过 **88 个后台测试**、完整打包、严格签名及冻结后台 HTTP 检查。前端数量与旧报告不同，因为未合入原目录更早的工作站修改；后台有 Starlette/httpx 弃用提示，未导致失败。这次仅更新交接并核对 Git／文件，未重复以上验收。

## 两个版本的接手入口

| 版本 | 分支／提交 | 工作目录及范围 |
| --- | --- | --- |
| 网页版 | `codex/local-companion-web`／`74e600ba16f1890e27cb09bddd4a1585321d91d8` | `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper`；本地 CLI、下载、字幕与时间轴、指定／高光切片、浏览器进度／预览／导出／恢复 |
| App 版 | `codex/local-companion-macos`／`ca0e41341dfd939816d498116b8b790083c86c6f` | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper`；继承上述核心，增加原生窗口／保存、后台进程清理、内置工具／模型及 App 打包 |

共同原始基线为 `0bcd8d5`。App 分支保留共享 React 界面和处理核心；共享修复先在网页版提交，再合入 App 分支。App 专属修改在 App 分支进行。继续开发直接进入对应工作目录，避免在原目录切换分支时混入旧修改。

版本交接：[网页版](../../../.codex/worktrees/local-companion-web/nyaru-clipper/docs/project-handoff.zh-CN.md)、[App 版](../../../.codex/worktrees/local-companion-macos/nyaru-clipper/docs/project-handoff.zh-CN.md)。[拆分回执](../.omo/evidence/branch-split-2026-10-14.json) 位于原目录本机证据区，不随 Git 分发。模型、视频、任务记录、配置、构建产物、旧工作站修改和早期 ArcTime 桌面适配器均未作为本批新增提交纳入分支。

## Git 与当前运行状态

- 仓库：`/Users/drm/project/nyaru-clipper`。
- 分支：`feat/arctime-pro-plugin`；当前 HEAD：`0bcd8d5`，`chore: adopt GPL-3.0-only license`。
- 上述是原目录保留的开发快照；两个新分支的实际提交和工作目录见上表。本次核验分支 HEAD、App 继承关系及两个工作目录无未提交修改；没有新增提交、fetch 或 push。
- `origin` 已配置为 `https://github.com/damin93381/nyaru-clipper.git`。本次未 fetch，远端最新状态和领先／落后关系未核验。
- 工作区有大量未提交修改和未跟踪文件，包含更早的原工作站改动。不能将这些修改全部归为本地工具或 App，也不能直接 `git add .`、重置或清理。
- 历史 2026-10-13 快照：已安装 App 后台 `ready=true`，四个任务为 `completed`；开发浏览器 `http://127.0.0.1:8787/` 不可达。本次没有核验它们当前是否在线。App 使用随机回环端口，不能把开发浏览器地址当作 App 地址；打开的标签页也不是运行证据。
- 2026-10-14 拆分验收：网页版使用隔离端口，首页、配置（ready）及空历史响应正常；新冻结后台在 `PATH=/usr/bin:/bin` 和临时数据目录下响应正常。两者验收后已停止；这是启动检查，不是媒体流水线复验。

以上运行状态均标明观察日期；当前在线状态待验证，继续任务时需重新检查。

## 交付物与数据保护

| 内容 | 位置 |
| --- | --- |
| 已安装 App | `/Users/drm/Applications/Nyaru Clipper.app` |
| 原 App 构建 | 原目录 `dist/Nyaru Clipper.app`；历史验收产物 |
| App 分支新构建 | `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper/dist/Nyaru Clipper.app`；本次核对存在，未替换已安装 App |
| 原 ZIP 构建 | 原目录 `dist/Nyaru-Clipper-macOS-arm64.zip`；2026-10-13 记录为 496480853 字节；新分支构建器输出 `.app`，不会自动生成 ZIP |
| App 模型／任务／日志 | `~/Library/Application Support/Nyaru Clipper/` 下的 `models/`、`runs/`、`app.log` |
| CLI／浏览器版任务 | 项目 `data/local-runs/`，不自动迁入 App |
| 独立开发 Python | `~/.cache/nyaru-clipper/companion-venv/bin/python` |
| CLI 默认模型 | `~/.cache/nyaru-clipper/models/ggml-small.bin` |

App 内置 Python、yt-dlp、FFmpeg/ffprobe、whisper.cpp、GGML 动态后端和多语种 small 模型，运行时无需终端或 Homebrew。首次启动将校验过的模型复制到用户数据目录；现有模型校验失败会报错并保留文件，不静默覆盖。

模型 SHA-256：`1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b`。原包签名／ZIP 完整性是历史记录；2026-10-14 App 分支的新构建已通过 `codesign --verify --deep --strict`，包内 yt-dlp 返回 `2026.08.19`。本次文档更新没有重新检查签名、模型校验和或 ZIP 完整性。

保留用户模型、任务清单、转写、已导出视频／字幕和失败日志；不要手改 `data/` 或 App 任务清单，未经明确选择替换，不要覆盖不同内容的导出文件。构建器遇到现有 `dist/Nyaru Clipper.app` 会拒绝覆盖，重建前先移走旧构建。移动 App 不删除数据，但未完成 ASR 的恢复会比较识别配置，当前须保持原 App 安装路径和模型；未完成下载需重新提交链接。

## 处理流程与源码入口

```mermaid
flowchart LR
    U[输入视频链接与切片模式] --> D[yt-dlp 下载]
    D --> A[FFmpeg 提取单声道 16 kHz 音频]
    A --> W[whisper.cpp 本地识别]
    W --> T[完整 SRT / TXT / JSON 与句子时间轴]
    T --> S{切片选择}
    S --> R[指定多个时间段]
    S --> H[字幕规则高光评分]
    R --> E[FFmpeg 导出 MP4 与从零计时 SRT]
    H --> E
    E --> P[预览与下载 / 原生保存面板]
```

ASR 按五分钟音频块处理，有源文件与配置校验、缓存和时间偏移。高光使用字幕密度、笑声、兴奋词和重复表达，选择达到阈值的非重叠片段；上限不保证一定导出该数量，也可能零片段。没有词级强制对齐、说话人分离、画面理解或大模型语义评分。

| 文件／目录 | 责任 |
| --- | --- |
| `scripts/local_companion.py`、`backend/app/arctime/cli.py` | CLI 的 doctor/run/resume/gui |
| `backend/app/arctime/workflow.py` | 清单、锁、下载与阶段恢复、校验、导出检查点 |
| `backend/app/arctime/local_asr.py` | 本地 whisper.cpp、五分钟块缓存与时间轴 |
| `backend/app/arctime/media.py` | 工具定位、下载、探测、字幕解析／重定位及切片选择 |
| `backend/app/arctime/gui.py` | 独立 FastAPI `/companion-api`、单任务执行、历史、文件白名单、视频 Range 与 WebVTT |
| `web/companion.html`、`web/src/companion/` | 独立 React 图形界面，复用设计令牌／组件 |
| `desktop/macos/App.swift` | AppKit/WebKit 窗口、启动状态、原生下载／保存、进程组退出清理 |
| `scripts/macos_companion.py`、`backend/app/arctime/macos.py` | 冻结后台入口、yt-dlp 自调用、模型校验、随机端口、父进程监控 |
| `scripts/build_macos_app.py`、`desktop/macos/requirements-build.txt` | PyInstaller 打包、原生依赖、Swift 编译、许可证、签名 |
| `backend/app/services/export_encoding.py` | 复用的 CPU H.264/AAC 编码；不要为 App 另造导出器 |
| `backend/app/main.py`、`worker.py`、`web/src/workstation/` | 旧工作站入口；本轮 App 不从这里启动 |

`backend/app/arctime/desktop.py` 和 `bridge.swift` 保留早期 ArcTime 桌面适配代码，当前本地入口不调用它们。原工作站的 uv/pnpm、单 GPU worker 与可信内网约束继续见根目录及子目录 `AGENTS.md`。

这些早期适配器及未跟踪 AGENTS 知识库只保留在原目录，没有作为产品源码加入两个新分支。网页版不含 `macos.py`、`desktop/macos/` 和 App 构建脚本；App 相对网页版的处理核心差异仅为 `media.py` 的冻结工具定位／下载器分派，其余核心相同。

## 接手运行与验证

以下进入网页版工作目录执行。App 可直接双击已安装包；浏览器 GUI 需要独立环境与已构建前端。

```bash
cd /Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py doctor
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/local_companion.py gui
```

GUI 默认监听 8787，支持 `--port`、`--output-dir`、`--model`、`--threads`。关闭浏览器页面不停止服务；App 关闭窗口或 Cmd-Q 则停止后台及子进程。

每个工作目录默认使用自己的 `data/local-runs/`，不会自动复制原目录历史。需要复用原历史时指定 `gui --output-dir /Users/drm/project/nyaru-clipper/data/local-runs`；不要同时启动两个服务写入相同任务。App 仍使用独立的 Application Support 目录。

前端修改后的构建及回归必须在 `web` 目录执行，以匹配锁定的 pnpm 版本：

```bash
cd web
corepack pnpm build
corepack pnpm test --run
```

App 相关 88 项回归在 App 分支目录执行；网页版选择同一组文件时去掉 `test_macos_companion.py`，为 84 项。独立环境已安装测试依赖，但 `requirements-build.txt` 不负责安装 pytest/httpx。旧验收中的 `/tmp/nyaru-arctime-tests/bin/python` 已不存在，不要继续依赖。

```bash
cd /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper
PYTHONPATH=backend ~/.cache/nyaru-clipper/companion-venv/bin/python -m pytest \
  backend/tests/test_macos_companion.py backend/tests/test_arctime_media.py \
  backend/tests/test_arctime_workflow.py backend/tests/test_local_asr.py \
  backend/tests/test_local_companion_cli.py backend/tests/test_companion_gui.py -q
```

App 重建前保留旧产物，然后使用含 PyInstaller 的独立构建环境执行：

```bash
cd /Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper
~/.cache/nyaru-clipper/companion-venv/bin/python scripts/build_macos_app.py
```

从零准备构建环境及模型参数见 [macOS 使用／构建说明](macos-app.zh-CN.md)。当前编译目标和原生依赖都要求 macOS 27；兼容旧系统须重新选择或构建依赖，不能仅修改 Info.plist。不要将完整 GPU 后端依赖塞入 App。

## 验收证据与已修复问题

- [CLI 验收](local-companion-acceptance-2026-10-12.md)、[浏览器 GUI 验收](local-companion-gui-acceptance-2026-10-13.md)、[macOS 原生验收](macos-app-acceptance-2026-10-13.md)。
- [2026-10-14 分支拆分回执](../.omo/evidence/branch-split-2026-10-14.json)：提交、测试选择、新构建及隔离 HTTP 检查。原生按钮操作／真实媒体处理没有随拆分再次验收。
- `.omo/evidence/macos-runtime-qa.json`：42 个 Mach-O 无开发机绝对依赖、包内媒体解码、强杀父应用后清理识别组及端口、模型／导出保留。
- `.omo/evidence/macos-native-qa.json` 及 `macos-export.mp4`／`.srt`：原生播放器、保存、同名替换、取消、高光表单、中断恢复。
- `.omo/evidence/macos-app-review.md`：独立审阅 WATCH / APPROVE，阻断项为空。审阅者验证代码／证据，不等于其亲自点击所有原生流程。

已修复首次启动重复 setsid 的 EPERM、WKDownload 不能写入已存在目标（改为同目录临时下载后安全替换）、helper 先退出导致遗漏进程组 SIGKILL、不同模型文件名导致首启缺文件。保留这些失败及修复记录，避免回退。

桌面自动化曾出现 ScreenCaptureKit -3811，重启后恢复并完成主要原生验收；额外退出复查遇到 -3812，未执行退出。不要把工具失败记为成功操作，健康响应也不等于重新验收功能。

## 待办与禁止动作

下面是未实施的后续工作，不是已承诺交付或当前阻塞：

1. 用用户授权的真实平台短视频核验下载访问条件，再覆盖长视频、识别质量、资源使用及实际扬声器输出。合成短样例不能代替这些验收。
2. 确定要支持的最低 macOS 版本，准备对应原生工具和干净机器验收；Intel 支持需独立构建与验证。
3. 如需对外分发，再处理 Developer ID、公证、依赖／模型许可证和源码交付要求；当前包只完成本地签名。
4. 在用户进一步要求语义或画面高光时扩展评分；当前规则筛选的能力边界必须继续说明。
5. 分支拆分已完成；后续共享修改先进入网页版，再同步 App 分支。远程推送需按后续指令执行，继续保留原目录旧工作站改动。

不要恢复调用 ArcTime 付费能力，不要删除模型／历史／失败证据，不要改生成的 requirements/API 类型或运行时目录，不要把服务直接暴露公网，不要为此增加 Redis/Celery 或多 worker。本文更新没有修改产品代码、启动／停止服务、提交或推送。
