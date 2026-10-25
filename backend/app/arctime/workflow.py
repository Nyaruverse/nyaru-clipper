from __future__ import annotations

import json
import math
import os
import re
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from app.arctime import media
from app.arctime.local_asr import LocalASR
from app.services.subtitles import render_srt

if os.name == "nt":
    import errno
    import msvcrt
    import stat
else:
    import fcntl

if TYPE_CHECKING:
    from app.arctime.saozi import SaoziSelector

fingerprint = media.fingerprint


@contextmanager
def _windows_exclusive_lock(path: Path):
    if path.is_symlink():
        raise ValueError("Run lock must not be a symbolic link")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("Run lock must be a regular file")
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
            raise RuntimeError("Run is busy in another companion process") from exc
        yield
    finally:
        os.close(descriptor)


@contextmanager
def exclusive_lock(path: Path):
    if os.name == "nt":
        with _windows_exclusive_lock(path):
            yield
        return
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
    try:
        media.write_json(directory / "job.json", job)
    except OSError:
        # Windows 文件锁竞态：写入失败不中止任务，内存状态继续推进
        pass


def create_run(url: str, root: Path, ranges: list[tuple[float, float]], highlight_count: int | None,
               transcriber: LocalASR | None = None, *, run_id: str | None = None,
               progress: Callable[[str], None] | None = None, saozi: bool = False,
               local_source: Path | None = None,
               should_cancel: Callable[[], bool] | None = None) -> Path:
    explicit = sum((bool(ranges), highlight_count is not None, saozi))
    if explicit > 1 or (highlight_count is not None and highlight_count <= 0):
        raise ValueError("指定时间段、高光与臊子模式互斥，最多选择一个；高光必须为正整数")
    if any(not math.isfinite(s) or not math.isfinite(e) or not 0 <= s < e for s, e in ranges):
        raise ValueError("Clip bounds must be finite and satisfy 0 <= start < end")
    identity = (transcriber or LocalASR()).identity()
    run_id = run_id or uuid.uuid4().hex[:12]
    if not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise ValueError("Invalid run identifier")
    root.mkdir(parents=True, exist_ok=True)
    directory = root.resolve() / run_id
    directory.mkdir(mode=0o700)
    # 计算 ASR 覆盖区间：指定时间段模式只转 ranges 的并集；其他模式转完整视频
    if ranges:
        asr_offset = min(s for s, _ in ranges)
        asr_end = max(e for _, e in ranges)
    else:
        asr_offset = 0.0
        asr_end = None  # 在 duration 探测后回填
    job: dict = {"version": 2, "state": "downloading", "ranges": ranges, "highlight_count": highlight_count,
                 "asr": identity, "completed_clips": [], "asr_offset": asr_offset}
    if not local_source:
        # 保留来源链接，供生成内容切片时自动拉取 B站弹幕
        job["url"] = url
    if saozi:
        job["saozi"] = True
    if not ranges and highlight_count is None and not saozi:
        job["mode"] = "full"  # 完整视频模式：只生成字幕不切片
    write_manifest(directory, job)
    try:
        if should_cancel is not None and should_cancel():
            raise media.RunCancelled()
        video = directory / "source.mp4"
        if progress:
            progress("正在导入本地录像" if local_source else "正在下载视频，完成后开始识别")
        if local_source:
            if local_source.is_symlink() or not local_source.is_file():
                raise ValueError("请选择有效的本地录像文件")
            shutil.copyfile(local_source, video)
            source = video
        else:
            source = media.download_video(url, directory)
        if should_cancel is not None and should_cancel():
            raise media.RunCancelled()
        if source != video:
            source.rename(video)
        duration = media.probe_video(video)
        if not saozi and not job.get("mode") == "full":
            media.select_clips([], duration, ranges, highlight_count)
        if asr_end is None:
            asr_end = duration
        job.update(state="downloaded", video=video.name, video_sha256=fingerprint(video), duration=duration,
                   asr_duration=asr_end - asr_offset)
        write_manifest(directory, job)
        return directory
    except BaseException as exc:
        if not isinstance(exc, media.RunCancelled):
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
    if not math.isfinite(float(job["duration"])) or float(job["duration"]) <= 0:
        raise ValueError("Invalid media duration")
    if not job.get("saozi") and not job.get("mode") == "full":
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
               *, progress: Callable[[str], None] | None = None,
               selector: SaoziSelector | None = None,
               should_cancel: Callable[[], bool] | None = None) -> dict:
    directory = directory.resolve()
    notify = progress or (lambda message: None)
    with exclusive_lock(directory / ".lock"):
        job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
        video = _verify(directory, job)
        if job.get("saozi"):
            if selector is None:
                raise ValueError("臊子需要已授权的模型配置")
            if job.get("saozi_model", selector.model) != selector.model:
                raise ValueError("臊子恢复必须沿用原供应商和模型")
            job["saozi_model"] = selector.model
        if job["state"] not in {"downloaded", "transcribing", "subtitles_ready", "analyzing", "exporting", "completed"}:
            raise ValueError("Unknown or incomplete job state")
        if job["state"] in {"downloaded", "transcribing"}:
            adapter = transcriber or LocalASR(Path(job["asr"]["model"]), job["asr"]["language"], job["asr"]["threads"])
            if adapter.identity() != job["asr"]:
                raise ValueError("Local ASR configuration changed; create a new run")
            job["state"] = "transcribing"
            write_manifest(directory, job)
            asr_offset = float(job.get("asr_offset", 0.0) or 0.0)
            asr_duration = float(job.get("asr_duration", job["duration"]))
            notify("正在本地识别并生成时间轴")
            try:
                if job.get("mode") == "ranges" and job.get("ranges"):
                    # 切片模式：按切片时长分级扩展，各区间独立转录
                    expanded = []
                    for s, e in job["ranges"]:
                        dur = e - s
                        pad = 10.0 if dur <= 120 else 20.0 if dur <= 300 else 30.0
                        expanded.append((max(0.0, s - pad), min(job["duration"], e + pad)))
                    cues = adapter.transcribe_ranges(video, directory, expanded, should_cancel=should_cancel)
                else:
                    cues = adapter.transcribe(video, directory, asr_duration, offset=asr_offset, should_cancel=should_cancel)
            except ValueError as exc:
                if not job.get("saozi") or str(exc) != "No speech was recognized; check the source audio and language":
                    raise
                cues = []
            if (not cues and not job.get("saozi")) or any(not math.isfinite(c.start_seconds) or not math.isfinite(c.end_seconds)
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
        subtitle_path = _path(directory, job["subtitles"])
        cues = media.read_subtitles(subtitle_path) if subtitle_path.read_text(encoding="utf-8-sig", errors="replace").strip() else []
        # 完整视频模式：只字幕不切片，跳过 selection/export
        if job.get("mode") == "full":
            job["state"] = "completed"
            write_manifest(directory, job)
            return job
        if job.get("saozi") and selector is not None:
            if job["state"] != "completed":
                job["state"] = "analyzing"
                write_manifest(directory, job)
            selection = selector.plan(directory, cues, job["duration"], progress=notify)
        else:
            selection = media.select_clips(cues, job["duration"], [tuple(r) for r in job["ranges"]], job["highlight_count"])
        if "selection" in job and selection != job["selection"]:
            raise ValueError("Clip selection changed during recovery")
        if job["state"] != "completed":
            job.update(state="exporting", selection=selection)
            write_manifest(directory, job)
        if not selection:
            notify("没有达到评分阈值的高光，保留完整字幕，不生成切片")
        for index, clip in enumerate(selection, start=1):
            if should_cancel is not None and should_cancel():
                raise media.RunCancelled()
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
