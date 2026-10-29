from __future__ import annotations

import html
import json
import os
import re
import struct
import subprocess
import sys
import threading
import time
import traceback
import zlib
from pathlib import Path

import httpx
from websockets.sync.client import connect

from app.arctime import automation, danmaku_fetch, live_capture, live_state, media

ROOMS_NAME = "rooms.json"
POLL_INTERVAL = 20.0
DANMAKU_URL = "wss://broadcastlv.chat.bilibili.com/sub"
DANMAKU_CONF = "https://api.live.bilibili.com/room/v1/Danmu/getConf"
LIVE_INFO = "https://api.live.bilibili.com/room/v1/Room/get_info"
ANCHOR_INFO = "https://api.live.bilibili.com/live_user/v1/UserInfo/get_anchor_in_room"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ROOM_RE = re.compile(r"^(?:https?://live\.bilibili\.com/(?:blanc/)?)?([1-9][0-9]*)/?$")
HEADER = struct.Struct(">IHHII")

_rooms_lock = threading.RLock()


def room_id_of(value: str) -> str:
    text = str(value or "").strip()
    match = ROOM_RE.fullmatch(text)
    if not match:
        raise ValueError("请输入 Bilibili 数字直播间号或 https://live.bilibili.com/12345 链接")
    return match.group(1)


def room_url(room_id: str) -> str:
    return f"https://live.bilibili.com/{room_id}"


class RoomStore:
    def __init__(self, path: Path):
        self.path = path

    def read(self) -> list[dict]:
        try:
            if self.path.is_symlink():
                return []
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        rooms = value.get("rooms") if isinstance(value, dict) else None
        if not isinstance(rooms, list):
            return []
        result = []
        for row in rooms:
            if not isinstance(row, dict):
                continue
            try:
                room_id = room_id_of(str(row.get("room_id") or ""))
            except ValueError:
                continue
            result.append({
                "room_id": room_id,
                "name": str(row.get("name") or "").strip()[:60],
                "enabled": bool(row.get("enabled", True)),
                "auto_run": bool(row.get("auto_run", True)),
                "created_at": float(row.get("created_at") or 0) or time.time(),
            })
        return result

    def write(self, rooms: list[dict]) -> None:
        with _rooms_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            media.write_json(self.path, {"rooms": rooms})

    def add(self, room: str, name: str = "") -> dict:
        room_id = room_id_of(room)
        rooms = self.read()
        existing = next((item for item in rooms if item["room_id"] == room_id), None)
        if existing is not None:
            if name.strip():
                existing["name"] = name.strip()[:60]
            self.write(rooms)
            return existing
        record = {"room_id": room_id, "name": name.strip()[:60], "enabled": False,
                  "auto_run": True, "created_at": time.time()}
        rooms.append(record)
        self.write(rooms)
        return record

    def update(self, room_id: str, *, name: str | None = None, enabled: bool | None = None,
               auto_run: bool | None = None) -> dict:
        rooms = self.read()
        target = next((item for item in rooms if item["room_id"] == room_id), None)
        if target is None:
            raise KeyError(room_id)
        if name is not None:
            target["name"] = name.strip()[:60]
        if enabled is not None:
            target["enabled"] = bool(enabled)
        if auto_run is not None:
            target["auto_run"] = bool(auto_run)
        self.write(rooms)
        return target

    def remove(self, room_id: str) -> None:
        rooms = self.read()
        if not any(item["room_id"] == room_id for item in rooms):
            raise KeyError(room_id)
        self.write([item for item in rooms if item["room_id"] != room_id])


def _packet(op: int, body: bytes = b"") -> bytes:
    return HEADER.pack(HEADER.size + len(body), HEADER.size, 1, op, 1) + body


def _unpack(raw: bytes) -> list[tuple[int, bytes]]:
    result: list[tuple[int, bytes]] = []
    offset = 0
    while offset + HEADER.size <= len(raw):
        length, header, version, op, _seq = HEADER.unpack_from(raw, offset)
        if length < HEADER.size or offset + length > len(raw):
            break
        body = raw[offset + header:offset + length]
        offset += length
        if version == 2 and op not in (2, 3):
            try:
                body = zlib.decompress(body)
            except zlib.error:
                continue
            result.extend(_unpack(body))
        else:
            result.append((op, body))
    return result


