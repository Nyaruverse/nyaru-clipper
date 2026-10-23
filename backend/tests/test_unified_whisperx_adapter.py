from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.models_unified import UnifiedOperation
from app.services.cache_identity import content_sha256
from app.services.subtitles import SubtitleSegment, SubtitleWord, render_srt
from app.services.task_execution import Execution, Executor
from app.services.task_operations import bind_task, enqueue_operation, set_admissions
from app.services.whisperx_adapter import WhisperXAdapter, WhisperXConfiguration
from test_unified_operations import database


def test_whisperx_adapter_rebases_validated_chunks_and_keeps_word_and_raw_alignment_data(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    model, alignment = tmp_path / 'cached-model', tmp_path / 'cached-alignment'
    model.mkdir()
    alignment.mkdir()
    (model / 'model.bin').write_bytes(b'fixture-model-identity')
    (alignment / 'config.json').write_text('{}')
    config = WhisperXConfiguration(settings={'whisperx_language': 'zh'}, model_ref=model, model_sha256=content_sha256(model),
        alignment_ref=alignment, alignment_sha256=content_sha256(alignment))
    video = tmp_path / '301-seconds.mp4'
    subprocess.run(['/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:r=1',
        '-f', 'lavfi', '-i', 'anullsrc=r=16000:cl=mono', '-t', '301', '-c:v', 'libx264', '-preset', 'ultrafast',
        '-c:a', 'aac', str(video)], check=True, capture_output=True, timeout=30)
    engine = database(tmp_path)
    with Session(engine) as session:
        binding = bind_task(session, uuid4(), 'whisperx', 'g', origin='native')
        operation = enqueue_operation(session, binding.task_id, 'process_recording', {})
        identifier = operation.id
        set_admissions(session, paused=False)
        session.commit()
    calls = []
    original = Execution.run_command

    def child(execution: Execution, command: list[str], **kwargs):
        if 'app.services.unified_asr_child' not in command:
            return original(execution, command, **kwargs)
        request = json.loads(Path(command[command.index('app.services.unified_asr_child') + 1]).read_bytes())
        folder = Path(request['work'])
        calls.append(folder.name)
        cue = SubtitleSegment('1', .1, .8, '原始词时间', [SubtitleWord('原始', .1, .4, .95)])
        (folder / 'asr-segments.json').write_text(json.dumps({'segments': [asdict(cue)]}))
        (folder / 'subtitles.zh.srt').write_text(render_srt([cue]))
        (folder / 'asr-alignment-raw.json').write_text(json.dumps({'segments': [{'text': 'raw alignment', 'words': [{'score': .95}]}]}))
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(Execution, 'run_command', child)

    def run(execution: Execution) -> None:
        directory = execution.staging('adapter-test')
        adapter = WhisperXAdapter(execution, config)
        segments = adapter.transcribe(video, directory, 301.)
        assert [(cue.start_seconds, cue.end_seconds) for cue in segments] == [(.1, .8), (300.1, 300.8)]
        assert segments[1].words[0].start_seconds == 300.1 and segments[1].words[0].confidence == .95
        assert adapter.transcribe(video, directory, 301.) == segments
        assert all(json.loads(path.read_bytes())['segments'][0]['words'][0]['score'] == .95
            for path in directory.rglob('asr-alignment-raw.json'))
        result = directory / 'merged.json'
        result.write_text(json.dumps([asdict(cue) for cue in segments]))
        execution.publish('test-merged', {'transcript': result})

    Executor(engine, tmp_path / 'tasks', tmp_path / 'guard').iteration(run)
    assert calls == ['chunk-0000', 'chunk-0001']
    with Session(engine) as session:
        assert session.get(UnifiedOperation, identifier).state == 'succeeded'
