"""切片合规风险词检测。

只保留真正会带来下架、封号或法律问题的内容：涉政、个人隐私、未成年/色情、
自残、毒品等。梗词不再使用静态词表，改由 clip_vocab 从每场弹幕与字幕中提取。

数据目录可放 clip_words.json 整组覆盖（未出现的键沿用默认值）：
{"risk_zh": [...], "risk_ja": [...]}
"""
from __future__ import annotations

import json
from pathlib import Path

RISK_ZH = (
    "政治", "政府", "选举", "首相", "总统",
    "开盒", "人肉搜索", "住址", "家庭住址", "电话号码", "手机号码", "身份证", "真实姓名",
    "本名", "户籍",
    "未成年", "色情", "裸聊", "裸体", "性行为",
    "自杀", "自残", "毒品", "吸毒", "贩毒", "枪支", "恐怖袭击",
)
RISK_JA = (
    "政治", "政府", "選挙", "首相", "大統領",
    "個人情報", "住所", "本名", "電話番号", "身分証明書",
    "未成年", "自殺", "自傷",
    "薬物", "麻薬", "わいせつ", "裸体", "テロ",
)
_MAX_RISK_TERMS = 12
MAX_FILE_BYTES = 256 * 1024


class Lexicon:
    def __init__(self, risk_zh: tuple[str, ...] = RISK_ZH, risk_ja: tuple[str, ...] = RISK_JA):
        self.risk_zh = risk_zh
        self.risk_ja = risk_ja

    def detect(self, zh_text: str, ja_text: str) -> list[str]:
        """返回字幕命中的风险词（去重，最多 12 个）。"""
        zh_lower = zh_text.lower()
        ja_lower = ja_text.lower()
        matched: list[str] = []
        for word in (*self.risk_zh, *self.risk_ja):
            if not word or word in matched:
                continue
            if word.lower() in zh_lower or word.lower() in ja_lower:
                matched.append(word)
                if len(matched) >= _MAX_RISK_TERMS:
                    break
        return matched


def load(path: Path | None = None) -> Lexicon:
    """读取数据目录的覆盖词表；文件缺失或损坏时使用内置词表。"""
    if path is None:
        return Lexicon()
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            return Lexicon()
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Lexicon()
    if not isinstance(payload, dict):
        return Lexicon()

    def pick(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        value = payload.get(key)
        if isinstance(value, list):
            return tuple(str(item).strip() for item in value
                         if isinstance(item, str) and item.strip())
        return default

    return Lexicon(pick("risk_zh", RISK_ZH), pick("risk_ja", RISK_JA))
