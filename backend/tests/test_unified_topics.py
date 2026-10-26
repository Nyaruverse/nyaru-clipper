from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize('end_id,accepted', [(10, False), (2, True), (5, True)])
def test_highlight_analysis_rejects_whole_video_partition(tmp_path, monkeypatch, end_id, accepted):
    import json
    from uuid import uuid4
    from pydantic import SecretStr
    from sqlmodel import Session
    from app.arctime import topic_segments
    from app.arctime.subtitle_document import Cue, SubtitleDocument
    from app.arctime.subtitle_style import SubtitleStyle
    from app.arctime.topic_models import TopicAnalyzeOptions, TopicError
    from app.services.task_execution import Executor
    from app.services.task_operations import bind_task, enqueue_operation, set_admissions
    from test_unified_operations import database

    engine = database(tmp_path)
    document = SubtitleDocument(source_fingerprint='0' * 64, revision=0, style=SubtitleStyle(),
        cues=[Cue(id=f'cue-{i+1:06d}', start_seconds=i*30., end_seconds=(i+1)*30., text=f'内容{i}') for i in range(10)],
        width=320, height=180, duration=300., fps=10.)
    with Session(engine) as session:
        task_id = bind_task(session, uuid4(), 'selective-highlights', 'g', origin='native').task_id
        enqueue_operation(session, task_id, 'analyze_topics', {'input': {}, 'config': {}})
        set_admissions(session, paused=False)
        session.commit()
    seen, results, errors = [], [], []

    def response(model, key, prompt, content, requester):
        seen.append(json.loads(content))
        return json.dumps({'segments': [{'start_id': 1, 'end_id': end_id, 'title': '候选', 'summary': '精彩互动'}]})

    monkeypatch.setattr(topic_segments, 'request_json', response)

    def run(execution):
        try:
            results.append(topic_segments.analyze_document(execution, document, TopicAnalyzeOptions(max_segments=5),
                'deepseek-chat', SecretStr('fixture-only'), None))
        except TopicError as error:
            errors.append(str(error))
            raise

    Executor(engine, tmp_path / 'tasks', tmp_path / 'guard').iteration(run)
    assert bool(results) == accepted
    assert bool(errors) != accepted
    assert seen[0]['highlight_budget_seconds'] == 120.


def test_topic_models_validate_boundaries_and_order() -> None:
    # Given the public analysis/export request boundary.
    assert importlib.util.find_spec("app.arctime.topic_models") is not None
    from app.arctime.topic_models import TopicAnalyzeOptions, TopicClipOptions
    from pydantic import ValidationError

    # When invalid ranges, counts or duplicate indices cross it, then reject them.
    for value in (
        {"start_seconds": -1},
        {"end_seconds": float("nan")},
        {"start_seconds": 2, "end_seconds": 1},
        {"max_segments": 101},
    ):
        with pytest.raises(ValidationError):
            TopicAnalyzeOptions.model_validate(value)
    with pytest.raises(ValidationError):
        TopicClipOptions(indices=[1, 1])
    assert TopicClipOptions(indices=[2, 0]).indices == [2, 0]


def test_danmaku_rejects_malformed_data_and_scores_only_available_signals() -> None:
    # Given bounded, user-supplied ASS/XML and topic results.
    assert importlib.util.find_spec("app.arctime.topic_scoring") is not None
    from app.arctime.topic_danmaku import parse_danmaku
    from app.arctime.topic_scoring import score_topics
    from app.arctime.topic_models import TopicSegment, TopicSegmentStore, ScoringConfig
    from app.arctime.subtitle_document import Cue
    from pydantic import ValidationError

    for text in (
        "garbage",
        '<i><d p="nan">bad</d></i>',
        '<!DOCTYPE i [<!ENTITY x "a">]><i/>',
        "Dialogue: 0,0:99:00,0:00:01,Default,,0,0,0,,text",
        '<i><d p="1">bad',
    ):
        with pytest.raises((ValueError, ValidationError)):
            parse_danmaku(text)
    parsed = parse_danmaku('<i><d p="2,1,25,0,0,0,user">精彩片段</d></i>')
    store = TopicSegmentStore(
        segments=[
            TopicSegment(
                index=0,
                start_id=1,
                end_id=1,
                start_seconds=0,
                end_seconds=20,
                cue_count=1,
                title="topic",
                summary="",
                preview="",
            )
        ]
    )
    cue = Cue(id="cue-000001", start_seconds=0.0, end_seconds=20.0, text="精彩片段")
    # When scoring with and without imported audience data, then absence stays explicit.
    assert score_topics(store, [cue], [], ScoringConfig()).segments[0].score is None
    scored = score_topics(store, [cue], parsed.entries, ScoringConfig())
    assert scored.segments[0].dm_count == 1
    assert 0 <= scored.segments[0].score <= 100
    assert scored.segments[0].loudness_db is None


