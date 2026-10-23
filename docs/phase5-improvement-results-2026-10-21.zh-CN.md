# 第五阶段实施与累计验收记录

日期：2026-10-21。对应[英文记录](/Users/drm/project/nyaru-clipper/docs/phase5-improvement-results-2026-10-21.md)。

**第五阶段及28项累计验收完成，最终独立 gate APPROVE、无阻塞，维护债务 WATCH。**用户指定的 **#37 → #24 → #19 → #30 → #27** 已依序实现、逐项审查通过，并与此前23项重新累计验收。当前总账为 **28项在记录范围内已验收／16项待处理**。[最终审查](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/final-gate.md)。本文不代表44项全部关闭或全平台发布。

分支 `codex/code-improvement-2026-10-21`，HEAD仍为 `e8ea71085cf5c6ff6f671499872f5c166d31f89b`，全部修改未提交。保留进入本轮时的478个文件、218条Git状态记录及原Companion工作树99个源码哈希；本轮仅修改8个既有源码／测试文件，新增6个测试文件，另更新成对文档。未提交、推送、合并或安装App。

当前候选为348文件源码清单，摘要 `4547225959352daf71f62e6d934ab1a00dde2e79c2b464b75847d076275a4bb2`。完整证据根：[第五阶段证据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/ledger.md)，[源码清单](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/final-source-manifest.json)，[基线保护收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/preservation-final.json)。仅凭HEAD不能重建这些未提交修改。

## 本轮五项

| 顺序 | 改动与兼容边界 | 逐项验证 |
| --- | --- | --- |
| #37 | 来源身份只包含经校验的媒体／字幕／有效双语内容与时轴、画布、切片映射，排除运行诊断。可证明的旧v1指纹读取时规范化、显式保存时保留备份和revision/CAS；受控自动导出前保存内容绑定证明，覆盖旧稿未POST后诊断变更／重开窗口。 | 100项相关测试；独立审查APPROVE/WATCH、无阻塞，另17项；真实旧稿GET只读、失败／重试、独立进程访问与保存通过。 |
| #24 | 合并起点取最小值、终点取最大值，保持文字／样式／原顺序。 | 30项相关测试、构建与审查通过。真实页面改时间后合并为[0,8]，自动保存revision3、重载保留；0.5秒预览、ASS及烧录均显示两行。 |
| #19 | 先将总时长舍入到整数十分之一秒，再拆分；解析器规则不变。 | 68项相关测试、构建与审查通过。真实59.99／3599.99显示01:00.0／01:00:00.0；00:60.0仍拒绝，合法表单经实际HTTP／Pydantic解析为60／3600秒。此表单的摄取边界为替身，未下载视频。 |
| #30 | 切片文件约束从恰好三位改为至少三位，继续验证路径、任务归属、完成状态和哈希。 | 70项相关测试、审查通过；真实999／1000手动编辑稿ASS及自动ASS＋libass烧录均通过，备份／已保存稿保留。未实际录制千段。 |
| #27 | 仅ArcTime读取／验证ATPJ并纳入身份；ASS／烧录在HTTP与共用执行入口规范化无关工程字段，前端按格式发送。 | 123项相关后端、41项相关前端及构建通过；累计发现旧ASS请求断言，补充ASS省略／ArcTime保留断言后13项通过。独立审查APPROVE/CLEAR，真实切换／删除／无效工程、ASS／烧录缓存复用、ZIP内容和下载通过。 |

#37不会推测已经无法证明来源的旧opaque哈希。此类稿保留409与显式源稿恢复／重新应用／备份流程；不会按画布或时长相同自动放行。真正媒体／字幕／切片时轴变化仍拒绝；GET不偷偷重写原稿。

