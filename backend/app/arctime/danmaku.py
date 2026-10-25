"""弹幕导入与切片互动评分。

弹幕文件由浏览器插件（如弹幕助手 acghelper）导出，支持两种格式：
- ASS：B 站弹幕转换后的字幕，取 Dialogue 行的起止时间与文本；
- XML：B 站原生弹幕池，取 <d p="时间,模式,字号,颜色,发送时间,池,用户哈希,...">文本</d>。

导入后按内容切片的时间窗口统计互动密度，给每个切片打 0–100 分，
作为「值不值得剪」的参考信号。所有分数都是相对本场自身基线的分位值，
换直播间不需要重新调参。
"""
from __future__ import annotations

import html
import json
import math
import re
import time
from pathlib import Path

from app.arctime import audio_factors, clip_vocab, clip_words, media

STORE_NAME = "danmaku.json"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 400_000
PEAK_WINDOW_SECONDS = 10.0

_ASS_TIME = re.compile(r"^(\d+):(\d{1,2}):(\d{1,2})(?:[.,](\d{1,3}))?$")
_ASS_TAG = re.compile(r"\{[^}]*\}")
_XML_ITEM = re.compile(r"<d\s+p=\"([^\"]*)\"[^>]*>(.*?)</d>", re.S)
_XML_TAG = re.compile(r"<[^>]+>")

# 抽奖、打卡等机器人弹幕会污染密度信号，统计前剔除
_BOT_PATTERNS = (
    "抽奖", "中奖", "关注了", "打卡", "签到", "粉丝牌", "直播间", "正在直播",
)


def _parse_ass_time(value: str) -> float | None:
    match = _ASS_TIME.match(value.strip())
    if not match:
        return None
    hours, minutes, seconds, fraction = match.groups()
    total = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    if fraction:
        total += int(fraction.ljust(3, "0")) / 1000
    return total


def _clean_text(value: str) -> str:
    text = _ASS_TAG.sub("", value) if "{" in value else value
    text = text.replace("\\N", " ").replace("\\n", " ")
    return " ".join(text.split())


def _keep(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return not any(pattern in lowered for pattern in _BOT_PATTERNS)


def parse_ass(content: str) -> list[list]:
    """解析 ASS 弹幕：Dialogue 行的 起始时间、结束时间、文本。"""
    entries: list[list] = []
    for line in content.splitlines():
        if not line.lower().startswith("dialogue:"):
            continue
        fields = line.split(",", 9)
        if len(fields) < 10:
            continue
        start = _parse_ass_time(fields[1])
        if start is None:
            continue
        end = _parse_ass_time(fields[2])
        text = _clean_text(fields[9])
        if _keep(text):
            entries.append([round(start, 3), text, "", round(end or start, 3)])
    return entries


def parse_xml(content: str) -> list[list]:
    """解析 B 站 XML 弹幕：p 属性第 1 段为时间（秒），第 7 段为发送者哈希。"""
    entries: list[list] = []
    for attributes, raw in _XML_ITEM.findall(content):
        parts = attributes.split(",")
        try:
            start = float(parts[0])
        except (ValueError, IndexError):
            continue
        user = parts[6].strip() if len(parts) > 6 else ""
        text = _clean_text(html.unescape(_XML_TAG.sub("", raw)))
        if _keep(text):
            entries.append([round(start, 3), text, user, None])
    return entries


def parse(content: str) -> tuple[str, list[list]]:
    """按内容嗅探格式并解析，返回 (格式, 条目)。"""
    head = content[:4096]
    if "<d p=" in head or head.lstrip().startswith("<"):
        entries = parse_xml(content)
        if entries:
            return "xml", entries
    entries = parse_ass(content)
    if entries:
        return "ass", entries
    return "unknown", []


def read_store(directory: Path) -> dict | None:
    path = directory / STORE_NAME
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 48 * 1024 * 1024:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) and isinstance(value.get("entries"), list) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_store(directory: Path, source: str, entries: list[list], meta: dict | None = None) -> dict:
    entries.sort(key=lambda item: item[0])
    if len(entries) > MAX_ENTRIES:
        # 超量时等距抽样，保留整场分布而不是只留前半段
        step = len(entries) / MAX_ENTRIES
        entries = [entries[int(i * step)] for i in range(MAX_ENTRIES)]
    store = {"source": source, "count": len(entries), "entries": entries}
    if meta:
        store.update({key: value for key, value in meta.items() if value is not None})
    media.write_json(directory / STORE_NAME, store)
    return store


