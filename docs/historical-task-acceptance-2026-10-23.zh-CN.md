# 历史任务功能验收

日期：2026-10-23（Asia/Shanghai）。对 `unified-native-build-20261023-01` 候选的冻结后端及随包工作台实测。**接口矩阵 19 组通过、2 组失败；整体验收未通过。** 两项产品问题尚未修复；旧工作站接管和锁屏下的原生交互另列限制。本轮只新增隔离运行数据、验收脚本与文档，未修改产品源码、重新打包或切换正式环境。

## 样本与执行边界

| 样本 | 本轮使用方式 | 事实边界 |
| --- | --- | --- |
| CLI 历史任务 `4beb340e0219`、`b6ee69e3b13a`、`e42790586570`、`061b0ecce533`、`2b46c356913c` | 全部复制到新域，以新来源 UUID 注册、准备、核验、接管 | 五个既有任务共用 20.4 秒 Tingting／FFmpeg 合成源；前三项各两个人工切片，后两项各一个高光片；不能视为五个真实节目 |
| 已保留的真实原片 `录播-472c1adbd0d1.mp4` | 复制后新建独立回放任务 `6a33ec62805c5b4dbbd69d8f2f82259d` | 150.033333 秒，实际 whisper.cpp small／ja 产生 21 条字幕与 0–15 秒切片；属于重新处理原片，不是恢复已删除任务 |
| 原工作站 `task-ec2a386fa864` | 只读 SQLite backup 与任务副本，在独立域尝试准备 | 旧数据库仍引用 `/home/drm/workfile/...`；未改写这些路径来制造接管成功。另五个未登记目录保持未知数据 |
| 早期 `40c0c9a8e93e`、`7fe886d15999` | 仅核实清理状态 | 658／1448 条字幕对应的任务、稿件和派生视频已永久删除，本轮没有恢复或以旧报告冒充重开结果 |

真实原片来自 `/Users/drm/Movies/Nyaru Clipper/原始录播/20261017-014802/完整原片/录播-472c1adbd0d1.mp4`，40,136,792 字节，SHA256 `aa444790a8f22575bda82335e451ff8a7e4c927671a1e44f25bc41dc139790c7`。译文仅手动填入两条带 QA 标记的文本，未调用外部翻译；21 条识别结果未逐句评定语义质量。

## 验收矩阵

| 功能 | 结果 | 实测依据 |
| --- | --- | --- |
| 历史 Companion 接管 | 通过，限定五个样本 | 冻结 CLI 完成接管，初始队列暂停；全部原字幕文字／时间、源片与切片摘要一致 |
| 任务库 | 通过 | 分页、检索、标题、标签、归档／取消归档、过期元数据版本 409 |
| 字幕保存与版本 | 通过 | 原文／译文、样式／位置／时间保存；旧版本 409、非法时间拒绝、不可变版本历史、原 SRT 保留 |
| 工作台编辑 | 通过，浏览器表面 | 21 条第二页正常；切换两条字幕任务后分页重置；X640→641→撤销640；拆分21→22、撤销／重做；合并21→20后撤销；最终21条、第5版，原文与时间轴恢复一致，重载仍保留 |
| 预览 | 部分通过 | PNG／libass、视频元数据、原片／切片选择和定位通过；锁屏期间播放请求 accepted、readyState4，但时间未推进，连续播放未验收 |
| 模板／公开设置 | 通过，限定存储协议 | CRUD、同 ID 版本更新、过期 CAS、导入／下载、默认模板与工程引用删除保护；ATPJ 使用 QA 字节样本，不能视为真实 ArcTime 工程打开成功 |
| SRT／VTT／ASS／ArcTime ZIP | 通过，限定产物协议 | 原始与保存稿、完整与切片下载、时间轴、ZIP 成员和导出内容核验；未启动 ArcTime 应用 |
| CPU 字幕烧录 | 通过 | 合成历史片6秒及真实片15秒通过实际产品导出接口；真实片从工作台按钮提交、链接下载，登记摘要、音视频轨、全量解码与字幕帧核验 |
| 队列 | 通过 | 暂停／启动、排序、优先级、单项暂停、取消／显式重试、过期队列版本拒绝、重复导出复用 |
| 进程崩溃与重开 | 通过，冻结后端表面 | 对运行中导出实际 SIGKILL，重开后 interrupted、不自动重试；显式 attempt2 成功；最终暂停重开保留稿件和4个导出。原生 CmdQ／NSSavePanel 本轮被锁屏阻挡 |
| 缺授权／坏输入／坏产物 | 通过 | 空凭据翻译拒绝，非法路径、缺任务、无效模板、缺失登记产物均有对应拒绝收据 |
| 部分翻译进度 | **失败 F01** | 实际1/2译文，API返回 completed／2/2；真实原片最初仅1/21译文，界面同样显示21/21已完成 |
| 历史高光语义 | **失败 F02** | 两个原高光任务 mode→ranges，score0.77→null、四条reasons→空；区间及媒体摘要保留 |
| 原工作站接管 | 部分／待处理 | 准备因旧主机绝对产物路径拒绝，零 TaskBinding、零操作；原数据库／目录不变，不能称成功迁移 |
| GPU／直播／跨平台 | 未获得新的功能通过结论 | 本轮 GPU 历史结果只读核验另见 remote 收据；未重新推理。真实直播、CUDA／WSL ROCm／AMF、系统重启与启动顺序仍待原有资格门槛 |

