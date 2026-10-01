#!/usr/bin/env python3
"""Vocabulary prep/words.yaml — rounds, filtering, adding cards. No manual editing needed.

    run words.py --dir . seen                         # everything already present or checked (en per line)
    run words.py --dir . filter cand.yaml --out next.yaml   # "do not take" rules for the next round
    run words.py --dir . add draft.yaml               # add cards from a draft (new round)
    run words.py --dir . round                        # round summary from "know" marks → what next

filter — rules from the methodology (modules/english.md, 2.2), everything that can be done mechanically:
  already in the deck or checked; a simple form of a known word (reading ← read,
  sender ← send, -s/-ed/-ing/-er/-ly/-ment/-ness/-tion); abbreviations (SQL, API);
  names and products (always capitalized); function words (zipf ≥ 6.5). Cognates
  (algorithm, architecture) — the agent decides: the script only marks them (`cognate?`).
  Input: a list of strings, a list of {en: …} or rank_words.py output ({candidates: [...]}).

add — draft: a YAML list of cards without id/rank/g:
  - { en: keep up with, ru: успевать за, kind: phrase, note: "…", used_in: [tech.kafka],
      ex: [{en: …, ru: …, about: system, from: tech.kafka}, …] }
  For verbs: --kind verbs ({inf, past, pp, ru, ex}); phrases: --kind phrases; answers: --kind answers.
  The script sets id (a slug with prefix w:/v:/p:/a:, NEVER changes), rank — at the end,
  g — by group_size, round — the round number; validates the schema; skips duplicates by en.
  Afterwards `run score_words.py prep/words.yaml content/` recalculates importance.

round — from prep/vocab-state.json: how much of the last round is known →
  ≥ 80% "next round ≈500", 50–80% "another round ≈200", < 50% "boundary found".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepio import Fail, read_json, read_yaml, slug, write_yaml  # noqa: E402

PREFIX = {"words": "w:", "verbs": "v:", "phrases": "p:", "answers": "a:"}
SUFFIXES = ("ing", "ed", "er", "ers", "es", "s", "ly", "ment", "ments", "ness", "tion", "ions", "ion", "able")
COGNATE_HINT = re.compile(r"(tion|sion|ism|ist|ity|ical|ure|ive|ology|ics|ator|ment)$")


def deck_path(root):
    return root / "prep" / "words.yaml"


def load_deck(root):
    d = read_yaml(deck_path(root), None) or {"version": 1, "group_size": 50, "groups": [], "words": []}
    for k in PREFIX:
        d.setdefault(k, [])
    return d


def seen_set(root, deck=None):
    deck = deck or load_deck(root)
    s = set()
    for k in PREFIX:
        for c in deck.get(k) or []:
            s.add(str(c.get("en") or c.get("inf") or "").lower().strip())
    s.discard("")
    return s


def base_forms(w):
    out = set()
    for suf in SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            b = w[: -len(suf)]
            out |= {b, b + "e"}
            if len(b) > 2 and b[-1] == b[-2]:
                out.add(b[:-1])          # stopped → stop
            if b.endswith("i"):
                out.add(b[:-1] + "y")    # studies → study
    return out


def filter_cmd(root, a):
    raw = read_yaml(Path(a.file), [])
    items = raw.get("candidates", raw) if isinstance(raw, dict) else raw
    seen = seen_set(root)
    try:
        from wordfreq import zipf_frequency
    except ImportError:
        zipf_frequency = lambda *_: 0  # noqa: E731
    keep, dropped = [], {}
    for it in items:
        en = (it if isinstance(it, str) else it.get("en", "")).strip()
        low = en.lower()
        reason = None
        if not low:
            continue
        if low in seen:
            reason = "already seen"
        elif any(b in seen for b in base_forms(low)):
            reason = "form of known word"
        elif re.fullmatch(r"[A-Z0-9]{2,6}s?", en):
            reason = "abbreviation"
        elif en[:1].isupper() and not (isinstance(it, dict) and it.get("keep")) and zipf_frequency(low, "en") < 3.5:
            reason = "name or product"
        elif " " not in low and zipf_frequency(low, "en") >= 6.5:
            reason = "function word"
        if reason:
            dropped[reason] = dropped.get(reason, 0) + 1
            continue
        row = dict(it) if isinstance(it, dict) else {"en": en}
        if " " not in low and COGNATE_HINT.search(low):
            row["cognate?"] = True
        keep.append(row)
        seen.add(low)
    out = {"candidates": keep, "dropped": dropped}
    if a.out:
        write_yaml(Path(a.out), out)
    else:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"kept {len(keep)}; dropped: " + ", ".join(f"{k} {v}" for k, v in dropped.items()), file=sys.stderr)


def add_cmd(root, a):
    deck = load_deck(root)
    draft = read_yaml(Path(a.file), [])
    if isinstance(draft, dict):
        draft = draft.get(a.kind) or draft.get("words") or []
    lst = deck[a.kind]
    ids = {c["id"] for k in PREFIX for c in deck[k]}
    seen = seen_set(root, deck)
    rnd = a.round or (max([c.get("round", 1) for c in deck["words"]] or [0]) + 1)
    size = deck.get("group_size") or 50
    added = skipped = 0
    rank = max([c.get("rank", 0) for c in lst] or [0])
    for c in draft:
        key = str(c.get("en") or c.get("inf") or "").strip()
        if not key or key.lower() in seen:
            skipped += 1
            continue
        cid = PREFIX[a.kind] + slug(key)
        n = 2
        while cid in ids:
            cid = f"{PREFIX[a.kind]}{slug(key)}-{n}"; n += 1
        card = {"id": cid, **{k: v for k, v in c.items() if k not in ("id", "rank", "g", "cognate?")}}
        if a.kind in ("words", "phrases"):
            rank += 1
            card["rank"] = rank
            card["g"] = (rank - 1) // size + 1
        if a.kind == "words":
            card["round"] = rnd
        lst.append(card); ids.add(cid); seen.add(key.lower()); added += 1
    if a.kind == "words":
        n_groups = (len(lst) + size - 1) // size
        have = {g.get("g") for g in deck.get("groups") or []}
        for g in range(1, n_groups + 1):
            if g not in have:
                deck.setdefault("groups", []).append({"g": g, "title": f"Слова {(g - 1) * size + 1}–{g * size}",
                                                      "title_en": f"Words {(g - 1) * size + 1}–{g * size}"})
    for k in list(deck):
        if k in PREFIX and not deck[k]:
            del deck[k]
    write_yaml(deck_path(root), deck, "words.schema.json")
    print(f"added {added}, skipped (duplicates) {skipped}; round {rnd}. Next: run score_words.py prep/words.yaml content/")


def round_cmd(root, a):
    deck = load_deck(root)
    vs = read_json(root / "prep" / "vocab-state.json", {}) or {}
    known, checked = set(), set()
    for rec in vs.values():
        if isinstance(rec, dict) and not rec.get("reset"):
            known |= set(rec.get("known") or [])
            checked |= set(rec.get("known") or []) | set(rec.get("unknown") or [])
    rounds = {}
    for c in deck["words"]:
        r = c.get("round", 1)
        x = rounds.setdefault(r, {"total": 0, "checked": 0, "known": 0})
        x["total"] += 1; x["checked"] += c["id"] in checked; x["known"] += c["id"] in known
    if not rounds:
        print(json.dumps({"advice": "no vocabulary yet — first round (modules/english.md, 2.2)"}, ensure_ascii=False))
        return
    last = max(rounds)
    r = rounds[last]
    share = r["known"] / r["checked"] if r["checked"] else None
    if r["checked"] < r["total"]:
        advice = f"round {last} not fully checked ({r['checked']} of {r['total']}) — finish checking on the page first"
    elif share >= 0.8:
        advice = "knows ≥ 80% — next round ≈ 500 words further down the frequency list"
    elif share >= 0.5:
        advice = "knows 50–80% — one more round ≈ 200 words"
    else:
        advice = "knows < 50% — vocabulary boundary found, stop rounds and start learning"
    learn = sum(1 for c in deck["words"] if c["id"] not in known)
    print(json.dumps({"rounds": rounds, "last": last, "known_share": round(share, 2) if share is not None else None,
                      "to_learn": learn, "advice": advice}, ensure_ascii=False, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seen")
    f = sub.add_parser("filter"); f.add_argument("file"); f.add_argument("--out")
    ad = sub.add_parser("add"); ad.add_argument("file"); ad.add_argument("--kind", choices=list(PREFIX), default="words")
    ad.add_argument("--round", type=int)
    sub.add_parser("round")
    a = ap.parse_args()
    root = Path(a.dir).expanduser()
    if a.cmd == "seen":
        print("\n".join(sorted(seen_set(root))))
    elif a.cmd == "filter":
        filter_cmd(root, a)
    elif a.cmd == "add":
        add_cmd(root, a)
    elif a.cmd == "round":
        round_cmd(root, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
