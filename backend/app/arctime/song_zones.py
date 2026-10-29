"""唱歌区间检测与切片边界吸附。

三路证据交叉确认，任何一路缺失都退化为"不检测"，绝不阻断切片流程：

1. 音频：0.5 秒响度序列做 10 秒平滑，高于本场 75 分位 −2 dB 且持续 ≥20 秒的
   平台段视为"持续发声"候选（歌声连续、谈话会因停顿而忽高忽低）；
2. 歌词 cue：译文字幕出现「歌词音译」等显式标记时，直接以标记 cue 覆盖区间为准；
3. 歌尾锚点：候选平台段结束后 30 秒内出现「聴いてくれてありがとう」「歌い終わ」
   等收尾语才算确认，避免把欢呼、惊呼当成歌声；确认后再向后延伸 45 秒内命中的
   收尾/歌回赘述 cue，剔除「今天的歌声真棒」「歌已经结束了」这类文字层歌尾。

检测结果用于把切片起止吸附到歌声之外，并写入每段的 song_overlap（与唱歌区间
的重合比），供自动选段过滤。
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Any

from app.arctime import audio_factors, media

SMOOTH_SECONDS = 10.0
# 判定阈值：本场响度 75 分位再减 2 dB，适应不同直播间的音量基线
PLATEAU_OFFSET_DB = -2.0
MIN_ZONE_SECONDS = 20.0
MERGE_GAP_SECONDS = 15.0
TAIL_WINDOW_SECONDS = 30.0
TALK_WINDOW_SECONDS = 45.0
SNAP_KEEP_SECONDS = 20.0
# 预览文本长度上限，与 topic_segments.MAX_PREVIEW_LEN 保持一致
PREVIEW_LEN = 200
# 低于该响度的帧视为静音，不参与分位计算
SILENCE_DB = -60.0

TAIL_ANCHORS = ("聴いてくれて", "聞いてくれて", "歌い終わ", "歌終わ", "曲終わ", "歌声",
                "本物の歌", "ご視聴ありがとう", "全曲歌", "歌ってみた", "歌いました")
TALK_ANCHORS = TAIL_ANCHORS + ("曲が終わ", "歌が終わ", "歌は終わ", "歌、終わ", "ありがとう",
                               "オリジナル曲", "歌の配信", "歌枠", "歌配信", "歌を歌")
LYRIC_MARKERS = ("歌词音译", "歌詞音訳", "（歌词", "(歌词")


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return SILENCE_DB
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _plateaus(audio: dict) -> list[tuple[float, float]]:
    """返回持续发声的候选平台段（秒），按本场分位自适应阈值。"""
    loudness = audio.get("loudness") or []
    step = float(audio.get("group_seconds") or 0.5)
    values = [value for value in loudness if value is not None and value > SILENCE_DB]
    if len(values) < int(MIN_ZONE_SECONDS / step):
        return []
    threshold = _quantile(values, .75) + PLATEAU_OFFSET_DB
    size = max(1, int(SMOOTH_SECONDS / step))
    spans: list[list[float]] = []
    current: list[float] | None = None
    for index, value in enumerate(loudness):
        recent = [item for item in loudness[max(0, index - size):index + 1]
                  if item is not None and item > SILENCE_DB]
        smooth = sum(recent) / len(recent) if recent else SILENCE_DB
        if value is not None and smooth >= threshold:
            current = [index * step, (index + 1) * step] if current is None else [current[0], (index + 1) * step]
        elif current is not None:
            spans.append(current)
            current = None
    if current is not None:
        spans.append(current)
    merged: list[list[float]] = []
    for span in spans:
        if merged and span[0] - merged[-1][1] <= MERGE_GAP_SECONDS:
            merged[-1][1] = span[1]
        else:
            merged.append(span)
    return [(start, end) for start, end in merged if end - start >= MIN_ZONE_SECONDS]


def _cue_hits(cues: list, zh_texts: list[str], start: float, end: float,
              anchors: tuple[str, ...]) -> list[int]:
    """返回起点落在 [start, end] 且文本命中锚点的 cue 下标。"""
    return [index for index, cue in enumerate(cues)
            if start <= cue.start_seconds <= end
            and any(anchor in cue.text or anchor in (zh_texts[index] if index < len(zh_texts) else "")
                    for anchor in anchors)]


def detect(cues: list, zh_texts: list[str], audio: dict | None) -> list[tuple[float, float]]:
    """检测唱歌区间；无音频因子时返回空（宁可不检测，也不误裁）。"""
    if not audio or not cues:
        return []
    zones: list[tuple[float, float]] = []
    for start, end in _plateaus(audio):
        markers = [index for index, cue in enumerate(cues)
                   if start - 1 <= cue.start_seconds <= end + 1
                   and any(marker in (zh_texts[index] if index < len(zh_texts) else "")
                           for marker in LYRIC_MARKERS)]
        if markers:
            # 歌词音译标记最可靠：区间以标记覆盖的 cue 为准，不向歌尾谈话延伸
            zones.append((max(0.0, cues[markers[0]].start_seconds - 2.0),
                          cues[markers[-1]].end_seconds + 2.0))
            continue
        tail = _cue_hits(cues, zh_texts, max(0.0, end - 2.0), end + TAIL_WINDOW_SECONDS, TAIL_ANCHORS)
        if not tail:
            continue
        talk = _cue_hits(cues, zh_texts, max(0.0, end - 2.0), end + TALK_WINDOW_SECONDS, TALK_ANCHORS)
        zone_end = max(cues[index].end_seconds for index in talk) if talk else end
        zones.append((max(0.0, start - 1.0), zone_end))
    zones.sort()
    merged: list[tuple[float, float]] = []
    for start, end in zones:
        if merged and start - merged[-1][1] <= 5.0:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _value(item: Any, key: str) -> Any:
    return item.get(key) if isinstance(item, dict) else getattr(item, key, None)


def _assign(item: Any, key: str, value: Any) -> None:
    if isinstance(item, dict):
        item[key] = value
    else:
        setattr(item, key, value)


def _overlap_ratio(start: float, end: float, zones: list[tuple[float, float]]) -> float:
    if end <= start:
        return 0.0
    covered = 0.0
    for zone_start, zone_end in zones:
        covered += max(0.0, min(end, zone_end) - max(start, zone_start))
    return covered / (end - start)


def _snap(segment: Any, zones: list[tuple[float, float]], cues: list,
          zh_texts: list[str]) -> bool:
    """把起点落在歌声内 / 终点落在歌声内的边界推到区间外，并对齐到 cue 边界。"""
    start = float(_value(segment, "start_seconds") or 0)
    end = float(_value(segment, "end_seconds") or 0)
    new_start, new_end = start, end
    changed = True
    guard = 0
    while changed and guard < 4:
        changed = False
        guard += 1
        for zone_start, zone_end in zones:
            if zone_start - 1.0 <= new_start < zone_end - 0.2 and zone_end + SNAP_KEEP_SECONDS <= new_end:
                new_start, changed = zone_end, True
            if zone_start + 0.2 < new_end <= zone_end + 1.0 and new_start + SNAP_KEEP_SECONDS <= zone_start:
                new_end, changed = zone_start, True
    if abs(new_start - start) < 0.2 and abs(new_end - end) < 0.2:
        return False
    starts = [cue.start_seconds for cue in cues]
    ends = [cue.end_seconds for cue in cues]
    start_index = bisect_left(starts, new_start - 0.05)
    end_index = bisect_right(ends, new_end + 0.05) - 1
    if start_index > end_index:
        return False
    new_start = starts[start_index]
    new_end = ends[end_index]
    if new_end - new_start < 10.0:
        return False
    _assign(segment, "start_seconds", new_start)
    _assign(segment, "end_seconds", new_end)
    _assign(segment, "start_id", start_index + 1)
    _assign(segment, "end_id", end_index + 1)
    _assign(segment, "cue_count", end_index - start_index + 1)
    if zh_texts:
        # 起止变了，预览必须跟着换，否则 UI 仍显示已被裁掉的歌尾
        _assign(segment, "preview", " ".join(zh_texts[start_index:end_index + 1])[:PREVIEW_LEN])
    return True


def refine(directory: Path, segments: list[Any], *, cues: list | None = None,
           zh_texts: list[str] | None = None, audio: dict | None = None) -> bool:
    """检测唱歌区间并吸附边界，写回每段 song_overlap；返回是否有改动。"""
    if not segments:
        return False
    if cues is None:
        ja_path = directory / "subtitles.srt"
        zh_path = directory / "subtitles.zh.srt"
        try:
            cues = media.read_subtitles(ja_path)
            zh_texts = ([cue.text for cue in media.read_subtitles(zh_path)]
                        if zh_path.is_file() and not zh_path.is_symlink() else [])
        except (OSError, ValueError):
            return False
    zh_texts = zh_texts or []
    if audio is None:
        audio = audio_factors.load(directory)
    zones = detect(cues, zh_texts, audio)
    changed = False
    for segment in segments:
        if zones:
            changed = _snap(segment, zones, cues, zh_texts) or changed
        start = float(_value(segment, "start_seconds") or 0)
        end = float(_value(segment, "end_seconds") or 0)
        ratio = round(_overlap_ratio(start, end, zones), 3) if zones else 0.0
        if _value(segment, "song_overlap") != ratio:
            _assign(segment, "song_overlap", ratio)
            changed = True
    return changed
