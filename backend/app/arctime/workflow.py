from __future__ import annotations

import fcntl
import json
import math
import os
import re
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from app.arctime import media
from app.arctime.local_asr import LocalASR
from app.services.subtitles import render_srt

fingerprint = media.fingerprint


@contextmanager
def exclusive_lock(path: Path):
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Run is busy in another companion process") from exc
        yield
    finally:
        os.close(descriptor)


def write_manifest(directory: Path, job: dict) -> None:
    media.write_json(directory / "job.json", job)


def create_run(url: str, root: Path, ranges: list[tuple[float, float]], highlight_count: int | None,
               transcriber: LocalASR | None = None, *, run_id: str | None = None,
               progress: Callable[[str], None] | None = None) -> Path:
    if bool(ranges) == (highlight_count is not None) or (highlight_count is not None and highlight_count <= 0):
        raise ValueError("Choose at least one explicit range or a positive highlight count")
    if any(not math.isfinite(s) or not math.isfinite(e) or not 0 <= s < e for s, e in ranges):
        raise ValueError("Clip bounds must be finite and satisfy 0 <= start < end")
    identity = (transcriber or LocalASR()).identity()
    run_id = run_id or uuid.uuid4().hex[:12]
    if not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise ValueError("Invalid run identifier")
    root.mkdir(parents=True, exist_ok=True)
    directory = root.resolve() / run_id
    directory.mkdir(mode=0o700)
    job = {"version": 2, "state": "downloading", "ranges": ranges, "highlight_count": highlight_count,
           "asr": identity, "completed_clips": []}
    write_manifest(directory, job)
    try:
        if progress:
            progress("正在下载视频，完成后开始识别")
        source = media.download_video(url, directory)
        video = directory / "source.mp4"
        if source != video:
            source.rename(video)
        duration = media.probe_video(video)
        media.select_clips([], duration, ranges, highlight_count)
        job.update(state="downloaded", video=video.name, video_sha256=fingerprint(video), duration=duration)
        write_manifest(directory, job)
        return directory
    except BaseException as exc:
        job["state"] = "download_failed"
        write_manifest(directory, job)
        exc.add_note(f"Run directory: {directory}")
        raise


def _path(directory: Path, relative: str) -> Path:
    path = directory / relative
    if Path(relative).name != relative or path.is_symlink() or path.resolve().parent != directory.resolve():
        raise ValueError("Invalid job artifact path")
    return path


def _verify(directory: Path, job: dict) -> Path:
    if job.get("version") == 1:
        raise ValueError("Legacy cloud job cannot be resumed locally; create a new local run")
    if job.get("version") != 2:
        raise ValueError("Unsupported job version")
    if "video" not in job:
        raise ValueError("Download did not complete; create a new run using the original URL")
    video = _path(directory, job["video"])
    if fingerprint(video) != job["video_sha256"]:
        raise ValueError("Source video changed; create a new run")
    media.select_clips([], float(job["duration"]), [tuple(r) for r in job["ranges"]], job["highlight_count"])
    return video


def _publish_text(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def resume_run(directory: Path, transcriber: LocalASR | None = None,
               *, progress: Callable[[str], None] | None = None) -> dict:
    directory = directory.resolve()
    notify = progress or (lambda message: None)
    with exclusive_lock(directory / ".lock"):
        job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
        video = _verify(directory, job)
        if job["state"] not in {"downloaded", "transcribing", "subtitles_ready", "exporting", "completed"}:
            raise ValueError("Unknown or incomplete job state")
        if job["state"] in {"downloaded", "transcribing"}:
            adapter = transcriber or LocalASR(Path(job["asr"]["model"]), job["asr"]["language"], job["asr"]["threads"])
            if adapter.identity() != job["asr"]:
                raise ValueError("Local ASR configuration changed; create a new run")
            job["state"] = "transcribing"
            write_manifest(directory, job)
            notify("正在本地识别并生成时间轴")
            cues = adapter.transcribe(video, directory, job["duration"])
            if not cues or any(not math.isfinite(c.start_seconds) or not math.isfinite(c.end_seconds)
                               or not 0 <= c.start_seconds < c.end_seconds <= job["duration"] or not c.text.strip()
                               for c in cues):
                raise ValueError("Local subtitles must be nonempty and within video duration")
            cues.sort(key=lambda c: (c.start_seconds, c.end_seconds))
            _publish_text(directory / "subtitles.srt", render_srt(cues))
            _publish_text(directory / "transcript.txt", "\n".join(c.text for c in cues) + "\n")
            media.write_json(directory / "transcript.json", {"asr": job["asr"], "segments": [asdict(c) for c in cues]})
            artifacts = {name: fingerprint(directory / name) for name in ("subtitles.srt", "transcript.txt", "transcript.json")}
            job.update(state="subtitles_ready", subtitles="subtitles.srt", artifacts=artifacts)
            write_manifest(directory, job)

        for name, digest in job["artifacts"].items():
            if fingerprint(_path(directory, name)) != digest:
                raise ValueError("Managed transcript changed; create a new run rather than mixing results")
        cues = media.read_subtitles(_path(directory, job["subtitles"]))
        selection = media.select_clips(cues, job["duration"], [tuple(r) for r in job["ranges"]], job["highlight_count"])
        if "selection" in job and selection != job["selection"]:
            raise ValueError("Clip selection changed during recovery")
        if job["state"] != "completed":
            job.update(state="exporting", selection=selection)
            write_manifest(directory, job)
        if not selection:
            notify("没有达到评分阈值的高光，保留完整字幕，不生成切片")
        for index, clip in enumerate(selection, start=1):
            target = directory / f"clip-{index:03d}.mp4"
            subtitle = target.with_suffix(".srt")
            completed = next((c for c in job["completed_clips"] if c["video"] == target.name), None)
            if completed:
                if fingerprint(_path(directory, completed["video"])) != completed["video_sha256"] or fingerprint(_path(directory, completed["subtitles"])) != completed["subtitles_sha256"]:
                    raise ValueError("Previously exported clip changed or is incomplete")
                continue
            notify(f"正在导出切片 {index}/{len(selection)}")
            if target.is_symlink() or subtitle.is_symlink():
                raise ValueError("Clip artifacts must not be symlinks")
            if target.exists():
                # Recover the publication/checkpoint gap without overwriting an existing pair.
                expected = render_srt(media.clip_subtitles(cues, clip["start"], clip["end"]))
                if not target.is_file() or not subtitle.is_file() or subtitle.read_text(encoding="utf-8") != expected:
                    raise ValueError("Incomplete or changed clip pair; preserve it and inspect before retrying")
                length = clip["end"] - clip["start"]
                if abs(media.probe_video(target) - length) > max(.5, length * .05):
                    raise ValueError("Existing clip duration does not match the selection")
            else:
                media.export_clip(video, target, clip["start"], clip["end"], cues)
            job["completed_clips"].append({"video": target.name, "subtitles": subtitle.name,
                                           "video_sha256": fingerprint(target), "subtitles_sha256": fingerprint(subtitle)})
            write_manifest(directory, job)
        job["state"] = "completed"
        write_manifest(directory, job)
        return job