def summary(directory: Path) -> dict:
    store = read_store(directory)
    if not store:
        return {"count": 0, "source": None, "url": None, "title": None}
    entries = store.get("entries") or []
    return {"count": int(store.get("count") or len(entries)),
            "source": store.get("source"),
            "span": round(entries[-1][0], 1) if entries else 0,
            "url": store.get("url"),
            "title": store.get("title")}


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(math.floor(position))
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _segment_stats(entries: list[list], start: float, end: float) -> dict:
    window = [item for item in entries if start <= item[0] < end]
    duration = max(end - start, 0.001)
    users = {item[2] for item in window if item[2]}
    texts = [item[1] for item in window]
    unique_texts = set(texts)
    repeat = (len(texts) - len(unique_texts)) / len(texts) if texts else 0.0
    # 10 秒滑动窗口峰值，用于定位「名场面」时刻
    peak, peak_time = 0, start
    left = 0
    for right, item in enumerate(window):
        while item[0] - window[left][0] > PEAK_WINDOW_SECONDS:
            left += 1
        if right - left + 1 > peak:
            peak = right - left + 1
            peak_time = window[left][0]
    # 按三等分统计，用于判断弹幕是均匀铺开还是集中在某一段
    thirds = [0, 0, 0]
    for item in window:
        thirds[min(2, max(0, int((item[0] - start) / duration * 3)))] += 1
    return {
        "count": len(window),
        "rate": len(window) / duration,
        "users": len(users),
        "repeat": repeat,
        "peak": peak,
        "peak_time": peak_time if peak else None,
        "thirds": thirds,
        "duration": duration,
    }


def _dm_shape(stats: dict) -> tuple[str, float]:
    """给弹幕分布形态打分：尖峰（名场面）> 递增 > 递减 > 平稳。"""
    total = stats["count"]
    if not total:
        return "无弹幕", .45
    duration = stats.get("duration") or 0
    if duration >= 20 and stats["peak"] / total >= .5:
        return "尖峰", 1.0
    thirds = stats.get("thirds") or [0, 0, 0]
    if total >= 5 and thirds[2] >= 2 * max(thirds[0], 1):
        return "递增", .85
    if total >= 5 and thirds[0] >= 2 * max(thirds[2], 1):
        return "递减", .75
    return "平稳", .7


def _read_cues(directory: Path) -> tuple[list, list]:
    """读取原文/译文字幕，用于热词匹配、金句提取与风险词统计；缺失时返回空列表。

    没有翻译字幕时把原文当作展示文本（译文字幕位置），不需要翻译的主播
    也能拿到金句与风险词。
    """
    cues = []
    for name in ("subtitles.srt", "subtitles.zh.srt"):
        try:
            cues.append(media.read_subtitles(directory / name))
        except (OSError, ValueError):
            cues.append([])
    return cues[0], cues[1] or cues[0]


