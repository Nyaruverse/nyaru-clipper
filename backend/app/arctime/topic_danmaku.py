"""Bounded ASS/XML import adapted from 69d3fa0 danmaku.py."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from app.arctime.topic_models import DanmakuEntry, DanmakuStore, TopicError

MAX_DANMAKU_BYTES = 8 * 1024 * 1024
_BOTS = ("抽奖", "中奖", "关注了", "打卡", "签到", "粉丝牌", "直播间", "正在直播")


def _text(text: str) -> str:
    return " ".join(re.sub(r"\{[^}]*\}", "", text).replace(r"\N", " ").split())


def _ass_seconds(value: str) -> float:
    match = re.fullmatch(
        r"(\d{1,3}):([0-5]\d):([0-5]\d)(?:[.,](\d{1,3}))?", value.strip()
    )
    if match is None:
        raise TopicError("无效 ASS 时间")
    hours, minutes, seconds, fraction = match.groups()
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int((fraction or "0").ljust(3, "0")) / 1000
    )


def parse_danmaku(content: str) -> DanmakuStore:
    if len(content.encode("utf-8")) > MAX_DANMAKU_BYTES:
        raise TopicError("弹幕超过 8 MiB 上限")
    entries = []
    if content.lstrip("\ufeff \r\n\t").startswith("<"):
        if "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
            raise TopicError("XML 不允许 DTD 或实体声明")
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as error:
            raise TopicError("无效弹幕 XML") from error
        source = "xml"
        for element in root.iter("d"):
            parts = element.get("p", "").split(",")
            try:
                seconds = float(parts[0])
            except ValueError as error:
                raise TopicError("无效 XML 弹幕时间") from error
            entries.append(
                DanmakuEntry(
                    seconds=seconds,
                    text=_text("".join(element.itertext())),
                    user=parts[6] if len(parts) > 6 else "",
                )
            )
            if len(entries) > 100000:
                raise TopicError("弹幕超过 100000 条上限")
    else:
        source = "ass"
        for line in content.splitlines():
            if not line.lower().startswith("dialogue:"):
                continue
            fields = line.split(",", 9)
            if len(fields) != 10:
                raise TopicError("无效 ASS Dialogue 行")
            start, end = _ass_seconds(fields[1]), _ass_seconds(fields[2])
            if end < start:
                raise TopicError("ASS 弹幕结束早于开始")
            entries.append(DanmakuEntry(seconds=start, text=_text(fields[9])))
            if len(entries) > 100000:
                raise TopicError("弹幕超过 100000 条上限")
    if not entries:
        raise TopicError("没有可读取的 ASS/XML 弹幕")
    return DanmakuStore(
        source=source,
        entries=sorted(
            [entry for entry in entries if not any(bot in entry.text for bot in _BOTS)],
            key=lambda entry: entry.seconds,
        ),
    )
