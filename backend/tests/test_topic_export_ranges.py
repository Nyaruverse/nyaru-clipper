from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import JsonValue, ValidationError
from test_unified_topics import topic_host

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost
    from fastapi.testclient import TestClient


@pytest.fixture
def analyzed_topics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[NativeHost, str, TestClient]]:
    from app.arctime import companion_llm, topic_segments
    from app.arctime.gui import create_app
    from app.services.task_operations import set_admissions
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from sqlmodel import Session

    host, task_id = topic_host(tmp_path)
    context = host.context(task_id)
    assert context is not None
    base = context.document(host.templates.load_defaults())
    document = base.model_copy(
        update={
            "cues": [
                base.cues[0].model_copy(update={"translation": "第一段译文"}),
                base.cues[1],
            ]
        }
    )
    host.documents.save(task_id, document, base=base)
    monkeypatch.setattr(
        companion_llm, "require_key", lambda *_args: SecretStr("fixture-only")
    )
    monkeypatch.setattr(
        topic_segments,
        "request_json",
        lambda *_args: (
            '{"segments":[{"start_id":1,"end_id":1,"title":"first","summary":"first"},{"start_id":2,"end_id":2,"title":"second","summary":"second"}]}'
        ),
    )
    with TestClient(create_app(host.root, host=host)) as client:
        response = client.post(
            f"/companion-api/jobs/{task_id}/topic-segments", json={"max_segments": 2}
        )
        assert response.status_code == 202, response.text
        with Session(host.engine) as session:
            set_admissions(session, paused=False)
            session.commit()
        assert host.executor.iteration(host.dispatch) == response.json()["operation_id"]
        yield host, task_id, client


def test_range_options_preserve_selection_and_freeze_boundaries() -> None:
    from app.arctime.topic_models import TopicClipOptions

    # Given reordered selection and one optional override.
    body = {
        "indices": [1, 0],
        "ranges": [{"index": 0, "start_seconds": 0, "end_seconds": 10}],
    }
    # When parsed, then defaults and selection order survive and range values are frozen.
    options = TopicClipOptions.model_validate(body)
    assert options.indices == [1, 0]
    assert options.ranges[0].end_seconds == 10
    with pytest.raises(ValidationError):
        options.ranges[0].end_seconds = 11
    assert TopicClipOptions(indices=[0]).ranges == []


@pytest.mark.parametrize(
    "ranges",
    [
        [{"index": index, "start_seconds": 0, "end_seconds": 10}]
        for index in (-1, 100, True, "0", 0.0, 1)
    ]
    + [
        [{"index": 0, "start_seconds": start, "end_seconds": end}]
        for start, end in (
            (-1, 10),
            (10, 10),
            (11, 10),
            (float("nan"), 10),
            (0, float("inf")),
        )
    ]
    + [[{"index": 0, "start_seconds": 0, "end_seconds": 10}] * 2],
)
def test_range_options_reject_invalid_boundaries_or_indices(ranges: JsonValue) -> None:
    from app.arctime.topic_models import TopicClipOptions

    # Given invalid boundaries, duplicate indices or an unselected override.
    # When parsed, then the request cannot cross the typed boundary.
    with pytest.raises(ValidationError):
        TopicClipOptions.model_validate({"indices": [0], "ranges": ranges})


def test_range_export_trims_real_media_in_selection_order(
    analyzed_topics: tuple[NativeHost, str, TestClient], tmp_path: Path
) -> None:
    from app.arctime import media
    from app.arctime.subtitle_encoding import subtitle_ffmpeg
    from app.models_unified import UnifiedOperation
    from sqlmodel import Session

    # Given a completed analysis with unchanged 20-second candidates.
    host, task_id, client = analyzed_topics
    url = f"/companion-api/jobs/{task_id}"
    analysis = client.get(url + "/topic-segments").json()
    # When reordered trimmed ranges are admitted and dispatched by the real queue.
    response = client.post(
        url + "/topic-clips",
        json={
            "indices": [1, 0],
            "mode": "combined",
            "variant": "original",
            "ranges": [
                {"index": 0, "start_seconds": 4, "end_seconds": 8},
                {"index": 1, "start_seconds": 25, "end_seconds": 31},
            ],
        },
    )
    assert response.status_code == 202, response.text
    identifier = response.json()["operation_id"]
    with Session(host.engine) as session:
        operation = session.get(UnifiedOperation, identifier)
        assert operation is not None
        frozen = json.loads(operation.snapshot_json)["config"]["topic_result"]
    assert [
        (row["start_seconds"], row["end_seconds"]) for row in frozen["segments"]
    ] == [(4, 8), (25, 31)]
    assert host.executor.iteration(host.dispatch) == identifier
    # Then analysis stays intact and downloaded media has the requested duration/order.
    assert client.get(url + "/topic-segments").json() == analysis
    clips = client.get(url + "/topic-clips").json()
    assert clips["state"] == "completed", clips
    assert [row["index"] for row in clips["items"]] == [1, 0]
    downloaded = client.get(clips["combined"]["url"])
    assert downloaded.status_code == 200
    video = tmp_path / "trimmed-combined.mp4"
    video.write_bytes(downloaded.content)
    probe = subprocess.run(
        [
            media.tool_path("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert float(json.loads(probe.stdout)["format"]["duration"]) == pytest.approx(
        10, abs=0.3
    )
    for second, blue in ((1, True), (7, False)):
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
        assert (pixel[2] > pixel[0]) == blue


def test_range_admission_preserves_duration_translation_and_stale_guards(
    analyzed_topics: tuple[NativeHost, str, TestClient],
) -> None:
    # Given only the first candidate has translated subtitles.
    host, task_id, client = analyzed_topics
    url = f"/companion-api/jobs/{task_id}"
    base_request = {"indices": [0], "variant": "bilingual"}
    for index, start, end, status in (
        (True, 0, 10, 422),
        (100, 0, 10, 422),
        (0, 10, 5, 422),
        (99, 0, 10, 409),
    ):
        response = client.post(
            url + "/topic-clips",
            json={
                "indices": [index],
                "variant": "original",
                "ranges": [
                    {"index": index, "start_seconds": start, "end_seconds": end}
                ],
            },
        )
        assert response.status_code == status, response.text
    # When an override expands into missing translation or beyond media duration.
    for end, message in ((21, "缺少翻译"), (41, "时长")):
        response = client.post(
            url + "/topic-clips",
            json={
                **base_request,
                "ranges": [{"index": 0, "start_seconds": 0, "end_seconds": end}],
            },
        )
        # Then admission preserves each existing safety boundary.
        assert response.status_code == 409, response.text
        assert message in response.text
    valid_request = {
        **base_request,
        "ranges": [{"index": 0, "start_seconds": 1, "end_seconds": 20}],
    }
    assert client.post(url + "/topic-clips", json=valid_request).status_code == 202
    context = host.context(task_id)
    assert context is not None
    base = context.document(host.templates.load_defaults())
    saved = host.documents.load(task_id, base)
    host.documents.save(task_id, saved, base=base)
    assert client.post(url + "/topic-clips", json=valid_request).status_code == 409
