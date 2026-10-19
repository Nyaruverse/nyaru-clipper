from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from app.arctime import media
from app.services.subtitles import SubtitleSegment

CHUNK_SECONDS = 300
ASR_TAIL_WINDOW_SECONDS = 30.0
ASR_CACHE_VERSION = 2  # v2: whisper 幻觉过滤（v1 缓存不自动重识别）
HALLUCINATION_MIN_REPEATS = 5   # 同一段归一化文本至少出现 N 次才算幻觉候选
HALLUCINATION_MAX_LEN = 60      # whisper 幻觉通常短，超长文本大概率为真
HALLUCINATION_MAX_GAP = 15.0    # 重复之间相邻时间间隔中位数 > 此值视为真实语音

# 字幕单行显示宽度上限：全角字符 ≤ 20 个，英文/数字等半角字符 ≤ 28 个。
# 半角按 20/28 折算宽度，混排行按宽度之和判定，避免语速快时长行超出显示区域。
MAX_LINE_WIDTH = 20.0
HALF_WIDTH_RATIO = 20.0 / 28.0
# 切分时优先在这些断句符号处断开（含空格与换行）
_LINE_BREAK_CHARS = "、。！？!?，,：:；;…．.・「」『』（）()【】　 \t"

# whisper multilingual 模型对无语音音频吐出的已知幻觉模板黑名单。
# 这些模板对任何语言都可能出现，直接命中即剔除（不计入重复次数）。
_HALLUCINATION_BLACKLIST = {
    "1/2 cwm fawr.",          # 威尔士语 "半个大风"，whisper multilingual 经典幻觉
    "cwm fawr",
    "fawr.",
    "fawr",
}


def _normalize(text: str) -> str:
    """归一化用于 whisper 幻觉重复匹配：去空格/标点/大小写。"""
    return re.sub(r"[\s\W_]+", "", text.lower())


def _filter_whisper_hallucinations(rows: list[dict]) -> list[dict]:
    """过滤 whisper 典型幻觉：密集重复的短文本簇。

    whisper 对纯音乐/长静音/背景声段容易吐出固定模板（如威尔士语 "cwm fawr"），
    特征是短文本以 2~10 秒周期密集重复几十次，不同于真实语音同一句话间隔较远。
    规则：
    1. 命中黑名单模板直接剔除（整行完全匹配）
    2. 归一化后出现 >= MIN_REPEATS 次 且 相邻重复的时间间隔中位数 <= MAX_GAP 秒
       且原文不长 → 只保留第一次
    3. 过滤后剩余 rows 极少 (<3 条 或 总字符 <20) → 整段视为无有效语音，返回空列表
    """
    if not rows:
        return rows
    # 先剔除黑名单模板（整行完全匹配，忽略前后空白与标点）
    def clean(text: str) -> str:
        return text.strip().rstrip("。！？!?.,，、").strip()
    filtered = [r for r in rows if clean(r.get("text", "")).lower() not in _HALLUCINATION_BLACKLIST]
    if not filtered:
        return []
    # 再按归一化文本计数 + 相邻间隔判定过滤密集重复簇
    from statistics import median
    key_times: dict[str, list[float]] = {}
    for r in filtered:
        key = _normalize(r.get("text", ""))
        if not key:
            continue
        key_times.setdefault(key, []).append(r.get("start_seconds", 0.0))
    hallucination_keys: set[str] = set()
    for key, times in key_times.items():
        n = len(times)
        if n < HALLUCINATION_MIN_REPEATS or len(key) > HALLUCINATION_MAX_LEN:
            continue
        # 相邻出现时间差的中位数
        times.sort()
        gaps = [times[i + 1] - times[i] for i in range(n - 1)]
        gap_median = median(gaps) if gaps else 0.0
        if gap_median <= HALLUCINATION_MAX_GAP:
            hallucination_keys.add(key)
    if not hallucination_keys:
        return filtered
    kept: list[dict] = []
    seen: set[str] = set()
    for r in filtered:
        k = _normalize(r.get("text", ""))
        if k in hallucination_keys and k in seen:
            continue
        seen.add(k)
        kept.append(r)
    # 整段无有效语音：返回空 rows 让上层视为"该 chunk 静音"，而非把幻觉写进字幕
    if len(kept) < 3 or sum(len(r.get("text", "")) for r in kept) < 20:
        return []
    return kept


