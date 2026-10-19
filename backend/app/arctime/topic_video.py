"""话题切片视频生成：把语义切片（topic_segments）按时间精确切成视频文件。

- 分别生成：每个话题段独立 mp4，烧录对应时间段字幕（沿用全局字幕样式与图形）。
- 组合生成：按段编号顺序逐段生成带编号标识的临时段，再用 concat 合并为一个 mp4。
所有 ffmpeg 调用均以任务目录为 cwd、滤镜只用纯文件名，规避 Windows 盘符/反斜杠转义。
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Literal

from app.arctime import media, workflow
from app.arctime import subtitle_style_legacy as subtitle_style

Variant = Literal["bilingual", "zh", "original"]
Mode = Literal["separate", "combined"]

_PROBE_TIMEOUT = 60
_ENCODE_TIMEOUT = 1800
# 合并视频中编号标识在每段开头显示的秒数
NUMBER_MARK_SECONDS = 3.0


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


# Alignment=9（右上角），白字 + 4px 黑描边，MarginR/MarginV 控制角落边距
_NUMBER_STYLE = (
    "Style: Number,Microsoft YaHei,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
    "-1,0,0,0,100,100,0,0,1,4,0,9,40,60,34,1"
)


def render_segment_ass(cues, translated, style_config, variant: Variant, number: int | None) -> str:
    """渲染单段 ASS；number 非空时在该段开头右上角显示编号标识。"""
    ass = subtitle_style.render_ass(cues, translated, style_config, variant)
    if number is None:
        return ass
    ass = ass.replace("\n[Events]\n", f"\n{_NUMBER_STYLE}\n[Events]\n", 1)
    duration = cues[-1].end_seconds if cues else NUMBER_MARK_SECONDS
    mark_end = min(NUMBER_MARK_SECONDS, max(0.5, duration))
    ass += f"Dialogue: 99,{_ass_time(0)},{_ass_time(mark_end)},Number,,0,0,0,,{number:02d}\n"
    return ass


def _probe_resolution(directory: Path, source: str) -> tuple[int, int]:
    result = subprocess.run(
        [media.tool_path("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", source],
        cwd=directory, capture_output=True, text=True, timeout=_PROBE_TIMEOUT, check=False)
    parts = (result.stdout or "").strip().split(",")
    if result.returncode != 0 or len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError("无法读取视频分辨率，生成已取消")
    return int(parts[0]), int(parts[1])


def _segment_cues(directory: Path, variant: Variant, start: float, end: float):
    """提取全局时间 [start, end) 对应的局部字幕（时间归零），与既有 burn 路径一致。"""
    ja_cues = media.clip_subtitles(
        media.read_subtitles(workflow._path(directory, "subtitles.srt")), start, end)
    translated = None
    if variant in {"bilingual", "zh"}:
        zh_cues = media.clip_subtitles(
            media.read_subtitles(workflow._path(directory, "subtitles.zh.srt")), start, end)
        if len(zh_cues) != len(ja_cues):
            raise ValueError(f"原文与译文字幕条数不一致（{len(ja_cues)}≠{len(zh_cues)}），无法烧录该段")
        translated = [cue.text for cue in zh_cues]
    return ja_cues, translated


def build_segment(directory: Path, source: str, start: float, end: float, variant: Variant,
                  style_store: subtitle_style.StyleStore, shape_pngs: list[Path],
                  out_name: str, ass_name: str, number: int | None = None) -> None:
    """精确切片 + 字幕/图形烧录。

    -ss/-t 必须作为输入选项（-i 之前）：重编码时帧精确，且解码器输出时间戳自动归零，
    subtitles 滤镜才能匹配局部时间轴的 ASS；放在 -i 之后（输出 seek）即便加 setpts
    也无法让 subtitles 滤镜命中，会导致非零起点段字幕/编号整体丢失。
    """
    ja_cues, translated = _segment_cues(directory, variant, start, end)
    ass_path = workflow._path(directory, ass_name)
    workflow._publish_text(ass_path, render_segment_ass(ja_cues, translated, style_store.current, variant, number))
    output = workflow._path(directory, out_name)
    output.unlink(missing_ok=True)

    duration = max(0.1, end - start)
    # -ss/-t 只作用于紧随其后的源输入；PNG 输入在其后，不受影响
    inputs = ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", source]
    if shape_pngs:
        for png in shape_pngs:
            inputs += ["-loop", "1", "-i", png.name]
        chain = ""
        previous = "0:v"
        for shape_index in range(len(shape_pngs)):
            chain += f"[{previous}][{shape_index + 1}:v]overlay=0:0[s{shape_index}];"
            previous = f"s{shape_index}"
        video_filter = f"{chain}[{previous}]subtitles={ass_path.name}"
        filter_args = ["-filter_complex", video_filter]
    else:
        filter_args = ["-vf", f"subtitles={ass_path.name}"]

    command = [
        media.tool_path("ffmpeg"), "-hide_banner", "-y", *inputs,
        *filter_args,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", out_name,
    ]
    try:
        result = subprocess.run(command, cwd=directory, capture_output=True,
                                text=True, timeout=_ENCODE_TIMEOUT, check=False)
    finally:
        ass_path.unlink(missing_ok=True)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 1024:
        tail = (result.stderr or "").strip().splitlines()
        raise ValueError(f"切片 {out_name} 合成失败：{tail[-1] if tail else '未知错误'}")


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [media.tool_path("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=_PROBE_TIMEOUT, check=False)
    try:
        return float((result.stdout or "").strip())
    except ValueError:
        return 0.0


def concat_parts(directory: Path, part_names: list[str], out_name: str) -> None:
    """同源同参数段优先 concat copy；时长校验不过则回退重编码合并。"""
    list_path = directory / ".topic-concat.txt"
    list_path.write_text("".join(f"file '{name}'\n" for name in part_names), encoding="utf-8")
    output = workflow._path(directory, out_name)
    output.unlink(missing_ok=True)
    expected = sum(_probe_duration(directory / name) for name in part_names)
    try:
        result = subprocess.run(
            [media.tool_path("ffmpeg"), "-hide_banner", "-y", "-f", "concat", "-safe", "0",
             "-i", list_path.name, "-c", "copy", "-movflags", "+faststart", out_name],
            cwd=directory, capture_output=True, text=True, timeout=_ENCODE_TIMEOUT, check=False)
        if result.returncode != 0 or not output.is_file() or abs(_probe_duration(output) - expected) > 1.5:
            result = subprocess.run(
                [media.tool_path("ffmpeg"), "-hide_banner", "-y", "-f", "concat", "-safe", "0",
                 "-i", list_path.name, "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                 "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_name],
                cwd=directory, capture_output=True, text=True, timeout=_ENCODE_TIMEOUT, check=False)
    finally:
        list_path.unlink(missing_ok=True)
    if result.returncode != 0 or not output.is_file() or abs(_probe_duration(output) - expected) > 1.5:
        tail = (result.stderr or "").strip().splitlines()
        raise ValueError(f"组合视频合并失败：{tail[-1] if tail else '时长校验不一致'}")


def generate(directory: Path, segments: list[dict], indices: list[int], mode: Mode, variant: Variant,
             style_store: subtitle_style.StyleStore, progress: Callable[[int, int, str], None] | None = None) -> dict:
    """按选中话题段生成视频。返回 {"items": [...], "combined": {...} | None}。

    分别生成：某段失败只记录该段失败并继续；组合生成：任一段失败即整体失败。
    """
    source = "source.mp4"
    if not (directory / source).is_file():
        raise ValueError("源视频缺失，无法生成切片视频")
    width, height = _probe_resolution(directory, source)
    shape_pngs = (subtitle_style.render_shape_pngs(style_store.shapes, directory, "topic", width=width, height=height)
                  if style_store.shapes else [])
    total = len(indices)
    items: list[dict] = []
    part_names: list[str] = []
    try:
        for done, index in enumerate(indices, start=1):
            segment = segments[index]
            # 组合模式：编号 = 点击选择顺序（第 N 个勾选的段显示 N 并按该顺序合并）；
            # 分别生成：文件名沿用切片自带编号
            number = done if mode == "combined" else index + 1
            if progress:
                progress(done, total, f"正在生成切片 {number:02d}（{done}/{total}）")
            if mode == "combined":
                part_name = f".topic-part-{number:02d}.mp4"
                ass_name = f".topic-part-{number:02d}.{variant}.ass"
                # 重新生成时清掉可能残留的旧临时段
                (directory / part_name).unlink(missing_ok=True)
                build_segment(directory, source, segment["start_seconds"], segment["end_seconds"],
                              variant, style_store, shape_pngs, part_name, ass_name, number=number)
                part_names.append(part_name)
                items.append({"index": index, "file": None, "state": "completed", "error": None})
            else:
                out_name = f"topic-{number:02d}.mp4"
                ass_name = f".topic-{number:02d}.{variant}.ass"
                try:
                    build_segment(directory, source, segment["start_seconds"], segment["end_seconds"],
                                  variant, style_store, shape_pngs, out_name, ass_name, number=None)
                    items.append({"index": index, "file": out_name, "state": "completed", "error": None})
                except ValueError as exc:
                    items.append({"index": index, "file": None, "state": "failed", "error": str(exc)[:300]})
        combined = None
        if mode == "combined":
            if progress:
                progress(total, total, "正在合并组合视频…")
            concat_parts(directory, part_names, "topic-combined.mp4")
            combined = {"file": "topic-combined.mp4", "state": "completed", "error": None}
        return {"items": items, "combined": combined}
    finally:
        for png in shape_pngs:
            png.unlink(missing_ok=True)
        if mode == "combined":
            for name in part_names:
                (directory / name).unlink(missing_ok=True)

