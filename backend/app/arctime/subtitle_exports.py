from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal, assert_never

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.arctime import media, workflow
from app.arctime.subtitle_encoding import burn_available, burn_clip, video_dimensions
from app.arctime.subtitle_inputs import ExportError, ExportInputs, ExportRequest, load_inputs
from app.arctime.subtitle_style import render_ass
from app.arctime.subtitle_document import SubtitleDocument
from app.arctime.subtitle_render import render_document_ass
from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_templates import TemplateStore
from app.services.subtitles import render_bilingual_srt, render_srt

if TYPE_CHECKING:
    from app.arctime.gui import JobManager


class ExportOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    kind: Literal["ass", "burn", "arctime"]
    video: str
    bilingual: bool
    filename: str = Field(pattern=r"^styled-[0-9a-f]{20}\.(ass|mp4|zip)$")
    sha256: str
    style: SubtitleStyle | None = None
    document: SubtitleDocument | None = None


class ExportActivity(BaseModel):
    state: Literal["exporting", "completed", "failed", "interrupted"]
    message: str
    error: str | None = None


class ExportSnapshot(BaseModel):
    active: ExportActivity | None = None
    outputs: list[ExportOutput] = Field(default_factory=list)


def _registry(directory: Path) -> Path:
    return workflow._path(directory, "subtitle-exports.json")


def read_exports(directory: Path) -> ExportSnapshot:
    path = _registry(directory)
    return ExportSnapshot.model_validate_json(path.read_bytes()) if path.is_file() else ExportSnapshot()


def export_artifact(directory: Path, name: str) -> Path:
    output = next((item for item in read_exports(directory).outputs if item.filename == name), None)
    if output is None:
        raise HTTPException(404, "导出文件不存在")
    path = workflow._path(directory, name)
    if not path.is_file() or media.fingerprint(path) != output.sha256:
        raise HTTPException(409, "导出文件缺失或发生变化；已保留文件，请重新检查")
    return path


