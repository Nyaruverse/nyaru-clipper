from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class FontCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)
    available: bool
    families: tuple[str, ...] = ()


def _macos_families() -> list[str]:
    core_text = ctypes.CDLL('/System/Library/Frameworks/CoreText.framework/CoreText')
    foundation = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    core_text.CTFontManagerCopyAvailableFontFamilyNames.argtypes = []
    core_text.CTFontManagerCopyAvailableFontFamilyNames.restype = ctypes.c_void_p
    foundation.CFArrayGetCount.argtypes = [ctypes.c_void_p]
    foundation.CFArrayGetCount.restype = ctypes.c_long
    foundation.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
    foundation.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
    foundation.CFStringGetLength.argtypes = [ctypes.c_void_p]
    foundation.CFStringGetLength.restype = ctypes.c_long
    foundation.CFStringGetMaximumSizeForEncoding.argtypes = [ctypes.c_long, ctypes.c_uint32]
    foundation.CFStringGetMaximumSizeForEncoding.restype = ctypes.c_long
    foundation.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char), ctypes.c_long, ctypes.c_uint32]
    foundation.CFStringGetCString.restype = ctypes.c_bool
    foundation.CFRelease.argtypes = [ctypes.c_void_p]
    foundation.CFRelease.restype = None
    array = core_text.CTFontManagerCopyAvailableFontFamilyNames()
    if not array:
        raise ValueError('CoreText font catalog unavailable')
    try:
        names = []
        for index in range(foundation.CFArrayGetCount(array)):
            string = foundation.CFArrayGetValueAtIndex(array, index)
            length = foundation.CFStringGetLength(string)
            capacity = foundation.CFStringGetMaximumSizeForEncoding(length, 0x08000100) + 1
            if capacity <= 0:
                raise ValueError('Invalid CoreText font family length')
            buffer = ctypes.create_string_buffer(capacity)
            if not foundation.CFStringGetCString(string, buffer, capacity, 0x08000100):
                raise ValueError('CoreText font family conversion failed')
            names.append(buffer.value.decode('utf-8'))
        return names
    finally:
        # Array elements are borrowed references; releasing the copied array releases them.
        foundation.CFRelease(array)


def _windows_families() -> list[str]:
    """用 fontTools 读取系统字体文件的 name 表，收集 family 名（中英文都收录，浏览器/ASS 均可按名解析）。"""
    from fontTools.ttLib import TTCollection, TTFont

    directories = [Path('C:/Windows/Fonts'), Path.home() / 'AppData' / 'Local' / 'Microsoft' / 'Windows' / 'Fonts']
    names: set[str] = set()
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() not in {'.ttf', '.otf', '.ttc'}:
                continue
            try:
                if path.suffix.lower() == '.ttc':
                    fonts = TTCollection(str(path), lazy=True).fonts
                else:
                    fonts = [TTFont(str(path), lazy=True)]
                for font in fonts:
                    table = font['name']
                    # 优先排版 family(16)，回退 family(1)；中文(0x0804)与英文(0x0409)名称都收录
                    for name_id in (16, 1):
                        records = [table.getName(name_id, 3, 1, 0x0804), table.getName(name_id, 3, 1, 0x0409)]
                        found = False
                        for record in records:
                            if record is None:
                                continue
                            value = record.toUnicode().strip()
                            if value:
                                names.add(value)
                                found = True
                        if found:
                            break
            except Exception:
                continue
    return list(names)


@lru_cache(maxsize=1)
def font_catalog() -> FontCatalog:
    try:
        if sys.platform == 'darwin':
            names = _macos_families()
        elif sys.platform.startswith('linux'):
            binary = shutil.which('fc-list')
            if binary is None:
                return FontCatalog(available=False)
            result = subprocess.run([binary, '--format', '%{family}\n'], capture_output=True, text=True,
                                    timeout=10, check=True)
            names = [name for line in result.stdout.splitlines() for name in line.split(',')]
        elif sys.platform == 'win32':
            names = _windows_families()
        else:
            return FontCatalog(available=False)
    except (ImportError, OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return FontCatalog(available=False)
    return FontCatalog(available=True, families=tuple(sorted({name.strip() for name in names if name.strip()}, key=str.casefold)))
