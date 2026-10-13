from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from app.arctime import media
from app.services.subtitles import SubtitleSegment

DEFAULT_MODEL = Path.home() / ".cache" / "nyaru-clipper" / "models" / "ggml-small.bin"
CHUNK_SECONDS = 300


def _segments_hash(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class LocalASR:
    model: Path = DEFAULT_MODEL
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
                "language": self.language, "threads": self.threads, "chunk_seconds": CHUNK_SECONDS}

    def transcribe(self, video: Path, directory: Path, duration: float) -> list[SubtitleSegment]:
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("ASR requires a finite positive media duration")
        identity = self.identity()
        source_hash = media.fingerprint(video)
        cache = directory / "asr"
        if cache.is_symlink():
            raise ValueError("ASR cache must not be a symlink")
        cache.mkdir(exist_ok=True)
        cues: list[SubtitleSegment] = []
        for index in range(math.ceil(duration / CHUNK_SECONDS)):
            start = index * CHUNK_SECONDS
            length = min(CHUNK_SECONDS, duration - start)
            key = {"version": 1, "source_sha256": source_hash, "asr": identity, "start": start, "duration": length}
            destination = cache / f"chunk-{index + 1:04d}.json"
            if destination.is_symlink():
                raise ValueError("ASR chunk must not be a symlink")
            rows = self._cached_rows(destination, key)
            if rows is None:
                rows = self._recognize(video, cache, index + 1, start, length, identity)
                media.write_json(destination, {"key": key, "segments": rows, "segments_sha256": _segments_hash(rows)})
            for row in rows:
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
                    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log,
                                            stderr=subprocess.STDOUT, timeout=7200, check=False)
                    if result.returncode:
                        raise RuntimeError(f"Local audio extraction or ASR failed; see asr/{log_path.name}")
            subtitle = prefix.with_suffix(".srt")
            if not subtitle.is_file():
                raise RuntimeError(f"Local ASR failed to produce subtitles; see asr/{log_path.name}")
            if not subtitle.read_text(encoding="utf-8-sig").strip():
                return []
            segments = media.read_subtitles(subtitle)
            if any(c.end_seconds > length + .25 for c in segments):
                raise ValueError("Local ASR timestamps exceed chunk duration")
            return [asdict(SubtitleSegment(c.id, c.start_seconds, min(c.end_seconds, length), c.text))
                    for c in segments if c.start_seconds < length]
