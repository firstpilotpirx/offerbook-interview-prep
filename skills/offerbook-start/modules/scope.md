<!-- A prep hub module. Not a skill: called from skills/offerbook-start/SKILL.md; the person never launches it. -->
<!-- Purpose: A sequential questionnaire for interview preparation — picks the specialty profile and collects the questionnaire (resume, job posting, level, stack, deadline). -->

# module `scope` — questionnaire

The result is the questionnaire `prep/answers.yaml`. Module `outline` builds the topic tree from it.

**Usually called from the wizard (module `wizard`)**: then the questions have already been asked there in steps 7–10, and this module only transfers the answers from `prep/wizard.yaml` into `answers.yaml` and asks whatever the profile requires but the wizard skipped. On its own — to change a single answer.

**Principle: draw nothing by default.** Questions first, then the course.

All example phrases below are said to the person in their explanation language (`explain-language`), translated on the fly.

## 1. Choose the specialty profile

Profiles live in `profiles/` next to the skills. List the available ones:

```bash
run validate_profiles.py            # also checks that the profiles are intact
ls profiles/*.yaml | grep -v '/_'
```

Ask what role the person is applying for, offering options from the non-abstract profiles (`title`). If none fits, say so plainly and offer the closest one. Currently only `backend` exists.

If the validator returned errors — stop and show them: a course cannot be built on a broken profile.

## 2. Load the questions

```bash
run validate_profiles.py --json <profile>
```

Take `scope_questions` from the assembled profile: the common ones from `base` plus the specialty questions. Order by `after`. Ask a question with `when` only if the condition holds for the answers collected so far.

## 3. Ask one at a time

For each question:

1. If `infer_from` contains `resume` or `vacancy` and they have already been received — derive the answer yourself and show it: "From the job posting: level — senior. Correct?"
2. Otherwise ask. `single` and `multi` — as options from `options`; `text` and `file` — open-ended.
3. After the answer, briefly show what you understood and let the person correct it.
4. An optional question can be skipped: use `default` (or "unknown") and say so.

The `stages-known` question is not asked as a list from the profile — only via `run stage_question.py` (2–3 questions by group, see the wizard, step 7). Unknown stages are on by default.

## 4. Save the questionnaire

```yaml
# prep/answers.yaml
profile: backend
profile_version: 1          # from the profile; needed by module `upgrade` for migrations
created: 2026-09-30
updated: 2026-09-30
answers:
  level: senior
  language: java
  databases: [postgresql, redis]
  messaging: [kafka]
  languages: [ru]             # course languages, main one first — from wizard step 0
  explain-language: ru        # = languages[0]
  interview-language: english
  deadline: two-weeks
  weak-spots: "haven't touched PostgreSQL locking in a long time"
skipped: [algorithms]       # skipped ones — so we don't ask again
stages_off: [leadership]    # turned off by the stages-known answer
```

Keys in `answers` are exactly the profile's question `id`s; `single`/`multi` values are exactly the options' `value`s. Otherwise the profile's `when` conditions won't work.

## Change one answer

If `prep/answers.yaml` already exists — don't go through everything again. Show the questionnaire, ask what to change, update the field and `updated`. Then offer to re-run module `outline`.

## Existing portal

If the person gives a link to an already built portal — read it and take the answers, checkmarks and their own stories from there. Progress checkmarks are tied to topic ids — do not rename them.

## End of module

A one-line summary — then back to the hub (the "What do we do next?" menu).
