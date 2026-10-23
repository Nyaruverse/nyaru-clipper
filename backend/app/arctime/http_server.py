from __future__ import annotations

from types import FrameType

from uvicorn import Server


class CompanionServer(Server):
    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        self.config.app.state.stream_stopping.set()
        super().handle_exit(sig, frame)
