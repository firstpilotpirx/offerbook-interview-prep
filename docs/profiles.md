# Specialty profiles

A profile is a YAML file in `profiles/` that defines, for one specialty:

- **interview stages** (axis 1) and their order;
- **cross-cutting sections** (axis 2) and which stages need them;
- **base topics** — a tree with priorities and stable ids;
- **survey questions** for the `scope` module on top of the common ones;
- **a registry of sources** for fact-checking.

## Languages: English-first

Profiles are written in English. Every human-readable field has an English primary value and an optional Russian twin:

| English (required where the field is used) | Russian (optional) |
|---|---|
| `title` (profile, stage, section, topic, source) | `title_ru` |
| `summary` (stage, section, topic) | `summary_ru` |
| `description` (profile) | `description_ru` |
| `text` (survey question) | `text_ru` |
| `label` (question option) | `label_ru` |

- Option `value`s, ids, `when` conditions and priorities are never translated.
- Book titles in `sources` keep their original names.
- If a `*_ru` field is missing, the English text is shown (e.g. `gRPC`, `PostgreSQL`).
- **Other explanation languages are translated by the agent at outline time**: `prep:outline` writes `title`/`summary` in the explanation language into `prep/outline.yaml`, and `title_en`/`summary_en` in English.
- The validator rejects Cyrillic in the primary fields: Russian goes only into `*_ru`.

Consumers pick the language like this (`validate_profiles.localized(obj, field, lang)`): `<field>_<lang>` if present, otherwise the English `<field>`.

- `tools/build_page.py` — stage titles on the page: `title_<explain-language>` or `title`; `title_en` in the page data is the English `title`.
- `tools/stage_question.py`, `tools/theory_question.py` — button labels: English by default; `--lang ru` (or `--dir` with `explain-language: ru`) takes `*_ru`.
- `tools/validate_profiles.py --print <id> --lang ru` — the tree with Russian titles.

## Inheritance

```
base (abstract)  ──►  backend
                 ──►  qa          (later)
                 ──►  frontend    (later)
```

`base` contains everything common to IT: 10 stages, 5 cross-cutting sections, 12 common questions. A specialty writes **only the differences**:

| What you need | How |
|---|---|
| add topics to a stage | a stage with the same `id` and a `topics` list — the topics are appended to the base ones |
| replace a stage's topics entirely | the same plus `replace_topics: true` |
| remove a stage, section or topic | `disable: [design, practice.live]` |
| a new stage | a stage with a new `id`; `title` and `order` are required |
| new survey questions | `scope_questions`, ordered via `after` |

## Study tracks

`tracks` in `base.yaml` splits the plan into kinds of work, each with its own unit and daily goal: theory (15 topics), coding problems (3), system design (1), soft skills (2), words (20, the trainer). `sections` lists which stages and cross-cutting sections belong to the track; every section is in exactly one track (`validate_profiles.py` checks it and warns about sections in no track). A specialty overrides a track by `id` (for example a lower `goal` or extra `sections`) or adds its own. A single outline node can be moved to another track with `track: <id>`. The page shows a ring per track and the readiness date of the slowest one (`references/page-format.md`).

## Conditions

`when` includes a stage, section, topic or question depending on the level and answers:

```yaml
when: { level: [senior, lead] }
when: { answer: { messaging: [kafka, rabbitmq] } }
```

Fields inside `when` are AND, values within a field are OR. If there is no answer, a condition on it does not turn anything off.

## Expansion

A profile does not list everything: PostgreSQL, Kafka or Spring come from the answers. A topic with `expand: from-answer` and `expand_from: databases` tells the `outline` module: "add children here for the selected databases". Children written in the profile remain the shared skeleton.

## Sections for approval and books

A cross-cutting section with `offer: true` (for backend — "Fundamentals") is not included silently: the wizard shows its blocks as buttons via `tools/theory_question.py`, and blocks matching the person's stack are marked "recommended". Blocks are switched on by survey answers (`when`): relational theory — if PostgreSQL or MySQL is present, caching — if Redis, integration — if there is a broker.

`sources` is the registry of canonical sources, including books. `covers` links a source to topics: lesson generation takes from there what to rely on.

## Id rules

- format `stage.topic.subtopic`, Latin letters, hyphens;
- a topic id starts with its parent's id;
- **an id never changes** — user progress is bound to it;
- `profiles/_ids.lock.json` stores all ids; removing an id is an error until `version` is bumped and the lock is updated;
- renames between versions go to `profiles/_renames.yaml` (progress is migrated by `tools/migrate.py`).

Translating or rewording `title`/`summary`/`*_ru` does not change ids and needs no `version` bump.

## Validation

```bash
pip install -r tools/requirements.txt
python3 tools/validate_profiles.py                    # all profiles
python3 tools/validate_profiles.py --print backend    # tree
python3 tools/validate_profiles.py --print backend --lang ru   # tree with Russian titles
python3 tools/validate_profiles.py --print backend --level senior --answer messaging=kafka
python3 tools/validate_profiles.py --json backend     # for skills
python3 tools/validate_profiles.py --update-lock      # after an intentional id change
```

What is checked:

1. schema (`_schema.json`): fields, types, id format, priorities 1–3, https for sources, only known `*_ru` fields;
2. primary text fields (`title`, `summary`, `text`, `label`, `description`) contain no Cyrillic;
3. the id matches the file name; `extends` exists, no cycles;
4. `disable` refers to something the parent has;
5. ids are unique across the resolved profile and start with the parent's id;
6. stages have a unique `order`; a non-abstract profile has no empty stages;
7. `used_in` refers to existing stages;
8. `when` uses only declared levels, existing questions and their options;
9. `expand_from` refers to an existing question;
10. questions: choice questions have options, `after` exists and has no cycles;
11. `covers` of sources refers to existing topics;
12. no ids disappeared compared to the lock, and `version` is bumped when ids change.

## New specialty

Copy `_template.yaml` → `profiles/<id>.yaml`, fill in the differences (English `title`/`summary`, Russian in `*_ru`), run `--print`, then `--update-lock`.
