"""Tracked adaptation of 69d3fa0 audio_factors; excitation is an acoustic proxy, not laughter detection."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import Field

from app.arctime.subtitle_encoding import subtitle_ffmpeg
from app.arctime.topic_models import TopicModel, TopicSegmentStore
from app.services.task_execution import Execution


class AudioFeatures(TopicModel):
    state: Literal["available", "truncated", "unavailable"] = "unavailable"
    loudness: list[float] = Field(default_factory=list, max_length=86400)
    tone: list[float] = Field(default_factory=list, max_length=86400)
    group_seconds: float = 0.5


def audio_features(
    execution: Execution, source: Path, duration: float
) -> AudioFeatures:
    workspace = execution.staging("topic-audio")
    pcm = workspace / "audio.s16le"
    try:
        result = execution.run_command(
            [
                subtitle_ffmpeg(),
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-i",
                str(source),
                "-t",
                str(min(duration, 43200.0)),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                str(pcm),
            ],
            timeout=1800,
        )
    except (OSError, subprocess.SubprocessError):
        return AudioFeatures()
    execution.check()
    if (
        result.returncode != 0
        or not pcm.is_file()
        or not 16000 <= pcm.stat().st_size <= 1382400000
    ):
        return AudioFeatures()
    loudness, tone = [], []
    with pcm.open("rb") as stream:
        while len(loudness) < 86400:
            execution.check()
            block = stream.read(16000 * 64)
            if len(block) < 16000:
                break
            for offset in range(0, len(block) - 15999, 16000):
                samples = np.frombuffer(
                    block[offset : offset + 16000], dtype="<i2"
                ).astype(np.float32)
                power = float(np.mean(samples * samples))
                loudness.append(
                    round(20 * math.log10(max(math.sqrt(power), 1.0) / 32768), 1)
                )
                difference = np.diff(samples)
                tone.append(
                    round(float(np.mean(difference * difference)) / (power + 1e-9), 3)
                )
    if not loudness:
        return AudioFeatures()
    return AudioFeatures(
        state="truncated" if duration > 43200 else "available",
        loudness=loudness,
        tone=tone,
    )


def apply_audio(store: TopicSegmentStore, audio: AudioFeatures) -> TopicSegmentStore:
    if not audio.loudness:
        return store.model_copy(update={"audio_state": "unavailable"})
    loud_ref = float(np.quantile(audio.loudness, 0.75))
    tone_ref = float(np.quantile(audio.tone, 0.65))
    excited = [
        loud >= loud_ref and tone >= tone_ref
        for loud, tone in zip(audio.loudness, audio.tone, strict=True)
    ]
    segments = []
    for segment in store.segments:
        first = max(0, int(segment.start_seconds / 0.5))
        last = min(len(audio.loudness), math.ceil(segment.end_seconds / 0.5))
        window = audio.loudness[first:last]
        segments.append(
            segment.model_copy(
                update={
                    "loudness_db": round(float(np.quantile(window, 0.95)), 1)
                    if window
                    else None,
                    "laugh_rate": round(
                        sum(excited[first:last])
                        / (segment.end_seconds - segment.start_seconds)
                        * 60,
                        1,
                    )
                    if window
                    else None,
                }
            )
        )
    return store.model_copy(update={"audio_state": audio.state, "segments": segments})
