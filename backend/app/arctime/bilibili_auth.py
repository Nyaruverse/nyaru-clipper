"""B 站扫码登录：生成登录二维码、轮询扫码状态、保存 Cookie。

B 站的历史弹幕接口必须登录才能返回数据，匿名只拿得到「当前弹幕池」的
有限条目（长回放约一万条上限）。这里走官方 passport 扫码流程：

1. `qrcode/generate` 拿到登录 URL 与 qrcode_key，前端展示二维码；
2. 用户用手机 B站 App 扫码并确认；
3. `qrcode/poll` 轮询到 code=0，响应头的 Set-Cookie 就是登录态；
4. 按 Netscape 格式写入 data/bilibili-cookies.txt，供 danmaku_fetch 复用。
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx
import segno

from app.arctime import danmaku_fetch

GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
COOKIE_NAME = "bilibili-cookies.txt"
# 二维码约 3 分钟过期，提前一点提示用户刷新
QR_TTL = 170

# poll 返回的业务码：0 成功，86101 未扫码，86090 已扫码待确认，86038 已过期
_STATES = {0: "success", 86101: "waiting", 86090: "scanned", 86038: "expired"}


class LoginError(RuntimeError):
    """扫码登录流程中的可预期错误。"""


def _expiry() -> int:
    return int(time.time()) + 30 * 24 * 3600


def managed_path() -> Path:
    """扫码登录固定写入 data/bilibili-cookies.txt（环境变量只影响读取优先级）。"""
    return danmaku_fetch.REPO_ROOT / "data" / COOKIE_NAME


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
        _save_managed(cookies)
        status = login_status()
        return {"state": "success", "message": "登录成功", "name": status.get("name")}


def _save_managed(cookies: dict[str, str]) -> None:
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
    """只删除扫码登录生成的文件，用户自己导出的 cookies.txt 不动。"""
    path = managed_path()
    removed = False
    if path.is_file() and not path.is_symlink():
        path.unlink()
        removed = True
    return {"removed": removed, **login_status()}
