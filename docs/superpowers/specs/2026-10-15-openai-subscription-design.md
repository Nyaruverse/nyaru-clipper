# OpenAI 订阅接入方案（用户已确认，实施中）

## 目标

在 Nyaru Clipper 的本地工作台与 macOS App 中新增“ChatGPT 订阅”供应商，用用户通过官方 OAuth 明确授权的订阅额度执行臊子切点分析和中日双语翻译，覆盖回放、本地录像与 Bilibili 实时切片。DeepSeek Flash 保留为可选供应商；严禁调用 DeepSeek Pro。

## 接入方式

推荐：直接实现官方 Sign in with ChatGPT 的本地应用流程，使用公共 Responses API。现有后端已经使用 HTTPX；无需为了纯文本分析启动完整 Codex 代理进程。

备选：在本地启动 Codex app-server，由它处理推理消息；仍需本应用管理官方订阅授权、令牌续期，并额外打包/管理子进程。本功能不需要代理工具执行能力，因而不推荐。

普通 OpenAI API Key 属于另一种计费入口，本次不添加。不得读取或复制 Codex/ChatGPT 其他应用的登录凭据，也不调用非官方 backend-api 地址。

## 用户流程与本地授权

1. 供应商选择包含 DeepSeek Flash 与 ChatGPT 订阅。
2. “Continue with ChatGPT”在系统浏览器打开官方登录页。应用提前启动127.0.0.1回调监听，使用独立、随机的state/nonce/PKCE和稳定安装host ID。
3. 登录、身份及scope验证完成后，展示连接状态、可用模型、“管理用量”和退出登录。账号模型列表由官方接口实时获得，不把本地固定模型表当作权限证明。
4. macOS令牌由受保护的本地凭据存储管理；前端、任务清单、日志和下载接口只接收脱敏状态，不接收令牌。退出清除可用凭据；过期允许安全续期，授权撤销要求重新登录。

## 推理与既有流程

- 只发送字幕及切点候选；视频下载、录制、识别、切片和字幕导出继续在本地执行。
- 共享请求边界支持供应商专用协议。OpenAI使用Responses SSE、store=false、stream=true、instructions及数组input；遵循当前订阅接口字段限制。
- 仅收到response.completed、非空内容且通过现有结构/ID/数量/候选/时间校验后，才发布切点或双语结果；中断、额度限制和失败不得作为成功。
- 每个任务保存供应商、模型和提示词身份；缓存不得跨供应商混用。旧任务缺省按DeepSeek解释，已有输出与缓存保留。选择新默认值只影响新任务；不自动把进行中的Flash任务切成OpenAI。
- 继续逐片发布双语SRT，保留原文SRT。单片字幕翻译失败保留录制与原文结果，明确显示待补齐。
- 明确连接/读超时与请求总时长上限，有界重试。额度耗尽或授权缺失直接给出恢复入口，不暗中切换供应商或调用Pro。

## 验证和交付

先验证OAuth回调、防串号/重放、权限缺失、令牌续期/退出、流式中断/失败、缓存隔离及原有Flash回归。随后构建更新macOS App，完成真实浏览器登录与一个实际推理请求；登录成功或模型列表成功均不替代推理验收。

真实媒体验收：新本地录像任务自动双语；至少一次需要云端候选选择的1–2分钟切片；真实Bilibili录制期间首片双语可下载，停止后尾段完成。验证配对文本、逐条时间轴、切片零起点和下载字节一致性，抽查翻译含义。40c0c9及35片既有结果不改写。

用户2026-10-15已确认官方订阅直连方案。实施及账号实际订阅调用权限仍待验证。不提交或推送现有未提交源码。

## 已核对的官方文档（2026-10-15）

- https://developers.openai.com/siwc/token-sharing-open-source
- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations
- https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt
