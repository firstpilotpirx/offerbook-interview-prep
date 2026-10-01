#!/usr/bin/env python3
"""Materials content/*.md — block skeletons and overview, without manual markup.

    run content.py --dir . scaffold tech tech.kafka.order              # lesson in the explanation language
    run content.py --dir . scaffold design design.cases.chat --kind case
    run content.py --dir . scaffold stories stories.indexer --kind story
    run content.py --dir . scaffold tech tech.kafka.order --lang en --companion   # short EN companion
    run content.py --dir . missing [--priority 1]                       # plan topics without material
    run content.py --dir . blocks tech                                  # block ids in the file

scaffold:
- file content/<section>.<lang>.md (lang — explain-language, tools/langs.py); no file —
  it is created with frontmatter (last_verified: today);
- block "@@ <id>" with the standard headings from templates/lesson/skeletons.yaml
  and <!-- write: … --> markers — the skeleton deliberately fails depth.py until written;
- default kind: case for design.cases.*, story for stories.*, answer for answers.*, otherwise lesson;
- block already exists — left untouched (exit 0, line "already exists").
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langs as lg  # noqa: E402
from prepio import REPO, read_yaml  # noqa: E402

BLOCK = re.compile(r"^@@\s+(\S+)\s*$", re.M)


def kind_of(tid: str) -> str:
    if tid.startswith("design.cases."):
        return "case"
    if tid.startswith("stories"):
        return "story"
    if tid.startswith("answers"):
        return "answer"
    return "lesson"


def leaves(root: Path) -> list[dict]:
    o = read_yaml(root / "prep" / "outline.yaml", {}) or {}
    skip = set((o.get("state") or {}).get("skip", []))
    out = []

    def walk(nodes):
        for n in nodes or []:
            if n.get("children"):
                walk(n["children"])
            elif n["id"] not in skip:
                out.append(n)
    walk(o.get("nodes"))
    return out


def ids_in(f: Path) -> set:
    return set(BLOCK.findall(f.read_text(encoding="utf-8"))) if f.exists() else set()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scaffold"); s.add_argument("section"); s.add_argument("topic")
    s.add_argument("--kind", choices=["lesson", "case", "story", "answer"]); s.add_argument("--lang")
    s.add_argument("--companion", action="store_true", help="short English companion version")
    m = sub.add_parser("missing"); m.add_argument("--priority", type=int); m.add_argument("--lang")
    b = sub.add_parser("blocks"); b.add_argument("section"); b.add_argument("--lang")
    a = ap.parse_args()
    root = Path(a.dir).expanduser()
    P = lg.primary(root)

    if a.cmd == "missing":
        lang = a.lang or P
        have = set()
        for f in (root / "content").glob(f"*.{lang}.md") if (root / "content").exists() else []:
            have |= ids_in(f)
        rows = [{"id": n["id"], "title": n.get("title"), "priority": n.get("priority", 2), "section": n["id"].split(".")[0]}
                for n in leaves(root) if n["id"] not in have and (not a.priority or n.get("priority", 2) == a.priority)]
        rows.sort(key=lambda r: (r["priority"], r["id"]))
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0

    lang = a.lang or P
    f = root / "content" / f"{a.section}.{lang}.md"
    if a.cmd == "blocks":
        print("\n".join(sorted(ids_in(f))))
        return 0

    if a.topic in ids_in(f):
        print(f"already exists: {a.topic} in {f.name}")
        return 0
    sk = read_yaml(REPO / "templates" / "lesson" / "skeletons.yaml", {})
    kind = a.kind or kind_of(a.topic)
    key = "en-companion" if a.companion else (lang if lang in sk[kind] else "en")
    heads = sk[kind][key]
    qa = sk["qa_example"].get(lang if lang in sk["qa_example"] else "en")
    node = next((n for n in leaves(root) if n["id"] == a.topic), {})
    lines = [f"@@ {a.topic}", ""]
    if lang not in sk[kind] and not a.companion:
        lines.append(f"<!-- language {lang}: translate the headings below into {lg.NAMES.get(lang, lang)} by meaning -->")
    if node.get("summary"):
        lines.append(f"<!-- about: {node['summary']} -->")
    for h in heads:
        lines += [f"### {h}", ""]
        if "Q&A" in h or "Вопросы" in h or "Follow-up" in h or "Что спросят" in h:
            lines += [qa, ""]
        else:
            lines += ["<!-- write: per the standard in references/material-format.md -->", ""]
    text = "\n".join(lines).rstrip() + "\n"
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        f.write_text(f"---\nlast_verified: {dt.date.today().isoformat()}\n---\n\n" + text, encoding="utf-8")
    else:
        old = f.read_text(encoding="utf-8").rstrip() + "\n\n"
        f.write_text(old + text, encoding="utf-8")
    print(f"skeleton {kind} ({key}): {a.topic} → {f.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
