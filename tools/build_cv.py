#!/usr/bin/env python3
"""Build a CV from YAML using the templates/cv/cv.html template.

    python3 tools/build_cv.py prep/cv/cv.en.yaml --out dist/cv.en.html
    python3 tools/build_cv.py prep/cv/cv.en.yaml --out dist/cv.en.html --pdf --md

Source format: schemas/cv.schema.json. The schema is checked before building;
content checks live in tools/cv_lint.py.

--pdf  prints A4 via Chromium (playwright) if it is installed;
       otherwise open the HTML in a browser and use "Print → Save as PDF".
--md   also writes a Markdown version next to it (for pasting into application forms).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jinja2
    import jsonschema
    import yaml
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency: {e.name}. pip install -r tools/requirements.txt")

REPO = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO / "templates" / "cv"
SCHEMA = REPO / "schemas" / "cv.schema.json"

LABELS = {
    "en": {"summary": "Summary", "skills": "Skills", "experience": "Experience", "projects": "Projects",
           "education": "Education", "certifications": "Certifications", "languages": "Languages", "stack": "Stack",
           "present": "Present"},
    "ru": {"summary": "О себе", "skills": "Навыки", "experience": "Опыт работы", "projects": "Проекты",
           "education": "Образование", "certifications": "Сертификаты", "languages": "Языки", "stack": "Стек",
           "present": "н. в."},
}
MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "ru": ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
}


def month(value: str, lang: str) -> str:
    if value == "present":
        return LABELS[lang]["present"]
    y, m = value.split("-")
    return f"{MONTHS[lang][int(m) - 1]} {y}"


def load(path: Path) -> dict:
    cv = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(json.loads(json.dumps(cv, default=str))),
                  key=lambda e: list(e.absolute_path))
    if errs:
        for e in errs:
            print(f"✗ {path.name}: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}", file=sys.stderr)
        sys.exit(1)
    return cv


def to_md(cv: dict) -> str:
    t, lang = LABELS[cv["lang"]], cv["lang"]
    b = cv["basics"]
    out = [f"# {b['name']}", f"**{b['title']}**", ""]
    contact = [x for x in (b.get("location"), b.get("work"), b["email"], b.get("phone")) if x]
    contact += [f"[{l['label']}]({l['url']})" for l in b.get("links", [])]
    out += [" · ".join(contact), "", f"## {t['summary']}", cv["summary"], "", f"## {t['skills']}"]
    out += [f"- **{s['group']}:** {', '.join(s['items'])}" for s in cv["skills"]]
    out += ["", f"## {t['experience']}"]
    for j in cv["experience"]:
        dates = f"{month(j['start'], lang)} – {month(j.get('end', 'present'), lang)}"
        out += ["", f"### {j['role']} · {j['company']}", f"*{dates}{' · ' + j['location'] if j.get('location') else ''}*"]
        if j.get("product"):
            out.append(f"_{j['product']}_")
        out += [f"- {a['text']}" for a in j["achievements"]]
        if j.get("stack"):
            out.append(f"{t['stack']}: {', '.join(j['stack'])}")
    for key in ("projects",):
        if cv.get(key):
            out += ["", f"## {t[key]}"] + [f"- **{p['name']}** — {p['text']}" for p in cv[key]]
    if cv.get("education"):
        out += ["", f"## {t['education']}"] + [f"- {e['school']}{' — ' + e['degree'] if e.get('degree') else ''}" for e in cv["education"]]
    if cv.get("languages"):
        out += ["", f"## {t['languages']}", " · ".join(f"{l['name']} — {l['level']}" for l in cv["languages"])]
    return "\n".join(out) + "\n"


def render_html(cv: dict) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    env.filters["month"] = month
    return env.get_template("cv.html").render(cv=cv, t=LABELS[cv["lang"]])


def print_pdf(html_path: Path, pdf_path: Path) -> bool:
    """HTML → A4 PDF via Chromium (playwright). False if playwright is not installed."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri())
        page.pdf(path=str(pdf_path), format="A4", prefer_css_page_size=True, print_background=True)
        browser.close()
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--md", action="store_true")
    args = ap.parse_args()

    cv = load(Path(args.source))
    html = render_html(cv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"HTML: {out}")

    if args.md:
        md = out.with_suffix(".md")
        md.write_text(to_md(cv), encoding="utf-8")
        print(f"Markdown: {md}")

    if args.pdf:
        pdf = out.with_suffix(".pdf")
        if print_pdf(out, pdf):
            print(f"PDF: {pdf}")
        else:
            print("! playwright is not installed: run --setup-pdf, or open the HTML and save it as PDF via Print", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
