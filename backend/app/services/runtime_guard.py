from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from app.services.unified_files import checked_path, make_parents

if os.name != 'nt':
    import fcntl


class SlotBusy(RuntimeError):
    pass


def default_guard_root() -> Path:
    configured = os.environ.get("APP_EXECUTION_GUARD_ROOT")
    return Path(configured).expanduser().absolute() if configured else Path.home() / ".cache/nyaru-clipper/execution-guard"


@contextmanager
def execution_slot(root: Path | None = None) -> Iterator[None]:
    path = checked_path(root or default_guard_root(), ".heavy.lock")
    if os.name == 'nt':
        from app.arctime.workflow import exclusive_lock
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with ExitStack() as stack:
            try:
                stack.enter_context(exclusive_lock(path))
            except RuntimeError as error:
                raise SlotBusy("another host executor owns the heavy-work slot") from error
            yield
        return
    make_parents(path)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SlotBusy("another host executor owns the heavy-work slot") from error
        yield
    finally:
        os.close(descriptor)


@contextmanager
def engine_slot() -> Iterator[None]:
    from app.services.task_execution import current_execution
    execution = current_execution.get()
    if execution is None:
        with execution_slot():
            yield
    else:
        execution.check()
        yield
