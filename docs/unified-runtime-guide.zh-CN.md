# 统一运行时候选操作指南

日期：2026-10-22。对应[英文](unified-runtime-guide.md)、[执行记录](unified-architecture-execution-2026-10-22.zh-CN.md)和[验收设计](superpowers/specs/2026-10-22-unified-architecture-design.zh-CN.md)。本指南描述已实现的候选入口；正式数据切换、安装替换和旧核心删除仍须通过计划门槛。

2026-10-23 已将中断恢复修复装入[新候选 App 与独立恢复包](candidate-package-2026-10-23.zh-CN.md)，通过冻结入口和真实原生隔离验收；使用该文档的精确包路径与摘要。旧 epoch 固定包保持原样。

## 1. 新建与运行

从仓库根运行，使用已安装所需引擎的平台环境。下列绝对路径是操作示例，须替换为本次清单中的独立目录；所有新建输出目录都必须不存在。`credentials` 引用既有授权目录，不能放入新数据根、来源封锁根或恢复包。

```bash
export PYTHONPATH="$PWD/backend"
backend/.venv/bin/python -m app.arctime.unified_cli init \
  --data /absolute/candidate --credentials /absolute/credentials \
  --model /absolute/ggml-small.bin --threads 4
backend/.venv/bin/python -m app.arctime.unified_cli serve \
  --runtime /absolute/candidate/runtime.json --port 0 --ready /absolute/ready.json
```

运行时按 `db/tasks/settings/guard/registry/packages` 分根，初始队列暂停。网页创建的任务先登记再等待队列启动；浏览器、原生和 CLI 共用同一 SQLite 与执行器。仅支持 loopback 或明确的私有 LAN 地址；`--host` 不接受通配或公网地址。LAN 仍按既有可信单用户边界运行。

安装包含已固定的 yt-dlp。WhisperX 平台还需显式准备主模型、对齐模型和 NLTK `punkt_tab`，设置 `APP_WHISPERX_MODEL_NAME/APP_WHISPERX_ALIGNMENT_MODEL_NAME` 为本地模型目录，`NLTK_DATA` 为含 `tokenizers/punkt_tab/english/` 的本地数据根；离线运行前按清单核对摘要。资格环境示例与下载摘要见执行记录 8.4。GPU 主机只安装 WhisperX 时，在新建任务中明确选择 WhisperX；CPP 缺失提示是另一引擎的准备情况。引擎不会在任务运行时静默替换，模板字体／FFmpeg 改变需另立验收收据。

```bash
backend/.venv/bin/python -m app.arctime.unified_cli queue --runtime /absolute/candidate/runtime.json
backend/.venv/bin/python -m app.arctime.unified_cli start --runtime /absolute/candidate/runtime.json
backend/.venv/bin/python -m app.arctime.unified_cli pause --runtime /absolute/candidate/runtime.json
```

`enqueue --request /absolute/request.json` 使用 `/api/v2/operations` 的同一判别请求，四种 kind 为 `process_recording/process_live/translate/export`。引擎、公开配置、模板／工程正文、输入摘要和文档版本由服务冻结，不能用浏览器传来的配置覆盖服务快照。重试未知外部调用可能计费的任务须显式确认；不会自动重发。

macOS 候选构建与启动：

```bash
backend/.venv/bin/python scripts/build_macos_app.py --unified-candidate --output-dir /absolute/build
"/absolute/build/Nyaru Clipper.app/Contents/MacOS/Nyaru Clipper" \
  --unified-runtime /absolute/candidate/runtime.json
```

冻结后端另有 `--unified-cli` 与 `--migration-cli` 入口。测试和重开须保留 `--unified-runtime` 参数；省略它仍会进入兼容桌面默认路径。退出时先结束 SSE，再等待执行器与进程组收尾；超过窗口等待时间可选择继续等待或显式强制退出。强制退出后须按恢复检查处理。

## 2. 来源登记、准备与接管

来源 UUID 从外部登记获得，不能按路径重新生成。工作站 roots 至少含绝对 `tasks/settings/database`，外部引用媒体另列 `media`，数据库名用 `database_name`。重定位保留 UUID，用 `register --mode relocate --expected-generation GENERATION` 登记新 roots，系统从原登记建立根别名。Companion 只读发现不接受无归属目录自动成为任务。

公开配置必须完整。用旧主机对应的 `APP_*` 环境和显式运行时执行 `capture-public`，检查导出文件包含所有公开 Settings、提供方／模型、CPP 模型路径和线程数。私密配置只读引用；API Key、cookie 内容、OAuth token 不进公开包。

