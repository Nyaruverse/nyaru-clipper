from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.arctime import (clip_words, danmaku, danmaku_fetch, danmaku_render, media, publish, topic_segments,
                         topic_video, translation, workflow)
from app.arctime import subtitle_style_legacy as legacy_style
from app.arctime.local_asr import LocalASR

TEMPLATES_NAME = "automation_templates.json"
TASKS_NAME = "automation_tasks.json"
MAX_TASKS = 200
STAGE_LABELS = [("import", "导入"), ("transcribe", "转写"), ("translate", "翻译"),
                ("clips", "切片"), ("publish", "投稿")]
# 与唱歌区间重合超过该比例的切片不进入自动选段（无音频因子时 song_overlap 为空，不拦截）
MAX_SONG_OVERLAP = .30


class AutomationConfig(BaseModel):
    language: str = Field(default="auto", pattern=r"^[a-z]{2,8}$")
    translate: bool = True
    max_segments: int = Field(default=30, ge=1, le=100)
    # 单条切片时长上限（秒）：超过该值的段落不进入自动选段，避免生成超长视频
    max_clip_seconds: int = Field(default=600, ge=30, le=3600)
    use_top_n: bool = True
    top_n: int = Field(default=5, ge=1, le=50)
    use_min_score: bool = False
    min_score: int = Field(default=80, ge=0, le=100)
    per_minutes: int = Field(default=30, ge=1, le=1440)
    per_count: int = Field(default=2, ge=1, le=20)
    generate_clips: bool = True
    auto_publish: bool = True
    publish_count: int | None = Field(default=None, ge=1, le=100)
    variant: Literal["bilingual", "zh", "original"] = "bilingual"
    style_template: str = Field(default="", max_length=64)
    shapes_template: str = Field(default="", max_length=64)
    # 切片弹幕：任务目录有弹幕数据时，把对应时间段的弹幕烧录到切片（位于字幕层下方）
    danmaku_enabled: bool = True
    danmaku_font_size: int = Field(default=40, ge=12, le=96)
    danmaku_area_height: int = Field(default=60, ge=10, le=100)


DEFAULT_CONFIG = AutomationConfig()


class TemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    config: AutomationConfig | None = None


def _templates_path(manager) -> Path:
    return manager.root / TEMPLATES_NAME


def _tasks_path(manager) -> Path:
    return manager.root / TASKS_NAME


def _stage_list() -> list[dict]:
    return [{"key": key, "label": label, "state": "pending", "message": None, "error": None}
            for key, label in STAGE_LABELS]


def read_templates(manager) -> list[dict]:
    path = _templates_path(manager)
    try:
        if path.is_symlink():
            raise ValueError
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        value = {}
    rows = value.get("templates") if isinstance(value, dict) else None
    templates: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            config = AutomationConfig.model_validate(row.get("config") or {})
        except ValueError:
            continue
        templates.append({"id": str(row.get("id") or ""), "name": str(row.get("name") or "未命名")[:40],
                          "config": config.model_dump(mode="json"),
                          "created_at": float(row.get("created_at") or 0),
                          "updated_at": float(row.get("updated_at") or 0)})
    if not templates:
        now = time.time()
        templates = [{"id": "default", "name": "默认模板", "config": DEFAULT_CONFIG.model_dump(mode="json"),
                      "created_at": now, "updated_at": now}]
        _write(_templates_path(manager), {"templates": templates})
    return templates


def save_template(manager, payload: TemplateInput, template_id: str | None = None) -> list[dict]:
    templates = read_templates(manager)
    config = (payload.config or DEFAULT_CONFIG).model_dump(mode="json")
    now = time.time()
    if template_id:
        target = next((item for item in templates if item["id"] == template_id), None)
        if target is None:
            raise KeyError(template_id)
        target.update(name=payload.name.strip()[:40], config=config, updated_at=now)
    else:
        template_id = uuid.uuid4().hex[:8]
        templates.append({"id": template_id, "name": payload.name.strip()[:40], "config": config,
                          "created_at": now, "updated_at": now})
    _write(_templates_path(manager), {"templates": templates})
    return templates