def topic_host(tmp_path: Path):
    import subprocess
    from uuid import UUID
    from sqlmodel import Session
    from app.arctime.unified_host import NativeHost
    from app.arctime.subtitle_encoding import subtitle_ffmpeg
    from app.services.task_artifacts import ArtifactFile, WorkstationArtifacts
    from app.services.task_operations import bind_task, digest
    from test_unified_operations import database

    host = NativeHost(
        database(tmp_path),
        task_root=tmp_path / "tasks",
        settings_root=tmp_path / "settings",
        credential_root=tmp_path / "credentials",
        guard_root=tmp_path / "guard",
        model=tmp_path / "model",
    )
    instance = UUID("00000000-0000-4000-8000-000000000001")
    with Session(host.engine) as session:
        binding = bind_task(
            session, instance, "topics-fixture", "generation", origin="native"
        )
        task_id = binding.task_id
        folder = host.root / task_id
        folder.mkdir()
        subprocess.run(
            [
                subtitle_ffmpeg(),
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=320x180:r=10:d=40",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1000:duration=40",
                "-vf",
                "drawbox=color=blue:t=fill:enable=gte(t\\,20)",
                "-c:a",
                "aac",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(folder / "source.mp4"),
            ],
            check=True,
            capture_output=True,
        )
        (folder / "subtitles.srt").write_text(
            "1\n00:00:00,000 --> 00:00:20,000\nOriginal first\n\n2\n00:00:20,000 --> 00:00:40,000\nOriginal second\n"
        )
        import json

        (folder / "transcript.json").write_text(
            json.dumps(
                {
                    "segments": [
                        {
                            "id": "1",
                            "start_seconds": 0.0,
                            "end_seconds": 20.0,
                            "text": "Original first",
                        },
                        {
                            "id": "2",
                            "start_seconds": 20.0,
                            "end_seconds": 40.0,
                            "text": "Original second",
                        },
                    ]
                }
            )
        )

        def reference(name):
            return ArtifactFile(
                path=f"{task_id}/{name}", sha256=digest((folder / name).read_bytes())
            )

        source = WorkstationArtifacts(
            source_instance_id=instance,
            legacy_id="topics-fixture",
            root=host.root,
            duration=40.0,
            source_language="ja",
            video=reference("source.mp4"),
            transcript=reference("transcript.json"),
            subtitles=reference("subtitles.srt"),
        )
        binding.context_json = source.model_dump_json()
        session.add(binding)
        session.commit()
    return host, task_id


