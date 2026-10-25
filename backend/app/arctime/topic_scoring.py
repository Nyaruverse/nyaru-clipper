"""Pure, bounded adaptation of 69d3fa0 danmaku/clip_vocab heuristics; no runtime file writes."""

from __future__ import annotations

import math
import time

from app.arctime.subtitle_document import Cue
from app.arctime.topic_models import (
    DanmakuEntry,
    ScoringConfig,
    TopicQuote,
    TopicSegmentStore,
)


def _quantile(values: list[float], q: float = 0.95) -> float:
    ordered = sorted(values)
    position = (len(values) - 1) * q
    low = math.floor(position)
    return (
        ordered[low] * (1 - position + low)
        + ordered[min(low + 1, len(values) - 1)] * (position - low)
        or 1.0
    )


def score_topics(
    store: TopicSegmentStore,
    cues: list[Cue],
    entries: list[DanmakuEntry],
    config: ScoringConfig,
) -> TopicSegmentStore:
    segments = []
    for segment in store.segments:
        text = "\n".join(
            cue.text + "\n" + cue.translation
            for cue in cues
            if cue.end_seconds > segment.start_seconds
            and cue.start_seconds < segment.end_seconds
        )
        risks = [
            term for term in config.risk_terms if term.casefold() in text.casefold()
        ][:12]
        segments.append(
            segment.model_copy(update={"risk_terms": risks, "risk": bool(risks)})
        )
    if not entries or not segments:
        return store.model_copy(
            update={"segments": segments, "streamer": config.streamer}
        )
    windows = [
        [
            entry
            for entry in entries
            if segment.start_seconds <= entry.seconds < segment.end_seconds
        ]
        for segment in segments
    ]
    rates = [
        len(window) / (segment.end_seconds - segment.start_seconds)
        for window, segment in zip(windows, segments, strict=True)
    ]
    users = [len({entry.user for entry in window if entry.user}) for window in windows]
    repeats = [
        (len(window) - len({entry.text for entry in window})) / len(window)
        if window
        else 0.0
        for window in windows
    ]
    speech = [
        segment.cue_count / (segment.end_seconds - segment.start_seconds)
        for segment in segments
    ]
    refs = [_quantile(values) for values in (rates, users, repeats, speech)]
    loud_values = [
        segment.loudness_db for segment in segments if segment.loudness_db is not None
    ]
    laugh_values = [
        segment.laugh_rate for segment in segments if segment.laugh_rate is not None
    ]
    loud_ref = _quantile(loud_values) if loud_values else 0.0
    laugh_ref = _quantile(laugh_values) if laugh_values else 0.0
    has_users = any(entry.user for entry in entries)
    scores, peaks = [], []
    for index, (segment, window) in enumerate(zip(segments, windows, strict=True)):
        left, peak, peak_time = 0, 0, None
        for right, entry in enumerate(window):
            while entry.seconds - window[left].seconds > 10:
                left += 1
            if right - left + 1 > peak:
                peak, peak_time = right - left + 1, window[left].seconds
        thirds = [0, 0, 0]
        for entry in window:
            thirds[
                min(
                    2,
                    int(
                        (entry.seconds - segment.start_seconds)
                        / (segment.end_seconds - segment.start_seconds)
                        * 3
                    ),
                )
            ] += 1
        shape, shape_score = ("平稳", 0.7) if window else ("无弹幕", 0.45)
        if (
            window
            and segment.end_seconds - segment.start_seconds >= 20
            and peak / len(window) >= 0.5
        ):
            shape, shape_score = "尖峰", 1.0
        elif len(window) >= 5 and thirds[2] >= 2 * max(thirds[0], 1):
            shape, shape_score = "递增", 0.85
        elif len(window) >= 5 and thirds[0] >= 2 * max(thirds[2], 1):
            shape, shape_score = "递减", 0.75
        density, audience, echo, talk = [
            min(1.0, values[index] / ref)
            for values, ref in zip((rates, users, repeats, speech), refs, strict=True)
        ]
        score = (
            100 * ((0.45 * density + 0.25 * audience) if has_users else 0.70 * density)
            + 15 * echo
            + 15 * talk
        )
        loud_multiplier = (
            0.95 + 0.2 * min(1.0, 10 ** ((segment.loudness_db - loud_ref) / 20))
            if segment.loudness_db is not None and loud_ref
            else 1.0
        )
        laugh_multiplier = (
            0.95 + 0.2 * min(1.0, segment.laugh_rate / laugh_ref)
            if segment.laugh_rate is not None and laugh_ref
            else 1.0
        )
        score = round(
            score
            * (0.95 + 0.15 * (shape_score - 0.45) / 0.55)
            * loud_multiplier
            * laugh_multiplier
            * (0.6 if segment.risk else 1)
        )
        scores.append(min(100, max(0, score)))
        peaks.append(peak_time)
        segments[index] = segment.model_copy(
            update={
                "dm_count": len(window),
                "dm_rate": round(rates[index], 2),
                "dm_users": users[index] if has_users else None,
                "dm_repeat": round(repeats[index], 3),
                "dm_peak": peak,
                "dm_peak_time": peak_time,
                "dm_shape": shape,
                "dm_shape_score": shape_score,
            }
        )
    picked = sorted(range(len(segments)), key=lambda i: scores[i], reverse=True)
    picked = [
        i for i in picked if scores[i] >= max(60.0, _quantile(scores, 0.7))
    ] or picked[:3]
    from app.arctime.topic_vocabulary import extract_terms, session_terms

    extracted = extract_terms([segments[i] for i in picked], entries)
    vocabulary = [term for term, _ in extracted if len(term) <= 12]
    terms = session_terms(config.profile_terms, extracted)
    matches = []
    for i, segment in enumerate(segments):
        selected = [
            cue
            for cue in cues
            if cue.end_seconds > segment.start_seconds
            and cue.start_seconds < segment.end_seconds
        ]
        text = "\n".join(
            [
                *(cue.text + "\n" + cue.translation for cue in selected),
                *(entry.text for entry in windows[i]),
            ]
        )
        matched = [(term, weight) for term, weight in terms if term in text]
        hits = sum(text.count(term) for term, _ in matched)
        rate = (
            sum(text.count(term) * weight for term, weight in matched)
            / (segment.end_seconds - segment.start_seconds)
            * 60
        )
        matches.append((hits, rate, [term for term, _ in matched]))
    meme_ref = _quantile([row[1] for row in matches])
    quotes = []
    for i, segment in enumerate(segments):
        selected = [
            cue
            for cue in cues
            if cue.end_seconds > segment.start_seconds
            and cue.start_seconds < segment.end_seconds
        ]
        hits, rate, matched = matches[i]
        score = min(100, round(scores[i] * (1 + 0.15 * min(1.0, rate / meme_ref))))
        segments[i] = segment.model_copy(
            update={
                "score": score,
                "grade": "高" if score >= 70 else "中" if score >= 40 else "低",
                "meme_hits": hits,
                "meme_rate": round(rate, 2),
                "hot_words": matched[:8],
            }
        )
        if i in picked and peaks[i] is not None and selected:
            selected = [
                cue
                for cue in selected
                if cue.end_seconds >= peaks[i] - 1 and cue.start_seconds <= peaks[i] + 8
            ]
            if not selected:
                continue
            cue = min(selected, key=lambda cue: abs(cue.start_seconds - peaks[i]))
            text = cue.translation or cue.text
            if 4 <= len(text) <= 80 and text not in {quote.text for quote in quotes}:
                quotes.append(
                    TopicQuote(text=text, start=cue.start_seconds, score=score)
                )
    return store.model_copy(
        update={
            "segments": segments,
            "scoring": "danmaku_text_audio" if loud_values else "danmaku_text",
            "scored_at": time.time(),
            "vocabulary": vocabulary[:16],
            "extracted_terms": dict(extracted),
            "quotes": quotes[:8],
            "streamer": config.streamer,
        }
    )
