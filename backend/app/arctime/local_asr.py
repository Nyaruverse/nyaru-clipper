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
ASR_CACHE_VERSION = 4  # v4: 切片模式支持多区间独立转录（v3 及以前缓存不自动重识别）
HALLUCINATION_MIN_REPEATS = 5   # 同一段归一化文本至少出现 N 次才算幻觉候选
HALLUCINATION_MAX_LEN = 60      # whisper 幻觉通常短，超长文本大概率为真
HALLUCINATION_MAX_GAP = 15.0    # 重复之间相邻时间间隔中位数 > 此值视为真实语音

# 语言探测：whisper 只在传入音频的前 30 秒上做语言检测，而整段开头常是 BGM/纯音乐，
# 直接喂整段会被音乐带偏（实测把日语整段认成威尔士语，开头字幕全毁）。改为在区间内取
# 多个 30 秒窗口分别检测，取置信度最高的结果；置信度都太低则退回 whisper 自己的 auto。
LANGUAGE_PROBE_SECONDS = 30.0
LANGUAGE_PROBE_AT = (0.10, 0.35, 0.60, 0.85)
LANGUAGE_PROBE_MIN_PROB = 0.60

_LANGUAGE_RE = re.compile(r"auto-detected language:\s*([a-z]{2,3})\s*\(p\s*=\s*([0-9.]+)\)")

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


def _probe_language(identity: dict, video: Path, directory: Path, offset: float, duration: float,
                    should_cancel: Callable[[], bool] | None = None) -> str | None:
    """在区间内取多个 30 秒窗口做语言检测，返回置信度最高者；都不够确信则返回 None。

    避免开头 BGM 让 whisper 把整段语言认错（见 LANGUAGE_PROBE_* 注释）。只提取 30 秒小段，
    所以每个窗口的开销只是几秒的解码 + 语言头推理，与整段识别相比可忽略。
    """
    probe_len = min(LANGUAGE_PROBE_SECONDS, duration)
    if probe_len < 5.0:
        return None
    best: tuple[float, str] | None = None
    with tempfile.TemporaryDirectory(prefix=".lang-probe-", dir=directory) as temporary:
        audio = Path(temporary) / "probe.wav"
        for fraction in LANGUAGE_PROBE_AT:
            if should_cancel is not None and should_cancel():
                raise media.RunCancelled()
            start = offset + min(duration - probe_len, duration * fraction)
            try:
                extract = subprocess.run(
                    [media.tool_path("ffmpeg"), "-nostdin", "-v", "error", "-y", "-ss", f"{start:.3f}",
                     "-i", str(video), "-t", f"{probe_len:.3f}", "-vn", "-ac", "1", "-ar", "16000",
                     "-c:a", "pcm_s16le", str(audio)], capture_output=True, text=True, timeout=300, check=False)
                if extract.returncode:
                    continue
                detect = subprocess.run(
                    [identity["binary"], "-m", identity["model"], "-f", str(audio),
                     "-t", str(identity["threads"]), "-dl"], capture_output=True, text=True, timeout=600, check=False)
            except (OSError, subprocess.SubprocessError):
                continue
            match = _LANGUAGE_RE.search(f"{detect.stdout or ''}\n{detect.stderr or ''}")
            if match is None:
                continue
            probability = float(match.group(2))
            if probability >= LANGUAGE_PROBE_MIN_PROB and (best is None or probability > best[0]):
                best = (probability, match.group(1))
    return best[1] if best is not None else None


def resolve_default_model() -> Path:
    """解析默认 whisper.cpp 模型路径。

    优先级：NYARU_WHISPER_MODEL 环境变量 → 项目内 data/model-cache/whisper.cpp/
    （优先 large-v3-turbo，缺失时回退 small）→ 用户缓存目录同名文件。
    turbo 准确率明显高于 small，且换模型后 ASR 缓存会按 model_sha256 自动失效。
    """
    env = os.environ.get("NYARU_WHISPER_MODEL", "").strip()
    if env:
        return Path(env).expanduser()
    names = ("ggml-large-v3-turbo.bin", "ggml-small.bin")
    repo_root = Path(__file__).resolve().parents[3] / "data" / "model-cache" / "whisper.cpp"
    for name in names:
        if (repo_root / name).is_file():
            return repo_root / name
    cache_root = Path.home() / ".cache" / "nyaru-clipper" / "models"
    for name in names:
        if (cache_root / name).is_file():
            return cache_root / name
    return cache_root / "ggml-small.bin"


DEFAULT_MODEL = resolve_default_model()


