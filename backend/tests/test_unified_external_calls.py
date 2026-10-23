from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlmodel import Session, select

from app.arctime import translation
from app.models import WorkstationEvent
from app.models_unified import UnifiedOperation
from app.services.subtitles import SubtitleSegment
from app.services.task_execution import Execution, Executor
from app.services.task_operations import OperationConflict, bind_task, enqueue_operation, retry_operation, set_admissions
from test_unified_operations import database


def queued(tmp_path: Path):
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), 'translation', 'g', origin='native')
        operation = enqueue_operation(session, binding.task_id, 'translate', {})
        identifier = operation.id
        set_admissions(session, paused=False)
        session.commit()
    return engine, identifier


def test_confirmed_response_is_reused_after_later_work_fails(tmp_path: Path) -> None:
    from app.services.external_calls import external_value
    from app.services.task_execution import WorkflowFailure
    from app.models_unified import OperationStep, UnifiedPublication
    engine, identifier = queued(tmp_path)
    calls = []
    executor = Executor(engine, tmp_path / 'tasks', tmp_path / 'guard')

    def run(execution: Execution) -> None:
        value = external_value(execution, {'prompt': 'test', 'model': 'test'},
            lambda: calls.append(1) or {'result': 'confirmed'}, lambda value: value, lambda value: value)
        assert value == {'result': 'confirmed'}
        if execution.attempt == 1:
            raise WorkflowFailure('subsequent_work_failed')

    executor.iteration(run)
    with Session(engine) as session:
        retry_operation(session, identifier)
        session.commit()
    executor.iteration(run)
    assert calls == [1]
    with Session(engine) as session:
        assert session.get(UnifiedOperation, identifier).state == 'succeeded'
        assert len(session.exec(select(UnifiedPublication)).all()) == 1
        assert len(session.exec(select(OperationStep).where(OperationStep.reused_publication_id.is_not(None))).all()) == 1


@pytest.mark.parametrize('status, expected', [(503, 'external_outcome_unknown_possible_repeat_charge'), (401, 'provider_rejected')])
def test_chatgpt_uncertain_request_is_not_retried(tmp_path: Path, status: int, expected: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.arctime import chatgpt_provider
    engine, identifier = queued(tmp_path)
    calls = []
    monkeypatch.setattr(chatgpt_provider, 'RETRY_DELAY', 0)
    provider = chatgpt_provider.ChatGPTProvider('slug', lambda: SecretStr('fake-secret'), transport=httpx.MockTransport(
        lambda request: calls.append(request.method) or httpx.Response(status)))
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail('unexpected DeepSeek request'))) as client:
        Executor(engine, tmp_path / 'tasks', tmp_path / 'guard').iteration(lambda execution:
            translation._request(client, SecretStr(''), [SubtitleSegment('1', 0., 1., '原文')], 0, 'chatgpt:slug', request_json=provider))
    assert calls == ['POST']
    with Session(engine) as session:
        operation = session.get(UnifiedOperation, identifier)
        assert operation.failure_code == expected
        assert operation.state == ('interrupted' if status == 503 else 'failed')


def test_uncertain_provider_call_is_not_blindly_retried_and_requires_explicit_acknowledgement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), 'translation', 'g', origin='native')
        operation = enqueue_operation(session, binding.task_id, 'translate', {})
        identifier = operation.id
        set_admissions(session, paused=False)
        session.commit()
    calls = []

    def remote(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        raise httpx.ReadTimeout('SECRET_CANARY_FAKE_TRANSPORT', request=request)

    monkeypatch.setattr(translation.time, 'sleep', lambda delay: None)
    with httpx.Client(transport=httpx.MockTransport(remote)) as client:
        def run(execution: Execution) -> None:
            translation._request(client, SecretStr('SECRET_CANARY_FAKE_KEY'), [SubtitleSegment('1', 0., 1., '原文')], 0, translation.MODEL)
        Executor(engine, tmp_path / 'tasks', tmp_path / 'guard').iteration(run)
    assert calls == ['POST']
    with Session(engine) as session:
        operation = session.get(UnifiedOperation, identifier)
        assert operation.state == 'interrupted'
        assert operation.failure_code == 'external_outcome_unknown_possible_repeat_charge'
        assert all('SECRET_CANARY' not in event.payload_json for event in session.exec(select(WorkstationEvent)).all())
        with pytest.raises(OperationConflict, match='acknowledge'):
            retry_operation(session, identifier)
        session.rollback()
        retry_operation(session, identifier, acknowledge_external_outcome=True)
        session.commit()
