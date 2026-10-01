#!/usr/bin/env python3
"""What to offer the person next. The prep hub calls this after every action.

    python3 tools/next_steps.py --dir .            # menu as text
    python3 tools/next_steps.py --dir . --json     # for the hub: state + options by weight

Looks only at files — so suggestions are the same in any session:
    prep/wizard.yaml, prep/answers.yaml, prep/outline.yaml, content/*.md,
    prep/words.yaml, prep/cv/*.yaml, prep/companies/*/company.yaml,
    prep/session.yaml       page address, when it was built
    prep/page-state.json    marks from the page (the hub exports them from db before the call)
    prep/inbox.json         "Interviews" form entries (the hub exports them from db)

Each option: id, label (for a button, ≤ 5 words), description (one line),
module (which module to run), weight (0–100), args.
Menu: top 3 by weight + "More options" — so everything fits into one 4-button choice.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pyyaml is missing: pip install -r tools/requirements.txt")


def ld(p: Path, default=None):
    if not p.exists():
        return default
    try:
        if p.suffix == ".json":
            return json.loads(p.read_text(encoding="utf-8"))
        return yaml.safe_load(p.read_text(encoding="utf-8")) or default
    except Exception:
        return default


def walk(nodes):
    for n in nodes or []:
        yield n
        yield from walk(n.get("children"))


def plural_days(n: int) -> str:
    if n == 0:
        return "today"
    if n == 1:
        return "tomorrow"
    return f"in {n} days"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", help="YYYY-MM-DD, for testing")
    args = ap.parse_args()
    root = Path(args.dir)
    prep = root / "prep"
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    wizard = ld(prep / "wizard.yaml", {})
    answers = (ld(prep / "answers.yaml", {}) or {}).get("answers", {})
    outline = ld(prep / "outline.yaml", {})
    session = ld(prep / "session.yaml", {})
    page_state = ld(prep / "page-state.json", {}) or {}
    inbox = ld(prep / "inbox.json", []) or []
    words = ld(prep / "words.yaml", None)
    companies = [ld(p, {}) | {"_dir": p.parent} for p in sorted((prep / "companies").glob("*/company.yaml"))]
    cvs = sorted((prep / "cv").glob("cv.*.yaml"))

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import langs as lg
    P = lg.primary(root)
    content_ru, content_en = set(), set()   # content_ru — the primary language (explain-language), named so for historical reasons
    newest_content = 0.0
    for f in (root / "content").glob("*.md") if (root / "content").exists() else []:
        newest_content = max(newest_content, f.stat().st_mtime)
        ids = set(re.findall(r"^@@\s+(\S+)", f.read_text(encoding="utf-8"), re.M))
        if f.name.endswith(f".{P}.md"):
            content_ru.update(ids)
        if f.name.endswith(".en.md"):
            content_en.update(ids)

    done = set((outline.get("state") or {}).get("done", [])) | set((page_state.get("done") or {}).keys())
    skip = set((outline.get("state") or {}).get("skip", [])) | set((page_state.get("skip") or {}).keys())
    leaves = [n for n in walk(outline.get("nodes")) if not n.get("children") and n.get("kind", "topic") == "topic"]
    active = [n for n in leaves if n["id"] not in skip]
    left = [n for n in active if n["id"] not in done]

    titles = {}
    prof = outline.get("profile") or next((c.get("profile") for c in companies if c.get("profile")), None)
    if prof:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            import validate_profiles as vp
            rep = vp.Report()
            res = vp.resolve(prof, vp.load_raw(rep), rep)
            titles = {s_["id"]: s_.get(f"title_{P}") or s_.get("title", s_["id"]) for s_ in (res or {}).get("stages", [])}
        except Exception:
            titles = {}

    A = []

    def add(id_, label, description, module, weight, **a):
        A.append({"id": id_, "label": label, "description": description, "module": module, "weight": weight, "args": a})

    # ---- plugin upgrade: first item until upgraded
    try:
        import migrate as mg
        plugin_v = json.loads((Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json").read_text())["version"]
        have_v = session.get("plugin_version")
        has_data = prep.exists() and (wizard or answers or outline)
        if has_data and (mg.ver_tuple(have_v) < mg.ver_tuple(plugin_v)
                         or int(session.get("data_version") or mg.guess_data_version(root)) < mg.DATA_VERSION):
            add("upgrade", f"Upgrade to {plugin_v}", "What's new, data backup, migration without losing progress", "upgrade", 99,
                to=plugin_v, was=have_v)
    except Exception:
        pass

    # ---- start and wizard
    if not prep.exists() or (not wizard and not answers and not outline):
        add("start", "Start preparing", "Step-by-step wizard: goal, resume, job posting, plan — then I'll build the page", "wizard", 100)
    elif wizard and not wizard.get("finished"):
        add("wizard-continue", f"Continue wizard", f"Stopped at step {wizard.get('step', '?')}", "wizard", 96)

    # ---- interviews: most urgent
    for c in companies:
        for st in c.get("stages", []):
            d = st.get("date")
            if not d:
                continue
            d = dt.date.fromisoformat(str(d))
            name = c.get("name", c["_dir"].name)
            stage = st.get("title") or titles.get(st.get("stage"), st.get("stage"))
            if st.get("status") == "scheduled" and d < today:
                add(f"debrief:{c.get('id')}:{st['id']}", f"Debrief stage at {name}"[:40],
                    f"«{stage}» was on {d:%d.%m} — what was asked, what to prioritize in the plan", "track", 98,
                    company=c.get("id"), stage=st["id"], mode="debrief")
            elif st.get("status") == "scheduled" and 0 <= (d - today).days <= 7:
                days = (d - today).days
                add(f"prepare:{c.get('id')}:{st['id']}", f"Prepare for {name}"[:40],
                    f"«{stage}» {plural_days(days)}{' at ' + st['time'] if st.get('time') else ''}: weak topics, past questions, questions for them",
                    "track", 94 - days * 2, company=c.get("id"), stage=st["id"], mode="prepare")
    if inbox:
        add("inbox", f"Import entries from the page", f"{len(inbox)} entries from the «Interviews» form waiting to be moved into cards", "track", 97, mode="sync")

    # ---- plan and materials
    if answers and not outline:
        add("outline", "Build the plan", "Topic tree from the questionnaire — you cross out extras and mark what you know", "outline", 90)
    no_material = [n for n in active if n["id"] not in content_ru]
    if outline and no_material:
        add("materials", "Write materials", f"{len(no_material)} topics without material, I'll start with the key ones", "build", 82, count=len(no_material))
    try:
        import depth as dp
        shallow = [r for r in dp.analyze(root) if not r["ok"]]
    except Exception:
        shallow = []
    if shallow:
        ids = sorted({r["id"] for r in shallow})
        add("deepen", "Deepen materials", f"Short topics: {len(ids)} — I'll expand them to full lessons, key ones first", "build", 81,
            topics=ids[:10], mode="deepen")
    built = session.get("built_at", 0) or 0
    if outline and (not session.get("page_url") or newest_content > built):
        add("page", "Build the page" if not session.get("page_url") else "Update the page",
            "I'll publish the plan with materials, vocabulary and interviews" if not session.get("page_url") else "Materials changed since the last build",
            "build", 78 if not session.get("page_url") else 72)

    # ---- English
    train = answers.get("english-train")
    if train is None and outline:
        # the wizard always asks; for old preparations — ask the question from the menu
        add("english-ask", "English for interviews?", "Decide whether to practice: vocabulary from your stories and a trainer", "wizard", 70,
            mode="edit", question="english-train")
    foreign = train in ("full", "texts") or (train is None and answers.get("interview-language") in ("english", "other"))
    if train == "full" and outline and not words:
        add("english", "Build vocabulary", "Words from your stories, topics and job posting — minus the ones you know", "english", 74)
    no_en = [i for i in content_ru if i not in content_en]
    if foreign and P != "en" and content_ru and no_en:
        add("english-text", "Translate to English", f"{len(no_en)} blocks have no English version yet", "english", 68, count=len(no_en))

    # ---- resume
    if not cvs:
        add("cv", "Resume", "Review yours or build one from scratch via questions", "resume", 55)
    for c in companies:
        vac = c["_dir"] / "vacancy.md"
        if vac.exists() and not list(c["_dir"].glob("cv.*.yaml")) and cvs and c.get("status") in ("lead", "applied", "active"):
            add(f"tailor:{c.get('id')}", f"Resume for {c.get('name')}"[:40], "I'll match it to the posting: what to highlight, what's missing", "resume", 60,
                company=c.get("id"), mode="tailor")
        if vac.exists() and not list(c["_dir"].glob("cover.*.md")) and c.get("status") in ("lead", "applied"):
            add(f"cover:{c.get('id')}", f"Cover letter for {c.get('name')}"[:40], "A cover letter for this posting — from your experience, nothing made up", "resume", 58,
                company=c.get("id"), mode="cover")

    # ---- study
    if left:
        p1 = [n for n in left if n.get("priority") == 1]
        pick = (p1 or left)[:3]
        add("study", "Continue the plan", "Next: " + ", ".join(n["title"] for n in pick), "build", 50,
            topics=[n["id"] for n in pick], mode="study")
    if words:
        add("trainer", "Review words", "«Learn by importance»: reviews first, then new words from the top of the list", "english", 45, mode="trainer")

    # ---- always available
    add("company", "Log an interview", "New company, HR call, scheduled stage, offer", "track", 30, mode="add")
    if outline:
        add("update", "Change the plan", "Add or remove topics, new job posting — without losing marks", "outline", 20, mode="update")
    if wizard or answers:
        add("answers", "Change answers", "Change one wizard answer: level, timeline, stack, language", "wizard", 15, mode="edit")

    A.sort(key=lambda a: -a["weight"])
    progress = {"done": len([n for n in active if n["id"] in done]), "total": len(active)}
    state = {"today": today.isoformat(), "page_url": session.get("page_url"), "progress": progress,
             "companies": [{"id": c.get("id"), "name": c.get("name"), "status": c.get("status")} for c in companies],
             "language": answers.get("interview-language"), "english_train": answers.get("english-train"), "explain_language": P, "labels_lang": "en", "words": bool(words), "cv": [p.name for p in cvs]}
    menu = A[:3] + ([{"id": "more", "label": "More options", "description": ", ".join(a["label"] for a in A[3:7]),
                      "module": None, "weight": 0, "args": {}}] if len(A) > 3 else [])

    if args.json:
        print(json.dumps({"state": state, "menu": menu, "all": A}, ensure_ascii=False, indent=2))
    else:
        pr = f"{progress['done']}/{progress['total']}" if progress["total"] else "no plan"
        print(f"Progress: {pr}; companies: {len(companies)}; page: {session.get('page_url') or 'none'}\n")
        for i, a in enumerate(menu, 1):
            print(f"{i}. {a['label']}{' (recommended)' if i == 1 else ''} — {a['description']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
