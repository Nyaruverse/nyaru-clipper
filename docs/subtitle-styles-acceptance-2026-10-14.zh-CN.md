# 字幕样式功能交付与验证

日期：2026-10-14（Asia/Shanghai）。版本：Nyaru Clipper 0.1.5，build 9。

构建目录为 `/Users/drm/.codex/worktrees/local-companion-macos/nyaru-clipper`；以下 `dist/` 和原生证据路径相对该目录。

自定义字幕样式、样式 JSON 模板、ArcTime ATPJ 模板、ASS 导出、切片烧录和 ArcTime 文件交接已实现。所选自动测试和下列实际流程通过。2026-10-15 的[原生预览复查](arctime-native-preview-2026-10-15.zh-CN.md)进一步确认双语及样式预览通过；不能宣称无损视觉往返或所有平台验收。

## 交付

- App：`dist/subtitle-style-0.1.5-upload-verified/Nyaru Clipper.app`。
- 解压包：`dist/Nyaru-Clipper-0.1.5-build9-macOS-arm64.zip`；旧包及旧安装保留。
- [中文使用说明](subtitle-styles.zh-CN.md)与[英文说明](subtitle-styles.md)。
- 共享源码位于浏览器工作目录 `/Users/drm/.codex/worktrees/local-companion-web/nyaru-clipper`，并同步到本 macOS 工作目录。2026-10-15功能提交已推送对应网页版／App开发分支；未合并主目录或master，原有主目录文档改动保留。

## 实际检查

| 检查 | 结果与证据 |
| --- | --- |
| 自动回归 | 所选后端 187 项通过；最后包说明变更后的 API 16 项通过；前端最终 22 项通过，TypeScript/Vite 构建通过。不是全仓库测试。 |
| 样式预览 | 浏览器实际修改字号和背景，短文本背景只包围文字；完整／切片切换、双语、跳转及含字幕全屏和退出经过操作。390、1440、1920 宽度的样式面板和下载区域无水平溢出。保留原有浅色主题；深色偏好下布局仍可读，未新增深色主题。 |
| ASS／烧录／ZIP | App 的实际按钮生成输出，ASS／MP4／ZIP 均通过系统保存面板保存。最终共享逻辑 build 8 再验证 64 号原文、0.4 背景、48.033 秒双语烧录、1280×720 ASS 和精修包校验和；build 9 只补原生选择面板，后端与前端字节一致。 |
| 两类模板 | build 9 实际取消选择、导入 JSON 后显示 64／0.4、导入 ArcTime 保存的 ATPJ、选择并确认保存关联。再从 App 导出带模板的 ZIP，原生模板下载与包内字节完全相同。保存文件可由新的存储对象读取。 |
| 原文件保护 | 用户任务原视频、SRT、识别／翻译等 17 个文件的前后 SHA256 相同；未重新识别、翻译或更改 Key。 |
| ArcTime 原生精修 | ArcTime Pro 4.5 实际导入合成 6 秒视频及 9 个 ASS 事件，修改文字和起止时间，保存原生 ATPJ；在第二新工程导入该模板，10 个样式定义一致且未混入旧字幕。 |
| ArcTime 尺寸兼容 | 最初 1080 参考画布被 ArcTime 改成 640×360 而坐标未缩放，已修复。新交接 ASS 使用视频实际尺寸；真实保存后 9 个事件、文字和时间保持，坐标在画内。对 ArcTime 保存的 ASS 在 1／3／5.5 秒用 libass 渲染，白日文、绿中文、背景、多行及字面特殊字符可见。 |
| 原生文件面板 | 发现 WKWebView 缺少文件面板委托并修复；build 9 使用系统 Open 面板完成 JSON／ATPJ 导入。Swift 实际编译及独立类型检查通过。 |
| 打包 | FFmpeg 的 SDL2 compatibility 动态加载 SDL3，漏打包会阻塞工具；已显式包含并在构建中检查冻结 FFmpeg 的 libass 滤镜。最终 App 严格 ad-hoc 签名验证通过。 |

## 保留的限制

2026-10-14 曾记录黑屏并保留为历史观察。2026-10-15 同时捕获 ArcTime 独立 mpv 窗口与实际屏幕，原生播放、双语多行、样式及时间轴跳转均通过。Java 主窗口的单窗截图遗漏视频窗口，会显示黑色占位区。修正了验证方法；旧区域截图黑屏本次未重现，未修改播放器或系统配置。

ArcTime 会取整字号、添加淡入淡出并重排字幕层。旧模板的同名样式可覆盖本次尺寸换算；界面、包内说明和使用指南均提示先导入模板、再导入 ASS，并检查分辨率、分组和排列。原生 ATPJ 可带旧媒体路径和用户标记，保持原样复制，请分享前检查。

本包为 Apple Silicon、最低 macOS 27.0；未检查 Intel、Linux 原生打包、干净机器或所有字体。只有本地 ad-hoc 签名，未进行 Developer ID 签名、公证或正式发布；源码推送不等同于安装包公开发布。未测试扬声器播放；导出媒体文件与代表帧已验证。

## 可复现证据

macOS 工作目录 `.omo/evidence/`：`final-native-runtime-verification.json`、`final-native-upload-verification.json`、`final-package-verification.json`、`native-saves/final-burned-frame.png`、`subtitle-native-upload-review.md`。

浏览器工作目录 `.omo/evidence/`：`subtitle-final-review.md`（APPROVE，零阻断）、`subtitle-interrupted-red.log`／`subtitle-interrupted-green.log`、`arctime-native-verification.md`、`arctime-native-manual-qa.md`、`subtitle-real-runtime/arctime-template-package-verification.json`、`subtitle-visual/`。合成素材和原生模板只留在本地证据目录，不作为公开源码或发布附件。
