#!/usr/bin/env python3
"""Migrating preparation data to a new plugin version — without losing progress.

    run migrate.py --dir . --status          # versions: data and plugin, whether an upgrade is needed
    run migrate.py --dir . --dry-run         # what would be done, changing nothing
    run migrate.py --dir .                   # backup → migrations → verification → version mark
    run migrate.py --dir . --init            # new folder: just record the current versions

The order is always the same:
1. Backup (tools/backup.py) — migration does not start without it.
2. Migration steps in order, from the data version in prep/session.yaml to DATA_VERSION.
   Each step is idempotent: running it again breaks nothing.
3. Topic id renames from profiles/_renames.yaml — in page marks,
   the plan, material blocks, card used_in, trainer state.
4. Comparing progress counters before and after (done, excluded, trainer
   cards, checked words, material blocks, companies). If anything
   decreased — automatic rollback from the backup and exit code 2.
5. In prep/session.yaml: data_version, plugin_version, upgraded_at, history.

Output: a MIGRATED / NOTHING / ROLLED_BACK line and JSON with details (--json).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backup as bk  # noqa: E402
import langs as lg  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DATA_VERSION = 4


def ver_tuple(v) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:3]) or (0,)


def load_yaml(p: Path, default=None):
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or default) if p.exists() else default


def dump_yaml(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def guess_data_version(root: Path) -> int:
    """Old folders without a version mark: detect by indicators."""
    ans = (load_yaml(root / "prep" / "answers.yaml", {}) or {}).get("answers", {}) or {}
    if "languages" in ans:
        return 4
    if "explain-language" in ans:
        return 3
    if "english-train" in ans:
        return 2
    return 1


# ---------------- migration steps ----------------
def m1_to_2(root: Path, log: list) -> None:
    """0.6: the english-train question. We do not invent an answer — the hub will ask with buttons (next_steps)."""
    log.append("english-train: ask in the menu if there is no answer")


def m2_to_3(root: Path, log: list) -> None:
    """0.8: explanation language. Old preparations — inferred from material files (as before the upgrade)."""
    p = root / "prep" / "answers.yaml"
    data = load_yaml(p, {}) or {}
    ans = data.setdefault("answers", {})
    if "explain-language" not in ans:
        ans["explain-language"] = lg.primary(root)
        dump_yaml(p, data)
        log.append(f"explain-language: {ans['explain-language']} (from existing materials)")


MIN_TS = 1420070400000  # 2015-01-01 in ms


def to_ts(v):
    """A mark's date as ms, or None (true, 1, garbage). Seconds and ISO strings are converted."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, str):
        if v.isdigit():
            v = int(v)
        else:
            try:
                v = dt.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp() * 1000
            except ValueError:
                return None
    if not isinstance(v, (int, float)):
        return None
    if 1e9 < v < 1e11:
        v *= 1000
    return int(v) if v >= MIN_TS else None


def normalize_page_state(root: Path, log: list) -> None:
    """Marks keep real dates: done[id] = ms (from doneAt if needed) or true; startedAt — ms or null."""
    sp = root / "prep" / "page-state.json"
    if not sp.exists():
        return
    st = json.loads(sp.read_text(encoding="utf-8"))
    done, at = st.get("done") or {}, st.get("doneAt") or {}
    fixed = 0
    for k, v in list(done.items()):
        if not v:
            done.pop(k); continue
        ts = to_ts(v) or to_ts(at.get(k))
        nv = ts if ts else True
        if nv != v:
            done[k] = nv; fixed += 1
    st["done"] = done
    st.pop("doneAt", None)
    sa = to_ts(st.get("startedAt"))
    if sa != st.get("startedAt"):
        st["startedAt"] = sa; fixed += 1
    if fixed:
        sp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        log.append(f"page marks: {fixed} dates normalized")


