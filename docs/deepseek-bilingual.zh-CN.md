# DeepSeek 中日双语字幕

在「翻译模型」中选择 `deepseek-flash` 或 `deepseek-v4-pro`，点击「保存模型」；无需重新输入 Key。`deepseek_model` 与 Key 保存在同一配置文件中，重启加载；旧的仅 Key 配置默认使用 Flash。已开始的翻译继续沿用记录的模型，面板显示当前任务模型。修改默认选项只影响尚未开始翻译的任务，不会覆盖已有双语结果或混用不同模型的缓存批次。

在本地配套工具及 macOS App 0.1.4（build 5）中，选择一个已完成任务，在「日语 → 中文 · 双语字幕」面板输入 DeepSeek API Key，点击「保存 Key 到配置文件」，再点击「生成中日双语字幕」。翻译只发送现有字幕文字到 DeepSeek 官方 API，不上传视频、重新下载、重新识别或重新编码切片；会消耗 DeepSeek API 额度。

Key 保存在任务根目录下的 `config.json`，保存时权限设为仅当前用户可读写（0600），重启自动加载。macOS 路径为 `~/Library/Application Support/Nyaru Clipper/runs/config.json`。保存新 Key 会原子替换配置；Key 不通过 API 返回，也不写入任务清单、日志或浏览器存储。配置含明文凭据，请勿分享或提交到仓库。也可手工配置 `{"deepseek_api_key": "你的 Key"}`，将文件权限设为 0600 后重启 App；设为空字符串即可禁用。无效配置会在界面提示，可重新保存修复。界面显示已完成／总字幕条数；认证、余额、网络及响应格式错误会显示在翻译面板。失败或中断后可继续，已校验的翻译批次保留，原视频任务保持完成状态。

完整视频新增 `subtitles.ja-zh.srt`，各切片新增 `clip-NNN.ja-zh.srt`。每条先日语、后简体中文，时间轴与原字幕相同；切片字幕按原选区从零计时。预览可切换原文和中日双语，结果面板可分别下载。现有视频、原文字幕、识别缓存和 `job.json` 保留。

翻译使用所选模型（默认 `deepseek-flash`）的非思考模式及 JSON 输出；每批最多 40 条。仅接受数量、顺序和 ID 对应的非空译文，截断或无效响应不发布结果；429 和临时服务／网络错误最多尝试三次。`translation.json` 单独保存来源校验和、模型、提示词版本及已完成批次，不通过下载接口提供。请勿手工改动缓存。已完成的结果缺失或校验失败会报告错误并保留文件。

字幕翻译继承原识别文字的错误。此版本不纠正日语原文、不添加翻译校对编辑器，也不会移除或覆盖原视频画面内已有的烧录字幕。双语 SRT 是外挂字幕，MP4 画面保持原样；播放器使用时选择该双语 SRT 即可。

接口依据：[DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) 和[模型说明](https://api-docs.deepseek.com/quick_start/pricing/)（2026-10-14 核验）。