def _read_job(directory: Path) -> dict:
    try:
        value = json.loads((directory / "job.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _segment_extras(directory: Path, segments: list[dict], words: clip_words.Lexicon | None,
                    build_audio: bool) -> tuple[list[dict], list, list]:
    """统计每个切片的音频因子与合规风险词，返回 (行, 原文字幕, 译文字幕)。"""
    audio = audio_factors.ensure(directory) if build_audio else audio_factors.load(directory)
    audio_rows = audio_factors.segment_stats(audio, segments)
    ja_cues, zh_cues = _read_cues(directory)
    lexicon = words or clip_words.load()
    rows: list[dict] = []
    for index, segment in enumerate(segments):
        start = float(segment.get("start_seconds") or 0)
        end = float(segment.get("end_seconds") or 0)
        ja_text = "".join(cue.text for cue in ja_cues if cue.end_seconds > start and cue.start_seconds < end)
        zh_text = "".join(cue.text for cue in zh_cues if cue.end_seconds > start and cue.start_seconds < end)
        risk_terms = lexicon.detect(zh_text, ja_text)
        row = {"loudness_db": None, "laugh_rate": None,
               "risk_terms": risk_terms, "risk": bool(risk_terms)}
        if audio_rows and index < len(audio_rows):
            row.update(audio_rows[index])
        rows.append(row)
    return rows, ja_cues, zh_cues


def _ratio_multiplier(value: float | None, ref: float, low: float, high: float) -> float:
    """按本场 95 分位把因子映射到 [low, high] 的评分系数。"""
    if value is None or not ref or ref <= 0:
        return 1.0
    ratio = min(1.0, max(0.0, float(value) / ref))
    return low + (high - low) * ratio


def _shape_multiplier(shape_score: float) -> float:
    """弹幕形态分 0.45（无弹幕）–1.0（尖峰）映射到 0.95–1.10。"""
    ratio = min(1.0, max(0.0, (float(shape_score) - .45) / .55))
    return .95 + .15 * ratio


def _loudness_multiplier(value: float | None, ref: float, low: float, high: float) -> float:
    """dBFS 为负值，按振幅比（相对本场 95 分位）换算 0–1 后再映射到 [low, high]。"""
    if value is None or not ref:
        return 1.0
    ratio = min(1.0, 10 ** ((float(value) - float(ref)) / 20))
    return low + (high - low) * ratio


def score_store(store: dict, entries: list[list], *, directory: Path | None = None,
                words: clip_words.Lexicon | None = None, build_audio: bool = False,
                vocab_root: Path | None = None,
                danmaku_meta: dict | None = None) -> bool:
    """就地写入因子与综合评分，返回是否有更新。

    两阶段：第一轮只用弹幕、音频、风险打基础分；再从第一轮高分切片里提取
    本场热词与金句（clip_vocab），第二轮用本场热词 + 主播画像加分。
    """
    segments = store.get("segments") or []
    if not segments:
        return False
    if directory is not None:
        extras, ja_cues, zh_cues = _segment_extras(directory, segments, words, build_audio)
        for segment, extra in zip(segments, extras):
            segment.update(extra)
    else:
        extras, ja_cues, zh_cues = None, [], []
    if not entries:
        return bool(extras)
    rows = []
    for segment in segments:
        start = float(segment.get("start_seconds") or 0)
        end = float(segment.get("end_seconds") or 0)
        stats = _segment_stats(entries, start, end)
        duration = max(end - start, 0.001)
        stats["speech"] = float(segment.get("cue_count") or 0) / duration
        stats["shape"], stats["shape_score"] = _dm_shape(stats)
        rows.append(stats)
    # 用本场 95 分位做归一，避免不同直播间密度量级差异导致分数失真
    rate_ref = _quantile([row["rate"] for row in rows], 0.95) or 1.0
    user_ref = _quantile([row["users"] for row in rows], 0.95) or 1.0
    repeat_ref = _quantile([row["repeat"] for row in rows], 0.95) or 1.0
    speech_ref = _quantile([row["speech"] for row in rows], 0.95) or 1.0
    loud_ref = _quantile([extra["loudness_db"] for extra in extras or []
                          if extra.get("loudness_db") is not None], 0.95)
    laugh_ref = _quantile([extra["laugh_rate"] for extra in extras or []
                           if extra.get("laugh_rate") is not None], 0.95)
    # ASS 弹幕没有发送者信息，参与人数维度无法计算，权重并入密度，保持 0–100 量级一致
    has_users = any(item[2] for item in entries)
    # 第一轮：不含动态热词的基础分
    scores: list[int] = []
    for index, row in enumerate(rows):
        extra = extras[index] if extras else {}
        density = min(1.0, row["rate"] / rate_ref)
        audience = min(1.0, row["users"] / user_ref)
        echo = min(1.0, row["repeat"] / repeat_ref)
        speech = min(1.0, row["speech"] / speech_ref)
        base = 100 * ((0.45 * density + 0.25 * audience + 0.15 * echo + 0.15 * speech)
                      if has_users else (0.70 * density + 0.15 * echo + 0.15 * speech))
        multiplier = (_loudness_multiplier(extra.get("loudness_db"), loud_ref, .95, 1.15)
                      * _ratio_multiplier(extra.get("laugh_rate"), laugh_ref, .95, 1.15)
                      * _shape_multiplier(row["shape_score"]))
        # 命中合规风险词：内容可能不宜公开传播，直接压低分数并标记
        if extra.get("risk_terms"):
            multiplier *= .60
        scores.append(max(0, min(100, round(base * multiplier))))

    # 第二轮：从第一轮高分切片提取本场热词与金句，并叠加主播画像
    vocabulary: list[str] = []
    quotes: list[dict] = []
    matched: list[dict] | None = None
    if directory is not None:
        meta = danmaku_meta or read_store(directory) or {}
        key, label = clip_vocab.streamer_label(_read_job(directory), meta)
        profile = clip_vocab.load_profile(vocab_root, key)
        picked = clip_vocab.high_segments(segments, scores)
        high = [segments[index] for index in picked]
        extracted = clip_vocab.extract_hot_terms(high, entries)
        quotes = clip_vocab.extract_quotes(
            [(segments[index], rows[index]["peak_time"], scores[index]) for index in picked], zh_cues)
        terms = clip_vocab.session_terms(profile, extracted)
        matched = clip_vocab.score_segments(segments, ja_cues, zh_cues, terms, entries)
        # 展示用热词只保留短语级长度，超长整句仍参与字幕匹配但不铺进标签
        vocabulary = [term for term, _ in extracted if len(term) <= 12][:16]
        store["streamer"] = label
        store["vocabulary"] = vocabulary
        store["quotes"] = quotes
        if vocab_root is not None and (extracted or quotes):
            try:
                clip_vocab.save_profile(
                    vocab_root, key, clip_vocab.merge_profile(profile, label, extracted, quotes))
            except OSError:
                pass
    meme_ref = _quantile([row["meme_rate"] for row in matched], .95) if matched else 0.0

    for index, (segment, row) in enumerate(zip(segments, rows)):
        extra = extras[index] if extras else {}
        score = scores[index]
        if matched is not None:
            match = matched[index]
            if meme_ref > 0:
                score = round(score * (1 + .15 * min(1.0, match["meme_rate"] / meme_ref)))
            segment["meme_hits"] = match["meme_hits"]
            segment["meme_rate"] = match["meme_rate"]
            segment["hot_words"] = match["hot_words"]
        segment["dm_count"] = row["count"]
        segment["dm_rate"] = round(row["rate"], 2)
        segment["dm_users"] = row["users"]
        segment["dm_peak"] = row["peak"]
        segment["dm_peak_time"] = round(row["peak_time"], 1) if row["peak_time"] is not None else None
        segment["dm_repeat"] = round(row["repeat"], 3)
        segment["dm_shape"] = row["shape"]
        segment["dm_shape_score"] = round(row["shape_score"], 2)
        segment["risk"] = bool(extra.get("risk_terms"))
        segment["score"] = max(0, min(100, score))
        segment["grade"] = "高" if segment["score"] >= 70 else "中" if segment["score"] >= 40 else "低"
    store["scored_at"] = time.time()
    return True


def apply(directory: Path, store: dict, *, words: clip_words.Lexicon | None = None,
          build_audio: bool = False, vocab_root: Path | None = None) -> dict:
    """给内容切片补齐音频/风险因子，提取热词金句并（有弹幕时）打分。"""
    data = read_store(directory)
    entries = data.get("entries") or [] if data else []
    if score_store(store, entries, directory=directory, words=words, build_audio=build_audio,
                   vocab_root=vocab_root, danmaku_meta=data):
        media.write_json(directory / "topic_segments.json", store)
    return store
