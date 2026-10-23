from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from fastapi import APIRouter, Response
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.db import get_database_url
from app.services.runtime_capabilities import get_runtime_capability_summary
from app.services.storage import get_tasks_root

router = APIRouter(tags=["health"])


def _database_is_readable() -> bool:
    try:
        url = make_url(get_database_url())
        if (
            url.drivername not in {"sqlite", "sqlite+pysqlite"}
            or not url.database
            or url.database == ":memory:"
            or url.host is not None
            or url.username is not None
            or url.password is not None
            or url.port is not None
            or url.query
        ):
            return False
        database_uri = Path(url.database).resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(database_uri, uri=True, timeout=1.0)) as connection:
            connection.execute("SELECT 1 FROM task LIMIT 1")
        return True
    except (sqlite3.Error, OSError, ArgumentError, ValueError):
        return False


@router.get("/health")
def healthcheck(response: Response) -> dict[str, object]:
    database_ready = _database_is_readable()
    get_tasks_root()
    if not database_ready:
        response.status_code = 503
    return {
        "status": "ok" if database_ready else "error",
        "storage": "ok",
        "database": "ok" if database_ready else "error",
        "runtime_capabilities": get_runtime_capability_summary(),
    }
