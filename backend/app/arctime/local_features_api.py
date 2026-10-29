"""本地定制功能路由：术语表、内容切片、切片视频、图形绘制、手动终止、旧版字幕样式与烧录合成、调试端点。

这些端点是本地分支独有功能，集中挂载避免改动上游 gui.py 主体。
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Literal
from urllib.parse import unquote

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

from app.arctime import (automation, bilibili_auth, clip_words, danmaku, danmaku_fetch, danmaku_render,
                         glossary, media, publish, recorder, topic_segments, topic_video, translation,
                         workflow)
from app.arctime import subtitle_style_legacy as legacy_style


class DanmakuInput(BaseModel):
    """切片弹幕烧录参数：字号按 1080p 画布基准，高度为弹幕区域占画面高度的百分比。"""

    enabled: bool = True
    font_size: int = Field(default=40, ge=12, le=96)
    area_height: int = Field(default=60, ge=10, le=100)

    def style(self) -> danmaku_render.DanmakuStyle | None:
        if not self.enabled:
            return None
        return danmaku_render.DanmakuStyle(font_size=self.font_size, area_height=self.area_height)


class TopicClipsInput(BaseModel):
    indices: list[int] = Field(min_length=1, max_length=100)
    mode: Literal["separate", "combined"] = "separate"
    variant: Literal["bilingual", "zh", "original"] = "bilingual"
    danmaku: DanmakuInput | None = None


class BurnInput(BaseModel):
    clip: str = Field(max_length=255)
    variant: Literal["bilingual", "zh", "original"] = "bilingual"
    # 填写起止秒数时，只合成原视频的这一段（clip 仍传原视频文件名）
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, gt=0)
    danmaku: DanmakuInput | None = None


class TranslationEditInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class JobIdsInput(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)


class DanmakuFetchInput(BaseModel):
    url: str | None = Field(default=None, max_length=8192)


class RoomInput(BaseModel):
    room: str = Field(min_length=1, max_length=200)
    name: str = Field(default="", max_length=60)
    auto_run: bool = True


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    enabled: bool | None = None
    auto_run: bool | None = None


class RecorderSettingsInput(BaseModel):
    record_path: str | None = Field(default=None, max_length=500)


class AutomationTaskInput(BaseModel):
    url: str = Field(min_length=1, max_length=8192)
    title: str = Field(default="", max_length=120)
    template_id: str | None = None
    config: automation.AutomationConfig | None = None


class AutomationTemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    config: automation.AutomationConfig | None = None


# ---- 管理器辅助（附加到 JobManager 实例，避免改动上游类定义）----

def _ensure_manager_extras(manager) -> None:
    if not hasattr(manager, "topic_clipping"):
        manager.topic_clipping = set()
    if not hasattr(manager, "burning"):
        manager.burning = set()
    if not hasattr(manager, "_storage_cache"):
        manager._storage_cache = None
    if not hasattr(manager, "recorder"):
        manager.recorder = recorder.RecorderService(manager)
    if not hasattr(manager, "automation_thread"):
        manager.automation_thread = None


def _clip_words(manager) -> clip_words.Lexicon:
    """读取数据目录的合规风险词覆盖表，缺失时用内置词表。"""
    return clip_words.load(manager.root / "clip_words.json")


def _vocab_root(manager) -> Path:
    """主播热词画像目录：按 UP 主分别累积本场提取的高分词汇。"""
    return manager.root / "streamers"


def _style_path(manager) -> Path:
    return manager.root / "style.json"


def load_style_store(manager) -> legacy_style.StyleStore:
    return legacy_style.load_style_store(_style_path(manager))


def save_style_store(manager, store: legacy_style.StyleStore) -> None:
    path = _style_path(manager)
    if path.is_symlink():
        raise HTTPException(409, "样式配置不能是符号链接，请检查 style.json")
    try:
        media.write_json(path, store.model_dump(mode="json"))
    except OSError:
        raise HTTPException(500, "样式配置保存失败，请检查数据目录权限后重试") from None


def load_glossary_store(manager) -> glossary.GlossaryStore:
    return glossary.load_glossary(manager.root / "glossary.json")


def save_glossary_store(manager, store: glossary.GlossaryStore) -> None:
    path = manager.root / "glossary.json"
    if path.is_symlink():
        raise HTTPException(409, "术语表不能是符号链接，请检查 glossary.json")
    try:
        media.write_json(path, store.model_dump(mode="json"))
    except OSError:
        raise HTTPException(500, "术语表保存失败，请检查数据目录权限后重试") from None


def read_topic_clips(manager, directory: Path) -> dict:
    path = directory / "topic_clips.json"
    try:
        if path.is_symlink() or not path.is_file():
            return {"state": "not_started"}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"state": "not_started"}
    if not isinstance(value, dict) or (not isinstance(value.get("items"), list) and value.get("state") != "stale"):
        return {"state": "not_started"}
    return value


def _safe_filename(text: str, fallback: str) -> str:
    """把投稿标题净化为合法文件名：去掉 Windows 非法字符，控制长度。"""
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", text).strip(" .")
    return cleaned[:60] or fallback


def submit_topic_clips(manager, job_id: str, indices: list[int], mode: str, variant: str,
                       danmaku_style: danmaku_render.DanmakuStyle | None = None) -> dict:
    _ensure_manager_extras(manager)
    directory = manager.directory(job_id)
    job = manager.read_json(directory / "job.json")
    if job.get("state") != "completed" or not (directory / "source.mp4").is_file():
        raise HTTPException(409, "请等待视频任务完成后再生成切片视频")
    stored = topic_segments.read_store(directory)
    identity = topic_segments.current_identity(directory)
    if (stored is None or stored.get("state") != "completed"
            or identity is None or stored.get("identity") != identity):
        raise HTTPException(409, "请先生成（或重新生成）内容切片，再生成切片视频")
    try:
        topic_store = topic_segments.TopicSegmentStore.model_validate(stored)
    except ValueError:
        raise HTTPException(409, "内容切片结果已损坏，请重新生成") from None
    segments = topic_store.segments
    normalized: list[int] = []
    for index in indices:
        if not isinstance(index, int) or not 0 <= index < len(segments) or index in normalized:
            raise HTTPException(400, "包含无效或重复的切片编号")
        normalized.append(index)
    # 保留客户端给定的顺序：组合视频按用户的点击选择顺序合并
    # 保留上一轮分别生成的段产物（独立资产，组合生成不应让它们从界面消失）
    previous = read_topic_clips(manager, directory)
    legacy_files = {
        item["index"]: item["file"]
        for item in previous.get("items", [])
        if isinstance(item, dict) and item.get("state") == "completed"
        and isinstance(item.get("file"), str) and (directory / item["file"]).is_file()
    }
    if variant in {"bilingual", "zh"}:
        if manager.read_json(directory / "translation.json").get("state") != "completed":
            raise HTTPException(409, "请先生成中日双语字幕，或选择烧录仅原文字幕")
        translation.ensure_zh_srt(directory)
        if not (directory / "subtitles.zh.srt").is_file():
            raise HTTPException(409, "译文字幕缺失，无法合成；请重新生成双语字幕")
    with manager.lock:
        if job_id in manager.topic_clipping:
            raise HTTPException(409, "切片视频正在生成中，请等待完成")
        manager.topic_clipping.add(job_id)
        state_record = {
            "state": "running", "mode": mode, "variant": variant, "indices": normalized,
            "done": 0, "total": len(normalized), "message": "正在准备生成切片视频…",
            "error": None, "items": [], "combined": None, "created_at": time.time(),
        }
        media.write_json(directory / "topic_clips.json", state_record)
    manager.executor.submit(run_topic_clips, manager, job_id, normalized, mode, variant, legacy_files,
                            danmaku_style)
    return state_record


def run_topic_clips(manager, job_id: str, indices: list[int], mode: str, variant: str,
                    legacy_files: dict | None = None,
                    danmaku_style: danmaku_render.DanmakuStyle | None = None) -> None:
    directory = manager.directory(job_id)

    def write(**changes) -> None:
        with manager.lock:
            record = read_topic_clips(manager, directory)
            record.update(changes)
            media.write_json(directory / "topic_clips.json", record)

    try:
        stored = topic_segments.read_store(directory)
        topic_store = topic_segments.TopicSegmentStore.model_validate(stored)
        segments = [segment.model_dump() for segment in topic_store.segments]

        def progress(done: int, total: int, message: str) -> None:
            write(done=done, message=message)

        result = topic_video.generate(directory, segments, indices, mode, variant,
                                      load_style_store(manager), progress,
                                      danmaku_style=danmaku_style)
        # 合并历史段产物：本次未涉及的段保留；组合模式下各段继承最近一次独立产物
        merged: dict[int, dict] = {item["index"]: item for item in result.get("items", [])}
        for legacy_index, legacy_file in (legacy_files or {}).items():
            if not isinstance(legacy_file, str) or not (directory / legacy_file).is_file():
                continue
            current = merged.get(legacy_index)
            if current is None:
                merged[legacy_index] = {"index": legacy_index, "file": legacy_file,
                                        "state": "completed", "error": None}
            elif mode == "combined" and current.get("file") is None and current.get("state") == "completed":
                current["file"] = legacy_file
        result["items"] = [merged[key] for key in sorted(merged)]
        failed = [item for item in result["items"] if item.get("state") == "failed"]
        if mode == "separate" and failed:
            write(state="failed", done=len(indices),
                  message=f"完成 {len(indices) - len(failed)}/{len(indices)} 段",
                  error=f"{len(failed)} 个切片生成失败：" + "；".join((item.get("error") or "")[:120] for item in failed[:2]),
                  **result)
        else:
            write(state="completed", done=len(indices), message="切片视频生成完成", **result)
    except Exception as exc:
        error = "切片视频生成超时，请重试" if isinstance(exc, subprocess.TimeoutExpired) else str(exc)[:300]
        write(state="failed", error=error, message="切片视频生成失败")
    finally:
        with manager.lock:
            manager.topic_clipping.discard(job_id)


# ---- 旧版字幕样式与烧录合成 ----

def _validate_style(config: legacy_style.SubtitleStyleConfig) -> legacy_style.SubtitleStyleConfig:
    try:
        config.original.validate_font()
        config.translated.validate_font()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return config


def read_burns(directory: Path) -> dict:
    path = directory / "burn.json"
    try:
        if path.is_symlink() or not path.is_file():
            return {"clips": {}}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"clips": {}}
    return value if isinstance(value, dict) and isinstance(value.get("clips"), dict) else {"clips": {}}


# 分段合成的每段秒数。分段编码后才能显示精确进度，并在中断后只补没跑完的段继续合成
# （被中断的 mp4 没有 moov 索引，无法在旧文件上接着写，只能靠分段续跑）
BURN_SEGMENT_SECONDS = 300

# 编码器选择：N 卡装上较新驱动后 NVENC 可用，实测比 CPU 的 x264 快约 2~3 倍（瓶颈在字幕烧录/解码，
# 所以只加分段并行没用，把编码甩给 GPU 才有效）。探测结果缓存复用；一旦运行中出错就降级到 x264，
# 避免同一次长任务被硬件编码问题反复卡住。
_NVENC_ARGS = ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", "26"]
_X264_ARGS = ["-c:v", "libx264", "-crf", "18", "-preset", "fast"]
_encoder_cache: list[str] | None = None
_encoder_lock = threading.Lock()


def _probe_nvenc() -> bool:
    """用一帧黑画面真正初始化一次 NVENC 编码器，能跑通才算可用（驱动过旧会在此暴露）。"""
    try:
        probe = subprocess.run(
            [media.tool_path("ffmpeg"), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "color=c=black:s=320x240:d=0.1", "-frames:v", "1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


def video_encoder_args() -> list[str]:
    global _encoder_cache
    with _encoder_lock:
        if _encoder_cache is None:
            _encoder_cache = list(_NVENC_ARGS) if _probe_nvenc() else list(_X264_ARGS)
        return list(_encoder_cache)


def video_encoder_name(args: list[str]) -> str:
    return args[args.index("-c:v") + 1]


def _downgrade_encoder() -> None:
    global _encoder_cache
    with _encoder_lock:
        _encoder_cache = list(_X264_ARGS)


def _burn_parts_dir(directory: Path, clip_name: str, variant: str) -> Path:
    return workflow._path(directory, f".{Path(clip_name).stem}.burn.{variant}.parts")


def _segment_cues(cues, translated: list[str] | None, seg_start: float, seg_len: float):
    """截取落在本段区间内的字幕，并把时间轴平移成段内相对时间（供局部时间轴 ASS 使用）。"""
    seg_end = seg_start + seg_len
    picked = [(cue, translated[index] if translated is not None else None)
              for index, cue in enumerate(cues)
              if cue.end_seconds > seg_start and cue.start_seconds < seg_end]
    seg_cues = [media.SubtitleSegment(str(order + 1), max(cue.start_seconds, seg_start) - seg_start,
                                      min(cue.end_seconds, seg_end) - seg_start, cue.text)
                for order, (cue, _) in enumerate(picked)]
    seg_translated = [text for _, text in picked] if translated is not None else None
    return seg_cues, seg_translated


def _range_bounds(clip_name: str) -> tuple[float, float] | None:
    """自定义时间段合成的记录键：range-<起点毫秒>-<终点毫秒>。"""
    match = re.fullmatch(r"range-(\d+)-(\d+)", clip_name)
    if not match:
        return None
    return int(match.group(1)) / 1000, int(match.group(2)) / 1000


def _danmaku_signature(style: danmaku_render.DanmakuStyle | None) -> str | None:
    """弹幕设置指纹：分段续跑时若弹幕参数变化，已编码的分段必须作废重编。"""
    return None if style is None else f"{style.font_size}x{style.area_height}"


def submit_burn(manager, job_id: str, clip_name: str, variant: str,
                start: float | None = None, end: float | None = None,
                danmaku_style: danmaku_render.DanmakuStyle | None = None) -> dict:
    _ensure_manager_extras(manager)
    directory = manager.directory(job_id)
    job = manager.read_json(directory / "job.json")
    if job.get("state") != "completed":
        raise HTTPException(409, "请等待视频任务完成后再合成")
    is_source = bool(job.get("video")) and clip_name == job.get("video")
    custom = start is not None or end is not None
    if custom:
        if not is_source:
            raise HTTPException(409, "只有完整视频可以按时间段合成")
        if start is None or end is None:
            raise HTTPException(422, "请同时填写起始与结束时间")
        duration = float(job.get("duration") or 0)
        if not (0 <= start < end <= duration + 0.05):
            raise HTTPException(422, f"时间范围需在 0 到 {duration:.1f} 秒之间，且起点早于终点")
        clip_name = f"range-{int(round(start * 1000))}-{int(round(end * 1000))}"
    if not is_source and _range_bounds(clip_name) is None \
            and not any(c["video"] == clip_name for c in job.get("completed_clips", [])):
        raise HTTPException(404, "切片不存在")
    if (is_source or custom) and not (directory / (job.get("video") or "")).is_file():
        raise HTTPException(409, "原视频缺失，无法合成；请重新创建任务")
    if variant in {"bilingual", "zh"}:
        if manager.read_json(directory / "translation.json").get("state") != "completed":
            raise HTTPException(409, "请先生成中日双语字幕")
        translation.ensure_zh_srt(directory)
    file = f"{Path(clip_name).stem}.burn.{variant}.mp4"
    with manager.lock:
        key = (job_id, clip_name, variant)
        if key in manager.burning:
            raise HTTPException(409, "该切片正在合成中，请稍候")
        burns = read_burns(directory)
        previous = burns["clips"].setdefault(clip_name, {}).get(variant) or {}
        signature = _danmaku_signature(danmaku_style)
        entry: dict = {"state": "burning", "file": file, "error": None, "danmaku": signature}
        if (previous.get("state") != "completed" and int(previous.get("segments_done") or 0) > 0
                and previous.get("danmaku") == signature):
            # 上次中断且已完成至少一段：保留进度，实现断点续跑
            entry["progress"] = previous.get("progress", 0.0)
            entry["segments_done"] = previous.get("segments_done")
            entry["segments_total"] = previous.get("segments_total")
            entry["encoder"] = previous.get("encoder")
        else:
            # 重新合成：清掉上次留下的分段文件，从头开始
            parts = _burn_parts_dir(directory, clip_name, variant)
            if parts.is_dir() and not parts.is_symlink():
                shutil.rmtree(parts, ignore_errors=True)
        burns["clips"][clip_name][variant] = entry
        media.write_json(directory / "burn.json", burns)
        manager.burning.add(key)
    manager.executor.submit(run_burn, manager, job_id, clip_name, variant, danmaku_style)
    return {"file": file, "state": "burning"}


def _encode_burn_segment(directory: Path, stem: str, source_name: str, variant: str, style, shape_pngs: list[Path],
                         cues, translated: list[str] | None, seg_index: int, seg_start: float,
                         seg_len: float, part: Path, encoder_args: list[str], on_progress,
                         source_offset: float = 0.0, danmaku_entries: list | None = None,
                         danmaku_style: danmaku_render.DanmakuStyle | None = None,
                         danmaku_offset: float = 0.0) -> None:
    """编码单个分段：局部时间轴 ASS + 图形 overlay，输出自包含的 part mp4（首帧为关键帧，便于 -c copy 拼接）。

    danmaku_offset 为本段在原始视频时间轴上的起点，用于截取对应的弹幕时间窗。
    """
    seg_cues, seg_translated = _segment_cues(cues, translated, seg_start, seg_len)
    # ASS 放在任务目录下（而非分段子目录），subtitles 滤镜按 cwd 相对文件名解析才能找到它
    seg_ass = workflow._path(directory, f".{stem}.burn.{variant}.part{seg_index:04d}.ass")
    workflow._publish_text(seg_ass, legacy_style.render_ass(seg_cues, seg_translated, style, variant))
    dm_ass = None
    if danmaku_entries and danmaku_style is not None:
        content = danmaku_render.build_ass(danmaku_entries,
                                           start=danmaku_offset + seg_start,
                                           end=danmaku_offset + seg_start + seg_len,
                                           style=danmaku_style)
        if content:
            dm_ass = workflow._path(directory, f".{stem}.burn.{variant}.part{seg_index:04d}.dm.ass")
            workflow._publish_text(dm_ass, content)
    # 弹幕层放在字幕层之前，保证弹幕在字幕下方
    filters = ([f"subtitles={dm_ass.name}"] if dm_ass is not None else []) + [f"subtitles={seg_ass.name}"]
    # ffmpeg 以 cwd=任务目录 运行，输出需带上分段子目录的相对路径
    part_arg = f"{part.parent.name}/{part.name}"
    cmd = [media.tool_path("ffmpeg"), "-hide_banner", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
           "-ss", f"{source_offset + seg_start:.3f}", "-t", f"{seg_len:.3f}", "-i", source_name]
    if shape_pngs:
        # 矩形图形按视频实际分辨率渲染为透明 PNG，overlay 叠加在字幕下层
        for png in shape_pngs:
            cmd += ["-loop", "1", "-i", png.name]
        chain = ""
        previous = "0:v"
        for shape_index in range(len(shape_pngs)):
            chain += f"[{previous}][{shape_index + 1}:v]overlay=0:0[s{shape_index}];"
            previous = f"s{shape_index}"
        cmd += ["-filter_complex", f"{chain}[{previous}]" + ",".join(filters)]
    else:
        cmd += ["-vf", ",".join(filters)]
    # 音频必须重编码：-c:a copy 在输入 seek 下各段音频帧数不齐（259/517/419），拼接处会丢音/多音；
    # 且不能加 -avoid_negative_ts make_zero——它会把每段首帧 PTS 顶到 seg_start，导致拼接总时长虚高
    cmd += [*encoder_args, "-c:a", "aac", "-b:a", "192k", "-shortest", part_arg]
    part.unlink(missing_ok=True)
    err_path = part.with_suffix(".err")
    timed_out = threading.Event()

    def _kill() -> None:
        timed_out.set()
        proc.kill()

    try:
        with open(err_path, "w", encoding="utf-8") as err_file:
            proc = subprocess.Popen(cmd, cwd=directory, stdout=subprocess.PIPE, stderr=err_file, text=True, bufsize=1)
            guard = threading.Timer(max(900.0, seg_len * 8), _kill)
            guard.daemon = True
            guard.start()
            try:
                for line in proc.stdout or []:
                    if not line.startswith("out_time_us="):
                        continue
                    try:
                        seconds = int(line.strip().split("=", 1)[1]) / 1_000_000
                    except ValueError:
                        continue
                    on_progress(seg_index, min(1.0, max(0.0, seconds / seg_len)))
                code = proc.wait()
            finally:
                guard.cancel()
        if timed_out.is_set():
            raise TimeoutError(f"第 {seg_index + 1} 段编码超时")
        if code != 0 or not part.is_file():
            try:
                tail = err_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
            except OSError:
                tail = []
            raise ValueError(f"第 {seg_index + 1} 段合成失败：{tail[-1] if tail else '未知错误'}")
    finally:
        err_path.unlink(missing_ok=True)
        seg_ass.unlink(missing_ok=True)
        if dm_ass is not None:
            dm_ass.unlink(missing_ok=True)


def run_burn(manager, job_id: str, clip_name: str, variant: str,
             danmaku_style: danmaku_render.DanmakuStyle | None = None) -> None:
    directory = manager.directory(job_id)
    stem = Path(clip_name).stem
    file = f"{stem}.burn.{variant}.mp4"
    parts_dir = _burn_parts_dir(directory, clip_name, variant)
    shape_pngs: list[Path] = []
    encoder_args = video_encoder_args()

    def record(state: str, error: str | None = None, *, done: int | None = None,
               total: int | None = None, progress: float | None = None) -> None:
        with manager.lock:
            burns = read_burns(directory)
            entry: dict = dict(burns["clips"].setdefault(clip_name, {}).get(variant) or {})
            entry["state"] = state
            entry["error"] = error
            entry["file"] = file if state == "completed" else None
            entry["encoder"] = video_encoder_name(encoder_args)
            entry["danmaku"] = _danmaku_signature(danmaku_style)
            if done is not None:
                entry["segments_done"] = done
            if total is not None:
                entry["segments_total"] = total
            if progress is not None:
                entry["progress"] = round(max(0.0, min(1.0, progress)), 4)
            if state == "completed":
                entry["progress"] = 1.0
                entry["sha256"] = media.fingerprint(directory / file)
            burns["clips"][clip_name][variant] = entry
            media.write_json(directory / "burn.json", burns)

    try:
        job = json.loads(workflow._path(directory, "job.json").read_text())
        cues = media.read_subtitles(workflow._path(directory, job["subtitles"]))
        source_name = clip_name
        source_offset = 0.0
        clip_zh = False
        bounds = _range_bounds(clip_name)
        if clip_name == job.get("video"):
            # 完整视频：用整段字幕与原片时长，不走切片偏移
            start, end = 0.0, float(job.get("duration") or 0)
            zh_name = "subtitles.zh.srt"
            if end <= 0:
                raise ValueError("无法读取原视频时长，合成已取消")
        elif bounds is not None:
            # 自定义时间段：原视频取这一段，字幕按同区间裁剪
            start, end = bounds
            source_name = job.get("video") or ""
            source_offset = start  # 原视频从 0 开始，分段起点要加上区间偏移
            cues = media.clip_subtitles(cues, start, end)
            zh_name = "subtitles.zh.srt"
            clip_zh = True
        else:
            index = next(i for i, c in enumerate(job["completed_clips"]) if c["video"] == clip_name)
            selection = job["selection"][index]
            start, end = float(selection["start"]), float(selection["end"])
            cues = media.clip_subtitles(cues, start, end)
            zh_name = f"{stem}.zh.srt"
        translated: list[str] | None = None
        if variant in {"bilingual", "zh"}:
            zh_path = workflow._path(directory, zh_name)
            if not zh_path.is_file():
                translation.ensure_zh_srt(directory)
            if not zh_path.is_file():
                raise ValueError("译文字幕缺失，无法合成；请重新生成双语字幕")
            translated_cues = media.read_subtitles(zh_path)
            if clip_zh:
                translated_cues = media.clip_subtitles(translated_cues, start, end)
            translated = [c.text for c in translated_cues]
            if len(translated) != len(cues):
                raise ValueError("译文数量与字幕不匹配，无法合成；请重新生成双语字幕")
        style_store = load_style_store(manager)
        style = style_store.current
        dm_entries: list = []
        if danmaku_style is not None:
            dm_store = danmaku.read_store(directory) or {}
            dm_entries = [item for item in (dm_store.get("entries") or []) if isinstance(item, list)]
        output = workflow._path(directory, file)
        duration = max(1.0, end - start)
        total = max(1, math.ceil(duration / BURN_SEGMENT_SECONDS))
        if style_store.shapes:
            probe = subprocess.run(
                [media.tool_path("ffprobe"), "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0", source_name],
                cwd=directory, capture_output=True, text=True, timeout=60, check=False)
            dims = probe.stdout.strip().split(",")
            if probe.returncode != 0 or len(dims) != 2 or not all(p.isdigit() for p in dims):
                raise ValueError("无法读取视频分辨率，合成已取消")
            shape_pngs = legacy_style.render_shape_pngs(style_store.shapes, directory, stem,
                                                        width=int(dims[0]), height=int(dims[1]))
        parts_dir.mkdir(exist_ok=True)
        with manager.lock:
            previous = read_burns(directory)["clips"].get(clip_name, {}).get(variant) or {}
        # 断点续跑：沿用上次已完成的段数（段按顺序编码，中断处之后的段需重做）
        done = int(previous.get("segments_done") or 0)
        if previous.get("segments_total") not in (None, total):
            done = 0  # 分段数变化，旧分段不可复用
        if done > 0 and previous.get("encoder") != video_encoder_name(encoder_args):
            done = 0  # 编码器变了（如 NVENC 失败后降级），分段混用会让 -c copy 拼接失败，只能重头来
        if done > 0 and previous.get("danmaku") != _danmaku_signature(danmaku_style):
            done = 0  # 弹幕设置变了，旧分段里没有/不是当前的弹幕样式，必须重编
        part_files = [parts_dir / f"part{i:04d}.mp4" for i in range(total)]
        while done > 0 and not part_files[done - 1].is_file():
            done -= 1
        for stale in part_files[done:]:
            stale.unlink(missing_ok=True)
        record("burning", done=done, total=total, progress=done / total)
        for seg_index in range(done, total):
            seg_start = seg_index * BURN_SEGMENT_SECONDS
            seg_len = min(float(BURN_SEGMENT_SECONDS), duration - seg_start)
            _encode_burn_segment(directory, stem, source_name, variant, style, shape_pngs, cues, translated,
                                 seg_index, seg_start, seg_len, part_files[seg_index], encoder_args,
                                 lambda idx, ratio: record("burning", done=idx, total=total,
                                                           progress=(idx + ratio) / total),
                                 source_offset=source_offset, danmaku_entries=dm_entries,
                                 danmaku_style=danmaku_style, danmaku_offset=start)
            record("burning", done=seg_index + 1, total=total, progress=(seg_index + 1) / total)
        # 所有分段完成后 -c copy 直接拼接（不重新编码，很快），再删掉中间分段
        list_path = workflow._path(directory, f".{stem}.burn.{variant}.concat.txt")
        workflow._publish_text(list_path, "\n".join(
            f"file '{parts_dir.name}/part{i:04d}.mp4'" for i in range(total)) + "\n")
        result = subprocess.run(
            [media.tool_path("ffmpeg"), "-hide_banner", "-y", "-f", "concat", "-safe", "0",
             "-i", list_path.name, "-c", "copy", "-movflags", "+faststart", file],
            cwd=directory, capture_output=True, text=True, timeout=1800, check=False)
        list_path.unlink(missing_ok=True)
        if result.returncode != 0 or not output.is_file():
            tail = (result.stderr or "").strip().splitlines()
            raise ValueError(f"视频拼接失败：{tail[-1] if tail else '未知错误'}")
        shutil.rmtree(parts_dir, ignore_errors=True)
        record("completed", done=total, total=total)
    except TimeoutError as exc:
        record("failed", f"{exc}；可点击「继续合成视频」接着跑")
    except Exception as exc:
        if video_encoder_name(encoder_args) == "h264_nvenc":
            # 硬件编码报错：降级到 x264，用户点「继续合成视频」时会自动用 CPU 重跑
            _downgrade_encoder()
        record("failed", str(exc)[:300])
    finally:
        for png in shape_pngs:
            try:
                png.unlink(missing_ok=True)
            except OSError:
                pass
        with manager.lock:
            manager.burning.discard((job_id, clip_name, variant))


# ---- 任务记录占用统计与清理 ----
#
# 单个任务目录里体积最大的是可重新生成的合成/切片视频（*.burn.*.mp4、topic-*.mp4），
# 其次是原视频 source.mp4。因此提供两级操作：
#   清理产物：只删可重新生成的视频产物与中断残留，保留原视频、切片原片、字幕与翻译；
#   彻底删除：连同任务记录、原视频与全部结果一起删除。

# 目录遍历只统计大小、不读取内容；结果缓存 20 秒，避免任务列表轮询反复扫盘。
_STORAGE_TTL = 20.0


def _job_ids(manager) -> set[str]:
    return {p.name for p in manager.root.iterdir()
            if p.is_dir() and not p.is_symlink() and re.fullmatch(r"[0-9a-f]{12}", p.name)}


def _walk_size(path: Path) -> int:
    """统计文件/目录真实占用，不跟随符号链接。"""
    if path.is_symlink():
        return 0
    try:
        if path.is_file():
            return path.stat().st_size
    except OSError:
        return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            item = Path(root) / name
            try:
                if not item.is_symlink():
                    total += item.stat().st_size
            except OSError:
                continue
    return total


def _cleanable(manager, directory: Path) -> tuple[list[Path], list[Path]]:
    """可安全清理的产物文件与临时目录（保留 source.mp4、切片原片、字幕与翻译）。"""
    files: list[Path] = []
    dirs: list[Path] = []
    seen: set[str] = set()

    def add_file(name) -> None:
        if not isinstance(name, str) or Path(name).name != name or name in seen:
            return
        seen.add(name)
        path = directory / name
        if path.is_file() and not path.is_symlink():
            files.append(path)

    # 合成视频（*.burn.*.mp4）
    for variants in read_burns(directory).get("clips", {}).values():
        if isinstance(variants, dict):
            for entry in variants.values():
                if isinstance(entry, dict):
                    add_file(entry.get("file"))
    # 切片视频（topic-NN.mp4 / topic-combined.mp4）
    topic_clips = read_topic_clips(manager, directory)
    for item in topic_clips.get("items", []):
        if isinstance(item, dict):
            add_file(item.get("file"))
    if isinstance(topic_clips.get("combined"), dict):
        add_file(topic_clips["combined"].get("file"))
    # 中断残留：编码临时目录、分段目录、拼接清单、错误输出与中间 ASS
    for child in directory.iterdir():
        if child.is_symlink():
            continue
        name = child.name
        if child.is_dir():
            if name.startswith(".encoding-") or name.endswith(".parts"):
                dirs.append(child)
        elif name.endswith(".concat.txt") or name.endswith(".err") or (name.startswith(".") and name.endswith(".ass")):
            files.append(child)
    return files, dirs


def _reset_products(manager, directory: Path, removed: set[str]) -> None:
    """产物被清理后复位登记，界面恢复为可重新合成/生成。"""
    burns = read_burns(directory)
    changed = False
    for variants in burns.get("clips", {}).values():
        if not isinstance(variants, dict):
            continue
        for variant, entry in list(variants.items()):
            if isinstance(entry, dict) and entry.get("file") in removed:
                del variants[variant]
                changed = True
    if changed:
        media.write_json(directory / "burn.json", burns)
    topic = read_topic_clips(manager, directory)
    if topic.get("state") != "not_started":
        items = [item for item in topic.get("items", [])
                 if not (isinstance(item, dict) and item.get("file") in removed)]
        combined = topic.get("combined")
        if isinstance(combined, dict) and combined.get("file") in removed:
            combined = None
        if items != topic.get("items") or combined != topic.get("combined"):
            topic["items"] = items
            topic["combined"] = combined
            media.write_json(directory / "topic_clips.json", topic)


def _reject_busy(manager, job_id: str) -> None:
    _ensure_manager_extras(manager)
    with manager.lock:
        if manager.active and manager.active.get("id") == job_id:
            raise HTTPException(409, "任务正在处理中，无法清理或删除")
        if job_id in manager.topic_clipping:
            raise HTTPException(409, "切片视频正在生成中，无法清理或删除")
        if any(key[0] == job_id for key in manager.burning):
            raise HTTPException(409, "合成视频正在生成中，无法清理或删除")


def job_storage(manager, job_id: str) -> dict:
    directory = manager.directory(job_id)
    if not directory.is_dir():
        return {"total": 0, "cleanable": 0}
    files, dirs = _cleanable(manager, directory)
    return {"total": _walk_size(directory),
            "cleanable": sum(_walk_size(item) for item in (*files, *dirs))}


def storage_snapshot(manager) -> dict:
    _ensure_manager_extras(manager)
    cache = manager._storage_cache
    if cache and time.time() - cache[0] < _STORAGE_TTL:
        return cache[1]
    jobs = {}
    for job_id in _job_ids(manager):
        try:
            jobs[job_id] = job_storage(manager, job_id)
        except (HTTPException, OSError):
            continue
    snapshot = {"jobs": jobs,
                "total": sum(item["total"] for item in jobs.values()),
                "cleanable": sum(item["cleanable"] for item in jobs.values())}
    manager._storage_cache = (time.time(), snapshot)
    return snapshot


def cleanup_job(manager, job_id: str) -> dict:
    directory = manager.directory(job_id)
    if not directory.is_dir():
        raise HTTPException(404, "任务不存在")
    _reject_busy(manager, job_id)
    files, dirs = _cleanable(manager, directory)
    freed = 0
    for path in files:
        size = _walk_size(path)
        try:
            path.unlink()
        except OSError:
            continue
        freed += size
    for path in dirs:
        freed += _walk_size(path)
        shutil.rmtree(path, ignore_errors=True)
    _reset_products(manager, directory, {path.name for path in files})
    return {"id": job_id, "freed": freed}


def delete_job(manager, job_id: str) -> dict:
    directory = manager.directory(job_id)
    if not directory.is_dir():
        raise HTTPException(404, "任务不存在")
    _reject_busy(manager, job_id)
    freed = _walk_size(directory)
    shutil.rmtree(directory, ignore_errors=True)
    with manager.lock:
        if manager.last and manager.last.get("id") == job_id:
            manager.last = None
    return {"id": job_id, "freed": freed}


def run_batch(manager, ids: list[str], action) -> dict:
    results = []
    for job_id in ids:
        try:
            results.append({**action(manager, job_id), "ok": True})
        except HTTPException as exc:
            results.append({"id": job_id, "ok": False, "freed": 0, "error": exc.detail})
    with manager.lock:
        manager._storage_cache = None
    return {"results": results, "freed": sum(item["freed"] for item in results)}


# ---- 路由 ----

def local_features_router(manager) -> APIRouter:
    _ensure_manager_extras(manager)
    router = APIRouter(prefix="/companion-api")

    @router.get("/debug/paths")
    def debug_paths():
        import app as app_pkg
        return {"gui_file": str(Path(__file__).resolve()),
                "app_package": str(Path(app_pkg.__file__).resolve()),
                "sys_executable": sys.executable,
                "cwd": str(Path.cwd()),
                "data_root": str(manager.root),
                "sys_path_head": sys.path[:5]}

    @router.get("/jobs-debug")
    def list_jobs_debug():
        import re
        ids = {p.name for p in manager.root.iterdir() if p.is_dir() and not p.is_symlink() and re.fullmatch(r"[0-9a-f]{12}", p.name)}
        with manager.lock:
            if manager.active:
                ids.add(manager.active["id"])
            if manager.last:
                ids.add(manager.last["id"])
        results = []
        for job_id in sorted(ids):
            try:
                job_json = manager.read_json(manager.directory(job_id) / "job.json")
                ver = job_json.get("version", 2)
                if ver != 2:
                    results.append({"id": job_id, "status": "skip_version", "version": ver})
                    continue
                r = manager.detail(job_id, include_segments=False)
                results.append({"id": job_id, "status": "ok", "state": r.get("state")})
            except Exception as e:
                results.append({"id": job_id, "status": "error", "type": type(e).__name__, "message": str(e)})
        return {"total": len(ids), "ok": sum(1 for r in results if r["status"] == "ok"), "results": results}

    @router.post("/jobs/{job_id}/cancel", status_code=202)
    def cancel_job(job_id: str):
        manager.cancel(job_id)
        return {"id": job_id, "state": "cancelling"}

    # ---- 任务记录占用统计与批量清理 ----

    @router.get("/storage")
    def get_storage():
        return storage_snapshot(manager)

    @router.post("/jobs/cleanup")
    def cleanup_jobs(payload: JobIdsInput):
        return run_batch(manager, payload.ids, cleanup_job)

    @router.post("/jobs/delete")
    def delete_jobs(payload: JobIdsInput):
        return run_batch(manager, payload.ids, delete_job)

    # ---- 内容切片 ----

    @router.get("/jobs/{job_id}/topic-segments")
    def get_topic_segments(job_id: str):
        directory = manager.directory(job_id)
        if not (directory / "job.json").is_file():
            raise HTTPException(404, "任务不存在")
        stored = topic_segments.read_store(directory)
        identity = topic_segments.current_identity(directory)
        if stored is None:
            return {"state": "not_started"}
        if identity is None or stored.get("identity") != identity or stored.get("state") != "completed":
            return {**stored, "state": "stale"}
        # 评分口径升级：旧任务按新公式就地重算，避免为此重新调用切片模型
        if stored.get("score_version") != danmaku.SCORE_VERSION and danmaku.read_store(directory):
            stored = danmaku.apply(directory, stored, words=_clip_words(manager), vocab_root=None)
        return stored

    @router.post("/jobs/{job_id}/topic-segments")
    def create_topic_segments(job_id: str, options: topic_segments.TopicAnalyzeOptions | None = None):
        directory = manager.directory(job_id)
        job = manager.read_json(directory / "job.json")
        if not job:
            raise HTTPException(404, "任务不存在")
        if job.get("state") != "completed":
            raise HTTPException(409, "请等待视频任务完成后再生成内容切片")
        if manager.config_error:
            raise HTTPException(409, "请先修复翻译配置，再生成内容切片")
        if not manager.api_key:
            raise HTTPException(409, "请先输入 DeepSeek API Key")
        translated = manager.read_json(directory / "translation.json")
        # 未翻译也能直接基于原文切分（不需要翻译的主播）；已翻译则自动用双语字幕
        if topic_segments.current_identity(directory) is None:
            raise HTTPException(409, "字幕文件缺失，请等待语音识别完成后再试")
        if job_id in manager.topic_clipping:
            raise HTTPException(409, "切片视频正在生成中，请等待完成后再重新分析")
        model = translated.get("identity", {}).get("model") or manager.translation_model
        # 首次生成内容切片时，按任务保留的来源链接自动拉一次弹幕；失败不阻断切片分析
        if not danmaku.read_store(directory):
            source_url = job.get("url")
            if source_url:
                try:
                    info, entries = danmaku_fetch.fetch(source_url)
                except Exception:
                    pass
                else:
                    danmaku.save_store(directory, "bilibili", entries,
                                       {"url": source_url, "title": info.get("title"),
                                        "cid": info.get("cid"), "owner_mid": info.get("owner_mid"),
                                        "owner_name": info.get("owner_name"), "fetched_at": time.time()})
        try:
            store = topic_segments.analyze_directory(directory, manager.api_key, model, options=options)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        # 内容切片已更新，旧切片视频的编号/边界可能错位，标记过期
        if read_topic_clips(manager, directory).get("state") != "not_started":
            media.write_json(directory / "topic_clips.json", {"state": "stale", "items": []})
        return danmaku.apply(directory, store.model_dump(mode="json"),
                             words=_clip_words(manager), build_audio=True,
                             vocab_root=_vocab_root(manager))

    # ---- 弹幕（浏览器插件导出的 ASS / XML）----

    @router.get("/jobs/{job_id}/danmaku")
    def get_danmaku(job_id: str):
        directory = manager.directory(job_id)
        if not (directory / "job.json").is_file():
            raise HTTPException(404, "任务不存在")
        return danmaku.summary(directory)

    @router.get("/jobs/{job_id}/danmaku/window")
    def get_danmaku_window(job_id: str, start: float, end: float):
        """预览用：取 [start, end) 时间窗内的弹幕，返回 [时间, 文本, 颜色] 紧凑数组。"""
        directory = manager.directory(job_id)
        if not (directory / "job.json").is_file():
            raise HTTPException(404, "任务不存在")
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
            raise HTTPException(400, "时间窗无效")
        span = min(float(end - start), 120.0)
        limit = start + span
        store = danmaku.read_store(directory) or {}
        entries = []
        for item in store.get("entries") or []:
            if not isinstance(item, list) or len(item) < 2:
                continue
            at = item[0]
            if not isinstance(at, (int, float)) or not start <= at < limit:
                continue
            color = item[5] if len(item) > 5 else None
            entries.append([at, item[1], color if isinstance(color, int) else None])
        return {"start": start, "end": limit, "entries": entries[:4000]}

    @router.post("/jobs/{job_id}/danmaku")
    async def upload_danmaku(job_id: str, request: Request):
        directory = manager.directory(job_id)
        if not (directory / "job.json").is_file():
            raise HTTPException(404, "任务不存在")
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > danmaku.MAX_FILE_BYTES:
            raise HTTPException(413, "弹幕文件过大（上限 64 MB）")
        body = await request.body()
        if not body:
            raise HTTPException(422, "请选择弹幕文件")
        if len(body) > danmaku.MAX_FILE_BYTES:
            raise HTTPException(413, "弹幕文件过大（上限 64 MB）")
        source, entries = danmaku.parse(body.decode("utf-8-sig", errors="replace"))
        if not entries:
            raise HTTPException(422, "未解析到弹幕，请确认导出的是 ASS 或 XML 弹幕文件")
        saved = danmaku.save_store(directory, source, entries)
        stored_topics = topic_segments.read_store(directory)
        topics = (danmaku.apply(directory, stored_topics, words=_clip_words(manager),
                                vocab_root=_vocab_root(manager)) if stored_topics else None)
        return {"count": saved["count"], "source": source, "topics": topics}

    # ---- B 站扫码登录（历史弹幕需要登录态） ----

    @router.get("/bilibili/auth")
    def bilibili_auth_status():
        return bilibili_auth.login_status()

    @router.post("/bilibili/login/qrcode", status_code=201)
    def bilibili_login_qrcode():
        try:
            return bilibili_auth.qr_code()
        except (bilibili_auth.LoginError, danmaku_fetch.UpstreamError) as exc:
            raise HTTPException(502, str(exc)) from None

    @router.get("/bilibili/login/qrcode/{key}")
    def bilibili_login_poll(key: str):
        try:
            return bilibili_auth.poll(key)
        except (bilibili_auth.LoginError, danmaku_fetch.UpstreamError) as exc:
            raise HTTPException(502, str(exc)) from None

    @router.delete("/bilibili/auth")
    def bilibili_logout():
        return bilibili_auth.logout()

    @router.post("/jobs/{job_id}/danmaku/fetch")
    def fetch_danmaku(job_id: str, payload: DanmakuFetchInput | None = None):
        directory = manager.directory(job_id)
        if not (directory / "job.json").is_file():
            raise HTTPException(404, "任务不存在")
        stored = danmaku.read_store(directory)
        url = (payload.url if payload else None) or (stored or {}).get("url")
        if not url:
            raise HTTPException(422, "请填写 B站视频链接或 BV 号")
        try:
            info, entries = danmaku_fetch.fetch(url)
        except danmaku_fetch.CookieMissing as exc:
            raise HTTPException(409, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except danmaku_fetch.UpstreamError as exc:
            raise HTTPException(502, str(exc)) from None
        except Exception as exc:
            raise HTTPException(502, f"弹幕拉取失败：{str(exc)[:200]}") from None
        saved = danmaku.save_store(directory, "bilibili", entries,
                                   {"url": url, "title": info.get("title"),
                                    "cid": info.get("cid"), "owner_mid": info.get("owner_mid"),
                                    "owner_name": info.get("owner_name"), "fetched_at": time.time()})
        topics = topic_segments.read_store(directory)
        topics = (danmaku.apply(directory, topics, words=_clip_words(manager),
                                vocab_root=_vocab_root(manager)) if topics else None)
        return {"count": saved["count"], "source": "bilibili",
                "title": info.get("title"), "topics": topics}

    @router.get("/jobs/{job_id}/topic-segments.txt")
    def topic_segments_text(job_id: str):
        directory = manager.directory(job_id)
        stored = topic_segments.read_store(directory)
        identity = topic_segments.current_identity(directory)
        if (stored is None or identity is None or stored.get("identity") != identity
                or stored.get("state") != "completed"):
            raise HTTPException(404, "内容切片不存在，请先生成")
        try:
            store = topic_segments.TopicSegmentStore.model_validate(stored)
        except ValueError:
            raise HTTPException(409, "内容切片结果已损坏，请重新生成") from None
        return Response(topic_segments.render_text(store), media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{job_id}-topic-segments.txt"'})

    # ---- 切片视频 ----

    @router.get("/jobs/{job_id}/topic-clips")
    def get_topic_clips(job_id: str):
        directory = manager.directory(job_id)
        record = read_topic_clips(manager, directory)
        with manager.lock:
            active = job_id in manager.topic_clipping
        if record.get("state") == "running" and not active:
            record = {**record, "state": "failed", "error": "切片视频生成已中断，请重新生成"}
        return record

    @router.post("/jobs/{job_id}/topic-clips", status_code=202)
    def create_topic_clips(job_id: str, payload: TopicClipsInput):
        return submit_topic_clips(manager, job_id, payload.indices, payload.mode, payload.variant,
                                  payload.danmaku.style() if payload.danmaku else None)

    @router.get("/jobs/{job_id}/topic-clips/{index}/bundle")
    def topic_clip_bundle(job_id: str, index: int):
        """打包下载切片：zip 内含「投稿标题/投稿标题.mp4 + 投稿标题.jpg」，解压即得同名文件夹。"""
        directory = manager.directory(job_id)
        record = read_topic_clips(manager, directory)
        item = next((row for row in record.get("items", [])
                     if isinstance(row, dict) and row.get("index") == index), None)
        if not item or item.get("state") != "completed" or not item.get("file"):
            raise HTTPException(404, "切片视频不存在，请先生成切片视频")
        video = manager.artifact(job_id, str(item["file"]))
        if not video.is_file():
            raise HTTPException(404, "切片视频文件已丢失，请重新生成")
        stored = topic_segments.read_store(directory) or {}
        segment = next((row for row in stored.get("segments", [])
                        if isinstance(row, dict) and row.get("index") == index), {})
        base = _safe_filename(str(segment.get("post_title") or ""), Path(item["file"]).stem)
        entries: list[tuple[Path, str]] = [(video, f"{base}/{base}.mp4")]
        cover_name = str(segment.get("cover") or "")
        if cover_name:
            cover = manager.artifact(job_id, cover_name)
            if cover.is_file():
                entries.append((cover, f"{base}/{base}.jpg"))
        tmp = tempfile.NamedTemporaryFile(prefix="nyaru-bundle-", suffix=".zip", delete=False)
        try:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as bundle:
                for path, arcname in entries:
                    bundle.write(path, arcname)
        finally:
            tmp.close()
        return FileResponse(tmp.name, media_type="application/zip", filename=f"{base}.zip",
                            background=BackgroundTask(os.unlink, tmp.name))

    # ---- B 站自动投稿（biliup）----

    @router.get("/publish")
    def get_publish_status():
        return publish.status(manager)

    @router.get("/publish/defaults")
    def get_publish_defaults():
        return publish.read_defaults(manager).model_dump(mode="json")

    @router.get("/publish/zones")
    def get_publish_zones():
        """B站投稿分区列表（在线获取并缓存，失败时用兜底列表）。"""
        return publish.zones(manager)

    @router.delete("/publish/{item_id}")
    def delete_publish_item(item_id: str):
        """删除投稿队列里的条目；正在上传的条目拒绝删除。"""
        try:
            return publish.remove_item(manager, item_id)
        except KeyError:
            raise HTTPException(404, "投稿条目不存在，可能已被删除") from None
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None

    @router.put("/publish/defaults")
    def put_publish_defaults(payload: publish.PublishDefaults):
        return publish.save_defaults(manager, payload).model_dump(mode="json")

    @router.post("/publish/credential/qrcode")
    def create_publish_qrcode():
        """扫码生成投稿凭据（TV 登录，含 access_token）。"""
        try:
            return bilibili_auth.tv_qr_code()
        except bilibili_auth.LoginError as exc:
            raise HTTPException(502, str(exc)) from None
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"获取投稿二维码失败：{exc}") from None

    @router.get("/publish/credential/qrcode/{key}")
    def poll_publish_qrcode(key: str):
        try:
            return bilibili_auth.tv_poll(key)
        except bilibili_auth.LoginError as exc:
            raise HTTPException(409, str(exc)) from None
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"查询扫码状态失败：{exc}") from None

    @router.get("/jobs/{job_id}/publish")
    def get_job_publish(job_id: str):
        manager.directory(job_id)
        publish.ensure_worker(manager)
        items = [item for item in publish.read_store(manager)["items"]
                 if item.get("job_id") == job_id]
        return {"items": items, "biliup_ready": publish.locate_biliup() is not None,
                "credential_ready": publish.credential_ready()}

    @router.post("/jobs/{job_id}/publish", status_code=202)
    def create_job_publish(job_id: str, payload: publish.PublishInput):
        try:
            return publish.submit(manager, job_id, payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    # ---- 术语表 ----

    @router.get("/glossary")
    def get_glossary():
        return load_glossary_store(manager).model_dump(mode="json")

    @router.put("/glossary")
    def put_glossary(payload: glossary.TermsUpdate):
        store = load_glossary_store(manager)
        store.terms = payload.terms
        save_glossary_store(manager, store)
        return store.model_dump(mode="json")

    @router.post("/glossary/import")
    def import_glossary(payload: glossary.TermsImport):
        store = load_glossary_store(manager)
        incoming, skipped = glossary.parse_terms_text(payload.text)
        if not incoming and skipped:
            raise HTTPException(422, "未解析到有效词条，请确认格式为 `# 原文=统一译文`")
        # 按 src 合并：导入词条覆盖同 src 已有项
        existing = {term.src: term for term in store.terms}
        for term in incoming:
            existing[term.src] = term
        merged = list(existing.values())
        if len(merged) > glossary.MAX_TERMS:
            raise HTTPException(422, f"合并后词条数超过上限 {glossary.MAX_TERMS}，请分批导入")
        store.terms = merged
        save_glossary_store(manager, store)
        return store.model_dump(mode="json")

    @router.post("/glossary/candidates/{index}/accept")
    def accept_glossary_candidate(index: int, payload: glossary.Term):
        store = load_glossary_store(manager)
        if not 0 <= index < len(store.candidates):
            raise HTTPException(404, "候选词不存在或已处理")
        store.candidates.pop(index)
        store.terms = [term for term in store.terms if term.src != payload.src]
        if len(store.terms) >= glossary.MAX_TERMS:
            raise HTTPException(422, "术语表已达上限")
        store.terms.append(payload)
        save_glossary_store(manager, store)
        return store.model_dump(mode="json")

    @router.post("/glossary/candidates/{index}/ignore")
    def ignore_glossary_candidate(index: int):
        store = load_glossary_store(manager)
        if not 0 <= index < len(store.candidates):
            raise HTTPException(404, "候选词不存在或已处理")
        candidate = store.candidates.pop(index)
        if candidate.src not in store.ignored:
            store.ignored.append(candidate.src)
        save_glossary_store(manager, store)
        return store.model_dump(mode="json")

    # ---- 旧版字幕样式 ----

    @router.get("/subtitle-style")
    def get_subtitle_style():
        return load_style_store(manager).model_dump(mode="json")

    @router.put("/subtitle-style")
    def put_subtitle_style(payload: legacy_style.SubtitleStyleConfig):
        store = load_style_store(manager)
        store.current = _validate_style(payload)
        save_style_store(manager, store)
        return store.model_dump(mode="json")

    @router.put("/subtitle-style/templates/{name}")
    def put_subtitle_style_template(name: str, payload: legacy_style.SubtitleStyleConfig):
        if not legacy_style.TEMPLATE_NAME.fullmatch(name):
            raise HTTPException(422, "模板名称无效")
        store = load_style_store(manager)
        if name not in store.templates and len(store.templates) >= legacy_style.MAX_TEMPLATES:
            raise HTTPException(422, "模板数量已达上限")
        store.templates[name] = _validate_style(payload)
        save_style_store(manager, store)
        return store.model_dump(mode="json")

    @router.delete("/subtitle-style/templates/{name}")
    def delete_subtitle_style_template(name: str):
        store = load_style_store(manager)
        store.templates.pop(name, None)
        save_style_store(manager, store)
        return store.model_dump(mode="json")

    # ---- 烧录合成 ----

    @router.post("/jobs/{job_id}/burn", status_code=202)
    def create_burn(job_id: str, payload: BurnInput):
        return submit_burn(manager, job_id, payload.clip, payload.variant, payload.start, payload.end,
                           payload.danmaku.style() if payload.danmaku else None)

    # ---- 图形绘制（存于 legacy style.json 的 shapes 字段）----

    @router.get("/shapes")
    def get_shapes():
        return {"shapes": [s.model_dump(mode="json") for s in load_style_store(manager).shapes]}

    @router.put("/shapes")
    def put_shapes(payload: legacy_style.ShapesUpdate):
        store = load_style_store(manager)
        store.shapes = payload.shapes
        save_style_store(manager, store)
        return {"shapes": [s.model_dump(mode="json") for s in store.shapes]}

    # ---- 图形模板 ----

    @router.get("/shapes/templates")
    def get_shapes_templates():
        store = load_style_store(manager)
        return {"templates": {k: [s.model_dump(mode="json") for s in v] for k, v in store.shapes_templates.items()}}

    @router.put("/shapes/templates/{name}")
    def put_shapes_template(name: str, payload: legacy_style.ShapesUpdate):
        store = load_style_store(manager)
        store.shapes_templates[name] = payload.shapes
        save_style_store(manager, store)
        return {"templates": {k: [s.model_dump(mode="json") for s in v] for k, v in store.shapes_templates.items()}}

    @router.delete("/shapes/templates/{name}")
    def delete_shapes_template(name: str):
        store = load_style_store(manager)
        store.shapes_templates.pop(name, None)
        save_style_store(manager, store)
        return {"templates": {k: [s.model_dump(mode="json") for s in v] for k, v in store.shapes_templates.items()}}

    @router.put("/jobs/{job_id}/translation/{cue_id}")
    def edit_job_translation(job_id: str, cue_id: int, payload: TranslationEditInput):
        directory = manager.directory(job_id)
        try:
            translation.edit_translated(directory, cue_id, payload.text)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        except OSError as exc:
            raise HTTPException(500, f"译文保存失败：{exc}")
        return {"ok": True}

    # ---- 录播（直播间 + 自动录制）----

    @router.get("/recorder")
    def get_recorder():
        return manager.recorder.status()

    @router.get("/recorder/recordings")
    def get_recordings():
        return {"items": manager.recorder.recordings()}

    @router.post("/recorder/rooms", status_code=201)
    def add_recorder_room(payload: RoomInput):
        try:
            room = manager.recorder.add_room(payload.room, payload.name)
            if not payload.auto_run:
                room = manager.recorder.update_room(room["room_id"], auto_run=False)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return room

    @router.put("/recorder/rooms/{room_id}")
    def update_recorder_room(room_id: str, payload: RoomUpdate):
        try:
            return manager.recorder.update_room(room_id, name=payload.name,
                                                enabled=payload.enabled, auto_run=payload.auto_run)
        except KeyError:
            raise HTTPException(404, "直播间不存在") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @router.delete("/recorder/rooms/{room_id}")
    def delete_recorder_room(room_id: str):
        try:
            manager.recorder.remove_room(room_id)
        except KeyError:
            raise HTTPException(404, "直播间不存在") from None
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc)) from None
        return {"ok": True}

    @router.put("/recorder/settings")
    def save_recorder_settings(payload: RecorderSettingsInput):
        try:
            return manager.recorder.save_settings(payload.record_path)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @router.post("/recorder/open-folder")
    def open_recorder_folder():
        try:
            manager.recorder.open_folder()
        except OSError as exc:
            raise HTTPException(409, f"无法打开录播文件夹：{exc}") from None
        return {"opened": True}

    @router.post("/recorder/rooms/{room_id}/start")
    def start_recorder_room(room_id: str):
        try:
            return manager.recorder.start_recording(room_id)
        except KeyError:
            raise HTTPException(404, "直播间不存在") from None
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None

    @router.post("/recorder/rooms/{room_id}/stop")
    def stop_recorder_room(room_id: str):
        try:
            return manager.recorder.stop_recording(room_id)
        except KeyError:
            raise HTTPException(404, "直播间不存在") from None
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None

    # ---- 自动化流水线 ----

    @router.get("/automation")
    def get_automation():
        return {"templates": automation.read_templates(manager),
                "tasks": automation.read_tasks(manager),
                "default_config": automation.DEFAULT_CONFIG.model_dump(mode="json"),
                "api_key_ready": manager.api_key is not None}

    @router.get("/automation/preview-sample")
    def automation_preview_sample():
        """样式预览用的 10 秒 1080p 样例视频（ffmpeg 测试画面），生成一次后缓存复用。"""
        path = manager.root / "preview-sample.mp4"
        if not path.is_file():
            tmp = manager.root / ".preview-sample.tmp.mp4"
            result = subprocess.run(
                [media.tool_path("ffmpeg"), "-hide_banner", "-y",
                 "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=10",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)],
                capture_output=True, timeout=180, check=False)
            if result.returncode != 0 or not tmp.is_file():
                tmp.unlink(missing_ok=True)
                raise HTTPException(500, "预览视频生成失败，请确认 ffmpeg 可用")
            os.replace(tmp, path)
        return FileResponse(path, media_type="video/mp4")

    @router.post("/automation/tasks", status_code=202)
    def create_automation_task(payload: AutomationTaskInput):
        try:
            return automation.enqueue(manager, kind="url", url=payload.url,
                                      title=payload.title or payload.url,
                                      template_id=payload.template_id, config=payload.config)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @router.post("/automation/tasks/upload", status_code=202)
    async def upload_automation_task(request: Request, config: str = "", title: str = ""):
        name = unquote(request.headers.get("x-filename") or "") or "upload.mp4"
        suffix = Path(name).suffix.lower() or ".mp4"
        if suffix not in {".mp4", ".mkv", ".flv", ".ts", ".mov", ".webm", ".m4v", ".avi"}:
            raise HTTPException(422, "仅支持常见视频文件格式")
        options = None
        if config:
            try:
                options = automation.AutomationConfig.model_validate_json(config)
            except ValueError:
                raise HTTPException(422, "自动化参数无效，请检查后重试") from None
        incoming = manager.root / ".automation-incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        temp = incoming / f"{uuid.uuid4().hex[:10]}{suffix}"
        size = 0
        with temp.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 32 * 1024 * 1024 * 1024:
                    handle.close()
                    temp.unlink(missing_ok=True)
                    raise HTTPException(413, "视频文件超过 32GB，请先在本地压缩")
                handle.write(chunk)
        if not size:
            temp.unlink(missing_ok=True)
            raise HTTPException(422, "没有收到视频文件")
        try:
            return automation.enqueue(manager, kind="upload", title=title or Path(name).stem,
                                      source_path=temp, source_name=name, config=options,
                                      auto_start=False)
        except ValueError as exc:
            temp.unlink(missing_ok=True)
            raise HTTPException(422, str(exc)) from None

    @router.post("/automation/tasks/{task_id}/danmaku", status_code=201)
    async def upload_automation_danmaku(task_id: str, request: Request):
        task = next((item for item in automation.read_tasks(manager) if item.get("id") == task_id), None)
        if task is None:
            raise HTTPException(404, "自动化任务不存在")
        if task.get("state") in {"running", "completed"}:
            raise HTTPException(409, "任务已开始，请等待结束后在任务详情里补充弹幕")
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > danmaku.MAX_FILE_BYTES:
            raise HTTPException(413, "弹幕文件过大（上限 64 MB）")
        body = await request.body()
        if not body:
            raise HTTPException(422, "请选择弹幕文件")
        if len(body) > danmaku.MAX_FILE_BYTES:
            raise HTTPException(413, "弹幕文件过大（上限 64 MB）")
        content = body.decode("utf-8-sig", errors="replace")
        source, entries = danmaku.parse(content)
        if not entries:
            raise HTTPException(422, "未解析到弹幕，请确认导出的是 XML 或 JSON 弹幕文件")
        incoming = manager.root / ".automation-incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        path = incoming / f"{task_id}.danmaku"
        try:
            path.write_text(content, encoding="utf-8")
        except OSError:
            raise HTTPException(500, "弹幕文件保存失败，请检查数据目录权限") from None
        name = unquote(request.headers.get("x-filename") or "") or f"{task_id}.xml"
        updated = automation.attach_danmaku(manager, task_id, path, name, len(entries))
        return {"task": updated, "count": len(entries), "source": source}

    @router.post("/automation/tasks/{task_id}/start")
    def start_automation_task(task_id: str):
        try:
            return automation.start_task(manager, task_id)
        except KeyError:
            raise HTTPException(404, "自动化任务不存在") from None
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None

    @router.post("/automation/tasks/{task_id}/retry")
    def retry_automation_task(task_id: str):
        try:
            return automation.retry_task(manager, task_id)
        except KeyError:
            raise HTTPException(404, "自动化任务不存在") from None
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None

    @router.delete("/automation/tasks/{task_id}")
    def delete_automation_task(task_id: str):
        try:
            automation.delete_task(manager, task_id)
        except KeyError:
            raise HTTPException(404, "自动化任务不存在") from None
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None
        return {"ok": True}

    @router.post("/automation/templates", status_code=201)
    def create_automation_template(payload: AutomationTemplateInput):
        return {"templates": automation.save_template(
            manager, automation.TemplateInput(name=payload.name, config=payload.config))}

    @router.put("/automation/templates/{template_id}")
    def update_automation_template(template_id: str, payload: AutomationTemplateInput):
        try:
            return {"templates": automation.save_template(
                manager, automation.TemplateInput(name=payload.name, config=payload.config), template_id)}
        except KeyError:
            raise HTTPException(404, "自动化模板不存在") from None

    @router.delete("/automation/templates/{template_id}")
    def delete_automation_template(template_id: str):
        try:
            return {"templates": automation.delete_template(manager, template_id)}
        except KeyError:
            raise HTTPException(404, "自动化模板不存在") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    manager.recorder.start()
    automation.ensure_worker(manager)

    return router
