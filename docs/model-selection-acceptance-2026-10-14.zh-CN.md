# DeepSeek 模型选择验收

App 0.1.4 build 5 已安装并启动。双语面板新增「翻译模型」下拉框及独立的「保存模型」按钮，可选择 `deepseek-flash`（默认）或 `deepseek-v4-pro`，与 Key 一起保存至现有 `runs/config.json` 的 `deepseek_model` 字段。模型列表依据 2026-10-14 [官方文档](https://api-docs.deepseek.com/quick_start/pricing/)。

保存模型无需重新输入 Key，保存 Key 也保留模型；兼容旧的仅 Key 配置。已开始的翻译固定使用记录的模型，失败恢复不会混用缓存，新任务使用新选择。手工填错模型后可保存有效模型修复，保留已校验的 Key；配置错误未修复时拒绝开始翻译。

验证：121 项相关 App 后端回归、7 项界面测试、TypeScript/Vite 构建、独立审阅及严格签名通过。隔离冻结后台验证模型保存、Key 保留、重启加载、0600 权限和接口隔离，使用非真实测试 Key，没有调用翻译服务。实际安装版后台的浏览器界面完成 Pro 选择、保存、刷新及 App 重启加载；最终保存为默认 Flash。截图在 `.omo/evidence/2026-10-14-model-selection/model-selection.png`。两个既有任务的 86 个原文件校验和保持不变。

原目录 App/ZIP 已更新并保留旧包；ZIP 完整性通过。原生窗口观察仍受屏幕捕获故障影响，未宣称原生模型按钮操作已验收。真实 Key 尚未设置，两个模型的真实翻译及质量未验收。源码同步至原目录和网页版／App 工作目录，未提交或推送。
