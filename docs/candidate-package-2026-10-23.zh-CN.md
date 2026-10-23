# 统一架构新候选包与隔离验收（2026-10-23）

**本机候选打包与隔离工作流验收完成；正式 App／正式数据未替换或切换。** [English](candidate-package-2026-10-23.md)。本轮把 M03／M24 的恢复修复装入新 App 与新独立恢复包，没有新增应用源码修改。源码来自独立 `codex/unified-architecture-2026-10-22` 工作树，基线 HEAD `428ba833193db888c6b049ac2983abe1b2ecae17`；实现仍未提交，不能仅凭 HEAD 重建。

## 1. 交付物与身份

| 交付物 | 精确位置／身份 |
| --- | --- |
| 候选 App | `/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-01/Nyaru Clipper.app` |
| [候选 App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-01/Nyaru-Clipper-unified-candidate-20261023-01.zip) | SHA256 `7a5c3cad144c57dc74bda2391e157452b69418d1476fdd40e2895f3b310ad6a9`；633635601 字节 |
| 独立恢复目录 | `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01`；本轮新 epoch 使用该固定路径 |
| [独立恢复包 ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01.zip) | SHA256 `47f34e5b0d577b20be6d4990bdfd6e093c946159581b4cd1a6035b548b969082` |
| 两处 bundle.json | App 内 `Contents/Resources/recovery/bundle.json` 与独立目录相同，SHA256 `1ce64b4effcc38a592d90b12e879dcc02a990a62316af8fbdc8e23e16b31ff12` |
| 原生二进制 | SHA256 `75921310a9f3e903c047ae1b1b2d412ada8a4b53ef68cf3c4f37d1f989c74017` |
| 冻结后端 | SHA256 `0807970e0f22d950b0736542dbdd4dd23bfa21b6d535504bd98c32f2d3690798` |

显示版本仍为 **0.1.19 build27**，不能作为候选身份。App 为本机 Apple Silicon／最低 macOS 27.0 的 ad-hoc 签名候选，未公证、未发布。App ZIP 完整 CRC 通过，解包后 **5406 个文件及权限**全等，原 App 与解包 App 均通过 `codesign --verify --deep --strict`。

包内／独立／ZIP 解包恢复资源的 **3619 个摘要**全部匹配；9 个读取器模块（含 `recovery_thaw_resume.py`）及 150 个归档 helper 模块与当前源码一致，解包 Python／helper 可执行位和读取器启动通过。接管前固定独立包路径及摘要，之后未移动或替换。恢复包不带正式授权或任务数据。

打包输入是[202 文件源码封存](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-source.json)，摘要 `1e10e6b3d72ea396b8b0223c1dea3251cfbbf807c51062407b1e31e2078df7ba`；构建前核对全等。后续只更新本轮文档，不能将旧封存当作文档更新后的全工作区摘要。

## 2. 实际验收

| 场景 | 实际入口与结果 |
| --- | --- |
| 空根原生启动／重开 | 新 App 显式 `--unified-runtime`，正常退出两次均 exit0、helper 退出、ready 移除；端口 52006→52198，任务 0、队列暂停 |
| 真实冻结接管 | App 内后端的 `--unified-cli`／`--migration-cli` 完成 init、pin、公开配置、register、prepare、verify、takeover、category、配方导出；HTTP 核对保存稿／模板／暂停队列。开发 Python 只生成夹具和检查 DB |
| R0／R1 | 独立冻结 Python `-I -S -B` 做 6 根同 epoch 快照、只读导出与 thaw；整组 withdrawn／thawed，旧源字节、inode、mode、flags 全等；R0 从未激活 |
| R1 强杀续跑 | 真实 SIGKILL 于 group 已 thawed、最终收据输出前，exit -9；固定 `thaw-intent.json` 的 `interrupted_thaw` 后独立续跑 exit0，证明修复已实际进入交付包 |
| 旧 helper 回退重开 | 使用封锁前制作的独立旧格式归档／工作副本；保存稿 revision1 可读取，联网处理 POST403；helper／launcher 退出，原源不变 |
| R2 | 冻结接管后保存 revision2；snapshot／只读导出全文一致；thaw exit2，旧源和新 DB 保持 immutable、无解冻凭据 |
| 原生接管后保存／重开 | 另一新根中任务 `987473f590455e688376ce7d1f63fc55` 从 r2 在原生窗口保存为 **r3**，正文“新候选包原生接管验收：保存并重开。”；正常退出／同一 runtime＋guard 重开，52506→52607，仍为同任务／r3／暂停队列，HTTP 全文相同；两次 exit0、helper 均退出 |
| 原生稿独立恢复 | 停止原生后另取完整快照，HTTP 两份文档＝DB＝独立读取器导出；r3 正文 SHA256 `ed3d5139f18e3c34fbaf74d507024c781a9ec4e4a49d0f6c6b3b68504eb8c8fd`；R2 thaw 仍 exit2 |

