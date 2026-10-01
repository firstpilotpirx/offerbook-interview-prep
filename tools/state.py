#!/usr/bin/env python3
"""Writing preparation state — instead of editing YAML by hand.

    run state.py --dir . session set mode=local page_url=http://localhost:8765/
    run state.py --dir . session get [key]
    run state.py --dir . answer set explain-language=ru level=senior 'databases=["postgresql","redis"]'
    run state.py --dir . answer get [key]
    run state.py --dir . wizard step explain --answer languages=ru,en          # step done (+ answers)
    run state.py --dir . wizard skip company                                   # step skipped
    run state.py --dir . wizard finish
    run state.py --dir . page import --state s.json --trainer t.json --vocab v.json --inbox i.json
    run state.py --dir . page export                                           # what to write to the page database
    run state.py --dir . page counts

Files: prep/session.yaml, prep/answers.yaml (answers:), prep/wizard.yaml,
prep/page-state.json, trainer-state.json, vocab-state.json, inbox.json.

`page import` accepts what ArtifactData returned (a document — an object or
{data: …}; a collection — a list of {id, data} or an object {id: data}) and normalizes
it to one shape. Empty or broken input does not overwrite the progress file.

After writing, the page is rebuilt (except session and page): --no-build to skip.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepio import Fail, apply, parse_pairs, read_json, read_yaml, rebuild, write_json, write_yaml  # noqa: E402

WIZARD_IDS = ["explain", "goal", "profile", "resume", "vacancy", "company", "basis", "level", "stack", "language",
              "weak", "generate"]
# wizard answers that the profile also needs (prep/answers.yaml) are written to both files
SHARED = {"languages", "explain-language", "english-train", "english-level", "interview-language", "level", "deadline"}


def session_cmd(root, a):
    p = root / "prep" / "session.yaml"
    s = read_yaml(p, {}) or {}
    if a.op == "get":
        print(json.dumps(s.get(a.key) if a.key else s, ensure_ascii=False, default=str))
        return
    pairs = parse_pairs(a.pairs)
    if "built_at" in pairs and pairs["built_at"] == "now":
        pairs["built_at"] = int(time.time())
    write_yaml(p, apply(s, pairs))
    print("session:", ", ".join(f"{k}={v}" for k, v in pairs.items()))


def answers_file(root):
    p = root / "prep" / "answers.yaml"
    return p, read_yaml(p, {}) or {}


def normalize_langs(pairs: dict, ans: dict) -> None:
    """languages: list of codes, main one first; explain-language always = languages[0]."""
    if "explain-language" in pairs and pairs["explain-language"] is not None:
        v = str(pairs["explain-language"]).lower()
        if len(v) != 2 or not v.isalpha():
            raise Fail("! explain-language is a two-letter code: en, ru, de, es…")
        pairs["explain-language"] = v
        if "languages" not in pairs and ans.get("languages"):
            rest = [x for x in ans["languages"] if x != v]
            pairs["languages"] = [v] + rest
    if "languages" in pairs and pairs["languages"] is not None:
        import re as _re
        raw = pairs["languages"]
        raw = _re.split(r"[,\s]+", raw) if isinstance(raw, str) else raw
        codes = []
        for x in raw or []:
            x = str(x).strip().lower()
            if not _re.fullmatch(r"[a-z]{2}", x):
                raise Fail(f"! languages: two-letter codes, main one first: ru,en — got {x!r}")
            if x not in codes:
                codes.append(x)
        if not codes:
            raise Fail("! languages: at least one language")
        pairs["languages"] = codes
        pairs["explain-language"] = codes[0]


def answer_cmd(root, a):
    p, data = answers_file(root)
    ans = data.setdefault("answers", {})
    if a.op == "get":
        print(json.dumps(ans.get(a.key) if a.key else ans, ensure_ascii=False, default=str))
        return
    pairs = parse_pairs(a.pairs)
    normalize_langs(pairs, ans)
    apply(ans, pairs)
    write_yaml(p, data)
    print("answers:", ", ".join(f"{k}={v}" for k, v in pairs.items()))
    if not a.no_build:
        rebuild(root)


def wizard_cmd(root, a):
    p = root / "prep" / "wizard.yaml"
    w = read_yaml(p, {}) or {}
    w.setdefault("path", []); w.setdefault("skipped", []); w.setdefault("answers", {})
    if a.op in ("step", "skip"):
        if a.step not in WIZARD_IDS:
            raise Fail(f"! unknown step {a.step}; available: {', '.join(WIZARD_IDS)}")
        lst, other = ("path", "skipped") if a.op == "step" else ("skipped", "path")
        if a.step not in w[lst]:
            w[lst].append(a.step)
        if a.step in w[other]:
            w[other].remove(a.step)
        pairs = parse_pairs(a.answer or [])
        _, cur = answers_file(root)
        normalize_langs(pairs, cur.get("answers", {}) or {})
        apply(w["answers"], pairs)
        nxt = next((s for s in WIZARD_IDS if s not in w["path"] and s not in w["skipped"]), "generate")
        w["step"] = nxt
        write_yaml(p, w)
        shared = {k: v for k, v in pairs.items() if k in SHARED}
        if shared:
            ap_, data = answers_file(root)
            apply(data.setdefault("answers", {}), shared)
            write_yaml(ap_, data)
        print(f"wizard: {a.op} {a.step} → next {nxt}")
    elif a.op == "finish":
        w["finished"] = True
        write_yaml(p, w)
        print("wizard: finished")
    elif a.op == "get":
        print(json.dumps(w, ensure_ascii=False, default=str))
        return
    if not a.no_build:
        rebuild(root)


def _doc(x):
    if isinstance(x, dict) and set(x) <= {"data", "id", "exists"} and isinstance(x.get("data"), dict):
        return x["data"]
    return x


def _coll(x):
    if isinstance(x, list):
        out = {}
        for it in x:
            if isinstance(it, dict) and "id" in it:
                out[it["id"]] = it.get("data", {k: v for k, v in it.items() if k != "id"})
        return out
    if isinstance(x, dict):
        return {k: _doc(v) for k, v in x.items()}
    return {}


def page_cmd(root, a):
    prep = root / "prep"
    import backup as bk
    if a.op == "counts":
        print(json.dumps(bk.counts(root), ensure_ascii=False))
        return
    if a.op == "export":
        print(json.dumps({
            "doc prep/state": read_json(prep / "page-state.json", {}),
            "doc trainer/state": read_json(prep / "trainer-state.json", {}),
            "collection vocab": read_json(prep / "vocab-state.json", {}),
        }, ensure_ascii=False))
        return
    before = bk.counts(root)
    plan = [("state", "page-state.json", _doc), ("trainer", "trainer-state.json", _doc),
            ("vocab", "vocab-state.json", _coll), ("inbox", "inbox.json", None)]
    for key, fname, norm in plan:
        src = getattr(a, key)
        if not src:
            continue
        raw = read_json(Path(src), None)
        if raw in (None, {}, []):
            print(f"  {key}: empty — leaving the file untouched")
            continue
        if key == "inbox":
            data = list(_coll(raw).values()) if not isinstance(raw, list) or (raw and "data" in raw[0]) else raw
        else:
            data = norm(raw)
        if key == "trainer" and "items" not in data:
            data = {"items": data, "updated": int(time.time() * 1000)}
        write_json(prep / fname, data)
        print(f"  {key} → prep/{fname}")
    after = bk.counts(root)
    shrink = [k for k in before if after.get(k, 0) < before[k] and k in ("done", "skip", "trainer", "vocab_checked")]
    if shrink:
        print("! the page has less than the files had: " + ", ".join(f"{k} {before[k]}→{after[k]}" for k in shrink)
              + ". The previous state is in prep/backups; check that this is the right page.")
    print("counts:", json.dumps(after, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--no-build", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("session", "answer"):
        s = sub.add_parser(name)
        ss = s.add_subparsers(dest="op", required=True)
        g = ss.add_parser("get"); g.add_argument("key", nargs="?")
        st = ss.add_parser("set"); st.add_argument("pairs", nargs="+")
    w = sub.add_parser("wizard")
    ws = w.add_subparsers(dest="op", required=True)
    for op in ("step", "skip"):
        x = ws.add_parser(op); x.add_argument("step"); x.add_argument("--answer", action="append")
    ws.add_parser("finish"); ws.add_parser("get")
    pg = sub.add_parser("page")
    ps = pg.add_subparsers(dest="op", required=True)
    im = ps.add_parser("import")
    for k in ("state", "trainer", "vocab", "inbox"):
        im.add_argument(f"--{k}")
    ps.add_parser("export"); ps.add_parser("counts")
    a = ap.parse_args()
    root = Path(a.dir).expanduser()
    {"session": session_cmd, "answer": answer_cmd, "wizard": wizard_cmd, "page": page_cmd}[a.cmd](root, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
