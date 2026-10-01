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

## Accuracy — every lesson is fact-checked

A lesson is not done when it is written; it is done when its facts were compared with primary sources. People learn from these pages for an interview: a confident wrong default or limit is worse than no lesson. Do not skip the check to save tokens — save tokens by checking well (batched, one fetch per doc section), not by not checking.

1. **While writing.** Start from the profile's source registry (`sources` in `profiles/<profile>.yaml`: official docs, RFCs, books) and the versions from the stack (`answers.yaml`). Write only what you can back up. Numbers, defaults, limits, config keys, API names, complexity, consistency guarantees and version-specific behaviour are the claims that must be checked.
2. **Fact-check pass** (`mode: verify` below, or right after writing a batch). Prefer a separate agent that did not write the text. Claim by claim, against the primary source; fix what is wrong.
3. **Sources section** in every lesson and system design case: 1–5 bullets, each a link to the exact documentation section (the docs of the person's version when the docs are versioned) or "Author, *Book*, ch. N". Not "Spring docs" but the page you actually checked.
4. **What could not be confirmed** stays only as a clearly marked claim: `[verify]` right after it plus a short reason ("changed in 3.x, docs unclear"). The page shows it as ⚠, the person sees exactly what to double-check. Never leave an unconfirmed claim unmarked.
5. **Record the check**: `run content.py verify <topic id> --source <url> [--source …] [--by subagent]`. It stores the date, the sources, the number of `[verify]` marks and a hash of the text; editing the block later makes the record stale, so a changed lesson needs a new check.
6. **No web access in this session** (no WebFetch / WebSearch): say so in one line, write from knowledge with sources as book chapters, and do not record a check. The lesson stays "not fact-checked" on the page and in the menu until a session with web access checks it.

The person's own stories, answers and questions to ask are not fact-checked: they are their material.

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
run content.py --dir . unverified           # lessons without a current fact-check — check them before publishing
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

## Check the facts (`mode: verify`)

The hub passes `args.topics` — lessons without a current fact-check (`run content.py unverified --priority 1` for the full list; key ones first).

1. Take the topics in batches of 3–5. For each batch start a fact-checking subagent (Agent tool) that did not write the lessons, with: the block texts, the person's versions (`answers.yaml`), the profile's source registry, and the task "list every checkable claim (versions, defaults, limits, config keys, API names, complexity, guarantees, numbers, attributions to books); check each against the primary source with WebFetch/WebSearch; answer per claim: correct / wrong → correct statement / unconfirmed, with the URL of the section you checked". No subagents in this session — do the same pass yourself.
2. Fix the wrong claims in the block. Rewrite unconfirmed ones as version-dependent or mark them `[verify]` with the reason.
3. Fill `### Sources` with the sections actually checked (links) and book chapters.
4. `run content.py verify <id> --source <url> … --by subagent` for each block.
5. After every batch: `run validate_content.py --dir <folder>` and `run build_page.py --dir <folder>` — the lessons on the page get the "fact-checked" badge.
6. One-line summary: how many lessons checked, how many claims fixed, how many still marked ⚠.
