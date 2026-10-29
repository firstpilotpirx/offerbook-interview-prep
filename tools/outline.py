#!/usr/bin/env python3
"""Plan edits: prep/outline.yaml — add, change, hide and check nodes through this script.

    run outline.py --dir . add tech.ratelimit "Rate limiting" --parent tech priority=1 origin=vacancy title_en="Rate limiting"
    run outline.py --dir . add tech.ratelimit.token-bucket "Token bucket" --parent tech.ratelimit priority=1 summary="…"
    run outline.py --dir . set tech.ratelimit priority=2 summary="…"      # k= deletes a key
    run outline.py --dir . tag tech.ratelimit acme                         # topic belongs to a company (inherited by children)
    run outline.py --dir . untag tech.ratelimit acme
    run outline.py --dir . hide tech.java tech.jvm                         # off the page, data and marks kept
    run outline.py --dir . hide --company acme                             # every group tagged only with this company
    run outline.py --dir . unhide tech.java
    run outline.py --dir . hidden                                          # what is hidden
    run outline.py --dir . check                                           # ids, priorities, companies, sizes

Rules (each one broke a real page):
- ids are never changed or reused: progress is keyed by id; a removed topic is hidden or skipped, not deleted;
- priority is 1, 2 or 3 (must / important / optional) — a word like "high" silently falls out of every filter;
- `companies: [<company id>]` marks company-specific topics; the page's company chip shows them plus every
  general topic, so a general topic is never tagged with a company "to make it visible";
- `hidden: true` takes a node and its subtree off the page (the header lists what is hidden); unhide brings it back;
- a group should have at most ~25 direct children: past that it is a list nobody ticks — split it;
- after writing, the page is rebuilt (--no-build to skip).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepio import Fail, parse_pairs, read_yaml, rebuild, write_yaml  # noqa: E402

KINDS = {"stage", "cross", "topic"}
MAX_CHILDREN = 25


def load(root: Path) -> tuple[Path, dict]:
    p = root / "prep" / "outline.yaml"
    o = read_yaml(p, None)
    if o is None:
        raise Fail("! no prep/outline.yaml yet — build the plan first (module outline)")
    o.setdefault("nodes", [])
    return p, o


def walk(nodes, parent=None, depth=0):
    for n in nodes or []:
        yield n, parent, depth
        yield from walk(n.get("children"), n, depth + 1)


def find(o: dict, nid: str) -> dict:
    for n, _, _ in walk(o["nodes"]):
        if n.get("id") == nid:
            return n
    raise Fail(f"! no node {nid}")


def company_ids(root: Path) -> set:
    return {p.parent.name for p in (root / "prep" / "companies").glob("*/company.yaml")}


def check(root: Path, o: dict) -> tuple[list, list]:
    errors, warnings = [], []
    seen = set()
    cos = company_ids(root)
    for n, parent, depth in walk(o["nodes"]):
        nid = n.get("id")
        if not nid:
            errors.append(f"node without id under {parent.get('id') if parent else 'the root'}")
            continue
        if nid in seen:
            errors.append(f"{nid}: duplicate id")
        seen.add(nid)
        if depth == 0 and n.get("kind") not in KINDS - {"topic"}:
            warnings.append(f"{nid}: a top-level node should have kind stage or cross")
        if parent and not nid.startswith(parent["id"] + ".") and depth > 0 and parent.get("kind") not in ("stage", "cross"):
            warnings.append(f"{nid}: id does not start with its parent id {parent['id']}")
        if "priority" in n and n["priority"] not in (1, 2, 3):
            errors.append(f"{nid}: priority {n['priority']!r} — must be 1, 2 or 3")
        for c in n.get("companies") or []:
            if c not in cos:
                errors.append(f"{nid}: company {c} does not exist (company.py add)")
        kids = n.get("children") or []
        if len(kids) > MAX_CHILDREN:
            warnings.append(f"{nid}: {len(kids)} children — split into groups of up to {MAX_CHILDREN}")
    return errors, warnings


def save(root: Path, p: Path, o: dict, no_build: bool) -> None:
    errors, _ = check(root, o)
    if errors:
        raise Fail("! not saved:\n  " + "\n  ".join(errors))
    write_yaml(p, o)
    if not no_build:
        rebuild(root)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--no-build", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("add"); x.add_argument("id"); x.add_argument("title"); x.add_argument("pairs", nargs="*")
    x.add_argument("--parent", help="parent node id; none — a new top-level section (give kind=stage|cross)")
    x.add_argument("--after", help="insert after this sibling id (default: at the end)")
    x = sub.add_parser("set"); x.add_argument("id"); x.add_argument("pairs", nargs="+")
    x = sub.add_parser("tag"); x.add_argument("id"); x.add_argument("companies", nargs="+")
    x = sub.add_parser("untag"); x.add_argument("id"); x.add_argument("companies", nargs="+")
    x = sub.add_parser("hide"); x.add_argument("ids", nargs="*"); x.add_argument("--company")
    x = sub.add_parser("unhide"); x.add_argument("ids", nargs="+")
    sub.add_parser("hidden")
    sub.add_parser("check")
    a = ap.parse_args()
    root = Path(a.dir).expanduser()
    p, o = load(root)

    if a.cmd == "check":
        errors, warnings = check(root, o)
        for w in warnings:
            print(f"! {w}")
        for e in errors:
            print(f"✗ {e}")
        print(f"outline: {sum(1 for _ in walk(o['nodes']))} nodes, errors {len(errors)}, warnings {len(warnings)}")
        return 1 if errors else 0
    if a.cmd == "hidden":
        rows = [n for n, _, _ in walk(o["nodes"]) if n.get("hidden")]
        for n in rows:
            print(f"{n['id']}\t{n.get('title', '')}")
        if not rows:
            print("nothing is hidden")
        return 0
    if a.cmd == "add":
        if any(n.get("id") == a.id for n, _, _ in walk(o["nodes"])):
            raise Fail(f"! {a.id} already exists — ids are never reused; use set")
        node = {"id": a.id, "title": a.title}
        node.update({k: v for k, v in parse_pairs(a.pairs).items() if v is not None})
        siblings = find(o, a.parent).setdefault("children", []) if a.parent else o["nodes"]
        if not a.parent and node.get("kind") not in ("stage", "cross"):
            raise Fail("! a top-level node needs kind=stage or kind=cross")
        pos = len(siblings)
        if a.after:
            idx = [i for i, s in enumerate(siblings) if s.get("id") == a.after]
            if not idx:
                raise Fail(f"! {a.after} is not a child of {a.parent or 'the root'}")
            pos = idx[0] + 1
        siblings.insert(pos, node)
    elif a.cmd == "set":
        n = find(o, a.id)
        for k, v in parse_pairs(a.pairs).items():
            if k in ("id", "children"):
                raise Fail(f"! {k} is not changed with set")
            if v is None:
                n.pop(k, None)
            else:
                n[k] = v
    elif a.cmd in ("tag", "untag"):
        n = find(o, a.id)
        cur = list(n.get("companies") or [])
        for c in a.companies:
            if a.cmd == "tag" and c not in cur:
                cur.append(c)
            if a.cmd == "untag" and c in cur:
                cur.remove(c)
        if cur:
            n["companies"] = cur
        else:
            n.pop("companies", None)
    elif a.cmd == "hide":
        ids = list(a.ids)
        if a.company:
            ids += [n["id"] for n, _, d in walk(o["nodes"]) if (n.get("companies") or []) == [a.company] and d <= 2]
        if not ids:
            raise Fail("! nothing to hide: give ids or --company")
        for nid in ids:
            find(o, nid)["hidden"] = True
        print("hidden: " + ", ".join(ids))
    elif a.cmd == "unhide":
        for nid in a.ids:
            find(o, nid).pop("hidden", None)
        print("shown again: " + ", ".join(a.ids))
    save(root, p, o, a.no_build)
    if a.cmd not in ("hide", "unhide"):
        print(f"outline: {a.id} updated")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as e:
        print(e, file=sys.stderr)
        sys.exit(2)
