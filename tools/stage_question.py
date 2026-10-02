#!/usr/bin/env python3
"""Wizard questions "Which stages will happen?" — ready for AskUserQuestion.

    run stage_question.py --profile backend [--level senior] [--known recruiter,tech] [--dir <folder> | --lang ru]

One button question holds 4 options, while a profile has about ten stages. So
stages are split into groups by the profile's `ask` field and turned into 1–3 questions
on one screen (multiSelect):

    early      — Early stages:     recruiter screening, experience interview
    technical  — Technical:        technical interview, practice, design
    final      — People and final: behavioral, leadership, final
    never      — not asked:        preparation, offer

Stages turned off by the level (`when: level`) are left out. If a group has more than
4 stages, it is split into parts. "Skip" on a question = "don't know" = all stages of the group.

Language: English by default. `--lang ru` takes the Russian texts (`title_ru`, `summary_ru`
from the profile). Without `--lang`, the language is the folder's explanation language
(`explain-language`, tools/langs.py) when `--dir` is given, otherwise en. For other languages
the texts stay English — the agent translates them when asking.

Output (JSON):
    {"questions": [...for AskUserQuestion...],
     "map": {"<label>": "<stage id>"},        # how to turn an answer back into stage ids
     "hidden_by_level": [...], "always": [...], "lang": "<lang>"}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_profiles as vp  # noqa: E402

GROUPS = {
    "en": [
        ("early", "Early stages", "Which of the early stages will happen?"),
        ("technical", "Technical", "Which technical stages will happen?"),
        ("final", "People/final", "Which people and final stages will happen?"),
    ],
    "ru": [
        ("early", "Первые этапы", "Какие из первых этапов будут?"),
        ("technical", "Технические", "Какие технические этапы будут?"),
        ("final", "Люди и финал", "Какие этапы про людей и финал будут?"),
    ],
}
UI = {
    "en": {"known": " (known)", "none": "This stage won't happen", "none_desc": "Turn it off in the plan"},
    "ru": {"known": " (известно)", "none": "Этого этапа не будет", "none_desc": "Выключить его в плане"},
}


def pick_lang(lang: str | None, folder: str | None) -> str:
    if lang:
        return lang.strip().lower()
    if folder:
        import langs as lg
        return lg.primary(Path(folder).expanduser())
    return "en"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--level")
    ap.add_argument("--known", default="", help="ids of stages already known from correspondence/the vacancy — marked in the label")
    ap.add_argument("--dir", help="preparation folder: its explanation language is used when --lang is not given")
    ap.add_argument("--lang", help="language of labels: en (default) or ru; other languages fall back to English")
    args = ap.parse_args()
    lang = pick_lang(args.lang, args.dir)
    ui = UI.get(lang, UI["en"])

    rep = vp.Report()
    prof = vp.resolve(args.profile, vp.load_raw(rep), rep)
    if not prof:
        print("\n".join(rep.errors), file=sys.stderr)
        return 1
    known = {k for k in args.known.split(",") if k}

    groups = GROUPS.get(lang, GROUPS["en"])
    by_group: dict[str, list] = {g[0]: [] for g in groups}
    hidden, always = [], []
    for st in prof["stages"]:
        ask = st.get("ask", "technical")
        lv = (st.get("when") or {}).get("level")
        if args.level and lv and args.level not in lv:
            hidden.append(st["id"])
            continue
        if ask == "never":
            always.append(st["id"])
            continue
        by_group.setdefault(ask, []).append(st)

    questions, mapping = [], {}
    for gid, header, text in groups:
        stages = by_group.get(gid) or []
        for part in range(0, len(stages), 4):
            chunk = stages[part:part + 4]
            opts = []
            for st in chunk:
                label = vp.localized(st, "title", lang, st["id"])
                if st["id"] in known:
                    label += ui["known"]
                mapping[label] = st["id"]
                opts.append({"label": label, "description": vp.localized(st, "summary", lang)[:90]})
            if len(opts) == 1:  # AskUserQuestion needs 2+ options
                opts.append({"label": ui["none"], "description": ui["none_desc"]})
                mapping[ui["none"]] = None
            questions.append({"header": header if part == 0 else f"{header} 2", "question": text,
                              "multiSelect": True, "options": opts})
    if len(questions) > 4:
        print("! more than 4 questions — split into two screens", file=sys.stderr)

    print(json.dumps({"questions": questions, "map": mapping, "hidden_by_level": hidden, "always": always,
                      "lang": lang}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
