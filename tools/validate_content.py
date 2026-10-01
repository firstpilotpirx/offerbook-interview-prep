#!/usr/bin/env python3
"""Check the materials and the trainer deck in a prep folder.

    python3 tools/validate_content.py --dir .           # check
    python3 tools/validate_content.py --dir . --require-en
    python3 tools/validate_content.py --dir . --update-lock

Expected layout (relative to --dir):
    content/<section>.<lang>.md, content/<section>.en.md   materials, "@@ id" blocks (lang is explain-language, tools/langs.py)
    prep/outline.yaml                                topic tree (if present)
    prep/words.yaml                                  trainer deck (if present)
    prep/ids.lock.json                               locked topic and card ids

Checks:
  • block ids are unique within each file and there are no empty blocks;
  • every section exists in each page language with the same ids (tools/langs.py: chosen
    languages are required; an English companion for English training — warning, error with --require-en);
  • frontmatter: last_verified is present and not older than --max-age days;
  • block ids exist in the outline, and every non-skipped leaf topic has material;
  • the deck matches schemas/words.schema.json, ids are unique, used_in / from point to real topics;
  • [[term]] links in English materials point to a card (by the en field);
  • cover letters prep/companies/*/cover.*.md: 150–300 words, no placeholders, the company is named;
  • interviews prep/companies/*/company.yaml: schema, stages exist in the profile, people exist in
    contacts, past stages have a date, questions reference plan topics;
  • no topic or card id disappeared compared to the lock: progress is tied to them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
    import yaml
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency: {e.name}. pip install -r tools/requirements.txt")

REPO = Path(__file__).resolve().parent.parent
WORDS_SCHEMA = REPO / "schemas" / "words.schema.json"
COMPANY_SCHEMA = REPO / "schemas" / "company.schema.json"
sys.path.insert(0, str(REPO / "tools"))
BLOCK = re.compile(r"^@@\s+(\S+)\s*$", re.M)
LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)

errors: list[str] = []
warnings: list[str] = []


def err(where, msg):
    errors.append(f"✗ {where}: {msg}")


def warn(where, msg):
    warnings.append(f"! {where}: {msg}")


def parse_md(path: Path):
    text = path.read_text(encoding="utf-8")
    front = {}
    m = FRONT.match(text)
    if m:
        try:
            front = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            err(path.name, f"frontmatter does not parse: {e}")
        text = text[m.end():]
    parts = BLOCK.split(text)
    blocks = {}
    for i in range(1, len(parts), 2):
        bid, body = parts[i], parts[i + 1]
        if bid in blocks:
            err(path.name, f"block «{bid}» is duplicated")
        if not body.strip():
            err(path.name, f"block «{bid}» is empty")
        blocks[bid] = body
    if parts[0].strip():
        warn(path.name, "text before the first @@ will not appear on the page")
    return front, blocks


def walk(nodes):
    for n in nodes or []:
        yield n
        yield from walk(n.get("children"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--require-en", action="store_true", help="the English companion is required too (interview in English)")
    ap.add_argument("--max-age", type=int, default=365, help="how many days last_verified counts as fresh")
    ap.add_argument("--update-lock", action="store_true")
    ap.add_argument("--require-depth", action="store_true",
                    help="shallow materials are an error (standard: references/material-format.md, script depth.py)")
    args = ap.parse_args()
    root = Path(args.dir)

    # ---- outline
    outline_ids, leaves, skipped = set(), set(), set()
    op = root / "prep" / "outline.yaml"
    if op.exists():
        try:
            o = yaml.safe_load(op.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            err("outline.yaml", f"YAML does not parse: {e}")
            o = {}
        for n in walk(o.get("nodes")):
            if n["id"] in outline_ids:
                err("outline.yaml", f"id «{n['id']}» is duplicated")
            outline_ids.add(n["id"])
            if not n.get("children") and n.get("kind", "topic") == "topic":
                leaves.add(n["id"])
        skipped = set((o.get("state") or {}).get("skip", []))
    else:
        warn("prep/outline.yaml", "missing — skipped checking materials against the tree")

    # ---- materials
    content_ids: set[str] = set()
    en_text = ""
    today = dt.date.today()
    pairs: dict[str, dict[str, Path]] = {}
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import langs as lg
    P = lg.primary(root)
    LANGS = lg.languages(root)
    for f in sorted((root / "content").glob("*.md")):
        m = re.match(r"(.+)\.([a-z]{2})\.md$", f.name)
        if not m or m.group(2) not in LANGS:
            err(f.name, f"name must be <section>.<lang>.md, lang one of: {', '.join(LANGS)}"
                f" (languages in prep/answers.yaml)")
            continue
        pairs.setdefault(m.group(1), {})[m.group(2)] = f

    for name, langs in sorted(pairs.items()):
        parsed = {}
        for lang, f in langs.items():
            front, blocks = parse_md(f)
            parsed[lang] = blocks
            content_ids |= set(blocks)
            if lang == "en":
                en_text += "\n".join(blocks.values())
            lv = front.get("last_verified")
            if not lv:
                warn(f.name, "no last_verified in frontmatter")
            else:
                d = lv if isinstance(lv, dt.date) else dt.date.fromisoformat(str(lv))
                age = (today - d).days
                if age > args.max_age:
                    warn(f.name, f"last_verified {d} — {age} days ago, re-check the facts")
            for bid in blocks:
                if outline_ids and bid not in outline_ids:
                    err(f.name, f"block «{bid}» not found in the outline")
        if P not in parsed:
            err(name, f"no .{P}.md — {P} is the main language, every section starts there")
            continue
        # every other page language must have the same blocks as the main file;
        # a chosen language is required, an English companion (English training) only with --require-en
        for lang in LANGS[1:]:
            soft = lg.companion(root, lang) and not args.require_en
            if lang not in parsed:
                (warn if soft else err)(name, f"no .{lang}.md")
                continue
            miss = sorted(set(parsed[P]) - set(parsed[lang]))
            extra = sorted(set(parsed[lang]) - set(parsed[P]))
            if miss:
                (warn if soft else err)(name, f"missing in .{lang}.md: {', '.join(miss)}")
            if extra:
                err(name, f"missing in .{P}.md: {', '.join(extra)}")

    for leaf in sorted(leaves - skipped - content_ids):
        warn("materials", f"topic «{leaf}» has no material")

    # ---- deck
    card_ids: set[str] = set()
    wp = root / "prep" / "words.yaml"
    known_refs = outline_ids | content_ids
    if wp.exists():
        try:
            deck = yaml.safe_load(wp.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            err("words.yaml", f"YAML does not parse: {e}")
            deck = {}
        schema = json.loads(WORDS_SCHEMA.read_text(encoding="utf-8"))
        v = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        for e in v.iter_errors(json.loads(json.dumps(deck, default=str))):
            err("words.yaml", f"schema, {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}")
        groups = {g["g"] for g in deck.get("groups", [])}
        prefix = {"words": "w:", "verbs": "v:", "phrases": "p:", "answers": "a:"}
        by_en = {}
        for kind, pre in prefix.items():
            for c in deck.get(kind, []) or []:
                cid = c.get("id", "?")
                if cid in card_ids:
                    err("words.yaml", f"card «{cid}» is duplicated")
                card_ids.add(cid)
                if not cid.startswith(pre):
                    err("words.yaml", f"«{cid}» in {kind} must start with «{pre}»")
                if "g" in c and groups and c["g"] not in groups:
                    err("words.yaml", f"«{cid}»: group {c['g']} is not in groups")
                refs = list(c.get("used_in", [])) + [c["from"]] if c.get("from") else list(c.get("used_in", []))
                refs += [x.get("from") for x in c.get("ex", []) if isinstance(x, dict) and x.get("from")]
                for r in refs:
                    if known_refs and r not in known_refs:
                        err("words.yaml", f"«{cid}» references topic «{r}», which does not exist")
                if kind == "words":
                    by_en[c.get("en", "").lower()] = cid
                    abouts = {x.get("about") for x in c.get("ex", [])}
                    if len(c.get("ex", [])) < 3 or len(abouts) < 3:
                        warn("words.yaml", f"«{cid}»: three examples needed — system, personal, work")
                if kind == "phrases" and c.get("word") and not str(c["word"]).startswith("w:"):
                    err("words.yaml", f"«{cid}»: word must point to a w: card")
        ranks = [c["rank"] for c in deck.get("words", []) if "rank" in c]
        if len(ranks) != len(set(ranks)):
            err("words.yaml", "word rank is duplicated")
        for term in sorted({t.strip().lower() for t in LINK.findall(en_text)}):
            if term not in by_en:
                err("materials .en", f"[[{term}]] — no card with this en")
    elif en_text and LINK.search(en_text):
        err("prep/words.yaml", "materials have [[links]] to words, but there is no deck")

    # ---- interviews
    companies = sorted((root / "prep" / "companies").glob("*/company.yaml"))
    if companies:
        cschema = json.loads(COMPANY_SCHEMA.read_text(encoding="utf-8"))
        cv = jsonschema.Draft202012Validator(cschema, format_checker=jsonschema.FormatChecker())
        stage_cache: dict[str, set] = {}
        for cp in companies:
            where = f"companies/{cp.parent.name}"
            try:
                c = yaml.safe_load(cp.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as e:
                err(where, f"YAML does not parse: {str(e).splitlines()[0]} (quote strings containing «,» «:» «?»)")
                continue
            for e in cv.iter_errors(json.loads(json.dumps(c, default=str))):
                err(where, f"schema, {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}")
            if c.get("id") != cp.parent.name:
                err(where, f"id «{c.get('id')}» does not match the folder")
            prof = c.get("profile")
            if prof and prof not in stage_cache:
                import validate_profiles as vp
                rep = vp.Report()
                resolved = vp.resolve(prof, vp.load_raw(rep), rep) if (vp.PROFILES / f"{prof}.yaml").exists() else None
                stage_cache[prof] = {s_["id"] for s_ in resolved["stages"]} if resolved else set()
                if not resolved:
                    err(where, f"profile «{prof}» not found")
            stages_ok = stage_cache.get(prof, set())
            people = {x["name"] for x in c.get("contacts", [])}
            seen = set()
            for st in c.get("stages", []):
                sid = st.get("id", "?")
                if sid in seen:
                    err(where, f"stage «{sid}» is duplicated")
                seen.add(sid)
                if stages_ok and st.get("stage") not in stages_ok:
                    err(where, f"stage «{sid}»: the profile has no stage «{st.get('stage')}»")
                if not sid.startswith(f"{st.get('stage')}-"):
                    err(where, f"stage id «{sid}» must start with «{st.get('stage')}-»")
                if st.get("status") in ("passed", "failed", "scheduled") and not st.get("date"):
                    err(where, f"stage «{sid}» with status {st['status']} has no date")
                if st.get("status") in ("passed", "failed") and st.get("date"):
                    if dt.date.fromisoformat(str(st["date"])) > today:
                        warn(where, f"stage «{sid}» passed in the future: {st['date']}")
                for w in st.get("with", []):
                    if w not in people:
                        err(where, f"stage «{sid}»: «{w}» is not in contacts")
                for q in st.get("questions", []):
                    if q.get("topic") and known_refs and q["topic"] not in known_refs:
                        warn(where, f"question «{q['q'][:40]}» → topic «{q['topic']}» is not in the plan; add the topic?")
                    if q.get("went") == "bad" and not q.get("topic"):
                        warn(where, f"failed question «{q['q'][:40]}» has no topic — it will not get into the plan")
            for cl in sorted(cp.parent.glob("cover.*.md")):
                text = FRONT.sub("", cl.read_text(encoding="utf-8"))
                n = len(re.findall(r"\w+", text))
                if not 120 <= n <= 320:
                    warn(where, f"{cl.name}: {n} words — 150–300 is better")
                if re.search(r"\[[^\]]{2,40}\]|\{[^}]{2,40}\}|<[A-ZА-Я][^>]{1,30}>", text):
                    err(where, f"{cl.name}: placeholders like [Company] or {{name}} remain")
                if c.get("name") and c["name"].split()[0].lower() not in text.lower():
                    warn(where, f"{cl.name}: company «{c['name']}» is not mentioned")
            if c.get("status") in ("offer", "accepted") and not any(x.get("kind") == "offer" for x in c.get("log", [])):
                warn(where, "status is offer, but log has no kind: offer entry with the terms")

    # ---- lesson depth
    import depth as dp
    for r in dp.analyze(root):
        if not r["ok"]:
            (err if args.require_depth else warn)(f"{r['file']} · {r['id']}", "shallow: " + "; ".join(r["problems"]))

    # ---- id stability
    lock_path = root / "prep" / "ids.lock.json"
    now = {"topics": sorted(outline_ids | content_ids), "cards": sorted(card_ids)}
    if args.update_lock:
        if errors:
            print("\n".join(errors))
            print("\nlock not updated: fix the errors first")
            return 1
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps(now, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"lock updated: {lock_path}")
    elif lock_path.exists():
        old = json.loads(lock_path.read_text(encoding="utf-8"))
        for k, label in (("topics", "topic"), ("cards", "card")):
            gone = sorted(set(old.get(k, [])) - set(now[k]))
            if gone:
                err("ids.lock.json", f"{label} ids disappeared (progress will be lost): {', '.join(gone[:20])}"
                    + (f" and {len(gone) - 20} more" if len(gone) > 20 else ""))
    else:
        warn("prep/ids.lock.json", "missing — run --update-lock after the first build")

    for line in warnings + errors:
        print(line)
    print(f"\nSections: {len(pairs)}, blocks: {len(content_ids)}, cards: {len(card_ids)}; "
          f"{'no errors' if not errors else f'errors: {len(errors)}'}, warnings: {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
