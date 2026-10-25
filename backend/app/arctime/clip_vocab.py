"""从弹幕与字幕中动态提取高分热词、金句，并按主播累积画像。

两阶段打分：
1. 第一轮只用不含词表的指标（弹幕密度、峰值、音频、风险）给切片打分；
2. 只从第一轮的高分切片里提取热词（弹幕 n-gram，按相对全场的提升度筛选）
   与金句（弹幕峰值时刻对齐字幕），第二轮再用这些热词加分。

画像按主播（B站稿件的 UP 主 mid）累积；本场热词优先，历史画像做平滑，
避免冷启动和单场噪声。提取只依赖第一轮分数，不会被历史画像反向强化。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from bisect import bisect_left
from collections import Counter
from pathlib import Path

from app.arctime import media

NGRAM_MIN = 2
NGRAM_MAX = 4
MIN_TERM_COUNT = 2
MIN_LIFT = 1.5
TOP_TERMS = 20
MAX_PROFILE_TERMS = 200
MAX_MATCH_TERMS = 160
MAX_QUOTES = 30
TOP_QUOTES = 8
PROFILE_DECAY = 0.85
HISTORY_WEIGHT = 0.6

# 高频但无区分度的泛用词，不计入热词
_GENERIC = frozenset("""
哈哈 哈哈哈 哈哈哈哈 草 草草 草草草 笑死 好耶 来了 来了来了 前排 打卡 签到 抽奖 中奖 关注 主播 直播
直播间 上号 什么 这个 那个 就是 真的 可以 没有 不是 已经 现在 今天 感觉 有点 一下 这样 那样 时候
自己 我们 你们 他们 草生 草生えた www wwww 233 666 awsl yyds 好听 可爱 喜欢 谢谢 谢谢主播
的话 一直 一样 动态 有人 知道 然后 但是 还是 应该 可能 怎么 之前 之后 这里 那里
""".split())
_RUN = re.compile(r"[0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]+")
# 长句按脚本切块（英文数字 / 假名 / 汉字），避免「不安desu」这类混排产出「安des」碎片
_SCRIPT = re.compile(r"[0-9A-Za-z]+|[\u3040-\u30ff\u30fc]+|[\u4e00-\u9fff]+")
MAX_TERM_LEN = 20
MAX_PROFILE_BYTES = 2 * 1024 * 1024


def _terms(text: str) -> set[str]:
    """抽取候选词：整句优先，长句再按脚本切块或退化为 2–4 字 n-gram。

    弹幕多数本身就是短句，直接整句计数比 n-gram 更干净；只有超长句才拆碎片，
    并跳过混排里的英文残片（如「不安desu」里的 desu），保留纯英文弹幕。
    """
    found: set[str] = set()
    for run in _RUN.findall(text):
        if run.isascii():
            lowered = run.lower()
            if 2 <= len(lowered) <= MAX_TERM_LEN:
                found.add(lowered)
            continue
        if 2 <= len(run) <= MAX_TERM_LEN:
            found.add(run)
        for chunk in _SCRIPT.findall(run):
            if chunk.isascii():
                continue
            if 2 <= len(chunk) <= 8:
                found.add(chunk)
                continue
            for size in range(NGRAM_MIN, NGRAM_MAX + 1):
                for index in range(len(chunk) - size + 1):
                    found.add(chunk[index:index + size])
    return found


def _valid(term: str) -> bool:
    return (bool(term) and term not in _GENERIC and not term.isdigit()
            and 2 <= len(term) <= MAX_TERM_LEN)


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(math.floor(position))
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def streamer_label(job: dict | None, danmaku_store: dict | None) -> tuple[str, str]:
    """确定画像键与展示名：优先 B站 UP 主 mid，其次来源链接，最后归入全局。"""
    store = danmaku_store or {}
    mid = str(store.get("owner_mid") or "").strip()
    name = str(store.get("owner_name") or "").strip()
    if mid:
        return f"bili:{mid}", name or f"UP {mid}"
    url = str((job or {}).get("url") or "").strip()
    if "bilibili.com" in url:
        return "bili:unknown", "未识别主播（B站）"
    if url:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
        return f"url:{digest}", "未识别主播（来源链接）"
    return "default", "未识别主播"


def profile_path(root: Path, key: str) -> Path:
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", key)[:48] or "default"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return root / f"{safe}-{digest}.json"


def load_profile(root: Path | None, key: str) -> dict:
    empty = {"terms": {}, "quotes": [], "sessions": 0}
    if root is None:
        return empty
    path = profile_path(root, key)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PROFILE_BYTES:
            return empty
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(value, dict):
        return empty
    terms = value.get("terms")
    quotes = value.get("quotes")
    return {"terms": terms if isinstance(terms, dict) else {},
            "quotes": quotes if isinstance(quotes, list) else [],
            "sessions": int(value.get("sessions") or 0)}


def merge_profile(profile: dict, label: str, extracted: list[tuple[str, float]],
                  quotes: list[dict]) -> dict:
    """历史权重衰减后叠加本场提取结果，得到新的主播画像。"""
    terms: dict[str, float] = {}
    for term, weight in (profile.get("terms") or {}).items():
        if _valid(str(term)):
            try:
                terms[str(term)] = float(weight) * PROFILE_DECAY
            except (TypeError, ValueError):
                continue
    for term, weight in extracted:
        terms[term] = terms.get(term, 0.0) + float(weight)
    ranked = sorted(terms.items(), key=lambda item: item[1], reverse=True)[:MAX_PROFILE_TERMS]
    merged_quotes: list[dict] = []
    seen: set[str] = set()
    for item in [*quotes, *(profile.get("quotes") or [])]:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text") or "").split())
        if not text or text in seen or len(text) > 80:
            continue
        seen.add(text)
        merged_quotes.append({"text": text,
                              "start": item.get("start"),
                              "score": item.get("score")})
        if len(merged_quotes) >= MAX_QUOTES:
            break
    return {"version": 1, "label": label, "sessions": int(profile.get("sessions") or 0) + 1,
            "terms": dict(ranked), "quotes": merged_quotes, "updated_at": time.time()}


def save_profile(root: Path | None, key: str, payload: dict) -> None:
    if root is None:
        return
    root.mkdir(parents=True, exist_ok=True)
    media.write_json(profile_path(root, key), payload)


def high_segments(segments: list[dict], scores: list[float]) -> list[int]:
    """按第一轮分数挑出用于提取的热门切片；门槛不够时退回前 3 段。"""
    if not segments:
        return []
    ordered = sorted(range(len(segments)), key=lambda index: scores[index], reverse=True)
    threshold = max(60.0, _quantile(scores, .7))
    picked = [index for index in ordered if scores[index] >= threshold]
    return picked or ordered[:min(3, len(ordered))]


def extract_hot_terms(high: list[dict], entries: list[list]) -> list[tuple[str, float]]:
    """从高分切片弹幕里提取相对全场有提升的词，返回 (词, 权重)。"""
    if not high or not entries:
        return []
    times = [float(item[0]) if item else 0.0 for item in entries]
    high_counts: Counter[str] = Counter()
    high_total = 0
    for segment in high:
        start = float(segment.get("start_seconds") or 0)
        end = float(segment.get("end_seconds") or 0)
        for index in range(bisect_left(times, start), bisect_left(times, end)):
            high_total += 1
            high_counts.update(_terms(str(entries[index][1] or "")))
    if high_total == 0:
        return []
    all_counts: Counter[str] = Counter()
    for item in entries:
        all_counts.update(_terms(str(item[1] or "")))
    total = max(1, len(entries))
    ranked: list[tuple[str, float]] = []
    for term, count in high_counts.items():
        if not _valid(term) or count < MIN_TERM_COUNT:
            continue
        lift = (count / high_total) / (max(1, all_counts.get(term, count)) / total)
        if lift < MIN_LIFT:
            continue
        ranked.append((term, count * min(lift, 6.0)))
    if not ranked:
        # 高分段几乎覆盖全场时提升度失效，退回纯高频词（仍需至少出现 3 次）
        ranked = [(term, float(count)) for term, count in high_counts.items()
                  if _valid(term) and count >= 3]
    return _dedupe(ranked)[:TOP_TERMS]


def _dedupe(ranked: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """n-gram 会同时产出整句与碎片；按覆盖度去重，保留更完整、更有区分度的候选。"""
    picked: list[tuple[str, float]] = []
    # 去重顺序按「权重 × 长度」：权重接近时先选整句，避免「有人」把整句挤成碎片
    for term, weight in sorted(ranked, key=lambda item: -(item[1] * (1 + .5 * len(item[0])))):
        if any(term in chosen or chosen in term for chosen, _ in picked):
            continue
        picked.append((term, weight))
    picked.sort(key=lambda item: (-item[1], -len(item[0])))
    return picked


def extract_quotes(high: list[tuple[dict, float | None, float | None]], zh_cues: list) -> list[dict]:
    """用弹幕峰值时刻对齐字幕，挑出可直接当标题用的金句。"""
    quotes: list[dict] = []
    seen: set[str] = set()
    for segment, peak, score in high:
        if peak is None:
            continue
        start = float(segment.get("start_seconds") or 0)
        end = float(segment.get("end_seconds") or 0)
        candidates = [cue for cue in zh_cues
                      if cue.end_seconds >= peak - 1 and cue.start_seconds <= peak + 8
                      and cue.start_seconds >= start - 1 and cue.start_seconds <= end]
        if not candidates:
            continue
        best = min(candidates, key=lambda cue: abs(cue.start_seconds - peak))
        text = " ".join(str(best.text or "").split())
        if not 4 <= len(text) <= 80 or text in seen:
            continue
        seen.add(text)
        quotes.append({"text": text, "start": round(float(best.start_seconds), 1),
                       "score": score})
        if len(quotes) >= TOP_QUOTES:
            break
    return quotes


def session_terms(profile: dict, extracted: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """本场热词优先，历史画像平滑后并入，最终权重归一到 0–1。"""
    history: dict[str, float] = {}
    for term, weight in (profile.get("terms") or {}).items():
        if _valid(str(term)):
            try:
                history[str(term)] = float(weight)
            except (TypeError, ValueError):
                continue
    merged: dict[str, float] = {}
    if history:
        top = max(history.values()) or 1.0
        # 历史词最多贡献 HISTORY_WEIGHT，避免老画像盖过本场信号
        merged = {term: HISTORY_WEIGHT * weight / top for term, weight in history.items()}
    if extracted:
        top = max((weight for _, weight in extracted), default=1.0) or 1.0
        for term, weight in extracted:
            merged[term] = min(1.0, merged.get(term, 0.0) + weight / top)
    ranked = sorted(merged.items(), key=lambda item: item[1], reverse=True)[:MAX_MATCH_TERMS]
    return ranked


def score_segments(segments: list[dict], ja_cues: list, zh_cues: list,
                   terms: list[tuple[str, float]], entries: list[list] | None = None) -> list[dict]:
    """统计每个切片命中热词的次数与加权密度。

    同时看主播说的话（原/译文字幕）和观众弹幕：字幕命中说明主播本人在抛这个梗，
    弹幕命中说明观众在同一段里反复刷，两者都是这个切片值得剪的信号。
    """
    times = [float(item[0]) if item else 0.0 for item in entries or []]
    match_terms = terms[:60]
    rows: list[dict] = []
    for segment in segments:
        start = float(segment.get("start_seconds") or 0)
        end = float(segment.get("end_seconds") or 0)
        duration = max(end - start, 0.001)
        ja_text = "".join(cue.text for cue in ja_cues if cue.end_seconds > start and cue.start_seconds < end)
        zh_text = "".join(cue.text for cue in zh_cues if cue.end_seconds > start and cue.start_seconds < end)
        parts = [zh_text, ja_text]
        if entries:
            parts.extend(str(entries[index][1] or "")
                         for index in range(bisect_left(times, start), bisect_left(times, end)))
        text = "\n".join(parts)
        hits = 0
        weighted = 0.0
        matched: list[tuple[str, float]] = []
        for term, weight in match_terms:
            count = text.count(term)
            if not count:
                continue
            hits += count
            weighted += count * weight
            matched.append((term, weight))
        matched.sort(key=lambda item: item[1], reverse=True)
        rows.append({"meme_hits": hits,
                     "meme_rate": round(weighted / duration * 60, 2),
                     "hot_words": [term for term, _ in matched[:8]]})
    return rows
