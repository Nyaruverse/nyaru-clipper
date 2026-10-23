from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from unification_fixtures import build_state, edit_cues, fixture_contract
from app.arctime.subtitle_templates import TemplateStore


def test_frozen_edit_fixture_has_5000_distinct_cues_within_media() -> None:
    contract = fixture_contract()
    cues = edit_cues()
    assert len(cues) == 5000
    assert len({cue.id for cue in cues}) == 5000
    assert all(round(cue.start_seconds * 1000) == i * 30 for i, cue in enumerate(cues))
    assert all(round((cue.end_seconds - cue.start_seconds) * 1000) == 20 for cue in cues)
    assert cues[-1].end_seconds < contract.media.frame_count / contract.media.fps
    assert cues[42].original_style is not None


def test_state_fixture_covers_both_instances_globals_and_rollback_levels(tmp_path: Path) -> None:
    bundle = build_state(tmp_path / 'candidate')
    assert len(bundle.sources) == 2
    for root in bundle.sources:
        assert (root / 'abcdef123456' / 'job.json').is_file()
        assert (root / '111111111111' / 'job.json').read_text() == '{broken'
        assert not (root / '222222222222' / 'source.mp4').exists()
        assert (root / '333333333333' / 'orphan.ass').is_file()
        assert json.loads((root / '444444444444' / 'job.json').read_bytes())['state'] == 'queued'
    for level in ('R0', 'R1', 'R2'):
        assert (bundle.root / 'rollback' / level / 'tasks' / 'abcdef123456' / 'job.json').is_file()
    store = TemplateStore(bundle.root / 'settings')
    defaults = store.load_studio_settings()
    template = next(template for template in store.list_styles() if template.id == defaults.default_template_id)
    assert template.arctime_template_id in {project.id for project in store.list_projects()}
    assert defaults.language == 'ja' and defaults.mode == 'saozi'
    assert (store.root / 'defaults.json').is_file()
    receipt = json.loads((bundle.root / 'fixture-receipt.json').read_bytes())
    assert receipt['status'] == 'fixture_only'
    assert 'SECRET_CANARY_NOT_REAL' not in json.dumps(receipt)
    assert receipt['protected_credential_reference'] is True
    for name, digest in receipt['files'].items():
        assert hashlib.sha256((bundle.root / name).read_bytes()).hexdigest() == digest
    assert all(not name.startswith('credentials/') for name in receipt['files'])


def test_fixture_builder_refuses_existing_output_without_changes(tmp_path: Path) -> None:
    root = tmp_path / 'protected'
    root.mkdir()
    (root / 'keep').write_text('keep')
    with pytest.raises(FileExistsError):
        build_state(root)
    assert list(root.iterdir()) == [root / 'keep']


def test_product_frame_and_roi_contract_is_fixed_before_export() -> None:
    product = fixture_contract().product
    assert product.sample_frames == (29, 30, 31, 60, 88, 89, 90)
    assert product.visible_frames == (30, 31, 60, 88, 89)
    assert product.roi == (0, 480, 1280, 240)
    assert product.cpu == {'video': 'libx264', 'preset': 'fast', 'crf': 20,
                           'audio': 'aac', 'container': 'mp4', 'movflags': '+faststart'}
    assert product.tolerance['rgb_rmse'] == 8.0


def test_frozen_directions_and_word_provenance_are_explicit(tmp_path: Path) -> None:
    bundle = build_state(tmp_path / 'directions')
    companion = bundle.sources[0] / 'abcdef123456'
    translation = json.loads((companion / 'translation.json').read_bytes())
    assert (translation['source_language'], translation['target_language']) == ('ja', 'zh')
    assert 'subtitles.ja-zh.srt' in translation['artifacts']
    assert json.loads((companion / 'transcript.json').read_bytes())['segments'][0]['words']
    workstation = bundle.root / 'workstation/same-legacy-id/work'
    transcript = json.loads((workstation / 'asr-segments.json').read_bytes())
    assert transcript['segments'][0]['words'][0]['confidence'] == .95
    bilingual = json.loads((workstation / 'subtitles.zh-ja.json').read_bytes())
    assert bilingual['model_metadata']['source_language'] == 'zh'
    assert bilingual['model_metadata']['target_language'] == 'ja'
    assert bilingual['segments'][0]['translated_text']
