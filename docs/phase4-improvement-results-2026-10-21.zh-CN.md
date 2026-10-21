# 第四阶段与累计验收结果

日期：2026-10-21。对应英文：[Phase-four and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase4-improvement-results-2026-10-21.md)。原始问题与独立关闭条件见[44 项改进计划](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.zh-CN.md)。

状态：五项已按 #39 → #11 → #28 → #38 → #42 实施、逐项验证，并与此前 18 项共同通过本轮累计验收。**最终 gate APPROVE、无阻塞项，codeQualityStatus WATCH；当前总账为 23 项在记录范围内已验收／21 项待处理。**见[最终审查](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/final-gate.md)。这不构成全平台发布验收。

## 修正与逐项验证

| 编号 | 当前行为 | 验证 |
| --- | --- | --- |
| #39 | 产物登记、legacy 与 v2 readiness 共用阶段／种类映射，识别实际写入的 `clip_export`；删除文件后两端均为 missing。 | 26 个回归、74 个相关测试，真实 SQLite／HTTP；独立 APPROVE。 |
| #11 | 手动导出单独记录运行与 export 阶段，不改写旧 canonical 历史；pending 调度保持原状。终态失败／恢复受持久归属约束，编码期间任务变化会拒绝发布。 | 82 个相关测试；真实 FFmpeg／API 201→400→201，失败保留旧 MP4；R1 修正后重新 APPROVE。 |
| #28 | 成功报告在验证执行身份、取消状态并写入终态后发布；失败诊断保留主异常。报告写入／登记／提交失败恢复旧输出，错误日志写盘失败不会阻断失败收尾。 | 84 个相关测试；真实 runner／报告下载；R28-1 修正后重新 APPROVE。 |
| #38 | 共享审阅组件按 taskId 重建局部状态，异步导出只刷新所属任务缓存。 | 21 个相关测试；真实浏览器缓存 A/B 切换、迟到导出、返回下载及 MP4 解码；独立 APPROVE。 |
| #42 | 来源检查的成功、失败和忙碌状态受来源类型、原始 URL、递增草稿代次约束，包含放弃后同 URL 重开。 | 32 个相关测试；真实浏览器切本地后迟到响应未覆盖，最终创建正确本地任务，放弃／重置／焦点通过；独立 APPROVE。 |

相关测试存在重叠，不累加为全量用例数。逐项红绿、diff 和审查位于[阶段证据目录](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21)。

## 当前累计证据

- 最终后端全量 **1107 passed**，0 failed/error/skipped；既有 Starlette 弃用警告保留。实际共享 downstream 入口为 **2 个后端 smoke、244 个前端测试、TypeScript／Vite build、17 个工作站浏览器测试通过**，退出码 0；2 个 smoke 与全量后端重叠。
- 固定 base／CUDA／ROCm 依赖导出检查通过；51 个基础依赖 pins 与预备环境一致，无依赖安装。默认 Chromium／指定 Chrome 各一个真实场景通过，显式 sandbox 保持开启；无效路径与零用例选择均预期失败，无浏览器回退。
- 当前 CPU Docker 镜像包含的 89 个应用 Python 文件与宿主源码哈希一致，新建／旧库迁移通过。宿主／容器真实 SQLite 锁竞争分别观测健康 200→503、任务 500→恢复 200；真实缓存内容替换／保留验证通过。
- 当前声明环境的 macOS App 构建、严格深度签名、冻结首页／jobs HTTP 200、合成 RS256 正反例均通过；8 个打包前端文件与当前 web/dist 一致，32 个构建依赖匹配。CLI／冻结 Companion 各 1 个 smoke 通过，5 个真实 Companion 页面流程通过、零页面错误、18 张截图。平台共记录 17 条最终命令退出码 0、22 个场景。#22 双磁盘故障／#23 损坏 receipt 的强条件由当前后端自动化验证；手动场景补充正常准入恢复／导出下载，不冒充手动故障注入。
- 完整结果见[平台实测报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/platform-qa/phase4-platform-manual-qa.md)、[23 项矩阵](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/combined-acceptance.md)、[根代理实测报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/manual-qa-report.md)。旧环境／夹具失败和两次审查阻塞的红灯均保留，不计为最终通过。测试服务已关闭，调用方 marker 保留，Docker Desktop 恢复本轮开始前的停止状态。

## 保留状态与限制

分支 `codex/code-improvement-2026-10-21`，HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`。全部修正保持未提交，未推送、合并或安装 App。473 个现有文件已备份；仅本轮授权源码／测试和配对文档发生变化，无缺失／意外修改。原 Companion 的 99 文件哈希保持一致，暂存区为空。未知 outputs、运行数据及原工作树均保留。

验收源码清单为 342 文件，SHA256 `ab7192754f3a9be450ff214668b3ff13f9b9d5564843952ac5a6b5d8aec66b0f`，见[冻结清单](/Users/drm/project/nyaru-clipper/.omo/evidence/phase4-workstation-output-consistency-2026-10-21/final-source-manifest.json)。HEAD 单独不能重建这些未提交修正。

本轮不构成 CUDA／ROCm／GPU 全流水线、真实 Bilibili／翻译／ASR 供应商、安装版原生退出、完整业务 Compose 或断电原子性验收。Python LSP／完整静态检查不可用，未安装；TypeScript 项目构建实测通过。#11／#39 的大测试模块维护债务保留为 WATCH。同步文件回滚依赖回滚文件系统操作本身可用。

当前剩余 21 项为：#13、#14、#15、#16、#17、#18、#19、#24、#25、#26、#27、#29、#30、#31、#33、#34、#35、#36、#37、#40、#41；本轮没有实施这些条目。
