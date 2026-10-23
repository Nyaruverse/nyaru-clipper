from __future__ import annotations

import importlib.util
from pathlib import Path

from app.services.asr_whisperx import _alignment_model_target_dir, _main_model_target_dir
from app.settings import Settings, get_settings


def whisperx_missing(common: list[str], settings: Settings | None = None) -> list[str]:
    missing = [item for item in common if item not in {'whisper-cli', '本地 Whisper 模型'}]
    if importlib.util.find_spec('whisperx') is None:
        missing.append('WhisperX 运行库')
    elif not language_data_ready():
        missing.append('WhisperX 本地断句数据（punkt_tab）')
    settings = settings or get_settings()
    model = Path(settings.whisperx_model_name or '')
    if not model.is_dir():
        model = _main_model_target_dir(settings)
    alignment = Path(settings.whisperx_alignment_model_name or '')
    if not settings.whisperx_alignment_model_name or not alignment.is_dir():
        alignment = _alignment_model_target_dir(settings)
    if not (model / 'model.bin').is_file():
        missing.append('WhisperX 本地模型缓存')
    if not (alignment / 'config.json').is_file():
        missing.append('WhisperX 本地对齐缓存')
    return missing


def language_data_ready() -> bool:
    try:
        from nltk.data import find
        find('tokenizers/punkt_tab/english/')
        return True
    except (ImportError, LookupError):
        return False
