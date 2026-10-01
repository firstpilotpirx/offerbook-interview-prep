#!/usr/bin/env python3
"""Interview summary: what's ahead, where I'm weak, what companies said.

    python3 tools/interviews_report.py --dir .            # markdown to stdout
    python3 tools/interviews_report.py --dir . --json     # for skills

Reads prep/companies/*/company.yaml. Computes:
  • upcoming stages by date;
  • the funnel: how many stages of each kind were passed and failed;
  • weak topics: questions with went: bad / ok, grouped by topic id, with companies —
    the `track` module raises their priority in the plan and clears the "done" mark;
  • facts from conversations (salary ranges, timelines) per company.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pyyaml is missing: pip install -r tools/requirements.txt")

WEIGHT = {"bad": 2, "ok": 1, "good": 0}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    today = dt.date.today()
    upcoming, funnel, facts = [], defaultdict(Counter), {}
    weak: dict[str, dict] = {}
    statuses = Counter()

    for cp in sorted(Path(args.dir, "prep", "companies").glob("*/company.yaml")):
        c = yaml.safe_load(cp.read_text(encoding="utf-8")) or {}
        name = c.get("name", cp.parent.name)
        statuses[c.get("status", "?")] += 1
        for st in c.get("stages", []):
            funnel[st.get("stage", "?")][st.get("status", "?")] += 1
            d = st.get("date")
            if st.get("status") == "scheduled" and d and dt.date.fromisoformat(str(d)) >= today:
                upcoming.append({"date": str(d), "time": st.get("time", ""), "company": name,
                                 "stage": st.get("stage"), "title": st.get("title", "")})
            for q in st.get("questions", []):
                w = WEIGHT.get(q.get("went", ""), 0)
                if not w:
                    continue
                t = q.get("topic") or "(no topic)"
                e = weak.setdefault(t, {"topic": t, "score": 0, "companies": set(), "questions": []})
                e["score"] += w
                e["companies"].add(name)
                e["questions"].append({"q": q["q"], "went": q["went"], "company": name, "note": q.get("note", "")})
        f = {}
        for entry in c.get("log", []):
            f.update(entry.get("facts") or {})
        if f:
            facts[name] = f

    upcoming.sort(key=lambda x: (x["date"], x["time"]))
    weak_list = sorted(weak.values(), key=lambda e: (-e["score"], e["topic"]))
    for e in weak_list:
        e["companies"] = sorted(e["companies"])

    if args.json:
        print(json.dumps({"statuses": statuses, "upcoming": upcoming,
                          "funnel": {k: dict(v) for k, v in funnel.items()},
                          "weak_topics": weak_list, "facts": facts}, ensure_ascii=False, indent=2))
        return 0

    print("# Interview summary\n")
    print("Companies: " + (", ".join(f"{k} — {v}" for k, v in statuses.items()) or "none"))
    print("\n## Upcoming\n")
    for u in upcoming or [{"date": "—", "time": "", "company": "nothing scheduled", "stage": "", "title": ""}]:
        print(f"- {u['date']} {u['time']} · {u['company']} · {u['stage']} {u['title']}".rstrip())
    print("\n## Stages\n")
    for stage, cnt in funnel.items():
        print(f"- {stage}: " + ", ".join(f"{k} {v}" for k, v in cnt.items()))
    print("\n## Weak spots\n")
    if not weak_list:
        print("No debriefs with rated answers yet.")
    for e in weak_list:
        print(f"- **{e['topic']}** — weight {e['score']}, companies: {', '.join(e['companies'])}")
        for q in e["questions"]:
            print(f"  - [{q['went']}] {q['q']} ({q['company']}){' — ' + q['note'] if q['note'] else ''}")
    if facts:
        print("\n## What they said\n")
        for name, f in facts.items():
            print(f"- {name}: " + "; ".join(f"{k}: {v}" for k, v in f.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
