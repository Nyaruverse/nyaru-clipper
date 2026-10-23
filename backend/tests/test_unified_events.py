from pathlib import Path

import anyio
from sqlmodel import Session

from app.services.workstation_events import iter_events, publish_event
from test_unified_operations import database


def test_explicit_host_events_never_use_the_default_database_and_reset_stale_cursor(tmp_path: Path, monkeypatch) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        event = publish_event(session, 'operation.updated', 'operation', {'state': 'queued'})
        session.commit()
        identifier = event.id

    def forbidden():
        raise AssertionError('default database must not be opened by an isolated host')

    monkeypatch.setattr('app.services.workstation_events.get_engine', forbidden)

    async def frame(cursor):
        stream = iter_events(cursor, heartbeat_seconds=0, engine=engine)
        result = await anext(stream)
        await stream.aclose()
        return result

    assert 'event: operation.updated' in anyio.run(frame, None)
    assert f'id: {identifier}\nevent: stream.reset' in anyio.run(frame, identifier + 100)
