<!-- Source: https://claude.ai/artifact/7uX5sGGDj3MxcZSYPTqKwA (snapshot 2026-09-30) -->
# Personalized prep course builder

Architecture draft. Assembled from the discussion on September 30, 2026 and from the experience of building a working prep portal (404 topics, 1000 checked words, a spaced-repetition trainer).

The document exists so work can continue in a new session without losing context.

------------------------------------------------------------------------

## 1. Idea

A set of skills that, instead of a one-size-fits-all course, builds a **personal prep page** for a specific person and a specific vacancy.

Scenario:

1.  The person installs the skills and runs a command.
2.  The skill "grills" them: which vacancy, which resume, what deadline, what level, what they are afraid of.
3.  It proposes topics with priorities. The person strikes out what's unneeded and marks what they already know.
4.  The skills write materials and build an artifact — a live page with progress.
5.  A trainer for review is built separately.

Positioning in one sentence: **roadmap.sh that knows what you already know and knows how to ask**.

------------------------------------------------------------------------

## 2. What's already on the market

Checked by search on 2026-09-30.

### Interview-prep SaaS

The "resume + vacancy → plan" combination is well covered:

- **PrepGenie** — analyzes the resume and the vacancy, finds gaps, builds a roadmap
- **PrepMind** — turns a job description into a schedule, flashcards, mock interviews
- **Interviews.chat**, **Teal**, **KrackerAI**, **Final Round AI** — the same plus answer practice

What they lack: they don't subtract what the person already knows, and they keep the content to themselves.

### Learning plugins for Claude Code

- **ai-learning-marketplace** — the closest: asks for a topic, researches it on the web, builds a roadmap with phases and criteria, then generates a tutor repository with 30-minute sessions, exercises and progress tracked via git
- **fast-learning / road-to-mastery** — speed versus depth
- There is a whole category of educational plugins on claudeskills.info

What they lack: the output is markdown and a git repository, not a live page; no personalization for a vacancy; no trainer.

### Precedents of working communities

Important for the content model:

- **roadmap.sh** — the community edits the roadmaps it uses itself
- **Exercism** — tracks are maintained by people learning the language
- **AnkiWeb** — decks are shared by people who made them for themselves

Common thread: content is a **by-product of self-interest**, not altruism. This defines the contribution model (see section 7).

### Conclusion

Nothing like this exists as a whole. The open niche: an artifact instead of SaaS, subtracting what's known, a trainer built from your own materials.

------------------------------------------------------------------------

## 3. Portal structure: stages × cross-cutting topics

The main lesson from practice: **not everything fits into stages**. Some sections run in parallel to all stages. The model has two axes.

### Axis 1 — interview stages

Universal for IT, personalized by depth and examples.

<div class="tbl">

| #   | Stage                       | Comment                                               |
|-----|-----------------------------|-------------------------------------------------------|
| 1   | Research and positioning    | company, product, vacancy, self-introduction, salary range |
| 2   | Recruiter screening         | motivation, money, format, start date, language       |
| 3   | Experience interview        | projects, personal contribution, hard decisions, results |
| 4   | Technical interview         | **the main personalized node**, branches by stack     |
| 5   | Practice                    | live coding, take-home task, review, debugging        |
| 6   | Design                      | module and system, trade-offs                         |
| 7   | Behavioral interview        | STAR, conflicts, mistakes, ownership                  |
| 8   | Leadership                  | included depending on position level                  |
| 9   | Final                       | CTO, team, expectations, success criteria             |
| 10  | Offer and negotiation       | compensation, terms, paperwork                        |

</div>

Not everyone gets every stage: some are merged, some skipped. The skill must be able to **turn off a whole stage** based on the survey answers.

### Axis 2 — cross-cutting sections

Not tied to a stage, needed at several at once:

- **Interview language** — if the interview is not in your native language. Minimal grammar, vocabulary from your own materials, ready answers, pronunciation of terms
- **My systems and stories** — what gets told at stages 3, 6, 7. Architecture diagrams, STAR stories, incidents
- **My answers** — cheat sheet: about me, why I'm leaving, salary range, start date
- **Questions for them** — needed at every stage, but different ones: to the recruiter about the process, to engineers about the stack, to the CTO about strategy
- **Trainer** — review on top of everything accumulated