def _segments_hash(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class LocalASR:
    model: Path = field(default_factory=resolve_default_model)
    language: str = "auto"
    threads: int = 4
    # 术语表原文拼成的初始提示词；为空时不传给 whisper，缓存行为与旧版本一致
    prompt: str = ""

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
                   should_cancel: Callable[[], bool] | None = None,
                   cache_prefix: str = "") -> list[SubtitleSegment]:
        """转录视频的指定区间。

        duration：要转录的区间长度（秒）。
        offset：区间起点相对视频的偏移（秒）。0 = 从头开始。
        cache_prefix：缓存文件名前缀，多区间独立转录时避免冲突。
        """
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("ASR requires a finite positive media duration")
        if not math.isfinite(offset) or offset < 0:
            raise ValueError("ASR offset must be non-negative")
        identity = self.identity()
        source_hash = media.fingerprint(video)
        # auto：先自己探测语言，探不出才交给 whisper 的 auto（避免开头 BGM 把整段语言带偏）
        language = self.language
        if language == "auto":
            language = _probe_language(identity, video, directory, offset, duration, should_cancel) or "auto"
        prompt = " ".join(self.prompt.split())[:400]
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
            key = {"version": ASR_CACHE_VERSION, "source_sha256": source_hash, "asr": identity,
                   "language": language, "start": start, "duration": length, "offset": offset}
            if prompt:
                # 提示词参与缓存键：术语表变化后旧分块自动失效
                key["prompt"] = prompt
            destination = cache / f"{cache_prefix}chunk-{index + 1:04d}.json"
            if destination.is_symlink():
                raise ValueError("ASR chunk must not be a symlink")
            rows = self._cached_rows(destination, key)
            if rows is None:
                rows = self._recognize(video, cache, index + 1, start, length, identity, language, prompt)
                media.write_json(destination, {"key": key, "segments": rows, "segments_sha256": _segments_hash(rows)})
            # 长行按显示宽度切分（缓存读取后执行，旧缓存无需重识别即可生效）
            for row in _split_long_rows(rows):
                cues.append(SubtitleSegment(str(len(cues) + 1), start + row["start_seconds"],
                                            start + row["end_seconds"], row["text"]))
        if not cues:
            raise ValueError("No speech was recognized; check the source audio and language")
        return cues

    def transcribe_ranges(self, video: Path, directory: Path,
                          ranges: list[tuple[float, float]],
                          should_cancel: Callable[[], bool] | None = None) -> list[SubtitleSegment]:
        """转录多个不连续区间，每个区间独立缓存、独立语言探测。

        ranges：[(start, end), ...]，单位秒，全局时间戳（相对于视频开头）。
        返回按时间排序的合并字幕。
        """
        if not ranges:
            raise ValueError("ASR ranges must not be empty")
        cues: list[SubtitleSegment] = []
        for i, (start, end) in enumerate(ranges):
            if should_cancel is not None and should_cancel():
                raise media.RunCancelled()
            sub = self.transcribe(video, directory, end - start, offset=start,
                                  should_cancel=should_cancel,
                                  cache_prefix=f"range-{i:04d}-")
            cues.extend(sub)
        return sorted(cues, key=lambda c: c.start_seconds)

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

    def _recognize(self, video: Path, cache: Path, index: int, start: float, length: float,
                   identity: dict, language: str, prompt: str = "") -> list[dict]:
        log_path = cache / f"chunk-{index:04d}.log"
        if log_path.is_symlink():
            raise ValueError("ASR log must not be a symlink")
        with tempfile.TemporaryDirectory(prefix=f".chunk-{index:04d}-", dir=cache) as temporary:
            audio = Path(temporary) / "audio.wav"
            prefix = Path(temporary) / f"chunk-{index:04d}"
            commands = [
                [media.tool_path("ffmpeg"), "-nostdin", "-v", "error", "-y", "-ss", str(start), "-i", str(video),
                 "-t", str(length), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)],
                # -sns 抑制非语音 token（音乐段的 "(音楽)"、♪ 之类标注不会再进字幕）；
                # -mc 0 关掉文本上下文，避免音乐段产出的幻觉顺着上下文带偏后面的真实语音
                [identity["binary"], "-m", identity["model"], "-f", str(audio), "-l", language,
                 "-t", str(self.threads), "-osrt", "-of", str(prefix), "-ml", "80", "-sow", "-np",
                 "-sns", "-mc", "0"],
            ]
            if prompt:
                # 术语表作为初始提示词，从源头减少专名误听
                commands[1] += ["--prompt", prompt]
            with log_path.open("w", encoding="utf-8") as log:
                for command in commands:
                    result = media.run_managed(command, stdin=subprocess.DEVNULL, stdout=log,
                                               stderr=subprocess.STDOUT, timeout=7200)
                    if result.returncode:
                        raise RuntimeError(f"Local audio extraction or ASR failed; see asr/{log_path.name}")
            subtitle = prefix.with_suffix(".srt")
            if not subtitle.is_file():
                raise RuntimeError(f"Local ASR failed to produce subtitles; see asr/{log_path.name}")
            # whisper.cpp 在 Windows 上会把 CRLF 插进 UTF-8 多字节序列，errors=replace 兜底
            if not subtitle.read_text(encoding="utf-8-sig", errors="replace").strip():
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
