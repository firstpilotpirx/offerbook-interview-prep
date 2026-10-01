#!/usr/bin/env python3
"""Validator for specialty profiles.

Run from the repository root:
    python3 tools/validate_profiles.py                  # check all profiles
    python3 tools/validate_profiles.py --print backend  # show the resolved tree
    python3 tools/validate_profiles.py --print backend --level middle --answer interview-language=english
    python3 tools/validate_profiles.py --print backend --lang ru   # the tree with Russian titles (*_ru)
    python3 tools/validate_profiles.py --json backend   # the resolved profile as JSON (for skills)
    python3 tools/validate_profiles.py --update-lock    # pin ids after intentional changes

Profiles are English-first: `title`, `summary`, `text`, `label`, `description` are English,
Russian lives in the parallel `*_ru` fields (see `localized`). Other explanation languages
are translated by the agent at outline time.

Dependencies: pyyaml, jsonschema (pip install -r tools/requirements.txt).
Exit code 1 if there are errors.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

try:
    import yaml
    import jsonschema
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency: {e.name}. Install: pip install -r tools/requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"
SCHEMA = PROFILES / "_schema.json"
LOCK = PROFILES / "_ids.lock.json"

# Fields with human text: the English value lives in the field itself, translations in <field>_<lang>.
TEXT_FIELDS = ("title", "summary", "text", "label", "description")
CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def localized(obj: dict, field: str, lang: str | None = "en", default: str = "") -> str:
    """Text of `field` in `lang`: `<field>_<lang>` if present, otherwise the English `<field>`."""
    if lang and lang != "en" and obj.get(f"{field}_{lang}"):
        return obj[f"{field}_{lang}"]
    return obj.get(field, default)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"✗ {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"! {where}: {msg}")


# ---------- loading ----------

def load_raw(rep: Report) -> dict[str, dict]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    raw: dict[str, dict] = {}
    for path in sorted(PROFILES.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        where = path.name
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            rep.err(where, f"YAML does not parse: {e}")
            continue
        if not isinstance(data, dict):
            rep.err(where, "the root must be an object")
            continue
        for e in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
            loc = "/".join(str(p) for p in e.absolute_path) or "(root)"
            rep.err(where, f"schema, {loc}: {e.message}")
        if data.get("id") != path.stem:
            rep.err(where, f"id '{data.get('id')}' does not match the file name '{path.stem}'")
        check_english(data, where, rep)
        raw[path.stem] = data
    return raw


def check_english(node, where: str, rep: Report, path: str = "") -> None:
    """English-first: primary text fields must not contain Cyrillic (Russian goes to *_ru)."""
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}/{k}" if path else k
            if k in TEXT_FIELDS and isinstance(v, str) and CYRILLIC.search(v):
                rep.err(where, f"{here}: '{v[:40]}' is not English — put it in {k}_ru and write {k} in English")
            check_english(v, where, rep, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            check_english(v, where, rep, f"{path}/{i}")


# ---------- inheritance ----------

def chain(pid: str, raw: dict, rep: Report) -> list[str] | None:
    seen, order = set(), []
    cur = pid
    while cur:
        if cur in seen:
            rep.err(f"{pid}.yaml", f"inheritance cycle: {' → '.join(order + [cur])}")
            return None
        if cur not in raw:
            rep.err(f"{pid}.yaml", f"extends: profile '{cur}' not found")
            return None
        seen.add(cur)
        order.append(cur)
        cur = raw[cur].get("extends")
    return list(reversed(order))  # from the root to the child


def walk_topics(topics, parent=None):
    for t in topics or []:
        yield t, parent
        yield from walk_topics(t.get("children"), t)


def all_ids(profile: dict) -> set[str]:
    ids = set()
    for kind in ("stages", "cross"):
        for s in profile.get(kind, []):
            ids.add(s["id"])
            for t, _ in walk_topics(s.get("topics")):
                ids.add(t["id"])
    return ids


def prune(topics, disabled: set[str]):
    out = []
    for t in topics or []:
        if t["id"] in disabled:
            continue
        t = dict(t)
        if "children" in t:
            t["children"] = prune(t["children"], disabled)
        out.append(t)
    return out


def merge_sections(base: list, child: list, rep: Report, where: str, kind: str) -> list:
    result = [copy.deepcopy(s) for s in base]
    index = {s["id"]: s for s in result}
    for s in child:
        s = copy.deepcopy(s)
        if s["id"] in index:
            tgt = index[s["id"]]
            topics = s.pop("topics", [])
            replace = s.pop("replace_topics", False)
            tgt.update(s)
            tgt["topics"] = topics if replace else tgt.get("topics", []) + topics
        else:
            index[s["id"]] = s
            result.append(s)
    return result


def resolve(pid: str, raw: dict, rep: Report) -> dict | None:
    order = chain(pid, raw, rep)
    if order is None:
        return None
    acc: dict = {"stages": [], "cross": [], "scope_questions": [], "sources": [], "levels": [], "tracks": []}
    for i, name in enumerate(order):
        p = raw[name]
        where = f"{name}.yaml"
        disabled = set(p.get("disable", []))
        if disabled:
            known = all_ids(acc) | {q["id"] for q in acc["scope_questions"]}
            for d in sorted(disabled - known):
                rep.err(where, f"disable: the parent has no '{d}'")
            for kind in ("stages", "cross"):
                acc[kind] = [s for s in acc[kind] if s["id"] not in disabled]
                for s in acc[kind]:
                    s["topics"] = prune(s.get("topics"), disabled)
            acc["scope_questions"] = [q for q in acc["scope_questions"] if q["id"] not in disabled]
        acc["stages"] = merge_sections(acc["stages"], p.get("stages", []), rep, where, "stages")
        acc["cross"] = merge_sections(acc["cross"], p.get("cross", []), rep, where, "cross")
        acc["scope_questions"] += copy.deepcopy(p.get("scope_questions", []))
        acc["sources"] += copy.deepcopy(p.get("sources", []))
        for tr in copy.deepcopy(p.get("tracks", [])):   # tracks: override by id, new ones appended
            cur = next((x for x in acc["tracks"] if x["id"] == tr["id"]), None)
            if cur:
                cur.update(tr)
            else:
                acc["tracks"].append(tr)
        if p.get("levels"):
            acc["levels"] = list(p["levels"])
        for k in ("id", "title", "title_ru", "version", "description", "description_ru"):
            if k in p:
                acc[k] = p[k]
        acc["abstract"] = p.get("abstract", False) if i == len(order) - 1 else acc.get("abstract", False)
    acc["abstract"] = raw[pid].get("abstract", False)
    acc["extends_chain"] = order
    acc["stages"].sort(key=lambda s: s.get("order", 10**6))
    return acc


# ---------- rules ----------

def check(p: dict, rep: Report) -> None:
    where = f"{p['id']} (resolved)"
    qs = {q["id"]: q for q in p["scope_questions"]}
    stage_ids = {s["id"] for s in p["stages"]}
    levels = set(p["levels"])

    # tracks: every stage and cross-cutting section in exactly one track
    sec_ids = stage_ids | {c["id"] for c in p["cross"]}
    owner = {}
    for tr in p.get("tracks", []):
        for s_ in tr.get("sections", []):
            if s_ not in sec_ids and not p.get("abstract"):   # base lists sections its children add
                rep.warn(where, f"track '{tr['id']}': section '{s_}' does not exist in this profile")
            if s_ in owner:
                rep.err(where, f"section '{s_}' is in two tracks: {owner[s_]} and {tr['id']}")
            owner[s_] = tr["id"]
    if p.get("tracks"):
        for s_ in sorted(sec_ids - set(owner)):
            rep.warn(where, f"section '{s_}' is in no track — counted as '{p['tracks'][0]['id']}'")
    # questions
    seen_q = set()
    for q in p["scope_questions"]:
        if q["id"] in seen_q:
            rep.err(where, f"question '{q['id']}' is declared twice")
        seen_q.add(q["id"])
        opts = [o["value"] for o in q.get("options", [])]
        if q["type"] in ("single", "multi") and not opts and q["id"] != "stages-known":
            rep.err(where, f"question '{q['id']}' of type {q['type']} has no options")
        if len(opts) != len(set(opts)):
            rep.err(where, f"question '{q['id']}': option values repeat")
        if q.get("after") and q["after"] not in qs:
            rep.err(where, f"question '{q['id']}': after → '{q['after']}' does not exist")
    # cycle in after
    for q in p["scope_questions"]:
        seen, cur = set(), q["id"]
        while cur and cur in qs:
            if cur in seen:
                rep.err(where, f"cycle in the question order through '{q['id']}'")
                break
            seen.add(cur)
            cur = qs[cur].get("after")

    def check_when(owner: str, cond: dict | None) -> None:
        if not cond:
            return
        for lv in cond.get("level", []):
            if lv not in levels:
                rep.err(where, f"{owner}: level '{lv}' is not declared in levels")
        for qid, vals in cond.get("answer", {}).items():
            if qid not in qs:
                rep.err(where, f"{owner}: condition on question '{qid}', which does not exist")
                continue
            opts = {o["value"] for o in qs[qid].get("options", [])}
            for v in vals:
                if opts and v not in opts and v != "unknown":
                    rep.err(where, f"{owner}: question '{qid}' has no option '{v}'")

    for q in p["scope_questions"]:
        check_when(f"question '{q['id']}'", q.get("when"))

    # stages and sections
    ids: dict[str, str] = {}
    orders: dict[int, str] = {}

    def claim(i: str, owner: str) -> None:
        if i in ids:
            rep.err(where, f"id '{i}' repeats ({ids[i]} and {owner})")
        ids[i] = owner

    for kind, sections in (("stage", p["stages"]), ("section", p["cross"])):
        for s in sections:
            sid = s["id"]
            claim(sid, f"{kind} {sid}")
            if not s.get("title"):
                rep.err(where, f"{kind} '{sid}' has no title (a new id without a base description?)")
            if kind == "stage":
                if "order" not in s:
                    rep.err(where, f"stage '{sid}' has no order")
                elif s["order"] in orders:
                    rep.err(where, f"order {s['order']} is used by two stages: '{orders[s['order']]}' and '{sid}'")
                else:
                    orders[s["order"]] = sid
            else:
                for u in s.get("used_in", []):
                    if u not in stage_ids:
                        rep.err(where, f"section '{sid}': used_in → stage '{u}' does not exist")
            check_when(f"{kind} '{sid}'", s.get("when"))
            if not s.get("topics") and not p["abstract"]:
                rep.err(where, f"{kind} '{sid}' has no topics — fill it in or turn it off via disable")
            for t, parent in walk_topics(s.get("topics")):
                tid = t["id"]
                claim(tid, f"topic in {sid}")
                prefix = (parent["id"] if parent else sid) + "."
                if not tid.startswith(prefix):
                    rep.err(where, f"topic '{tid}' must start with '{prefix}'")
                check_when(f"topic '{tid}'", t.get("when"))
                exp = t.get("expand")
                if exp == "from-answer":
                    src = t.get("expand_from")
                    if not src:
                        rep.err(where, f"topic '{tid}': expand: from-answer without expand_from")
                    elif src not in qs:
                        rep.err(where, f"topic '{tid}': expand_from → question '{src}' does not exist")
                elif t.get("expand_from"):
                    rep.warn(where, f"topic '{tid}': expand_from without expand: from-answer")
                if "priority" not in t:
                    rep.warn(where, f"topic '{tid}' has no priority, defaults to 2")

    # sources
    src_ids = set()
    for s in p["sources"]:
        if s["id"] in src_ids:
            rep.err(where, f"source '{s['id']}' repeats")
        src_ids.add(s["id"])
        for c in s.get("covers", []):
            if c not in ids:
                rep.err(where, f"source '{s['id']}': covers → topic '{c}' does not exist")


# ---------- id stability ----------

def lock_entry(p: dict) -> dict:
    return {"version": p.get("version"), "ids": sorted(all_ids(p))}


def check_lock(resolved: dict[str, dict], rep: Report) -> None:
    if not LOCK.exists():
        rep.warn("_ids.lock.json", "file is missing — run with --update-lock to pin the ids")
        return
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    for pid, p in resolved.items():
        old = lock.get(pid)
        if not old:
            rep.warn(pid, "profile is not in the lock — run --update-lock")
            continue
        now = lock_entry(p)
        gone = sorted(set(old["ids"]) - set(now["ids"]))
        added = sorted(set(now["ids"]) - set(old["ids"]))
        if gone:
            rep.err(pid, "ids are gone (user progress will be lost): " + ", ".join(gone)
                    + ". If intentional — bump version and run --update-lock")
        if (gone or added) and now["version"] == old["version"]:
            rep.err(pid, f"ids changed but version is still {now['version']} — bump version")


# ---------- output ----------

PRI = {1: "●", 2: "◐", 3: "○"}


def applies(cond: dict | None, level: str | None, answers: dict[str, set[str]]) -> bool:
    if not cond:
        return True
    if level and "level" in cond and level not in cond["level"]:
        return False
    for qid, vals in cond.get("answer", {}).items():
        if qid in answers and not (answers[qid] & set(vals)):
            return False
    return True


def print_tree(p: dict, level: str | None, answers: dict[str, set[str]], lang: str = "en") -> None:
    def T(x):
        return localized(x, "title", lang, x.get("id", ""))

    def show(topics, depth):
        n = 0
        for t in topics or []:
            if not applies(t.get("when"), level, answers):
                continue
            mark = PRI.get(t.get("priority", 2))
            extra = f"  ⤷ expands from '{t['expand_from']}'" if t.get("expand") == "from-answer" else ""
            print(f"{'  ' * depth}{mark} {T(t)}  [{t['id']}]{extra}")
            n += 1 + show(t.get("children"), depth + 1)
        return n

    print(f"{T(p)}  ({' → '.join(p['extends_chain'])}, v{p.get('version')})")
    if level or answers:
        print("filter:", ", ".join([f"level={level}"] if level else []
                                  + [f"{k}={'|'.join(sorted(v))}" for k, v in answers.items()]))
    total = 0
    for s in p["stages"]:
        if not applies(s.get("when"), level, answers):
            print(f"\n{s['order']:>2}. {T(s)}  — turned off by a condition")
            continue
        flags = " (personalized)" if s.get("personalized") else ""
        flags += " (optional)" if s.get("optional") else ""
        print(f"\n{s['order']:>2}. {T(s)}{flags}")
        total += show(s.get("topics"), 2)
    print("\nCross-cutting sections")
    for c in p["cross"]:
        if not applies(c.get("when"), level, answers):
            print(f"  – {T(c)} — turned off by a condition")
            continue
        print(f"  ◇ {T(c)}  → {', '.join(c.get('used_in', [])) or 'everywhere'}")
        total += show(c.get("topics"), 2)
    print(f"\nTopics: {total}   ● essential  ◐ important  ○ optional")


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", dest="show", metavar="PROFILE", help="show the resolved profile tree")
    ap.add_argument("--json", dest="as_json", metavar="PROFILE", help="print the resolved profile as JSON")
    ap.add_argument("--level", help="filter for --print: position level")
    ap.add_argument("--answer", action="append", default=[], metavar="Q=V[,V]",
                    help="filter for --print: answer to a survey question (repeatable)")
    ap.add_argument("--lang", default="en", help="language of titles for --print: en (default) or ru (*_ru fields)")
    ap.add_argument("--update-lock", action="store_true", help="write the current ids to _ids.lock.json")
    args = ap.parse_args()

    rep = Report()
    raw = load_raw(rep)
    resolved: dict[str, dict] = {}
    for pid in raw:
        p = resolve(pid, raw, rep)
        if p:
            check(p, rep)
            resolved[pid] = p

    if args.update_lock and not rep.errors:
        LOCK.write_text(json.dumps({k: lock_entry(v) for k, v in resolved.items()},
                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"lock updated: {LOCK.relative_to(ROOT)}")
    elif not args.update_lock:
        check_lock(resolved, rep)

    target = args.show or args.as_json
    if target:
        if target not in resolved:
            rep.err(target, "profile not found or failed to resolve")
        elif args.as_json:
            print(json.dumps(resolved[target], ensure_ascii=False, indent=2))
        else:
            answers = {}
            for a in args.answer:
                k, _, v = a.partition("=")
                answers[k] = set(v.split(","))
            print_tree(resolved[target], args.level, answers, args.lang)

    out = sys.stderr if args.as_json else sys.stdout
    for line in rep.warnings + rep.errors:
        print(line, file=out)
    if not target or rep.errors:
        status = "no errors" if not rep.errors else f"errors: {len(rep.errors)}"
        print(f"\nProfiles: {len(raw)}, {status}, warnings: {len(rep.warnings)}", file=out)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