def test_topics_http_freezes_edits_exports_downloads_and_rejects_stale(
    tmp_path: Path, monkeypatch
) -> None:
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from sqlmodel import Session, select
    from app.arctime.gui import create_app
    from app.arctime import companion_llm
    from app.models_unified import UnifiedOperation
    from app.services.task_operations import set_admissions

    # Given a real registered media source and a manually saved editing document.
    host, task_id = topic_host(tmp_path)
    context = host.context(task_id)
    base = context.document(host.templates.load_defaults())
    edited = base.model_copy(
        update={
            "cues": [
                cue.model_copy(
                    update={
                        "text": "Saved edit " + str(i),
                        "translation": "翻译 " + str(i),
                    }
                )
                for i, cue in enumerate(base.cues)
            ]
        }
    )
    saved = host.documents.save(task_id, edited, base=base)
    monkeypatch.setattr(
        companion_llm, "require_key", lambda *args: SecretStr("fixture-only")
    )
    client = TestClient(create_app(host.root, host=host))
    url = f"/companion-api/jobs/{task_id}"
    assert client.get(url + "/topic-segments").status_code == 200
    from app.arctime import topic_segments

    seen = []

    def response(model, key, prompt, content, requester):
        seen.append(content)
        return '{"segments":[{"start_id":1,"end_id":1,"title":"first","summary":"first"},{"start_id":2,"end_id":2,"title":"second","summary":"second"}]}'

    monkeypatch.setattr(topic_segments, "request_json", response)
    # When admitted and dispatched via the same real queue, then it uses frozen edits.
    assert (
        client.post(
            url + "/danmaku", json={"content": '<i><d p="1">精彩内容</d></i>'}
        ).status_code
        == 200
    )
    admitted = client.post(url + "/topic-segments", json={"max_segments": 2})
    assert admitted.status_code == 202, admitted.text
    identifier = admitted.json()["operation_id"]
    with Session(host.engine) as session:
        set_admissions(session, paused=False)
        session.commit()
    assert host.executor.iteration(host.dispatch) == identifier
    store = client.get(url + "/topic-segments").json()
    assert store["state"] == "completed", store
    assert store["document_revision"] == saved.revision
    assert "Saved edit 0" in seen[0] and "翻译 0" in seen[0]
    assert not (host.root / task_id / "job.json").exists()
    for mode, variant in (
        ("separate", "original"),
        ("separate", "zh"),
        ("combined", "bilingual"),
    ):
        exported = client.post(
            url + "/topic-clips",
            json={"indices": [1, 0], "mode": mode, "variant": variant},
        )
        assert exported.status_code == 202, exported.text
        host.executor.iteration(host.dispatch)
        result = client.get(url + "/topic-clips").json()
        assert result["state"] == "completed", result
        assert [item["index"] for item in result["items"]] == [1, 0]
        for item in result["items"]:
            downloaded = client.get(item["url"])
            assert downloaded.status_code == 200 and len(downloaded.content) > 1000
        if mode == "combined":
            import subprocess
            from app.arctime.subtitle_encoding import subtitle_ffmpeg

            combined = client.get(result["combined"]["url"])
            assert combined.status_code == 200
            video = tmp_path / "downloaded-combined.mp4"
            video.write_bytes(combined.content)
            for second, expected in ((1, "blue"), (21, "red")):
                pixel = subprocess.run(
                    [
                        subtitle_ffmpeg(),
                        "-v",
                        "error",
                        "-ss",
                        str(second),
                        "-i",
                        str(video),
                        "-vf",
                        "crop=2:2:0:0",
                        "-frames:v",
                        "1",
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgb24",
                        "-",
                    ],
                    check=True,
                    capture_output=True,
                ).stdout
                assert (pixel[2] > pixel[0]) == (expected == "blue")
            from app.services.topic_results import latest, products

            files = products(host, latest(host, task_id, "export_topics"))
            ass = files["subtitle-001"][1].read_text()
            assert "Saved edit 1" in ass and "0:00:00.00,0:00:20.00" in ass
    # When another edit is saved, then the old analysis cannot admit an export.
    host.documents.save(task_id, saved, base=base)
    assert client.get(url + "/topic-segments").json()["state"] == "stale"
    assert client.post(url + "/topic-clips", json={"indices": [0]}).status_code == 409
    assert client.post(url + "/topic-clips", json={"indices": [999]}).status_code in (
        409,
        422,
    )
    with Session(host.engine) as session:
        assert {op.kind for op in session.exec(select(UnifiedOperation)).all()} == {
            "analyze_topics",
            "export_topics",
        }
    client.close()
    from app.arctime.unified_host import NativeHost

    reopened = NativeHost(
        host.engine,
        task_root=host.root,
        settings_root=host.settings_root,
        credential_root=host.credential_root,
        guard_root=host.guard_root,
        model=host.model,
    )
    with TestClient(create_app(host.root, host=reopened)) as reopened_client:
        assert (
            reopened_client.get(result["combined"]["url"]).content == combined.content
        )
        assert reopened_client.get(url + "/topic-segments").json()["state"] == "stale"


