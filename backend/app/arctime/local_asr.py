from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from app.arctime import media
from app.services.subtitles import SubtitleSegment
from app.services.task_execution import current_execution

DEFAULT_MODEL = Path.home() / ".cache" / "nyaru-clipper" / "models" / "ggml-small.bin"
CHUNK_SECONDS = 300
ASR_TAIL_WINDOW_SECONDS = 30.0
VAD_MODEL_NAME: Final = 'ggml-silero-v6.2.0.bin'
VAD_MODEL_SHA256: Final = '2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987'
DEFAULT_VAD_MODEL: Final = DEFAULT_MODEL.with_name(VAD_MODEL_NAME)


def _vad_model() -> Path:
    resources = getattr(sys, '_MEIPASS', None)
    path = Path(resources) / 'models' / VAD_MODEL_NAME if resources else DEFAULT_VAD_MODEL
    if path.is_symlink() or not path.is_file() or media.fingerprint(path) != VAD_MODEL_SHA256:
        raise RuntimeError('Verified VAD model is missing or changed; preserve the source and check the installation')
    return path


def _segments_hash(rows: list[dict], language: str) -> str:
    return hashlib.sha256(json.dumps({'segments': rows, 'language': language}, sort_keys=True,
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class DetectedLanguage(BaseModel):
    model_config = ConfigDict(frozen=True)
    language: str = Field(pattern=r'^[a-z]{2,3}$')


class ASRLanguage(DetectedLanguage):
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class _Recognition(BaseModel):
    model_config = ConfigDict(frozen=True)
    result: DetectedLanguage


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
        languages: dict[str, float] = {}
        for index in range(math.ceil(duration / CHUNK_SECONDS)):
            start = index * CHUNK_SECONDS
            length = min(CHUNK_SECONDS, duration - start)
            key = {"version": 2, "source_sha256": source_hash, "asr": identity, "start": start, "duration": length}
            destination = cache / f"chunk-{index + 1:04d}.json"
            if destination.is_symlink():
                raise ValueError("ASR chunk must not be a symlink")
            result = self._cached_rows(destination, key)
            if result is None:
                result = self._recognize(video, cache, index + 1, start, length, identity)
                rows, language = result
                media.write_json(destination, {"key": key, "segments": rows, 'language': language,
                    "segments_sha256": _segments_hash(rows, language)})
            rows, language = result
            languages[language] = languages.get(language, 0.) + sum(row['end_seconds'] - row['start_seconds'] for row in rows)
            for row in rows:
                cues.append(SubtitleSegment(str(len(cues) + 1), start + row["start_seconds"],
                                            start + row["end_seconds"], row["text"]))
        if not cues:
            raise ValueError("No speech was recognized; check the source audio and language")
        detected = ASRLanguage(source_sha256=source_hash, language=max(languages, key=lambda code: languages[code]))
        target = directory / 'asr-language.json'
        if target.is_symlink():
            raise ValueError('ASR language must not be a symlink')
        media.write_json(target, detected.model_dump())
        return cues

    @staticmethod
    def _cached_rows(path: Path, key: dict) -> tuple[list[dict], str] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload["segments"]
            language = DetectedLanguage.model_validate(payload).language
            if payload["key"] != key or payload["segments_sha256"] != _segments_hash(rows, language):
                return None
            if not isinstance(rows, list) or any(
                not isinstance(row["text"], str) or not row["text"].strip()
                or not 0 <= row["start_seconds"] < row["end_seconds"] <= key["duration"]
                for row in rows
            ):
                return None
            if rows != sorted(rows, key=lambda row: (row["start_seconds"], row["end_seconds"])):
                return None
            return rows, language
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _recognize(self, video: Path, cache: Path, index: int, start: float, length: float, identity: dict) -> tuple[list[dict], str]:
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
                 "-t", str(self.threads), "-osrt", "-oj", "-of", str(prefix), "-ml", "80", "-sow", "-np"],
            ]
            with log_path.open("w", encoding="utf-8") as log:
                tools = Path(identity['binary']).parent
                environment = dict(os.environ, DYLD_LIBRARY_PATH=str(tools)) if (
                    sys.platform == 'darwin' and (tools / 'libomp.dylib').is_file()) else None
                for attempt in range(2):
                    pending = commands if attempt == 0 else [commands[-1] + ['--vad', '-vm', str(_vad_model())]]
                    if attempt:
                        log.write('\nRetrying invalid ASR timestamps with voice activity detection\n')
                        log.flush()
                        prefix.with_suffix('.srt').unlink()
                        prefix.with_suffix('.json').unlink(missing_ok=True)
                    for command in pending:
                        execution = current_execution.get()
                        result = execution.run_command(command, log=log, timeout=7200,
                            env=environment if command[0] == identity['binary'] else None) if execution else subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log,
                                                stderr=subprocess.STDOUT, timeout=7200, check=False,
                                                env=environment if command[0] == identity['binary'] else None)
                        if result.returncode:
                            raise RuntimeError(f"Local audio extraction or ASR failed; see asr/{log_path.name}")
                    subtitle = prefix.with_suffix(".srt")
                    if not subtitle.is_file():
                        raise RuntimeError(f"Local ASR failed to produce subtitles; see asr/{log_path.name}")
                    language = _Recognition.model_validate_json(prefix.with_suffix('.json').read_bytes()).result.language if self.language == 'auto' else self.language
                    if not subtitle.read_text(encoding="utf-8-sig").strip():
                        return [], language
                    segments = media.read_subtitles(subtitle, merge_contiguous_zero_duration=True)
                    tail_window = min(ASR_TAIL_WINDOW_SECONDS, length / 2)
                    end_tolerance = min(1.0, length / 2)
                    invalid = any(c.end_seconds > length + end_tolerance and (
                        c.start_seconds < length - tail_window or c.end_seconds > length + tail_window)
                        for c in segments)
                    if not invalid:
                        return [asdict(SubtitleSegment(c.id, c.start_seconds, min(c.end_seconds, length), c.text))
                                for c in segments if c.start_seconds < length], language
                    if attempt:
                        raise ValueError("Local ASR timestamps exceed chunk duration")
        raise AssertionError('ASR retry did not terminate')
