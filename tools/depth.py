#!/usr/bin/env python3
"""Material depth: does a lesson have enough volume and all required sections.

    run depth.py --dir <folder>            # report for all topics
    run depth.py --dir <folder> --json     # for the hub and the build module (mode: deepen)

Standard: skills/offerbook-start/references/material-format.md. In short:

  priority        RU, words   EN, words   required RU sections (###; Russian headings, see REQUIRED)
  1 essential     400         180         In short · How it works · Interview questions · Check yourself
  2 important     250         120         In short · How it works · Interview questions · Check yourself
  3 optional      120          60         In short · Interview questions

  EN: "In short" and "Interview Q&A" are required.

  Cross-cutting sections have their own formats (not lessons):
    stories.*   STAR story: Situation · Task · Action · Result, from 180 words (EN from 100)
    answers.*   ready-to-say answer, from 60 words (EN from 40)
    questions.* list of questions to ask them, from 40 words
    design.cases.*  system design problem, a plan for the conversation: Functional requirements ·
                    Non-functional requirements · What to ask the interviewer · What to watch for in the
                    implementation, from 300/200/120 words by priority
  "Interview questions" must have at least 4 questions for priority 1, 3 for 2, 2 for 3.

Priority comes from prep/outline.yaml; a topic without a priority counts as "important".
Used by validate_content.py (--require-depth) and next_steps.py ("Deepen materials" button).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

BLOCK = re.compile(r"^@@\s+(\S+)\s*$", re.M)
FRONT = re.compile(r"\A---\n.*?\n---\n", re.S)
H3 = re.compile(r"^###\s+(.+?)\s*$", re.M)

# Rule keys: ru — Russian primary; en — English companion version (shorter:
# what you actually say in the interview); enmain — English as the explanation
# language (full lesson); any — another explanation language (de, es…): headings are
# in that language, so the section count is checked and questions are counted as "- **Question?**" items.
MIN_WORDS = {"ru": {1: 400, 2: 250, 3: 120}, "en": {1: 150, 2: 100, 3: 60},
             "enmain": {1: 320, 2: 200, 3: 100}, "any": {1: 350, 2: 220, 3: 110}}
MIN_SECTIONS = {1: 4, 2: 4, 3: 2}

# Cross-cutting sections have their own formats: STAR story, ready-to-say answer, question lists.
KINDS = {
    "stories": {"min": {"ru": 180, "en": 100, "enmain": 150, "any": 160},
                "req": {"ru": ["ситуация", "задача", "действия", "результат"], "en": ["situation", "task", "action", "result"],
                        "enmain": ["situation", "task", "action", "result"], "any": []}},
    "answers": {"min": {"ru": 60, "en": 40, "enmain": 50, "any": 50}, "req": {"ru": [], "en": [], "enmain": [], "any": []}},
    "questions": {"min": {"ru": 40, "en": 30, "enmain": 35, "any": 35}, "req": {"ru": [], "en": [], "enmain": [], "any": []}},
    "language": {"min": {"ru": 80, "en": 60, "enmain": 70, "any": 70}, "req": {"ru": [], "en": [], "enmain": [], "any": []}},
    "trainer": None,
}
# System design problems: a plan for the conversation, not a worked solution.
CASE_PREFIX = "design.cases."
_CASE_EN = ["functional requirements", "non-functional requirements", "what to ask the interviewer", "what to watch for"]
CASE = {"min": {"ru": {1: 300, 2: 200, 3: 120}, "en": {1: 150, 2: 100, 3: 60},
                "enmain": {1: 260, 2: 180, 3: 110}, "any": {1: 280, 2: 190, 3: 115}},
        "req": {"ru": ["функциональные требования", "нефункциональные требования", "что уточнить у интервьюера",
                       "на что обратить внимание"],
                "en": _CASE_EN, "enmain": _CASE_EN, "any": []}}
REQUIRED = {
    "ru": {1: ["суть", "как устроено", "вопросы на интервью", "проверь себя"],
           2: ["суть", "как устроено", "вопросы на интервью", "проверь себя"],
           3: ["суть", "вопросы на интервью"]},
    "en": {1: ["in short", "interview q&a"], 2: ["in short", "interview q&a"], 3: ["in short"]},
    "enmain": {1: ["in short", "how it works", "interview q&a", "check yourself"],
               2: ["in short", "how it works", "interview q&a", "check yourself"],
               3: ["in short", "interview q&a"]},
    "any": {1: [], 2: [], 3: []},
}
QA_HEAD = {"ru": "вопросы на интервью", "en": "interview q&a", "enmain": "interview q&a", "any": None}
QA_ITEM = re.compile(r"^\s*[-*]\s+\*\*[^*]+\?\*\*", re.M)
MIN_QA = {1: 4, 2: 3, 3: 2}


def priorities(root: Path) -> dict[str, int]:
    p = root / "prep" / "outline.yaml"
    if not p.exists():
        return {}
    out = {}

    def walk(nodes):
        for n in nodes or []:
            out[n["id"]] = int(n.get("priority") or 2)
            walk(n.get("children"))
    walk((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("nodes"))
    return out


def sections(body: str) -> dict[str, str]:
    parts = H3.split(body)
    res = {}
    for i in range(1, len(parts), 2):
        res[parts[i].strip().lower().rstrip(":")] = parts[i + 1]
    return res


def analyze(root: Path) -> list[dict]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import langs as lg
    P = lg.primary(root)
    pri = priorities(root)
    skip = set()
    op = root / "prep" / "outline.yaml"
    if op.exists():
        skip = set(((yaml.safe_load(op.read_text(encoding="utf-8")) or {}).get("state") or {}).get("skip", []))
    rows = []
    for f in sorted((root / "content").glob("*.md")):
        m = re.match(r".+\.([a-z]{2})\.md$", f.name)
        if not m:
            continue
        code = m.group(1)
        lang = "ru" if code == "ru" else ("enmain" if P == "en" else "en") if code == "en" else "any"
        parts = BLOCK.split(FRONT.sub("", f.read_text(encoding="utf-8")))
        for i in range(1, len(parts), 2):
            tid, body = parts[i], parts[i + 1]
            if tid in skip:
                continue
            p = pri.get(tid, 2)
            words = len(re.findall(r"\w+", re.sub(r"```.*?```", " ", body, flags=re.S)))
            secs = sections(body)
            have = set(secs)
            prefix = tid.split(".")[0]
            problems, qa = [], 0
            if tid.startswith(CASE_PREFIX):
                need, kind = CASE["min"][lang][p], "case"
                missing = [r for r in CASE["req"][lang] if not any(h.startswith(r) for h in have)]
            elif prefix in KINDS:  # cross-cutting section: its own format
                rule = KINDS[prefix]
                if rule is None:
                    continue
                need, req = rule["min"][lang], rule["req"][lang]
                missing = [r for r in req if not any(h.startswith(r) for h in have)]
                kind = prefix
            else:  # stage topic: a full lesson
                need, kind = MIN_WORDS[lang][p], "lesson"
                missing = [r for r in REQUIRED[lang][p] if not any(h.startswith(r) for h in have)]
                if QA_HEAD[lang] is None:   # other language: count sections, questions by the "- **…?**" form
                    if len(secs) < MIN_SECTIONS[p]:
                        problems.append(f"sections {len(secs)} of {MIN_SECTIONS[p]}")
                    qa = len(QA_ITEM.findall(body))
                    if qa < MIN_QA[p]:
                        problems.append(f"questions {qa} of {MIN_QA[p]}")
                else:
                    qa_sec = next((v for k, v in secs.items() if k.startswith(QA_HEAD[lang])), "")
                    qa = len(re.findall(r"^\s*[-*]\s+\*\*", qa_sec, re.M))
                    if QA_HEAD[lang] not in missing and qa < MIN_QA[p]:
                        problems.append(f"questions {qa} of {MIN_QA[p]}")
            if words < need:
                problems.insert(0, f"{words} words of {need}")
            if missing:
                problems.append("missing sections: " + ", ".join(missing))
            rows.append({"id": tid, "lang": code, "file": f.name, "kind": kind, "priority": p, "words": words,
                         "min": need, "qa": qa, "missing": missing, "problems": problems, "ok": not problems})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = analyze(Path(args.dir).expanduser())
    bad = [r for r in rows if not r["ok"]]
    if args.json:
        print(json.dumps({"total": len(rows), "shallow": bad}, ensure_ascii=False, indent=2))
        return 0
    for r in bad:
        print(f"✗ {r['file']} · {r['id']} (priority {r['priority']}): " + "; ".join(r["problems"]))
    print(f"\nBlocks: {len(rows)}, shallow: {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
