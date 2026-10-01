<!-- prep hub module. Not a skill: called from skills/offerbook-start/SKILL.md; the person does not run it. -->
<!-- Purpose: Prepares for an English-language interview using the person's own materials — builds a vocabulary from what they will talk about (stories, answers, plan topics), checks what they already know, and builds a spaced-repetition trainer. -->

# module `english` — English for your own stories

Main rule: **only what the person will say themselves goes into the vocabulary.** Not "top 1000 IT words", but words from their stories, their answers and their plan topics. Every card references the topic where the word will be needed (`used_in`). A card without such a reference is a validation error.

Input: `prep/answers.yaml` (`explain-language`, `english-train`, `english-level`, `interview-language`), `prep/outline.yaml`, `content/*.<lang>.md`.

**Card translation language** — the explanation language: the card's `ru` field is the translation into it (the field name is historical; for German it holds German). If the explanation language is English, the module does only step 1 (answers and stories out loud); there is no vocabulary.
Output: `content/*.en.md`, `prep/words.yaml`, the vocabulary-check page and the trainer.

## When to run

- `english-train: full` — vocabulary and trainer; `texts` — only step 1 (answers and stories in English), skip steps 2–6.
- The wizard always asks `english-train`. No answer (an older prep) — first ask it with buttons (wizard step 9), then continue.
- After the `outline` module and at least a draft of the materials: the vocabulary is built from text that does not exist before the build.
- Again — after every `update` module run: new topics bring new words, old cards are not touched.

## Step 1. English corpus

The vocabulary is built from English text, so that text has to exist first.

1. **My answers** (`answers.*`) — translate the way the person will say it out loud: short phrases, conversational register, no bureaucratese. This is not a translation but a retelling in their voice.
2. **My stories** (`stories.*`) — systems and STAR. Keep their numbers and names.
3. **Plan topics** — if English is a chosen course language, the full `.en.md` lessons already exist (module `build`): use them, write nothing extra. Otherwise write a short English companion of each block of `content/<section>.<lang>.md` in `content/<section>.en.md` with the same `@@ id`s: what is said in an interview, not a textbook (material-format.md, "EN companion").

The level from `english-level` sets the text difficulty:

| Level | English text |
|---|---|
| a2, b1 | short sentences, Present/Past Simple, no idioms; key phrases listed separately for each block |
| b2 | normal speech, phrasal verbs, linking words |
| c1 | like a native speaker in an interview, focus on precise terminology |

Show the person the answers and stories in English and let them correct them — these are their words, they will be saying them.

## Step 2. Vocabulary — method (tested on a live run: 1,000 words → 295 to learn)

Goal: **every word needed for this interview, and not a single one the person already knows.** Learning thousands of words makes no sense: the tail of the frequency list gives less and less.

### 2.1. Frequency analysis of your own materials

```bash
run word_freq.py content/ --dir . --top 600 --out prep/word-freq.yaml   # language — from the questionnaire
```

- Cleanup: `@@ id` lines, code blocks and inline code, URLs are not counted — code has its own words, they do not need learning.
- Words of the explanation language → base form (Russian — pymorphy3 with a stop list and parts of speech; others — simplemma, function words are cut off by frequency).
- English words in the text — separately: these are terms the person already reads.
- **Coverage** — show the person the table from the output (on the live run: top 100 — 33% of the text, 300 — 55%, 1000 — 81%). In one line: "so we take the top of the list; the tail doesn't pay off".

### 2.2. First list (≈ 400 words)

