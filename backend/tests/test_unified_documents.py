from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.arctime.subtitle_document import Cue, SubtitleDocument
from app.arctime.subtitle_style import SubtitleStyle
from app.models_unified import DocumentHead, DocumentVersion
from app.services.task_documents import Documents
from app.services.task_operations import bind_task
from test_unified_operations import database


def document() -> SubtitleDocument:
    return SubtitleDocument(source_fingerprint="f" * 64, revision=0, style=SubtitleStyle(),
        cues=[Cue(id="cue-000001", start_seconds=0., end_seconds=1., text="source")],
        width=1280, height=720, duration=2., fps=30.)


def test_document_current_revision_is_only_database_registered_body(tmp_path: Path) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), "document", "g", origin="native")
        task_id = binding.task_id
        session.commit()
    root = tmp_path / "files"
    documents = Documents(engine, root)
    base = document()
    assert documents.load(task_id, base).revision == 0
    saved = documents.save(task_id, base, base=base)
    assert saved.revision == 1
    assert Documents(engine, root).load(task_id, base).model_dump() == saved.model_dump()
    with pytest.raises(ValueError, match="冲突"):
        documents.save(task_id, base, base=base)
    with Session(engine) as session:
        assert len(session.exec(select(DocumentVersion)).all()) == 1
        head = session.get(DocumentHead, task_id)
        assert head.revision == 1
    path = root / head.body_path
    before = path.read_bytes()
    edit = saved.model_copy(update={"cues": [saved.cues[0].model_copy(update={"text": "next"})]})

    def disk_written(point: str) -> None:
        if point == "body":
            raise OSError("simulated database unavailable after body fsync")

    with pytest.raises(OSError):
        Documents(engine, root, fault=disk_written).save(task_id, edit, base=base)
    assert documents.load(task_id, base).revision == 1
    assert path.read_bytes() == before
    saved2 = documents.save(task_id, edit, base=base)
    assert saved2.revision == 2 and saved2.cues[0].text == "next"
    assert path.read_bytes() == before


def test_corrupt_registered_document_is_never_replaced_with_source(tmp_path: Path) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), "document", "g", origin="native")
        task_id = binding.task_id
        session.commit()
    documents = Documents(engine, tmp_path / "files")
    documents.save(task_id, document(), base=document())
    with Session(engine) as session:
        head = session.get(DocumentHead, task_id)
    (documents.root / head.body_path).write_bytes(b"corrupt registered body")
    with pytest.raises(ValueError, match="hash"):
        documents.load(task_id, document())


def test_document_save_rejects_unsafe_sqlite_durability(tmp_path: Path) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), 'document', 'g', origin='native')
        task_id = binding.task_id
        session.commit()
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA synchronous=OFF')
    with pytest.raises(ValueError, match='SQLite'):
        Documents(engine, tmp_path / 'files').save(task_id, document(), base=document())
    with Session(engine) as session:
        assert session.get(DocumentHead, task_id) is None
