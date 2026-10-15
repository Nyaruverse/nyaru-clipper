import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from app.arctime import media, saozi_translation, translation
from app.services.subtitles import SubtitleSegment, render_srt

KEY = SecretStr('test-secret')


def source(directory, count=2, text='こんにちは'):
    directory.mkdir(exist_ok=True)
    cues = [SubtitleSegment(i + 1, i * 2, i * 2 + 1, text + str(i)) for i in range(count)]
    (directory / 'subtitles.srt').write_text(render_srt(cues))
    job = {'version': 2, 'state': 'completed', 'subtitles': 'subtitles.srt',
           'artifacts': {'subtitles.srt': media.fingerprint(directory / 'subtitles.srt')},
           'selection': [{'start': 0, 'end': 2}], 'completed_clips': [{'video': 'clip-001.mp4'}]}
    media.write_json(directory / 'job.json', job)
    return cues


def api(calls, fail=False):
    def handler(request):
        payload = json.loads(request.content)
        rows = json.loads(payload['messages'][1]['content'])['segments']
        calls.append(rows)
        if fail:
            return httpx.Response(401)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'segments': [{'id': r['id'], 'zh': '译文' + str(r['id'])} for r in rows]})}}]})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_append_retry_and_final(tmp_path):
    calls = []
    source(tmp_path)
    state = saozi_translation.translate(tmp_path, KEY, final=False, client=api(calls))
    assert state['state'] == 'partial' and state['done'] == 2
    clip = (tmp_path / 'clip-001.ja-zh.srt').read_bytes()
    clip_mtime = (tmp_path / 'clip-001.ja-zh.srt').stat().st_mtime_ns
    source(tmp_path, 3)
    with pytest.raises(ValueError, match='API Key'):
        saozi_translation.translate(tmp_path, KEY, final=False, client=api(calls, True))
    failed = json.loads((tmp_path / 'translation.json').read_text())
    assert failed['state'] == 'failed' and failed['done'] == 2 and failed['artifacts']
    state = saozi_translation.translate(tmp_path, KEY, client=api(calls))
    assert state['state'] == 'completed' and state['done'] == state['total'] == 3
    assert [[r['id'] for r in batch] for batch in calls] == [[1, 2], [3], [3]]
    assert (tmp_path / 'clip-001.ja-zh.srt').read_bytes() == clip
    assert (tmp_path / 'clip-001.ja-zh.srt').stat().st_mtime_ns == clip_mtime
    assert '译文3' in (tmp_path / 'subtitles.ja-zh.srt').read_text()


def test_exact_v1_reuse(tmp_path):
    old, new = tmp_path / 'old', tmp_path / 'new'
    source(old)
    source(new)
    translation.translate_run(old, KEY, client=api([]))
    before = (old / 'translation.json').read_bytes()
    calls = []
    state = saozi_translation.translate(new, KEY, reuse_from=old, client=api(calls))
    assert state['state'] == 'completed' and state['done'] == 2 and calls == []
    assert (old / 'translation.json').read_bytes() == before
    assert (old / 'subtitles.ja-zh.srt').read_bytes() == (new / 'subtitles.ja-zh.srt').read_bytes()


@pytest.mark.parametrize('damage', ['cue', 'rows', 'artifact', 'symlink'])
def test_reuse_rejects_corruption(tmp_path, damage):
    old, new = tmp_path / 'old', tmp_path / 'new'
    source(old)
    source(new)
    translation.translate_run(old, KEY, client=api([]))
    if damage == 'cue':
        source(new, text='changed')
    elif damage == 'rows':
        state = json.loads((old / 'translation.json').read_text())
        state['batches'][0]['rows'].reverse()
        media.write_json(old / 'translation.json', state)
    elif damage == 'artifact':
        (old / 'subtitles.ja-zh.srt').write_text('changed')
    else:
        path = old / 'clip-001.ja-zh.srt'
        path.unlink()
        path.symlink_to(old / 'subtitles.ja-zh.srt')
    calls = []
    with pytest.raises(ValueError):
        saozi_translation.translate(new, KEY, reuse_from=old, client=api(calls))
    assert calls == [] and not (new / 'subtitles.ja-zh.srt').exists()


@pytest.mark.parametrize('damage', ['cue', 'rows', 'artifact', 'symlink', 'source_hash'])
def test_incremental_rejects_corruption(tmp_path, damage):
    source(tmp_path)
    saozi_translation.translate(tmp_path, KEY, final=False, client=api([]))
    if damage == 'cue':
        source(tmp_path, text='changed')
    elif damage == 'rows':
        state = json.loads((tmp_path / 'translation.json').read_text())
        state['batches'][0]['rows'].reverse()
        media.write_json(tmp_path / 'translation.json', state)
    elif damage == 'artifact':
        (tmp_path / 'subtitles.ja-zh.srt').write_text('changed')
    elif damage == 'source_hash':
        (tmp_path / 'subtitles.srt').write_text('changed')
    else:
        path = tmp_path / 'clip-001.ja-zh.srt'
        path.unlink()
        path.symlink_to(tmp_path / 'subtitles.ja-zh.srt')
    calls = []
    with pytest.raises(ValueError):
        saozi_translation.translate(tmp_path, KEY, client=api(calls))
    assert calls == []


def test_silence_requires_no_provider_request(tmp_path):
    source(tmp_path, 0)
    calls = []
    result = saozi_translation.translate(tmp_path, KEY, client=api(calls))
    assert calls == [] and result['state'] == 'completed'
    assert (tmp_path / 'subtitles.ja-zh.srt').read_text() == ''


def test_batch_failure_keeps_finished_clip_and_resumes(tmp_path):
    source(tmp_path, 41)
    calls = []
    good = api(calls)
    def handler(request):
        if len(calls) == 1:
            return httpx.Response(402)
        return good.send(request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match='余额不足'):
            saozi_translation.translate(tmp_path, KEY, final=False, client=client)
    state = json.loads((tmp_path / 'translation.json').read_text())
    assert state['done'] == 40 and state['state'] == 'failed'
    assert 'clip-001.ja-zh.srt' in state['artifacts']
    assert len(media.read_subtitles(tmp_path / 'subtitles.ja-zh.srt')) == 40
    state = saozi_translation.translate(tmp_path, KEY, client=api(calls))
    assert state['done'] == 41 and [r['id'] for r in calls[-1]] == [41]
    assert len(calls) == 2


def test_prompt_and_existing_lock(tmp_path):
    from app.arctime import workflow
    source(tmp_path, text='大家好')
    calls = []
    good = api(calls)
    def handler(request):
        assert json.loads(request.content)['messages'][0]['content'] == saozi_translation.PROMPT
        return good.send(request)
    with workflow.exclusive_lock(tmp_path / '.lock'):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            state = saozi_translation.translate(tmp_path, KEY, client=client, locked=True)
    assert state['state'] == 'completed' and len(calls) == 1


def test_tamper_during_request_preserved(tmp_path):
    source(tmp_path)
    calls = []
    good = api(calls)
    def handler(request):
        (tmp_path / 'subtitles.ja-zh.srt').write_text('user edit')
        return good.send(request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match='内容不同'):
            saozi_translation.translate(tmp_path, KEY, client=client)
    assert (tmp_path / 'subtitles.ja-zh.srt').read_text() == 'user edit'


def test_new_clip_from_cached_cues_without_request(tmp_path):
    source(tmp_path)
    saozi_translation.translate(tmp_path, KEY, final=False, client=api([]))
    job = json.loads((tmp_path / 'job.json').read_text())
    job['selection'].append({'start': 2, 'end': 4})
    job['completed_clips'].append({'video': 'clip-002.mp4'})
    media.write_json(tmp_path / 'job.json', job)
    calls = []
    state = saozi_translation.translate(tmp_path, KEY, client=api(calls))
    assert calls == [] and state['state'] == 'completed'
    assert 'clip-002.ja-zh.srt' in state['artifacts']
    cue = media.read_subtitles(tmp_path / 'clip-002.ja-zh.srt')[0]
    assert cue.start_seconds == 0 and cue.text.endswith('译文2')


def test_first_failure_does_not_advertise_empty_global(tmp_path):
    source(tmp_path)
    with pytest.raises(ValueError):
        saozi_translation.translate(tmp_path, KEY, client=api([], True))
    state = json.loads((tmp_path / 'translation.json').read_text())
    assert state['state'] == 'failed' and 'subtitles.ja-zh.srt' not in state['artifacts']
    assert not (tmp_path / 'subtitles.ja-zh.srt').exists()


def test_existing_v1_translation_can_be_retried_under_live_lock(tmp_path):
    from app.arctime import workflow
    source(tmp_path)
    translation.translate_run(tmp_path, KEY, client=api([]))
    before = {p.name: media.fingerprint(p) for p in tmp_path.iterdir() if p.is_file()}
    calls = []
    with workflow.exclusive_lock(tmp_path / '.lock'):
        result = saozi_translation.translate(tmp_path, KEY, client=api(calls), locked=True)
    assert result['state'] == 'completed' and calls == []
    assert all(media.fingerprint(tmp_path / name) == digest for name, digest in before.items())


def test_publication_checkpoint_gap_preserves_files_with_readable_error(tmp_path):
    source(tmp_path)
    saozi_translation.translate(tmp_path, KEY, final=False, client=api([]))
    previous = (tmp_path / 'translation.json').read_bytes()
    source(tmp_path, 3)
    saozi_translation.translate(tmp_path, KEY, client=api([]))
    published = (tmp_path / 'subtitles.ja-zh.srt').read_bytes()
    (tmp_path / 'translation.json').write_bytes(previous)
    calls = []
    with pytest.raises(ValueError, match='已生成的双语字幕发生变化；保留文件，请检查任务'):
        saozi_translation.translate(tmp_path, KEY, client=api(calls))
    assert calls == [] and (tmp_path / 'subtitles.ja-zh.srt').read_bytes() == published
    assert (tmp_path / 'translation.json').read_bytes() == previous