```bash
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  capture-public --output /absolute/public-settings.json
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  register --source SOURCE_UUID --origin companion --roots /absolute/source-roots.json \
  --public-settings /absolute/public-settings.json
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  prepare --source SOURCE_UUID --legacy-id LEGACY_ID
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  verify --batch BATCH_ID
```

`prepare` 只复制独立候选、全局包和历史；`verify` 只验证。两者均不启动模型或网络，不赋予执行权，不自动启动旧排队任务。已保存的字幕 revision／词级信息、标题／标签／归档和全局模板／工程保留；多处已保存稿不一致时拒绝自动选择。

接管前封存独立恢复包并固定 `bundle.json` 摘要：

```bash
backend/.venv/bin/python scripts/build_unified_recovery.py --output /absolute/reader \
  --legacy-helper --tools-root /absolute/frozen-tools
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/candidate/runtime.json \
  pin-recovery --bundle /absolute/reader/bundle.json --sha256 BUNDLE_SHA256
```

`frozen-tools` 须包含已验证的 ffmpeg／ffprobe 及全部所需动态库，使用候选 App 已整理的工具目录或同等完整目录。运行时需使用 `pin-recovery` 返回的 `runtime-recovery-*.json`。恢复包应包含独立 CPython、精确格式读取器、旧界面 helper 和媒体工具，不能指回候选源码或虚拟环境。接管 guard JSON 包含 `group_id/domains/locks/guard_root`，完整列出旧任务、设置、数据库、外部媒体保护域及旧入口锁；控制目录位于新运行时 guard 根。

```bash
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/PINNED_RUNTIME.json \
  takeover --guard /absolute/guard.json --batch BATCH_A --batch BATCH_B --port 0
```

同一 Supervisor 持有旧锁，安装持续封锁，重新核对来源 generation，单事务切换整批引用，然后持续托管 API；不能先退出 Supervisor 再启动执行器。旧写入失败探针、全部锁 inode、来源摘要、reader/helper 摘要和暂停队列均需记录。后续重开用 `serve-guarded` 或原生 `--migration-guard`，并保留同一 pinned runtime／guard。macOS 使用 immutable 属性；Linux 只接受另行验证的只读挂载保护配置，chmod 不能替代，native ROCm 安装成功也不证明迁移保护通过。

## 3. R0／R1／R2 与新版无法启动

| 级别 | 进入条件 | 允许行为 |
| --- | --- | --- |
| R0 | 整组从未激活、无统一新写入，队列暂停且全部执行权释放 | 整组撤销后恢复旧权限 |
| R1 | 整组曾激活，但没有统一新写入；无外部依赖，全部执行权释放 | 同一恢复包与 guard 下，先提交整组撤销凭据，再恢复旧权限 |
| R2 | 任务／字幕／模板／默认／工程等发生任何统一新写入 | 保留封锁；同 epoch 多根快照后只读导出，或在独立旧工作副本继续编辑 |

批次 B 取消不会撤销批次 A 的 R2。只改全局模板也会进入 R2。缺任一成员、未知 schema、缺失／变更的 guard 或恢复包、运行进程／组、无法核对原锁 inode，均拒绝解封。任何回退都不能把新数据库覆盖为旧 schema，或覆盖较新的字幕和导出。

候选仍可运行时，可先导出独立恢复配方：

```bash
backend/.venv/bin/python -m app.arctime.migration_cli --runtime /absolute/PINNED_RUNTIME.json \
  recovery-recipes --guard /absolute/guard.json --output-root /absolute/recipes
```

把配方、固定包及摘要保存在所有数据／授权／来源根以外。新版不能启动时直接使用冻结 Python；不能启动候选来修补 schema、重建锁或重新探测目录：

```bash
/absolute/reader/runtime/bin/python3.11 -I -S -B /absolute/reader/reader.py \
  --mode snapshot --manifest /absolute/recipes/snapshot.json \
  --output-root /absolute/snapshot --install-seal
/absolute/reader/runtime/bin/python3.11 -I -S -B /absolute/reader/reader.py \
  --mode read-only --manifest /absolute/snapshot/complete.json \
  --bundle /absolute/reader/bundle.json --output-root /absolute/recovered
```

以入口返回的实际 receipt 路径为准，不能仅凭输出目录存在推断完成。快照持有既有 GUI、重任务和 guard 控制锁，包含数据库／WAL、任务、设置、包、registry 和 guard，授权仅保留独立引用。读取器输出最后已登记稿的 JSON／SRT／ASS、完整已提交产物及 task／publication／global-history 索引；不会补跑模型、AI 或编码。未保存客户端草稿不属于数据库恢复范围。

