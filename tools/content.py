#!/usr/bin/env python3
"""Materials content/*.md — block skeletons and overview, without manual markup.

    run content.py --dir . scaffold tech tech.kafka.order              # lesson in the explanation language
    run content.py --dir . scaffold design design.cases.chat --kind case
    run content.py --dir . scaffold stories stories.indexer --kind story
    run content.py --dir . scaffold tech tech.kafka.order --lang en --companion   # short EN companion
    run content.py --dir . missing [--priority 1]                       # plan topics without material
    run content.py --dir . blocks tech                                  # block ids in the file
    run content.py --dir . verify tech.kafka.order --source https://kafka.apache.org/documentation/#semantics \
        --source "Kleppmann, DDIA, ch. 11" [--open 1] [--by subagent]       # record a finished fact-check
    run content.py --dir . unverified [--priority 1]                    # lessons not fact-checked yet

verify / unverified — the fact-check record prep/verified.yaml (references/material-format.md, "Accuracy"):
- a lesson or system design case counts as checked when its claims were compared with primary sources
  and `verify` stored the date, the sources, the number of claims still marked [verify] and a hash of the text;
- an edit after the check makes the record stale (hash differs) — the block is "not verified" again;
- stories, answers and questions to ask are the person's own material and are not fact-checked.

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
VERIFY_MARK = re.compile(r"\[verify\]", re.I)
SOURCES_HEADS = ("sources", "источники", "quellen", "fuentes", "fonti", "źródła", "джерела", "kaynaklar")
PERSONAL = ("stories", "answers", "questions")


def needs_check(tid: str) -> bool:
    """Lessons and system design cases are fact-checked; the person's own stories and answers are not."""
    return tid.split(".")[0] not in PERSONAL


def split_blocks(text: str) -> dict:
    parts = BLOCK.split(re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S))
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def block_hash(body: str) -> str:
    import hashlib
    return hashlib.sha1(re.sub(r"\s+", " ", body).strip().encode("utf-8")).hexdigest()[:12]


def sources_of(body: str) -> list:
    """Items of the block's Sources section (any course language), or [] if there is none."""
    out, cur = [], None
    for line in body.splitlines():
        h = re.match(r"^###\s+(.+?)\s*$", line)
        if h:
            cur = h.group(1).strip().lower().startswith(SOURCES_HEADS)
            continue
        if cur and re.match(r"^\s*[-*]\s+\S", line):
            out.append(line.strip()[2:].strip())
        elif cur and line.strip() and not out:
            out.append(line.strip())   # a one-line Sources paragraph (older lessons)
    return out


def main_blocks(root: Path) -> dict:
    """{id: body} for blocks of the main language."""
    P = lg.primary(root)
    out = {}
    for f in sorted((root / "content").glob(f"*.{P}.md")) if (root / "content").exists() else []:
        out.update(split_blocks(f.read_text(encoding="utf-8")))
    return out


def verify_state(root: Path) -> dict:
    """{id: {state: ok|open|stale|none, date, sources, open}} for every block that needs a fact-check."""
    rec = (read_yaml(root / "prep" / "verified.yaml", {}) or {}).get("blocks", {}) or {}
    out = {}
    for tid, body in main_blocks(root).items():
        if not needs_check(tid):
            continue
        r = rec.get(tid)
        marks = len(VERIFY_MARK.findall(body))
        if not r:
            st = "none"
        elif r.get("hash") != block_hash(body):
            st = "stale"
        elif marks or r.get("open"):
            st = "open"
        else:
            st = "ok"
        out[tid] = {"state": st, "date": str(r.get("date")) if r else None, "sources": len((r or {}).get("sources", [])),
                    "open": marks, "has_sources": bool(sources_of(body))}
    return out


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
    v = sub.add_parser("verify"); v.add_argument("topic")
    v.add_argument("--source", action="append", default=[], help="URL of the doc section or 'Author, Book, ch. N' (repeat)")
    v.add_argument("--open", type=int, help="claims still marked [verify] (default: counted in the text)")
    v.add_argument("--by", default="", help="who checked: subagent / self")
    u = sub.add_parser("unverified"); u.add_argument("--priority", type=int)
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

    if a.cmd == "verify":
        body = main_blocks(root).get(a.topic)
        if body is None:
            print(f"! no block {a.topic} in content/*.{P}.md", file=sys.stderr); return 1
        if not needs_check(a.topic):
            print(f"! {a.topic} is the person's own material — not fact-checked", file=sys.stderr); return 1
        srcs = [s.strip() for s in a.source if s.strip()]
        if not srcs:
            print("! at least one --source: the doc section URL or 'Author, Book, ch. N'", file=sys.stderr); return 1
        if not sources_of(body):
            print("! the block has no Sources section — add it (references/material-format.md) and run verify again", file=sys.stderr); return 1
        from prepio import write_yaml
        p = root / "prep" / "verified.yaml"
        data = read_yaml(p, {}) or {}
        blocks = data.setdefault("blocks", {})
        opened = a.open if a.open is not None else len(VERIFY_MARK.findall(body))
        blocks[a.topic] = {"date": dt.date.today().isoformat(), "hash": block_hash(body), "sources": srcs, "open": opened,
                           **({"by": a.by} if a.by else {})}
        write_yaml(p, data)
        print(f"verified: {a.topic} · {len(srcs)} sources · open {opened}")
        return 0

    if a.cmd == "unverified":
        pri = {n["id"]: n.get("priority", 2) for n in leaves(root)}
        rows = [{"id": k, "priority": pri.get(k, 2), **v} for k, v in verify_state(root).items()
                if v["state"] != "ok" and (not a.priority or pri.get(k, 2) == a.priority)]
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
