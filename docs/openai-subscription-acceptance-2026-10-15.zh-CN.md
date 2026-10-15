# ChatGPT 订阅接入验收，2026-10-15

当前已安装0.1.8 build14，完成签名、安装哈希、重启登录保留、模型列表、原生双语播放及系统保存核验。真实新本地／直播处理在build13完成；build14仅修正实时翻译状态提示，未改变录制、识别、供应商请求及导出流程。

## 已验证

| 场景 | 实际结果 | 证据 |
| --- | --- | --- |
| 供应商选择 | 原生 App 可选 DeepSeek Flash／ChatGPT订阅；保存后重启仍保留 ChatGPT 与GPT-6-Luna | 原生操作记录；`openai-native/local-bilingual-preview.png` |
| 官方授权 | 系统浏览器打开 Nyaru Clipper 专属官方登录页；用户确认授权；JWT验证成功，订阅权限有效，返回7个账号模型 | `openai-subscription-progress.md` |
| 真实语义调用 | 公开 Responses 返回完成的切点JSON，73秒处结束当前话题 | `openai-response-diagnostic.json`、`openai-real-cut-receipt.md` |
| 新建本地录像 | `73fbcd311737`，150.033333秒，切成73及77.033333秒；21/21条翻译、3份双语SRT | `openai-online-local.json` |
| Bilibili实时 | 房间545068，`68faca68e130`，181.105秒，切成107.705及73.4秒；40/40条翻译、3份双语SRT | `openai-online-live.json` |
| 停止前输出 | 实时任务仍处于recording时，首段双语SRT已能下载；观察器在180.37秒停止录制，尾段随后完成 | 同上，early_bilingual |
| 文件与时间轴 | 每片双语字幕与原文条数、起止时间一致，从切片局部时间计时；HTTP下载字节等于任务文件 | 两份在线验收JSON |
| 原生预览 | build13本地首片0→23秒；最终build14实时首片0→7秒，中日字幕同屏 | `openai-native/local-bilingual-preview.png`、`openai-native/final-build14-live-preview.png` |
| 原生系统保存 | build14通过NSSavePanel将本地与实时首片双语SRT保存至项目验收目录，字节及SHA256与原文件一致 | `openai-native-final.json` |
| 旧文件保护 | 40c0c9原任务56项、35片目标原有113项哈希保持一致 | `openai-install-hashes.json` |
| 回归 | 最终状态修复后382项相关后端测试通过；41项界面测试及生产构建通过 | 工具执行记录、`openai-subscription-progress.md` |

证据目录为本仓库 `.omo/evidence/`。共享实现源位于 `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper`，原生打包源位于 `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper`。

## 修复与边界

- 首个新任务`35b20d192dcc`保留失败记录：实际订阅响应的完成事件output为空，完整结果位于此前output_item.done。解析器现按输出索引收集完整项，必须收到completed终态才成功；空、截断及失败流仍拒绝。真实安全样本回归及实际调用均通过。
- 旧任务缺少供应商字段时回退原有Flash；保存模型／检查点优先。新默认仅用于新任务。任务与缓存使用`chatgpt:<模型>`隔离，失败不自动切换供应商。DeepSeek Pro已禁用，本次没有Pro调用。
- 官方凭据与DeepSeek Key分开保存；前端、任务、导出和证据不记录令牌。目录0700、文件0600、原子写入、符号链接拒绝、PKCE/JWT/续期与撤销路径有回归覆盖。真实到期续期及撤销未通过等待或撤销当前用户授权验收。
- 用户未看到旧Downloads权限提示；重新检查时该请求已失败为Cannot create file，未授予权限。最终build14改由系统保存框选取项目验收目录，两个双语SRT均成功落盘；Downloads目录保存仍未通过验收，项目目录保存已通过。
- 译文仅作样本核对；ASR的专有名词和游戏术语仍可能错误，未完成逐句语义校对。技术验收不等于全句翻译质量验收。
- 当前为本机Apple Silicon验证；未公证、未公开发布，未验证Intel／旧macOS或Linux GPU配置。未提交／推送，历史与原文件保留。