### What is personalized and what is shared

- **Stages 1–3, 5, 7–10** are almost the same for any IT role. Only the examples change. → candidates for a shared community base
- **Stage 4** depends entirely on the vacancy. → generated for the person
- **Cross-cutting** — half and half: shared structure, personal content

This is exactly the boundary between the "community base" and the "personal part".

------------------------------------------------------------------------

## 4. Data model

### Tree node (topic)

    id            stable, never changes               (pg.indexes)
    stage         stage or cross                      (4 | cross)
    parent        for nesting
    title         title
    summary       one line: what exactly they will ask
    priority      1 must / 2 important / 3 optional
    tags          from vacancy, my experience, stack
    body          material in markdown
    sources       list of links to canonical sources
    last_verified date facts were last checked
    lang          material language

### User state (separate from content)

    done{id}       done
    skip{id}       excluded from the plan, not counted in stats
    doneAt{id}     when marked — for deadline forecasting
    collapsed{}    collapsed sections
    startedAt      prep start

**Critical:** state is stored separately from content and keyed by `id`. This lets you rewrite sections any number of times without losing marks. Proven: the portal was rewritten more than ten times and progress was never lost.

### Nesting and collapsing

In the current portal the tree is flat: section → item. That's not enough. **Arbitrary nesting** is needed:

    Stage 4. Technical interview          [bar] 12/86
      └ Databases                          [bar]  8/34
          └ PostgreSQL                     [bar]  5/18
              └ Indexes                    [bar]  2/6
                  └ item: B-tree
                  └ item: BRIN

Requirements:

- **Any level collapses**, not just the top one. Each node has its own collapsed state, remembered between visits (already works for the top level, needs generalizing)
- **A progress bar on every node**, not just the root. A node's bar is computed over all leaves inside it, recursively
- Next to the bar — a `done / total` counter over the same subtree
- Excluded items count in neither the numerator nor the denominator
- A collapsed node still shows its bar: it tells you where to go next

The point: one screen shows which branches are closed, which are touched, and which haven't been started at all.

### File format

Already tried and tested:

    @@ pg.indexes
    Material in markdown.

    @@ pg.explain
    Next material.

One file per section; the builder glues them into a page. For the community, add frontmatter with `sources` and `last_verified`.

------------------------------------------------------------------------

## 5. Skill set

<div class="tbl">

| Skill          | What it does                                                                          |
|----------------|---------------------------------------------------------------------------------------|
| `prep:scope`   | **sequential survey**, step by step. Result — a prep profile                          |
| `prep:outline` | proposes a topic tree with priorities; the person strikes out extras and marks what they know |
| `prep:build`   | writes materials, builds the artifact                                                 |
| `prep:trainer` | frequency analysis of materials → vocabulary → spaced-repetition cards               |
| `prep:update`  | adds topics along the way **without losing progress** — the hardest part              |
| `prep:share`   | exports the person's edits to the shared base as a PR                                 |

</div>

### Call order

    scope → outline → (person edits) → build → trainer
                                          ↑
                                       update (many times)

### `prep:scope` — sequential wizard

**Principle: draw nothing by default.** The topic tree is built only from the person's answers, step by step. Not "here's a course, strike out what you don't need", but "answer the questions and a course will be assembled from them".

Steps come one at a time; each next one depends on the previous:

1.  **Who you are** — name, role, years in development
2.  **Resume** — file or link; if none, a short account of experience. This gives stack, level, projects
3.  **Vacancy** — text, link or company name. This gives requirements and priorities
4.  **Position level** — junior / middle / senior / lead. Affects whether stages 6 and 8 are included
5.  **Which stages there will be** — if known from correspondence with the recruiter. Unknown ones are on by default; extra ones are turned off entirely
6.  **Deadline** — when the interview is. Determines depth and volume of materials
7.  **Interview language** — whether the cross-cutting language section is needed
8.  **Weak spots** — what they fear, what they haven't touched in a while. Raises priority
9.  **What to exclude** — topics that certainly won't come up or that they know by heart
10. **Own systems** — which projects they're ready to talk about, what can't be disclosed (NDA)

