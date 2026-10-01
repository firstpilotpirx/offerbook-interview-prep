<!-- A prep hub module. Not a skill: called from skills/offerbook-start/SKILL.md; the person never launches it. -->
<!-- Purpose: Builds the interview-preparation topic tree from the specialty profile and the questionnaire — applies conditions, expands the stack, sets priorities, lets the person cross out what's unneeded and mark what they already know. -->

# module `outline` — topic tree

Input: `prep/answers.yaml` and a profile from `profiles/`. Output: `prep/outline.yaml`.

All example phrases and button labels below are said to the person in their explanation language (`explain-language`), translated on the fly.

## 1. Assemble the profile

```bash
run validate_profiles.py --json <profile from the questionnaire>
```

If there are errors — stop and show them. If `profile_version` in the questionnaire is lower than the profile's `version` — warn: some ids may have changed; progress is reconciled via `_ids.lock.json`.

For a quick look at what remains after the conditions:

```bash
run validate_profiles.py --print backend --level senior --answer messaging=kafka --answer interview-language=english
```

## 2. Apply the questionnaire

In order:

1. **Stages.** Remove those turned off by a `when` condition and those listed in `stages_off`.
2. **Cross-cutting sections.** Remove those turned off by `when`.
3. **Topics.** Remove those turned off by `when`, recursively.
4. **Expansion.** For a topic with `expand: from-answer`, add children based on the answer to `expand_from`. For example, `tech.db` + `databases: [postgresql, redis]` → `tech.db.postgresql`, `tech.db.redis`, each with its own items. For `from-vacancy` — based on the job posting's requirements.
5. **Tracks.** Every topic lands in a study track by its section (`tracks` in the profile: theory, coding problems, system design, soft skills; words live in the trainer). Set `track: <id>` on a node only when it sits in a section of another kind — for example LeetCode problems inside the tech stage go to `problems`.
6. **Priorities.** Raise to 1 whatever is named in the job posting or in `weak-spots`. Lower to 3 whatever appears in the resume as a strength. System design cases (`design.cases.*`) close to the posting's domain — priority 1; domain cases not in the catalog (e.g. a wallet or an exchange for fintech) — add with id `design.cases.<slug>` and `origin: vacancy`.
7. **Exclusions.** Mark everything from `exclude` as `skip`; do not delete.

### ids of expanded topics

- id = parent id + `.` + slug of the value: `tech.db.postgresql`, `tech.db.postgresql.indexes`.
- **Never change the id of a topic that has already been issued.** Progress is tied to it.
- Before writing, check that all ids in the tree are unique.

## 2½. Foundation — for approval

Besides the stage topics, the profile has a "Foundation" section (`offer: true`): theory for the stack — normalization and isolation for relational databases, delivery semantics for brokers, SOLID and GoF, Fowler's patterns, DDD, microservice patterns, distributed systems. Do not include it silently — offer it:

```bash
run theory_question.py --profile <profile> --dir <folder>
```

Show `questions` on one screen (AskUserQuestion, multiSelect). Selected blocks go into the plan; their topics expand as lessons. Unselected ones go into `state.skip` (do not delete: the person can bring them back on the page). In one line: "Added foundation: relational databases, integration, code and design."

Tie a theory lesson to technology: in "Essence" — the principle; in "How it works" — how it's done in the person's stack (normalization → what it looks like in their PostgreSQL schema; outbox → how their Kafka + database do it).

## 3. Show it to the person

Show it stage by stage, not all at once. At each stage:

- topics with priorities (● key, ◐ important, ○ optional) and a label for where the topic came from: profile, job posting, your experience;
- ask: what to cross out, what you already know.

Crossed out → `skip`, known → `done`. Delete nothing: crossed-out items can be brought back.

## 4. Save

```yaml
# prep/outline.yaml
profile: backend
profile_version: 1
built_from: prep/answers.yaml
built: 2026-09-30
order:                     # "Preparation order" in the page header: 4–6 steps, the most important for the posting first
  - System design and your own systems
  - Java, Spring, concurrency
  - Kafka, PostgreSQL
  - Everything else
nodes:
  - id: tech
    title: Technical interview
    kind: stage            # stage | cross | topic
    order: 4
    children:
      - id: tech.db
        title: Databases
        priority: 1
        origin: profile    # profile | vacancy | resume | answer
        children:
          - id: tech.db.postgresql
            title: PostgreSQL
            priority: 1
            origin: answer
      - id: tech.algo-warmup
        title: LeetCode warm-up on Java
        track: problems    # optional: move a node to another study track (profiles → tracks)
state:                     # separate from the content, keyed by id
  done: [tech.api.http]
  skip: [tech.api.grpc]
```

## End of module

A one-line summary — then back to the hub (the "What do we do next?" menu).

## Editing the plan (`mode: update`)

The first screen — "What to change?" buttons: "Add topics", "Remove topics", "New job posting", "Raise priority".

- New topics get new ids; **old ids are never changed or deleted** — anything removed from the plan is marked `skip`.
- "New job posting" → posting text, comparison with the resume, new topics with `origin: vacancy`, priorities recalculated.
- After the edit: `run validate_content.py --dir <folder>`; then the hub will offer to update the materials and the page by itself.
