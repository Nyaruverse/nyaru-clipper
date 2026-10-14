from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from app.arctime import media
from app.arctime.subtitle_inputs import ExportError


def subtitle_ffmpeg() -> str:
    if not getattr(sys, "frozen", False) and sys.platform == "darwin":
        for path in (Path("/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg"), Path("/usr/local/opt/ffmpeg@7/bin/ffmpeg")):
            if path.is_file():
                return str(path)
    return media.tool_path("ffmpeg")


@lru_cache(maxsize=4)
def has_libass(binary: str) -> bool:
    try:
        result = subprocess.run([binary, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and any(" ass " in line for line in result.stdout.splitlines())


def burn_available() -> bool:
    try:
        return has_libass(subtitle_ffmpeg())
    except FileNotFoundError:
        return False


def video_dimensions(path: Path) -> tuple[int, int]:
    result = subprocess.run([media.tool_path("ffprobe"), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", str(path)], capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise ExportError("无法读取视频尺寸")
    streams = json.loads(result.stdout).get("streams", [])
    if not streams or type(streams[0].get("width")) is not int or type(streams[0].get("height")) is not int:
        raise ExportError("视频尺寸无效")
    width, height = streams[0]["width"], streams[0]["height"]
    if width <= 0 or height <= 0:
        raise ExportError("视频尺寸无效")
    return width, height


def burn_clip(source: Path, working: Path, duration: float, notify: Callable[[str], None]) -> Path:
    binary = subtitle_ffmpeg()
    if not has_libass(binary):
        raise ExportError("当前 FFmpeg 不支持 libass 字幕烧录，请安装支持 libass 的版本")
    target = working / "burn.mp4"
    command = [binary, "-hide_banner", "-nostdin", "-n", "-i", str(source), "-vf", "ass=filename=subtitle.ass",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats", str(target)]
    messages: queue.Queue[str | None] = queue.Queue()
    with (working / "encoder.log").open("w", encoding="utf-8") as log:
        with subprocess.Popen(command, cwd=working, stdout=subprocess.PIPE, stderr=log, text=True) as process:
            if process.stdout is None:
                raise ExportError("编码进度管道不可用")
            def read_progress() -> None:
                if process.stdout is not None:
                    for line in process.stdout:
                        messages.put(line)
                messages.put(None)
            reader = threading.Thread(target=read_progress, daemon=True)
            reader.start()
            deadline = time.monotonic() + max(300, duration * 10)
            try:
                while time.monotonic() < deadline:
                    try:
                        line = messages.get(timeout=.25)
                    except queue.Empty:
                        continue
                    if line is None:
                        break
                    key, _, value = line.strip().partition("=")
                    if key == "out_time_us" and value.isdigit():
                        notify(f"正在烧录字幕：{min(99, int(int(value) / 1_000_000 / duration * 100))}%")
                else:
                    process.kill()
                    raise ExportError("字幕烧录超时；原视频和字幕已保留")
                if process.wait(timeout=30):
                    raise ExportError("字幕烧录失败；原视频和字幕已保留，请查看导出日志")
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait()
                raise ExportError("字幕编码工具失败；原结果已保留") from None
            finally:
                reader.join(timeout=5)
    actual = media.probe_video(target)
    if abs(actual - duration) > max(.5, duration * .05):
        raise ExportError("字幕视频时长校验失败；原结果已保留")
    return target
