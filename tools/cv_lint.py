#!/usr/bin/env python3
"""CV content check and comparison against a vacancy.

    python3 tools/cv_lint.py prep/cv/cv.en.yaml
    python3 tools/cv_lint.py prep/cv/cv.en.yaml --vacancy prep/companies/acme/vacancy.md
    python3 tools/cv_lint.py prep/cv/cv.en.yaml --json      # for the skill's `resume` module

Rules (the same for any CV, hence a script rather than eyeballing):
  errors
    • schema schemas/cv.schema.json
    • dates: start ≤ end, experience from newest to oldest
    • no email
  warnings
    • summary not 25–90 words
    • a role has fewer than 2 bullets; the last two roles have numbers in fewer than half their bullets
    • bullet longer than 35 words
    • bullet starts with a weak opener (Responsible for, Worked on, Helped, and Russian equivalents; see WEAK)
    • first person (I, my, we, and Russian equivalents) in bullets
    • role older than 12 years with more than 3 bullets: shorten
    • more than ~900 words (≈ two pages)
    • with --vacancy: vacancy terms missing from the CV (what to add, if it is true)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
    import yaml
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency: {e.name}. pip install -r tools/requirements.txt")

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "schemas" / "cv.schema.json"

WEAK = {
    "en": ["responsible for", "worked on", "helped", "participated in", "involved in", "assisted", "was part of", "tasks included", "duties"],
    "ru": ["отвечал за", "участвовал", "занимался", "помогал", "принимал участие", "в обязанности", "работал над"],
}
FIRST_PERSON = {"en": r"\b(i|me|my|we|our)\b", "ru": r"\b(я|мой|моя|мои|мы|наш|наша|наши)\b"}
NUMBER = re.compile(r"\d|%|×|\bx\d|\bk\b|\bm\b", re.I)
# Vacancy terms: words with a capital/digit/dot/plus (Kafka, PostgreSQL, K8s, C#, .NET) and known lowercase ones
TECH = re.compile(r"(?<![\w.])(?:[A-Z][A-Za-z0-9+#.]*[A-Za-z0-9+#]|[a-z]+[A-Z][A-Za-z0-9]*|[A-Za-z]+\d+[A-Za-z]*|\.[A-Z]+)(?![\w])")
STOP = {"The", "We", "You", "Our", "Your", "This", "What", "Who", "About", "Requirements", "Responsibilities", "Nice",
        "Benefits", "Job", "Role", "Team", "Company", "Experience", "Strong", "Senior", "Middle", "Junior", "Lead",
        "Engineer", "Developer", "Backend", "Remote", "EU", "US", "Must", "Plus", "Bonus", "Knowledge", "Understanding",
        "Ability", "Good", "Excellent", "English", "Great", "Work", "Working", "Years", "Year", "Hands", "At", "In",
        "Is", "Are", "And", "Or", "For", "With", "If", "As", "On", "To", "Of", "A", "An", "It", "Be", "Will"}


def words(s: str) -> int:
    return len(re.findall(r"\w+", s))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--vacancy")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    errors, warnings = [], []
    cv = yaml.safe_load(Path(args.source).read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for e in jsonschema.Draft202012Validator(schema).iter_errors(json.loads(json.dumps(cv, default=str))):
        errors.append(f"schema, {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}")
    if errors:
        return emit(errors, warnings, {}, args.json)

    lang = cv["lang"]
    today = dt.date.today().strftime("%Y-%m")
    sw = words(cv["summary"])
    if not 25 <= sw <= 90:
        warnings.append(f"summary: {sw} words, 25–90 is better")

    prev_start = None
    total = sw + sum(len(s["items"]) for s in cv["skills"])
    for i, j in enumerate(cv["experience"]):
        where = f"{j['role']} · {j['company']}"
        end = j.get("end", "present")
        end_v = today if end == "present" else end
        if j["start"] > end_v:
            errors.append(f"{where}: start {j['start']} is after end {end}")
        if prev_start and j["start"] > prev_start:
            errors.append(f"{where}: experience must go from newest to oldest")
        prev_start = j["start"]
        ach = j["achievements"]
        if len(ach) < 2:
            warnings.append(f"{where}: {len(ach)} bullet(s), need at least 2")
        with_num = sum(1 for a in ach if NUMBER.search(a["text"]))
        if i < 2 and ach and with_num / len(ach) < 0.5:
            warnings.append(f"{where}: numbers in only {with_num} of {len(ach)} bullets — ask about scale and outcome")
        years_ago = int(today[:4]) - int(end_v[:4])
        if years_ago > 12 and len(ach) > 3:
            warnings.append(f"{where}: role {years_ago} years ago, {len(ach)} bullets — shorten to 1–3")
        for a in ach:
            t = a["text"]
            total += words(t)
            if words(t) > 35:
                warnings.append(f"{where}: long bullet ({words(t)} words): «{t[:50]}…»")
            low = t.lower()
            for w in WEAK[lang]:
                if low.startswith(w):
                    warnings.append(f"{where}: bullet starts with «{w}» — start with the action and the result")
            if re.search(FIRST_PERSON[lang], low):
                warnings.append(f"{where}: first person in bullet «{t[:50]}…»")
    if total > 900:
        warnings.append(f"≈{total} words — more than two pages, shorten older roles")
    if not cv["basics"].get("email"):
        errors.append("no email")

    gap = {}
    if args.vacancy:
        vac = Path(args.vacancy).read_text(encoding="utf-8")
        vac = "\n".join(l for l in vac.splitlines() if not l.lstrip().startswith("#"))  # headings are the company name
        try:
            from wordfreq import zipf_frequency
        except ImportError:
            zipf_frequency = None
        text_cv = json.dumps(cv, ensure_ascii=False).lower()
        terms = {}
        for m in TECH.finditer(vac):
            t = m.group(0).strip(".")
            if t in STOP or len(t) < 2:
                continue
            terms[t] = terms.get(t, 0) + 1
        def common_word(t):  # capitalized word at sentence start (Payments, Build) is not a term
            return bool(zipf_frequency) and t[1:].islower() and not any(c.isdigit() for c in t) \
                and zipf_frequency(t.lower(), "en") > 3.2
        missing = sorted((t for t in terms if t.lower() not in text_cv and not common_word(t)), key=lambda t: -terms[t])
        present = sorted(t for t in terms if t.lower() in text_cv)
        gap = {"present": present, "missing": missing}
    return emit(errors, warnings, gap, args.json)


def emit(errors, warnings, gap, as_json) -> int:
    if as_json:
        print(json.dumps({"errors": errors, "warnings": warnings, "vacancy": gap}, ensure_ascii=False, indent=2))
    else:
        for e in errors:
            print(f"✗ {e}")
        for w in warnings:
            print(f"! {w}")
        if gap:
            print(f"\nFrom the vacancy, present in the CV: {', '.join(gap['present']) or '—'}")
            print(f"Missing from the CV: {', '.join(gap['missing']) or '—'}")
            print("  → add only what is actually true; the rest goes into the prep plan as a gap")
        print(f"\nerrors: {len(errors)}, warnings: {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
