#!/usr/bin/env python3
"""Translating the page interface into the explanation language, other than ru and en.

    run i18n.py --dir . dump > /tmp/en.json          # English strings — source for translation
    run i18n.py --dir . check                         # what is missing in prep/i18n.<lang>.json
    run i18n.py --dir . merge /tmp/de.json            # write the translation (keys are verified)

Interface strings live in templates/portal/i18n.json (ru, en). For another language the agent
translates the whole English block, keeping the keys, and writes it via merge.
The page shows missing keys in English.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langs as lg  # noqa: E402
from prepio import REPO, Fail, read_json, write_json  # noqa: E402

BASE = REPO / "templates" / "portal" / "i18n.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--lang")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dump"); sub.add_parser("check")
    m = sub.add_parser("merge"); m.add_argument("file")
    a = ap.parse_args()
    root = Path(a.dir).expanduser()
    lang = a.lang or lg.primary(root)
    base = json.loads(BASE.read_text(encoding="utf-8"))
    target = root / "prep" / f"i18n.{lang}.json"
    if a.cmd == "dump":
        print(json.dumps(base["en"], ensure_ascii=False, indent=1))
        return 0
    if lang in ("ru", "en"):
        print(f"language {lang} is built in — no translation needed")
        return 0
    have = read_json(target, {}) or {}
    if a.cmd == "merge":
        new = read_json(Path(a.file), None)
        if not isinstance(new, dict):
            raise Fail("! expected a JSON object key → string")
        unknown = sorted(set(new) - set(base["en"]))
        bad = [k for k, v in new.items() if not isinstance(v, str) or not v.strip()]
        if unknown or bad:
            raise Fail(f"! unknown keys: {unknown[:10]}; empty: {bad[:10]} — file not written")
        have.update(new)
        write_json(target, have)
    missing = sorted(set(base["en"]) - set(have))
    print(json.dumps({"lang": lang, "file": str(target), "have": len(have), "total": len(base["en"]),
                      "missing": missing}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
