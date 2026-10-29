"""B 站自动投稿：调用 biliup CLI 把切片视频批量投到 B 站。

- 凭据：data/bilibili-cookies.json，由扫码登录时用网页 Cookie 换取 TV token 生成；
- 投稿信息（分区/标签/简介/动态）存 data/publish_defaults.json，跨切片复用，
  对应 B 站投稿页的「一键填写」；
- 队列与状态存 data/publish.json：提交后立即上传，第一条直接发布，其余顺延到
  4 小时后交给 B站自带定时发布（--dtime，B站要求距提交大于 4 小时）；
  未填时间段时每条间隔 2 小时，填了时间段则按（小时数 ÷ 投稿数量）± 10 分钟排间隔；
  只投自制（--copyright 1），不使用转载来源。
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from app.arctime import bilibili_auth, media

STORE_NAME = "publish.json"
DEFAULTS_NAME = "publish_defaults.json"
ZONES_NAME = "publish_zones.json"
REPO_ROOT = Path(__file__).resolve().parents[3]
# 队列里保留的条目上限（含历史成功记录）
MAX_ITEMS = 300
UPLOAD_TIMEOUT = 3600.0
WORKER_INTERVAL = 15.0
# 排期至少留出的准备时间，避免「点了立即投稿」还要等下一轮轮询
MIN_DELAY = 15.0
# B站自带定时投稿要求距离提交大于 4 小时，多留 15 分钟余量
DTIME_MIN_AHEAD = 4 * 3600 + 900
# 多条投稿顺延到 4 小时后，未填时间段时彼此的间隔（2 小时）
DTIME_STAGGER = 2 * 3600.0
# 填了时间段时，按（小时数 ÷ 投稿数量）计算间隔，并做 ±10 分钟随机浮动
DTIME_JITTER = 600.0
ZONES_TTL = 7 * 24 * 3600
ZONES_URL = "https://member.bilibili.com/x/vupre/web/archive/pre"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
# 拿不到在线分区时的兜底列表（只列已核对过 id 的常用大区与子分区）
FALLBACK_ZONES = [
    {"id": 160, "name": "生活", "children": [
        {"id": 21, "name": "日常"}, {"id": 138, "name": "搞笑"}, {"id": 250, "name": "出行"},
        {"id": 251, "name": "三农"}, {"id": 239, "name": "家居房产"}, {"id": 161, "name": "手工"},
        {"id": 162, "name": "绘画"}]},
    {"id": 5, "name": "娱乐", "children": [
        {"id": 241, "name": "娱乐杂谈"}, {"id": 262, "name": "CP安利"}, {"id": 263, "name": "颜值安利"},
        {"id": 264, "name": "娱乐资讯"}, {"id": 137, "name": "明星综合"}, {"id": 71, "name": "综艺"}]},
    {"id": 4, "name": "游戏", "children": [
        {"id": 17, "name": "单机游戏"}, {"id": 65, "name": "网络游戏"}, {"id": 172, "name": "手机游戏"},
        {"id": 171, "name": "电子竞技"}, {"id": 173, "name": "桌游棋牌"}, {"id": 136, "name": "音游"}]},
]
_BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class PublishDefaults(BaseModel):
    """跨切片复用的投稿信息（标题与封面仍随切片变化）。"""

    tid: int = Field(default=21, ge=1, le=10000)
    tid_v2: int | None = Field(default=None, ge=1, le=100000)
    tags: str = Field(default="虚拟主播,切片", max_length=200)
    desc: str = Field(default="", max_length=2000)
    dynamic: str = Field(default="", max_length=2000)
    submit: Literal["app", "web", "b-cut-android"] = "web"
    line: str = Field(default="", max_length=32)


class PublishInput(BaseModel):
    """一次投稿请求：选中的切片、投稿数量与随机时间段（epoch 秒，留空为立即投稿）。"""

    indices: list[int] = Field(min_length=1, max_length=100)
    count: int = Field(default=1, ge=1, le=100)
    start_ts: int | None = None
    end_ts: int | None = None


def locate_biliup() -> Path | None:
    """按环境变量 → 用户目录 → 仓库 tools → PATH 的顺序查找 biliup 可执行文件。"""
    binary = "biliup.exe" if os.name == "nt" else "biliup"
    candidates: list[Path] = []
    env = os.environ.get("APP_BILIUP_PATH", "").strip()
    if env:
        candidates.append(Path(env).expanduser())
    user_root = Path.home() / ".nyaru-clipper" / "tools" / "biliup"
    for root in (user_root, REPO_ROOT / "tools" / "biliup"):
        if root.is_dir():
            found = [path for path in root.rglob(binary) if path.is_file()]
            found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            candidates.extend(found)
    for path in candidates:
        if path.is_file():
            return path
    resolved = shutil.which("biliup")
    return Path(resolved) if resolved else None


def read_defaults(manager) -> PublishDefaults:
    path = manager.root / DEFAULTS_NAME
    try:
        return PublishDefaults.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return PublishDefaults()


def save_defaults(manager, defaults: PublishDefaults) -> PublishDefaults:
    media.write_json(manager.root / DEFAULTS_NAME, defaults.model_dump(mode="json"))
    return defaults


def read_store(manager) -> dict:
    path = manager.root / STORE_NAME
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": [], "updated_at": None}
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        return {"items": [], "updated_at": None}
    return value


def _write(manager, store: dict) -> None:
    store["updated_at"] = time.time()
    store["items"] = store["items"][-MAX_ITEMS:]
    media.write_json(manager.root / STORE_NAME, store)


def credential_ready() -> bool:
    return bilibili_auth.managed_json_path().is_file()


def lock_dir() -> Path:
    """biliup 的账号级上传锁目录（与它的 dirs::data_local_dir() 解析结果一致）。"""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "biliup" / "locks"


def ensure_lock_dir() -> Path:
    """提前创建 biliup 上传锁目录。

    biliup 1.3.x 每次上传前都会在 %LOCALAPPDATA%\\biliup\\locks 建账号级互斥锁，
    目录建不出来就直接报 “Failed to create upload lock: 拒绝访问 (os error 5)”。
    先由本程序把目录建好（并给出可操作的提示），避免上传在半路失败。
    """
    path = lock_dir()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"无法创建 biliup 上传锁目录 {path}：{exc}。"
            "请检查该目录的读写权限，或把 biliup 加入杀毒软件/安全软件的白名单后重试") from exc
    return path


def _fetch_zones() -> list[dict]:
    """用当前登录 Cookie 从 B站投稿页接口取最新分区树（只保留可选子分区）。"""
    cookies = bilibili_auth.cookie_dict()
    if not cookies:
        raise RuntimeError("尚未登录 B站，无法获取分区")
    response = httpx.get(ZONES_URL, headers={"User-Agent": _UA,
                                             "Referer": "https://member.bilibili.com/platform/upload/video/frame"},
                         cookies=cookies, timeout=20.0)
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(str(payload.get("message") or payload.get("code") or "获取分区失败"))
    items = []
    for zone in (payload.get("data") or {}).get("typelist") or []:
        children = [{"id": int(child["id"]), "name": str(child.get("name") or "")}
                    for child in zone.get("children") or []
                    if child.get("show", True) and isinstance(child.get("id"), int)]
        if children:
            items.append({"id": int(zone["id"]), "name": str(zone.get("name") or ""), "children": children})
    if not items:
        raise RuntimeError("分区列表为空")
    return items


def zones(manager) -> dict:
    """分区列表：在线获取后缓存 7 天；失败时退回缓存或内置常用分区。"""
    path = manager.root / ZONES_NAME
    cached = None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and isinstance(loaded.get("items"), list):
            cached = loaded
    except (OSError, json.JSONDecodeError):
        cached = None
    now = time.time()
    if cached and now - float(cached.get("updated_at") or 0) < ZONES_TTL:
        return {"items": cached["items"], "updated_at": cached.get("updated_at"), "stale": False}
    try:
        items = _fetch_zones()
        media.write_json(path, {"items": items, "updated_at": now})
        return {"items": items, "updated_at": now, "stale": False}
    except Exception:
        if cached:
            return {"items": cached["items"], "updated_at": cached.get("updated_at"), "stale": True}
        return {"items": FALLBACK_ZONES, "updated_at": None, "stale": True}


def status(manager) -> dict:
    """投稿总览：队列、工具与凭据是否就绪。"""
    ensure_worker(manager)
    store = read_store(manager)
    return {"items": store["items"], "updated_at": store.get("updated_at"),
            "biliup_ready": locate_biliup() is not None, "credential_ready": credential_ready()}


def _read_topic_clips(directory: Path) -> dict:
    try:
        value = json.loads((directory / "topic_clips.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": []}
    return value if isinstance(value, dict) else {"items": []}


def _schedule(count: int, start_ts: float | None, end_ts: float | None,
              now: float) -> list[tuple[float, bool]]:
    """排期：第 1 条立即发布，其余顺延到 4 小时后交给 B站定时。

    - 未填时间段：其余每条间隔 2 小时；
    - 填了时间段：间隔 = 时间段小时数 ÷ 投稿数量 ±10 分钟随机浮动，
      其余条目从时间段开始（不足 4 小时则从 4 小时余量处）依次排开。
    """
    floor = now + DTIME_MIN_AHEAD
    window = start_ts is not None or end_ts is not None
    if window and (start_ts is None or end_ts is None):
        raise ValueError("请同时填写时间段的开始与结束")
    if window and float(end_ts) <= float(start_ts):
        raise ValueError("结束时间必须晚于开始时间")
    if count == 1:
        if not window:
            return [(now + MIN_DELAY, False)]
        start, end = float(start_ts), float(end_ts)
        if end <= floor:
            # 单条且时间不足 4 小时：B站不接受定时，改为立刻投稿
            return [(now + MIN_DELAY, False)]
        low = max(start, floor)
        if end - low < 60:
            raise ValueError("时间段太短，请把结束时间再往后延一些")
        return [(random.uniform(low, end), True)]
    if window:
        span = float(end_ts) - float(start_ts)
        interval = span / count
        if interval < DTIME_JITTER:
            raise ValueError(f"时间段太短：{count} 条投稿建议至少留出 {count * 10} 分钟")
        cursor = max(float(start_ts), floor)
        jitter = DTIME_JITTER
    else:
        interval = DTIME_STAGGER
        cursor = floor
        jitter = 0.0
    plan = [(now + MIN_DELAY, False)]
    for _ in range(count - 1):
        plan.append((cursor, True))
        cursor += max(DTIME_JITTER, interval + random.uniform(-jitter, jitter))
    return plan


def submit(manager, job_id: str, payload: PublishInput) -> dict:
    """把选中的切片加入投稿队列：提交时立即上传，第一条直接发布，其余交给 B站定时发布。"""
    directory = manager.directory(job_id)
    if not (directory / "job.json").is_file():
        raise ValueError("任务不存在")
    clips = {item["index"]: item for item in _read_topic_clips(directory).get("items", [])
             if isinstance(item, dict) and item.get("state") == "completed" and item.get("file")}
    try:
        segments = json.loads((directory / "topic_segments.json").read_text(encoding="utf-8")).get("segments", [])
    except (OSError, json.JSONDecodeError):
        segments = []
    segment_by_index = {int(segment["index"]): segment for segment in segments
                        if isinstance(segment, dict) and isinstance(segment.get("index"), int)}
    store = read_store(manager)
    busy = {(item.get("job_id"), item.get("index")) for item in store["items"]
            if item.get("state") in {"scheduled", "uploading", "success"}}
    picked = [index for index in dict.fromkeys(payload.indices)
              if index in clips and (job_id, index) not in busy]
    if not picked:
        raise ValueError("所选切片都已在投稿队列或已投稿；请先生成新的切片视频")
    picked = picked[:payload.count]
    plan = _schedule(len(picked), payload.start_ts, payload.end_ts, time.time())
    for index, (scheduled_at, remote) in zip(picked, plan):
        item = clips[index]
        segment = segment_by_index.get(index, {})
        cover = str(segment.get("cover") or "")
        title = str(segment.get("post_title") or "").strip() or Path(str(item["file"])).stem
        # dtime = 上传后交给 B站定时发布；now = 上传后立即发布
        delivery = "dtime" if remote else "now"
        store["items"].append({
            "id": f"{job_id}-{index}-{int(scheduled_at)}",
            "job_id": job_id, "index": index, "title": title,
            "file": str(item["file"]), "cover": cover or None,
            "state": "scheduled", "scheduled_at": scheduled_at, "delivery": delivery,
            "created_at": time.time(), "started_at": None, "finished_at": None,
            "bvid": None, "error": None,
        })
    with manager.lock:
        _write(manager, store)
    ensure_worker(manager)
    return status(manager)


def remove_item(manager, item_id: str) -> dict:
    """删除队列条目（历史记录或未开始的排期）；正在上传的条目不允许删除。"""
    with manager.lock:
        store = read_store(manager)
        target = next((item for item in store["items"] if item.get("id") == item_id), None)
        if target is None:
            raise KeyError(item_id)
        if target.get("state") == "uploading":
            raise RuntimeError("该条目正在上传中，无法删除；请等上传结束或失败后再试")
        store["items"] = [item for item in store["items"] if item.get("id") != item_id]
        _write(manager, store)
    return status(manager)


def ensure_worker(manager) -> None:
    """惰性启动后台排期线程：应用重启后首次访问投稿接口时自动续跑。"""
    with manager.lock:
        thread = getattr(manager, "publish_thread", None)
        if thread is not None and thread.is_alive():
            return
        thread = threading.Thread(target=_loop, args=(manager,), daemon=True, name="publish-scheduler")
        manager.publish_thread = thread
    thread.start()


def _loop(manager) -> None:
    while True:
        try:
            process_due(manager)
        except Exception:
            pass
        time.sleep(WORKER_INTERVAL)


def process_due(manager) -> None:
    while True:
        item = _claim_next(manager)
        if item is None:
            return
        _upload(manager, item)


def _claim_next(manager) -> dict | None:
    now = time.time()
    with manager.lock:
        store = read_store(manager)
        changed = False
        for item in store["items"]:
            # 上次运行被中断的上传无法确认结果，标记失败让用户复核后重投
            if item.get("state") == "uploading":
                item["state"] = "failed"
                item["error"] = "上传中断（应用已重启），请确认 B 站稿件列表后重新投稿"
                changed = True
        for item in store["items"]:
            if item.get("state") != "scheduled":
                continue
            # B站自带定时的条目在提交时立刻上传，到点由 B站发布；本地排期要等到点
            if item.get("delivery") != "dtime" and float(item.get("scheduled_at") or 0) > now:
                continue
            item["state"] = "uploading"
            item["started_at"] = now
            item["error"] = None
            _write(manager, store)
            return dict(item)
        if changed:
            _write(manager, store)
    return None


def _command(manager, item: dict, defaults: PublishDefaults, biliup: Path) -> list[str]:
    directory = manager.directory(str(item["job_id"]))
    video = directory / str(item["file"])
    fields = [str(biliup), "-u", str(bilibili_auth.ensure_upload_credentials()),
              "upload", str(video), "--submit", defaults.submit,
              "--copyright", "1", "--title", str(item["title"]),
              "--tid", str(defaults.tid)]
    if defaults.tid_v2:
        fields += ["--tid-v2", str(defaults.tid_v2)]
    cover = str(item.get("cover") or "")
    if cover and (directory / cover).is_file():
        fields += ["--cover", str(directory / cover)]
    tags = ",".join(part.strip() for part in defaults.tags.split(",") if part.strip())
    if tags:
        fields += ["--tag", tags]
    desc = defaults.desc.replace("{title}", str(item["title"])).strip()
    if desc:
        fields += ["--desc", desc]
    if defaults.dynamic.strip():
        fields += ["--dynamic", defaults.dynamic.strip()]
    if defaults.line.strip():
        fields += ["--line", defaults.line.strip()]
    if item.get("delivery") == "dtime":
        fields += ["--dtime", str(int(item["scheduled_at"]))]
    return fields


def _upload(manager, item: dict) -> None:
    state, error, bvid = "success", None, None
    try:
        biliup = locate_biliup()
        if biliup is None:
            raise RuntimeError("未找到 biliup 可执行文件，请把它放到 tools/biliup 或设置 APP_BILIUP_PATH")
        video = manager.directory(str(item["job_id"])) / str(item["file"])
        if not video.is_file():
            raise RuntimeError("切片视频文件不存在，请重新生成")
        defaults = read_defaults(manager)
        ensure_lock_dir()
        result = media.run_managed(_command(manager, item, defaults, biliup),
                                   timeout=UPLOAD_TIMEOUT, text=True)
        output = _ANSI_RE.sub("", f"{result.stdout or ''}\n{result.stderr or ''}")
        if result.returncode != 0:
            raise RuntimeError(_tail(output) or f"biliup 退出码 {result.returncode}")
        match = _BV_RE.search(output)
        bvid = match.group(0) if match else None
    except Exception as exc:
        state, error = "failed", str(exc)[:300]
    with manager.lock:
        store = read_store(manager)
        for row in store["items"]:
            if row.get("id") == item.get("id"):
                row.update(state=state, error=error, bvid=bvid,
                           finished_at=time.time())
                break
        _write(manager, store)


def _tail(output: str, limit: int = 300) -> str:
    lines = [line.strip() for line in output.strip().splitlines() if line.strip()]
    return " | ".join(lines[-3:])[:limit]
