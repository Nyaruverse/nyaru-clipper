# 八阶段累计修改与提交交接

日期：2026-10-21。对应[英文](/Users/drm/project/nyaru-clipper/docs/code-improvement-rollup-2026-10-21.md)。

**原44项问题已完成八阶段修正，并在记录范围内累计验收44／44、待处理0项。最终独立gate APPROVE、specCompliance PASS、blockers=[]，维护债务WATCH。**本次将验收对应源码／直接测试／必要配置与成对文档提交到 `codex/code-improvement-2026-10-21`，暂不合并或推送。历史记录中的“未提交”限于当时；本次提交范围以本文及Git记录为准。

## 八阶段总账

| 阶段 | 实施顺序 | 累计已验收／待处理 | 记录 |
| --- | --- | --- | --- |
| 1 | #1–7、#20、#21 |9／35| [第一阶段](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.zh-CN.md) |
| 2 | #32 → #43 → #44 → #12 |13／31| [第二阶段](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.zh-CN.md) |
| 3 | #22 → #23 → #8 → #9 → #10 |18／26| [第三阶段](/Users/drm/project/nyaru-clipper/docs/phase3-improvement-results-2026-10-21.zh-CN.md) |
| 4 | #39 → #11 → #28 → #38 → #42 |23／21| [第四阶段](/Users/drm/project/nyaru-clipper/docs/phase4-improvement-results-2026-10-21.zh-CN.md) |
| 5 | #37 → #24 → #19 → #30 → #27 |28／16| [第五阶段](/Users/drm/project/nyaru-clipper/docs/phase5-improvement-results-2026-10-21.zh-CN.md) |
| 6 | #26 → #31 → #29 → #41 → #33 |33／11| [第六阶段](/Users/drm/project/nyaru-clipper/docs/phase6-improvement-results-2026-10-21.zh-CN.md) |
| 7 | #17 → #25 → #14 → #18 → #34 |38／6| [第七阶段](/Users/drm/project/nyaru-clipper/docs/phase7-improvement-results-2026-10-21.zh-CN.md) |
| 8 | #40 → #36 → #13 → #15 → #35 → #16 |44／0| [第八阶段及最新累计证据](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.zh-CN.md) |

各组互斥覆盖1–44；原中英44项问题块及独立验收条件保持字节一致。第一阶段970通过／1环境失败是历史状态，第二阶段已修复解释器和发布入口；不同阶段／重叠测试不能相加为独立总用例数。

## 累计修改

- 数据保护与恢复：凭据脱敏、异常进程组回收、缓存内容／参数身份、原子成片及失败回滚、翻译／receipt发布恢复、队列终态与重试事务、旧字幕稿兼容。
- 编辑与输出：任务／草稿归属、字幕合并与时间范围、高光padding、格式专属缓存、Unicode换行与溢出拒绝、命名冲突、报告及产物就绪投影。
- 有界开销：上传原子转移、批次容量扫描、只读路径与尾部日志、活跃帧预览、不可变导出快照／小型进度写入、增量直播样式检查、SSE刷新合并与请求取消。
- 平台与维护：依赖闭包、三profile固定版本生成、Docker迁移、数据库readiness、真实smoke及浏览器选择、通用编码解耦；迁移有效断言后退役无消费者ASR／执行器／旧页面。
- 原生生命周期：日志追加、全部字幕会话退出前保存、最新候选实际保存／退出／同构建重开。

按此前授权纳入Companion现有源码基线，承载#5／#6及后续Studio／字幕／原生修正，不将基线冒充本计划新增功能。原Companion99哈希保持；源码、直接测试和平台配置作为共同验收候选提交，文档单独提交。

## 最新验收与可携带记录

冻结候选355文件，摘要 `7702e7f6e0c23172326dc62ddd604729b09062c27a299d94404808c77410fae4`，原审阅HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`。本次未改验收后的产品源码；提交前重新核对全部候选哈希、115份gate证据及原问题块，沿用同一候选的实际结果，不冒充重新运行完整套件。

| 入口 | 最新记录及边界 |
| --- | --- |
| 完整后端 |1357通过，0失败／错误／跳过；既有Starlette/httpx警告。 |
| 真实共享下游 |327前端、TypeScript／Vite、17工作站浏览器及2个重叠后端smoke通过。部分浏览器HTTP为替身，真实生产HTTP／媒体场景另补。 |
| 平台 |22／22命令通过；CPU Docker89个app文件／8 web资源／363源码资源无漂移；macOS33分发包／10直接依赖；三profile检查与50基础pins匹配。 |
| 实际最新原生App | 两份草稿均脏、A未选中；原生保存并退出后A8→9、B1→2。同一二进制重开窗口显示两份保存文字；B5000条完整、其余4999条精确相同；两次进程／helper／端口／ready均关闭。 |
| 保护 |497文件阶段八基线、249原状态路径、C99保护通过；九项删除保留原文／理由和有效断言迁移。 |

[版本化验收摘要与355文件清单](/Users/drm/project/nyaru-clipper/docs/validation/code-improvement-acceptance-2026-10-21.json)保留八阶段编号、44项矩阵、最终结果及报告哈希，不含原始日志、数据库、媒体或凭据。原始证据仅存被忽略的 `.omo/evidence/`；阶段文档中的本机证据链接不会随clone携带，提交摘要不是完整原始证据备份。

## 提交边界与限制

纳入相对原HEAD变化的最终候选源码／直接测试／声明配置／构建与发布脚本、九项删除、原改进计划、八阶段双语结果、第二阶段成对计划、部署／运维变更及本汇总。测试源码与413字节人工grapheme夹具是可重跑输入，不是测试产物。文档索引只暂存本次改进条目，其他既有索引差异留在工作区。

排除并原地保留运行data、原始.omo证据、环境／依赖目录、dist、测试报告／trace／截图、临时库／ready／日志、App包、媒体／字幕输出、密钥／Cookie／授权配置、.DS_Store和outputs。旧交接、此前功能说明／历史验收文档、含占位值的 `web/pnpm-workspace.yaml` 不提交。明确路径暂存并检查候选文本／暂存blob的敏感模式，只记录位置和分类，不输出秘密值。不删除排除项，不替换安装版App或操作用户业务数据。

真实GPU／CUDA／ROCm／AMF、模型／供应商／登录、完整Compose、掉电、全部字体、长时直播及全站响应式／深色／HIG未认证。既有模块／类型债务、非阻塞活动计数耦合、工具警告保留WATCH。暂存检查覆盖此前未跟踪文件，显示 `db_migrations.py:107` 及 `test_subtitle_identity.py:216` 两处末尾空行；两文件均与已验收候选／阶段八基线一致，未改源码，也不声称格式全绿。主路径为宿主机uv＋pnpm，Docker备用；不合并、不推送。
