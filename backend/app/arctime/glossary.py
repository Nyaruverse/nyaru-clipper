from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

CATEGORIES = ("人名", "作品名", "术语")
MAX_TERMS = 500
MAX_CANDIDATES = 100
_TERM_TEXT = re.compile(r"^[^\x00-\x1f]{1,64}$")


class Term(BaseModel):
    src: str = Field(min_length=1, max_length=64, pattern=_TERM_TEXT)
    dst: str = Field(min_length=1, max_length=64, pattern=_TERM_TEXT)
    category: Literal["人名", "作品名", "术语"] = "术语"


class Candidate(BaseModel):
    src: str = Field(min_length=1, max_length=64)
    dst: str = Field(min_length=1, max_length=64)
    category: Literal["人名", "作品名", "术语"] = "术语"


class TermsUpdate(BaseModel):
    terms: list[Term] = Field(default_factory=list, max_length=MAX_TERMS)


class TermsImport(BaseModel):
    text: str = Field(max_length=1_000_000)


class GlossaryStore(BaseModel):
    version: int = 1
    terms: list[Term] = Field(default_factory=list, max_length=MAX_TERMS)
    candidates: list[Candidate] = Field(default_factory=list, max_length=MAX_CANDIDATES)
    ignored: list[str] = Field(default_factory=list, max_length=MAX_TERMS)


def load_glossary(path: Path) -> GlossaryStore:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
            return GlossaryStore()
        return GlossaryStore.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError):
        return GlossaryStore()


def parse_terms_text(text: str) -> tuple[list[Term], int]:
    """解析术语表文本，格式：每行 `# 原文=统一译文`（`#` 前缀可选）。

    返回 (有效词条列表, 跳过的无效行数)。同一文件内 src 重复时取最后一条。
    """
    seen: dict[str, Term] = {}
    skipped = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # 剥离行首的术语行标记 `#`
        if line.startswith("#"):
            line = line[1:].strip()
        if "=" not in line:
            skipped += 1
            continue
        src, _, dst = line.partition("=")
        src = src.strip()
        dst = dst.strip()
        if not src or not dst:
            skipped += 1
            continue
        try:
            term = Term(src=src, dst=dst, category="术语")
        except ValueError:
            skipped += 1
            continue
        seen[term.src] = term
    return list(seen.values()), skipped


def add_candidates(store: GlossaryStore, found: list[Candidate]) -> int:
    """合并新候选词：跳过已收录词条、已忽略项与重复候选，返回新增数量。"""
    known = {term.src for term in store.terms} | set(store.ignored)
    pending = {candidate.src for candidate in store.candidates}
    added = 0
    for candidate in found:
        if candidate.src in known or candidate.src in pending:
            continue
        if len(store.candidates) >= MAX_CANDIDATES:
            break
        store.candidates.append(candidate)
        pending.add(candidate.src)
        added += 1
    return added