def delete_template(manager, template_id: str) -> list[dict]:
    templates = read_templates(manager)
    if not any(item["id"] == template_id for item in templates):
        raise KeyError(template_id)
    if len(templates) == 1:
        raise ValueError("至少保留一个自动化模板")
    _write(_templates_path(manager), {"templates": [item for item in templates if item["id"] != template_id]})
    return read_templates(manager)


def read_tasks(manager) -> list[dict]:
    try:
        if _tasks_path(manager).is_symlink():
            raise ValueError
        value = json.loads(_tasks_path(manager).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    rows = value.get("tasks") if isinstance(value, dict) else None
    return [row for row in rows or [] if isinstance(row, dict)]


def _write(path: Path, value: dict) -> None:
    try:
        media.write_json(path, value)
    except OSError:
        pass


def _write_tasks(manager, tasks: list[dict]) -> None:
    _write(_tasks_path(manager), {"tasks": tasks[-MAX_TASKS:]})


def _patch_task(manager, task_id: str, **changes) -> dict | None:
    with manager.lock:
        tasks = read_tasks(manager)
        target = next((item for item in tasks if item.get("id") == task_id), None)
        if target is None:
            return None
        target.update(changes)
        _write_tasks(manager, tasks)
        return dict(target)


def _set_stage(manager, task_id: str, key: str, state: str, message: str | None = None,
               error: str | None = None) -> None:
    with manager.lock:
        tasks = read_tasks(manager)
        target = next((item for item in tasks if item.get("id") == task_id), None)
        if target is None:
            return
        for stage in target.get("stages") or []:
            if stage.get("key") == key:
                stage["state"] = state
                stage["message"] = message
                stage["error"] = error
        _write_tasks(manager, tasks)


def resolve_config(manager, template_id: str | None, config: AutomationConfig | None) -> tuple[AutomationConfig, str]:
    if config is not None:
        return config, ""
    templates = read_templates(manager)
    if template_id:
        target = next((item for item in templates if item["id"] == template_id), None)
        if target is None:
            raise ValueError("自动化模板不存在，请重新选择")
        return AutomationConfig.model_validate(target["config"]), str(target.get("name") or "")
    target = templates[0]
    return AutomationConfig.model_validate(target["config"]), str(target.get("name") or "")


def enqueue(manager, *, kind: str, title: str, config: AutomationConfig | None = None,
            template_id: str | None = None, url: str | None = None,
            source_path: Path | None = None, source_name: str = "",
            recording_dir: Path | None = None, auto_start: bool = True) -> dict:
    if kind not in {"recording", "upload", "url"}:
        raise ValueError("未知的自动化入口类型")
    selected, template_name = resolve_config(manager, template_id, config)
    if selected.generate_clips and not manager.api_key:
        raise ValueError("自动切片需要先保存 DeepSeek API Key")
    if kind == "url":
        if not url:
            raise ValueError("请输入视频链接")
        from app.arctime.companion_models import JobInput
        payload = JobInput(url=url, language=selected.language)
        url = payload.url
    elif source_path is None or not Path(source_path).is_file():
        raise ValueError("请选择有效的本地视频文件")
    tasks = read_tasks(manager)
    task = {
        "id": uuid.uuid4().hex[:12],
        "job_id": uuid.uuid4().hex[:12],
        "kind": kind,
        "title": (title or "未命名视频").strip()[:120],
        "source_name": source_name or (Path(source_path).name if source_path else ""),
        "url": url,
        "source_path": str(source_path) if source_path else None,
        "recording_dir": str(recording_dir) if recording_dir else None,
        "config": selected.model_dump(mode="json"),
        "template_name": template_name,
        "state": "queued" if auto_start else "draft",
        "stages": _stage_list(),
        "selected": [],
        "error": None,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
    }
    tasks.append(task)
    _write_tasks(manager, tasks)
    if auto_start:
        ensure_worker(manager)
    return task


def start_task(manager, task_id: str) -> dict:
    """把「待开始」的任务手动加入执行队列。"""
    with manager.lock:
        tasks = read_tasks(manager)
        target = next((item for item in tasks if item.get("id") == task_id), None)
        if target is None:
            raise KeyError(task_id)
        if target.get("state") != "draft":
            raise RuntimeError("只有待开始的任务可以手动开始")
        target["state"] = "queued"
        _write_tasks(manager, tasks)
        result = dict(target)
    ensure_worker(manager)
    return result


def retry_task(manager, task_id: str) -> dict:
    with manager.lock:
        tasks = read_tasks(manager)
        target = next((item for item in tasks if item.get("id") == task_id), None)
        if target is None:
            raise KeyError(task_id)
        if target.get("state") == "running":
            raise RuntimeError("自动化任务正在运行，无法重试")
        target["state"] = "queued"
        target["error"] = None
        target["finished_at"] = None
        for stage in target.get("stages") or []:
            if stage.get("state") in {"failed", "running"}:
                stage.update(state="pending", message=None, error=None)
        _write_tasks(manager, tasks)
        result = dict(target)
    ensure_worker(manager)
    return result


def attach_danmaku(manager, task_id: str, path: Path, name: str, count: int) -> dict:
    """给尚未开始的任务挂上弹幕文件，导入阶段会把它转成任务目录的 danmaku.json。"""
    task = _patch_task(manager, task_id, danmaku_path=str(path), danmaku_name=name[:120],
                       danmaku_count=count)
    if task is None:
        raise KeyError(task_id)
    return task


def delete_task(manager, task_id: str) -> None:
    with manager.lock:
        tasks = read_tasks(manager)
        target = next((item for item in tasks if item.get("id") == task_id), None)
        if target is None:
            raise KeyError(task_id)
        if target.get("state") == "running":
            raise RuntimeError("自动化任务正在运行，无法删除")
        _write_tasks(manager, [item for item in tasks if item.get("id") != task_id])
    leftover = target.get("danmaku_path")
    if leftover:
        try:
            Path(str(leftover)).unlink(missing_ok=True)
        except OSError:
            pass


def ensure_worker(manager) -> None:
    with manager.lock:
        thread = getattr(manager, "automation_thread", None)
        if thread is not None and thread.is_alive():
            return
        thread = threading.Thread(target=_loop, args=(manager,), name="automation-worker", daemon=True)
        manager.automation_thread = thread
    thread.start()


def _loop(manager) -> None:
    while True:
        task = _claim(manager)
        if task is None:
            time.sleep(2)
            continue
        _run_task(manager, task)


def _claim(manager) -> dict | None:
    with manager.lock:
        if manager.active:
            return None
        tasks = read_tasks(manager)
        target = next((item for item in tasks if item.get("state") == "queued"), None)
        if target is None:
            return None
        target["state"] = "running"
        target["started_at"] = time.time()
        target["error"] = None
        job_id = str(target["job_id"])
        manager.active = {"id": job_id, "state": "preparing", "message": "准备自动化任务",
                          "started_at": time.time(), "error": None, "live": False, "saozi": False,
                          "model": manager.translation_model, "llm_provider": manager.llm_provider}
        _write_tasks(manager, tasks)
        return dict(target)


def _finish(manager, task_id: str, state: str, error: str | None) -> None:
    with manager.lock:
        tasks = read_tasks(manager)
        target = next((item for item in tasks if item.get("id") == task_id), None)
        if target is not None:
            target["state"] = state
            target["error"] = error
            target["finished_at"] = time.time()
            _write_tasks(manager, tasks)
        if manager.active and manager.active.get("id") == (target or {}).get("job_id"):
            manager.last = manager.active
            manager.active = None


def _notify(manager, state: str, message: str) -> None:
    with manager.lock:
        if manager.active:
            manager.active["state"] = state
            manager.active["message"] = message


def _run_task(manager, task: dict) -> None:
    task_id = str(task["id"])
    job_id = str(task["job_id"])
    try:
        config = AutomationConfig.model_validate(task.get("config") or {})
        directory = manager.root / job_id
        notify = lambda message: _notify(manager, "preparing", message)

        _stage(manager, task_id, "import", "running", "正在导入视频")
        _notify(manager, "preparing", "正在导入录像")
        _import_stage(manager, task, config, directory, notify)
        _stage(manager, task_id, "import", "done", "导入完成")

        if manager.read_json(directory / "job.json").get("state") == "completed":
            _stage(manager, task_id, "transcribe", "done", "沿用已完成的转写结果")
        else:
            _stage(manager, task_id, "transcribe", "running", "正在本地识别")
            _notify(manager, "transcribing", "正在本地识别并生成时间轴")
            _transcribe_stage(manager, config, directory, notify)
            _stage(manager, task_id, "transcribe", "done", "转写完成")

        if not config.translate:
            _stage(manager, task_id, "translate", "skipped", "未开启翻译")
        elif not manager.api_key:
            _stage(manager, task_id, "translate", "skipped", "未配置 DeepSeek API Key")
        elif manager.read_json(directory / "translation.json").get("state") == "completed":
            _stage(manager, task_id, "translate", "done", "沿用已完成的翻译")
        else:
            _stage(manager, task_id, "translate", "running", "正在生成中日双语字幕")
            _notify(manager, "translating", "正在生成中日双语字幕")
            try:
                translation.translate_run(directory, manager.api_key, progress=notify,
                                          model=manager.translation_model)
                _stage(manager, task_id, "translate", "done", "翻译完成")
            except Exception as exc:
                # 翻译失败不阻断后续：切片退回仅原文字幕
                _stage(manager, task_id, "translate", "failed", None, str(exc)[:300])

        if not config.generate_clips:
            _stage(manager, task_id, "clips", "skipped", "未开启自动切片")
            indices: list[int] = []
        else:
            indices = _clips_stage(manager, task_id, config, directory, notify)

        if not indices or not config.auto_publish:
            _stage(manager, task_id, "publish", "skipped",
                   "没有可投稿的切片" if not indices else "未开启自动投稿")
        else:
            _stage(manager, task_id, "publish", "running", "正在加入投稿队列")
            _notify(manager, "preparing", "正在加入投稿队列")
            try:
                publish.submit(manager, job_id, publish.PublishInput(
                    indices=indices, count=config.publish_count or len(indices)))
                _patch_task(manager, task_id, selected=indices)
                _stage(manager, task_id, "publish", "done", f"已加入投稿队列（{len(indices)} 条）")
            except Exception as exc:
                _stage(manager, task_id, "publish", "failed", None, str(exc)[:300])
                raise

        failed = [stage for stage in (_task_stages(manager, task_id)) if stage.get("state") == "failed"]
        _finish(manager, task_id, "failed" if failed else "completed",
                failed[0].get("error") if failed else None)
    except Exception as exc:
        _finish(manager, task_id, "failed", str(exc)[:500] or "自动化任务失败")


def _task_stages(manager, task_id: str) -> list[dict]:
    task = next((item for item in read_tasks(manager) if item.get("id") == task_id), None)
    return (task or {}).get("stages") or []


def _stage(manager, task_id: str, key: str, state: str, message: str | None = None,
           error: str | None = None) -> None:
    _set_stage(manager, task_id, key, state, message, error)


def _import_stage(manager, task: dict, config: AutomationConfig, directory: Path, notify) -> str:
    """导入本地视频或下载链接；返回已有的 job 状态（completed 表示可跳过转写）。"""
    kind = task.get("kind")
    if (directory / "job.json").is_file():
        job = manager.read_json(directory / "job.json")
        if job.get("state") == "completed":
            return "completed"
    adapter = LocalASR(manager.model, config.language, manager.threads, prompt=manager._asr_prompt())
    if not (directory / "job.json").is_file():
        source = Path(str(task.get("source_path"))) if task.get("source_path") else None
        if kind == "url":
            workflow.create_run(str(task.get("url")), manager.root, [], None, adapter,
                                run_id=str(task["job_id"]), progress=notify,
                                should_cancel=lambda: False)
        else:
            if source is None or not source.is_file():
                raise ValueError("源视频文件已丢失，请重新选择")
            workflow.create_run("", manager.root, [], None, adapter, run_id=str(task["job_id"]),
                                progress=notify, local_source=source, should_cancel=lambda: False)
    directory = manager.root / str(task["job_id"])
    _import_danmaku(manager, task, directory)
    if kind == "upload":
        source = Path(str(task.get("source_path") or ""))
        try:
            source.relative_to(manager.root)
            source.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
    return "imported"


def _import_danmaku(manager, task: dict, directory: Path) -> None:
    if danmaku.read_store(directory):
        return
    uploaded = task.get("danmaku_path")
    if uploaded:
        path = Path(str(uploaded))
        try:
            if path.is_file():
                source, entries = danmaku.parse(path.read_text(encoding="utf-8", errors="replace"))
                if entries:
                    danmaku.save_store(directory, source, entries, {"title": task.get("title")})
                    path.unlink(missing_ok=True)
                    return
        except (OSError, ValueError):
            pass
    recording_dir = task.get("recording_dir")
    if recording_dir:
        xml = Path(str(recording_dir)) / "danmaku.xml"
        try:
            if xml.is_file():
                entries = danmaku.parse_xml(xml.read_text(encoding="utf-8", errors="replace"))
                if entries:
                    danmaku.save_store(directory, "bilibili-live", entries,
                                       {"room_id": task.get("source_name"), "title": task.get("title")})
                    return
        except (OSError, ValueError):
            pass
    if task.get("kind") == "url" and task.get("url"):
        try:
            info, entries = danmaku_fetch.fetch(str(task["url"]))
        except Exception:
            return
        if entries:
            danmaku.save_store(directory, "bilibili", entries, {
                "url": task["url"], "title": info.get("title"), "cid": info.get("cid"),
                "owner_mid": info.get("owner_mid"), "owner_name": info.get("owner_name"),
                "fetched_at": time.time()})


def _transcribe_stage(manager, config: AutomationConfig, directory: Path, notify) -> None:
    saved = manager.read_json(directory / "job.json")
    saved_asr = saved.get("asr") or {}
    adapter = (LocalASR(Path(saved_asr["model"]), saved_asr.get("language", config.language),
                        saved_asr.get("threads", manager.threads), prompt=manager._asr_prompt())
               if saved_asr.get("model") else None)
    workflow.resume_run(directory, adapter, progress=notify, should_cancel=lambda: False)


def _read_clip_products(directory: Path) -> list[int]:
    """读取已生成且文件仍在的切片编号，供失败重试时跳过重复生成。"""
    try:
        value = json.loads((directory / "topic_clips.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(value, dict) or value.get("state") != "completed":
        return []
    result = []
    for item in value.get("items") or []:
        name = item.get("file") if isinstance(item, dict) else None
        if item.get("state") == "completed" and isinstance(name, str) and (directory / name).is_file():
            try:
                result.append(int(item["index"]))
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(result)


def _clips_stage(manager, task_id: str, config: AutomationConfig, directory: Path, notify) -> list[int]:
    if not manager.api_key:
        raise ValueError("自动切片需要先保存 DeepSeek API Key")
    existing = _read_clip_products(directory)
    if existing:
        _patch_task(manager, task_id, selected=existing)
        _stage(manager, task_id, "clips", "done", f"沿用已生成的 {len(existing)} 个切片")
        return existing
    _stage(manager, task_id, "clips", "running", "正在用 LLM 分析内容切片")
    _notify(manager, "analyzing", "正在用 LLM 分析内容切片")
    stored = topic_segments.read_store(directory)
    identity = topic_segments.current_identity(directory)
    if not stored or stored.get("state") != "completed" or stored.get("identity") != identity:
        store = topic_segments.analyze_directory(
            directory, manager.api_key, manager.translation_model,
            options=topic_segments.TopicAnalyzeOptions(max_segments=config.max_segments))
        stored = store.model_dump(mode="json")
    applied = danmaku.apply(directory, stored,
                            words=clip_words.load(manager.root / "clip_words.json"),
                            build_audio=True, vocab_root=manager.root / "streamers")
    segments = applied.get("segments") or []
    indices = _select_indices(segments, config)
    if not indices:
        media.write_json(directory / "topic_clips.json", {
            "state": "completed", "mode": "separate", "variant": config.variant, "indices": [],
            "done": 0, "total": 0, "message": "没有达到条件的切片", "error": None,
            "items": [], "combined": None, "created_at": time.time()})
        _stage(manager, task_id, "clips", "done", "没有达到条件的切片")
        return []
    variant = config.variant
    if variant != "original" and manager.read_json(directory / "translation.json").get("state") != "completed":
        variant = "original"
    if variant in {"bilingual", "zh"}:
        translation.ensure_zh_srt(directory)
        if not (directory / "subtitles.zh.srt").is_file():
            variant = "original"
    _stage(manager, task_id, "clips", "running", f"正在生成 {len(indices)} 个切片视频")
    _notify(manager, "exporting", f"正在生成 {len(indices)} 个切片视频")

    def progress(done: int, total: int, message: str) -> None:
        _stage(manager, task_id, "clips", "running", message)
        _notify(manager, "exporting", message)

    try:
        style_store = legacy_style.load_style_store(manager.root / "style.json")
        if config.style_template:
            picked_style = style_store.templates.get(config.style_template)
            if picked_style is not None:
                style_store.current = picked_style
        if config.shapes_template:
            picked_shapes = style_store.shapes_templates.get(config.shapes_template)
            if picked_shapes is not None:
                style_store.shapes = picked_shapes
        danmaku_style = (danmaku_render.DanmakuStyle(font_size=config.danmaku_font_size,
                                                     area_height=config.danmaku_area_height)
                         if config.danmaku_enabled else None)
        result = topic_video.generate(directory, segments, indices, "separate", variant,
                                      style_store,
                                      progress,
                                      danmaku_style=danmaku_style)
    except Exception:
        media.write_json(directory / "topic_clips.json", {
            "state": "failed", "mode": "separate", "variant": variant, "indices": indices,
            "done": 0, "total": len(indices), "message": "切片视频生成失败", "error": "切片视频生成失败",
            "items": [], "combined": None, "created_at": time.time()})
        raise
    items = result.get("items") or []
    completed = [int(item["index"]) for item in items
                 if item.get("state") == "completed" and item.get("file")]
    failed = [item for item in items if item.get("state") == "failed"]
    media.write_json(directory / "topic_clips.json", {
        "state": "failed" if failed and not completed else "completed",
        "mode": "separate", "variant": variant, "indices": indices,
        "done": len(items), "total": len(indices),
        "message": f"已生成 {len(completed)}/{len(indices)} 个切片",
        "error": (f"{len(failed)} 个切片生成失败" if failed else None),
        "items": items, "combined": result.get("combined"), "created_at": time.time()})
    if not completed:
        raise ValueError("切片视频全部生成失败")
    _stage(manager, task_id, "clips", "done", f"已生成 {len(completed)} 个切片")
    return completed


def _select_indices(segments: list[dict], config: AutomationConfig) -> list[int]:
    def _start(item) -> float:
        try:
            return float(item.get("start") or item.get("start_seconds") or 0)
        except (TypeError, ValueError, AttributeError):
            return 0.0

    def _duration(item) -> float:
        try:
            end = item.get("end")
            if end is None:
                end = item.get("end_seconds")
            return float(end or 0) - _start(item)
        except (TypeError, ValueError, AttributeError):
            return 0.0

    def _fits(item) -> bool:
        if _duration(item) > config.max_clip_seconds:
            return False
        overlap = item.get("song_overlap")
        return not isinstance(overlap, (int, float)) or overlap <= MAX_SONG_OVERLAP

    scored = [(index, int(item["score"])) for index, item in enumerate(segments)
              if isinstance(item, dict) and isinstance(item.get("score"), int)]
    if scored:
        candidates = [pair for pair in scored if _fits(segments[pair[0]])]
        if config.use_min_score:
            candidates = [pair for pair in candidates if pair[1] >= config.min_score]
        if config.use_top_n:
            candidates = sorted(candidates, key=lambda pair: (pair[1], -pair[0]),
                                reverse=True)[:config.top_n]
    else:
        limit = config.top_n if config.use_top_n else len(segments)
        candidates = [(index, 0) for index in range(len(segments))
                      if _fits(segments[index])][:limit]
    window = max(1, config.per_minutes) * 60
    buckets: dict[int, list[tuple[int, int]]] = {}
    for index, score in candidates:
        key = int(_start(segments[index]) // window)
        buckets.setdefault(key, []).append((index, score))
    picked: list[int] = []
    for key in sorted(buckets):
        group = sorted(buckets[key], key=lambda pair: (pair[1], -pair[0]), reverse=True)
        picked.extend(index for index, _ in group[:config.per_count])
    return sorted(picked)
