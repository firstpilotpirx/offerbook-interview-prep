#!/usr/bin/env python3
"""Interviews: company card prep/companies/<id>/company.yaml — only through this script.

    run company.py --dir . add "Acme Payments" status=applied vacancy.title="Senior Backend" vacancy.url=https://…
    run company.py --dir . set acme status=active vacancy.salary="€80–95k"
    run company.py --dir . contact acme Anna role=recruiter
    run company.py --dir . stage acme tech status=scheduled date=2026-10-02 time=15:00 format=video 'with=["Mark"]'
    run company.py --dir . stage acme tech-1 status=passed feelings="Fine" next="Wait a week"
    run company.py --dir . question acme tech-1 "How does Kafka keep order?" topic=tech.kafka went=bad note="…"
    run company.py --dir . log acme hr-call "Range up to 95k" with=Anna 'facts={"range":"€80–95k"}'
    run company.py --dir . vacancy acme vacancy.md          # put the job posting text into the company folder
    run company.py --dir . show acme

Rules:
- company id is a slug of the name; stage id is <stage>-<n> (tech-1, tech-2); `stage acme tech …`
  without a number: update the last unfinished tech stage or create the next one;
- updated is set automatically; date defaults to today;
- the record is validated against schemas/company.schema.json; on error the file is not changed;
- after writing, the page is rebuilt (--no-build to skip).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepio import Fail, parse_pairs, read_yaml, rebuild, slug, write_yaml  # noqa: E402

SCHEMA = "company.schema.json"
OPEN = {"expected", "scheduled"}


def today() -> str:
    return dt.date.today().isoformat()


def path(root: Path, cid: str) -> Path:
    return root / "prep" / "companies" / cid / "company.yaml"


def load(root: Path, cid: str) -> dict:
    p = path(root, cid)
    if not p.exists():
        have = [x.parent.name for x in (root / "prep" / "companies").glob("*/company.yaml")]
        raise Fail(f"! no company {cid}; available: {', '.join(have) or 'none'}")
    return read_yaml(p, {})


def set_dotted(d: dict, pairs: dict) -> None:
    for k, v in pairs.items():
        cur = d
        parts = k.split(".")
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        if v is None:
            cur.pop(parts[-1], None)
        else:
            cur[parts[-1]] = v


def save(root: Path, c: dict, no_build: bool) -> None:
    c["updated"] = today()
    write_yaml(path(root, c["id"]), c, SCHEMA)
    if not no_build:
        rebuild(root)


def find_stage(c: dict, ref: str, create: bool) -> dict:
    stages = c.setdefault("stages", [])
    if re.fullmatch(r"[a-z][a-z0-9-]*-\d+", ref):
        st = next((s for s in stages if s["id"] == ref), None)
        if st:
            return st
        if not create:
            raise Fail(f"! no stage {ref}")
        base = ref.rsplit("-", 1)[0]
        st = {"id": ref, "stage": base, "status": "expected"}
        stages.append(st)
        return st
    same = [s for s in stages if s["stage"] == ref]
    open_ = [s for s in same if s.get("status") in OPEN]
    if open_:
        return open_[0]
    if not create:
        raise Fail(f"! no open stage {ref}")
    st = {"id": f"{ref}-{len(same) + 1}", "stage": ref, "status": "expected"}
    stages.append(st)
    return st


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--no-build", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("add"); x.add_argument("name"); x.add_argument("pairs", nargs="*"); x.add_argument("--id")
    x = sub.add_parser("set"); x.add_argument("cid"); x.add_argument("pairs", nargs="+")
    x = sub.add_parser("contact"); x.add_argument("cid"); x.add_argument("name"); x.add_argument("pairs", nargs="*")
    x = sub.add_parser("stage"); x.add_argument("cid"); x.add_argument("ref"); x.add_argument("pairs", nargs="*")
    x = sub.add_parser("question"); x.add_argument("cid"); x.add_argument("ref"); x.add_argument("q"); x.add_argument("pairs", nargs="*")
    x = sub.add_parser("log"); x.add_argument("cid"); x.add_argument("kind"); x.add_argument("text"); x.add_argument("pairs", nargs="*")
    x = sub.add_parser("vacancy"); x.add_argument("cid"); x.add_argument("file")
    x = sub.add_parser("show"); x.add_argument("cid")
    sub.add_parser("list")
    a = ap.parse_args()
    root = Path(a.dir).expanduser()

    if a.cmd == "list":
        for p in sorted((root / "prep" / "companies").glob("*/company.yaml")):
            c = read_yaml(p, {})
            print(f"{c.get('id')}\t{c.get('status')}\t{c.get('name')}")
        return 0
    if a.cmd == "add":
        cid = a.id or slug(a.name)
        if path(root, cid).exists():
            raise Fail(f"! company {cid} already exists — use set")
        c = {"id": cid, "name": a.name, "status": "lead", "created": today()}
        outline = read_yaml(root / "prep" / "outline.yaml", {}) or {}
        if outline.get("profile"):
            c["profile"] = outline["profile"]
        set_dotted(c, parse_pairs(a.pairs))
        save(root, c, a.no_build)
        print(f"company: {cid} added")
        return 0
    c = load(root, a.cid)
    if a.cmd == "show":
        print(json.dumps(c, ensure_ascii=False, indent=1, default=str))
        return 0
    if a.cmd == "set":
        set_dotted(c, parse_pairs(a.pairs))
    elif a.cmd == "contact":
        cs = c.setdefault("contacts", [])
        ct = next((x for x in cs if x.get("name") == a.name), None)
        if not ct:
            ct = {"name": a.name}; cs.append(ct)
        set_dotted(ct, parse_pairs(a.pairs))
    elif a.cmd == "stage":
        st = find_stage(c, a.ref, create=True)
        set_dotted(st, parse_pairs(a.pairs))
        if c.get("status") in ("lead", "applied") and st.get("status") in ("scheduled", "passed"):
            c["status"] = "active"
        print(f"stage: {st['id']} {st.get('status')}")
    elif a.cmd == "question":
        st = find_stage(c, a.ref, create=False)
        q = {"q": a.q}; set_dotted(q, parse_pairs(a.pairs))
        st.setdefault("questions", []).append(q)
    elif a.cmd == "log":
        e = {"date": today(), "kind": a.kind, "text": a.text}
        set_dotted(e, parse_pairs(a.pairs))
        c.setdefault("log", []).append(e)
        c["log"].sort(key=lambda r: str(r.get("date")))
    elif a.cmd == "vacancy":
        dst = path(root, a.cid).parent / "vacancy.md"
        shutil.copyfile(a.file, dst)
        c.setdefault("vacancy", {})["file"] = "vacancy.md"
    save(root, c, a.no_build)
    print(f"company: {a.cid} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
