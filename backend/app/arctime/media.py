from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from app.services.highlight_scoring import derive_scene_like_windows, score_candidate_windows
from app.services.subtitles import SubtitleSegment, render_srt

if os.name == 'nt':
    import threading
    import time
    json_io_lock = threading.RLock()


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == 'nt':
            with json_io_lock:
                for attempt in range(6):
                    try:
                        os.replace(name, path)
                        break
                    except PermissionError:
                        if attempt == 5:
                            raise
                        time.sleep(.01 * 2 ** attempt)
        else:
            os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def parse_time(value: str) -> float:
    parts = value.strip().replace(",", ".").split(":")
    if not 1 <= len(parts) <= 3 or any(not re.fullmatch(r"\d+(?:\.\d+)?", p) for p in parts):
        raise ValueError("Time must be nonnegative seconds, MM:SS or HH:MM:SS.mmm")
    if len(parts) > 1 and (any(float(p) >= 60 for p in parts[1:]) or any("." in p for p in parts[:-1])):
        raise ValueError("Invalid clock time")
    seconds = sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))
    if not math.isfinite(seconds):
        raise ValueError("Time must be finite")
    return seconds


def read_subtitles(path: Path, *, merge_contiguous_zero_duration: bool = False) -> list[SubtitleSegment]:
    content = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    cues: list[SubtitleSegment] = []
    if path.suffix.lower() == ".ass":
        in_events = False
        fields = []
        for line in content.splitlines():
            if line.startswith("["):
                in_events = line.strip().lower() == "[events]"
            elif in_events and line.startswith("Format:"):
                fields = [p.strip().lower() for p in line.partition(":")[2].split(",")]
            elif in_events and line.startswith("Dialogue:"):
                if not fields or fields[-1] != "text" or not {"start", "end", "text"}.issubset(fields):
                    raise ValueError("ASS event format is missing or unsupported")
                values = line.partition(":")[2].lstrip().split(",", len(fields) - 1)
                if len(values) != len(fields):
                    raise ValueError("Incomplete ASS dialogue")
                row = dict(zip(fields, values, strict=True))
                text = re.sub(r"\{[^}]*\}", "", row["text"]).replace(r"\N", "\n").replace(r"\n", "\n").replace(r"\h", " ")
                cues.append(SubtitleSegment(str(len(cues) + 1), parse_time(row["start"]), parse_time(row["end"]), text))
    elif path.suffix.lower() == ".srt":
        for block in re.split(r"\n\s*\n", content):
            lines = block.splitlines()
            if len(lines) < 3 or not lines[0].strip().isdigit():
                raise ValueError("Incomplete SRT cue")
            match = re.fullmatch(r"(\d+:\d{2}:\d{2}[,.]\d{3})\s+-->\s+(\d+:\d{2}:\d{2}[,.]\d{3})", lines[1].strip())
            if match is None:
                raise ValueError("Invalid SRT timing")
            cues.append(SubtitleSegment(str(len(cues) + 1), parse_time(match[1]), parse_time(match[2]), "\n".join(lines[2:])))
    else:
        raise ValueError("Expected ASS or SRT subtitles")
    if merge_contiguous_zero_duration:
        normalized: list[SubtitleSegment] = []
        for cue in cues:
            if (cue.start_seconds == cue.end_seconds and cue.text.strip() and normalized
                    and normalized[-1].text.strip() and normalized[-1].end_seconds == cue.start_seconds):
                normalized[-1].text += "\n" + cue.text
            else:
                normalized.append(cue)
        cues = normalized
    if not cues or any(c.start_seconds >= c.end_seconds or not c.text.strip() for c in cues):
        raise ValueError("Subtitles must contain nonempty text and positive cue durations")
    return sorted(cues, key=lambda c: (c.start_seconds, c.end_seconds))


def clip_subtitles(segments: list[SubtitleSegment], start: float, end: float) -> list[SubtitleSegment]:
    return [SubtitleSegment(str(i + 1), max(c.start_seconds, start) - start, min(c.end_seconds, end) - start, c.text)
            for i, c in enumerate(s for s in segments
                if round((min(s.end_seconds, end) - start) * 1000)
                > round((max(s.start_seconds, start) - start) * 1000))]


def select_clips(segments: list[SubtitleSegment], duration: float, ranges: list[tuple[float, float]], highlight_count: int | None) -> list[dict]:
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Media duration must be finite and positive")
    if bool(ranges) == (highlight_count is not None):
        raise ValueError("Choose explicit ranges or highlights")
    if any(not math.isfinite(s) or not math.isfinite(e) or not 0 <= s < e <= duration for s, e in ranges):
        raise ValueError("Clip bounds must satisfy 0 <= start < end <= video duration")
    if ranges:
        return [{"start": float(s), "end": float(e), "score": None, "reasons": ["manual"]} for s, e in dict.fromkeys(ranges)]
    if highlight_count is None or highlight_count <= 0:
        raise ValueError("Highlight count must be positive")
    candidates = score_candidate_windows(derive_scene_like_windows(segments), segments, media_end_s=duration)
    selected = []
    for c in sorted(candidates, key=lambda c: (-c["score"], c["default_range"]["start_s"])):
        start = max(0.0, c["default_range"]["start_s"])
        end = min(duration, c["default_range"]["end_s"])
        if start < end and not any(start < old["end"] and end > old["start"] for old in selected):
            selected.append({"start": start, "end": end, "score": c["score"], "reasons": c["reasons"]})
            if len(selected) == highlight_count:
                break
    return selected


