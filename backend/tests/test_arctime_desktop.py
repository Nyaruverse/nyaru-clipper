from pathlib import Path

import pytest

from app.arctime.desktop import ArcTimeDesktop, DesktopError


def window(title="ArcTime Pro", texts=()):
    dialog = title == "语音转写"
    return {"id": 2 if dialog else 1, "title": title, "width": 640 if dialog else 1920, "height": 480 if dialog else 1080,
            "texts": [{"text": t, "x": .5, "y": .5} for t in texts]}


class FakeDesktop(ArcTimeDesktop):
    def __init__(self, windows):
        super().__init__()
        self.windows = windows
        self.calls = []

    def bridge(self, action, *args):
        self.calls.append((action, args))
        return {"windows": self.windows}


def test_unrelated_project_is_never_replaced(tmp_path):
    d = FakeDesktop([window("ExistingProject - ArcTime Pro")])
    with pytest.raises(DesktopError, match="unrelated"):
        d.open_video(tmp_path / "nyaru-123.mp4")
    assert all(action == "inspect" for action, _ in d.calls)


def test_login_required_never_clicks_start(tmp_path):
    d = FakeDesktop([window("语音转写", ["请先登录", "开始"]), window("nyaru-123.mp4")])
    with pytest.raises(DesktopError, match="login"):
        d.submit(tmp_path / "nyaru-123.mp4")
    assert not any(action == "click" for action, _ in d.calls)


def test_no_timeline_engine_is_rejected(tmp_path):
    d = FakeDesktop([window("语音转写", ["无时间轴", "开始"]), window("nyaru-123.mp4")])
    with pytest.raises(DesktopError, match="timeline"):
        d.submit(tmp_path / "nyaru-123.mp4")


def test_unknown_dialog_never_clicks_start(tmp_path):
    d = FakeDesktop([window("nyaru-123.mp4")])
    with pytest.raises(DesktopError):
        d.submit(tmp_path / "nyaru-123.mp4")
    assert not any(action == "click" for action, _ in d.calls)


def test_resume_status_never_clicks_start(tmp_path):
    d = FakeDesktop([window("语音转写", ["开始"]), window("nyaru-123.mp4")])
    assert d.status(tmp_path / "nyaru-123.mp4") == "unknown"
    assert not any(action == "click" for action, _ in d.calls)


def test_status_detects_available_result(tmp_path):
    d = FakeDesktop([window("语音转写", ["该项目已有转写结果", "获取"]), window("nyaru-123.mp4")])
    assert d.status(tmp_path / "nyaru-123.mp4") == "ready"


def test_changed_project_refuses_even_known_buttons(tmp_path):
    d = FakeDesktop([window("other.mp4"), window("语音转写", ["获取", "开始"] )])
    with pytest.raises(DesktopError, match="project"):
        d.status(tmp_path / "nyaru-123.mp4")


def test_duplicate_start_buttons_are_ambiguous(tmp_path):
    d = FakeDesktop([window("nyaru-123.mp4"), window("语音转写", ["开始", "开始"] )])
    with pytest.raises(DesktopError, match="ambiguous"):
        d.submit(tmp_path / "nyaru-123.mp4")
