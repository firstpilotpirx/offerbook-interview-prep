# Prep page format

One artifact page. Taken from a working portal (404 topics, trainer at the top) and extended: arbitrary nesting, two languages, the "Interviews" («Собесы») section.

**Implementation — `templates/portal/`: `template.html` (skeleton), `page.css` (styles), `page.js` (code), `i18n.json` (ru/en strings); built into one file by `tools/build_page.py`.** This document describes what is in the template and why; a page for a given person differs only in data.

## Skeleton (reference — the working portal with 404 topics; implemented in the template)

UI labels below are shown in English; the page ships both ru and en strings (`templates/portal/i18n.json`), Russian equivalents in parentheses where useful.

```
┌ top bar (sticky): Prep: Acme │ Plan Vocabulary Trainer Interviews Documents │ RU|EN ◐ ┐

 SENIOR · BACKEND · JAVA                                ← eyebrow: level · profile · stack (--eyebrow)
 Technical interview prep                              ← large heading (--heading)
 Topics based on your CV and the Acme vacancy…         ← intro paragraph (--intro)
 Materials ready for 400 of 400 topics.  Excluded from the plan: 71 (not counted).

 ┌ Word trainer ──────────────────────────────────── 630 due ┐  ← click opens the "Trainer" tab
 │ ▓▓░░░░░░  ■ learned 0 ■ consolidating 0 ■ learning 30 ■ not started 630 │
 └ Cards total 660 · reviews all time 42 · today 42 ┘

 ┌ 184 / 329  56% ┐ ┌ 125 / 193  65%        ┐ ┌ 6 days    until October 7       ┐
 │ Topics done     │ │ Of them marked "must"  │ │ Forecast at the current pace    │
 └ ▓▓▓▓▓░░░        ┘ └ ▓▓▓▓▓▓░░              ┘ └ Pace 26/day… Must-haves in 3  ┘

 ORDER OF PREPARATION  1 System design and your systems  2 Java, Spring…   ← outline.yaml: order
 TAGS  [must] … [important] … [optional] … [vacancy] … [my experience] …

 [Search…] [All|Not done|Done|Excluded] [Any|Must|Important|Optional] [From vacancy]
                                                                          ● Saved
 ──────────────────────────────────────────────────────────────────────────────────
 CONTENTS (sticky)        │  04 TECHNICAL INTERVIEW                         12 / 48
 TECHNICAL INTERVIEW      │  ┌ Frameworks [must]                     1 / 9  › ┐   ← thick section card
   Frameworks      1/9    │  │ ▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   ← progress strip at the bottom
   Databases       0/12   │  └ (expanded: topics and nested groups)         ┘
 MY SYSTEMS               │  ┌ Databases                            0 / 12 › ┐
```

Russian labels for the same elements: Plan/Vocabulary/Trainer/Interviews/Documents = «План / Словарь / Тренажёр / Собесы / Документы»; "Order of preparation" = «Порядок подготовки»; "Tags" = «Метки»; priority tags must/important/optional = «главное / важно / по желанию»; filters All/Not done/Done/Excluded = «Все / Не пройдено / Пройдено / Исключённые»; Any/Must/Important/Optional = «Любой / Главное / Важно / По желанию»; "From vacancy" = «Из вакансии»; "Saved" = «Сохранено».

Rules:

- **Levels.** The top level of the plan (a stage or a cross-cutting section) is a group caption in caps with the stage number and a counter. Its children are **thick cards** (22px heading, counter, chevron, strip at the bottom). Topics placed directly in a stage — one card with the stage name. Deeper levels — ordinary nested rows and topics.
- **Cards are collapsed by default**, expanded ones are remembered (`state.expanded`). Click anywhere on the card header; a double click fires once. "Expand all / Collapse all" («Развернуть всё / Свернуть всё») — above the tree on the right. Any filter or search expands the cards with matches.
- **Contents** on the left, sticky: group captions and cards with counters, completed ones green; a click expands the card and scrolls to it. Hidden on narrow screens.
- **Width** up to 1320px, lesson text up to ~760px.
- Completed items are green: the card's counter and strip, the contents entry.

- Order: stages by `order`, then cross-cutting sections (◇).
- Any node with children collapses via the arrow or the heading; on first open only the first stage is expanded.
- During search everything expands; matches are searched in headings and materials in both languages.
- A leaf is a topic: "done" checkbox, heading, tags, a "what they'll ask" line, "Material" and "Exclude" («Материал», «Исключить») buttons. On narrow screens the buttons become icons ▤ ⊘. An open lesson has a **Copy** button (top right): the topic title, the "what they'll ask" line and the whole lesson as Markdown-like text (`toText`), for pasting into a new chat; clipboard API first, then a hidden textarea, then a download.

