"""Languages of a preparation — shared by all tools.

At the very start the person picks one or more languages for the course (`languages` in
prep/answers.yaml, ISO 639-1 codes, e.g. [ru] or [ru, en]). The first one is the main
language: the conversation, the page interface and the full lessons. `explain-language`
always equals the first one (kept for older tools and data).

- Materials: content/<section>.<lang>.md — one file per section and chosen language.
  One language chosen — one file per section, nothing is duplicated (saves tokens).
- English training (`english-train: full | texts`) needs English texts: then `en` is added
  to the page languages even if it was not chosen; that .en.md is a short companion.
- Page switcher: one button per page language; a single language — no switcher.

Old preparations without `languages`: the explanation language plus `en` if .en.md files
exist (tools/migrate.py writes this down once).
"""
from __future__ import annotations

import re
from pathlib import Path

DEFAULT = "en"
FILE = re.compile(r"^(.+)\.([a-z]{2})\.md$")
NAMES = {"en": "English", "ru": "Русский", "de": "Deutsch", "es": "Español", "fr": "Français",
         "uk": "Українська", "pl": "Polski", "pt": "Português", "it": "Italiano", "tr": "Türkçe",
         "sr": "Srpski", "kk": "Қазақша", "zh": "中文", "ja": "日本語"}


def _answers(root: Path) -> dict:
    p = root / "prep" / "answers.yaml"
    if not p.exists():
        return {}
    try:
        import yaml
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("answers", {}) or {}
    except Exception:
        return {}


def _codes(v) -> list[str]:
    if isinstance(v, str):
        v = re.split(r"[,\s]+", v)
    out = []
    for x in v or []:
        x = str(x).strip().lower()
        if re.fullmatch(r"[a-z]{2}", x) and x not in out:
            out.append(x)
    return out


def _has_en_files(root: Path) -> bool:
    c = root / "content"
    return c.exists() and any(c.glob("*.en.md"))


def primary(root: Path) -> str:
    """Main language of a preparation folder (the first chosen one)."""
    ans = _answers(root)
    chosen_ = _codes(ans.get("languages"))
    if chosen_:
        return chosen_[0]
    v = str(ans.get("explain-language") or "").strip().lower()
    if re.fullmatch(r"[a-z]{2}", v):
        return v
    found = {FILE.match(f.name).group(2) for f in (root / "content").glob("*.md") if FILE.match(f.name)} \
        if (root / "content").exists() else set()
    found.discard("en")
    return sorted(found)[0] if len(found) == 1 else DEFAULT


def chosen(root: Path) -> list[str]:
    """Languages the person picked, main one first."""
    c = _codes(_answers(root).get("languages"))
    if c:
        return c
    p = primary(root)
    return [p, "en"] if p != "en" and _has_en_files(root) else [p]


def english_training(root: Path) -> bool:
    return str(_answers(root).get("english-train") or "").lower() in ("full", "texts")


def languages(root: Path) -> list[str]:
    """Page and material languages: the chosen ones, plus en when English is trained."""
    c = chosen(root)
    if "en" not in c and english_training(root):
        c = c + ["en"]
    return c


def companion(root: Path, lang: str) -> bool:
    """True for an English file that exists only for English training (short companion)."""
    return lang == "en" and lang not in chosen(root) and lang in languages(root)