def tool_path(name: str) -> str:
    from app.settings import execution_settings
    settings = execution_settings.get()
    if settings is not None:
        configured = {'ffmpeg': settings.ffmpeg_binary, 'ffprobe': settings.ffprobe_binary, 'yt-dlp': settings.ytdlp_binary}.get(name)
        if configured is not None and configured != name:
            found = shutil.which(configured)
            if found is None:
                raise FileNotFoundError(f'Configured tool is missing: {name}')
            return found
    if getattr(sys, "frozen", False):
        path = Path(sys.executable) if name == "yt-dlp" else Path(sys._MEIPASS) / name
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        raise FileNotFoundError(f"Bundled tool is missing: {name}")
    found = shutil.which(name)
    bundled = Path(__file__).resolve().parents[3] / ".bin" / name
    if found:
        return found
    environment_tool = Path(sys.executable).parent / name
    if environment_tool.is_file() and os.access(environment_tool, os.X_OK):
        return str(environment_tool)
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    if os.name == 'nt':
        for directory in (Path(sys.executable).parent, bundled.parent):
            candidate = directory / (name + '.exe')
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    raise FileNotFoundError(f"Required tool is missing: {name}")


def probe_video(path: Path) -> float:
    result = subprocess.run([tool_path("ffprobe"), "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)],
                            capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise ValueError("ffprobe could not read the video")
    payload = json.loads(result.stdout)
    duration = float(payload.get("format", {}).get("duration", "nan"))
    if not math.isfinite(duration) or duration <= 0 or not any(s.get("codec_type") == "video" for s in payload.get("streams", [])):
        raise ValueError("A finite-duration video stream is required")
    return duration


def download_video(url: str, directory: Path) -> Path:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Video URL must be HTTP(S), without embedded credentials")
    if (directory / "source.mp4").exists():
        raise FileExistsError("Download destination already exists")
    downloader = [tool_path("yt-dlp")]
    if getattr(sys, "frozen", False):
        downloader.append("--yt-dlp")
    command = [*downloader, "--no-playlist", "--no-progress", "--no-overwrites",
                             "--no-write-info-json", "--restrict-filenames", "-f", "bv*+ba/b", "--merge-output-format", "mp4",
                             "--remux-video", "mp4", "--ffmpeg-location", tool_path("ffmpeg"),
                             "-o", str(directory / "source.%(ext)s"), "--", url]
    from app.services.task_execution import current_execution
    execution = current_execution.get()
    result = execution.run_command(command, timeout=7200) if execution else subprocess.run(
        command, capture_output=True, text=True, timeout=7200, check=False)
    if result.returncode:
        raise RuntimeError("yt-dlp download failed; check URL access and downloader configuration")
    path = directory / "source.mp4"
    probe_video(path)
    return path


def export_clip(source: Path, target: Path, start: float, end: float, segments: list[SubtitleSegment]) -> None:
    from app.services.export_encoding import ExportEncodingConfig, ExportInvocation, execute_video_export
    from app.settings import get_settings

    final_subtitle = target.with_suffix(".srt")
    log_path = target.with_suffix(".log")
    if target.exists() or target.is_symlink() or final_subtitle.is_symlink() or log_path.is_symlink():
        raise FileExistsError("Final clip already exists or an output is a symlink")
    duration = probe_video(source)
    # Remuxing can shorten the container timestamp by a frame; retain the selected subtitle tail.
    if start < duration < end <= duration + .05:
        duration = end
    select_clips([], duration, [(start, end)], None)
    expected_subtitle = render_srt(clip_subtitles(segments, start, end))
    retained_subtitle = final_subtitle.exists()
    if retained_subtitle and final_subtitle.read_text(encoding="utf-8") != expected_subtitle:
        raise FileExistsError("Existing subtitles differ from the requested clip; preserving them")
    settings = get_settings()
    encoding_config = ExportEncodingConfig(
        ffmpeg_binary=tool_path("ffmpeg"),
        export_video_backend=settings.export_video_backend,
        windows_ffmpeg_binary=settings.windows_ffmpeg_binary,
    )
    with tempfile.TemporaryDirectory(prefix=".encoding-", dir=target.parent) as temporary:
        video = Path(temporary) / "clip.mp4"
        subtitle = video.with_suffix(".srt")
        execution = execute_video_export(ExportInvocation(source, video, start, end, "managed-video"), encoding_config, log_path)
        if execution.completed_process.returncode or not video.is_file():
            raise RuntimeError(f"ffmpeg clip encoding failed; see {log_path.name}; previous clips are preserved")
        actual_duration = probe_video(video)
        if abs(actual_duration - (end - start)) > max(.5, (end - start) * .05):
            raise ValueError("Encoded clip duration does not match the selected interval")
        subtitle.write_text(expected_subtitle, encoding="utf-8")
        if not retained_subtitle:
            os.link(subtitle, final_subtitle)
        try:
            os.link(video, target)
        except BaseException:
            if not retained_subtitle:
                final_subtitle.unlink()
            raise