## Tabs

```
[ Plan ]  [ Vocabulary ]  [ Trainer ]  [ Interviews ]  [ Documents ]      RU | EN   ◐
```

The page exists **from the first minute**: while the wizard is not finished, "Plan" shows a "Setting up" («Настройка подготовки») card with the wizard steps (✓ done, ● current, ○ ahead, – skipped) and the answers, and below it a placeholder "The plan appears after…". Empty tabs show a placeholder saying when they will be filled. "Vocabulary" and "Trainer" are hidden only if the interview is in the person's native language.

**Documents** — in groups: "My resume" («Моё резюме»), then each company. CV: "Open", "PDF" (if printed) or "Print → PDF", "HTML", "Markdown". Cover letter: text, word count, "Copy", `.txt`, `.md`. A company's card on "Interviews" links to its documents.

- **Plan** — the tree of stages and cross-cutting sections with materials.
- **Trainer** and **Vocabulary** — if the interview is not in the native language (`english` module/references/trainer-format.md`).
- **Interviews** — if there is at least one company.
- **Language switch** — one button per page language (`langs`: the course languages chosen in the first wizard step, plus `en` when English is trained): `RU | EN`, `RU | DE`… One language — no switch. The main language (`lang`) is open by default. Interface: ru and en in the template's `I18N`, other languages — `prep/i18n.<lang>.json` (a translation of the `en` block), missing strings fall back to English. **◐** — theme.

## Data in the page

```js
var OUTLINE = [...];                 // nodes from prep/outline.yaml: id, kind, order, title, title_<lang>, priority, origin, children
var CONTENT = {<lang>: {id: html}, ...};   // one entry per page language, from content/*.<lang>.md
var I18N = {ru: {...}, en: {...}};   // UI strings
var DECK = {...};                    // trainer deck, if any
var COMPANIES = [...];               // from prep/companies/*/company.yaml
var BUILD = {version, built, profile, profile_version};
```

Content is separated from state. The page can be rebuilt any number of times — marks live by id.

## Language switch

- Switches at once: node headings (`title` / `title_en`), materials (`CONTENT.ru` / `CONTENT.en`), UI strings (`I18N`).
- The choice is remembered per viewer: `localStorage['prep.lang']`, reads and writes in `try/catch`. No storage — default `ru`.
- A block has no translation — show the other language with a "no translation" mark and do not hide the topic.
- In English materials `[[keep up with]]` is a link: clicking pops up the word card (`ru`, `note`, examples) and a "to trainer" button.
- Each block has a small "show in the other language" button — to compare a paragraph without switching the whole page.

## Plan tab, top to bottom

1. **Header**: eyebrow, title, intro, "materials ready", "excluded".
2. **Overview**: topics done, "must" topics done, and **readiness by the goals** — the date when every track is finished at its daily goal; the slowest track decides and is named ("slowest: Words, 193 left, 20 a day"). No mixed overall percent: the units of the tracks are not comparable.
3. **Tracks**: one card per study track from the profile (`tracks` in the page data), only tracks that have topics or words. Each card: a ring for today (`done today / goal`), the unit, seven bars for the week (green — goal met, blue — partly), progress `done / total`, and "left N · ≈ date" at the goal pace. A click filters the plan to that track (a chip in the filters removes it); the Words card opens the trainer. "Daily goals" — a slider per track: topics into `S.goals[id]` (doc `prep/state`), words into the trainer goal.
4. **Word trainer** card.
5. Order of preparation, tags, filters, the tree.

A topic's track: the node's own `track:` if set, otherwise the track whose `sections` contain its top-level section (stage or cross-cutting section); otherwise the first topic track. A topic counts for a day by the date of its "done" mark.

## Plan tree

- Arbitrary nesting, **any node collapses**, collapse state is remembered.
- **A progress bar and a `done / total` counter on every node**, recursively over leaves. A collapsed node shows the bar too.
- Skipped (`skip`) topics count in neither the numerator nor the denominator.
- Tags: priority (must / important / optional — «главное / важно / по желанию»), origin (vacancy / my experience / profile / after interview), "failed N times" from the `track` module.
- Filters: priority, origin, not done; search over headings and text in the current language.
- At the top: overall progress, a completion forecast at the current pace, "marked today".
- Leaf: heading, a single "what they'll ask" line, expandable material, "done", "exclude".

## Interviews

One collapsible card per company, toggled in place like the plan cards (open state in `S.expanded["co:<id>"]`). A running process starts open, a finished one collapsed.

- **Header:** name, outcome pill, stages passed / total, chevron. Outcome (`coOutcome`): offer or accepted — success (green); rejected or any failed stage — failure (red); withdrawn or paused — closed (grey); otherwise in progress.
- **Progress bar** under the header: one segment per stage (cancelled and skipped are not counted) — passed green, failed red, scheduled accent, expected grey.
- **Inside:** position, salary range, format; "Next stage" with date and time while the process runs; a link to the company's documents.
- **Stage map:** a vertical stepper in the profile's order, icon and color per status (✓ passed, ✕ failed, ● scheduled, ○ expected, – cancelled or skipped, never color alone). Clicking a stage opens its questions with ratings, impression, what they said, the next step.
- **History** (collapsible): HR calls, emails, decisions; facts (range, deadlines) highlighted.
- Over all cards: one line with the number of companies, in progress, successes, failures.

At the top of the section: upcoming stages by date and "weak spots" («где проседаю») — from `interviews_report.py`.

**"Add entry" form** («Добавить запись»): company (list + new), type (HR call / stage scheduled / stage passed / note / offer / rejection), date, text. Writes to the `inbox` collection and shows "Saved. Ask Claude to "sync interviews"" («Записано. Скажите Claude „синхронизируй собесы“»). The entry reaches the files via the `track` module.

## Live updates

Locally the page is served by `tools/serve.py`. Every 2.5 s the page reads `version.json`; if the build `id` changed, it saves marks and the scroll position and reloads. It does not reload during a trainer session.

## Storage

Order: local server → artifact db → this browser only.

The local server (`/api/state`, `/api/trainer`, `/api/vocab`, `/api/inbox`) writes straight into the prep folder: `prep/page-state.json`, `trainer-state.json`, `vocab-state.json`, `inbox.json` — the hub reads them without syncing.

Via artifact capabilities (load `artifact-capabilities` before building):

```
doc  prep/state      {done: {id: ms}, skip: {id: true}, collapsed: {id: true}, expanded: {id: true}, startedAt: ms}
doc  trainer/state   {items: {cardId: {b, d, s}}}
coll vocab           vocabulary-check batches
coll inbox           "Interviews" form entries, until synced
```

- Save with a delay and when leaving the page. No storage — work in memory and say so.
- Language, open tab, collapsed nodes when `db` is unavailable — in `localStorage` (conveniences only).

### Rules the template must keep (each one broke a real page)

1. **Copy everything read from storage.** The artifact db returns frozen objects (`Object.freeze`); the page runs in strict mode, so `S.expanded[id] = true` on such an object throws and the click handler dies — nothing expands, nothing ticks. Read through `clone()` / `asS()` (JSON copy), never use `d.data()` directly.
2. **Never write a doc you have not read.** Writes are enabled only after all reads finished. A doc that did not exist when the tab loaded is re-read right before the first write and merged (`mergeS`: a mark set anywhere survives). Otherwise an old tab overwrites real progress with its empty state.
3. **Toggle in place, never rebuild the tree inside a click.** A card or group click shows/hides its own body (filled once, lazily) and updates `aria-expanded`; it does not call `drawTree()`. Removing the clicked element during its own handler breaks clicks in WebKit (Safari). A second click within 350 ms is a double click and is ignored (`tooSoon`), not `e.detail`.

4. **Dates are milliseconds, and the forecast trusts only real dates.** `done[id]` is the time in ms (`true` only when the date is truly unknown), `startedAt` is ms. Never write `true`, ISO strings or a separate `doneAt` when moving progress: `Number(true)` is 1 January 1970 and the forecast turns into thousands of days. The template normalizes what it reads (`toTs`, `asS`), counts the pace only from dated marks and hides a forecast longer than two years; `tools/migrate.py` normalizes `prep/page-state.json` the same way.

Check after any template change: Playwright with a mock `window.claude.use('db')` that returns deep-frozen data — expand a card, tick a topic, and an "old tab" (doc missing at load, written later) must not lose the remote marks.

## Before publishing

1. `run validate_profiles.py` and `run validate_content.py --dir .` with no errors.
2. Back up `prep/state` and `trainer/state`; after publishing — check that the number of marks has not decreased.
3. If edited from another session — read the live version and merge.
4. Check at narrow width (phone) and in the dark theme.
