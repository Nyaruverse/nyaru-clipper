# 第六阶段实施与累计验收记录

日期：2026-10-21。对应[英文记录](/Users/drm/project/nyaru-clipper/docs/phase6-improvement-results-2026-10-21.md)。

**第六阶段及33项累计验收完成，最终独立 gate APPROVE、无阻塞项，维护债务 WATCH。当前总账为33项在记录范围内已验收／11项待处理。**用户指定的 **#26 → #31 → #29 → #41 → #33** 已依序实施、逐项验证，并与此前28项重新累计验收，不以历史绿灯代替本轮结果。[最终复核](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/final-gate.md)。本文不构成全平台发布验收。

分支 `codex/code-improvement-2026-10-21`，HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`。修改均未提交；已捕获486文件基线，保护检查仅允许本轮授权改动，226条原Git状态记录和原Companion工作树99个源码哈希保持，暂存区为空。未提交、推送、合并或安装App；主路径仍为宿主机 `uv + pnpm`，Docker为备用路径。

冻结候选包含352个源码／测试／配置文件，清单摘要 `4f13f6e4038e6f1d7d17cd9a7e7ad13f57302bb573e755df3e7a2e0836539eaf`。五项的有序before/after链覆盖33个不同清单路径，包含只核对未改动的导出文件，不能解读为33个文件均被修改。[源码清单](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/final-source-manifest.json)、[基线保护收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/preservation-final.json)。仅凭HEAD无法重建这些未提交修正。

## 本轮五项

| 顺序 | 修正与兼容边界 | 逐项验证与真实入口 |
| --- | --- | --- |
| #26 | 从当前实际媒体重新ffprobe取可信时长；已知时长才补边并钳制，未知时长保留原场景范围并明确为null，不再冒用字幕或镜头终点。空字幕列表保持正常无候选。 | 24项红灯→117项相关通过，独立APPROVE/WATCH。实际60秒媒体、字幕20秒结束、场景10–30，页面显示并提交8–32；下载MP4为24秒且完整解码。场景／字幕／能量输入为合成夹具。 |
| #31 | CLI与GUI共用供应商／模型解析：任务固定值优先，否则当前配置；下载前固定选择，残留DeepSeek Key不覆盖当前ChatGPT设置。非LLM普通任务不因可选配置损坏而被拒绝。 | 审查R31-1经4项红灯修复，192项相关通过、独立复审APPROVE/WATCH。实际CLI新建／resume、GUI HTTP、真实SSE解析器的合成响应验证；普通任务202、需LLM任务409。未连接真实供应商。 |
| #29 | Python `regex`的`\X`与浏览器`Intl.Segmenter`保持完整grapheme；显式换行、文字顺序、强调codepoint坐标保留。声明直接依赖`regex==2026.7.10`并核对冻结闭包。 | 97项相关后端／36项前端、构建与三profile导出检查通过；独立APPROVE/CLEAR。真实libass的ZWJ、旗帜、重音、肤色样例与显式整簇换行像素一致。QA字体未安装或打包。 |
| #41 | 基础、高级、文档入口共用自动布局与横纵溢出判定，前端同步；双语、隐藏、逐条样式及旋转覆盖，自由坐标保留独立语义。 | R41-1横向漏检经3后端＋3前端红灯修复，最终120后端／43前端与构建通过，独立复审APPROVE/CLEAR。实际120字号八行各入口拒绝；64字号预览／模板／ASS／MP4烧录均完整八行，页面滑块修正并保存重载。 |
| #33 | 预览发送活跃字幕和必要元数据／样式，保留旧完整document请求；冷源构建一次、热缓存浅拷贝，渲染后复核源签名。完整保存／导出不变，不保存局部帧。 | 115项相关后端／66项前端与构建通过，独立APPROVE/WATCH。实际5000条整稿997903bytes，单活跃请求1421bytes；冷构建1次、后续3次热请求0额外构建。重叠两条与旧协议PNG逐像素相同；源变化拒绝。真实页面编辑保存5000条，完整ASS保留5000事件。 |

#29先将renderer身份升至3，#41最终升至4；排版改变产生新身份，原revision2／3产物继续按原SHA验证下载，不覆盖或盲目别名。当前9个历史产物下载哈希仍一致。`regex`更新通过既有生成入口；三份requirements导出与本轮前字节相同，uv.lock仅相关版本和直接依赖元数据变化，前端没有新增包。

#33同一场景缓存返回不新增请求；实际GUI的6次预览均200，最多两条活跃字幕、请求最大1555bytes。完整保存977821bytes、完整导出998968bytes；这些是不同夹具／编辑状态的实测数，不是恒定请求大小或时延承诺。所有字幕同时活跃时仍发送全部活跃字幕，保留20MiB／50000条边界。现有前端全稿扫描及其他性能待办没有借此宣称解决。

## 当前累计验证

| 入口 | 本轮实际结果 |
| --- | --- |
| 完整后端 | **1251 passed**，0失败／错误／跳过；仅一条既有Starlette/httpx弃用警告。 |
| 真实共享下游脚本 | **2个后端smoke＋308个前端测试＋TypeScript/Vite构建＋17个工作站浏览器用例**，exit0；两个后端smoke与完整后端重叠，不重复计数。 |
| 依赖与浏览器 | base／CUDA／ROCm三profile导出检查通过、51个基础已安装pins匹配；默认Chromium／指定Chrome实际启动并保留sandbox，无效路径无回退、零用例选择均按预期exit1。 |
| 工作站真实链路 | 当前FFmpeg／runner／SQLite／HTTP：导出201→编码失败400→重试201保留旧MP4；legacy／v2产物ready→missing一致；成功／失败终态报告可下载。上游ML为受控替身。 |
| 根代理Companion | 当前CUA时间编辑／合并／保存／重载、八行溢出与修复、5000条编辑与场景缓存；真实旧稿独立进程重开、999／1000四个不同输出、ASS／ZIP／libass烧录，删除工程后ASS／烧录缓存ID／SHA／mtime／数量不变而ZIP拒绝。 |
| 平台补充 | **21/21运行命令exit0**、无失败或跳过；CPU镜像89个app文件匹配、全新及旧库迁移／锁健康／真实媒体缓存；干净macOS声明闭包33个分发包／10个直接需求，构建／严格深度签名／冻结HTTP、8个web资源与合成RS256正反例。CLI及当前冻结smoke各1例，5个Companion实际流程、18张截图、0页面／控制台错误。 |
| 视觉复核 | 两名独立复核者各检查14张真实PNG，A/B均PASS；重叠帧像素完全相同，来源时序与截图格式有效。仅针对变化的字幕消费者，不构成整站手机／主题／HIG认证。 |

[33项累计矩阵](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/combined-acceptance.md)、[根代理真实QA](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/manual-qa-report.md)、[平台报告](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/platform-qa/platform-report.json)、[平台退出收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/platform-qa/qa-exit-receipts.json)逐项记录证据和边界。#22双磁盘故障、#23损坏receipt来自本轮自动回归；正常浏览器流程不冒充故障注入。#19／#38／#42此前手动操作仍标为历史，本轮重新执行对应完整自动回归。冻结后产品源码没有变化。最终复核独立核对352个源码哈希、有序差异链、144个QA产物哈希、5000条ASS事件和重叠帧相等性，没有重复跑完整套件冒充新结果。

![当前页面重载后八行字幕完整显示](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/browser-captures/41-final-restored.png)

## 失败保留、限制与交接

R31-1与R41-1保留原审查、真实反例、修复红灯和新复审。QA辅助脚本曾误认为自动导出会保存旧稿、选择source.mp4烧录、使用无效FFmpeg时间参数`.5`，以及假设请求必大于1MB；均保留失败日志／夹具，修正QA输入后实际重跑，未削弱产品守卫或删改有效断言。早期pnpm自动依赖状态路径失败、解释器／依赖检查辅助错误及截图格式修复也有记录。CUA原JPEG保留，转PNG后RGBA逐像素相同；不合格滚动位置截图保留但不用于通过结论。

未验收真实GPU／CUDA／ROCm、供应商／登录／模型、安装版原生窗口与退出、完整Compose部署、掉电或所有字体。自动布局沿用保守字宽估计，可能拒绝某些视觉上能容纳的字体组合；显式自由坐标仍可有意置于画布外。LSP缺失且未擅自安装，不能声称其诊断通过。既有大模块／异常风格、旧无模型任务只读标签、一个真实定时测试的低级维护意见保留WATCH；本轮没有扩大为无关重构。

自有端口／进程、容器、浏览器页均已关闭，父目录标记及证据保留；Docker恢复进入本轮时的停止状态，镜像和缓存保留。[清理记录](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/root-cleanup.json)、[Docker恢复收据](/Users/drm/project/nyaru-clipper/.omo/evidence/phase6-output-correctness-and-preview-2026-10-21/docker-restoration.json)。

累计已验收33项：**#1、#2、#3、#4、#5、#6、#7、#8、#9、#10、#11、#12、#19、#20、#21、#22、#23、#24、#26、#27、#28、#29、#30、#31、#32、#33、#37、#38、#39、#41、#42、#43、#44**。剩余11项：**#13、#14、#15、#16、#17、#18、#25、#34、#35、#36、#40**。两组互斥且覆盖44项。原44条问题及其独立验收条件保持，下一批尚未实施。
