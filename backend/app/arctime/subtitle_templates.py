import hashlib
from enum import Enum
import os
from pathlib import Path
import re
import tempfile
import threading
from uuid import uuid4
from typing import assert_never

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.arctime.subtitle_style import SubtitleStyle, TextStyle
from app.arctime.ass_import import inspect_ass


class _Binding(Enum):
    PRESERVE = 'preserve'


def nyaru_style() -> SubtitleStyle:
    return SubtitleStyle(
        original=TextStyle(font='Hiragino Maru Gothic ProN', size=44, color='#F7F3FF',
            outline_color='#2D2147', outline=3.5, background_color='#181325', margin=170,
            spacing=.2, shadow=1.1, shadow_color='#181325', max_width=90),
        translation=TextStyle(font='Noto Sans CJK SC', size=64, color='#A0F5DA',
            outline_color='#2D2147', outline=4.6, background_color='#181325', margin=80,
            bold=True, spacing=.6, line_height=1.15, shadow=1.8, shadow_color='#181325', max_width=90))


class StyleTemplate(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str
    name: str = Field(min_length=1, max_length=100)
    style: SubtitleStyle
    arctime_template_id: str | None = None
    builtin: bool = False

    @field_validator('name')
    @classmethod
    def safe_name(cls, value: str) -> str:
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError('Template name must be visible text without controls.')
        return value.strip()


class ProjectTemplate(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str
    name: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    size: int = Field(gt=0, le=16 * 1024 * 1024)


class TemplateStore:
    def __init__(self, root: Path):
        self.root = Path(root).absolute() / 'templates'
        self._lock = threading.RLock()
        self._check(self.root)
        for path in (self.root, self.root / 'styles', self.root / 'projects'):
            self._check(path)
            path.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _check(self, path: Path) -> Path:
        for part in (path, *path.parents):
            if part.is_symlink():
                raise ValueError(f'Symlink is not permitted in template storage: {part.name}')
        if not path.is_relative_to(self.root):
            raise ValueError('Template path is outside storage.')
        return path

    def _path(self, folder: str, template_id: str, extension: str = 'json') -> Path:
        if not re.fullmatch(r'[0-9a-f]{32}', template_id):
            raise ValueError('Invalid template identifier.')
        return self._check(self.root / folder / f'{template_id}.{extension}')

    def _write(self, path: Path, content: bytes) -> None:
        self._check(path)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.template-')
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            self._check(path)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def load_defaults(self) -> SubtitleStyle:
        path = self._check(self.root / 'defaults.json')
        return SubtitleStyle.model_validate_json(path.read_bytes()) if path.exists() else nyaru_style()

    def save_defaults(self, style: SubtitleStyle) -> SubtitleStyle:
        with self._lock:
            self._write(self.root / 'defaults.json', style.model_dump_json().encode())
        return style

    def list_styles(self) -> list[StyleTemplate]:
        directory = self._check(self.root / 'styles')
        result = [StyleTemplate(id='nyaru', name='猫雷 Nyaru｜薄荷电波·中日双语', style=nyaru_style(), builtin=True),
                  StyleTemplate(id='default', name='双语基础', style=SubtitleStyle(), builtin=True),
                  StyleTemplate(id='white', name='单语白字描边', style=SubtitleStyle(translation=TextStyle()), builtin=True)]
        for path in sorted(directory.glob('*.json')):
            item = StyleTemplate.model_validate_json(self._check(path).read_bytes())
            if path != self._path('styles', item.id) or item.builtin:
                raise ValueError('Stored style identity is corrupt.')
            if item.arctime_template_id:
                self.download_project(item.arctime_template_id)
            result.append(item)
        return result

    def save_style(self, name: str, style: SubtitleStyle, arctime_template_id: str | None | _Binding = _Binding.PRESERVE,
                   template_id: str | None = None) -> StyleTemplate:
        with self._lock:
            entries = self.list_styles()
            current = None
            if template_id is not None:
                current = next((item for item in entries if item.id == template_id), None)
                if current is None or current.builtin:
                    raise ValueError('Template is missing or built-in and read-only.')
            binding = current.arctime_template_id if current is not None else None
            match arctime_template_id:
                case _Binding.PRESERVE:
                    pass
                case str() | None:
                    binding = arctime_template_id
                case unreachable:
                    assert_never(unreachable)
            item = StyleTemplate(id=template_id or uuid4().hex, name=name, style=style,
                                 arctime_template_id=binding)
            if any(other.name.casefold() == item.name.casefold() and other.id != item.id for other in entries):
                raise ValueError('A template with this name already exists.')
            if binding is not None:
                self.download_project(binding)
            self._write(self._path('styles', item.id), item.model_dump_json().encode())
            return item

    def import_style(self, content: bytes) -> StyleTemplate:
        if len(content) > 64 * 1024:
            raise ValueError('Style template exceeds 64 KiB.')
        item = StyleTemplate.model_validate_json(content)
        return self.save_style(item.name, item.style, item.arctime_template_id)

    def download_style(self, template_id: str) -> bytes:
        item = next((item for item in self.list_styles() if item.id == template_id), None)
        if item is None:
            raise ValueError('Style template not found.')
        return item.model_dump_json(indent=2).encode()

    def delete_style(self, template_id: str) -> None:
        with self._lock:
            self._path('styles', template_id).unlink()

    def list_projects(self) -> list[ProjectTemplate]:
        result = []
        for path in sorted(self._check(self.root / 'projects').glob('*.json')):
            item = ProjectTemplate.model_validate_json(self._check(path).read_bytes())
            if path != self._path('projects', item.id):
                raise ValueError('Stored project identity is corrupt.')
            self.download_project(item.id)
            result.append(item)
        return result

    def save_project(self, name: str, filename: str, content: bytes) -> ProjectTemplate:
        if Path(filename).name != filename or Path(filename).suffix.lower() != '.atpj':
            raise ValueError('Project upload requires a plain .atpj filename.')
        validated_name = StyleTemplate(id='', name=name, style=SubtitleStyle()).name
        with self._lock:
            if any(item.name.casefold() == validated_name.casefold() for item in self.list_projects()):
                raise ValueError('A project template with this name already exists.')
            item = ProjectTemplate(id=uuid4().hex, name=validated_name, size=len(content),
                                   sha256=hashlib.sha256(content).hexdigest())
            blob = self._path('projects', item.id, 'atpj')
            self._write(blob, content)
            try:
                self._write(self._path('projects', item.id), item.model_dump_json().encode())
            except OSError:
                blob.unlink()
                raise
            return item

    def download_project(self, template_id: str) -> bytes:
        item = ProjectTemplate.model_validate_json(self._path('projects', template_id).read_bytes())
        blob = self._path('projects', template_id, 'atpj')
        if blob.stat().st_size > 16 * 1024 * 1024:
            raise ValueError('Project template exceeds 16 MiB.')
        content = blob.read_bytes()
        if item.id != template_id or len(content) != item.size or hashlib.sha256(content).hexdigest() != item.sha256:
            raise ValueError('Project template failed integrity verification.')
        return content

    def delete_project(self, template_id: str) -> None:
        with self._lock:
            if any(item.arctime_template_id == template_id for item in self.list_styles()):
                raise ValueError('Project template is linked to a style; remove that association first.')
            self.download_project(template_id)
            self._path('projects', template_id).unlink()
            self._path('projects', template_id, 'atpj').unlink()
