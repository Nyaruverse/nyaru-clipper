import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.arctime.gui import create_app


def test_font_catalog_endpoint_is_read_only_and_reports_unknown_font(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.get('/companion-api/subtitle-fonts')
        assert response.status_code == 200, response.text
        catalog = response.json()
        assert set(catalog) == {'available', 'families'}
        assert type(catalog['available']) is bool
        assert isinstance(catalog['families'], list)
        assert all(isinstance(name, str) and name.strip() for name in catalog['families'])
        assert 'NyaruDefinitelyAbsentFont_71d608b4' not in catalog['families']
        assert client.get('/companion-api/subtitle-fonts').json() == catalog
        assert not (tmp_path / 'config.json').exists()
        (tmp_path / 'font-catalog-response.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2))


@pytest.mark.skipif(sys.platform != 'darwin', reason='Requires actual macOS CoreText catalog')
def test_actual_macos_catalog_includes_arial(tmp_path):
    from app.arctime.subtitle_fonts import font_catalog
    font_catalog.cache_clear()
    result = font_catalog()
    assert result.available is True
    assert 'Arial' in result.families
    assert len(result.families) == len(set(result.families))
    (tmp_path / 'macos-font-catalog.json').write_text(result.model_dump_json(indent=2))


def test_cached_discovery_runs_once(monkeypatch):
    from app.arctime import subtitle_fonts
    calls = []
    monkeypatch.setattr(subtitle_fonts.sys, 'platform', 'darwin')
    monkeypatch.setattr(subtitle_fonts, '_macos_families', lambda: calls.append('called') or ['Arial', 'Arial', '日本語'])
    subtitle_fonts.font_catalog.cache_clear()
    try:
        first = subtitle_fonts.font_catalog()
        assert subtitle_fonts.font_catalog() is first
        assert calls == ['called']
        assert set(first.families) == {'Arial', '日本語'}
    finally:
        subtitle_fonts.font_catalog.cache_clear()


def test_linux_catalog_decodes_aliases_and_never_runs_shell(monkeypatch):
    from app.arctime import subtitle_fonts
    monkeypatch.setattr(subtitle_fonts.sys, 'platform', 'linux')
    monkeypatch.setattr(subtitle_fonts.shutil, 'which', lambda name: '/usr/bin/fc-list' if name == 'fc-list' else None)
    commands = []
    def run(command, **kwargs):
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, 'Arial,Arial MT\nNoto Sans CJK JP\nArial\n', '')
    monkeypatch.setattr(subtitle_fonts.subprocess, 'run', run)
    subtitle_fonts.font_catalog.cache_clear()
    try:
        catalog = subtitle_fonts.font_catalog()
        assert catalog.available and set(catalog.families) == {'Arial', 'Arial MT', 'Noto Sans CJK JP'}
        assert commands[0][0][0] == '/usr/bin/fc-list'
        assert commands[0][1]['timeout'] == 10 and not commands[0][1].get('shell', False)
    finally:
        subtitle_fonts.font_catalog.cache_clear()


@pytest.mark.parametrize('platform', ['win32', 'linux'])
def test_unsupported_or_missing_catalog_reports_unavailable(monkeypatch, platform):
    from app.arctime import subtitle_fonts
    monkeypatch.setattr(subtitle_fonts.sys, 'platform', platform)
    monkeypatch.setattr(subtitle_fonts.shutil, 'which', lambda name: None)
    subtitle_fonts.font_catalog.cache_clear()
    try:
        assert subtitle_fonts.font_catalog().model_dump(mode='json') == {'available': False, 'families': []}
    finally:
        subtitle_fonts.font_catalog.cache_clear()


def test_system_discovery_failure_is_visible_as_unavailable(monkeypatch):
    from app.arctime import subtitle_fonts
    monkeypatch.setattr(subtitle_fonts.sys, 'platform', 'darwin')
    def unavailable():
        raise OSError('CoreText unavailable')
    monkeypatch.setattr(subtitle_fonts, '_macos_families', unavailable)
    subtitle_fonts.font_catalog.cache_clear()
    try:
        assert subtitle_fonts.font_catalog().model_dump(mode='json') == {'available': False, 'families': []}
    finally:
        subtitle_fonts.font_catalog.cache_clear()


@pytest.mark.parametrize('convert', [True, False])
def test_corefoundation_array_released_on_success_and_conversion_failure(monkeypatch, convert):
    from types import SimpleNamespace
    from app.arctime import subtitle_fonts
    released = []
    def copy():
        return 101
    def count(array):
        assert array == 101
        return 1
    def element(array, index):
        assert (array, index) == (101, 0)
        return 202
    def length(string):
        assert string == 202
        return 3
    def capacity(length, encoding):
        assert encoding == 0x08000100
        return 12
    def cstring(string, buffer, size, encoding):
        assert string == 202 and size == 13
        buffer.value = '日本語'.encode()
        return convert
    def release(reference):
        released.append(reference)
    text = SimpleNamespace(CTFontManagerCopyAvailableFontFamilyNames=copy)
    foundation = SimpleNamespace(CFArrayGetCount=count, CFArrayGetValueAtIndex=element,
        CFStringGetLength=length, CFStringGetMaximumSizeForEncoding=capacity,
        CFStringGetCString=cstring, CFRelease=release)
    monkeypatch.setattr(subtitle_fonts.ctypes, 'CDLL', lambda path: text if 'CoreText' in path else foundation)
    if convert:
        assert subtitle_fonts._macos_families() == ['日本語']
    else:
        with pytest.raises(ValueError, match='conversion'):
            subtitle_fonts._macos_families()
    assert released == [101]
