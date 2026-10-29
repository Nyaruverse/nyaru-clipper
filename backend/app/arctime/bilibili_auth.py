"""B 站扫码登录：生成登录二维码、轮询扫码状态、保存 Cookie。

B 站的历史弹幕接口必须登录才能返回数据，匿名只拿得到「当前弹幕池」的
有限条目（长回放约一万条上限）。这里走官方 passport 扫码流程：

1. `qrcode/generate` 拿到登录 URL 与 qrcode_key，前端展示二维码；
2. 用户用手机 B站 App 扫码并确认；
3. `qrcode/poll` 轮询到 code=0，响应头的 Set-Cookie 就是登录态；
4. 按 Netscape 格式写入 data/bilibili-cookies.txt，供 danmaku_fetch 复用。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
import segno

from app.arctime import danmaku_fetch

GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
COOKIE_NAME = "bilibili-cookies.txt"
# biliup（投稿工具）读取的登录凭据格式，由网页 Cookie 换取 TV 登录 token 生成
COOKIE_JSON_NAME = "bilibili-cookies.json"
# 二维码约 3 分钟过期，提前一点提示用户刷新
QR_TTL = 170

# TV 登录（BiliTV）：投稿工具 biliup 需要 access_token，网页 Cookie 没有，扫码后一并生成
_TV_APP_KEY = "4409e2ce8ffd12b8"
_TV_APPSEC = "59b43e04ad6965f34319062b478f83dd"
_TV_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:38.0) Gecko/20100101 Firefox/38.0 Iceweasel/38.2.1 BiliApp"
_TV_AUTH_URL = "https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
_TV_POLL_URL = "https://passport.bilibili.com/x/passport-tv-login/qrcode/poll"

# poll 返回的业务码：0 成功，86101 未扫码，86090 已扫码待确认，86038 已过期
_STATES = {0: "success", 86101: "waiting", 86090: "scanned", 86038: "expired"}


class LoginError(RuntimeError):
    """扫码登录流程中的可预期错误。"""


def _expiry() -> int:
    return int(time.time()) + 30 * 24 * 3600


def managed_path() -> Path:
    """扫码登录固定写入 data/bilibili-cookies.txt（环境变量只影响读取优先级）。"""
    return danmaku_fetch.REPO_ROOT / "data" / COOKIE_NAME


def managed_json_path() -> Path:
    """投稿工具 biliup 读取的凭据文件（含 access_token）。"""
    return danmaku_fetch.REPO_ROOT / "data" / COOKIE_JSON_NAME


def qr_code() -> dict:
    with danmaku_fetch._client("") as client:
        response = client.get(GENERATE_URL)
        if response.status_code != 200:
            raise LoginError(f"二维码生成失败（HTTP {response.status_code}）")
        data = danmaku_fetch._check(response.json(), "生成登录二维码")
    url = str(data.get("url") or "")
    key = str(data.get("qrcode_key") or "")
    if not url or not key:
        raise LoginError("二维码信息不完整，请重试")
    return {"key": key, "url": url, "image": segno.make(url, error="m").svg_data_uri(),
            "expires_in": QR_TTL}


def poll(key: str) -> dict:
    with danmaku_fetch._client("") as client:
        response = client.get(POLL_URL, params={"qrcode_key": key})
        if response.status_code != 200:
            raise LoginError(f"扫码状态查询失败（HTTP {response.status_code}）")
        data = danmaku_fetch._check(response.json(), "查询扫码状态")
        state = _STATES.get(int(data.get("code") or 0), "waiting")
        if state != "success":
            return {"state": state, "message": str(data.get("message") or "")}
        cookies = {cookie.name: cookie.value for cookie in response.cookies.jar
                   if "bilibili" in (cookie.domain or "")}
        if not cookies.get("SESSDATA"):
            raise LoginError("登录成功但没有拿到 SESSDATA，请重试")
        _write_netscape(cookies)
        status = login_status()
        return {"state": "success", "message": "登录成功", "name": status.get("name")}


def _write_netscape(cookies: dict[str, str]) -> None:
    path = managed_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    expiry = _expiry()
    lines = ["# Netscape HTTP Cookie File", "# 由 Trae 扫码登录生成，删除即可退出登录", ""]
    for name, value in cookies.items():
        lines.append(f".bilibili.com\tTRUE\t/\tFALSE\t{expiry}\t{name}\t{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def cookie_dict() -> dict[str, str]:
    """读取扫码登录生成的 Netscape Cookie 文件为字典。"""
    path = managed_path()
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 7 and fields[5]:
            result[fields[5]] = fields[6]
    return result


def _sign(params: dict[str, str]) -> dict[str, str]:
    """B 站 App 接口签名：按 key 排序拼接后加盐 MD5。"""
    encoded = urlencode(sorted(params.items()))
    sign = hashlib.md5((encoded + _TV_APPSEC).encode("utf-8")).hexdigest()
    return {**params, "sign": sign}


def _tv_code(payload: dict, action: str) -> dict:
    if int(payload.get("code") or 0) != 0:
        raise LoginError(f"{action}失败：{payload.get('message') or payload.get('code')}")
    return payload.get("data") or {}


def _tv_form(auth_code: str | None = None) -> dict[str, str]:
    form = {"appkey": _TV_APP_KEY, "local_id": "0", "ts": str(int(time.time()))}
    if auth_code:
        form["auth_code"] = auth_code
    return _sign(form)


def _tv_request(url: str, form: dict[str, str]) -> dict:
    response = httpx.post(url, data=form, timeout=20, follow_redirects=False,
                          headers={"User-Agent": _TV_UA})
    return response.json()


def tv_qr_code() -> dict:
    """申请 TV 登录二维码：扫码确认后可直接拿到 biliup 所需的 access_token。"""
    data = _tv_code(_tv_request(_TV_AUTH_URL, _tv_form()), "申请投稿二维码")
    url = str(data.get("url") or "")
    auth_code = str(data.get("auth_code") or "")
    if not url or not auth_code:
        raise LoginError("投稿二维码信息不完整，请重试")
    return {"key": auth_code, "url": url, "image": segno.make(url, error="m").svg_data_uri(),
            "expires_in": QR_TTL}


def tv_poll(key: str) -> dict:
    """轮询 TV 登录：成功后写入 data/bilibili-cookies.json，同时刷新网页 Cookie。"""
    payload = _tv_request(_TV_POLL_URL, _tv_form(key))
    code = int(payload.get("code") or 0)
    if code == 86090:
        return {"state": "scanned", "message": "已扫码，请在手机上确认"}
    if code in (86039, 86101):
        return {"state": "waiting", "message": "等待扫码确认"}
    if code == 86038:
        return {"state": "expired", "message": "二维码已过期，请刷新"}
    if code != 0:
        raise LoginError(f"获取投稿凭据失败：{payload.get('message') or code}")
    data = payload.get("data") or {}
    token = data.get("token_info") or {}
    if not token.get("access_token"):
        raise LoginError("TV 登录未返回 access_token，请重新扫码")
    login = {"cookie_info": data.get("cookie_info") or {},
             "sso": data.get("sso") or [],
             "token_info": token,
             "platform": "BiliTV"}
    path = managed_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(login, ensure_ascii=False), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    # TV 登录同样返回网页 Cookie，顺手刷新 cookies.txt，弹幕接口无需再单独扫码
    cookies = {str(item.get("name")): str(item.get("value"))
               for item in (login["cookie_info"].get("cookies") or [])
               if isinstance(item, dict) and item.get("name")}
    if cookies.get("SESSDATA"):
        _write_netscape(cookies)
    status = login_status()
    return {"state": "success", "message": "投稿凭据已生成", "name": status.get("name")}


def ensure_upload_credentials() -> Path:
    """确保 cookies.json 存在（不存在时由投稿面板扫码生成）。"""
    path = managed_json_path()
    if not path.is_file():
        raise LoginError("尚未生成投稿凭据，请在投稿面板点「扫码获取投稿凭据」")
    return path


def login_status() -> dict:
    try:
        cookie = danmaku_fetch.cookie_header()
    except danmaku_fetch.CookieMissing:
        return {"logged_in": False, "name": None, "mid": None}
    if not cookie:
        return {"logged_in": False, "name": None, "mid": None}
    try:
        with danmaku_fetch._client(cookie) as client:
            response = client.get(NAV_URL)
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {"logged_in": False, "name": None, "mid": None}
    data = payload.get("data") or {}
    logged_in = bool(payload.get("code") == 0 and data.get("isLogin"))
    return {"logged_in": logged_in, "name": data.get("uname") or None,
            "mid": int(data.get("mid") or 0) or None}


def logout() -> dict:
    """删除扫码登录生成的文件（含投稿凭据），用户自己导出的 cookies.txt 不动。"""
    removed = False
    for path in (managed_path(), managed_json_path()):
        if path.is_file() and not path.is_symlink():
            path.unlink()
            removed = True
    return {"removed": removed, **login_status()}
