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

if os.name == "nt":
    import threading
    import time

    # Windows cannot replace a JSON file while a reader holds it open.
    json_io_lock = threading.RLock()


class RunCancelled(Exception):
    """协作式取消：任务被用户手动终止。"""


_ACTIVE_PROCESSES: set[subprocess.Popen] = set()
_ACTIVE_PROCESSES_LOCK = threading.Lock()


def run_managed(command: list, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run 的可终止版本：登记 Popen 句柄，支持 taskkill 进程树。"""
    kwargs.pop("capture_output", None)  # Popen 不支持 capture_output，手动转换
    text = kwargs.pop("text", False)
    timeout = kwargs.pop("timeout", None)
    # 把调用方传入的 stdout/stderr 统一捕获到 PIPE，再手动 utf-8 replace 写回。
    # 否则在 Windows 上当 stdout 是 TextIOWrapper 时 Popen 会用 cp936 locale decode，
    # 子进程输出 UTF-8 日文等多字节序列就触发 UnicodeDecodeError。
    external_stdout = kwargs.pop("stdout", None)
    external_stderr = kwargs.pop("stderr", None)
    # 统一走 binary PIPE，避免 Windows locale (cp936) 解码 UTF-8 子进程输出
    kwargs["stdout"] = subprocess.PIPE
    kwargs["stderr"] = subprocess.PIPE
    kwargs.pop("check", None)
    process = subprocess.Popen(command, **kwargs)
    with _ACTIVE_PROCESSES_LOCK:
        _ACTIVE_PROCESSES.add(process)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        # 调用方要求 stderr 合并到 stdout：手动拼接
        if external_stderr is subprocess.STDOUT and stderr:
            stdout = (stdout or b"") + stderr
            stderr = None
        if external_stdout is subprocess.STDOUT:
            # 调用方明确要求 stderr 合并但 stdout 就是 PIPE——此时 CompletedProcess.stdout 保持 bytes
            external_stdout = None
        if isinstance(stdout, bytes) and external_stdout is not None:
            _write_output(external_stdout, stdout)
        if isinstance(stderr, bytes) and external_stderr is not None and external_stderr is not subprocess.STDOUT:
            _write_output(external_stderr, stderr)
        if text and isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if text and isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        _kill_process(process)
        raise
    finally:
        with _ACTIVE_PROCESSES_LOCK:
            _ACTIVE_PROCESSES.discard(process)


def _write_output(target, payload: bytes) -> None:
    """向调用方传入的 stdout/stderr 目标写回内容，兼容 TextIOWrapper / BufferedWriter / 路径等。"""
    if not payload:
        return
    try:
        if hasattr(target, "write") and hasattr(target, "encoding"):
            # TextIOWrapper：utf-8 replace 后写字符串
            target.write(payload.decode("utf-8", errors="replace"))
        elif hasattr(target, "write"):
            # BufferedWriter：直接写 bytes
            target.write(payload)
        elif target is subprocess.STDOUT or target is None:
            return
        else:
            # 兜底：尝试以二进制写入路径
            with open(target, "ab") as handle:
                handle.write(payload)
    except OSError:
        pass


def _kill_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                       capture_output=True, check=False)
    else:
        try:
            process.kill()
        except OSError:
            pass


def terminate_active_processes() -> int:
    """终止所有登记的子进程，返回终止数量。"""
    with _ACTIVE_PROCESSES_LOCK:
        processes = list(_ACTIVE_PROCESSES)
    for process in processes:
        _kill_process(process)
    return len(processes)


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
        if os.name == "nt":
            with json_io_lock:
                for attempt in range(6):
                    try:
                        os.replace(name, path)
                        break
                    except PermissionError:
                        # Windows readers and file scanners can briefly deny rename.
                        # Keep the old JSON intact and stop after a bounded retry.
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
    try:
        # errors="replace" 兜底：whisper.cpp 在 Windows 上会把 CRLF 插进 UTF-8 多字节序列中间，
        # 导致原生 utf-8 decode 崩；replace 只替换坏字节不丢内容。
        content = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n").strip()
    except OSError:
        # Windows 文件锁竞态：读取失败返回空列表，避免前端白屏
        return []
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
            for i, c in enumerate(s for s in segments if s.end_seconds > start and s.start_seconds < end)]


def select_clips(segments: list[SubtitleSegment], duration: float, ranges: list[tuple[float, float]], highlight_count: int | None) -> list[dict]:
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Media duration must be finite and positive")
    if bool(ranges) == (highlight_count is not None):
        raise ValueError("Choose explicit ranges or highlights")
    if any(not math.isfinite(s) or not math.isfinite(e) or not 0 <= s < e for s, e in ranges):
        raise ValueError("Clip bounds must be finite and satisfy 0 <= start < end")
    for index, (s, e) in enumerate(ranges, start=1):
        if e > duration:
            raise ValueError(f"第 {index} 段时间超出视频总长（视频总长 {duration:.1f} 秒，该段结束于 {e:.1f} 秒）")
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
    found = shutil.which(name)
    bundled = Path(__file__).resolve().parents[3] / ".bin" / name
    if found:
        return found
    environment_tool = Path(sys.executable).parent / name
    if environment_tool.is_file() and os.access(environment_tool, os.X_OK):
        return str(environment_tool)
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    if os.name == "nt":
        for directory in (Path(sys.executable).parent, bundled.parent):
            candidate = directory / (name + ".exe")
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
    host = parsed.hostname or ""
    # B 站登录态 cookie（需要登录的视频）
    cookie_path = os.environ.get("APP_BILIBILI_COOKIE_PATH", "").strip()
    cookie_args: list[str] = []
    if cookie_path and ("bilibili.com" in host or "b23.tv" in host):
        cookie_file = Path(cookie_path).expanduser()
        if cookie_file.is_file():
            cookie_args = ["--cookies", str(cookie_file)]
    # YouTube 反爬严格，可通过 cookie 文件或浏览器登录态绕过人机校验
    is_youtube = "youtube.com" in host or "youtu.be" in host
    if is_youtube:
        yt_cookie_path = os.environ.get("APP_YOUTUBE_COOKIE_PATH", "").strip()
        yt_browser = os.environ.get("APP_YOUTUBE_COOKIES_FROM_BROWSER", "").strip()
        if yt_cookie_path and Path(yt_cookie_path).expanduser().is_file():
            cookie_args = ["--cookies", str(Path(yt_cookie_path).expanduser())]
        elif yt_browser:
            cookie_args = ["--cookies-from-browser", yt_browser]

    def attempt(extra_args: list[str]) -> subprocess.CompletedProcess:
        return run_managed([*downloader, *cookie_args, *extra_args, "--no-playlist", "--no-progress", "--no-overwrites",
                            "--no-write-info-json", "--restrict-filenames", "-f", "bv*+ba/b", "--merge-output-format", "mp4",
                            "--remux-video", "mp4", "--ffmpeg-location", tool_path("ffmpeg"),
                            "-o", str(directory / "source.%(ext)s"), "--", url],
                           text=True, timeout=7200)

    result = attempt([])
    if result.returncode and is_youtube:
        # 兜底：android 客户端通常不需要登录态即可过人机校验，但可用清晰度较低
        for leftover in directory.glob("source.*"):
            leftover.unlink(missing_ok=True)
        result = attempt(["--extractor-args", "youtube:player_client=android"])
    if result.returncode:
        tail = [line.strip() for line in (result.stderr or "").strip().splitlines() if line.strip()][-2:]
        detail = "；".join(tail) or "未知错误"
        raise RuntimeError(f"yt-dlp download failed: {detail}")
    path = directory / "source.mp4"
    probe_video(path)
    return path


def export_clip(source: Path, target: Path, start: float, end: float, segments: list[SubtitleSegment]) -> None:
    from app.services.export_encoding import ExportInvocation, execute_video_export
    from app.settings import get_settings

    final_subtitle = target.with_suffix(".srt")
    log_path = target.with_suffix(".log")
    if target.exists() or target.is_symlink() or final_subtitle.is_symlink() or log_path.is_symlink():
        raise FileExistsError("Final clip already exists or an output is a symlink")
    duration = probe_video(source)
    select_clips([], duration, [(start, end)], None)
    expected_subtitle = render_srt(clip_subtitles(segments, start, end))
    retained_subtitle = final_subtitle.exists()
    if retained_subtitle and final_subtitle.read_text(encoding="utf-8") != expected_subtitle:
        raise FileExistsError("Existing subtitles differ from the requested clip; preserving them")
    settings = get_settings()
    settings.ffmpeg_binary = tool_path("ffmpeg")
    with tempfile.TemporaryDirectory(prefix=".encoding-", dir=target.parent) as temporary:
        video = Path(temporary) / "clip.mp4"
        subtitle = video.with_suffix(".srt")
        execution = execute_video_export(ExportInvocation(source, video, start, end, "managed-video"), settings, log_path)
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