#27保留renderer_revision=2和既有不带工程的规范缓存。历史上错误纳入非空工程ID的ASS／烧录身份，首次规范请求可能生成一次新身份；旧receipt和产物继续按SHA校验下载，不将无法证明的旧缓存盲目别名到新源。当前规范请求切换或删除工程后，身份、SHA、mtime和登记数量保持不变。ArcTime仍拒绝损坏／删除／无效工程；工程字段为空的原有可选语义保持。

## 当前累计验证

| 验证入口 | 本轮实际结果 |
| --- | --- |
| 完整后端 | **1152 passed**，0失败／错误／跳过；JUnit与日志保存。 |
| 真实共享下游脚本 | **2个后端smoke＋285个前端测试＋TypeScript/Vite构建＋17个工作站浏览器用例**，exit0；2个后端smoke与完整后端重叠。 |
| 依赖与浏览器入口 | base／CUDA／ROCm三份导出一致，51个已安装基础pins匹配；默认Chromium／指定Chrome各1用例通过且保留显式sandbox；无效可执行路径和零用例选择按预期exit1。 |
| 真实工作站链路 | 实际FFmpeg、runner、SQLite与HTTP：导出201→失败400→重试201保护旧MP4，legacy／v2 ready→missing一致，成功／失败终态报告可下载；上游准备阶段及ML为受控替身。 |
| 根代理Companion | 实际浏览器编辑／保存／重载、时间边界、旧稿重开、999／1000、ASS／ZIP与真实libass烧录；0.5秒成片可见两行。 |
| 平台补充 | 20个最终命令exit0、25个surface／9个adversarial场景通过：CPU镜像89个后端文件匹配、迁移／锁健康／真实缓存；macOS构建／严格签名／冻结HTTP、8个前端文件与32个依赖匹配、RS256正反例；CLI／冻结smoke各1例，Companion五流程18截图、0页面错误、2次真实活动轮询。 |

[28项累计矩阵](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/combined-acceptance.md)逐项映射本轮证据。[根代理实测记录](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/manual-qa-report.md)、[退出码收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/qa-exit-receipts.json)与平台报告保留实际命令和限制。此前阶段结果仅作历史背景，不作为本轮成功收据。#22双磁盘故障、#23半写receipt由当前自动回归证明；正常浏览器流程不冒充这些故障注入。#38／#42本轮重新执行完整前端／工作站浏览器回归，第四阶段手动操作仍明确标为历史。

![当前真实烧录0.5秒两行字幕](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/browser-captures/27-merged-burn-at-half-second.png)

## 保留的失败与限制

本轮失败记录包括：旧ASS工程字段断言、早期夹具缺必需selection诊断、错误假设ASS单行、QA帧提取时间写为`.5`、重复创建模板，以及平台夹具的活动状态／刷新假设。均保留日志，修正夹具或合同断言后实际重跑；没有删测试、降低产品校验或将失败当成功。平台冻结检查准确记录仅一个获授权测试文件发生变化；产品、后端和打包dist的稳定性单独核验。

主路径仍为宿主机uv+pnpm，Docker仅CPU后备验证。未验收真实GPU／CUDA／ROCm流水线、外部供应商／真实登录、安装版原生窗口与退出、完整Compose业务部署、掉电原子性或完整字体／grapheme布局。LSP未安装且未擅自安装，不能将其计作静态诊断通过；实际tsc／构建结果另列。#37及此前模块大小／异常风格债务保留WATCH，性能和排版条目仍在待办范围。

本轮根代理与平台自有监听端口、容器和浏览器页已关闭，调用方父目录标记保留；Docker Desktop恢复进入本轮时的停止状态，镜像和缓存保留。[平台报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/platform-qa/platform-report.json)、[清理收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase5-subtitle-identity-and-export-boundaries-2026-10-21/cleanup-final.json)。

剩余16项：**#13、#14、#15、#16、#17、#18、#25、#26、#29、#31、#33、#34、#35、#36、#40、#41**。与已验收28项不重叠，合计44项。下一阶段需另行选择；本轮未扩大到这些条目。