媒体是新生成的 5 秒真实 H264，字幕／模板为受控夹具；未重新执行 ASR、在线翻译、真实直播或 GPU。接管原生夹具显式使用无模型路径，因此模型缺失提示属于该夹具配置；空根启动使用 App 内真实 bundled small 模型。未把旧 1538／46 项回归数字冒充本轮重跑。

## 3. 启动与回退边界

**候选必须显式传隔离 runtime，不直接双击或省略参数。** 省略参数仍会走兼容默认数据路径。下列为已经验证、保持可写的独立空根；不是封存样本：

```bash
"/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-01/Nyaru Clipper.app/Contents/MacOS/Nyaru Clipper" \
  --unified-runtime /Users/drm/.cache/nyaru-clipper/packaged-native-empty-20261023-01/runtime.json
```

如另建根，按[运行／回退指南](unified-runtime-guide.zh-CN.md)使用新数据／授权目录初始化。已接管根必须使用其固定 runtime 和 guard；本轮 R2 样本现已封锁，**不可直接启动或解封**：

- `/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-recovery-03/R2`
- `/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-native-guarded-01/R2`

R0／R1 必须先整组撤销后恢复旧权限；R2 仅保持封锁、快照／只读导出或独立旧格式工作副本。逐项恢复权限仍非原子，原件变化应停止恢复并保留新数据。已有 epoch 固定的 bundle 路径和摘要不可静默改绑；ZIP 可用于在新路径先校验再创建新 epoch，不能据此移动现有固定目录。10 月 22 日 build-04 样本 reader／build-05 App 保留原样，不用本包替换它们。

## 4. 保护、证据与待验收

构建前后，正式 App **1496 个文件的内容摘要一致**；正式数据 **6815 项元数据**（相对路径、mode、size、mtime、inode、flags）一致。正式数据正文／授权明文未读取，此项不声称做了正文全量哈希。所有自建 App／API／helper 已结束，R2 封锁现场与失败尝试保留。

- [构建日志](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-build.log)、[App／ZIP 身份](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-app-manifest.json)
- [空根原生收据](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-native-empty.json)、[原生接管保存／重开](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-native-guarded.json)
- [恢复验收收据](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-recovery/receipt.md)、[详细冻结命令与逐项产物](../.omo/evidence/candidate-package-20261023-recovery/report.md)
- [正式环境前](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-formal-before.json)／[后](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-formal-after.json)、[主会话最终收据](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-receipt.md)

失败尝试 recovery-01（缺公开设置，正确拒绝）及 recovery-02（QA 将 immutable 目录复制到 helper 归档）未删除；修正夹具后新根 recovery-03 完整通过，没有为此修改产品源码。

M03 保持本机 local_passed；M24 仍 partial，矩阵仍 **22／3／3**。受控 OS 重启、开机保护顺序及其他平台 profile、CUDA／WSL ROCm、Windows AMF、真实直播、公证／跨机器资格均未新增验收，P6 仍 planned。没有正式安装／迁移、提交／推送／合并。
