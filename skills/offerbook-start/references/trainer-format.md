# Trainer and vocabulary-check format

Taken from the working version ("Word trainer", "Interview vocabulary", the portal's built-in trainer) and fixed where it used to break.

**Implemented in the "Vocabulary" and "Trainer" tabs of the page template (`templates/portal/page.js`, styles — `page.css`).** The deck gets there from `prep/words.yaml` via `tools/build_page.py`. Do not hand-write a separate trainer page.

## Data

The page receives the deck as one JSON built from `prep/words.yaml`:

```js
var DECK = {
  version: 1,
  groups: [{g: 1, title: "Самое нужное", title_en: "Must know"}],
  words:   [{id: "w:keep-up-with", en, ru, g, rank, kind, forms, note, used_in, ex: [{en, ru, about, from}]}],
  verbs:   [{id: "v:be", inf, past, pp, ru, ex}],
  phrases: [{id: "p:...", en, ru, g, word, from}],
  answers: [{id: "a:pitch-1", prompt_ru, en, from}]
};
```

(`title` holds the group name in the explanation language — Russian in this example.)

**The progress key is the card's `id`.** The old version used `'w' + index`: inserting a word in the middle shifted progress onto neighbors. Do not repeat this.

Migration from the old version: map old `w<i>` to new `w:<slug>` by the `en` field and carry the state over once on load.

## Decks

Main principle — **time is limited, learn from most to least important.** At the top of the tab — 4 counters (learned, in progress, not started yet, reviewed today) and a big "Learn by importance" button. Below — decks under the headings "Words by importance" and "Other", each with: name, "Group N of M · K cards", a large due count on the right, a composite bar and a legend with numbers. At the bottom: "Cards per round" 10/20/30/50, direction, "Reset progress" (on the second click).

Session: a header with "← Back to decks", position, ✓ and ✗; a thin progress strip; the card in the center; a new word — 6 options as a list; after answering — the translation, a note (false friends, prepositions) and one random example. Keys: Space/Enter — show/next/got it, 1 — missed, 2 — got it, Esc — back to decks.

| Deck | What | Direction | Size |
|---|---|---|---|
| "Learn by importance" | all unknown words: first due ones by `rank`, then new ones by `rank` | mixed | session size |
| "Words 1–50", "51–100"… | unknown words by `rank`, sliced into 50s after "I know" marking | mixed (60% RU→EN), EN→RU, RU→EN | 50 |
| Irregular verbs | only from your own stories | three forms | all |
| Phrases | sentences from the examples | RU→EN | by group |
| My answers | answers split by sentence | RU prompt → say it in EN | all |

## Four sides of a word

Each word is asked in four ways — each has its own Leitner box, state key `<id>|<side>`:

| Side | Given | What to do |
|---|---|---|
| `pick-en` | word in the explanation language | pick the English one out of 6 |
| `pick-ru` | English word | pick the translation out of 6 |
| `say-en` | word in the explanation language | recall the English → "Got it / Missed" |
| `say-ru` | English word | recall the translation → self-assessment |

- In a session the sides are **mixed**: random order, the same word never twice in a row, a word's picking sides come before its recall sides.
- A word is learned when all four sides are learned (minimum box = 4); a word's status in the bars follows its minimum box.
- "Cards per round" counts sides: 20 ≈ 5 words × 4 sides.
- Progress from past versions (one box per word, key `<id>`) is carried over to all four sides on load; the old key is not deleted.
- Verbs, phrases and answers — one side, as before.

## Mechanics (Leitner)

```
STEPS = [0, 1, 3, 7, 16]   // days until the next showing, by box
state[id] = {b: box, d: due (ms), s: seen (bool), f: first shown (ms), l: last shown (ms), n: total reviews, t: reviews today}
```

- **New card** (`!s`): pick from 6 options. Distractors come from the same group and the same `kind`, otherwise the answer can be guessed by form.
- **Familiar card**: show the prompt → "Show answer" → self-assessment "Got it / Missed".
- Correct: `b = min(b + 1, 4)`, `d = now + STEPS[b] * DAY`.
- Mistake: `b = 0`, the card **goes back to the end of the current session**.
- **Session**: cards with `d <= now`, lower `rank` first, mixed within the session. Size 10 / 20 / 30. If everything is reviewed — 10 random ones.
- End-of-session screen: got / missed, how many are due for review, "Another round" and "Back to decks".

### Composite bar

On every deck and group, over all cards:

| Segment | Condition |
|---|---|
| learned | `b = 4` |
| consolidating | `b` 2–3 |
| learning | `s` and `b` 0–1 |
| not started | no state |

Next to it — "reviewed today" and the due count.

### Progress and forecast

- **Progress %** of a deck or of everything: the average box over all sides, `Σ min(b, 4) / (4 × sides)`. It moves with every correct answer, not only when a word is fully learned.
- **Pace**: cards started per day (`f`, or `l` for cards from older versions) over the last 14 days. Word decks share one pace; verbs, phrases and answers each have their own.
- **Forecast** per deck and overall, shown as "start in N days · learned ≈ by <date>":
  - word decks are started in order (the "by importance" round goes from the top), so deck k starts when all fresh words of decks 1..k are started: `(fresh before + fresh in deck) / pace`;
  - a started side still needs its remaining intervals `STEPS[b+1..3]` from its due date; a fresh one `1 + 3 + 7 = 11` days after it is started;
  - the deck is learned when its slowest card is. It assumes no mistakes and says so; with no pace yet — "the estimate appears after your first rounds".
- Shown on the trainer tab (overall line + every deck) and on the trainer card on the Plan tab.

### Daily goal

- `goal` — new words a day, stored next to the progress (`trainer/state.goal`, local server: `trainer-state.json`), 20 by default; a slider 5–50 on the trainer tab changes it.
- A word counts on the day it was first shown (its earliest side, `f`). Today's ring: new words today / goal; seven small rings for the week; a streak of days with the goal met (today not finished yet does not break it).
- "Learn by importance" puts reviews first, then at most `goal − new today` new words. When the goal is met and nothing is due, the button turns into an explicit "Extra round" without the cap. Single decks are never capped.
- The forecast for word decks uses the goal as the pace (the actual pace is shown next to it).

## Pronunciation

The browser's own Web Speech API (`speechSynthesis`): no keys, no subscriptions, no network for system voices; the voices come from the OS (macOS and iOS have good en-US, en-GB and Russian voices; Chrome adds online Google voices).

- 🔊 next to every English word and example: on the trainer card, in the vocabulary check and lists, in the [[term]] popup. Inside a checkbox row the button does not toggle the checkbox.
- **A smooth round, no extra clicks** (all on by default):
  1. the card opens → its question is spoken in its language (Russian voice for the translation side, English for the English side);
  2. a "pick of 6" answer → a short rising chime and a green frame if right; a low buzz, a red frame and a shake if wrong; then the correct answer is spoken (a hidden answer is never spoken before that);
  3. after the answer has been spoken to the end (if a browser drops the end-of-speech event, the page waits while it is still speaking), a pause and the next card opens by itself. Two pauses: after a right answer (2 s by default) and after a mistake (3.5 s), each 0–5 s in steps of 0.1 s — sliders in the settings and under the card during a round. A countdown bar runs on "Next", which skips the wait;
  4. self-assessed cards: "Show answer" speaks the answer; "Got it" chimes, "Missed" buzzes.
  `V` repeats the question, or the answer once it is shown. Sounds are synthesized with Web Audio — no files.
- Settings on the trainer tab, per device (`localStorage prep.tts`): auto-play, sounds ✓/✗, auto-advance and its two pauses, English voice (any `en-*` voice of the device, "default" picks Enhanced/Premium/Natural/Google voices first), speed 0.7–1.15×.
- No speech API or no voice for the language — no buttons, nothing breaks.

## Word card

- `en` in large type, `forms` below it (forms or transcription);
- after answering: `ru`, `note` (false friends, prepositions) and three examples labeled: system, my experience, work;
- a "used in" link → topics from `used_in` on the prep page.

## Language

- Direction switch: EN→RU / RU→EN.
- Interface-language switch RU / EN — shared with the prep page (see `build` module/references/page-format.md`).

## Storage

Via the artifact's `db` capability (load `artifact-capabilities` before building):

```
doc  trainer/state      {items: {<id>: {b, d, s}}, updated}
coll vocab              check-batch documents: {known: [id], unknown: [id]}
```

- Save with a delay (debounce ~1.5 s) and at the end of a session.
- If storage is unavailable — work in memory and honestly show "progress is kept in this window only".
- Before every publish of a new version — back up `trainer/state`; after it — reconcile the card count with the state.

## Vocabulary check

A separate page or tab before the trainer.

**First, the quick frequency check** (if cards have `band` or `zipf`):

- Bands: 1 — zipf ≥ 5, 2 — 4–5, 3 — 3–4, 4 — < 3. A band with fewer than 20 words is not included in the quick check.
- Per band — 10 words, evenly spread by `rank` (`list[floor((i + 0.5) * n / 10)]`), **without translation**: it is a check, not a hint.
- ≥ 9 of 10 ticked → the whole band goes into `known`, except the unticked words from the sample. Otherwise only the ticked ones go into `known`, the rest go to batches.
- Storage: batch `q<band>` in `vocab`: `{band, pass, known, unknown, at}`. "Recheck" → `{reset: true}`, such records are not counted. "I'll tick everything by hand" → `{pass: false, skipped: true}` for all bands.
- While there is an unchecked band — the tab shows only the quick check; batches come after it.

**Then batches** — for words not resolved by the quick check:

- Words in `rank` order, in batches of 30 or 50.
- Each has: `en`, `ru`, an "I know" checkbox. A "Save batch and continue" button.
- A batch is saved as a whole: `{known, unknown}` — to tell "don't know" from "didn't look".
- Counters: checked / know / to learn. Opens at the first unchecked batch.
- Only `unknown` words go into the trainer. A word marked "I know" can be returned to the trainer with one click.

## Pitfalls we have already hit

- Groups by part of speech instead of importance — useless; only one continuous list by `rank`.
- Duplicate functions when editing the page: the new function is placed above the old one, and due to declaration hoisting the old one runs. Check with `grep -c "^function name"`.
- Edits from another session: read the live version and merge, do not overwrite.