def _char_width(ch: str) -> float:
    """全角字符（CJK/全角标点/半角假名等）宽 1，ASCII 半角字符按 20/28 折算。"""
    return 1.0 if ord(ch) > 0x7E else HALF_WIDTH_RATIO


def _line_width(text: str) -> float:
    return sum(_char_width(ch) for ch in text)


def _split_text_lines(text: str) -> list[str]:
    """把超宽单行文本切为多行：贪心按宽度推进，断点优先取断句符号，无符号则硬切。"""
    text = " ".join(text.split())  # 折叠换行与连续空白
    if _line_width(text) <= MAX_LINE_WIDTH:
        return [text] if text else []
    parts: list[str] = []
    current = ""
    for ch in text:
        if _line_width(current + ch) > MAX_LINE_WIDTH and current:
            cut = max(current.rfind(c) for c in _LINE_BREAK_CHARS)
            head = current[:cut + 1].strip() if cut >= 0 else ""
            tail = current[cut + 1:].strip() if cut >= 0 else ""
            if head and tail:
                # 断句符号留在上一行行尾，其后内容并入下一行继续推进
                parts.append(head)
                current = (tail + ch).strip()
                continue
            parts.append(current.strip())
            current = ch
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


def _split_long_rows(rows: list[dict]) -> list[dict]:
    """对超出显示宽度的字幕行按字符宽度占比切分时间轴，生成多条短行。

    在 ASR 缓存读取之后执行：旧缓存无需重识别，切分结果确定可复现。
    """
    result: list[dict] = []
    for row in rows:
        text = " ".join(str(row.get("text", "")).split())
        parts = _split_text_lines(text) if text else []
        if len(parts) <= 1:
            result.append({**row, "text": text} if text != row.get("text") else row)
            continue
        start, end = row["start_seconds"], row["end_seconds"]
        widths = [_line_width(part) for part in parts]
        total = sum(widths) or 1.0
        cursor = start
        for position, (part, width) in enumerate(zip(parts, widths)):
            if position == len(parts) - 1:
                piece_end = end
            else:
                piece_end = min(end - 0.05, max(cursor + 0.2, cursor + (end - start) * width / total))
            result.append({**row, "start_seconds": round(cursor, 3),
                           "end_seconds": round(max(piece_end, cursor + 0.05), 3), "text": part})
            cursor = piece_end
    return result


def resolve_default_model() -> Path:
    """解析默认 whisper.cpp 模型路径。

    优先级：NYARU_WHISPER_MODEL 环境变量 → 项目内 data/model-cache/whisper.cpp/ggml-small.bin
    → 用户缓存目录 ~/.cache/nyaru-clipper/models/ggml-small.bin
    """
    env = os.environ.get("NYARU_WHISPER_MODEL", "").strip()
    if env:
        return Path(env).expanduser()
    repo_model = Path(__file__).resolve().parents[3] / "data" / "model-cache" / "whisper.cpp" / "ggml-small.bin"
    if repo_model.is_file():
        return repo_model
    return Path.home() / ".cache" / "nyaru-clipper" / "models" / "ggml-small.bin"


DEFAULT_MODEL = resolve_default_model()