def test_audio_features_use_tracked_decoder_and_failed_media_is_unavailable(
    tmp_path: Path,
) -> None:
    # Given real media with audio and a real unified execution token.
    assert importlib.util.find_spec("app.arctime.topic_audio") is not None
    import subprocess
    from sqlmodel import Session
    from app.arctime.subtitle_encoding import subtitle_ffmpeg
    from app.arctime.topic_audio import audio_features
    from app.services.task_operations import enqueue_operation, set_admissions

    host, task_id = topic_host(tmp_path)
    source = tmp_path / "audio.wav"
    subprocess.run(
        [
            subtitle_ffmpeg(),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=2",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    results = []
    with Session(host.engine) as session:
        enqueue_operation(
            session, task_id, "analyze_topics", {"input": {}, "config": {}}
        )
        set_admissions(session, paused=False)
        session.commit()

    def run(execution):
        results.append(audio_features(execution, source, 2.0))
        bad = tmp_path / "broken.mp4"
        bad.write_bytes(b"invalid media")
        results.append(audio_features(execution, bad, 2.0))
        execution.publish("proof", {"source": source_copy(execution, source)})

    def source_copy(execution, source):
        copied = execution.staging("proof") / "source.wav"
        copied.write_bytes(source.read_bytes())
        return copied

    # When decoding succeeds and then malformed media fails, then no stale successful factors survive.
    host.executor.iteration(run)
    assert results[0].state == "available" and len(results[0].loudness) == 4
    assert results[1].state == "unavailable" and not results[1].loudness


@pytest.mark.parametrize("indices", [[True], [1.0], ["1"]])
def test_export_indices_reject_coercion(indices) -> None:
    from pydantic import ValidationError
    from app.arctime.topic_models import TopicClipOptions

    # Given ambiguous JSON values, when selecting clips, then integer indices are mandatory.
    with pytest.raises(ValidationError):
        TopicClipOptions(indices=indices)


def test_topic_admission_requires_key_and_queued_cancellation_stays_cancelled(
    tmp_path: Path, monkeypatch
) -> None:
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from app.arctime.gui import create_app
    from app.arctime import companion_llm

    host, task_id = topic_host(tmp_path)
    client = TestClient(create_app(host.root, host=host))
    url = f"/companion-api/jobs/{task_id}"
    # Given no credential, when submitting analysis, then admission fails without queueing a paid call.
    assert client.post(url + "/topic-segments", json={}).status_code == 409
    monkeypatch.setattr(
        companion_llm, "require_key", lambda *args: SecretStr("fixture-only")
    )
    operation = client.post(url + "/topic-segments", json={}).json()["operation_id"]
    current = client.get(url + "/topic-segments").json()
    assert current["document_revision"] == 0
    # When cancelled in the shared queue, then the topic projection cannot report success.
    assert client.post(f"/api/v2/operations/{operation}/cancel").status_code == 200
    assert client.get(url + "/topic-segments").json()["state"] == "cancelled"
    assert host.executor.iteration(host.dispatch) is None
    client.close()


def test_topic_cancel_during_external_response_never_publishes_topics_or_profile(
    tmp_path: Path, monkeypatch
) -> None:
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from sqlmodel import Session, select
    from app.arctime.gui import create_app
    from app.arctime import companion_llm, topic_segments
    from app.models_unified import UnifiedPublication
    from app.services.task_operations import request_cancel, set_admissions

    host, task_id = topic_host(tmp_path)
    client = TestClient(create_app(host.root, host=host))
    url = f"/companion-api/jobs/{task_id}"
    monkeypatch.setattr(
        companion_llm, "require_key", lambda *args: SecretStr("fixture-only")
    )
    identifier = client.post(url + "/topic-segments", json={}).json()["operation_id"]

    def cancelled_response(*args):
        with Session(host.engine) as session:
            request_cancel(session, identifier)
            session.commit()
        return '{"segments":[{"start_id":1,"end_id":1,"title":"title","summary":"summary"}]}'

    monkeypatch.setattr(topic_segments, "request_json", cancelled_response)
    with Session(host.engine) as session:
        set_admissions(session, paused=False)
        session.commit()
    # Given a provider reply racing cancellation, when dispatch finishes, then outcome remains uncertain and no late publication appears.
    host.executor.iteration(host.dispatch)
    result = client.get(url + "/topic-segments").json()
    assert result["state"] == "interrupted"
    assert result["error"] == "external_outcome_unknown_possible_repeat_charge"
    assert (
        client.post(f"/api/v2/operations/{identifier}/retry", json={}).status_code
        == 409
    )
    with Session(host.engine) as session:
        assert not session.exec(
            select(UnifiedPublication).where(
                UnifiedPublication.operation_id == identifier,
                UnifiedPublication.state == "committed",
            )
        ).all()
    assert not host.globals.keys("topics/profile-applied")
    client.close()


def test_topic_profile_is_frozen_and_publication_retry_applies_it_once(
    tmp_path: Path, monkeypatch
) -> None:
    import json
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from sqlmodel import Session
    from app.arctime.gui import create_app
    from app.arctime import companion_llm, topic_segments
    from app.services.topic_profiles import profile_identity, TopicProfile, load_profile
    from app.services.topic_admission import danmaku_store
    from app.services.task_operations import set_admissions, retry_operation
    from app.models_unified import UnifiedOperation

    # Given a streamer profile and a queued immutable snapshot.
    host, task_id = topic_host(tmp_path)
    client = TestClient(create_app(host.root, host=host))
    url = f"/companion-api/jobs/{task_id}"
    monkeypatch.setattr(
        companion_llm, "require_key", lambda *args: SecretStr("fixture-only")
    )
    calls = []

    def response(*args):
        calls.append(1)
        return '{"segments":[{"start_id":1,"end_id":1,"title":"title","summary":"summary"}]}'

    monkeypatch.setattr(topic_segments, "request_json", response)
    assert (
        client.post(
            url + "/danmaku",
            json={
                "streamer": "Fixture streamer",
                "content": "<i>"
                + "".join(f'<d p="{i}">特别名场面</d>' for i in range(1, 5))
                + "</i>",
            },
        ).status_code
        == 200
    )
    key, label = profile_identity(host, task_id, danmaku_store(host, task_id))
    with host.globals.mutation():
        host.globals.write(
            key,
            TopicProfile(label=label, terms={"Original": 2.0})
            .model_dump_json()
            .encode(),
        )
    identifier = client.post(url + "/topic-segments", json={}).json()["operation_id"]
    with Session(host.engine) as session:
        operation = session.get(UnifiedOperation, identifier)
        config = json.loads(operation.snapshot_json)["config"]
        assert config["topic_scoring"]["profile_terms"] == {"Original": 2.0}
        set_admissions(session, paused=False)
        session.commit()
    with host.globals.mutation():
        host.globals.write(
            key,
            TopicProfile(label=label, terms={"new profile": 3.0})
            .model_dump_json()
            .encode(),
        )

    def fail_commit(point):
        if point == "before_commit":
            raise OSError("fixture profile commit interruption")

    host.globals.fault = fail_commit
    # When publication succeeds but the profile commit fails, then retry reuses the published topic result and applies once.
    host.executor.iteration(host.dispatch)
    with Session(host.engine) as session:
        assert session.get(UnifiedOperation, identifier).state == "failed"
        retry_operation(session, identifier)
        session.commit()
    host.globals.fault = lambda point: None
    host.executor.iteration(host.dispatch)
    result = client.get(url + "/topic-segments").json()
    assert result["state"] == "completed" and calls == [1]
    assert "Original" in result["segments"][0]["hot_words"]
    profile = load_profile(host, key)
    assert (
        profile.sessions == 1
        and "特别名场面" in profile.terms
        and "new profile" in profile.terms
    )
    assert profile.terms["特别名场面"] == 4.0
    assert len(host.globals.keys("topics/profile-applied")) == 1
    assert client.get(url + "/subtitle-exports").json()["active"] is None
    client.close()


def test_legacy_topic_routes_require_unified_host(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from app.arctime.gui import create_app

    client = TestClient(create_app(tmp_path / "legacy"))
    # Given the compatibility-only entry point, when requesting topics, then no legacy background executor is started.
    for route in ("topic-segments", "topic-clips", "danmaku"):
        assert (
            client.get("/companion-api/jobs/abcdef123456/" + route).status_code == 409
        )
    client.close()


@pytest.mark.parametrize("iteration", range(5))
def test_running_topic_export_cancels_and_releases_real_process(
    tmp_path: Path, monkeypatch, iteration
) -> None:
    import threading
    import time
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from sqlmodel import Session, select
    from app.arctime.gui import create_app
    from app.arctime import companion_llm, topic_segments
    from app.models_unified import (
        OperationProcess,
        UnifiedOperation,
        UnifiedPublication,
    )
    from app.services.task_operations import set_admissions, request_cancel

    # Given admitted analysis and a real FFmpeg export in the unified executor.
    host, task_id = topic_host(tmp_path)
    client = TestClient(create_app(host.root, host=host))
    url = f"/companion-api/jobs/{task_id}"
    monkeypatch.setattr(
        companion_llm, "require_key", lambda *args: SecretStr("fixture-only")
    )
    monkeypatch.setattr(
        topic_segments,
        "request_json",
        lambda *args: (
            '{"segments":[{"start_id":1,"end_id":2,"title":"full","summary":"full"}]}'
        ),
    )
    client.post(url + "/topic-segments", json={})
    with Session(host.engine) as session:
        set_admissions(session, paused=False)
        session.commit()
    host.executor.iteration(host.dispatch)
    submitted = client.post(
        url + "/topic-clips", json={"indices": [0], "variant": "original"}
    )
    assert submitted.status_code == 202, submitted.text
    identifier = submitted.json()["operation_id"]
    thread = threading.Thread(target=lambda: host.executor.iteration(host.dispatch))
    thread.start()
    deadline = time.monotonic() + 10
    seen = False
    while thread.is_alive() and time.monotonic() < deadline:
        with Session(host.engine) as session:
            active = session.exec(
                select(OperationProcess).where(
                    OperationProcess.operation_id == identifier,
                    OperationProcess.released == False,
                )
            ).first()
            if active is not None:
                request_cancel(session, identifier)
                session.commit()
                seen = True
                break
        time.sleep(0.005)
    thread.join(timeout=10)
    # When cancellation arrives during an owned child process, then it is released without any late product commit.
    assert seen and not thread.is_alive()
    assert client.get(url + "/topic-clips").json()["state"] == "cancelled"
    with Session(host.engine) as session:
        assert session.get(UnifiedOperation, identifier).state == "cancelled"
        assert all(
            row.released
            for row in session.exec(
                select(OperationProcess).where(
                    OperationProcess.operation_id == identifier
                )
            ).all()
        )
        assert not session.exec(
            select(UnifiedPublication).where(
                UnifiedPublication.operation_id == identifier,
                UnifiedPublication.state == "committed",
            )
        ).all()
    client.close()


def test_unknown_streamers_do_not_share_profile_state(tmp_path: Path) -> None:
    from app.arctime.topic_models import DanmakuStore
    from app.services.topic_profiles import profile_identity

    host, task_id = topic_host(tmp_path)
    # Given no reliable owner identity, when resolving two tasks, then their accumulated profiles are isolated.
    assert (
        profile_identity(host, task_id, DanmakuStore())[0]
        != profile_identity(host, "0" * 32, DanmakuStore())[0]
    )


def test_audio_without_danmaku_keeps_score_unavailable() -> None:
    from app.arctime.topic_models import ScoringConfig, TopicSegment, TopicSegmentStore
    from app.arctime.topic_scoring import score_topics

    segment = TopicSegment(
        index=0,
        start_id=1,
        end_id=1,
        start_seconds=0,
        end_seconds=20,
        cue_count=1,
        title="audio only",
        summary="",
        preview="",
        loudness_db=-20.0,
        laugh_rate=10.0,
    )
    # Given audio without imported interaction data, when scoring, then the combined confidence stays unavailable.
    result = score_topics(
        TopicSegmentStore(audio_state="available", segments=[segment]),
        [],
        [],
        ScoringConfig(),
    )
    assert result.scoring == "unavailable" and result.segments[0].score is None
    assert result.audio_state == "available" and result.segments[0].loudness_db == -20.0


@pytest.mark.parametrize("later_error", [False, True])
def test_topic_cap_stops_paid_batches_and_reports_actual_coverage(
    tmp_path: Path, monkeypatch, later_error: bool
) -> None:
    import json
    from uuid import uuid4
    from pydantic import SecretStr
    from sqlmodel import Session
    from app.arctime import topic_segments
    from app.arctime.subtitle_document import Cue, SubtitleDocument
    from app.arctime.subtitle_style import SubtitleStyle
    from app.arctime.topic_models import TopicAnalyzeOptions
    from app.models_unified import UnifiedOperation
    from app.services.task_execution import Executor
    from app.services.task_operations import (
        bind_task,
        enqueue_operation,
        set_admissions,
    )
    from test_unified_operations import database

    # Given 2001 cues and one requested segment, the first batch already fills the output cap.
    engine = database(tmp_path)
    document = SubtitleDocument(
        source_fingerprint="0" * 64,
        revision=0,
        style=SubtitleStyle(),
        cues=[
            Cue(
                id=f"cue-{i + 1:06d}",
                start_seconds=float(i * 10),
                end_seconds=float((i + 1) * 10),
                text=f"cue {i + 1}",
            )
            for i in range(2001)
        ],
        width=320,
        height=180,
        duration=20010.0,
        fps=10.0,
    )
    with Session(engine) as session:
        binding = bind_task(
            session, uuid4(), "batch-cap", "generation", origin="native"
        )
        operation = enqueue_operation(
            session, binding.task_id, "analyze_topics", {"input": {}, "config": {}}
        )
        identifier = operation.id
        set_admissions(session, paused=False)
        session.commit()
    calls = []

    def response(model, key, prompt, content, requester):
        calls.append(len(json.loads(content)["segments"]))
        if len(calls) > 1 and later_error:
            raise OSError("unnecessary later provider call failed")
        return '{"segments":[{"start_id":1,"end_id":2,"title":"kept topic","summary":"kept summary"}]}'

    monkeypatch.setattr(topic_segments, "request_json", response)
    results = []

    def run(execution):
        results.append(
            topic_segments.analyze_document(
                execution,
                document,
                TopicAnalyzeOptions(max_segments=1),
                "deepseek-chat",
                SecretStr("fixture-only"),
                None,
            )
        )

    # When real unified external-call tracking executes analysis, then no later request or error can discard the completed capped result.
    Executor(engine, tmp_path / "tasks", tmp_path / "guard").iteration(run)
    assert calls == [2000]
    with Session(engine) as session:
        assert session.get(UnifiedOperation, identifier).state == "succeeded"
    assert len(results[0].segments) == 1
    assert (
        results[0].total_cues == 2001
        and results[0].covered_cues == 2000
        and results[0].truncated is True
    )


@pytest.mark.parametrize("max_segments", [1, 10])
def test_overlapping_topic_boundaries_fail_without_retitle_or_trim(
    tmp_path: Path, monkeypatch, max_segments: int
) -> None:
    from uuid import uuid4
    from pydantic import SecretStr
    from sqlmodel import Session
    from app.arctime import topic_segments
    from app.arctime.subtitle_document import Cue, SubtitleDocument
    from app.arctime.subtitle_style import SubtitleStyle
    from app.arctime.topic_models import TopicAnalyzeOptions, TopicError
    from app.models_unified import UnifiedOperation
    from app.services.task_execution import Executor
    from app.services.task_operations import (
        bind_task,
        enqueue_operation,
        set_admissions,
    )
    from test_unified_operations import database

    # Given overlapping model-selected topics, even a cap reached earlier in the same response must not hide invalid boundaries.
    engine = database(tmp_path)
    document = SubtitleDocument(
        source_fingerprint="0" * 64,
        revision=0,
        style=SubtitleStyle(),
        cues=[
            Cue(
                id=f"cue-{i + 1:06d}",
                start_seconds=float(i * 10),
                end_seconds=float((i + 1) * 10),
                text=f"cue {i + 1}",
            )
            for i in range(3)
        ],
        width=320,
        height=180,
        duration=30.0,
        fps=10.0,
    )
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), "overlap", "generation", origin="native")
        operation = enqueue_operation(
            session, binding.task_id, "analyze_topics", {"input": {}, "config": {}}
        )
        identifier = operation.id
        set_admissions(session, paused=False)
        session.commit()
    monkeypatch.setattr(
        topic_segments,
        "request_json",
        lambda *args: (
            '{"segments":[{"start_id":1,"end_id":2,"title":"first","summary":"first"},{"start_id":2,"end_id":3,"title":"second","summary":"second"}]}'
        ),
    )
    errors = []
    results = []

    def run(execution):
        try:
            results.append(
                topic_segments.analyze_document(
                    execution,
                    document,
                    TopicAnalyzeOptions(max_segments=max_segments),
                    "deepseek-chat",
                    SecretStr("fixture-only"),
                    None,
                )
            )
        except TopicError as error:
            errors.append(str(error))
            raise

    # When the response crosses the analysis boundary, then it fails rather than trimming the second title onto cue 3.
    Executor(engine, tmp_path / "tasks", tmp_path / "guard").iteration(run)
    assert not results and errors == ["模型切片边界越界或重叠"]
    with Session(engine) as session:
        assert session.get(UnifiedOperation, identifier).state == "failed"
