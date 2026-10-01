# CV format

A CV is always built the same way: YAML source → check → template. Do not write HTML by hand and do not edit the template for one person.

```
prep/cv/cv.en.yaml                    source (schemas/cv.schema.json)
prep/cv/cv.ru.yaml                    Russian version, if needed
prep/companies/<id>/cv.en.yaml        vacancy-tailored version — a copy of the source with edits
        │
        ├─ run cv_lint.py <yaml> [--vacancy prep/companies/<id>/vacancy.md]
        └─ run build_cv.py <yaml> --out dist/cv.en.html --pdf --md
                  └─ templates/cv/cv.html
```

## Structure (section order is fixed)

| Section | Field | Rule |
|---|---|---|
| Header | `basics` | name, role as in the vacancy, city, work format, email, phone, 1–3 links |
| Summary | `summary` | 3–4 sentences, 25–90 words: who, how many years, strengths, what they're looking for |
| Skills | `skills[]` | 3–5 groups (Languages, Frameworks, Data, Infrastructure, Practices), only what they have worked with |
| Experience | `experience[]` | newest to oldest |
| Projects | `projects[]` | optional: open source, pet projects with a link |
| Education | `education[]` | brief |
| Certifications | `certifications[]` | optional |
| Languages | `languages[]` | honest level |

### Role

```yaml
- company: Chainly
  about: Crypto portfolio tracker                 # what the company does, if it isn't well known
  role: Senior Backend Engineer / Tech Lead
  start: 2019-06
  end: present
  product: "History indexer and token database behind a wallet app with <N> monthly users"
  achievements:
    - text: "Cut p95 latency of the token API from <X> ms to <Y> ms by moving hot reads to Redis"
      story: stories.indexer                # where this is told in detail in the plan
  stack: [TypeScript, PostgreSQL, Kafka]
```

- **A bullet** = action verb + what was done + the result, ideally in numbers. Not "Responsible for…", "Worked on…".
- Last two roles: 3–5 bullets, half of them with numbers. Roles older than 12 years: 1–3 bullets.
- No first person (I, we, «я», «мы»).
- `story` links a bullet to a story in the plan: everything written will be asked about in the experience interview, and the person must be ready for it.
- Length — up to two pages (~900 words).

## Look

One column, no tables, icons, photos or background graphics — that is how ATS systems read CVs. A4, 16 mm margins, sans-serif font 10.5 pt, accent color only on section headings. PDF — via `--pdf` (Chromium) or printing the HTML from the browser.

## Tailoring to a vacancy

1. `cv_lint.py --vacancy` shows vacancy terms that are missing from the CV.
2. For each: was it in their experience? → add it to a bullet or skills (with the person's confirmation). It wasn't → **do not add it**; pass it to the prep plan as a gap.
3. Order of bullets and skills: whatever matches the vacancy goes higher.
4. Save as `prep/companies/<id>/cv.en.yaml`; do not touch the source.

## `cv_lint.py` checks

Errors: schema, dates (start ≤ end, newest to oldest), missing email.
Warnings: summary length, too few bullets, too few numbers, long bullets, weak openings, first person, old roles with many bullets, length over two pages.
