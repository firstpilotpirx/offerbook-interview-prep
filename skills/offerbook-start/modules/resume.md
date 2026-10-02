<!-- A prep hub module. Not a skill: called from skills/offerbook-start/SKILL.md; the person never launches it. -->
<!-- Purpose: Resume for interview preparation — build one from scratch with guiding questions, review an existing one with recommendations, tailor it to a job posting. -->

# module `resume` — resume

Three modes. The result is `prep/cv/cv.<lang>.yaml` (source following `schemas/cv.schema.json`), recommendations and the built files.

**Format, sections, bullet rules and look — in [references/cv-format.md](../references/cv-format.md).** The resume is always built by scripts, the same way for everyone:

```bash
run cv_lint.py prep/cv/cv.en.yaml [--vacancy prep/companies/<id>/vacancy.md]
run build_cv.py prep/cv/cv.en.yaml --out dist/cv.en.html --pdf --md
```

**The main rule: only what the person said.** Do not add technologies, numbers or achievements on your own. Everything in the resume will be asked about in the experience interview — anything invented will fail the stage. If a number is missing — ask, don't fill it in.

All button labels below are examples: say them in the person's explanation language (`explain-language`), translating on the fly.

## review — review an existing one

1. Read the file (PDF, DOCX) or the pasted text. LinkedIn and hh.ru links are closed to the agent — ask for a file instead, as in the wizard, step 3.
2. Transfer it into `prep/cv/cv.<lang>.yaml` following the schema: roles and years, stack, projects, bullets. Show "here's what I understood" — this fills in the wizard's questionnaire.
3. `run cv_lint.py` — mechanical remarks (weak openings, no numbers, length) come from here, not from eyeballing.
4. Recommendations as a list, each with a reason:
   - where personal contribution is missing ("we did" → what you did);
   - where a result in numbers is missing — as a question, not an invention;
   - what is outdated or not relevant to this role;
   - what is missing for the specialty profile.
5. Screen: "Apply all / I'll choose / Not now". After the edits — `cv_lint.py` again, then `build_cv.py`.

## create — build from scratch

A series of wizard steps, one role at a time:

1. Company, position, years.
2. What the product is and its scale (users, load, team).
3. What you were personally responsible for.
4. Two or three results — with numbers, if any.
5. The stack at this job.

Then: education, languages, links. Every step can be skipped. Answers are written straight to `prep/cv/cv.<lang>.yaml`; at the end — `cv_lint.py` and `build_cv.py`.

## tailor — for a job posting

Requires a resume and a job posting. `run cv_lint.py prep/cv/cv.en.yaml --vacancy prep/companies/<id>/vacancy.md` returns posting terms that are not in the resume. For each:

- matches → move it higher, use the posting's wording;
- present in the experience but not written → offer to add it (with the person's confirmation);
- not in the experience → do not add it; pass it to the preparation plan as a gap.

The result is a separate version `prep/companies/<id>/cv.<lang>.yaml`; do not touch the source. Gaps go to `prep/gaps.yaml` for the plan.

Afterwards — `run build_page.py --dir <folder> --pdf`: the resume appears in the page's "Documents" tab and in the company card, with "Open", "PDF", "HTML", "Markdown" buttons. Files are in `dist/docs/<id>/`.

## Language

If the interview is in English — an English version of the resume alongside, in the same voice as the answers in module `english`.

## cover — cover letter (`mode: cover`)

For one job posting: `prep/companies/<id>/cover.<lang>.md`. Requires the posting (`vacancy.md`) and a resume — preferably the version tailored to this company.

Buttons first:
- tone: "Professional (recommended)" / "Warm" / "Short, 3 paragraphs";
- language: the posting's language is preselected;
- "Why you?" — one or two reasons for interest in the company: buttons drawn from what's visible in the posting (product, stack, tasks), plus "My own reason".

Format, 150–300 words:

```markdown
---
company: acme
vacancy: Senior Backend Engineer
lang: en
---
Greeting.

Paragraph 1 — which role, and how your experience relates to their problem (one bridging sentence).
Paragraph 2 — 2–3 matches between the posting's requirements and your experience, with numbers from the resume.
Paragraph 3 — why this company: product, problem, stack — based on facts from the posting.
Closing — readiness to talk. Signature.
```

Rules:
- **Only facts from the resume and the person's answers.** Numbers are the same as in the resume. No fact — ask, or don't write it.
- No placeholders (`[Company]`, `{name}`) — the validator catches them.
- Do not retell the whole resume: the letter answers "why you, and why us".

Check and show:

```bash
run validate_content.py --dir <folder>    # length, placeholders, whether the company is named
run build_page.py --dir <folder>          # letter in the "Documents" tab: "Copy", .txt, .md
```

Show the text in chat with buttons "Keep it (recommended)" / "Shorter" / "Different tone" / "I'll edit it myself".
