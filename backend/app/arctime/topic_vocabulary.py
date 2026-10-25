"""Pure hot-term extraction adapted from 69d3fa0 clip_vocab.py (same-session lift and history smoothing)."""

from __future__ import annotations

import re
from collections import Counter

from app.arctime.topic_models import DanmakuEntry, TopicSegment

_GENERIC = frozenset(
    "哈哈 哈哈哈 哈哈哈哈 草 草草 草草草 笑死 好耶 来了 来了来了 前排 打卡 签到 抽奖 中奖 关注 主播 直播 直播间 上号 什么 这个 那个 就是 真的 可以 没有 不是 已经 现在 今天 感觉 有点 一下 这样 那样 时候 自己 我们 你们 他们 草生 草生えた www wwww 233 666 awsl yyds 好听 可爱 喜欢 谢谢 谢谢主播 的话 一直 一样 动态 有人 知道 然后 但是 还是 应该 可能 怎么 之前 之后 这里 那里".split()
)


def _terms(text: str) -> set[str]:
    found = set()
    for run in re.findall(r"[0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]+", text):
        if run.isascii():
            if 2 <= len(run) <= 20:
                found.add(run.lower())
            continue
        if 2 <= len(run) <= 20:
            found.add(run)
        for chunk in re.findall(
            r"[0-9A-Za-z]+|[\u3040-\u30ff\u30fc]+|[\u4e00-\u9fff]+", run
        ):
            if chunk.isascii():
                continue
            if 2 <= len(chunk) <= 8:
                found.add(chunk)
                continue
            for size in range(2, 5):
                for index in range(len(chunk) - size + 1):
                    found.add(chunk[index : index + size])
    return {
        term
        for term in found
        if term not in _GENERIC and not term.isdigit() and 2 <= len(term) <= 20
    }


def extract_terms(
    high: list[TopicSegment], entries: list[DanmakuEntry]
) -> list[tuple[str, float]]:
    selected = [
        entry
        for entry in entries
        if any(
            segment.start_seconds <= entry.seconds < segment.end_seconds
            for segment in high
        )
    ]
    if not selected:
        return []
    counts = Counter(term for entry in selected for term in _terms(entry.text))
    all_counts = Counter(term for entry in entries for term in _terms(entry.text))
    ranked = []
    for term, count in counts.items():
        lift = (count / len(selected)) / (all_counts[term] / len(entries))
        if count >= 2 and lift >= 1.5:
            ranked.append((term, count * min(lift, 6.0)))
    if not ranked:
        ranked = [(term, float(count)) for term, count in counts.items() if count >= 3]
    picked = []
    for term, weight in sorted(
        ranked, key=lambda item: -(item[1] * (1 + 0.5 * len(item[0])))
    ):
        if not any(term in chosen or chosen in term for chosen, _ in picked):
            picked.append((term, weight))
    return sorted(picked, key=lambda item: (-item[1], -len(item[0])))[:20]


def session_terms(
    profile: dict[str, float], extracted: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    top = max(profile.values(), default=1.0) or 1.0
    merged = {term: 0.6 * weight / top for term, weight in profile.items()}
    top = max((weight for _, weight in extracted), default=1.0) or 1.0
    for term, weight in extracted:
        merged[term] = min(1.0, merged.get(term, 0.0) + weight / top)
    return sorted(merged.items(), key=lambda item: -item[1])[:60]