After each step the skill shows what it understood and lets the person correct it. Only once the profile is complete does it move on to `prep:outline`.

Important details:

- A step can be skipped; then a reasonable default is used, and this is said explicitly
- The profile is saved; you can come back to it and change one answer without going through everything again
- Multiple-choice questions rather than open ones wherever possible: faster to answer
- **Link to an existing portal.** If the person already has a built page, they give the link and the skill reads it as a source: takes topics, marks, their own stories. That way an update doesn't start from scratch, and migration between builder versions works

------------------------------------------------------------------------

## 6. Content reliability

The problem is real: while building the portal, the model gave a broken link to the JUnit guide and the wrong Spring Boot version for `@ServiceConnection`.

**A list of links doesn't save you.** It removes made-up URLs, but not made-up facts.

What's needed:

1.  **A registry of canonical sources** per stack: roots of the official documentation for Java, Spring, PostgreSQL, Kafka, ClickHouse, Redis and so on
2.  **Generation rule:** any statement about a version, API or limit is either confirmed by a fetch from the registry or marked "verify before the interview"
3.  **CI for links:** once a week, hit every URL; broken ones go into an issue. Cheap and immediately visible
4.  **`last_verified` on every topic.** Knowledge goes stale: in a year, half the facts about versions are wrong. The date lets the generator say "this topic is 14 months old, re-check it"

`last_verified` matters more than the license.

------------------------------------------------------------------------

## 7. Community model

"I'm the engine, they're the boards" sounds logical but usually falls apart: nobody wants to fill someone else's base.

**Solution: contribution as export, not as separate work.**

A person prepared for an interview, fixed three topics locally, pressed "share" — the edits go upstream as a PR. Then the base fills itself, and it gets exactly the content someone actually needed.

### Open question (decide first)

Is the base shared and versioned (git, PRs, review) — or does everyone have their own copy, with only topic "seeds" shared?

- The first gives quality but needs moderation
- The second starts instantly, but content drifts apart

**Proposal:** start with the second, with the option to send an edit upstream. Add moderation once there is a flow.

------------------------------------------------------------------------

## 8. Where the real value is

Not in the content — an LLM will write it. In three things:

1.  **Subtracting what's known.** "Mark what you know" → a plan from what's left. Real result: of 1000 words, 295 remained (705 already known); of 404 topics, some were excluded by hand. Neither roadmap.sh nor the SaaS tools have this — it pays them to show a big course
2.  **Stable ids and progress migration.** Without this, people stop updating the course after the first lost marks
3.  **Measurement.** Deadline forecast at current pace, percentages, memorization stages, "reviewed today"

------------------------------------------------------------------------

## 9. What already works (reference for the skills)

Everything below was built by hand and tested in practice — it is the model of what the skills should generate.

### Portal

- 404 topics in 35 sections, each with reading material
- Labels: must / important / optional, from vacancy, my experience
- Filters, search, collapsible sections with memory
- Excluding a topic from the plan: not counted in stats
- Completion forecast at the current pace
- Progress syncs across devices

### Vocabulary check

- Frequency analysis of materials: pymorphy3 for Russian lemmatization + wordfreq for general English frequency
- Pages of 30 and 50 words, "I know it" marks, saved in batches
- Result: 1000 checked, 705 known, 295 to learn

### Trainer

- 8 sections with their own progress bar: 6 word groups by importance, irregular verbs, phrases
- Stacked bar: learned / consolidating / learning / not started
- A new word — choose from 6 options; a familiar one — active recall with self-assessment
- Leitner: intervals of 0 / 1 / 3 / 7 / 16 days; a mistake returns the card to the same round
- Cards are taken by importance and shown shuffled
- Three examples per word: about systems, about personal experience, about work
- Notes on false friends (`actual` ≠ the Russian "актуальный", i.e. "current") and prepositions

### Word ranking

Two signals: frequency in English overall (wordfreq) + frequency of the concept in the portal's materials. Technical words without which topics can't be explained (`idempotent`, `concurrency`, `scalability`) are boosted by hand.

------------------------------------------------------------------------