**R0／R1 已先做封锁快照时**，复制 `thaw.json` 为新的操作配方，增加：

```json
{"sealed_snapshot":{"path":"/absolute/snapshot/complete.json","sha256":"COMPLETE_SHA256"}}
```

其余原字段必须保留。`thaw` 会在锁屏障内仅临时恢复新 DB／guard 控制区的原权限，提交整组撤销、恢复旧权限，然后重新封锁控制区；新任务／设置／媒体仍保持只读。R2 会在恢复控制区之前拒绝。

```bash
/absolute/reader/runtime/bin/python3.11 -I -S -B /absolute/reader/reader.py \
  --mode thaw --manifest /absolute/thaw-sealed.json --bundle /absolute/reader/bundle.json \
  --output-root /absolute/thaw-receipt
```

**故障续跑**：快照安装封锁中断时，保留最初 `source-protection.json`，用新输出目录和原摘要设置 `protection_record/protection_sha256`，再执行 snapshot；禁止从已封锁权限推断原模式。thaw 在提交撤销后遇到旧权限恢复失败时，保留 `controls-resealed.json`，重新取得完整快照（不再 `--install-seal`），在新 thaw 配方中更新 `sealed_snapshot`，并增加 `controls_protection={path,sha256}` 指向该重新封锁记录，再用新输出目录继续。先核对 group 为 `withdrawing`、没有 activated 绑定或新写入。原权限记录缺失、字节／inode 变化均停止。

**SIGKILL／断进程续跑（10 月 23 日新冻结包）**：强杀不会执行 finally，可能没有 `controls-resealed.json`。保留解封前 fsync 的 `<前次输出>/thaw-intent.json`、其摘要及原完整配方，在原配方中仅增加：

```json
{"interrupted_thaw":{"path":"/absolute/previous-output/thaw-intent.json","sha256":"INTENT_SHA256"}}
```

原 `sealed_snapshot`、`controls_protection`（若有）、bundle、guard 等字段不得变化。使用同一固定 reader、`--mode thaw` 和新的 `--output-root`。锁屏障内核对原权限日志／inode，非控制根、旧原件字节变化均拒绝；仅容许恢复产生的 SQLite／guard 控制差异。当前 DB 仍须无 R2、无执行权且整组撤销集合一致。已标 `thawed` 但最终收据丢失时，仅在原权限与 DB／guard 凭据完整一致后补收据，绝不重授统一映射。缺 intent、摘要不符或状态损坏时停止，不猜测原权限、不覆盖新数据。

旧根逐文件恢复权限不能视为原子操作：部分旧根可能已可写，完整恢复后强杀会释放旧锁；此时统一映射已先整组撤销。若旧入口产生了新字节，后续恢复应拒绝而保留它。不能把这段时间写成“所有旧写入均被拒绝”。[已演练关键边界](unified-architecture-execution-2026-10-22.zh-CN.md#9-2026-10-23m03m24-接管与崩溃回退补验收)不替代实际重启／所有时刻／跨平台资格。

此修复只在新冻结包内生效。已经固定的 build-04 样本包和 build-05 App 不包含本次修复，不能原地更新文件或重绑已有 ownership 的 bundle 摘要；它们的原快照／只读恢复继续保留。旧包遇到未覆盖的 thaw 中断时保持现场，不能借新包演练结果宣布该旧 epoch 已验收。

旧界面仅使用已验证的旧格式快照工作副本。`legacy-browser` 要求 snapshot 配方中有不含授权的 `legacy={snapshot,files}`，摘要和 helper ABI 全等；helper 在 loopback 动态端口运行，禁止登录、联网处理与模型调用，退出时回收其进程。不要将新的统一任务根直接传给旧格式入口。

## 4. 验收与后续边界

以[执行记录](unified-architecture-execution-2026-10-22.zh-CN.md)逐项登记 M01—M28，保持实现、测试和平台 accepted 分离。Linux CUDA、WSL ROCm、真实直播、AMF、实际旧入口／重启保护及正式安装／切换没有相应证据就不能勾选。server-194 是 native Linux ROCm 的补充资格环境，不能替代两份目标 GPU 平台收据。

P6 的旧写入核心删除仍以全部 P5 必选项通过、调用清单清零和单独审核删除范围为前提。当前保留旧入口、兼容读取器、旧产物、未知目录和所有失败证据。
