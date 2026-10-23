# 候选 App02：历史任务修复与复验

日期：2026-10-23（Asia/Shanghai）。本轮两项修复 **completed，限定本机复验 accepted**；不是正式发布、全平台验收或正式数据切换。对应[英文](candidate-fixes-2026-10-23.md)。

## 修复范围与兼容性

| 问题 | 修订位置 | 最终行为 |
| --- | --- | --- |
| F01 部分译文误报完成 | `backend/app/arctime/native_projection.py` | 列表与详情均按保存文档中非空译文计数；0 条为 not_started，部分为 partial，全部非空才 completed。显示“已保存译文 n/N 条”；清空后撤掉旧双语下载，不把手工编辑说成供应商翻译完成。 |
| F02 历史高光元信息丢失 | 同上；新增 `backend/app/arctime/migrated_selection.py` | 从当前绑定组、代际和已激活成员登记的归档 job.json 恢复模式、评分、理由与范围。校验候选及 job.json 摘要和范围；损坏时沿用来源不可用错误，不改历史数据。 |
| 回归证据 | 新增 `backend/tests/test_unified_projection_regressions.py` | 覆盖列表／详情、空白／部分／全部／清空、手动／高光、跨批次同代际成员、归档篡改和文档兼容性。 |

未改数据库、WorkstationArtifacts 格式或指纹、历史文档格式；没有增加依赖。实现位于独立工作树，HEAD 为 `428ba833193db888c6b049ac2983abe1b2ecae17`，已有大量未提交改动，不能仅靠 HEAD 重建本包。[构建输入清单](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/source-input.json)记录准确字节；本轮产品修改仅上述 3 文件。

有效旧实现反例为 **6 failed／2 passed**，修复后专项 **8 passed**；相邻后端 **82 passed**（已含这 8 项），前端 **332 passed／40 文件**，打包内 TypeScript／Vite 构建成功。[专项与回归日志](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/receipt.md)。独立代码审阅 APPROVE、无阻塞；唯一非阻塞的无效同对象指纹断言已删除，保留真正的独立指纹与文档读回断言。未运行新一轮全量后端或 LSP。

## 新包身份

显示版本仍是 0.1.19／build 27，必须按路径与摘要识别。Apple Silicon macOS 候选，严格 ad-hoc 签名通过；未公证。

| 交付 | SHA256 |
| --- | --- |
| [候选 App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-02/Nyaru-Clipper-unified-candidate-20261023-02.zip)（633640976 字节） | `914e36a0b7cf97ad864cedf9d87abfcfcb1b0ae76248b5ec5da2eb7272eff14b` |
| [独立恢复 ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02.zip)（98611249 字节） | `31e364935d925993b6a849d8c1f7df21b325731c29a39e3e298774153a339c42` |
| 原生可执行文件 | `c978b378058e073e2a58f1478bb3d184ab08256daa4e35e53593dbb02ef1ffd4` |
| 冻结后端 | `e75a50f2e31f166e5a4661bb7016e287ffb46f290811ea15108d03bb0f294d5e` |
| App 内／独立恢复 bundle.json | `52342c6a998c6241a5381db6a778bb792ae38a0e197989d166da79da73016b54` |

App 5407 文件、恢复包 3620 资源（151 个 legacy Python 模块）逐项校验；ZIP CRC、解包内容与权限、原包／解包签名、独立解释器与 reader 入口通过。恢复包固定目录为 `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-02`，不得移动或替换已登记 reader pin。详见[包身份](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/artifacts.json)。

## 实包验收矩阵

