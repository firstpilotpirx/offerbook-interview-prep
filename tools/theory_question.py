#!/usr/bin/env python3
"""Wizard questions "Which fundamental theory should be added?" — ready for AskUserQuestion.

    run theory_question.py --profile backend --dir <folder> [--level senior] [--lang ru]

Takes the profile's cross-cutting section with `offer: true` (for backend — "Fundamentals", id theory),
keeps the blocks that fit the survey answers (prep/answers.yaml: databases, brokers, level,
algorithms) and lays them out as 1–4 multiple-choice questions with 4 options each.

Recommended: blocks with priority 1 and blocks switched on by your stack specifically (e.g.
"Relational databases: theory" — because PostgreSQL is in the answers). Recommended ones get
" (recommended)" in the label and come first.

Language: English by default. `--lang ru` takes the Russian texts (`title_ru` from the profile).
Without `--lang`, the language is the folder's explanation language (`explain-language`,
tools/langs.py) when `--dir` is given, otherwise en. For other languages the texts stay
English — the agent translates them when asking.

Output (JSON):
    {"questions": [...], "map": {"<label>": "<block id>"}, "all": [id…], "recommended": [id…], "lang": "<lang>"}
The person's answer → blocks that were not chosen go to the plan's state.skip (not deleted).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_profiles as vp  # noqa: E402

UI = {
    "en": {"rec": " (recommended)", "none": "Not needed", "none_desc": "Skip this block",
           "header": "Theory", "q1": "Which fundamental theory should be added to the plan?",
           "q2": "And from these blocks?"},
    "ru": {"rec": " (рекомендую)", "none": "Не нужно", "none_desc": "Пропустить этот блок",
           "header": "Фундамент", "q1": "Какую фундаментальную теорию добавить в план?",
           "q2": "И из этих блоков?"},
}


def applies(cond: dict | None, level: str | None, answers: dict) -> tuple[bool, bool]:
    """(fits, switched on specifically by a survey answer)."""
    if not cond:
        return True, False
    if level and "level" in cond and level not in cond["level"]:
        return False, False
    by_answer = False
    for qid, vals in (cond.get("answer") or {}).items():
        if qid not in answers:
            continue  # no answer — do not switch off
        got = answers[qid] if isinstance(answers[qid], list) else [answers[qid]]
        if not set(map(str, got)) & set(vals):
            return False, False
        by_answer = True
    return True, by_answer


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--dir", help="preparation folder with prep/answers.yaml (default: current folder)")
    ap.add_argument("--level")
    ap.add_argument("--lang", help="language of labels: en (default) or ru; default — the explanation language of --dir")
    args = ap.parse_args()
    folder = Path(args.dir or ".").expanduser()
    if args.lang:
        lang = args.lang.strip().lower()
    elif args.dir:
        import langs as lg
        lang = lg.primary(folder)
    else:
        lang = "en"
    ui = UI.get(lang, UI["en"])

    rep = vp.Report()
    prof = vp.resolve(args.profile, vp.load_raw(rep), rep)
    if not prof:
        print("\n".join(rep.errors), file=sys.stderr)
        return 1
    ap_file = folder / "prep" / "answers.yaml"
    answers = ((yaml.safe_load(ap_file.read_text(encoding="utf-8")) or {}).get("answers", {})) if ap_file.exists() else {}
    level = args.level or answers.get("level")

    def T(x):
        return vp.localized(x, "title", lang, x.get("id", ""))

    sections = [c for c in prof["cross"] if c.get("offer")]
    blocks = []
    for sec in sections:
        for t in sec.get("topics", []):
            ok, by_answer = applies(t.get("when"), level, answers)
            if not ok:
                continue
            rec = by_answer or t.get("priority", 2) == 1
            kids = ", ".join(T(c) for c in t.get("children", [])[:3])
            blocks.append({"id": t["id"], "title": T(t), "desc": kids, "rec": rec, "by_answer": by_answer})
    blocks.sort(key=lambda b: (not b["by_answer"], not b["rec"]))

    questions, mapping = [], {}
    for i in range(0, len(blocks), 4):
        chunk = blocks[i:i + 4]
        opts = []
        for b in chunk:
            label = b["title"] + (ui["rec"] if b["rec"] else "")
            mapping[label] = b["id"]
            opts.append({"label": label, "description": b["desc"][:100]})
        if len(opts) == 1:
            opts.append({"label": ui["none"], "description": ui["none_desc"]})
            mapping[ui["none"]] = None
        n = i // 4 + 1
        questions.append({"header": ui["header"] if n == 1 else f"{ui['header']} {n}",
                          "question": ui["q1"] if n == 1 else ui["q2"],
                          "multiSelect": True, "options": opts})
    if len(questions) > 4:
        print("! more than 4 questions — show them on two screens", file=sys.stderr)
    print(json.dumps({"questions": questions, "map": mapping, "all": [b["id"] for b in blocks],
                      "recommended": [b["id"] for b in blocks if b["rec"]], "lang": lang},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