def _segments_hash(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class LocalASR:
    model: Path = field(default_factory=resolve_default_model)
    language: str = "auto"
    threads: int = 4

    def identity(self) -> dict:
        model = self.model.expanduser().resolve(strict=True)
        with model.open("rb") as handle:
            if handle.read(4) != b"lmgg":
                raise ValueError("Expected a whisper.cpp GGML model (.bin)")
        if not self.language.isascii() or not self.language.isalpha() or len(self.language) > 8:
            raise ValueError("Language must be a Whisper language code or auto")
        if not 1 <= self.threads <= 64:
            raise ValueError("Threads must be between 1 and 64")
        return {"engine": "whisper.cpp", "binary": media.tool_path("whisper-cli"),
                "model": str(model), "model_sha256": media.fingerprint(model),
                "language": self.language, "threads": self.threads,
                "chunk_seconds": CHUNK_SECONDS, "cache_version": ASR_CACHE_VERSION}

    def transcribe(self, video: Path, directory: Path, duration: float, offset: float = 0.0,
                   should_cancel: Callable[[], bool] | None = None) -> list[SubtitleSegment]:
        """转录视频的指定区间。

        duration：要转录的区间长度（秒）。
        offset：区间起点相对视频的偏移（秒）。0 = 从头开始。
        """
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("ASR requires a finite positive media duration")
        if not math.isfinite(offset) or offset < 0:
            raise ValueError("ASR offset must be non-negative")
        identity = self.identity()
        source_hash = media.fingerprint(video)
        cache = directory / "asr"
        if cache.is_symlink():
            raise ValueError("ASR cache must not be a symlink")
        cache.mkdir(exist_ok=True)
        cues: list[SubtitleSegment] = []
        for index in range(math.ceil(duration / CHUNK_SECONDS)):
            if should_cancel is not None and should_cancel():
                raise media.RunCancelled()
            start = offset + index * CHUNK_SECONDS
            length = min(CHUNK_SECONDS, duration - index * CHUNK_SECONDS)
            key = {"version": 2, "source_sha256": source_hash, "asr": identity,
                   "start": start, "duration": length, "offset": offset}
            destination = cache / f"chunk-{index + 1:04d}.json"
            if destination.is_symlink():
                raise ValueError("ASR chunk must not be a symlink")
            rows = self._cached_rows(destination, key)
            if rows is None:
                rows = self._recognize(video, cache, index + 1, start, length, identity)
                media.write_json(destination, {"key": key, "segments": rows, "segments_sha256": _segments_hash(rows)})
            # 长行按显示宽度切分（缓存读取后执行，旧缓存无需重识别即可生效）
            for row in _split_long_rows(rows):
                cues.append(SubtitleSegment(str(len(cues) + 1), start + row["start_seconds"],
                                            start + row["end_seconds"], row["text"]))
        if not cues:
            raise ValueError("No speech was recognized; check the source audio and language")
        return cues

    @staticmethod
    def _cached_rows(path: Path, key: dict) -> list[dict] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload["segments"]
            if payload["key"] != key or payload["segments_sha256"] != _segments_hash(rows):
                return None
            if not isinstance(rows, list) or any(
                not isinstance(row["text"], str) or not row["text"].strip()
                or not 0 <= row["start_seconds"] < row["end_seconds"] <= key["duration"]
                for row in rows
            ):
                return None
            if rows != sorted(rows, key=lambda row: (row["start_seconds"], row["end_seconds"])):
                return None
            return rows
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _recognize(self, video: Path, cache: Path, index: int, start: float, length: float, identity: dict) -> list[dict]:
        log_path = cache / f"chunk-{index:04d}.log"
        if log_path.is_symlink():
            raise ValueError("ASR log must not be a symlink")
        with tempfile.TemporaryDirectory(prefix=f".chunk-{index:04d}-", dir=cache) as temporary:
            audio = Path(temporary) / "audio.wav"
            prefix = Path(temporary) / f"chunk-{index:04d}"
            commands = [
                [media.tool_path("ffmpeg"), "-nostdin", "-v", "error", "-y", "-ss", str(start), "-i", str(video),
                 "-t", str(length), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)],
                [identity["binary"], "-m", identity["model"], "-f", str(audio), "-l", self.language,
                 "-t", str(self.threads), "-osrt", "-of", str(prefix), "-ml", "80", "-sow", "-np"],
            ]
            with log_path.open("w", encoding="utf-8") as log:
                for command in commands:
                    result = media.run_managed(command, stdin=subprocess.DEVNULL, stdout=log,
                                               stderr=subprocess.STDOUT, timeout=7200)
                    if result.returncode:
                        raise RuntimeError(f"Local audio extraction or ASR failed; see asr/{log_path.name}")
            subtitle = prefix.with_suffix(".srt")
            if not subtitle.is_file():
                raise RuntimeError(f"Local ASR failed to produce subtitles; see asr/{log_path.name}")
            if not subtitle.read_text(encoding="utf-8-sig").strip():
                return []
            segments = media.read_subtitles(subtitle, merge_contiguous_zero_duration=True)
            tail_window = min(ASR_TAIL_WINDOW_SECONDS, length / 2)
            if any(c.end_seconds > length and (c.start_seconds < length - tail_window
                                               or c.end_seconds > length + tail_window) for c in segments):
                raise ValueError("Local ASR timestamps exceed chunk duration")
            rows = [asdict(SubtitleSegment(c.id, c.start_seconds, min(c.end_seconds, length), c.text))
                    for c in segments if c.start_seconds < length]
            rows = _filter_whisper_hallucinations(rows)
            return rows
