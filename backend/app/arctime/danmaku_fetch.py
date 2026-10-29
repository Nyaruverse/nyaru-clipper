"""从 B 站稿件接口自动拉取弹幕。

需要登录态：弹幕池接口对匿名请求会返回空数据或 412 风控，因此复用项目已有的
APP_BILIBILI_COOKIE_PATH（Netscape cookies.txt），未配置时依次查找 data/bilibili-cookies.txt
与仓库根目录的 bilibili-cookies.txt。

流程：BV/av 号 → x/web-interface/view 取 cid 与时长 → 三路合并拉取：
x/v1/dm/list.so（弹幕池，长视频会截断）+ x/v2/dm/web/seg.so（6 分钟分段）
+ x/v2/dm/web/history/seg.so（按日期的历史弹幕，需登录 Cookie）
→ 按「时间+发送者+文本」去重 → 写入 danmaku.json。
"""
from __future__ import annotations

import concurrent.futures
import json
import math
import os
import re
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.arctime import danmaku

SEGMENT_SECONDS = 360
MAX_SEGMENTS = 600
REQUEST_TIMEOUT = 20.0
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
REPO_ROOT = Path(__file__).resolve().parents[3]

_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_AV_RE = re.compile(r"(?:\bav|/video/av)(\d+)", re.I)


class CookieMissing(RuntimeError):
    """找不到可用的登录 Cookie。"""


class UpstreamError(RuntimeError):
    """B 站接口返回错误或风控。"""


def cookie_file() -> Path | None:
    candidates = [os.environ.get("APP_BILIBILI_COOKIE_PATH", "").strip()]
    candidates += [str(REPO_ROOT / "data" / "bilibili-cookies.txt"),
                   str(REPO_ROOT / "bilibili-cookies.txt")]
    for value in candidates:
        if value:
            path = Path(value).expanduser()
            if path.is_file():
                return path
    return None


def _json_cookie_pairs() -> list[str]:
    """cookies.txt 不存在时，从 biliup 的 cookies.json 里取 cookie_info 兜底。"""
    path = REPO_ROOT / "data" / "bilibili-cookies.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = (payload.get("cookie_info") or {}).get("cookies") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return []
    pairs: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name, value = str(item.get("name") or ""), str(item.get("value") or "")
        if name and name not in seen:
            seen.add(name)
            pairs.append(f"{name}={value}")
    return pairs


def cookie_header(required: bool = False) -> str:
    path = cookie_file()
    if path is None:
        pairs = _json_cookie_pairs()
        if pairs:
            return "; ".join(pairs)
        if not required:
            return ""
        raise CookieMissing(
            "未找到 B 站登录 Cookie。请在「内容切片与摘要」面板点「扫码登录 B站」，"
            "或把导出的 cookies.txt 放到 data/bilibili-cookies.txt（也可用 APP_BILIBILI_COOKIE_PATH 指定）。")
    pairs: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 7:
            domain, name, value = fields[0], fields[5], fields[6]
            if "bilibili" not in domain:
                continue
        elif "=" in line:
            name, _, value = line.partition("=")
        else:
            continue
        name = name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        pairs.append(f"{name}={value.strip()}")
    if not pairs:
        raise CookieMissing("Cookie 文件里没有有效的 B 站登录信息，请重新导出 cookies.txt。")
    return "; ".join(pairs)


def parse_target(url: str) -> tuple[str, str]:
    text = (url or "").strip()
    if not text:
        raise ValueError("请填写 B站视频链接或 BV 号")
    if "live.bilibili.com" in text:
        raise ValueError("直播中的弹幕需要实时录制，暂不支持自动拉取；请填写直播回放稿件的视频链接。")
    match = _BV_RE.search(text)
    if match:
        return "bvid", match.group(1)
    if re.fullmatch(r"\d+", text):
        return "aid", text
    match = _AV_RE.search(text)
    if match:
        return "aid", match.group(1)
    raise ValueError("无法识别视频链接，请填写 BV 号、av 号或 bilibili.com/video/ 链接")


def _client(cookie: str | None) -> httpx.Client:
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.bilibili.com/",
               "Origin": "https://www.bilibili.com"}
    if cookie:
        headers["Cookie"] = cookie
    return httpx.Client(timeout=REQUEST_TIMEOUT, headers=headers, follow_redirects=True)


def _check(payload: dict, action: str) -> dict:
    code = payload.get("code")
    if code == 0:
        return payload.get("data") or {}
    if code == -412:
        raise UpstreamError(f"{action}被 B站风控拦截，请稍后重试或更新 Cookie")
    if code == -101:
        raise CookieMissing(f"{action}需要登录，Cookie 已失效，请重新导出 cookies.txt")
    message = payload.get("message") or f"错误码 {code}"
    raise UpstreamError(f"{action}失败：{message}")


def resolve_video(url: str, cookie: str) -> dict:
    kind, value = parse_target(url)
    params = {"bvid": value} if kind == "bvid" else {"aid": value}
    with _client(cookie) as client:
        response = client.get("https://api.bilibili.com/x/web-interface/view", params=params)
        if response.status_code != 200:
            raise UpstreamError(f"视频信息请求失败（HTTP {response.status_code}）")
        data = _check(response.json(), "读取视频信息")
    pages = data.get("pages") or []
    if not pages:
        raise UpstreamError("该稿件没有可用的分 P 信息")
    page = pages[0]
    owner = data.get("owner") or {}
    return {
        "cid": int(page["cid"]),
        "aid": int(data.get("aid") or 0),
        "duration": float(page.get("duration") or data.get("duration") or 0),
        "title": data.get("title") or "",
        "bvid": data.get("bvid") or "",
        "owner_mid": int(owner.get("mid") or 0) or None,
        "owner_name": owner.get("name") or "",
        "pubdate": int(data.get("pubdate") or 0) or None,
    }


