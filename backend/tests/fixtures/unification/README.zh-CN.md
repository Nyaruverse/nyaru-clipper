# 统一架构夹具

`contract.json` 在产品接入前固定 P0 输入与 M07／M28 阈值。生成的媒体、声音、字体、模型、授权及私有收据不进 Git。合成文本为本夹具编写；系统声音和字体资源不复制进夹具包。

在仓库根执行 `uv sync --project backend --frozen` 后，从 `backend/` 运行：

```bash
.venv/bin/python -m pytest -q tests/test_unified_import.py tests/test_unified_fixtures.py tests/test_unified_media_fixture.py tests/test_unified_platform_preflight.py
```

媒体测试使用 macOS 已安装的 `say` Kyoko／Tingting 声音和产品现有的 libass FFmpeg 选择器。其他平台复用摘要固定的生成包；跳过 macOS 生成器不代表 GPU 通过。权限探针要求普通 POSIX 用户，不认证 root、WSL 挂载语义、重启保护或运行时 Supervisor。

要保留独立夹具包，在仓库根运行，输出必须是父目录已存在的**新目录**：

```bash
PYTHONPATH=backend:backend/tests backend/.venv/bin/python -c 'from pathlib import Path; from unification_media import build_media; print(build_media(Path("/absolute/new/fixture")))'
```

`build_media` 拒绝已有输出。失败保留部分文件供检查，不写最终 `manifest.json`。完成包固定文件摘要、契约摘要、工具版本、Arial 字体摘要、RGB 转换、参考帧及隐去夹具根的完整命令。manifest 最后写入，只记录准备结果，不记录迁移或产品验收通过。

| 夹具 | 内容与证据边界 |
| --- | --- |
| F-media | 4501 帧、30fps、1280×720，中日合成语音。原文及译文在契约中；ASR 质量对比前须核对生成音轨。 |
| F-edit | 5000 条唯一 cue，间隔 30ms、持续 20ms，包含局部样式和已保存 revision 1。使用真实媒体的 R2 样本还包含现有读取器生成的来源证明。 |
| F-live | 7 个恰好 20 秒的闭合 MP4 块及 7 秒尾块、`closed.csv` 和明确标为合成的断流映射。重编码 AAC 以消除直接复制带来的时长漂移。这是闭合块夹具，不是采集／停止／恢复验收。 |
| F-state | 两个由外部标识的 Companion 实例包含相同旧 ID，覆盖坏清单、缺源、排队、失败和孤立产物；包含真实模板／默认／工程格式、受保护假授权及独立 R0／R1／R2 样本。工作站 JSON／SRT 使用现有序列化函数并保留词级时间，只证明冻结格式，不证明 GPU 推理。 |
| Expected | 五秒片段文档，字幕在第 1—3 秒；含 ASS／SRT、透明预览、FFV1 参考及 7 张固定 RGB 帧。固定 ROI 为 `(0,480,1280,240)`。FFV1 仅作参考，不能满足 M28。 |

`discover_companion(root, source_instance_id)` 是未来 P5 导入器提前落在 P0 的只读预检切片。它不从路径生成实例、不创建锁、不复制任务、不写映射、不封锁根、不授予执行权。`task_generation` 只覆盖任务文件，**不是**激活使用的 `source_generation`；后者还须绑定全局包并在未来 Supervisor 保护下复核。terminal 只描述已持久观察，不证明写入者已停止。翻译／导出等次级记录处于运行状态时，不会被判为 terminal。

已测试同 generation 发现结果相等；持久映射幂等、冲突处理、prepare／verify／activate、跨批次回退、整组发布及独立恢复仍属于 P2—P5 门槛。原读取器能读取夹具版本，不代表冻结恢复启动器通过。M01—M28 的结果须与夹具准备检查分别记录。

参见[执行记录](../../../../docs/unified-architecture-execution-2026-10-22.zh-CN.md)及[英文版本](README.md)。
