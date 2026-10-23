from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.arctime import subtitle_encoding, subtitle_exports
from app.arctime.gui import create_app
from app.services.task_artifacts import resolve_workstation
from test_unified_artifacts import frozen_source


def test_workstation_result_uses_existing_editor_api_without_legacy_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = frozen_source(tmp_path)
    resolved = resolve_workstation(source)
    monkeypatch.setattr(subtitle_encoding, 'video_metadata', lambda path: (1280, 720, 30.))
    monkeypatch.setattr(subtitle_exports, 'video_dimensions', lambda path: (1280, 720))
    output = tmp_path / 'candidate'
    with TestClient(create_app(output, artifacts=(resolved,))) as client:
        jobs = client.get('/companion-api/jobs')
        assert jobs.status_code == 200, jobs.text
        assert jobs.json()[0]['id'] == source.task_id
        assert jobs.json()[0]['bilingual_suffix'] == '.zh-ja'
        url = f'/companion-api/jobs/{source.task_id}'
        document = client.get(url + '/subtitle-document')
        assert document.status_code == 200, document.text
        draft = document.json()
        draft['cues'][0]['text'] = '编辑后的原文'
        saved = client.post(url + '/subtitle-document', json=draft)
        assert saved.status_code == 200, saved.text
        assert saved.json()['revision'] == 1
        assert client.post(url + '/subtitle-document', json=draft).status_code == 409
        original = client.get(url + '/files/subtitles.srt')
        assert original.status_code == 200 and '这是统一架构' in original.text
        assert client.get(url + '/files/subtitles.zh-ja.vtt').text.startswith('WEBVTT')
        assert client.get(url + '/files/subtitles.ja-zh.srt').status_code == 404
        assert client.post(url + '/resume').status_code == 409
        assert client.post(url + '/translate').status_code == 409
    with TestClient(create_app(output, artifacts=(resolved,))) as reopened:
        again = reopened.get(url + '/subtitle-document')
        assert again.status_code == 200, again.text
        assert again.json()['cues'][0]['text'] == '编辑后的原文'
        assert again.json()['revision'] == 1
    assert not (source.root / 'job.json').exists()
    assert not (output / source.task_id / 'job.json').exists()


def test_candidate_output_cannot_overlap_old_artifact_root(tmp_path: Path) -> None:
    source = frozen_source(tmp_path)
    with pytest.raises(ValueError):
        create_app(source.root / 'nested-output', artifacts=(resolve_workstation(source),))


def test_editor_uses_registered_immutable_document_revision_when_unified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlmodel import Session
    from app.models_unified import DocumentHead
    from app.services.task_documents import Documents
    from app.services.task_operations import bind_task
    from test_unified_operations import database
    source = frozen_source(tmp_path)
    resolved = resolve_workstation(source)
    monkeypatch.setattr(subtitle_encoding, 'video_metadata', lambda path: (1280, 720, 30.))
    engine = database(tmp_path)
    with Session(engine) as session:
        bind_task(session, source.source_instance_id, source.legacy_id, source.fingerprint, origin='native')
        session.commit()
    output = tmp_path / 'new-documents'
    documents = Documents(engine, output)
    url = f'/companion-api/jobs/{source.task_id}/subtitle-document'
    with TestClient(create_app(output, artifacts=(resolved,), documents=documents)) as client:
        draft = client.get(url).json()
        draft['cues'][0]['text'] = '数据库登记的新稿'
        saved = client.post(url, json=draft)
        assert saved.status_code == 200, saved.text
        assert client.post(url, json=draft).status_code == 409
    assert not (output / source.task_id / 'subtitle-document.json').exists()
    with TestClient(create_app(output, artifacts=(resolved,), documents=Documents(engine, output))) as client:
        reopened = client.get(url)
        assert reopened.json()['revision'] == 1 and reopened.json()['cues'][0]['text'] == '数据库登记的新稿'
    with Session(engine) as session:
        head = session.get(DocumentHead, source.task_id)
        assert (output / head.body_path).is_file()