def _read_varint(data: bytes, pos: int, end: int) -> tuple[int, int]:
    result = shift = 0
    while pos < end:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 63:
            break
    raise ValueError("protobuf varint 越界")


def _iter_fields(data: bytes):
    pos, end = 0, len(data)
    while pos < end:
        key, pos = _read_varint(data, pos, end)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _read_varint(data, pos, end)
            yield field, wire, value
        elif wire == 2:
            length, pos = _read_varint(data, pos, end)
            yield field, wire, data[pos:pos + length]
            pos += length
        elif wire == 5:
            pos += 4
        elif wire == 1:
            pos += 8
        else:
            raise ValueError("不支持的 protobuf 字段类型")


def parse_segment(data: bytes) -> list[list]:
    """解析 DmSegMobileReply：每个 DanmakuElem 取 progress(2)、midHash(6)、content(7)。"""
    entries: list[list] = []
    for field, wire, value in _iter_fields(data):
        if field != 1 or wire != 2:
            continue
        progress = content = user = None
        for sub_field, sub_wire, sub_value in _iter_fields(value):
            if sub_field == 2 and sub_wire == 0:
                progress = sub_value
            elif sub_field == 6 and sub_wire == 2:
                user = sub_value.decode("utf-8", "replace")
            elif sub_field == 7 and sub_wire == 2:
                content = sub_value.decode("utf-8", "replace")
        if progress is None or content is None:
            continue
        text = danmaku._clean_text(content)
        if danmaku._keep(text):
            entries.append([round(progress / 1000, 3), text, user or "", None])
    return entries


def _fetch_segment(cid: int, index: int, cookie: str) -> list[list]:
    with _client(cookie) as client:
        response = client.get("https://api.bilibili.com/x/v2/dm/web/seg.so",
                              params={"type": 1, "oid": cid, "segment_index": index})
    if response.status_code != 200 or not response.content:
        return []
    try:
        return parse_segment(response.content)
    except ValueError:
        return []


def _fetch_list(cid: int, cookie: str) -> list[list]:
    with _client(cookie) as client:
        response = client.get("https://api.bilibili.com/x/v1/dm/list.so", params={"oid": cid})
    if response.status_code != 200 or not response.content:
        return []
    raw = response.content
    if not raw.lstrip().startswith(b"<"):
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            try:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error:
                return []
    return danmaku.parse_xml(raw.decode("utf-8", "replace"))


_CST = timezone(timedelta(hours=8))


def _candidate_dates(pubdate: int | None) -> list[str]:
    """历史弹幕按发送日期分页，回放弹幕集中在开播当天；取发布日前后一天兜底。"""
    if not pubdate:
        return []
    day = datetime.fromtimestamp(float(pubdate), tz=_CST).date()
    today = datetime.now(tz=_CST).date()
    return [(day + timedelta(days=delta)).isoformat()
            for delta in (-1, 0, 1) if day + timedelta(days=delta) <= today]


def _fetch_history(cid: int, date: str, cookie: str) -> list[list]:
    """按日期拉历史弹幕（需要登录 Cookie），匿名或无数据时返回空。"""
    with _client(cookie) as client:
        response = client.get("https://api.bilibili.com/x/v2/dm/web/history/seg.so",
                              params={"type": 1, "oid": cid, "date": date})
    if response.status_code != 200 or not response.content:
        return []
    if "json" in (response.headers.get("content-type") or ""):
        return []
    try:
        return parse_segment(response.content)
    except ValueError:
        return []


def fetch_entries(info: dict, cookie: str) -> list[list]:
    cid = info["cid"]
    # 弹幕有多个口径，且匿名访问会被限流/截断，三路合并去重：
    # - list.so：弹幕池 XML，长视频会静默截断（实测 2.4 小时回放只返回最新约一万条）；
    # - seg.so：按 6 分钟分段，匿名时每段很少，登录后返回完整分段；
    # - history/seg.so：按发送日期的历史弹幕，覆盖最完整，但必须登录 Cookie。
    entries = _fetch_list(cid, cookie)
    segments = min(MAX_SEGMENTS, max(1, math.ceil(info["duration"] / SEGMENT_SECONDS)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_fetch_segment, cid, index, cookie)
                   for index in range(1, segments + 1)]
        for future in futures:
            try:
                entries.extend(future.result())
            except Exception:
                continue
    if cookie:
        for date in _candidate_dates(info.get("pubdate")):
            entries.extend(_fetch_history(cid, date, cookie))
    seen: set[tuple] = set()
    unique: list[list] = []
    for item in entries:
        key = (round(float(item[0]), 1), item[2], item[1])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    unique.sort(key=lambda item: item[0])
    return unique


def fetch(url: str) -> tuple[dict, list[list]]:
    """解析链接并拉取全部弹幕，返回 (视频信息, 条目)。"""
    parse_target(url)  # 先校验链接，避免链接写错时先抱怨 Cookie
    cookie = cookie_header()
    info = resolve_video(url, cookie)
    entries = fetch_entries(info, cookie)
    if not entries:
        if not cookie:
            raise CookieMissing(
                "没有拉到弹幕。若该稿件需要登录，请在「内容切片与摘要」面板点「扫码登录 B站」，"
                "或把导出的 cookies.txt 放到 data/bilibili-cookies.txt（也可用 APP_BILIBILI_COOKIE_PATH 指定）。")
        raise UpstreamError("没有拉到弹幕，可能该稿件未开启弹幕、弹幕池为空或接口被风控")
    return info, entries
