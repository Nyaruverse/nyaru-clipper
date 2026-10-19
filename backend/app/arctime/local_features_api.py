"""本地定制功能路由：术语表、内容切片、切片视频、图形绘制、手动终止、旧版字幕样式与烧录合成、调试端点。

这些端点是本地分支独有功能，集中挂载避免改动上游 gui.py 主体。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.arctime import glossary, media, topic_segments, topic_video, translation, workflow
from app.arctime import subtitle_style_legacy as legacy_style


class TopicClipsInput(BaseModel):
    indices: list[int] = Field(min_length=1, max_length=100)
    mode: Literal["separate", "combined"] = "separate"
    variant: Literal["bilingual", "zh", "original"] = "bilingual"


class BurnInput(BaseModel):
    clip: str = Field(max_length=255)
    variant: Literal["bilingual", "zh", "original"] = "bilingual"


class TranslationEditInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


# ---- 管理器辅助（附加到 JobManager 实例，避免改动上游类定义）----

def _ensure_manager_extras(manager) -> None:
    if not hasattr(manager, "topic_clipping"):
        manager.topic_clipping = set()
    if not hasattr(manager, "burning"):
        manager.burning = set()


def _style_path(manager) -> Path:
    return manager.root / "style.json"


def load_style_store(manager) -> legacy_style.StyleStore:
    return legacy_style.load_style_store(_style_path(manager))


def save_style_store(manager, store: legacy_style.StyleStore) -> None:
    path = _style_path(manager)
    if path.is_symlink():
        raise HTTPException(409, "样式配置不能是符号链接，请检查 style.json")
    try:
        media.write_json(path, store.model_dump(mode="json"))
    except OSError:
        raise HTTPException(500, "样式配置保存失败，请检查数据目录权限后重试") from None


def load_glossary_store(manager) -> glossary.GlossaryStore:
    return glossary.load_glossary(manager.root / "glossary.json")


def save_glossary_store(manager, store: glossary.GlossaryStore) -> None:
    path = manager.root / "glossary.json"
    if path.is_symlink():
        raise HTTPException(409, "术语表不能是符号链接，请检查 glossary.json")
    try:
        media.write_json(path, store.model_dump(mode="json"))
    except OSError:
        raise HTTPException(500, "术语表保存失败，请检查数据目录权限后重试") from None


def read_topic_clips(manager, directory: Path) -> dict:
    path = directory / "topic_clips.json"
    try:
        if path.is_symlink() or not path.is_file():
            return {"state": "not_started"}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"state": "not_started"}
    if not isinstance(value, dict) or (not isinstance(value.get("items"), list) and value.get("state") != "stale"):
        return {"state": "not_started"}
    return value


def submit_topic_clips(manager, job_id: str, indices: list[int], mode: str, variant: str) -> dict:
    _ensure_manager_extras(manager)
    directory = manager.directory(job_id)
    job = manager.read_json(directory / "job.json")
    if job.get("state") != "completed" or not (directory / "source.mp4").is_file():
        raise HTTPException(409, "请等待视频任务完成后再生成切片视频")
    stored = topic_segments.read_store(directory)
    identity = topic_segments.current_identity(directory)
    if (stored is None or stored.get("state") != "completed"
            or identity is None or stored.get("identity") != identity):
        raise HTTPException(409, "请先生成（或重新生成）内容切片，再生成切片视频")
    try:
        topic_store = topic_segments.TopicSegmentStore.model_validate(stored)
    except ValueError:
        raise HTTPException(409, "内容切片结果已损坏，请重新生成") from None
    segments = topic_store.segments
    normalized: list[int] = []
    for index in indices:
        if not isinstance(index, int) or not 0 <= index < len(segments) or index in normalized:
            raise HTTPException(400, "包含无效或重复的切片编号")
        normalized.append(index)
    # 保留客户端给定的顺序：组合视频按用户的点击选择顺序合并
    # 保留上一轮分别生成的段产物（独立资产，组合生成不应让它们从界面消失）
    previous = read_topic_clips(manager, directory)
    legacy_files = {
        item["index"]: item["file"]
        for item in previous.get("items", [])
        if isinstance(item, dict) and item.get("state") == "completed"
        and isinstance(item.get("file"), str) and (directory / item["file"]).is_file()
    }
    if variant in {"bilingual", "zh"}:
        if manager.read_json(directory / "translation.json").get("state") != "completed":
            raise HTTPException(409, "请先生成中日双语字幕，或选择烧录仅原文字幕")
        translation.ensure_zh_srt(directory)
        if not (directory / "subtitles.zh.srt").is_file():
            raise HTTPException(409, "译文字幕缺失，无法合成；请重新生成双语字幕")
    with manager.lock:
        if job_id in manager.topic_clipping:
            raise HTTPException(409, "切片视频正在生成中，请等待完成")
        manager.topic_clipping.add(job_id)
        state_record = {
            "state": "running", "mode": mode, "variant": variant, "indices": normalized,
            "done": 0, "total": len(normalized), "message": "正在准备生成切片视频…",
            "error": None, "items": [], "combined": None, "created_at": time.time(),
        }
        media.write_json(directory / "topic_clips.json", state_record)
    manager.executor.submit(run_topic_clips, manager, job_id, normalized, mode, variant, legacy_files)
    return state_record


def run_topic_clips(manager, job_id: str, indices: list[int], mode: str, variant: str,
                    legacy_files: dict | None = None) -> None:
    directory = manager.directory(job_id)

    def write(**changes) -> None:
        with manager.lock:
            record = read_topic_clips(manager, directory)
            record.update(changes)
            media.write_json(directory / "topic_clips.json", record)

    try:
        stored = topic_segments.read_store(directory)
        topic_store = topic_segments.TopicSegmentStore.model_validate(stored)
        segments = [segment.model_dump() for segment in topic_store.segments]

        def progress(done: int, total: int, message: str) -> None:
            write(done=done, message=message)

        result = topic_video.generate(directory, segments, indices, mode, variant,
                                      load_style_store(manager), progress)
        # 合并历史段产物：本次未涉及的段保留；组合模式下各段继承最近一次独立产物
        merged: dict[int, dict] = {item["index"]: item for item in result.get("items", [])}
        for legacy_index, legacy_file in (legacy_files or {}).items():
            if not isinstance(legacy_file, str) or not (directory / legacy_file).is_file():
                continue
            current = merged.get(legacy_index)
            if current is None:
                merged[legacy_index] = {"index": legacy_index, "file": legacy_file,
                                        "state": "completed", "error": None}
            elif mode == "combined" and current.get("file") is None and current.get("state") == "completed":
                current["file"] = legacy_file
        result["items"] = [merged[key] for key in sorted(merged)]
        failed = [item for item in result["items"] if item.get("state") == "failed"]
        if mode == "separate" and failed:
            write(state="failed", done=len(indices),
                  message=f"完成 {len(indices) - len(failed)}/{len(indices)} 段",
                  error=f"{len(failed)} 个切片生成失败：" + "；".join((item.get("error") or "")[:120] for item in failed[:2]),
                  **result)
        else:
            write(state="completed", done=len(indices), message="切片视频生成完成", **result)
    except Exception as exc:
        error = "切片视频生成超时，请重试" if isinstance(exc, subprocess.TimeoutExpired) else str(exc)[:300]
        write(state="failed", error=error, message="切片视频生成失败")
    finally:
        with manager.lock:
            manager.topic_clipping.discard(job_id)


# ---- 旧版字幕样式与烧录合成 ----

def _validate_style(config: legacy_style.SubtitleStyleConfig) -> legacy_style.SubtitleStyleConfig:
    try:
        config.original.validate_font()
        config.translated.validate_font()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return config


def read_burns(directory: Path) -> dict:
    path = directory / "burn.json"
    try:
        if path.is_symlink() or not path.is_file():
            return {"clips": {}}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"clips": {}}
    return value if isinstance(value, dict) and isinstance(value.get("clips"), dict) else {"clips": {}}


def submit_burn(manager, job_id: str, clip_name: str, variant: str) -> dict:
    _ensure_manager_extras(manager)
    directory = manager.directory(job_id)
    job = manager.read_json(directory / "job.json")
    if job.get("state") != "completed":
        raise HTTPException(409, "请等待视频任务完成后再合成")
    if not any(c["video"] == clip_name for c in job.get("completed_clips", [])):
        raise HTTPException(404, "切片不存在")
    if variant in {"bilingual", "zh"}:
        if manager.read_json(directory / "translation.json").get("state") != "completed":
            raise HTTPException(409, "请先生成中日双语字幕")
        translation.ensure_zh_srt(directory)
    file = f"{Path(clip_name).stem}.burn.{variant}.mp4"
    with manager.lock:
        key = (job_id, clip_name, variant)
        if key in manager.burning:
            raise HTTPException(409, "该切片正在合成中，请稍候")
        burns = read_burns(directory)
        burns["clips"].setdefault(clip_name, {})[variant] = {"state": "burning", "file": file, "error": None}
        media.write_json(directory / "burn.json", burns)
        manager.burning.add(key)
    manager.executor.submit(run_burn, manager, job_id, clip_name, variant)
    return {"file": file, "state": "burning"}


def run_burn(manager, job_id: str, clip_name: str, variant: str) -> None:
    directory = manager.directory(job_id)

    def record(state: str, error: str | None = None, file: str | None = None) -> None:
        with manager.lock:
            burns = read_burns(directory)
            entry: dict = {"state": state, "file": file, "error": error}
            if state == "completed" and file:
                entry["sha256"] = media.fingerprint(directory / file)
            burns["clips"].setdefault(clip_name, {})[variant] = entry
            media.write_json(directory / "burn.json", burns)

    ass_path: Path | None = None
    shape_pngs: list[Path] = []
    try:
        job = json.loads(workflow._path(directory, "job.json").read_text())
        index = next(i for i, c in enumerate(job["completed_clips"]) if c["video"] == clip_name)
        selection = job["selection"][index]
        cues = media.clip_subtitles(media.read_subtitles(workflow._path(directory, job["subtitles"])),
                                    selection["start"], selection["end"])
        translated: list[str] | None = None
        if variant in {"bilingual", "zh"}:
            zh_path = workflow._path(directory, f"{Path(clip_name).stem}.zh.srt")
            if not zh_path.is_file():
                translation.ensure_zh_srt(directory)
            if not zh_path.is_file():
                raise ValueError("译文字幕缺失，无法合成；请重新生成双语字幕")
            translated = [c.text for c in media.read_subtitles(zh_path)]
        style_store = load_style_store(manager)
        style = style_store.current
        stem = Path(clip_name).stem
        file = f"{stem}.burn.{variant}.mp4"
        ass_path = workflow._path(directory, f".{stem}.burn.{variant}.ass")
        workflow._publish_text(ass_path, legacy_style.render_ass(cues, translated, style, variant))
        output = workflow._path(directory, file)
        output.unlink(missing_ok=True)
        # 矩形图形按视频实际分辨率渲染为透明 PNG，overlay 叠加在字幕下层
        inputs = ["-i", clip_name]
        if style_store.shapes:
            probe = subprocess.run(
                [media.tool_path("ffprobe"), "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0", clip_name],
                cwd=directory, capture_output=True, text=True, timeout=60, check=False)
            parts = probe.stdout.strip().split(",")
            if probe.returncode != 0 or len(parts) != 2 or not all(p.isdigit() for p in parts):
                raise ValueError("无法读取视频分辨率，合成已取消")
            shape_pngs = legacy_style.render_shape_pngs(style_store.shapes, directory, stem,
                                                        width=int(parts[0]), height=int(parts[1]))
            for png in shape_pngs:
                inputs += ["-loop", "1", "-i", png.name]
            chain = ""
            previous = "0:v"
            for shape_index in range(len(shape_pngs)):
                chain += f"[{previous}][{shape_index + 1}:v]overlay=0:0[s{shape_index}];"
                previous = f"s{shape_index}"
            video_filter = f"{chain}[{previous}]subtitles={ass_path.name}"
            filter_arg = "-filter_complex"
        else:
            video_filter = f"subtitles={ass_path.name}"
            filter_arg = "-vf"
        result = subprocess.run(
            [media.tool_path("ffmpeg"), "-hide_banner", "-y", *inputs,
             filter_arg, video_filter,
             "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "copy",
             "-shortest", "-movflags", "+faststart", file],
            cwd=directory, capture_output=True, text=True, timeout=1800, check=False)
        if result.returncode != 0 or not output.is_file():
            tail = (result.stderr or "").strip().splitlines()
            raise ValueError(f"视频合成失败：{tail[-1] if tail else '未知错误'}")
        record("completed", file=file)
    except subprocess.TimeoutExpired:
        record("failed", error="合成超时，请重试")
    except Exception as exc:
        record("failed", error=str(exc)[:300])
    finally:
        if ass_path is not None:
            try:
                ass_path.unlink(missing_ok=True)
            except OSError:
                pass
        for png in shape_pngs:
            try:
                png.unlink(missing_ok=True)
            except OSError:
                pass
        with manager.lock:
            manager.burning.discard((job_id, clip_name, variant))


# ---- 路由 ----

def local_features_router(manager) -> APIRouter:
    _ensure_manager_extras(manager)
    router = APIRouter(prefix="/companion-api")

    @router.get("/debug/paths")
    def debug_paths():
        import app as app_pkg
        return {"gui_file": str(Path(__file__).resolve()),
                "app_package": str(Path(app_pkg.__file__).resolve()),
                "sys_executable": sys.executable,
                "cwd": str(Path.cwd()),
                "data_root": str(manager.root),
                "sys_path_head": sys.path[:5]}

    @router.get("/jobs-debug")
    def list_jobs_debug():
        import re
        ids = {p.name for p in manager.root.iterdir() if p.is_dir() and not p.is_symlink() and re.fullmatch(r"[0-9a-f]{12}", p.name)}
        with manager.lock:
            if manager.active:
                ids.add(manager.active["id"])
            if manager.last:
                ids.add(manager.last["id"])
        results = []
        for job_id in sorted(ids):
            try:
                job_json = manager.read_json(manager.directory(job_id) / "job.json")
                ver = job_json.get("version", 2)
                if ver != 2:
                    results.append({"id": job_id, "status": "skip_version", "version": ver})
                    continue
                r = manager.detail(job_id, include_segments=False)
                results.append({"id": job_id, "status": "ok", "state": r.get("state")})
            except Exception as e:
                results.append({"id": job_id, "status": "error", "type": type(e).__name__, "message": str(e)})
        return {"total": len(ids), "ok": sum(1 for r in results if r["status"] == "ok"), "results": results}

    @router.post("/jobs/{job_id}/cancel", status_code=202)
    def cancel_job(job_id: str):
        manager.cancel(job_id)
        return {"id": job_id, "state": "cancelling"}

    # ---- 内容切片 ----

    @router.get("/jobs/{job_id}/topic-segments")
    def get_topic_segments(job_id: str):
        directory = manager.directory(job_id)
        if not (directory / "job.json").is_file():
            raise HTTPException(404, "任务不存在")
        stored = topic_segments.read_store(directory)
        identity = topic_segments.current_identity(directory)
        if stored is None:
            return {"state": "not_started"}
        if identity is None or stored.get("identity") != identity or stored.get("state") != "completed":
            return {**stored, "state": "stale"}
        return stored

    @router.post("/jobs/{job_id}/topic-segments")
    def create_topic_segments(job_id: str, options: topic_segments.TopicAnalyzeOptions | None = None):
        directory = manager.directory(job_id)
        job = manager.read_json(directory / "job.json")
        if not job:
            raise HTTPException(404, "任务不存在")
        if job.get("state") != "completed":
            raise HTTPException(409, "请等待视频任务完成后再生成内容切片")
        if manager.config_error:
            raise HTTPException(409, "请先修复翻译配置，再生成内容切片")
        if not manager.api_key:
            raise HTTPException(409, "请先输入 DeepSeek API Key")
        translated = manager.read_json(directory / "translation.json")
        if translated.get("state") != "completed":
            raise HTTPException(409, "请先完成日译中翻译后再生成内容切片")
        if topic_segments.current_identity(directory) is None:
            raise HTTPException(409, "双语字幕文件缺失，请重新生成翻译后再试")
        if job_id in manager.topic_clipping:
            raise HTTPException(409, "切片视频正在生成中，请等待完成后再重新分析")
        model = translated.get("identity", {}).get("model") or manager.translation_model
        try:
            store = topic_segments.analyze_directory(directory, manager.api_key, model, options=options)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        # 内容切片已更新，旧切片视频的编号/边界可能错位，标记过期
        if read_topic_clips(manager, directory).get("state") != "not_started":
            media.write_json(directory / "topic_clips.json", {"state": "stale", "items": []})
        return store.model_dump(mode="json")

    @router.get("/jobs/{job_id}/topic-segments.txt")
    def topic_segments_text(job_id: str):
        directory = manager.directory(job_id)
        stored = topic_segments.read_store(directory)
        identity = topic_segments.current_identity(directory)
        if (stored is None or identity is None or stored.get("identity") != identity
                or stored.get("state") != "completed"):
            raise HTTPException(404, "内容切片不存在，请先生成")
        try:
            store = topic_segments.TopicSegmentStore.model_validate(stored)
        except ValueError:
            raise HTTPException(409, "内容切片结果已损坏，请重新生成") from None
        return Response(topic_segments.render_text(store), media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{job_id}-topic-segments.txt"'})

    # ---- 切片视频 ----

    @router.get("/jobs/{job_id}/topic-clips")
    def get_topic_clips(job_id: str):
        directory = manager.directory(job_id)
        record = read_topic_clips(manager, directory)
        with manager.lock:
            active = job_id in manager.topic_clipping
        if record.get("state") == "running" and not active:
            record = {**record, "state": "failed", "error": "切片视频生成已中断，请重新生成"}
        return record

    @router.post("/jobs/{job_id}/topic-clips", status_code=202)
    def create_topic_clips(job_id: str, payload: TopicClipsInput):
        return submit_topic_clips(manager, job_id, payload.indices, payload.mode, payload.variant)

    # ---- 术语表 ----

    @router.get("/glossary")
    def get_glossary():
        return load_glossary_store(manager).model_dump(mode="json")

    @router.put("/glossary")
    def put_glossary(payload: glossary.TermsUpdate):
        store = load_glossary_store(manager)
        store.terms = payload.terms
        save_glossary_store(manager, store)
        return store.model_dump(mode="json")

    @router.post("/glossary/import")
    def import_glossary(payload: glossary.TermsImport):
        store = load_glossary_store(manager)
        incoming, skipped = glossary.parse_terms_text(payload.text)
        if not incoming and skipped:
            raise HTTPException(422, "未解析到有效词条，请确认格式为 `# 原文=统一译文`")
        # 按 src 合并：导入词条覆盖同 src 已有项
        existing = {term.src: term for term in store.terms}
        for term in incoming:
            existing[term.src] = term
        merged = list(existing.values())
        if len(merged) > glossary.MAX_TERMS:
            raise HTTPException(422, f"合并后词条数超过上限 {glossary.MAX_TERMS}，请分批导入")
        store.terms = merged
        save_glossary_store(manager, store)
        return store.model_dump(mode="json")

    @router.post("/glossary/candidates/{index}/accept")
    def accept_glossary_candidate(index: int, payload: glossary.Term):
        store = load_glossary_store(manager)
        if not 0 <= index < len(store.candidates):
            raise HTTPException(404, "候选词不存在或已处理")
        store.candidates.pop(index)
        store.terms = [term for term in store.terms if term.src != payload.src]
        if len(store.terms) >= glossary.MAX_TERMS:
            raise HTTPException(422, "术语表已达上限")
        store.terms.append(payload)
        save_glossary_store(manager, store)
        return store.model_dump(mode="json")

    @router.post("/glossary/candidates/{index}/ignore")
    def ignore_glossary_candidate(index: int):
        store = load_glossary_store(manager)
        if not 0 <= index < len(store.candidates):
            raise HTTPException(404, "候选词不存在或已处理")
        candidate = store.candidates.pop(index)
        if candidate.src not in store.ignored:
            store.ignored.append(candidate.src)
        save_glossary_store(manager, store)
        return store.model_dump(mode="json")

    # ---- 旧版字幕样式 ----

    @router.get("/subtitle-style")
    def get_subtitle_style():
        return load_style_store(manager).model_dump(mode="json")

    @router.put("/subtitle-style")
    def put_subtitle_style(payload: legacy_style.SubtitleStyleConfig):
        store = load_style_store(manager)
        store.current = _validate_style(payload)
        save_style_store(manager, store)
        return store.model_dump(mode="json")

    @router.put("/subtitle-style/templates/{name}")
    def put_subtitle_style_template(name: str, payload: legacy_style.SubtitleStyleConfig):
        if not legacy_style.TEMPLATE_NAME.fullmatch(name):
            raise HTTPException(422, "模板名称无效")
        store = load_style_store(manager)
        if name not in store.templates and len(store.templates) >= legacy_style.MAX_TEMPLATES:
            raise HTTPException(422, "模板数量已达上限")
        store.templates[name] = _validate_style(payload)
        save_style_store(manager, store)
        return store.model_dump(mode="json")

    @router.delete("/subtitle-style/templates/{name}")
    def delete_subtitle_style_template(name: str):
        store = load_style_store(manager)
        store.templates.pop(name, None)
        save_style_store(manager, store)
        return store.model_dump(mode="json")

    # ---- 烧录合成 ----

    @router.post("/jobs/{job_id}/burn", status_code=202)
    def create_burn(job_id: str, payload: BurnInput):
        return submit_burn(manager, job_id, payload.clip, payload.variant)

    # ---- 图形绘制（存于 legacy style.json 的 shapes 字段）----

    @router.get("/shapes")
    def get_shapes():
        return {"shapes": [s.model_dump(mode="json") for s in load_style_store(manager).shapes]}

    @router.put("/shapes")
    def put_shapes(payload: legacy_style.ShapesUpdate):
        store = load_style_store(manager)
        store.shapes = payload.shapes
        save_style_store(manager, store)
        return {"shapes": [s.model_dump(mode="json") for s in store.shapes]}

    @router.put("/jobs/{job_id}/translation/{cue_id}")
    def edit_job_translation(job_id: str, cue_id: int, payload: TranslationEditInput):
        directory = manager.directory(job_id)
        try:
            translation.edit_translated(directory, cue_id, payload.text)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        except OSError as exc:
            raise HTTPException(500, f"译文保存失败：{exc}")
        return {"ok": True}

    return router