接口21组的结构化原始矩阵在 [manualQa.json](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/api/manualQa.json)，不能与真实原片、浏览器补充项目或旧单元测试数量相加。首次“任意崩溃均应自动暂停”断言是测试预期错误，原记录保留；普通导出崩溃保留此前 admissions 设置不单独计产品缺陷，接管时初始暂停仍是独立门槛。

## 两项未关闭问题

**F01：部分翻译误报整稿完成。** `backend/app/arctime/native_projection.py` 以“任一 cue 有译文”判定整稿 completed，done 使用全部 cue 数；工作台也添加“已完成”。应分别统计非空译文和总数，保留 partial，并避免把手工稿描述为真实供应商完成。复验需覆盖0／部分／全部译文、清空译文、保存重开及完整／切片下载。见[独立复现收据](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/api/partial-translation-count.json)。

**F02：历史高光信息投影丢失。** 无新处理操作的历史任务默认推导为 ranges，切片投影不携带旧评分及理由。应从已登记历史来源保留／读取模式与选择元数据；旧任务无新操作时不能推断人工切片。复验需覆盖人工／高光两类及新建／迁移两类，逐项比较模式、区间、评分、理由和源摘要。见[来源与投影对比](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/api/mode-fidelity.json)。原文件没有被删改，但兼容展示未达完整保真。

修复需产生新的候选身份并复测相关路径；本轮保留现有包用于复现，不把源码修复结果套用到旧包。工作站路径问题需明确来源根映射及恢复流程后重新准备，不能直接改正式 SQLite 或批量接管未知目录。

## 产物、隔离根与保护

真实片成品：[下载的 MP4](/Users/drm/Downloads/styled-b7144b15f36664c5539b.mp4)，4,707,200 字节，SHA256 `5da9e0e09ccbc9f04ce9db0af109c5f97c3ffbabf28944e535fbad17c81278f1`；H.264／AAC，1280×720、30fps、450帧，视频15秒、容器15.018秒。使用第2版稿件导出；后续编辑演练撤销后保存至第5版，没有声称旧成品自动更新为新修订。[2秒字幕帧](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/ui/real-burn-frame-2.png)及[最终核验](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023/final-browser-verification.json)保留。

| 用途 | 隔离目录及限制 |
| --- | --- |
| 冻结接口 QA | `/Users/drm/.cache/nyaru-clipper/historical-api-20261023-01`；新来源、新凭据，已写入为R2；不能对源副本直接解冻 |
| 真实原片／界面 QA | `/Users/drm/.cache/nyaru-clipper/historical-native-20261023-01`；第5版稿件、两项登记导出、队列暂停；使用目录内固定 runtime-recovery 与 guard；新域R2，不替代旧封存域 |
| 工作站失败准备 | `/Users/drm/.cache/nyaru-clipper/historical-workstation-20261023-02`；只登记来源，未激活；01为早期 QA Python版本不符留下的空目录 |
| 权威证据入口 | `/Users/drm/project/nyaru-clipper/.omo/evidence/historical-task-acceptance-20261023`；api／real／ui／remote 分别记录范围，包含早期测试预期错误与失败证据 |

五个原历史任务与真实原片的内容摘要、inode／mode／flags等清单前后相同；正式 App 数据元数据与开始基线一致，14个归档原片与既有清单摘要／大小一致。正式数据正文与凭据未全量读取。旧R2域、正式App和正式数据未切换，190个打包输入中的非文档文件摘要未变；App与冻结后端、reader身份核验一致。

自建候选及 helper 已停止；原生进程以SIGTERM结束，不能据此称为用户 CmdQ 正常退出。锁屏未解锁前不重试原生验收；后续显式启动仍必须传入绝对 runtime 与匹配 guard，不能双击默认入口。完成 F01／F02 及剩余平台资格前，本轮不支持正式切换或P6退役。
