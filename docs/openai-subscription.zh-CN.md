# ChatGPT 订阅接入

本地工作台支持两个可选 AI 供应商：DeepSeek Flash 和 ChatGPT 订阅。它们用于臊子语义切点分析与中日字幕翻译；录制、识别和视频导出仍在本机进行。

在 **AI 供应商** 中选择 **ChatGPT 订阅**，点击 **Continue with ChatGPT**，再点击浏览器继续登录链接。在官方页面完成登录并允许使用 ChatGPT 订阅额度后，返回 Nyaru Clipper，选择账号返回的模型并保存供应商与模型。保存的选择用于新任务；已经开始的任务沿用原供应商、模型和缓存。DeepSeek Pro 已禁用。

账号登录成功或读取到模型列表，不代表已经验证推理权限。实际可用性和额度由 OpenAI 控制；请求失败会保留原切片和已完成的字幕批次，不会自动切换供应商。界面提供管理用量和退出账号入口。

凭据单独保存在 `runs/.chatgpt/`，目录和文件仅当前用户可读写，并采用原子替换。前端、任务清单与下载接口不会收到令牌。此连接独立使用官方注册流程，不复用其他应用的凭据。

实现遵循官方 [Sign in with ChatGPT 流程](https://developers.openai.com/siwc/token-sharing-open-source)、[Responses 请求](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)及当前[预览限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)。真实账号与原生 App 验收单独记录；本使用说明不代表实际在线推理已验收。