| 验收 | 结果与边界 | 证据 |
| --- | --- | --- |
| 五份历史任务副本 | **25/25 场景组 PASS**；同一 20.4 秒 Tingting／FFmpeg 合成源，三手动、两高光，不能当真实录音验收 | [矩阵](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/packaged/manualQa.json)、[311 引用独立审计](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/packaged/independent-artifact-audit.json) |
| F01 | 列表及详情：初始 0、纯空格 0、1/2 partial、2/2 completed、清空 0；清空双语文件返回 404，CAS 409 不覆盖，重开保留 | [历史副本报告](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/packaged/historical-fixes-manual-qa.md) |
| F02 | 全五任务的模式／范围／分数／理由在初始、编辑、导出、重开四轮一致 | 同上 |
| 周边功能 | 库搜索／标签／归档／分页、字幕历史／CAS／SRT／VTT、模板 CAS、设置序列保存与读回、队列、预览、ASS、ArcTime ZIP、CPU 烧录通过；设置本身无公开 CAS，不作该项声明 | 同上 |
| 崩溃与重试 | 运行中导出 SIGKILL → interrupted；重开不自动重试；显式 attempt 2 完成并完整解码。6 秒视频轨，AAC 容器 6.037 秒 | 同上 |
| 真实 150 秒原片 | 新任务 `ad3ad70afddf5287b5d1b4f797665a2a`：实际打包 whisper.cpp 识别 21 条，首末两条明确手工 QA 译文，列表／详情 partial 2/21；原片、切片完整解码，PNG／ASS 通过 | [真实原片报告](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/real/historical-fixed-real-manual-qa.md) |
| 原生 App | WKWebView 播放时间 0→3→10 秒；保存第 2 版，CmdQ 后按原隔离参数重开保留。界面提交真实 15 秒烧录并经 NSSavePanel 保存，登记产物与保存文件 SHA 相同，完整解码通过 | [原生收据](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/real/native-verification.json)、[成片](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/real/native-saved-burn.mp4) |
| 独立恢复 | 原生验收后暂停队列、停止 App/helper，六根 immutable 封存；新恢复包只读导出 3 份文档，无错误，真实任务第 2 版 21 条／2 条译文一致 | [R2](/Users/drm/.cache/nyaru-clipper/historical-fixed-native-20261023-01/R2/complete.json)、[最终审计](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/final-audit.json) |

原始失败记录全部保留：初轮脚本使用 tab／换行被现有校验拒绝，其依赖计数随之失败；随后改用合法空格并按实际历史版本复验。原生保存面板的路径输入未导航，完整路径被当作冒号文件名保存到旧 fixture；只将本次新生成文件移入证据目录，未替换旧文件。以上属于验收操作修正，不曾放宽产品校验。

## 保护边界与接手方式

正式 App 完整内容／元数据、正式数据元数据与构建前一致；未声称正式数据全文哈希。五份原始历史任务与既有四轮保护基线一致，真实原片与本轮选用的原任务哈希／元数据一致。未替换正式 App、未切换正式数据、未连接远端、未提交／推送／合并。

新域 `historical-fixed-api-20261023-01` 和 `historical-fixed-native-20261023-01` 使用新 source UUID 与 App02 reader pin，旧 App01／恢复包／保护域／epoch 保留。所有自建后端、原生 App/helper 已停止，队列暂停。真实域六根与新 R2 已封存；**不直接重开／解封／thaw 此 R2**，只读恢复入口与精确 argv 留在收据。下一次可写测试需按恢复规程建立独立新域，不能重绑旧 reader pin。

任何候选启动必须显式传绝对 `--unified-runtime` 与匹配 `--migration-guard`；不要双击候选 App，以免落入默认正式路径。此文中的 runtime 仅供定位封存证据，不是可写启动指令。正式 App 无需回退；本轮候选停止、保留新数据与包即可，不能用旧包覆写新文档或正式数据。

[上轮 App01 验收失败](/Users/drm/.codex/worktrees/unified-architecture/nyaru-clipper/docs/historical-task-acceptance-2026-10-23.zh-CN.md)继续作为历史事实。本轮未重新完成 App02 的 R0／R1 解冻、完整 M03／M24 平台资格；此前结果不自动升级为新包资格。M24 系统重启／开机保护、CUDA／WSL ROCm／Windows AMF、真实直播与外部翻译服务仍待验收，P6 与正式切换仍未启动。语义准确率、ArcTime GUI、公证也未验收。

![候选 App02 重开后仍为已保存译文 2/21 条](/Users/drm/project/nyaru-clipper/.omo/evidence/historical-fixes-20261023/real/native-reopen.png)
