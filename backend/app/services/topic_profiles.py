from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from app.arctime.topic_models import (
    DanmakuStore,
    TopicModel,
    TopicQuote,
    TopicSegmentStore,
)
from app.services.task_execution import Execution
from app.services.task_operations import digest

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


class TopicProfile(TopicModel):
    label: str = "未识别主播"
    sessions: int = Field(default=0, ge=0)
    terms: dict[str, float] = Field(default_factory=dict)
    quotes: list[TopicQuote] = Field(default_factory=list, max_length=30)


def profile_identity(
    host: NativeHost, task_id: str, danmaku: DanmakuStore
) -> tuple[str, str]:
    if danmaku.streamer:
        label = danmaku.streamer
        identity = "streamer:" + label.casefold()
    else:
        identity = "task:" + task_id
        label = "未指定主播（仅本任务）"
    return f"topics/profiles/{digest(identity)}.json", label


def load_profile(host: NativeHost, key: str) -> TopicProfile:
    content = host.globals.read(key)
    return TopicProfile.model_validate_json(content) if content else TopicProfile()


def accumulate_profile(
    host: NativeHost, execution: Execution, key: str, store: TopicSegmentStore
) -> None:
    if not store.vocabulary and not store.quotes:
        return
    marker = f"topics/profile-applied/{execution.operation_id}.json"
    with host.globals.mutation(execution=execution):
        if host.globals.read(marker) is not None:
            return
        current = load_profile(host, key)
        weights = {term: weight * 0.85 for term, weight in current.terms.items()}
        for term, weight in store.extracted_terms.items():
            weights[term] = weights.get(term, 0.0) + weight
        quotes = []
        seen = set()
        for quote in [*store.quotes, *current.quotes]:
            if quote.text not in seen:
                seen.add(quote.text)
                quotes.append(quote)
        updated = TopicProfile(
            label=store.streamer or current.label,
            sessions=current.sessions + 1,
            terms=dict(sorted(weights.items(), key=lambda item: -item[1])[:200]),
            quotes=quotes[:30],
        )
        host.globals.write(key, updated.model_dump_json().encode())
        host.globals.write(marker, b'{"applied":true}')