def _ws_auth(room_id: str) -> tuple[str, str, int]:
    """取弹幕服务器地址、鉴权 token 与登录 uid。

    匿名连接（uid=0 / 空 token）会被服务器直接断开，因此必须带登录 Cookie；
    getDanmuInfo 接口有 -352 风控，这里用 getConf 接口取 token。
    """
    try:
        cookie = danmaku_fetch.cookie_header()
    except Exception:
        cookie = ""
    uid = 0
    match = re.search(r"DedeUserID=(\d+)", cookie)
    if match:
        uid = int(match.group(1))
    token, host = "", ""
    try:
        response = httpx.get(DANMAKU_CONF, params={"room_id": room_id},
                             headers={"User-Agent": UA, "Referer": room_url(room_id), "Cookie": cookie},
                             timeout=10.0)
        payload = response.json()
        data = payload.get("data") or {}
        if payload.get("code") == 0:
            token = str(data.get("token") or "")
            host = str(data.get("host") or "")
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    return f"wss://{host or 'broadcastlv.chat.bilibili.com'}/sub", token, uid


class DanmakuCollector:
    """直播间弹幕与 SC 采集：断线期间内容无法补录，gap 会写入 meta。"""

    def __init__(self, room_id: str, path: Path, stop: threading.Event):
        self.room_id = room_id
        self.path = path
        self.stop = stop
        self.thread: threading.Thread | None = None
        self.error: str | None = None
        self.gaps: list[list[float]] = []
        self.count = 0
        self.sc_count = 0
        self._handle = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name=f"danmaku-{self.room_id}", daemon=True)
        self.thread.start()

    def close(self, timeout: float = 15.0) -> None:
        if self.thread is not None:
            self.thread.join(timeout=timeout)

    def _write(self, row: dict) -> None:
        if self._handle is None:
            self._handle = self.path.open("a", encoding="utf-8")
        self._handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._handle.flush()

    def _run(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            for attempt in range(3):
                if self.stop.is_set():
                    break
                outage_start = None
                try:
                    target, token, uid = _ws_auth(self.room_id)
                    with connect(target, open_timeout=10, close_timeout=5, max_size=2 ** 23,
                                 additional_headers={"User-Agent": UA,
                                                     "Origin": "https://live.bilibili.com"}) as ws:
                        if outage_start is not None:
                            self.gaps.append([outage_start, time.time()])
                        ws.send(_packet(7, json.dumps({
                            "uid": uid, "roomid": int(self.room_id), "protover": 2,
                            "platform": "web", "type": 2, "key": token,
                        }).encode()))
                        while not self.stop.is_set():
                            try:
                                raw = ws.recv(timeout=30)
                            except TimeoutError:
                                ws.send(_packet(2, b"[object Object]"))
                                continue
                            except OSError:
                                raise
                            if isinstance(raw, str):
                                raw = raw.encode()
                            for op, body in _unpack(raw):
                                if op == 5:
                                    self._handle_message(body)
                except Exception:
                    if not self.stop.is_set():
                        self.error = "弹幕连接中断；断线期间的弹幕无法补录"
                    outage_start = outage_start or time.time()
                if self.stop.wait(2 ** attempt):
                    break
        finally:
            if self._handle is not None:
                self._handle.close()
                self._handle = None

    def _handle_message(self, body: bytes) -> None:
        try:
            message = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return
        if not isinstance(message, dict):
            return
        cmd = str(message.get("cmd") or "")
        if cmd.startswith("DANMU_MSG"):
            info = message.get("info") or []
            if len(info) < 3 or not isinstance(info[0], list) or not isinstance(info[2], list):
                return
            layer, user = info[0], info[2]
            text = str(info[1] or "").strip()
            if not text:
                return
            try:
                ts = float(layer[4]) / 1000 if layer[4] else time.time()
            except (TypeError, ValueError, IndexError):
                ts = time.time()
            row = {"ts": round(ts, 3), "type": "danmu", "text": text[:500],
                   "uid": user[0] if user else 0, "uname": str(user[1] if len(user) > 1 else ""),
                   "mode": layer[1] if len(layer) > 1 else 1, "color": layer[3] if len(layer) > 3 else 16777215}
            self.count += 1
            self._write(row)
        elif cmd == "SUPER_CHAT_MESSAGE":
            data = message.get("data") or {}
            if not isinstance(data, dict):
                return
            text = str(data.get("message") or "").strip()
            user = data.get("user_info") or {}
            try:
                ts = float(data.get("start_time") or data.get("time") or time.time())
            except (TypeError, ValueError):
                ts = time.time()
            row = {"ts": round(ts, 3), "type": "sc", "text": text[:500],
                   "uid": data.get("uid") or 0, "uname": str(user.get("uname") or ""),
                   "price": data.get("price") or 0,
                   "start_ts": data.get("start_time"), "end_ts": data.get("end_time")}
            self.sc_count += 1
            self._write(row)


def _session_chunks(session: Path) -> list[Path]:
    listing = session / "closed.csv"
    if not listing.is_file() or listing.is_symlink():
        return []
    text = listing.read_text(encoding="utf-8")
    text = text[:text.rfind("\n") + 1]
    result: list[Path] = []
    for line in text.splitlines():
        name = line.split(",", 1)[0].strip()
        if not re.fullmatch(r"chunk-[0-9]{5}\.(?:ts|mp4)", name):
            continue
        path = session / name
        if path.is_file() and not path.is_symlink():
            result.append(path)
    return result


def _session_start(session: Path, chunks: list[Path], durations: list[float]) -> float:
    for path in chunks:
        try:
            return path.stat().st_ctime
        except OSError:
            continue
    return time.time() - sum(durations)


def _live_info(room_id: str) -> dict:
    try:
        response = httpx.get(LIVE_INFO, params={"room_id": room_id},
                             headers={"User-Agent": UA, "Referer": room_url(room_id)}, timeout=10.0)
        data = response.json().get("data") or {}
        status = int(data.get("live_status") or 0)
        title = str(data.get("title") or "")
    except (httpx.HTTPError, ValueError, TypeError):
        return {}
    result = {"live_status": status, "title": title}
    if status == 1:
        try:
            anchor = httpx.get(ANCHOR_INFO, params={"roomid": room_id},
                               headers={"User-Agent": UA, "Referer": room_url(room_id)}, timeout=10.0)
            info = (anchor.json().get("data") or {}).get("info") or {}
            result["uname"] = str(info.get("uname") or "")
        except (httpx.HTTPError, ValueError, TypeError):
            pass
    return result


def _xml_time(value: float) -> str:
    return f"{max(0.0, value):.3f}"


def _build_xml(recordings: list[dict], entries_path: Path, out_path: Path) -> dict:
    """把按服务器时间记录的弹幕映射到合并后的视频时间轴，输出 B 站 XML。"""
    entries: list[dict] = []
    try:
        for line in entries_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                entries.append(row)
    except OSError:
        pass
    windows = [(item["start"], item["start"] + item["duration"], item["offset"]) for item in recordings]
    rows: list[tuple[float, int, str, str, int, int]] = []
    sc_rows = []
    dropped = 0
    for row in entries:
        ts = float(row.get("ts") or 0)
        placed = None
        for start, end, offset in windows:
            if start <= ts <= end:
                placed = offset + (ts - start)
                break
        if placed is None:
            dropped += 1
            continue
        if row.get("type") == "sc":
            sc_rows.append({**row, "video_time": round(placed, 3)})
            text = f"【SC ¥{row.get('price') or 0}】{row.get('text') or ''}"
            rows.append((placed, 4, text, str(row.get("uname") or ""), int(row.get("uid") or 0), 16777215))
        else:
            rows.append((placed, int(row.get("mode") or 1), str(row.get("text") or ""),
                         str(row.get("uname") or ""), int(row.get("uid") or 0), int(row.get("color") or 16777215)))
    rows.sort(key=lambda item: item[0])
    body = []
    for index, (at, mode, text, uname, uid, color) in enumerate(rows, start=1):
        body.append(f'<d p="{_xml_time(at)},{mode},25,{color},0,0,{uid},{index}">{html.escape(text)}</d>')
    out_path.write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<i>\n  <chatserver>chat.bilibili.com</chatserver>\n"
                        f"  <chatid>0</chatid>\n  <mission>0</mission>\n  <maxlimit>1000000</maxlimit>\n"
                        "  <source>k-v</source>\n  <d>\n    " + "\n    ".join(body) + "\n  </d>\n</i>\n",
                        encoding="utf-8")
    return {"count": len(rows), "sc": len(sc_rows), "dropped": dropped,
            "users": len({item[3] for item in rows if item[3]}), "sc_rows": sc_rows}