def m3_to_4(root: Path, log: list) -> None:
    """0.13: course languages (several or one); mark dates normalized. Written down from what the folder already has."""
    normalize_page_state(root, log)
    p = root / "prep" / "answers.yaml"
    data = load_yaml(p, {}) or {}
    ans = data.setdefault("answers", {})
    if not ans.get("languages"):
        ans["languages"] = lg.chosen(root)
        ans["explain-language"] = ans["languages"][0]
        dump_yaml(p, data)
        log.append(f"languages: {', '.join(ans['languages'])} (from existing materials)")


STEPS = {1: m1_to_2, 2: m2_to_3, 3: m3_to_4}


# ---------------- id renames ----------------
def renames_for(root: Path) -> dict:
    outline = load_yaml(root / "prep" / "outline.yaml", {}) or {}
    prof = outline.get("profile")
    reg = load_yaml(REPO / "profiles" / "_renames.yaml", {}) or {}
    have = int(outline.get("profile_version") or 0)
    out = {}
    for r in reg.get(prof, []) or []:
        if int(r.get("since", 0)) > have:
            out[r["from"]] = r["to"]
    return out


def apply_renames(root: Path, ren: dict, log: list) -> None:
    if not ren:
        return
    def sub_id(i):  # both the ids themselves and nested ones: tech.old → tech.new, tech.old.x → tech.new.x
        for a, b in ren.items():
            if i == a or i.startswith(a + "."):
                return b + i[len(a):]
        return i
    prep = root / "prep"
    # page marks
    sp = prep / "page-state.json"
    if sp.exists():
        st = json.loads(sp.read_text(encoding="utf-8"))
        for k in ("done", "skip", "collapsed", "expanded"):
            if isinstance(st.get(k), dict):
                st[k] = {sub_id(i): v for i, v in st[k].items()}
        sp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    # plan
    op = prep / "outline.yaml"
    o = load_yaml(op, {}) or {}
    def walk(nodes):
        for n in nodes or []:
            n["id"] = sub_id(n["id"]); walk(n.get("children"))
    walk(o.get("nodes"))
    if isinstance(o.get("state"), dict):
        for k in ("done", "skip"):
            o["state"][k] = [sub_id(i) for i in o["state"].get(k) or []]
    if o:
        dump_yaml(op, o)
    # materials
    for f in (root / "content").glob("*.md") if (root / "content").exists() else []:
        t = f.read_text(encoding="utf-8")
        t2 = re.sub(r"^(@@\s+)(\S+)", lambda m: m.group(1) + sub_id(m.group(2)), t, flags=re.M)
        if t2 != t:
            f.write_text(t2, encoding="utf-8")
    # cards
    wp = prep / "words.yaml"
    deck = load_yaml(wp, None)
    if deck:
        for kind in ("words", "phrases", "answers"):
            for c in deck.get(kind) or []:
                if c.get("used_in"):
                    c["used_in"] = [sub_id(i) for i in c["used_in"]]
                for e in c.get("ex") or []:
                    if isinstance(e, dict) and e.get("from"):
                        e["from"] = sub_id(e["from"])
        dump_yaml(wp, deck)
    log.append(f"renamed ids: {len(ren)}")


# ---------------- old trainer: w<number> → w:<slug> ----------------
def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def migrate_legacy_trainer(root: Path, log: list) -> None:
    """Keys like w12/v3/p7 (old portal, progress by number) → card ids by the en field.
    Requires prep/legacy-deck.json — the old page's deck ({words:[{i,en}], verbs:[{i,inf}], phrases:[{i,en}]})."""
    tp, lp = root / "prep" / "trainer-state.json", root / "prep" / "legacy-deck.json"
    if not tp.exists() or not lp.exists():
        return
    st = json.loads(tp.read_text(encoding="utf-8"))
    items = st.get("items", st)
    legacy = [k for k in items if re.fullmatch(r"[wvp]\d+", k)]
    if not legacy:
        return
    old = json.loads(lp.read_text(encoding="utf-8"))
    deck = load_yaml(root / "prep" / "words.yaml", {}) or {}
    by_en = {}
    for kind, pre in (("words", "w"), ("verbs", "v"), ("phrases", "p")):
        for c in deck.get(kind) or []:
            by_en[(pre, slug(str(c.get("en") or c.get("inf") or "")))] = c["id"]
    moved, lost = 0, []
    for k in legacy:
        pre, i = k[0], int(k[1:])
        src = {"w": "words", "v": "verbs", "p": "phrases"}[pre]
        rec = next((x for x in old.get(src, []) if int(x.get("i", -1)) == i), None)
        new = rec and by_en.get((pre, slug(str(rec.get("en") or rec.get("inf") or ""))))
        if new:
            if new not in items:
                items[new] = items[k]
            del items[k]; moved += 1
        else:
            lost.append(k)
    if "items" in st:
        st["items"] = items
    tp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    log.append(f"old trainer: moved {moved}" + (f", left as is without a match: {len(lost)}" if lost else ""))


