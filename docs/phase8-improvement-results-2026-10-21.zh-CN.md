# 第八阶段实施与44项累计验收记录

日期：2026-10-21。对应[英文记录](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.md)。

**#40 → #36 → #13 → #15 → #35 → #16 已依序实施、逐项验证，并与此前38项完成累计验收。总账为44项在记录范围内已验收／0项待处理；最终独立gate APPROVE、specCompliance PASS、无阻塞项，codeQualityStatus WATCH。**[最终复核](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/final-gate.md)独立核对355源码、115证据哈希、六项源链、九项删除及原生重开文件／截图。本文不构成全平台发布认证。

分支 `codex/code-improvement-2026-10-21`，HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`。既有未提交修改保留，暂存区为空；497文件基线、249条原状态路径、原Companion工作树99个源码哈希均受保护，只有明确授权的修正与九项删除。冻结355文件候选摘要为 `7702e7f6e0c23172326dc62ddd604729b09062c27a299d94404808c77410fae4`，仅凭HEAD不能重建当前修改。[源码清单](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/final-source-manifest.json)、[源码链](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/source-chain-check.json)、[最终保护收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/preservation-final.json)。

## 六项结果

| 顺序 | 实际修正 | 验证与边界 |
| --- | --- | --- |
| #40 | SSE固定窗口合并刷新，任务ID去重；刷新前取消旧请求，全部相关查询传递AbortSignal，清理卸载／断线状态。 | 103项相关与构建通过、独立APPROVE。真实Vite／FastAPI／SQLite／SSE两窗口每key共2请求，实际ERR_ABORTED；API中断重启后从cursor714回放100事件715–814，最终标题可见、0页面错误。 |
| #36 | 通用编码器只接受不可变三字段配置；两个真实调用方分别适配。公共命令日志实现移到标准库模块，移除间接ORM／DB／事件导入。 | 188项相关、审查独立14项通过；真实CPU编码、AMF未配置回退及源文件保护通过。最终App内冻结后端实际HTTP202恢复→内置FFmpeg导出→200下载／SHA／2秒probe与解码通过；未声称AMF硬件验收或依赖缩减。 |
| #13 | 完整字幕稿以内容寻址不可变快照保存，列表／历史只保留引用；小型活动记录独立写入，产物与receipt完整性及旧格式读取保留；空闲导出停止轮询，手动／父任务自动活动可唤醒。 | 127后端／75前端及独立审查通过。实际5000条字幕／20产物／ASS、烧录、ZIP仅1份973,753字节快照；列表19,499,073→25,733字节，10次进度写入309,008,591→901字节，registry SHA不变。20下载SHA、真实烧录解码、浏览器空闲与两种唤醒通过。 |
| #15 | 正常直播追加只检查新增／变化片段；翻译部分成功、失败重试及模板改变保留明确脏集合。启动／恢复仍完整校验，不信任持久化下载状态。 | 176项相关／55项回调消费者通过，生产与测试修订分别独立APPROVE。N=20／40／80实测检查40／80／160次，历史输入／产物重访均0；真实4次烧录、尾片／断点／恢复解码通过，两个独立生产CLI会话各8份SHA下载，损坏409／恢复200。线性结论仅覆盖样式检查与哈希。 |
| #35 | 先迁移有效ASR／发布／进程故障断言，再删无消费者旧入口、非结构化执行器、cleanup及无效配置／orjson声明。现用推理、manifest、发布和结构化回退保留。 | 68基线→迁移后71→退役后220相关／40工具检查，三profile导出检查及独立11项通过。14路径清单含两个有原文及理由的删除记录。基础依赖只移除orjson，其余pins／锁记录保持，GPU导出字节不变。模型推理使用替身。 |
| #16 | 六个共享审核测试完整迁移到有效入口；真实AppRouter补9场景；终态残留进度经3例真实红灯后增加一行running守卫。删除4死模块及3旧专属测试。 | 删除前172／后153项、tsc／Vite及独立19项通过。实际生产API浏览器30状态／宽度／系统主题组合，150 PNG哈希核对、两份限定视觉复核PASS。当前路由、共享审核、legacy API／types、能力组件与有效测试保留。 |

#13发布路径 `media.write_json` 另计443,914字节，只是被代理的JSON写入，不能冒充全部文件系统写入或生产耗时加速。#15原先过度耦合具体计数的测试经fresh审查后改为独立历史访问观察及工作上限，旧代码真实重访反例保留。#16旧 `cancel_requested` 页面断言因v2合同无法产生该状态而明确退役，没有伪造产品功能；六个保留审核body逐字等价。[完整44项矩阵](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/combined-acceptance.md)记录每个ID的独立证据与限制。

## 最新原生App实际保存、退出与重开

使用最终候选新构建的[原生App](</Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/platform-qa/macos-clean-build/Nyaru Clipper.app>)，Application Support隔离到自有测试目录，未替换安装版或操作用户工程。实际原生窗口编辑两个任务，通过自有revision冲突保持两份草稿未保存；当前选中B，A未选中。恢复夹具原revision后，在原生退出提示点击“保存并退出”。A从8→9版、B从1→2版，B完整保存5000条，其余4999条与保存前精确相同。

重开同一App二进制后，在实际原生窗口分别看见A的 `P8-A保存`／第9版和B的 `P8-B保存`／第2版／5000条。随后正常退出；两次native／helper进程、端口和ready文件均关闭，旧日志前缀及两次启动标记保留。二进制SHA为 `b7e5e0306fe9e44d413d6d9c916d46e5d2b60437187d3763cb46246e7f2d819f`。[原生QA](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/native-qa.md)、[绑定当前候选的收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/native-current-acceptance.json)、[A重开画面](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/native-A-reopened.png)、[实际保存退出提示](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/native-save-quit-alert.png)。

![最新原生App重开后，B显示已保存第2版、5000条及实际编辑文字](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/native-B-reopened.png)

## 当前累计检查

| 入口 | 当前结果 |
| --- | --- |
| 完整后端 | **1357 passed，0失败／错误／跳过**；一条既有Starlette/httpx弃用警告。 |
| 真实共享下游入口 | **327前端测试、tsc／Vite、17个工作站浏览器用例**及2个重叠后端smoke通过；不重复相加。浏览器部分使用HTTP替身，真实生产HTTP由专门场景补充。 |
| 依赖／浏览器合同 | 正常三profile生成检查通过，50基础已安装pins匹配；默认Chromium／指定Chrome实际启动，无效路径无回退／零选择按预期失败。sandbox仅由证据包装开启，产品配置不改。 |
| 平台 | **22/22最终命令exit0**。当前CPU Docker镜像89个app文件一致，新旧库迁移及宿主机／容器SQLite锁200→503→200通过；复用并重新验证macOS严格声明环境33分发包／10直接需求，无额外包或差异。当前App构建／严格签名／8 web资源／冻结HTTP／合成RS256／真实冻结导出通过；CLI／冻结smoke各1例，5个Companion浏览器流程通过，363源码／资源无漂移。 |
| 真实媒体／API／原生补验 | 旧9产物及9 receipt SHA保留；失败编码／重试、报告及容量、5000条活跃帧预览、八行PNG／ASS／烧录、上传inode零复制、601.25秒分块批次单次扫描及11,250,045字节日志有界只读通过。实际最新原生双任务保存退出重开通过。 |

[平台报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/platform-qa/platform-report.json)、[原始命令退出收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/platform-qa/qa-exit-receipts.json)、[gate输入检查](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/gate-input-checks.json)、[115份冻结证据清单](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/gate-artifact-manifest.json)保留当前观测。此前手动流程在矩阵中明确标为历史，由当前全量回归、源码保护和本轮真实补验支持累计结论，不声称38项旧手势全部重播。

## 限制与交接

原生窗口要求已实际完成；未验收真实GPU／CUDA／ROCm／AMF、模型推理、外部供应商／登录、完整Compose、掉电、全部字体或长时间直播。#16视觉范围仅是条件进度区域；既有1280px最小宽度导致手机裁切、固定浅色及字号问题保留WATCH，未认证全站响应式／深色／HIG／AA。名为end的截图是聚焦后稳定画面，不是页面底部滚动证据。

保留全部失败验收尝试：冻结后端直接SIGTERM的ready清理假设改为正常SIGINT重跑，手机首次错误裁切改用文档坐标／DPR重拍，均未改产品或削弱守卫。LSP不可用、TS7专用检查不兼容现有TS5，实际项目tsc通过；模块体量／风格、一个非阻塞活动写入计数测试耦合、pnpm／ReactRouter警告及既有 `db_migrations.py:107` 末尾空行均保留WATCH，不声称lint／格式全绿。

原始中英各44问题块保持字节一致；已审gate输入另存 `gate-reviewed-input`，本次只派生接纳状态与文档。[最终文档及保护检查](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/acceptance-final.json)记录发布后的核对。主路径仍为宿主机uv＋pnpm，Docker为备用；没有宿主机依赖安装或模型下载，Docker自有构建按声明安装镜像依赖。未提交、推送、合并、替换安装版App或写入记忆。自有资源关闭、Docker恢复原停止状态，[资源收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase8-final-six-performance-and-retirement-2026-10-21/resources-final.json)。44个编号均已在上述范围闭合，无下一批待处理条目。
