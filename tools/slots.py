#!/usr/bin/env python3
"""Interview slots in the person's time zone — exact, with daylight saving time on both sides.

    run slots.py --from Europe/London --to Europe/Berlin "2026-11-12 16:30" "2026-11-16 15:00"
    run slots.py --from America/New_York "2026-11-02 10:00"          # --to defaults to the local zone
    run slots.py --to Europe/Berlin --json "2026-11-16T15:00+00:00"   # an offset in the text wins over --from

Prints each slot in both zones, the weekday and how many days are left. Never convert by hand: around
the end of March and the end of October the offset between two cities changes on different dates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from zoneinfo import ZoneInfo


def parse(s: str, src: ZoneInfo) -> dt.datetime:
    s = s.strip().replace("T", " ")
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        sys.exit(f"! cannot read the time: {s!r} — use YYYY-MM-DD HH:MM")
    return d if d.tzinfo else d.replace(tzinfo=src)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slots", nargs="+")
    ap.add_argument("--from", dest="src", default="UTC", help="IANA zone the slots are written in (Europe/London)")
    ap.add_argument("--to", dest="dst", help="IANA zone of the person (default: this computer's zone)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    src = ZoneInfo(a.src)
    dst = ZoneInfo(a.dst) if a.dst else dt.datetime.now().astimezone().tzinfo
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for s in a.slots:
        d = parse(s, src)
        loc = d.astimezone(dst)
        rows.append({"given": s, "source": d.isoformat(timespec="minutes"), "local": loc.isoformat(timespec="minutes"),
                     "local_date": loc.date().isoformat(), "local_time": loc.strftime("%H:%M"),
                     "weekday": loc.strftime("%a"), "days_left": (loc.date() - now.astimezone(dst).date()).days,
                     "past": loc < now})
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    for r in rows:
        mark = " (past)" if r["past"] else f" · in {r['days_left']} d"
        print(f"{r['given']} {a.src} → {r['weekday']} {r['local_date']} {r['local_time']} local{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