Take the top 600 lemmas and find a natural English equivalent for each (the card's translation is in the explanation language) — the way it would be said in an interview. While doing so:

- merge synonyms that map to one English word;
- drop whatever is still a function word;
- give irregular verbs their three forms right away (they also go into the verb deck);
- add words from the vacancy and from your English answers: `run rank_words.py prep/companies/ content/ --weight answers=3 --weight vacancy=2` gives candidates that are not in the explanation-language (e.g. Russian) text.

**Do not take** (in the first or later rounds):
- anything already checked in previous rounds (match by `en` of all cards and `vocab` records);
- simple forms of known words: reading when read is known, sender when send is known;
- names and products: Kafka, PostgreSQL, Spring;
- abbreviations: SQL, API, JVM;
- function words;
- obvious cognates the person already knows: algorithm, architecture, configuration.

Selection and writing — via scripts:

```bash
run words.py --dir . filter candidates.yaml --out prep/round-<N>.yaml   # already seen, forms of known words, abbreviations, names, function words; cognates flagged cognate?
# agent: remove the flagged cognate? the person surely knows; translate; write examples → draft
run words.py --dir . add draft.yaml                                     # id, rank, groups, round number, schema check
run score_words.py prep/words.yaml content/ --boosts prep/word-boosts.txt
run build_page.py --dir .
```

### 2.3. Checking — round by round

The person marks "I know" on the "Vocabulary" tab (step 3). The round's result and what next — `run words.py --dir . round`. Rule by share of known words in the round:

| Known in the round | What to do |
|---|---|
| ≥ 80% | go deeper: **next round** — another ≈ 500 words further down the frequency list, same "do not take" rules, zero overlap with previous rounds |
| 50–80% | one more, smaller round (≈ 200) |
| < 50% | the vocabulary boundary is found — stop the rounds |

When the frequency list yields little new — add general words for technical conversation and interviews: ensure, mitigate, overhead, deadline, stakeholder, ownership, whereas.

On the live run: round 1 — 425 words, knew 400; round 2 — 575 words, did not know almost half. Total 1,000 → 705 known → 295 to learn.

### 2.4. Ranking what to learn

```bash
run score_words.py prep/words.yaml content/ --boosts prep/word-boosts.txt
```

```
score = zipf + 0.6 × log10(1 + frequency_in_materials) + boost
```

- `zipf` — frequency in English (wordfreq): a frequent word is more useful.
- Frequency in materials — by the translation's lemmas in `content/*.<lang>.md` and by the word itself in `*.en.md`. The logarithm keeps a word that occurs 400 times from crushing the rest.
- `prep/word-boosts.txt` — manual boosts, one per line `word +N`:
  - `+1.0` — words and expressions specifically for interviews: trade-off, outage, stakeholder, single point of failure, under the hood, rely on, whereas;
  - `+1.2…+2.2` — terms without which the person's topics cannot be explained: idempotent +2.2, concurrency +2.2, scalability +2.0, maintainability +1.8, overwrite +1.4, mitigate +1.3, pitfall +1.2. They are rare and without a boost would sink to the end.

The script writes `rank`, `g` (groups of 50), `zipf`, `band`. It does not touch `id`.

## Step 3. Checking "what I already know"

First the person marks what they know — otherwise the trainer clogs up with things they know. Everything is on the page, "Vocabulary" tab (format — [trainer-format.md](../references/trainer-format.md#vocabulary-check)):

1. **Quick frequency check** — a first-round accelerator. 10 words from each band without translation; knows 9 of 10 — the whole band is known. In the first round (where the person knows ~95%) it clears hundreds of words in a minute.
2. **Batches of 50** with translation and an "I know" checkbox — for the rest.

Only unmarked words go into the trainer. Result in one line: "Of N checked, you know K, to learn M". By the share known in the round, decide whether another round is needed (table in 2.3).

## Step 4. Cards

`prep/words.yaml` per the schema `schemas/words.schema.json`:

```yaml
- id: "w:keep-up-with"         # slug of en, NEVER changes
  en: keep up with
  ru: успевать за, не отставать от
  g: 1                          # importance group
  rank: 1
  kind: phrase
  note: Всегда с «with». Не путать с keep up — «продолжать».
  used_in: [tech.services.messaging, stories.indexer]
  ex:
    - { en: "...", ru: "...", about: system,   from: tech.services.messaging }
    - { en: "...", ru: "...", about: personal, from: stories.indexer }
    - { en: "...", ru: "...", about: work }
```

(`ru` and `note` above are example data in Russian as the explanation language.)

Rules:

- **id — a slug of the English text with a prefix** (`w:` word, `v:` verb, `p:` phrase, `a:` answer). Not a sequence number: when a new word is inserted the numbers shift, and progress slides onto other cards.
- **Three examples**: about systems, about personal experience, about work in general. The first two come from their materials, with `from`.
- **`note`** — false friends (actual ≠ «актуальный», accurate ≠ «аккуратный»), prepositions, typical mistakes of Russian speakers (or speakers of the explanation language).
- **Importance groups**: one continuous list by `rank` (step 2.4), sliced into 50s. Not by part of speech or by topic — that was tested and is useless. On the page the decks are called "Words 1–50", "51–100"… — the person learns top-down.
- **The three examples** are written in parallel (can be three agents): about systems; about the person's domain and experience; about work and interviews. Irregular verbs get at least one past-tense example.
- **Irregular verbs** — a separate deck, ~70 by frequency: basic ones first, then those for talking about work.
- **Irregular verbs** — only those that occur in their stories, with an example from the story.
- **Phrases** — sentences from the examples, for translating from the explanation language into English.
- **My answers** — the self-introduction and other answers, split by sentence: prompt in the explanation language → say it in English.

In the English materials mark key words as `[[keep up with]]` — the page turns them into a link to the card, and the validator checks that the card exists.

## Step 5. Validation

```bash
run validate_content.py --dir . --require-en
run validate_content.py --dir . --update-lock   # after the first build
```

Do not publish if there are errors. A missing card id = lost progress.

## Step 6. Trainer

**Time before the interview is always limited — you cannot learn everything.** So the trainer is designed so the person takes the most important things every day:

- the main button "Learn by importance": one session — first reviews that are due, by importance, then new words from the top of the list;
- decks "Words 1–50", "51–100"… — for those who want to go through a whole group;
- no spelling or listening practice: in an interview the person speaks, and they can already read. Only recognition and active recall.

In the hub: if there are cards due — a "Review words" item every day; before a scheduled stage — an importance-ordered session first thing.


It is embedded in the prep page as a separate tab or lives as a separate page. Mechanics, storage and UI — in [references/trainer-format.md](../references/trainer-format.md). In short:

- Leitner: intervals 0 / 1 / 3 / 7 / 16 days;
- a new word — pick from 6 options, a familiar one — active recall with self-assessment;
- a mistake returns the card into the same session;
- a composite bar on every deck: learned / consolidating / learning / not started;
- a direction switch EN → RU / RU → EN and an interface-language switch.

## Updating

On an `update` module run: run steps 2–5 only for new blocks. Do not rewrite existing cards or change their `id` and `rank` — new words get the next `rank`s. A word no longer used anywhere is not deleted: remove it from `used_in` and keep it.