# ---------------- main ----------------
def compare(before: dict, after: dict) -> list:
    return [f"{k}: was {before[k]}, now {after.get(k, 0)}" for k in before if after.get(k, 0) < before[k]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.dir).expanduser()
    sp = root / "prep" / "session.yaml"
    session = load_yaml(sp, {}) or {}
    plugin = bk.plugin_version()
    have_plugin = session.get("plugin_version")
    have_data = session.get("data_version") or guess_data_version(root)
    has_data = (root / "prep").exists() and any((root / "prep").iterdir())

    status = {"plugin_version": plugin, "was_plugin_version": have_plugin, "data_version": have_data,
              "target_data_version": DATA_VERSION, "has_data": has_data,
              "needs_upgrade": has_data and (ver_tuple(have_plugin) < ver_tuple(plugin) or have_data < DATA_VERSION),
              "renames": renames_for(root) if has_data else {}}

    if args.init:
        session.update({"plugin_version": plugin, "data_version": DATA_VERSION})
        dump_yaml(sp, session)
        print(f"INIT plugin {plugin}, data {DATA_VERSION}")
        return 0
    if args.status or args.dry_run:
        if args.dry_run:
            status["steps"] = [STEPS[v].__doc__.strip().splitlines()[0] for v in range(have_data, DATA_VERSION) if v in STEPS]
            status["counts"] = bk.counts(root)
        print(json.dumps(status, ensure_ascii=False, indent=None if args.json else 1))
        return 0
    if not status["needs_upgrade"]:
        print("NOTHING — data is already in this version's format")
        return 0

    before = bk.counts(root)
    backup = bk.create(root, f"upgrade-{have_plugin or 'old'}-to-{plugin}")
    log: list = []
    try:
        for v in range(have_data, DATA_VERSION):
            if v in STEPS:
                STEPS[v](root, log)
        apply_renames(root, status["renames"], log)
        migrate_legacy_trainer(root, log)
    except Exception as e:  # rollback on any error
        bk.restore(root, backup)
        print(f"ROLLED_BACK migration error: {e}\n  data restored from {backup}")
        return 2
    after = bk.counts(root)
    lost = compare(before, after)
    if lost:
        bk.restore(root, backup)
        print("ROLLED_BACK progress decreased — data restored from backup:\n  " + "\n  ".join(lost)
              + f"\n  backup: {backup}")
        return 2
    hist = session.get("history") or []
    hist.append({"from": have_plugin, "to": plugin, "at": dt.datetime.now().isoformat(timespec="seconds"),
                 "backup": str(backup.relative_to(root))})
    session.update({"plugin_version": plugin, "data_version": DATA_VERSION,
                    "upgraded_at": dt.datetime.now().isoformat(timespec="seconds"), "history": hist[-20:]})
    dump_yaml(sp, session)
    res = {"backup": str(backup), "log": log, "before": before, "after": after, "from": have_plugin, "to": plugin}
    print(json.dumps(res, ensure_ascii=False) if args.json else
          f"MIGRATED {have_plugin or 'old version'} → {plugin}\n  backup: {backup}\n  " + "\n  ".join(log or ["data format unchanged"])
          + f"\n  progress before/after: {before} / {after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
