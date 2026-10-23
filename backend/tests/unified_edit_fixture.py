from __future__ import annotations

import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlmodel import SQLModel, Session, create_engine

from app.arctime import media
from app.arctime.gui import create_app
from app.arctime.subtitle_document import DocumentStore
from app.arctime.subtitle_encoding import subtitle_ffmpeg
from app.arctime.subtitle_style import SubtitleStyle, TextStyle
from app.arctime.subtitle_templates import TemplateStore
from app.models import Artifact, Task
from app.services.subtitles import SubtitleSegment, SubtitleWord, write_bilingual_subtitle_outputs, write_subtitle_outputs
from app.services.task_artifacts import ResolvedArtifacts
from app.services.workstation_artifacts import snapshot_workstation


@dataclass(frozen=True, slots=True)
class EditorFixture:
    root: Path
    editor: Path
    artifacts: ResolvedArtifacts
    source_hashes: dict[str, str]

    def current_source_hashes(self) -> dict[str, str]:
        old = self.root / 'old-data'
        return {str(path.relative_to(old)): media.fingerprint(path)
                for path in sorted(old.rglob('*')) if path.is_file()}


def make_editor_fixture(root: Path, bundle: Path, *, stress: bool = False) -> EditorFixture:
    import shutil
    root.mkdir(mode=0o700)
    task_id = 'abcdef123456abcdef123456abcdef12'
    task_root = root / 'old-data/tasks' / task_id
    raw, work, exports = (task_root / name for name in ['raw', 'work', 'exports'])
    for directory in [raw, work, exports]:
        directory.mkdir(parents=True)
    shutil.copyfile(bundle / 'source.mp4', raw / 'source.mp4')
    if stress:
        segments = [SubtitleSegment(f'word-source-{i + 1}', i * .03, i * .03 + .02, f'原文 {i + 1}',
                    [SubtitleWord(f'原文 {i + 1}', i * .03, i * .03 + .02, .95)]) for i in range(5000)]
        translations = [f'翻訳 {i + 1}' for i in range(5000)]
    else:
        segments = [SubtitleSegment('word-source-1', 2., 4., 'Original fixture',
                    [SubtitleWord('Original fixture', 2., 4., .95)])]
        translations = ['統一テスト字幕']
    source_language = 'zh' if stress else 'en'
    transcript, subtitles = write_subtitle_outputs(work, segments,
        model_metadata={'engine': 'frozen-whisperx-format', 'language': source_language}, elapsed_seconds=1.)
    bilingual, _ = write_bilingual_subtitle_outputs(work, segments, translations,
        model_metadata={'source_language': source_language, 'target_language': 'ja', 'fixture_only': True}, elapsed_seconds=1.)
    clip = exports / 'clip-00001000-00006000.mp4'
    subprocess.run([subtitle_ffmpeg(), '-v', 'error', '-nostdin', '-n', '-ss', '1', '-i', str(raw / 'source.mp4'),
        '-t', '5', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-c:a', 'aac', '-movflags', '+faststart', str(clip)],
        check=True, capture_output=True, timeout=60)
    engine = create_engine('sqlite:///' + str(root / 'old-data/tasks.sqlite3'))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Task(id=task_id, source_url='https://fixture.invalid', normalized_source_url='https://fixture.invalid', status='success'))
        import json
        for kind, path, metadata in [
            ('source_video', raw / 'source.mp4', {}), ('transcript_json', transcript, {}),
            ('subtitle_srt', subtitles, {'language': source_language}), ('bilingual_transcript_json', bilingual, {}),
            ('clip_export', clip, {'start_s': 1., 'end_s': 6.}),
        ]:
            session.add(Artifact(task_id=task_id, stage_name='fixture', kind=kind,
                                 path=str(path), metadata_json=json.dumps(metadata)))
        session.commit()
        artifacts = snapshot_workstation(session, task_id=task_id, root=task_root,
            source_instance_id=UUID('00000000-0000-4000-8000-000000000001'))
    engine.dispose()
    editor = root / 'editor'
    defaults = SubtitleStyle(original=TextStyle(font='Arial', size=48., x=640., y=640.))
    TemplateStore(editor).save_defaults(defaults)
    if stress:
        directory = editor / artifacts.source.task_id
        directory.mkdir()
        store = DocumentStore(artifacts=lambda directory: artifacts)
        document = store.load(directory, defaults)
        cues = list(document.cues)
        cues[42] = cues[42].model_copy(update={'original_style': TextStyle(color='#00FF00')})
        store.save(directory, document.model_copy(update={'cues': cues}))
    fixture = EditorFixture(root, editor, artifacts, {})
    return EditorFixture(root, editor, artifacts, fixture.current_source_hashes())


def serve_editor_fixture(root: Path, bundle: Path, ready: Path, *, stress: bool = True) -> None:
    import uvicorn
    fixture = make_editor_fixture(root, bundle, stress=stress)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        app = create_app(fixture.editor, artifacts=(fixture.artifacts,))
        media.write_json(ready, {'url': f'http://127.0.0.1:{listener.getsockname()[1]}',
            'task_id': fixture.artifacts.source.task_id, 'fixture_only': True})
        uvicorn.Server(uvicorn.Config(app, log_level='warning')).run(sockets=[listener])
