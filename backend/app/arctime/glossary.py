from __future__ import annotations

import json
import re
import unicodedata
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


# whisper.cpp 初始提示词上限约 224 token；中日文按字符保守截断，避免靠后的词条被丢弃
ASR_PROMPT_CHARS = 120


def asr_prompt(terms: list[Term], limit: int = ASR_PROMPT_CHARS) -> str:
    """把术语原文拼成 whisper 初始提示词，降低专名误听。

    人名、作品名优先于普通术语；超长时跳过放不下的词条，而不是截断词条本身。
    """
    ordered = sorted(terms, key=lambda term: (term.category == "术语", term.src))
    values: list[str] = []
    used = 0
    for term in ordered:
        src = term.src.strip()
        if not src or src in values:
            continue
        extra = len(src) + (1 if values else 0)
        if used + extra > limit:
            continue
        values.append(src)
        used += extra
    return "、".join(values)


# 匹配时需要忽略的符号：间隔符与长音符（ASR 对同一专名的写法经常不一致）
_IGNORED_MARKS = {"・", "･", "·", "ー"}


def normalize_text(value: str) -> str:
    """归一化用于「术语是否出现」的比对，不改变发给模型的原文。

    全半角统一、片假名转平假名，并去掉空白、间隔符与长音符，
    让 `星街スイセイ` / `星街すいせい` / `星街 すいせい` 视作同一个名字。
    """
    text = unicodedata.normalize("NFKC", value)
    text = "".join(chr(ord(ch) - 0x60) if "\u30a1" <= ch <= "\u30f6" else ch for ch in text)
    return "".join(ch for ch in text if not ch.isspace() and ch not in _IGNORED_MARKS)


def match_terms(terms: list[Term], texts: list[str]) -> list[Term]:
    """返回确实出现在给定文本里的术语；比对前两边都做归一化。"""
    normalized = [normalize_text(text) for text in texts]
    found: list[Term] = []
    for term in terms:
        src = normalize_text(term.src)
        if src and any(src in text for text in normalized):
            found.append(term)
    return found


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
