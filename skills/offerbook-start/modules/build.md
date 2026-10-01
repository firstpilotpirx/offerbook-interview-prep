<!-- prep hub module. Not a skill: called from skills/offerbook-start/SKILL.md; the person does not run it. -->
<!-- Purpose: Writes materials for the topic tree and builds a live interview-prep page with progress on every node. -->

# module `build` — materials and page

Input: `prep/outline.yaml`, profile, questionnaire. Output: `content/*.<lang>.md` — in the explanation language `explain-language` (+ `*.en.md` via the `english` module) and the artifact page.

The full page format — tabs, RU/EN switch, tree, the "Interviews" section, storage — is in [references/page-format.md](../references/page-format.md). Read it before building.

## Materials

One file per stage or cross-cutting section and **course language** (`languages` in `prep/answers.yaml`; `run state.py --dir . answer get languages`): `content/<stage-id>.<lang>.md`. Only the chosen languages — one language, one file per section; never write a language that was not chosen (it costs tokens and nobody reads it). The first language holds the full lesson; every other chosen language gets the same lesson written in that language, with the same `@@ id`s. The only exception is the short English companion that the `english` module writes for English training. Inside — blocks by id:

```markdown
---
stage: tech
sources: [postgresql-docs, rfc9110]
last_verified: 2026-09-30
---

@@ tech.db.postgresql.indexes
Material in markdown.

@@ tech.db.postgresql.explain
Next material.
```

- **Each block is a lesson per the standard in [../references/material-format.md](../references/material-format.md)**: sections "In short", "How it works", "Interview Q&A", "Check yourself", length by priority. A comma-separated list of terms is a table of contents — not allowed. Read the standard and the example before the first topic.
- Theory from "Foundations" and how a technology works go in different places (the "Theory and technology" table in the standard).
- Write only for topics without `skip`.
- Depth follows `deadline` from the questionnaire: a week → the gist and common questions; a month → with a full walkthrough.
- Examples come from the questionnaire's stack and the CV, not abstract ones.
- The main language is the first course language (`explain-language` = `languages[0]`, English by default). Lesson section headings are in that language too, matching the standard in meaning (In short / How it works / Interview Q&A / Check yourself → «Суть» / «Как устроено» / «Вопросы на интервью» / «Проверь себя» → Kurz gesagt / So funktioniert es…). Questions are always bullets `- **Question?** answer`: that way they collapse on the page in any language.
- If English is being trained, the English companion version is written by the `english` module: not a literal translation, but how it is said in an interview.
- Node names in the other chosen languages — `title_<lang>` in the outline (`title_en`, `title_de`…): from the profile for English, otherwise translate during the build. One language — only `title`.

## Skeleton and order

```bash
run content.py --dir <folder> missing --priority 1              # what to write first
run content.py --dir <folder> scaffold <section> <topic id>     # block skeleton with the standard headings
```

The skeleton is the standard's headings in the explanation language (`templates/lesson/skeletons.yaml`) plus "write" markers. Fill it with text, then `run depth.py --dir <folder>`: until the skeleton is written, the check will not pass it.

## Accuracy

- Facts about versions, APIs, limits, defaults and prices you are not sure of get a "verify before the interview" mark. No need to fetch to verify: that costs tokens.
- Sources in a lesson — one line without links (book, chapter, or documentation section).
- Do not invent: if you do not know for sure — a mark, not a confident statement.

## Page

**The page is not written by hand.** It is built from files using the fixed template `templates/portal/template.html`:

```bash
run build_page.py --dir <folder> [--pdf] --title "Prep: <company>" \
    --heading "Technical interview prep" \
    --eyebrow "SENIOR BACKEND · JAVA + WEB3" \
    --intro "Topics based on your CV and the <company> vacancy: from … to …. Click a section…"
```

The header is remembered: the passed `--title/--heading/--eyebrow/--intro` are saved to `prep/page.yaml`, and later builds (including those from the hub after each step) take them from there — no need to pass them every time. Header: `--title` — in the top bar, `--heading` — the large title, `--eyebrow` — level · profile · stack, `--intro` — 2–3 sentences about this person's plan. Without them they are taken from the questionnaire. "Prep order" («Порядок подготовки») is the `order` field in `prep/outline.yaml` (written by the `outline` module).

Result: `dist/index.html` (for local display), `dist/artifact.html` (for publishing), `dist/version.json` (open pages use it to know it is time to refresh), `dist/docs/…` (CVs as files).

Where to show it is decided by the hub (step 1½): a local server `run serve.py` + the built-in browser, or an artifact with `capabilities: {"db": {}, "downloads": true}`. Here you only build — after each batch of materials, so the person sees the page fill up.

If the template itself needs changing (a new tab, a different look), that is a change for everyone: edit `templates/portal/` (`template.html`, `page.css`, `page.js`, strings — `i18n.json`), test on `examples/sample`, do not make a copy for one person.

## Before publishing

```bash
run validate_profiles.py
run validate_content.py --dir .            # checks every chosen language; --require-en also requires the English companion
run validate_content.py --dir . --update-lock   # after the first successful build
```

Then back up the state, publish, reconcile the marks. If it was edited from another session — read the live version and merge.

## Study session (`mode: study`)

The hub passes `args.topics` — 2–3 topics worth going through now.

1. Buttons: which topic to take (topics from `args.topics`) + "I'll pick on the page".
2. For the chosen topic: briefly, the gist of the material in your own words, then 2–3 self-check questions **as buttons** (answer options, one correct), as in an interview.
3. Wrap-up — buttons: "Mark as done", "More questions", "Come back later".
4. "Mark as done" → write to the page's `prep/state` document (`done.<id>` = time) via ArtifactData and to `prep/outline.yaml` (`state.done`).

## Deepen materials (`mode: deepen`)

The hub passes `args.topics` — topics that failed `run depth.py`. For each, top-priority ones first:

1. Read the current block — it is a draft; do not throw away correct facts or the link to the person's experience.
2. Rewrite it into a lesson per the standard: add missing sections, explanations, questions with answers.
3. After every 3–5 topics — `run depth.py --dir <folder>` and `run build_page.py --dir <folder>`: the person sees the lessons fill up.

Block ids do not change — "done" marks are preserved.