class RecorderService:
    def __init__(self, manager):
        self.manager = manager
        self.root = manager.root / "recorder"
        self.store = RoomStore(self.root / ROOMS_NAME)
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.live: dict[str, dict] = {}
        self.active: str | None = None
        self.sessions: dict[str, dict] = {}

    # ---- 生命周期 ----

    def start(self) -> None:
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                return
            self.thread = threading.Thread(target=self._loop, name="recorder-service", daemon=True)
            self.thread.start()
        self._recover_incomplete()

    def close(self) -> None:
        self.stop.set()

    # ---- 录播路径设置 ----

    def _read_settings(self) -> dict:
        path = self.root / "settings.json"
        try:
            if path.is_symlink():
                return {}
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @property
    def recordings_root(self) -> Path:
        custom = self._read_settings().get("record_path")
        if isinstance(custom, str) and custom.strip():
            return Path(custom)
        return self.manager.root / "recordings"

    def settings(self) -> dict:
        default = self.manager.root / "recordings"
        custom = self._read_settings().get("record_path")
        return {"record_path": str(self.recordings_root), "default_record_path": str(default),
                "custom": isinstance(custom, str) and bool(custom.strip())}

    def save_settings(self, record_path: str | None) -> dict:
        text = (record_path or "").strip()
        if not text:
            media.write_json(self.root / "settings.json", {"record_path": None})
            return self.settings()
        path = Path(text).expanduser()
        if not path.is_absolute():
            raise ValueError("请填写绝对路径，例如 D:\\recordings")
        if path.exists() and not path.is_dir():
            raise ValueError("该路径已存在且不是文件夹")
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"无法创建文件夹：{exc}") from None
        media.write_json(self.root / "settings.json", {"record_path": str(path)})
        return self.settings()

    def open_folder(self) -> None:
        path = self.recordings_root
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["/usr/bin/open", str(path)], check=False, timeout=15)
        else:
            subprocess.run(["xdg-open", str(path)], check=False, timeout=15)

    # ---- 对外查询 ----

    def status(self) -> dict:
        rooms = self.store.read()
        with self.lock:
            live = {key: dict(value) for key, value in self.live.items()}
            sessions = {key: dict(value) for key, value in self.sessions.items()}
            active = self.active
        result = []
        for room in rooms:
            info = live.get(room["room_id"], {})
            session = sessions.get(room["room_id"], {})
            result.append({**room, "url": room_url(room["room_id"]),
                           "live_status": info.get("live_status"), "title": info.get("title") or "",
                           "uname": info.get("uname") or "", "recording": bool(session),
                           "stopping": bool(session.get("stopping")),
                           "started_at": session.get("started_at"), "current_dir": session.get("directory")})
        return {"rooms": result, "recordings": self.recordings(), "active": active,
                "poll_interval": POLL_INTERVAL,
                "record_path": str(self.recordings_root),
                "default_record_path": str(self.manager.root / "recordings")}

    def recordings(self) -> list[dict]:
        items: list[dict] = []
        seen: set[str] = set()
        roots = [self.manager.root / "recordings"]
        if self.recordings_root != roots[0]:
            roots.append(self.recordings_root)
        for root in roots:
            if not root.is_dir():
                continue
            for meta in root.glob("*/*/meta.json"):
                directory = str(meta.parent)
                if directory in seen:
                    continue
                try:
                    value = json.loads(meta.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(value, dict) and value.get("room_id"):
                    seen.add(directory)
                    value["directory"] = directory
                    items.append(value)
        items.sort(key=lambda item: float(item.get("started_at") or 0), reverse=True)
        return items[:60]

    # ---- 房间 CRUD ----

    def add_room(self, room: str, name: str = "") -> dict:
        record = self.store.add(room, name)
        self.store_reload()
        return record

    def update_room(self, room_id: str, **changes) -> dict:
        record = self.store.update(room_id_of(room_id), **changes)
        return record

    def remove_room(self, room_id: str) -> None:
        room_id = room_id_of(room_id)
        with self.lock:
            if self.active == room_id:
                raise RuntimeError("该直播间正在录制，请等录制结束或先关闭自动录制")
        self.store.remove(room_id)
        with self.lock:
            self.live.pop(room_id, None)

    def store_reload(self) -> None:
        # 仅用于让下一次轮询读取最新配置，rooms.json 已在 add/update 时写入
        pass

    # ---- 手动控制 ----

    def start_recording(self, room_id: str) -> dict:
        room_id = room_id_of(room_id)
        room = next((item for item in self.store.read() if item["room_id"] == room_id), None)
        if room is None:
            raise KeyError(room_id)
        info = _live_info(room_id)
        if info:
            with self.lock:
                self.live[room_id] = info
        if not info or info.get("live_status") != 1:
            raise RuntimeError("直播间当前未开播，无法开始录制")
        with self.lock:
            if room_id in self.sessions:
                raise RuntimeError("该直播间正在录制中")
            if self.active is not None:
                raise RuntimeError("另一个直播间正在录制，请等其结束")
        self._start_session(room, info)
        return {"ok": True}

    def stop_recording(self, room_id: str) -> dict:
        room_id = room_id_of(room_id)
        with self.lock:
            session = self.sessions.get(room_id)
        if session is None:
            raise RuntimeError("该直播间未在录制")
        self._request_stop(room_id)
        return {"ok": True}

    # ---- 后台轮询 ----

    def _loop(self) -> None:
        while True:
            try:
                self._poll()
            except Exception:
                pass
            if self.stop.wait(POLL_INTERVAL):
                return

    def _poll(self) -> None:
        rooms = self.store.read()
        for room in rooms:
            room_id = room["room_id"]
            info = _live_info(room_id)
            if info:
                with self.lock:
                    self.live[room_id] = info
            status = info.get("live_status")
            with self.lock:
                session = self.sessions.get(room_id)
                active = self.active
            if status == 1 and room["enabled"]:
                if session is None and active is None:
                    self._start_session(room, info)
            elif status == 0 and session is not None:
                self._request_stop(room_id)

    def _recover_incomplete(self) -> None:
        """启动时收尾遗留的录制目录（有分块但没有 meta.json），例如上次停止异常时。"""
        rooms = {item["room_id"]: item for item in self.store.read()}
        roots = [self.manager.root / "recordings"]
        if self.recordings_root != roots[0]:
            roots.append(self.recordings_root)
        for root in roots:
            if not root.is_dir():
                continue
            for folder in root.iterdir():
                if not folder.is_dir():
                    continue
                match = re.search(r"(\d+)$", folder.name)
                if not match:
                    continue
                room_id = match.group(1)
                room = rooms.get(room_id) or {"room_id": room_id, "auto_run": False}
                for directory in folder.iterdir():
                    if not directory.is_dir() or (directory / "meta.json").is_file():
                        continue
                    if not list(directory.glob("capture-*/closed.csv")) and not (directory / "danmaku.jsonl").is_file():
                        continue
                    session = {"directory": directory, "started_at": directory.stat().st_mtime,
                               "title": "", "name": room.get("name") or "",
                               "auto_run": bool(room.get("auto_run"))}
                    try:
                        self._finalize(room_id, session, None, None)
                    except Exception:
                        traceback.print_exc()

    def _start_session(self, room: dict, info: dict) -> None:
        room_id = room["room_id"]
        stamp = time.strftime("%Y%m%d-%H%M%S")
        uname = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", (info.get("uname") or "").strip())[:24].strip(" ._")
        folder = f"{uname}_{room_id}" if uname else room_id
        directory = self.recordings_root / folder / stamp
        try:
            directory.mkdir(parents=True, exist_ok=False)
        except OSError:
            directory = self.recordings_root / folder / f"{stamp}-{int(time.time() % 1000)}"
            directory.mkdir(parents=True, exist_ok=True)
        stop = threading.Event()
        session = {"directory": directory, "started_at": time.time(), "stop": stop,
                   "title": info.get("title") or "", "name": room.get("name") or info.get("uname") or "",
                   "auto_run": bool(room.get("auto_run", True))}
        with self.lock:
            if self.active is not None:
                return
            self.active = room_id
            self.sessions[room_id] = {key: session[key] for key in ("directory", "started_at", "title", "name")}
        thread = threading.Thread(target=self._record, args=(room_id, session),
                                  name=f"record-{room_id}", daemon=True)
        thread.start()

    def _request_stop(self, room_id: str) -> None:
        with self.lock:
            session = self.sessions.get(room_id)
            if session is not None:
                session["stopping"] = True
            event = self._session_events.get(room_id)
        if session is not None and event is not None:
            event.set()

    @property
    def _session_events(self) -> dict:
        return self.__dict__.setdefault("_stops", {})

    def _record(self, room_id: str, session: dict) -> None:
        directory: Path = session["directory"]
        stop: threading.Event = session["stop"]
        self._session_events[room_id] = stop
        started = time.time()
        capture = None
        collector = None
        error = None
        try:
            capture = live_capture.LiveCapture(room_url(room_id), directory, stop)
            collector = DanmakuCollector(room_id, directory / "danmaku.jsonl", stop)
            collector.start()
            for _chunk in capture.chunks():
                pass
            capture.close()
        except Exception as exc:
            error = str(exc) or "录制失败"
        finally:
            stop.set()
            if collector is not None:
                collector.close()
            try:
                self._finalize(room_id, session, collector, error)
            except Exception as exc:
                self._write_meta(directory, {"room_id": room_id, "name": session.get("name"),
                                             "title": session.get("title"), "started_at": started,
                                             "ended_at": time.time(), "state": "failed",
                                             "error": str(exc)[:300], "sessions": []})
            with self.lock:
                self.sessions.pop(room_id, None)
                self.active = None
                self._session_events.pop(room_id, None)

    def _finalize(self, room_id: str, session: dict, collector: DanmakuCollector | None,
                  error: str | None) -> None:
        directory: Path = session["directory"]
        sessions = sorted([item for item in directory.glob("capture-*") if item.is_dir()])
        plan: list[dict] = []
        total = 0.0
        for item in sessions:
            chunks = _session_chunks(item)
            durations = []
            for chunk in chunks:
                durations.append(media.probe_video(chunk))
            duration = sum(durations)
            if not duration:
                continue
            plan.append({"session": item.name, "start": _session_start(item, chunks, durations),
                         "duration": duration, "offset": total, "chunks": chunks,
                         "durations": durations})
            total += duration
        meta = {"room_id": room_id, "name": session.get("name"), "title": session.get("title"),
                "started_at": session.get("started_at"), "ended_at": time.time(),
                "duration": round(total, 3), "sessions": len(plan),
                "danmaku_count": collector.count if collector else 0,
                "sc_count": collector.sc_count if collector else 0,
                "danmaku_gaps": collector.gaps if collector else [],
                "danmaku_error": collector.error if collector else None,
                "record_error": error, "state": "recorded", "merged": False}
        if not plan:
            if collector is not None:
                meta["danmaku_xml"] = self._xml_meta(_build_xml([], directory / "danmaku.jsonl",
                                                                directory / "danmaku.xml"))
            self._write_meta(directory, meta)
            return
        chunks = [{"path": str(chunk.relative_to(directory)), "duration": duration}
                  for item in plan for chunk, duration in zip(item["chunks"], item["durations"])]
        target = directory / "recording.mp4"
        try:
            live_state.concatenate(directory, chunks, target)
            meta.update(merged=True, video="recording.mp4")
        except ValueError as exc:
            meta.update(merged=False, merge_error=str(exc)[:300])
        xml_meta = _build_xml([{"start": item["start"], "duration": item["duration"], "offset": item["offset"]}
                               for item in plan], directory / "danmaku.jsonl", directory / "danmaku.xml")
        try:
            media.write_json(directory / "danmaku-sc.json", {"items": xml_meta.pop("sc_rows", [])})
        except OSError:
            pass
        meta["danmaku_xml"] = self._xml_meta(xml_meta)
        self._write_meta(directory, meta)
        if meta.get("merged") and session.get("auto_run"):
            try:
                automation.enqueue(self.manager, kind="recording", title=meta.get("title") or meta.get("name") or room_id,
                                   source_path=target, source_name=target.name, recording_dir=directory)
                meta["automation"] = "queued"
            except Exception as exc:
                meta["automation"] = str(exc)[:300]
            self._write_meta(directory, meta)
        if meta.get("merged"):
            for item in sessions:
                try:
                    for path in sorted(item.glob("chunk-*")):
                        path.unlink(missing_ok=True)
                    (item / "closed.csv").unlink(missing_ok=True)
                    item.rmdir()
                except OSError:
                    pass

    @staticmethod
    def _xml_meta(result: dict) -> dict:
        return {"count": result.get("count", 0), "sc": result.get("sc", 0), "dropped": result.get("dropped", 0),
                "users": result.get("users", 0), "file": "danmaku.xml"}

    @staticmethod
    def _write_meta(directory: Path, meta: dict) -> None:
        try:
            media.write_json(directory / "meta.json", meta)
        except OSError:
            pass
