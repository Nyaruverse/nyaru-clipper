import pytest
from pydantic import ValidationError

from app.arctime.companion_models import JobInput


def test_saozi_replay_is_a_third_exclusive_mode():
    request = JobInput(url="https://example.org/replay", saozi=True)
    assert request.saozi is True
    with pytest.raises(ValidationError):
        JobInput(url="https://example.org/replay", saozi=True, highlights=2)


def test_live_saozi_only_accepts_bilibili_rooms():
    request = JobInput(url="https://live.bilibili.com/12345", saozi=True, live=True)
    assert request.live is True
    for url in ("https://example.org/live", "https://live.bilibili.com.evil.org/12345",
                "https://live.bilibili.com/", "https://live.bilibili.com/12345?token=secret"):
        with pytest.raises(ValidationError):
            JobInput(url=url, saozi=True, live=True)
    with pytest.raises(ValidationError):
        JobInput(url="https://live.bilibili.com/12345", highlights=2, live=True)
