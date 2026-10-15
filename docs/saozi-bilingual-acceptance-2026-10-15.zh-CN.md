# 臊子自动双语验收：2026-10-15

当前安装版 **0.1.7 build 11**。自动双语已接入回放、本地录像和Bilibili实时流程；实时每次发布切片时补齐对应双语SRT，翻译失败单独报告，继续保留原文录制及视频。原文为日语时译中文，中文时译日语。

## 现有35片与原生App

- `40c0c9a8e93e` → `1bd089ad75b3`：复用658条既有译文，生成全局加35片共36份双语SRT，**翻译API请求为0**。
- 原任务56个文件及目标原有113个文件的SHA256均保持不变。全局双语文件与原任务逐字节一致；35片按实际切点逐条验证文本与零起点时间轴。
- 安装版36个双语文件HTTP下载均与磁盘文件一致；原生窗口默认「中日双语」，已看到日文原文与中文译文同时显示，播放时间从0推进至5秒。
- 原生系统保存得到 `~/Downloads/saozi-40c0c9-clip-001-bilingual-native.srt`，SHA256为 `94d17d739385aecd20e8de2a3c32279ed6017d21f6b662cf1d1cc5d74f678053`，与任务文件一致。新版签名触发下载目录权限等待，用户手动允许后同一保存正常完成。

## 回归、审阅与安装

- App工作树22个相关后端测试文件：**286 passed**；前端四文件：**25 passed**；TypeScript/Vite构建通过。存在原有Starlette/httpx弃用提示，不称为全仓库通过。
- 新增行为测试先复现未自动翻译、直播无双语发布、命令行翻译错误终止录制、旧缓存不兼容，再验证修复。
- 代码复审APPROVE，无剩余阻断项。命令行翻译失败现继续收集并收尾，末尾仍失败则退出码1；已有v1缓存沿用原路径，不重写旧翻译。
- 安装版与新构建1498项文件匹配，严格签名通过；旧App保存在 `~/Library/Application Support/Nyaru Clipper/app-backups/2026-10-15-0.1.6-build10-before-saozi-bilingual/Nyaru Clipper.app`。用户配置及模型保留。未公证、未发布、未提交或推送。

## 真实新任务

**真实新API流程验收受外部服务阻塞，未完成。**150秒本地任务 `515dbca2e1df` 在切点分析阶段收到真实DeepSeek HTTP503，恢复同一任务后仍返回503。45秒任务 `fed1a9f30275` 已完成本地识别与一个视频切片，但8条自动翻译在300秒验证窗口内未完成；随后正常退出并重开App，检查点保留，界面显示「已中断，可继续」，未留占用中的后台任务。失败与中断均保留，不算双语成功。

连通性检查：模型列表HTTP200、配置的Flash可用；最小Flash文本请求HTTP503，Pro最小请求20秒读超时。未修改用户默认Flash模型。真实新Bilibili双语任务未启动；旧版Bilibili接入/切片证据及本次增量双语的回归测试不替代这项真实在线验收。

## 本地证据

web工作树 `.omo/evidence/saozi-bilingual-backfill.json`、`saozi-bilingual-before.json`、`saozi-bilingual-service-report.md`、`saozi-bilingual-review.md`。App工作树 `.omo/evidence/saozi-bilingual-install.json`、`saozi-bilingual-installed.json`、`saozi-bilingual-native.json`、`saozi-bilingual-provider-failure.json` 与 `saozi-ui/bilingual-native-*.jpg/txt`。

没有逐句人工审校全部译文或验证多小时直播稳定性。进程恰在全局双语文件发布与检查点保存之间退出时，保留文件并报校验错误，需要人工检查，不会自动覆盖可能的手工改动。
