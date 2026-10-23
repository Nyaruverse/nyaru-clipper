from pathlib import Path
from types import ModuleType
import sys

import pytest

from app.arctime.engine_readiness import language_data_ready, whisperx_missing
from app.settings import Settings


def test_offline_language_assets_are_checked_without_downloading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = ModuleType('nltk.data')
    def missing(path: str):
        assert path == 'tokenizers/punkt_tab/english/'
        raise LookupError(path)
    data.find = missing
    monkeypatch.setitem(sys.modules, 'nltk', ModuleType('nltk'))
    monkeypatch.setitem(sys.modules, 'nltk.data', data)
    monkeypatch.setattr('importlib.util.find_spec', lambda name: name == 'whisperx')
    models = tmp_path / 'models'
    models.mkdir()
    (models / 'model.bin').write_bytes(b'fixture-only')
    (models / 'config.json').write_text('{}')
    settings = Settings(whisperx_model_name=str(models), whisperx_alignment_model_name=str(models))
    assert not language_data_ready()
    assert whisperx_missing([], settings) == ['WhisperX 本地断句数据（punkt_tab）']
    data.find = lambda path: models
    assert language_data_ready()
    assert whisperx_missing([], settings) == []
