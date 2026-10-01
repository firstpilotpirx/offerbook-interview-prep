#!/usr/bin/env python3
"""Build the preparation page from files using the templates/portal/template.html template.

    python3 tools/build_page.py --dir .          # → <dir>/dist/index.html + version.json
    python3 tools/build_page.py --dir examples/sample --out /tmp/prep.html --title "Prep: Acme"

Reads (relative to --dir):
    prep/wizard.yaml                   wizard progress (the page works from minute one — with placeholders)
    prep/outline.yaml                  the tree (if present); the order field is "Preparation order" as a list of lines
    prep/cv/cv.*.yaml, prep/companies/<id>/cv.*.yaml, cover.*.md   documents
    content/<section>.<lang>.md          materials, one file per page language (tools/langs.py)
    prep/i18n.<lang>.json              page UI translation, if the language is neither ru nor en
    prep/words.yaml                    the deck (if present → Vocabulary and Trainer tabs)
    prep/companies/*/company.yaml      interviews (Interviews tab)

Stage titles come from the profile (profiles/*.yaml, English-first): the page shows
`title_<lang>` when the profile has it (e.g. title_ru), otherwise the English `title`;
`title_en` in the page data is always the English title.

The template is never edited for a particular person: everything personal lives in the data.
The page is published as an artifact with capabilities {"db": {}} — progress
is stored in db (prep/state, trainer/state, vocab, inbox), separately from content,
so a rebuild does not lose checkmarks.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

try:
    import markdown
    import yaml
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency: {e.name}. pip install -r tools/requirements.txt")

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "templates" / "portal" / "template.html"
I18N = REPO / "templates" / "portal" / "i18n.json"   # UI strings ru/en; another language — prep/i18n.<lang>.json
BLOCK = re.compile(r"^@@\s+(\S+)\s*$", re.M)
FRONT = re.compile(r"\A---\n.*?\n---\n", re.S)
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
KEEP = ("id", "kind", "order", "title", "title_en", "summary", "summary_en", "priority", "origin", "track")


QA_HEADS = ("вопросы на интервью", "проверь себя", "interview q&a", "check yourself")
QA_BLOCK = re.compile(r"(<h3>([^<]+)</h3>\s*<ul>)(.*?)(</ul>)", re.S)
QA_ITEM = re.compile(r"<li>\s*(?:<p>)?\s*<strong>(.+?)</strong>\s*(.*?)(?:</p>)?\s*</li>", re.S)


def fold_answers(html_text: str) -> str:
    """In question sections answers are folded: <details><summary>question</summary>answer</details>."""
    def block(m):
        if not m.group(2).strip().lower().startswith(QA_HEADS):
            # another explanation language: fold the list if every item is "**Question?** answer"
            lis = re.findall(r"<li>(.*?)</li>", m.group(3), re.S)
            if not lis or not all(re.match(r"\s*(?:<p>)?\s*<strong>[^<]+\?</strong>", x) for x in lis):
                return m.group(0)
        items = QA_ITEM.sub(lambda i: f'<li class="qa"><details><summary>{i.group(1)}</summary><div>{i.group(2).strip()}</div></details></li>',
                            m.group(3))
        return m.group(1).replace("<ul>", '<ul class="qa-list">') + items + m.group(4)
    return QA_BLOCK.sub(block, html_text)


def verified_map(root: Path) -> dict:
    """Fact-check state per lesson for the page badge (content.py verify / unverified)."""
    try:
        import content as ct
        return {k: {"s": v["state"], "d": v["date"], "n": v["sources"], "o": v["open"]} for k, v in ct.verify_state(root).items()}
    except Exception as e:
        print(f"verified: {e}", file=sys.stderr)
        return {}


def md_to_html(text: str) -> str:
    def term(m):
        t, label = m.group(1).strip(), (m.group(2) or m.group(1)).strip()
        return f'<a class="term" href="#" data-term="{html.escape(t, quote=True)}">{html.escape(label)}</a>'
    text = LINK.sub(term, text)
    html_ = fold_answers(markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists"]))
    # a claim that could not be confirmed during the fact-check: shown as a warning mark on the page
    return re.sub(r"\[verify\]", '<mark class="vfy" data-vfy="1">⚠</mark>', html_, flags=re.I)


def load_content(root: Path, langs: list) -> dict:
    out = {l: {} for l in langs}
    for f in sorted((root / "content").glob("*.md")):
        m = re.match(r".+\.([a-z]{2})\.md$", f.name)
        if not m or m.group(1) not in out:
            continue
        text = FRONT.sub("", f.read_text(encoding="utf-8"))
        parts = BLOCK.split(text)
        for i in range(1, len(parts), 2):
            out[m.group(1)][parts[i]] = md_to_html(parts[i + 1].strip())
    return out


def slim(nodes):
    res = []
    for n in nodes or []:
        x = {k: n[k] for k in n if k in KEEP or re.fullmatch(r"(title|summary)_[a-z]{2}", k)}
        if n.get("children"):
            x["children"] = slim(n["children"])
        res.append(x)
    return res


def report(companies: list) -> dict:
    today = dt.date.today()
    upcoming, weak = [], {}
    for c in companies:
        for st in c.get("stages", []):
            d = st.get("date")
            if st.get("status") == "scheduled" and d and dt.date.fromisoformat(str(d)) >= today:
                upcoming.append({"date": str(d), "time": st.get("time", ""), "company": c.get("name"),
                                 "stage": st.get("stage"), "title": st.get("title", "")})
            for q in st.get("questions", []):
                w = {"bad": 2, "ok": 1}.get(q.get("went"), 0)
                if w and q.get("topic"):
                    e = weak.setdefault(q["topic"], {"topic": q["topic"], "score": 0, "companies": set()})
                    e["score"] += w
                    e["companies"].add(c.get("name"))
    upcoming.sort(key=lambda x: (x["date"], x["time"]))
    wl = sorted(weak.values(), key=lambda e: -e["score"])
    for e in wl:
        e["companies"] = sorted(e["companies"])
    return {"upcoming": upcoming, "weak_list": wl, "weak": {e["topic"]: e["score"] for e in wl}}


WIZARD_STEPS = [
    ("explain", "Язык объяснений", "Explanation language"),
    ("goal", "Цель", "Goal"), ("profile", "Специальность", "Role"), ("resume", "Резюме", "Resume"),
    ("vacancy", "Вакансия", "Vacancy"), ("company", "Компания", "Company"), ("basis", "Основа плана", "Plan basis"),
    ("level", "Уровень и срок", "Level and timing"), ("stack", "Стек", "Stack"), ("language", "Английский", "English"),
    ("weak", "Слабые места", "Weak spots"), ("generate", "Что собрать", "What to build"),
]


def ld(p: Path, default=None):
    if not p.exists():
        return default
    return json.loads(json.dumps(yaml.safe_load(p.read_text(encoding="utf-8")), default=str)) or default


def documents(root: Path, companies: list, pdf: bool = False) -> list:
    """Resumes and cover letters: embedded in the page and written as files to dist/docs/."""
    sys.path.insert(0, str(REPO / "tools"))
    import build_cv as bc
    groups = []
    want_pdf = {"on": pdf}

    def one(owner_id, owner_name, folder: Path):
        docs = []
        for cvp in sorted(folder.glob("cv.*.yaml")):
            try:
                cv = bc.load(cvp)
            except SystemExit:
                docs.append({"kind": "cv", "lang": cvp.stem.split(".")[-1], "error": "the resume failed schema validation"})
                continue
            html_text = bc.render_html(cv)
            outdir = root / "dist" / "docs" / owner_id
            outdir.mkdir(parents=True, exist_ok=True)
            hp = outdir / f"cv.{cv['lang']}.html"
            hp.write_text(html_text, encoding="utf-8")
            (outdir / f"cv.{cv['lang']}.md").write_text(bc.to_md(cv), encoding="utf-8")
            pdfp = outdir / f"cv.{cv['lang']}.pdf"
            if want_pdf["on"] and (not pdfp.exists() or pdfp.stat().st_mtime < hp.stat().st_mtime):
                if not bc.print_pdf(hp, pdfp):
                    print("! PDF not printed: playwright is missing (run --setup-pdf)", file=sys.stderr)
                    want_pdf["on"] = False
            docs.append({"kind": "cv", "lang": cv["lang"], "title": cv["basics"].get("title", ""),
                         "html": html_text, "md": bc.to_md(cv),
                         "href": f"docs/{owner_id}/cv.{cv['lang']}.html",
                         "pdf": f"docs/{owner_id}/cv.{cv['lang']}.pdf" if pdfp.exists() else None,
                         "file": f"cv-{owner_id}-{cv['lang']}"})
        for cl in sorted(folder.glob("cover.*.md")):
            text = FRONT.sub("", cl.read_text(encoding="utf-8")).strip()
            lang = cl.stem.split(".")[-1]
            docs.append({"kind": "cover", "lang": lang, "md": text, "html": md_to_html(text),
                         "words": len(re.findall(r"\w+", text)), "file": f"cover-{owner_id}-{lang}"})
        if docs:
            groups.append({"id": owner_id, "name": owner_name, "docs": docs})

    one("general", "Моё резюме", root / "prep" / "cv")
    for c in companies:
        one(c.get("id", "company"), c.get("name", c.get("id", "")), root / "prep" / "companies" / c.get("id", ""))
    return groups


def setup_state(root: Path, outline: dict, companies: list, deck, P: str = "ru") -> dict:
    wizard = ld(root / "prep" / "wizard.yaml", {}) or {}
    answers = (ld(root / "prep" / "answers.yaml", {}) or {}).get("answers", {})
    passed = set(wizard.get("path", []))
    skipped = set(wizard.get("skipped", []))
    steps = []
    for sid, ru, en in WIZARD_STEPS:
        st = "done" if sid in passed else ("skipped" if sid in skipped else "todo")
        steps.append({"id": sid, "title": ru if P == "ru" else en, "title_en": en, "status": st})
    return {
        "finished": bool(wizard.get("finished")) or bool(outline.get("nodes")),
        "current": wizard.get("step"),
        "steps": steps,
        "answers": {k: v for k, v in (wizard.get("answers") or {}).items() if isinstance(v, (str, int, float, list))},
        "profile_answers": answers,
        "has": {"plan": bool(outline.get("nodes")), "deck": bool(deck), "companies": len(companies),
                "cv": bool(list((root / "prep" / "cv").glob("cv.*.yaml")))},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--out", help="default: <dir>/dist/index.html")
    ap.add_argument("--title", default="Подготовка к интервью")
    ap.add_argument("--title-en", default="Interview preparation")
    ap.add_argument("--pdf", action="store_true", help="print the resume PDF (needs playwright: run --setup-pdf)")
    ap.add_argument("--eyebrow", help="eyebrow line: \"SENIOR BACKEND · JAVA + WEB3\" (default: from the survey answers)")
    ap.add_argument("--heading", help="large header heading (default: --title)")
    ap.add_argument("--intro", help="intro paragraph under the heading")
    args = ap.parse_args()
    root = Path(args.dir).expanduser()
    out = Path(args.out) if args.out else root / "dist" / "index.html"
    # the header is remembered in prep/page.yaml: given values are saved, missing ones are taken from there
    meta_p = root / "prep" / "page.yaml"
    meta = ld(meta_p, {}) or {}
    given = {k: getattr(args, k) for k in ("title", "title_en", "heading", "eyebrow", "intro")
             if getattr(args, k) is not None and getattr(args, k) != ap.get_default(k)}
    if given:
        meta.update(given)
        meta_p.parent.mkdir(parents=True, exist_ok=True)
        meta_p.write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
    for k, v in meta.items():
        if k in ("title", "title_en", "heading", "eyebrow", "intro") and k not in given:
            setattr(args, k, v)
    sys.path.insert(0, str(REPO / "tools"))
    import langs as lg
    P, LANGS = lg.primary(root), lg.languages(root)
    i18n = ld(root / "prep" / f"i18n.{P}.json", None) if P not in ("ru", "en") else None   # UI translation

    # everything is optional: the page builds from minute one and fills in as you go
    outline = ld(root / "prep" / "outline.yaml", {}) or {}
    deck = ld(root / "prep" / "words.yaml", None)
    companies = [ld(cp, {}) for cp in sorted((root / "prep" / "companies").glob("*/company.yaml"))]

    stages = {}
    prof = outline.get("profile") or next((c.get("profile") for c in companies if c.get("profile")), None)
    if prof:
        sys.path.insert(0, str(REPO / "tools"))
        import validate_profiles as vp
        rep = vp.Report()
        resolved = vp.resolve(prof, vp.load_raw(rep), rep) if (vp.PROFILES / f"{prof}.yaml").exists() else None
        if resolved:
            for s_ in resolved["stages"] + resolved["cross"]:
                # profiles are English-first: show title_<P> (e.g. title_ru) if present, else English
                st_ = {}
                if s_.get("title"):
                    st_["title"] = s_.get(f"title_{P}") or s_["title"]
                    st_["title_en"] = s_["title"]
                if "order" in s_:
                    st_["order"] = s_["order"]
                stages[s_["id"]] = st_

    # study tracks (profiles/base.yaml → tracks): unit, daily goal, which sections belong to each
    tracks = []
    try:
        sys.path.insert(0, str(REPO / "tools"))
        import validate_profiles as vp
        rep_ = vp.Report()
        src = vp.resolve(prof, vp.load_raw(rep_), rep_) if prof and (vp.PROFILES / f"{prof}.yaml").exists() else None
        src = src or vp.resolve("base", vp.load_raw(rep_), rep_)
        for tr in (src or {}).get("tracks", []):
            tracks.append({"id": tr["id"], "title": tr.get(f"title_{P}") or tr.get("title", tr["id"]), "title_en": tr.get("title", tr["id"]),
                           "unit": tr.get(f"unit_{P}") or tr.get("unit", ""), "unit_en": tr.get("unit", ""),
                           "goal": int(tr.get("goal") or 1), "kind": tr.get("kind", "topics"), "sections": tr.get("sections", [])})
    except Exception as e:  # the page still works without tracks
        print(f"tracks: {e}", file=sys.stderr)

    answers = (ld(root / "prep" / "answers.yaml", {}) or {}).get("answers", {})
    eyebrow = args.eyebrow
    if not eyebrow:
        parts = [str(answers.get("level", "")).upper(), (prof or "").upper()]
        lang_ = answers.get("language")
        if lang_:
            parts.append(str(lang_).upper())
        eyebrow = " · ".join(p_ for p_ in parts if p_)
    company = next((c.get("name") for c in companies if c.get("status") in ("active", "applied", "lead")), None)
    intro_ru = ("Темы по вашему резюме" + (f" и вакансии {company}" if company else "") +
                ". Нажмите на раздел, чтобы раскрыть темы, и на тему — чтобы открыть урок. "
                "Отмечайте пройденное — прогресс сохраняется сам.")
    intro_en = ("Topics from your resume" + (f" and the {company} vacancy" if company else "") +
                ". Click a section to open its topics, and a topic to open the lesson. "
                "Tick what you have done — progress saves itself.")
    intro = args.intro or (intro_ru if P == "ru" else intro_en)
    title = args.title if (args.title != ap.get_default("title") or P == "ru") else args.title_en
    data = {
        "ui": json.loads(I18N.read_text(encoding="utf-8")),
        "tracks": tracks, "lang": P, "langs": LANGS, "lang_names": {l: lg.NAMES.get(l, l.upper()) for l in LANGS}, "i18n": i18n,
        "eyebrow": eyebrow, "heading": args.heading or title, "intro": intro, "intro_en": intro_en if P != "en" else None,
        "heading_en": args.title_en if not args.heading else None,
        "order": outline.get("order") or [],
        "stages": stages,
        "title": title, "title_en": args.title_en,
        "build": {"built": dt.datetime.now().isoformat(timespec="seconds"), "profile": prof,
                  "profile_version": outline.get("profile_version")},
        "setup": setup_state(root, outline, companies, deck, P),
        "outline": slim(outline.get("nodes")),
        "content": load_content(root, LANGS),
        "verified": verified_map(root),
        "deck": deck,
        "companies": companies,
        "documents": documents(root, companies, args.pdf),
        "report": report(companies),
    }
    import hashlib
    body = json.dumps({k: v for k, v in data.items() if k != "build"}, ensure_ascii=False, sort_keys=True)
    data["build"]["id"] = hashlib.sha1(body.encode()).hexdigest()[:12]
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8")
    if any(k not in page for k in ("{{DATA}}", "{{TITLE}}", "{{CSS}}", "{{JS}}")):
        sys.exit("The template lacks {{DATA}}, {{TITLE}}, {{CSS}} or {{JS}}")
    # page skeleton — template.html, styles — page.css, code — page.js, strings — i18n.json;
    # assembled into one file: the artifact and file:// work without external resources
    page = page.replace("{{CSS}}", (TEMPLATE.parent / "page.css").read_text(encoding="utf-8"), 1)
    page = page.replace("{{JS}}", (TEMPLATE.parent / "page.js").read_text(encoding="utf-8").replace("</script", "<\\/script"), 1)
    page = page.replace("{{TITLE}}", html.escape(title)).replace("{{DATA}}", payload)

    out.parent.mkdir(parents=True, exist_ok=True)
    # index.html — a full document for local viewing (server, file://, built-in browser);
    # artifact.html — page content only: the Artifact tool adds the document skeleton itself
    out.write_text(f'<!doctype html><html lang="{P}"><head><meta charset="utf-8">'
                   '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>\n'
                   + page + '\n</body></html>\n', encoding="utf-8")
    (out.parent / "artifact.html").write_text(page, encoding="utf-8")
    (out.parent / "version.json").write_text(json.dumps({"id": data["build"]["id"], "built": data["build"]["built"]}),
                                             encoding="utf-8")
    n_nodes = sum(1 for _ in re.finditer(r'"id":', json.dumps(data["outline"])))
    n_docs = sum(len(g["docs"]) for g in data["documents"])
    blocks_ = " / ".join(f"{l.upper()} {len(data['content'][l])}" for l in LANGS)
    print(f"{out}: {len(page) // 1024} KB, build {data['build']['id']}, language {P}, nodes {n_nodes}, blocks {blocks_}, cards "
          f"{len((deck or {}).get('words', []))}, companies {len(companies)}, documents {n_docs}")
    if len(page) > 15 * 1024 * 1024:
        print("! the page is larger than 15 MB — the artifact limit is 16 MB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
