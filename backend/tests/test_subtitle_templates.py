import json
import stat

import pytest

from app.arctime.subtitle_style import SubtitleStyle, TextStyle
from app.arctime.subtitle_templates import TemplateStore


def test_nyaru_is_builtin_default_without_changing_saved_custom_style(tmp_path):
    store = TemplateStore(tmp_path)
    builtin = next(item for item in store.list_styles() if item.id == 'nyaru')
    assert builtin.builtin
    assert store.load_defaults() == builtin.style
    assert builtin.style.original.font == 'Hiragino Maru Gothic ProN'
    assert builtin.style.translation.color == '#A0F5DA'
    assert builtin.style.translation.size == 64
    with pytest.raises(ValueError):
        store.delete_style('nyaru')
    custom = SubtitleStyle(original=TextStyle(size=77))
    store.save_defaults(custom)
    assert TemplateStore(tmp_path).load_defaults() == custom


def test_defaults_persist_privately(tmp_path):
    store = TemplateStore(tmp_path)
    style = SubtitleStyle(original=TextStyle(size=72))
    store.save_defaults(style)
    assert TemplateStore(tmp_path).load_defaults() == style
    assert stat.S_IMODE((tmp_path / 'templates/defaults.json').stat().st_mode) == 0o600


def test_style_rename_copy_import_delete(tmp_path):
    store = TemplateStore(tmp_path)
    first = store.save_style('First', SubtitleStyle())
    renamed = store.save_style('Renamed', first.style, template_id=first.id)
    assert renamed.id == first.id
    copied = store.save_style('Copy', renamed.style)
    assert copied.id != first.id
    payload = json.loads(store.download_style(first.id))
    payload['name'] = 'Imported'
    imported = store.import_style(json.dumps(payload).encode())
    assert imported.style == first.style
    store.delete_style(first.id)
    assert first.id not in [item.id for item in store.list_styles()]


def test_collisions_builtin_and_corruption_fail(tmp_path):
    store = TemplateStore(tmp_path)
    store.save_style('Name', SubtitleStyle())
    with pytest.raises(ValueError):
        store.save_style('name', SubtitleStyle())
    with pytest.raises(ValueError):
        store.delete_style('default')
    with pytest.raises(ValueError):
        store.save_style('New', SubtitleStyle(), template_id='default')
    with pytest.raises(ValueError):
        store.import_style(b'{"style": {"version": 99}}')
    (tmp_path / 'templates/defaults.json').write_text('broken')
    with pytest.raises(ValueError):
        store.load_defaults()


def test_project_bytes_binding_and_deletion(tmp_path):
    store = TemplateStore(tmp_path)
    content = b'opaque\x00project'
    project = store.save_project('Native', 'native.atpj', content)
    style = store.save_style('Linked', SubtitleStyle(), project.id)
    assert TemplateStore(tmp_path).download_project(project.id) == content
    with pytest.raises(ValueError):
        store.delete_project(project.id)
    assert store.list_styles()[-1].arctime_template_id == project.id
    store.delete_style(style.id)
    store.delete_project(project.id)
    assert store.list_projects() == []


@pytest.mark.parametrize('target', ['templates', 'templates/defaults.json', 'templates/styles'])
def test_symlinks_rejected(tmp_path, target):
    store = TemplateStore(tmp_path)
    outside = tmp_path / 'outside'
    outside.mkdir()
    path = tmp_path / target
    if path.exists():
        path.rename(tmp_path / 'previous')
    path.symlink_to(outside)
    with pytest.raises(ValueError):
        store.load_defaults() if target.endswith('json') else store.list_styles()


def test_project_size_extension_and_tampering(tmp_path):
    store = TemplateStore(tmp_path)
    with pytest.raises(ValueError):
        store.save_project('Bad', 'bad.txt', b'x')
    with pytest.raises(ValueError):
        store.save_project('Large', 'large.atpj', b'x' * (16 * 1024 * 1024 + 1))
    project = store.save_project('Good', 'good.atpj', b'original')
    (tmp_path / 'templates/projects' / f'{project.id}.atpj').write_bytes(b'tamper')
    with pytest.raises(ValueError):
        store.download_project(project.id)


def test_rename_preserves_binding_when_omitted(tmp_path):
    store = TemplateStore(tmp_path)
    project = store.save_project('Native', 'native.atpj', b'project')
    original = store.save_style('Linked', SubtitleStyle(), project.id)
    renamed = store.save_style('Renamed', original.style, template_id=original.id)
    assert renamed.arctime_template_id == project.id
    unlinked = store.save_style('Renamed', original.style, None, original.id)
    assert unlinked.arctime_template_id is None


@pytest.mark.parametrize('extension', ['json', 'atpj'])
def test_project_symlink_rejected(tmp_path, extension):
    store = TemplateStore(tmp_path)
    project = store.save_project('Native', 'native.atpj', b'project')
    target = tmp_path / 'templates/projects' / f'{project.id}.{extension}'
    original = tmp_path / f'original.{extension}'
    target.rename(original)
    target.symlink_to(original)
    with pytest.raises(ValueError):
        store.download_project(project.id)


def test_dangling_project_binding_fails_visibly(tmp_path):
    store = TemplateStore(tmp_path)
    project = store.save_project('Native', 'native.atpj', b'project')
    store.save_style('Linked', SubtitleStyle(), project.id)
    (tmp_path / 'templates/projects' / f'{project.id}.atpj').unlink()
    with pytest.raises(FileNotFoundError):
        store.list_styles()


def test_corrupt_project_metadata_fails_visibly(tmp_path):
    store = TemplateStore(tmp_path)
    project = store.save_project('Native', 'native.atpj', b'project')
    (tmp_path / 'templates/projects' / f'{project.id}.json').write_text('{}')
    with pytest.raises(ValueError):
        store.list_projects()
