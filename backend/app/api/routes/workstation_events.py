"""Server-sent events for durable workstation projections."""

from __future__ import annotations

from typing import Annotated
from threading import Event

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Engine

from app.services.workstation_events import iter_events

router = APIRouter(prefix="/v2/events", tags=["workstation-events"])


@router.get(
    "",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "A replayable server-sent event stream.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def workstation_events_endpoint(
    last_event_id: Annotated[int | None, Header(alias="Last-Event-ID", ge=0)] = None,
    cursor: Annotated[int | None, Query(ge=0)] = None,
) -> StreamingResponse:
    """Keep a browser client synchronized through replayable SSE state changes."""
    replay_after = last_event_id if last_event_id is not None else cursor
    return StreamingResponse(
        iter_events(replay_after, heartbeat_seconds=15),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def events_router(engine: Engine, *, stopped: Event | None = None) -> APIRouter:
    result = APIRouter(prefix='/v2/events', tags=['workstation-events'])

    @result.get('', response_class=StreamingResponse)
    async def unified_events_endpoint(
        last_event_id: Annotated[int | None, Header(alias='Last-Event-ID', ge=0)] = None,
        cursor: Annotated[int | None, Query(ge=0)] = None,
    ) -> StreamingResponse:
        replay_after = last_event_id if last_event_id is not None else cursor
        return StreamingResponse(iter_events(replay_after, heartbeat_seconds=15, engine=engine, stopped=stopped),
            media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    return result
