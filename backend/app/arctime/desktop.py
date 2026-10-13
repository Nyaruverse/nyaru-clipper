from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


class DesktopError(RuntimeError):
    pass


class ArcTimeDesktop:
    def bridge(self, action: str, *args: str) -> dict:
        if sys.platform != "darwin":
            raise DesktopError("macOS is required for this desktop adapter")
        source = Path(__file__).with_name("bridge.swift")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        cache = Path(tempfile.gettempdir()) / f"nyaru-arctime-{os.getuid()}"
        cache.mkdir(mode=0o700, exist_ok=True)
        if cache.is_symlink() or cache.stat().st_uid != os.getuid() or cache.stat().st_mode & 0o077:
            raise DesktopError("unsafe native bridge cache permissions")
        binary = cache / digest
        if not binary.is_file():
            with tempfile.TemporaryDirectory(dir=cache) as build:
                output = Path(build) / "bridge"
                result = subprocess.run(["/usr/bin/swiftc", str(source), "-o", str(output)], capture_output=True, text=True, timeout=120, check=False)
                if result.returncode:
                    raise DesktopError("native bridge compilation failed; Xcode Command Line Tools are required")
                os.replace(output, binary)
        result = subprocess.run([str(binary), action, *map(str, args)], capture_output=True, text=True, timeout=45, check=False)
        try:
            payload = json.loads(result.stdout)
        except ValueError as exc:
            raise DesktopError("native bridge did not return valid JSON") from exc
        if result.returncode:
            raise DesktopError(payload.get("error", "native_bridge_failed"))
        return payload

    def inspect(self) -> list[dict]:
        return self.bridge("inspect")["windows"]

    def launch(self) -> None:
        if sys.platform != "darwin":
            raise DesktopError("macOS is required for this desktop adapter")
        result = subprocess.run(["/usr/bin/open", "-a", "/Applications/ArcTime Pro.app"], capture_output=True, timeout=10, check=False)
        if result.returncode:
            raise DesktopError("ArcTime Pro is not installed in /Applications")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.inspect():
                return
            time.sleep(.5)
        raise DesktopError("ArcTime did not open its window")

    def _main(self, video: Path | None = None) -> dict:
        windows = self.inspect()
        main = [w for w in windows if w["width"] >= 900 and w["height"] >= 500]
        if len(main) != 1:
            raise DesktopError("ArcTime main window is missing or ambiguous")
        if video is not None and video.stem not in main[0]["title"]:
            raise DesktopError("ArcTime project changed; reopen the managed project before resume")
        return main[0]

    def _key(self, window: dict, code: int, modifier: str = "cmd") -> None:
        self.bridge("key", window["id"], window["title"], code, modifier)

    def _click(self, window: dict, labels: tuple[str, ...]) -> None:
        hits = [t["text"] for t in window["texts"] if t["text"] in labels]
        if len(hits) != 1:
            raise DesktopError("ArcTime button is missing or ambiguous")
        self.bridge("click", window["id"], window["title"], hits[0])

    def _dialog(self, video: Path) -> dict:
        main = self._main(video)
        dialogs = [w for w in self.inspect() if w["id"] != main["id"] and any(t in w["title"] for t in ("语音转写", "语音识别", "Transcription", "Speech"))]
        if len(dialogs) != 1:
            raise DesktopError("ArcTime transcription dialog is missing or ambiguous")
        return dialogs[0]

    def open_video(self, video: Path) -> None:
        main = self._main()
        if main["title"] != "ArcTime Pro" and video.stem not in main["title"]:
            raise DesktopError("Refusing to replace an unrelated ArcTime project")
        if video.stem in main["title"]:
            return
        self._key(main, 34)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            dialogs = [w for w in self.inspect() if w["id"] != main["id"]]
            if len(dialogs) == 1:
                dialog = dialogs[0]
                self._key(dialog, 5, "cmdshift")
                time.sleep(.3)
                self.bridge("text", dialog["id"], dialog["title"], str(video))
                self._key(dialog, 36, "none")
                time.sleep(.3)
                self._key(dialog, 36, "none")
                break
            time.sleep(.5)
        else:
            raise DesktopError("ArcTime media import dialog did not open")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if video.stem in self._main()["title"]:
                return
            time.sleep(.5)
        raise DesktopError("ArcTime did not confirm the managed video was imported")

    def open_transcription(self, video: Path) -> None:
        main = self._main(video)
        self.bridge("point", main["id"], main["title"], ".5", ".9")
        self._key(main, 18)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                self._dialog(video)
                return
            except DesktopError:
                time.sleep(.5)
        raise DesktopError("ArcTime transcription dialog did not open")

    def check_ready(self, video: Path) -> None:
        dialog = self._dialog(video)
        labels = " ".join(t["text"] for t in dialog["texts"])
        if any(t in labels for t in ("请先登录", "未登录", "登录后", "Log in", "Sign in")):
            raise DesktopError("ArcTime login is required; log in inside ArcTime and resume")
        if any(t in labels for t in ("无时间轴", "no timeline", "No timeline")):
            raise DesktopError("Select an ArcTime engine that produces a timeline")
        hits = [t for t in dialog["texts"] if t["text"] in ("开始", "开始识别", "开始转写", "Start")]
        if len(hits) != 1:
            raise DesktopError("ArcTime start button is missing or ambiguous")

    def submit(self, video: Path) -> None:
        self.check_ready(video)
        self._click(self._dialog(video), ("开始", "开始识别", "开始转写", "Start"))

    def status(self, video: Path) -> str:
        labels = " ".join(t["text"] for t in self._dialog(video)["texts"])
        if any(t in labels for t in ("请先登录", "未登录", "Log in", "Sign in")):
            raise DesktopError("ArcTime login is required")
        if any(t in labels for t in ("转写失败", "识别失败", "上传失败", "积分不足", "余额不足", "Failed")):
            raise DesktopError("ArcTime reported transcription failure or insufficient credits")
        if "获取" in labels and any(t in labels for t in ("已有转写结果", "转写完成", "获取结果")):
            return "ready"
        if any(t in labels for t in ("正在计算", "处理中", "上传中", "排队", "正在上传", "Processing")):
            return "processing"
        return "unknown"

    def save(self, video: Path) -> None:
        main = self._main(video)
        self.bridge("point", main["id"], main["title"], ".5", ".9")
        self._key(main, 1)

    def collect(self, video: Path) -> Path:
        self._click(self._dialog(video), ("获取", "获取结果", "Get"))
        time.sleep(.5)
        self.save(video)
        output = video.with_suffix(".ass")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if output.is_file() and output.stat().st_size:
                return output
            time.sleep(.5)
        raise DesktopError("ArcTime did not save its ASS; preserve the project and resume")
