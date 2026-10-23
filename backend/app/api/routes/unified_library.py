from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.api.schemas.unified_library import LibraryItem, LibraryPage, LibraryPatch
from app.db import get_session
from app.models import Task, TaskTagLink
from app.models_unified import TaskBinding
from app.services.migration_groups import record_new_write
from app.services.task_library_lifecycle import TaskMetadataPatch, patch_task_metadata
from app.services.task_operations import canonical, digest
from app.services.unified_database import begin_unified_mutation


def item(session: Session, task: Task) -> LibraryItem:
    tags = tuple(session.exec(select(TaskTagLink.tag_name).where(TaskTagLink.task_id == task.id).order_by(TaskTagLink.tag_name)).all())
    value = task.model_dump(mode='json')
    for field in ('created_at', 'updated_at', 'archived_at'):
        timestamp = getattr(task, field)
        value[field] = timestamp.replace(tzinfo=None).isoformat() if timestamp is not None else None
    value['tags'] = list(tags)
    return LibraryItem(task_id=task.id, title=task.title, tags=tags, status=task.status,
        archived=task.archived_at is not None, version=digest(canonical(value)), created_at=task.created_at, updated_at=task.updated_at)


def library_router(sessions: Callable[[], Iterator[Session]]) -> APIRouter:
    router = APIRouter(prefix='/v2/library', tags=['unified-library'])

    @router.get('', response_model=LibraryPage)
    def list_library(search: str = Query(default='', max_length=200), tag: str | None = Query(default=None, max_length=80),
                     include_archived: bool = False, page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
                     session: Session = Depends(sessions)) -> LibraryPage:
        statement = select(Task).join(TaskBinding).where(TaskBinding.state == 'activated')
        if not include_archived:
            statement = statement.where(Task.archived_at == None)
        if search:
            statement = statement.where(or_(Task.title.contains(search, autoescape=True), Task.id.contains(search, autoescape=True)))
        if tag:
            statement = statement.where(Task.id.in_(select(TaskTagLink.task_id).where(TaskTagLink.tag_name == tag)))
        total = session.exec(select(func.count()).select_from(statement.subquery())).one()
        tasks = session.exec(statement.order_by(Task.updated_at.desc(), Task.id).offset((page - 1) * page_size).limit(page_size)).all()
        return LibraryPage(items=tuple(item(session, task) for task in tasks), total=total, page=page, page_size=page_size)

    @router.patch('/{task_id}', response_model=LibraryItem)
    def update_library(task_id: str, payload: LibraryPatch, session: Session = Depends(sessions)) -> LibraryItem:
        begin_unified_mutation(session)
        binding, task = session.get(TaskBinding, task_id), session.get(Task, task_id)
        if binding is None or binding.state != 'activated' or task is None:
            raise HTTPException(404, '任务不存在或尚未接管')
        if item(session, task).version != payload.expected_version:
            raise HTTPException(409, '任务元数据已变化，请保留输入并重新读取')
        patch_task_metadata(session, task_id, TaskMetadataPatch(title=payload.title, tags=payload.tags, archived=payload.archived,
            updates_title='title' in payload.model_fields_set, updates_tags='tags' in payload.model_fields_set,
            updates_archive='archived' in payload.model_fields_set))
        record_new_write(session)
        session.flush()
        result = item(session, task)
        session.commit()
        return result

    return router


router = library_router(get_session)
