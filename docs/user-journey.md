# User journey

## In short

The person knows one entry point — `/offerbook-start`. From there the hub leads them around the loop and shows a menu after every step. Coming back later, they can say `/offerbook-next` or "what's next" — the menu opens right away:

```
  folder ─► sync with the page ─► menu as buttons ─► action ─► summary ─┐
                ▲                                                       │
                └───────────────────────────────────────────────────────┘
```

The menu is computed by `tools/next_steps.py` from the prep files, so the suggestions are the same in any session:

| Situation | First button |
|---|---|
| nothing yet | Start preparing |
| wizard interrupted | Continue the wizard |
| a stage at a company has passed, no debrief | Debrief the stage at X |
| there are entries from the form on the page | Bring in entries from the page |
| a stage within the next 7 days | Prepare for X |
| answers exist, no plan | Build the plan |
| topics without material | Write materials |
| no page, or materials are newer | Build / update the page |
| `english-train: full`, no vocabulary | Build the vocabulary |
| there is a vacancy, no resume for it | Resume for X |
| everything is built | Continue with the plan (top 3 topics) |

Always available: "Log an interview", "Change the plan", "Change answers", "Done for today".

## 1. Wizard

One entry point, step by step; any optional step can be skipped and any step revisited. Nothing is generated before the summary.

| # | Step | Can skip | What it gives |
|---|---|---|---|
| 0 | Explanation language: English (default) / your language / other | no, first screen | language of conversation, materials and page; switch to EN |
| 1 | Goal: vacancy / interview scheduled / searching / update | no | wizard branch |
| 2 | Specialty → profile | no | stages, topics, questions |
| 3 | Resume: upload / create from scratch / tell about it | yes | experience, stack, stories |
| 4 | Vacancy + match against the resume | yes | priorities, gaps |
| 5 | Company in "Interviews" | yes | company card |
| 6 | Plan basis: vacancy / resume / profile / weak spots | no, default | origin and topic priorities |
| 7 | Level, deadline, stages | partly | depth, which stages to include |
| 8 | Stack (profile questions) | partly | expands the technical stage |
| 9 | English: whether to train it (always asked), level, what to prepare | no, required | English block |
| 10 | Weak spots, exclusions | yes | priorities, skip |
| 11 | What to generate | no, preselected | set of skills |
| 12 | Summary → "Generate" | — | launch |

State is kept in `prep/wizard.yaml`: you can stop and come back.

## 2. Generation

```
module `resume` → module `scope` → module `outline` → module `build` → module `english` → module `track`
```

The page is published as soon as the plan is ready; materials are added after it.

## 3. The page

- **Plan** — tree of stages, progress on every node, materials, RU / EN.
- **Vocabulary** — mark what I already know (from the words of my own materials).
- **Trainer** — Leitner: words, verbs, phrases, my answers.
- **Interviews** — companies, stage timelines, HR conversations, a form for notes.

## 4. Updates

| What | How | Skill |
|---|---|---|
| Mark something done | checkbox on the page or "mark X" in chat | page / module `track` |
| HR conversation, stage scheduled, offer | form on the page → "sync interviews", or tell it in chat | module `track` |
| Debrief of a past stage | a series of questions in chat | module `track` |
| New topics, another vacancy | in chat | module `update` |
| New words after new topics | automatically after the update | module `english` |
| Change one wizard answer | "change step N" | module `wizard` |

Interview outcomes flow back into the plan: topics where the person struggled move up in priority, and the "done" mark is removed.

## Files

```
prep/
  wizard.yaml         wizard answers
  answers.yaml        questionnaire for the profile
  cv/cv.en.yaml       resume (schemas/cv.schema.json)
  outline.yaml        topic tree + done/skip state
  words.yaml          deck
  ids.lock.json       stable ids
  companies/<id>/
    company.yaml      stages, questions, conversations
    vacancy.md
    cv.en.yaml        tailored resume
content/
  <section>.ru.md
  <section>.en.md
```

## Hub modules

| Module | Status |
|---|---|
| module `wizard` | wizard, done |
| module `resume` | done |
| module `scope` | done, called by the wizard |
| module `outline` | done |
| module `build` | done |
| module `english` | done |
| module `track` | done |
| module `update` | next |
| module `mock` | later: mock interview on plan topics |
| module `share` | later |
