"""音频因子：响度峰值与笑声/尖叫（兴奋度）近似检测。

用 ffmpeg 把 source.mp4 的音轨解码成 16 kHz 单声道 s16le，按 0.5 秒一组计算：
- 响度：RMS 转 dBFS，反映突然放大的音量；
- 高频占比：一阶差分能量与原信号能量之比，近似 2–8 kHz 能量占比，
  笑声、尖叫、欢呼会明显高于普通说话。

结果缓存为 audio.json；解码失败返回 None，绝不阻断内容切片。
"""
from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np

from app.arctime import media

STORE_NAME = "audio.json"
SAMPLE_RATE = 16000
GROUP_SECONDS = 0.5
SAMPLES_PER_GROUP = int(SAMPLE_RATE * GROUP_SECONDS)
# 最多缓存 12 小时音频特征，超出部分截断（单场直播极少更长）
MAX_GROUPS = 12 * 3600 * 2


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(math.floor(position))
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _decode(source: Path) -> dict | None:
    """流式解码音轨，返回 0.5 秒粒度的响度与高频占比序列。"""
    try:
        command = [media.tool_path("ffmpeg"), "-v", "error", "-nostdin", "-i", str(source),
                   "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except (OSError, ValueError):
        return None
    loudness: list[float] = []
    tone: list[float] = []
    buffer = bytearray()
    completed = False
    try:
        assert process.stdout is not None
        while len(loudness) < MAX_GROUPS:
            block = process.stdout.read(SAMPLES_PER_GROUP * 2 * 64)
            if not block:
                completed = True
                break
            buffer.extend(block)
            while len(buffer) >= SAMPLES_PER_GROUP * 2 and len(loudness) < MAX_GROUPS:
                chunk = bytes(buffer[:SAMPLES_PER_GROUP * 2])
                del buffer[:SAMPLES_PER_GROUP * 2]
                samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                power = float(np.mean(samples * samples)) if samples.size else 0.0
                loudness.append(round(20 * math.log10(max(math.sqrt(power), 1.0) / 32768), 1))
                if samples.size > 1:
                    diff = np.diff(samples)
                    tone.append(round(float(np.mean(diff * diff)) / (power + 1e-9), 3))
                else:
                    tone.append(0.0)
    finally:
        if process.stdout is not None:
            try:
                process.stdout.close()
            except OSError:
                pass
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=10)
        except (subprocess.TimeoutExpired, OSError):
            pass
    # 到缓存上限时视为有效（只是截断），中途解码失败则丢弃
    if len(loudness) >= MAX_GROUPS:
        completed = True
    if not loudness or not completed:
        return None
    return {"sample_rate": SAMPLE_RATE, "group_seconds": GROUP_SECONDS,
            "duration": round(len(loudness) * GROUP_SECONDS, 1),
            "loudness": loudness, "tone": tone}


def load(directory: Path) -> dict | None:
    """读取已缓存的音频特征（不触发解码）。"""
    path = directory / STORE_NAME
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("loudness"), list):
        return None
    return value


def ensure(directory: Path, source: Path | None = None) -> dict | None:
    """有缓存且视频未变化时复用，否则解码并写入 audio.json。失败返回旧缓存或 None。"""
    source = source or directory / "source.mp4"
    cached = load(directory)
    try:
        stat = source.stat()
    except OSError:
        return cached
    if (cached and cached.get("source_size") == stat.st_size
            and abs(float(cached.get("source_mtime") or 0) - stat.st_mtime) < 1.0):
        return cached
    payload = _decode(source)
    if payload is None:
        return cached
    payload.update(version=1, source_size=stat.st_size, source_mtime=stat.st_mtime,
                   created_at=time.time())
    try:
        media.write_json(directory / STORE_NAME, payload)
    except OSError:
        pass
    return payload


def segment_stats(audio: dict | None, segments: list[dict]) -> list[dict] | None:
    """按切片窗口统计响度峰值与每分钟「兴奋帧」数（笑声/尖叫/欢呼近似）。"""
    if not audio:
        return None
    loudness = audio.get("loudness") or []
    tone = audio.get("tone") or []
    if not loudness or len(tone) != len(loudness):
        return None
    try:
        group = float(audio.get("group_seconds") or GROUP_SECONDS)
    except (TypeError, ValueError):
        return None
    if group <= 0:
        return None
    # 兴奋帧：响度进入全场前 25%，且高频占比高于全场 65 分位
    loud_ref = _quantile(loudness, .75)
    tone_ref = _quantile(tone, .65)
    excited = [d >= loud_ref and t >= tone_ref for d, t in zip(loudness, tone)]
    rows: list[dict] = []
    for segment in segments:
        start = float(segment.get("start_seconds") or 0)
        end = float(segment.get("end_seconds") or 0)
        first = max(0, int(start / group))
        last = min(len(loudness), max(first + 1, int(math.ceil(end / group))))
        window = loudness[first:last]
        duration = max(end - start, 1.0)
        rows.append({"loudness_db": round(_quantile(window, .95), 1) if window else None,
                     "laugh_rate": round(sum(excited[first:last]) / duration * 60, 1)})
    return rows
