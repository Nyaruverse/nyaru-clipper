from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.arctime.subtitle_style import SubtitleStyle
from app.arctime.subtitle_templates import StudioSettings, TemplateStore
from app.models_unified import GlobalHead, GlobalVersion
from app.services.global_documents import GlobalDocuments
from test_unified_operations import database


def test_templates_use_immutable_bodies_and_shared_revision_checks(tmp_path: Path) -> None:
    engine = database(tmp_path)
    settings = tmp_path / 'settings'
    documents = GlobalDocuments(engine, settings)
    first = TemplateStore(settings, documents=documents)
    second = TemplateStore(settings, documents=GlobalDocuments(engine, settings))
    item = first.save_style('Shared', SubtitleStyle())
    first.save_studio_settings(StudioSettings(default_template_id=item.id))
    changed = second.save_style('Updated', item.style, template_id=item.id, expected_revision=1)
    assert changed.revision == 2
    with pytest.raises(ValueError, match='revision'):
        first.save_style('Stale', item.style, template_id=item.id, expected_revision=1)
    assert first.download_style(item.id) == second.download_style(item.id)
    assert not (settings / 'templates/styles' / f'{item.id}.json').exists()
    with Session(engine) as session:
        versions = session.exec(select(GlobalVersion).where(GlobalVersion.key == f'templates/styles/{item.id}.json')).all()
        assert len(versions) == 2
        assert all((settings / row.body_path).is_file() for row in versions)
    with pytest.raises(ValueError, match='默认模板'):
        first.delete_style(item.id)


def test_project_set_failure_keeps_database_heads_unchanged_and_does_not_adopt_orphans(tmp_path: Path) -> None:
    engine = database(tmp_path)
    settings = tmp_path / 'settings'
    bodies = []

    def fail(point: str) -> None:
        if point == 'body':
            bodies.append(1)
            if len(bodies) == 2:
                raise OSError('injected full disk')

    store = TemplateStore(settings, documents=GlobalDocuments(engine, settings, fault=fail))
    with pytest.raises(OSError):
        store.save_project('Project', 'example.atpj', b'local project fixture')
    reopened = TemplateStore(settings, documents=GlobalDocuments(engine, settings))
    assert reopened.list_projects() == []
    assert list((settings / '.unified/global').rglob('r1-*'))
    with Session(engine) as session:
        assert session.exec(select(GlobalHead)).all() == []
        assert session.exec(select(GlobalVersion)).all() == []
    project = reopened.save_project('Project', 'example.atpj', b'local project fixture')
    style = reopened.save_style('Bound', SubtitleStyle(), project.id)
    assert reopened.download_project(project.id) == b'local project fixture'
    with pytest.raises(ValueError, match='linked'):
        reopened.delete_project(project.id)
    reopened.delete_style(style.id)
    reopened.delete_project(project.id)
    assert reopened.list_projects() == []
    assert list((settings / '.unified/global').rglob('r1-*'))
