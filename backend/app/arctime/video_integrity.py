from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from app.arctime import media


class VideoDecodeError(ValueError):
    def __init__(self) -> None:
        super().__init__('视频解码损坏或检查未完成；原视频已保留')


def validate_video_decode(path: Path, duration: float) -> None:
    try:
        with tempfile.TemporaryFile(mode='w+b') as diagnostics:
            command = [
                media.tool_path('ffmpeg'), '-nostdin', '-hide_banner', '-v', 'error', '-threads', '2',
                '-i', str(path), '-map', '0:v:0', '-an', '-sn', '-dn',
                '-fps_mode', 'passthrough', '-enc_time_base', 'demux', '-f', 'null', '-',
            ]
            from app.services.task_execution import current_execution
            execution = current_execution.get()
            result = execution.run_command(command, timeout=max(60, duration * 2), log=diagnostics) if execution else subprocess.run(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=diagnostics,
                timeout=max(60, duration * 2), check=False)
            diagnostics.seek(0, os.SEEK_END)
            if result.returncode or diagnostics.tell():
                raise VideoDecodeError()
    except (OSError, subprocess.TimeoutExpired):
        raise VideoDecodeError() from None
