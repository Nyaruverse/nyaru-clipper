from pathlib import Path
from typing import Protocol

from pydantic import JsonValue

from app.services.subtitles import SubtitleSegment


class AsrAdapter(Protocol):
    def identity(self) -> dict[str, JsonValue]: ...
    def transcribe(self, video: Path, directory: Path, duration: float) -> list[SubtitleSegment]: ...
