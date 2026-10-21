# 第七阶段实施与累计验收记录

日期：2026-10-21。对应[英文记录](/Users/drm/project/nyaru-clipper/docs/phase7-improvement-results-2026-10-21.md)。

**第七阶段及38项累计验收完成，最终独立gate APPROVE、specCompliance PASS、无阻塞项，维护债务WATCH。当前总账为38项在记录范围内已验收／6项待处理。**用户指定的 **#17 → #25 → #14 → #18 → #34** 已依序完成，并与此前33项累计验收。[最终复核](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/final-gate.md)独立核验355源码／316证据哈希、完整顺序链及实际原生重开证据。本文不构成全平台发布验收。

分支 `codex/code-improvement-2026-10-21`，HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`。保留原有未提交修改；492文件基线、236条原Git状态记录、原Companion工作树99个源码哈希保护检查通过，暂存区为空。未提交、推送、合并或替换安装版App；主路径仍为宿主机 `uv + pnpm`，Docker为备用路径。

冻结候选355个源码／测试／配置文件，清单摘要 `66915d94be21716ff22c32c15b68804f0fee0acbda1e0bd9021921d843bc0f88`。有序差异链记录五项修正，以及视觉复核后仅增加原生破坏性按钮标记的 `25/visual-fix` 补丁。[源码清单](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/final-source-manifest.json)、[源码链](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/source-chain-check.json)、[保护收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/preservation-final.json)。仅凭HEAD无法重建当前未提交修正。

## 五项结果

| 顺序 | 修正与边界 | 验证 |
| --- | --- | --- |
| #17 | 原生日志打开后定位末尾，保留旧内容并追加helper输出；不引入日志轮转。 | 2个真实Foundation红灯→29项相关通过，独立APPROVE/CLEAR；实际旧App复现截断，新App启动／退出／重开保留标记与真实stderr。最新完整候选重复启动亦保留。 |
| #25 | 原生退出先协商全部字幕会话，包括未选中任务；仅保存成功且无脏状态，或用户明确放弃，才停止helper。冲突／验证／网络／桥未就绪时保留窗口，保存中可取消退出；默认设置需先单独保存。 | 47项相关前端及构建、测试夹具修正后的mutation红灯／9项hook通过，独立APPROVE/CLEAR。旧版反例＋8个修后实际原生场景；最终候选再次完成双任务真实Save→退出→重开。视觉发现放弃按钮样式后单行补充AppKit destructive角色，真实AppKit红灯→7项通过及Swift类型检查，独立复审APPROVE/WATCH。 |
| #14 | 仅应用拥有、身份匹配、同文件系统的上传暂存允许原子转移；外部原片保持复制。跨文件系统明确拒绝整片复制回退，清理不删除身份不符文件。 | 159项相关通过，独立APPROVE/CLEAR；两版真实HTTP上传均202完成，保留inode、0次整片复制、SHA一致，4秒媒体ffprobe／FFmpeg导出解码通过；外部原片仅复制1次，原inode与SHA不变。 |
| #18 | 显式批次合并重复容量扫描，计入整个托管任务目录；既有报告／导出覆盖后更新容量。备份删除后的校准与task.updated同事务，失败不泄漏事件或提交调用方其他修改。 | 214项相关通过、最终独立review3 APPROVE/WATCH；真实601.25秒PCM经FFmpeg分3块，新建／缓存每批各1次扫描、5产物及5ready事件ID稳定，未登记文件计入且保留。当前真实报告／导出覆盖后数据库容量与目录实测一致。 |
| #34 | 路径查询不建目录，创建集中到明确写入／启动入口；初始化默认根的回退仍与后续读路径一致。日志摘要最多尾读65536字节，丢弃首段不完整行并保留脱敏边界。 | 28项红灯→289项相关通过，独立60项通过、APPROVE/WATCH；真实11,250,045字节日志两次摘要合计读131072字节。两版API禁止mkdir时正常读取，目录不变；任务目录缺失后不重建，产物404。外部路径／符号链接拒绝和UTF8／超长行／部分凭据边界通过。 |

#18初审发现覆盖备份删除后容量高估（H18-1），复审发现容量校准后缺少刷新事件（M18-2）；均保留旧审查／失败证据，经真实红灯修复后重新独立审查。若备份清理后的校准事务自身失败，保留警告与保守高估值，下一次成功发布／校准恢复；没有新增无限重试。#34原始legacy `summary`仍遵循原接口合同，`safe_summary`及v2继续脱敏，不能将所有原始日志字段称为已去敏。

## #25实际原生验收

使用证据目录中单独构建的App，实际Foundation Application Support隔离在 `native-home`，未触碰安装版或用户工程。先载入两个任务，再通过受控revision冲突让两份编辑同时保持未保存；恢复自有夹具原revision后点击原生“保存并退出”。当前选中A从10→11版，未选中、含5000条字幕的B从1→2版；其余稿件字段与字幕保持。窗口、native/helper进程、端口和ready文件全部关闭。重开同一构建后，两份编辑均在实际原生窗口显示已保存，随后正常退出并确认资源关闭。

[最终原生收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/root-native-final.json)绑定355源码、同一App二进制及24个证据哈希；[此前九场景](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/root-native25.json)明确保留冲突、取消、进行中取消、关闭最后窗口、明确放弃、干净退出及桥未就绪边界。进行中取消的实际传输最后为 `Load failed`；迟到成功保存仅有自动回归，未冒充手动观测。无法确认编辑器状态时的提示截图被工具缩小，像素级验收明确受限；完整无障碍文本和失败保留行为另有证据。

![最终原生App重开后，第一个任务显示第11版及实际保存文字](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/native-final-reopened-A.jpg)

[第二个5000条任务重开后第2版画面](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/native-final-reopened-B.jpg)、[最终原生退出提示](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/native-final-quit-prompt.jpg)显示安全保存、取消与红色放弃动作。两名限定原生视觉复核者均APPROVE、无产品阻塞；未观测的键盘／动态、同版本主题配对等仍受限，不构成全面HIG认证。

## 本轮累计检查

| 入口 | 实际结果 |
| --- | --- |
| 完整后端 | **1329 passed**，0失败／错误／跳过，一条既有Starlette/httpx弃用警告；补充原生角色回归前的1328项结果也保留。 |
| 真实共享下游 | **2个后端smoke＋317个前端测试＋TypeScript/Vite构建＋17个工作站浏览器用例**，exit0；smoke与完整后端重叠，不相加重复统计。 |
| 依赖／浏览器 | 三profile导出检查通过、51基础已安装pins匹配；默认Chromium、指定Chrome实际启动，无效路径无回退、零选择均按预期exit1。sandbox由证据专用配置明确开启，产品配置不变。 |
| 实际工作站／Companion | FFmpeg／SQLite／HTTP导出201→失败400→重试201、旧MP4保留，ready→missing一致，成功／失败报告可下载；旧稿独立进程重开不改原稿、九个历史产物下载SHA保持，八行PNG／模板／ASS／烧录和5000条活跃帧预览通过。上游ML为受控替身。 |
| 平台补充 | **21/21最终运行命令exit0**；CPU镜像89个app文件一致，全新／旧库迁移、宿主机／容器锁健康与真实媒体缓存通过。复用并重新核对上一轮隔离的macOS声明环境33分发包／10直接需求；当前App构建、严格深度签名、冻结HTTP／8个web资源、合成RS256正反例，CLI及冻结smoke各1例通过。5个实际浏览器流程、18截图、0页面错误。363个源码／资源无漂移。 |

[38项累计矩阵](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/combined-acceptance.md)、[根代理真实QA](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/manual-qa-report.md)、[平台报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/platform-qa/platform-report.json)、[平台退出收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/platform-qa/qa-exit-receipts.json)逐ID列出当前证据与限制。此前手动操作仍标为历史，本轮全量回归与受保护源码重新核对；不声称此前33个手动流程全部重播。

## 限制与交接

保留浏览器筛选错误／遗漏sandbox QA配置、平台内容检查早于Docker哈希依赖完成等失败日志，修正验收编排后真实重跑，未修改产品守卫或削弱有效断言。未知状态低清图片、陈旧截图辅助闭包产生的错误窗口记录明确排除通过结论。`git diff --check`报出 `db_migrations.py:107` 一个末尾空行，来自#18函数抽取；属于已记录的格式WATCH，不能声称差异检查全绿。

未验收真实GPU／CUDA／ROCm、供应商／登录／ASR模型、完整Compose、掉电、所有字体及安装版升级。原生窗口保存／退出／重开已对本轮隔离构建实际验收。LSP缺失且未擅自安装；既有模块体量、错误风格及测试锚点维护意见保留WATCH。自有资源已关，Docker恢复初始停止状态，镜像、夹具和证据保留。[清理记录](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/root-cleanup.json)、[Docker恢复](/Users/drm/project/nyaru-clipper/.omo/evidence/phase7-data-preservation-and-io-boundaries-2026-10-21/docker-restoration.json)。

累计已验收38项：**#1、#2、#3、#4、#5、#6、#7、#8、#9、#10、#11、#12、#14、#17、#18、#19、#20、#21、#22、#23、#24、#25、#26、#27、#28、#29、#30、#31、#32、#33、#34、#37、#38、#39、#41、#42、#43、#44**。剩余6项：**#13、#15、#16、#35、#36、#40**。两组互斥并覆盖44项，原问题及独立验收条件保持。复核输入中的总账与保护收据原件另存于证据目录的gate-reviewed-input，接纳状态与文档派生检查单独记录，测试及产品证据不改写。
