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


@pytest.mark.parametrize("value,live,expected", [
    (" 12345 ", True, "https://live.bilibili.com/12345"),
    (" BV1xx411c7mD ", False, "https://www.bilibili.com/video/BV1xx411c7mD"),
])
def test_source_identifiers_are_normalized(value, live, expected):
    request = JobInput(url=value, saozi=True, live=live)
    assert request.url == expected


@pytest.mark.parametrize("value,live", [("0", True), ("-123", True),
    ("123?token=secret", True), ("BV123", False), ("BV1xx411c7mD", True), ("12345", False)])
def test_invalid_or_mismatched_identifiers_are_rejected(value, live):
    with pytest.raises(ValidationError):
        JobInput(url=value, saozi=True, live=live)