## 10. Pitfalls

Collected along the way, all real:

1.  **Duplicate function definitions.** A new version of a function was inserted above the old one — because of hoisting, the old one runs. Check with `grep -c "^function name"`
2.  **Progress lost on publish.** Back up state before every publish, verify after
3.  **Artifact version conflicts.** If it was edited from another session — read the live version and merge, don't overwrite
4.  **Parts of speech instead of importance.** Word lists split into verbs/nouns are useless. You need a single list in descending importance, cut into equal groups
5.  **Ask first, then do.** Things had to be redone several times because of a misunderstood wording
6.  **Links go stale.** AWS Builders' Library moved to another domain, the JUnit guide returned 404

------------------------------------------------------------------------

## 11. What to decide next

1.  Shared base or seeds (section 7)
2.  Which minimal skill set to release first — probably `scope` + `outline` + `build`
3.  Source registry format: a file in the repository or a separate package
4.  How many steps in `prep:scope` are required and how many can be skipped
5.  Whether position level needs to be a separate dimension (junior / middle / senior / lead) or is inferred from the vacancy
6.  Tuning for roles: backend first, then QA, frontend, analysts
7.  How to read an existing portal by link: parse the HTML or keep topic sources alongside

------------------------------------------------------------------------

## 12. Links to working artifacts

The first build, made by hand. Serves as a reference and a source for the skills.

- **Prep portal** (404 topics, trainer built in at the top): https://claude.ai/artifact/TCtE94RfA1AoZZ4K5Sy7nZ
- **Vocabulary check** (1000 words, "I know it" marks): https://claude.ai/artifact/AUu3pf9vnpd4n3qErWdgDv
- **Trainer as a separate page** (early version, later built into the portal): https://claude.ai/artifact/TQr51erXpYiapJ4Gk6LHAF

Build sources: `content/*.md` with `@@ id` markup, `template.html`, `build.py`, `word_freq.py`.

------------------------------------------------------------------------

## Appendix. Detailed stage tree

Base from another agent, kept as a reference for `prep:outline`.

### General list for IT

1.  **First conversation with a recruiter** — introduction, experience, motivation, salary, format, start date, language
2.  **Experience and role-fit interview** — projects, personal contribution, difficult situations, results, interests
3.  **Professional interview** — specialty knowledge, tools, approaches, processes, review of practice
4.  **Practical task** — a real-time task, take-home assignment, review of finished work, defending the solution
5.  **Collaboration interview** — team, communication, conflicts, feedback, autonomy, priorities
6.  **Leadership interview** — planning, decisions, risks, mentoring, cross-team collaboration, people management
7.  **Final interview** — manager or team, tasks, success criteria, candidate's questions
8.  **Closing the hire** — references, offer, negotiation, start date

### For a backend developer

1.  **Recruiter** — experience, stack, level, motivation, money, format, date
2.  **Experience and project review** — which services, what you owned, what loads and volumes, what decisions you made, what failures you resolved
3.  **Technical interview** - Language and platform: specifics, standard library, memory, concurrency and async - Frameworks: request handling, dependencies and configuration, data access - Databases: SQL and schema, indexes and plans, transactions and locks, choosing a store - Networking and APIs: HTTP, REST, gRPC, authentication, timeouts, retries, idempotency - Service interaction: queues and brokers, caching, consistency, partial failures - Quality and operations: tests, security, logs, metrics, tracing, CI/CD, containers
4.  **Practical interview** — algorithms, an applied task, SQL, debugging, review, tests
5.  **Take-home assignment** — a service or API, database, validation and errors, tests, discussion
6.  **Design** - Module: interfaces, boundaries of responsibility, code structure, extensibility - System: requirements and load, components, API, data model, storage, caches, queues, scaling, fault tolerance, security, observability, cost, trade-offs
7.  **Behavioral** — working with product, frontend, QA, infrastructure; requirements and deadlines; disagreements; ownership of incidents; initiative and mentoring
8.  **Technical leadership** — strategy and architecture, breaking down large changes, technical debt, growing developers, hiring, alignment with the business
9.  **Final and offer** — team tasks, ownership of services and on-call, goals for the first months, terms, start date
