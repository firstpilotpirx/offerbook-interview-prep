#!/usr/bin/env python3
"""What's new since the person's version — for the upgrade screen.

    run whats_new.py --dir .                 # since the version in prep/session.yaml
    run whats_new.py --from 0.5.0 --lang en --json

Reads the plugin's CHANGELOG.yaml: notes of all versions newer than the previous one,
and a combined list of actions (rebuild_page, ask:<question>, offer:<what>,
profile_topics) without duplicates. Questions that already have an answer in
prep/answers.yaml are removed from ask:.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langs as lg  # noqa: E402
from migrate import ver_tuple, load_yaml  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--lang")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.dir).expanduser()
    session = load_yaml(root / "prep" / "session.yaml", {}) or {}
    frm = args.frm or session.get("plugin_version") or "0.0.0"
    lang = args.lang or lg.primary(root)
    answers = (load_yaml(root / "prep" / "answers.yaml", {}) or {}).get("answers", {}) or {}
    log = yaml.safe_load((REPO / "CHANGELOG.yaml").read_text(encoding="utf-8")) or []
    newer = [e for e in log if ver_tuple(e["version"]) > ver_tuple(frm)]
    newer.sort(key=lambda e: ver_tuple(e["version"]))
    actions = []
    for e in newer:
        for a in e.get("actions") or []:
            if a.startswith("ask:") and a[4:] in answers:
                continue
            if a not in actions:
                actions.append(a)
    notes = [{"version": e["version"], "notes": (e.get("notes") or {}).get(lang) or (e.get("notes") or {}).get("en") or []}
             for e in newer]
    out = {"from": frm, "to": newer[-1]["version"] if newer else frm, "versions": notes, "actions": actions}
    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        if not newer:
            print("No new versions.")
        for n in reversed(notes):
            print(f"{n['version']}:")
            for line in n["notes"]:
                print(f"  • {line}")
        if actions:
            print("Actions:", ", ".join(actions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