def _package(working: Path, inputs: ExportInputs, request: ExportRequest, project: bytes | None,
             dimensions: tuple[int, int]) -> Path:
    basename = "source" if request.video == "source.mp4" else "clip"
    original = render_srt(inputs.original)
    (working / f"{basename}.srt").write_text(original, encoding="utf-8")
    names = [f"{basename}.mp4", f"{basename}.ass", f"{basename}.srt", "style.json", "README.txt"]
    shutil.copyfile(inputs.source, working / names[0])
    shutil.copyfile(working / "subtitle.ass", working / names[1])
    (working / "style.json").write_text(request.style.model_dump_json(indent=2), encoding="utf-8")
    if inputs.translated is not None:
        name = f"{basename}.ja-zh.srt"
        (working / name).write_text(render_bilingual_srt(inputs.original, [cue.text for cue in inputs.translated]), encoding="utf-8")
        names.append(name)
    if request.document is not None:
        (working / 'subtitle-document.json').write_text(request.document.model_dump_json(indent=2), encoding='utf-8')
        names.append('subtitle-document.json')
    if project is not None:
        (working / "template.atpj").write_bytes(project)
        names.append("template.atpj")
    (working / "README.txt").write_text(
        "ArcTime Pro 精修交接 / editable subtitle handoff\n"
        f"1. 导入 {basename}.mp4。\n"
        "2. 如含 template.atpj，先使用「从其它工程文件导入样式」，再导入同名 ASS（包括样式）。\n"
        "旧工程分辨率可能不同；覆盖同名样式会覆盖字号，请检查双语位置和背景。\n"
        "3. 调整字幕文字和时间轴，另存新的 .atpj 工程。\n"
        "原文和译文为独立 ASS 样式；切片从零计时。\n"
        "视频没有新增烧录字幕；原画面已有字幕不会被移除。\n"
        "请安装 style.json 中的字体；本包不包含字体文件。\n"
        "工程模板保持原生格式，可能引用旧媒体；这里只导入其样式。\n"
        "Import video; optionally import project styles first, then matching ASS with styles.\n"
        "Duplicate template styles can replace scaled font sizes; check resolution and layout.\n"
        "Check fonts/groups and save a new project. This package does not generate .atpj.\n", encoding="utf-8")
    metadata = {"version": 1, "time_origin_seconds": inputs.time_origin, "width": dimensions[0], "height": dimensions[1],
        "fonts": [request.style.original.font, request.style.translation.font],
        "sha256": {name: media.fingerprint(working / name) for name in names}}
    (working / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    archive = working / "handoff.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in [*names, "manifest.json"]:
            bundle.write(working / name, arcname=name)
    return archive


class SubtitleExports:
    def __init__(self, manager: JobManager):
        self.manager = manager
        self.templates = TemplateStore(manager.root)
        self.failures: dict[str, ExportActivity] = {}

    def snapshot(self, job_id: str) -> ExportSnapshot:
        directory = self.manager.directory(job_id)
        self.manager.detail(job_id, include_segments=False)
        with self.manager.lock:
            snapshot = read_exports(directory)
            if job_id in self.failures:
                snapshot.active = self.failures[job_id]
            live = self.manager.active
            if live and live["id"] == job_id and live["state"] == "subtitle_export":
                snapshot.active = ExportActivity(state="exporting", message=live["message"])
            elif snapshot.active and snapshot.active.state == "exporting":
                snapshot.active = ExportActivity(state="interrupted", message="字幕导出已中断，请重新导出；原结果已保留")
            return snapshot

    def submit(self, job_id: str, request: ExportRequest) -> str:
        directory = self.manager.directory(job_id)
        try:
            load_inputs(directory, request)
            project = self.templates.download_project(request.arctime_template_id) if request.arctime_template_id else None
            if request.kind == "burn" and not burn_available():
                raise ExportError("当前 FFmpeg 不支持 libass 字幕烧录")
        except (OSError, ValueError) as error:
            raise HTTPException(409, str(error) if isinstance(error, ExportError) else "任务或模板文件无效，请检查后重试") from None
        with self.manager.lock:
            if self.manager.active:
                raise HTTPException(409, "已有任务正在处理，请等待完成")
            try:
                read_exports(directory)
            except (OSError, ValueError):
                raise HTTPException(409, "导出记录无效，请检查后重试") from None
            self.failures.pop(job_id, None)
            self.manager.active = {"id": job_id, "state": "subtitle_export", "message": "准备字幕导出", "error": None}
            self.manager.executor.submit(self.run, job_id, request, project)
        return job_id

    def run(self, job_id: str, request: ExportRequest, project: bytes | None) -> None:
        directory = self.manager.directory(job_id)
        errors = (OSError, ValueError, RuntimeError, subprocess.SubprocessError, HTTPException)
        try:
            with workflow.exclusive_lock(directory / ".lock"):
                snapshot = read_exports(directory)
                try:
                    self._run_locked(directory, request, project, snapshot)
                except errors:
                    snapshot.active = ExportActivity(state="failed", message="字幕导出失败")
                    media.write_json(_registry(directory), snapshot.model_dump())
                    raise
        except errors as error:
            message = str(error) if isinstance(error, ExportError) else "字幕导出失败；原文件已保留，请检查文件、模板和编码日志后重试"
            with self.manager.lock:
                self.failures[job_id] = ExportActivity(state="failed", message="字幕导出失败", error=message)
        finally:
            with self.manager.lock:
                self.manager.last = self.manager.active
                self.manager.active = None

    def _run_locked(self, directory: Path, request: ExportRequest, project: bytes | None, snapshot: ExportSnapshot) -> None:
        def progress(message: str) -> None:
            snapshot.active = ExportActivity(state="exporting", message=message)
            media.write_json(_registry(directory), snapshot.model_dump())
            with self.manager.lock:
                if self.manager.active:
                    self.manager.active["message"] = message
        progress("正在校验字幕和媒体")
        inputs = load_inputs(directory, request)
        identity = hashlib.sha256(json.dumps({"renderer_revision": 2, "package_revision": 1, "request": request.model_dump(), "inputs": inputs.digests,
            "project": hashlib.sha256(project).hexdigest() if project else None}, sort_keys=True).encode()).hexdigest()[:20]
        extension = {"ass": "ass", "burn": "mp4", "arctime": "zip"}[request.kind]
        filename = f"styled-{identity}.{extension}"
        destination = workflow._path(directory, filename)
        receipt = workflow._path(directory, f"styled-{identity}.receipt.json")
        pending = ExportOutput.model_validate_json(receipt.read_bytes()) if receipt.is_file() else None
        if pending and (pending.id != identity or pending.filename != filename or pending.kind != request.kind
                        or pending.video != request.video or pending.bilingual != request.bilingual or pending.style != request.style or pending.document != request.document):
            raise ExportError("导出恢复记录与请求不一致；已保留文件，请检查")
        existing = next((item for item in snapshot.outputs if item.id == identity), None)
        if existing:
            export_artifact(directory, existing.filename)
        elif destination.exists():
            if pending is None or not destination.is_file() or media.fingerprint(destination) != pending.sha256:
                raise ExportError("已有导出文件无法验证；已保留文件，请检查")
            snapshot.outputs.append(pending)
        else:
            dimensions = video_dimensions(inputs.source)
            content = (render_document_ass(inputs.document, request.bilingual) if inputs.document is not None else
                       render_ass(inputs.original, inputs.translated, request.style, *dimensions, video_canvas=request.kind != "burn"))
            with tempfile.TemporaryDirectory(prefix=".subtitle-export-", dir=directory) as temporary:
                working = Path(temporary)
                (working / "subtitle.ass").write_text(content, encoding="utf-8")
                try:
                    match request.kind:
                        case "ass":
                            product = working / "subtitle.ass"
                        case "burn":
                            product = burn_clip(inputs.source, working, media.probe_video(inputs.source), progress)
                        case "arctime":
                            progress("正在打包 ArcTime 精修文件")
                            product = _package(working, inputs, request, project, dimensions)
                        case unreachable:
                            assert_never(unreachable)
                    output = ExportOutput(id=identity, kind=request.kind, video=request.video, bilingual=request.bilingual,
                        filename=filename, sha256=media.fingerprint(product), style=request.style, document=request.document)
                    if pending is not None and pending != output:
                        raise ExportError("导出内容与恢复记录不一致；已保留文件，请检查")
                    if pending is None:
                        with receipt.open("x", encoding="utf-8") as handle:
                            handle.write(output.model_dump_json())
                            handle.flush()
                            os.fsync(handle.fileno())
                    os.link(product, destination)
                    snapshot.outputs.append(output)
                finally:
                    log = working / "encoder.log"
                    if log.is_file():
                        shutil.copyfile(log, workflow._path(directory, f"styled-{identity}.log"))
        snapshot.active = ExportActivity(state="completed", message="字幕导出完成")
        media.write_json(_registry(directory), snapshot.model_dump())
