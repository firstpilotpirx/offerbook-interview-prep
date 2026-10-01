<!-- A prep hub module. Not a skill: called from skills/offerbook-start/SKILL.md; the person never launches it. -->
<!-- Purpose: A step-by-step interview-preparation wizard — leads from the goal through resume, job posting, company, plan basis, stack and language to generating the page, materials and trainer; every step can be skipped and any step revisited. -->

# module `wizard` — the wizard

The wizard is the single entry point. It generates nothing itself until the last step: it collects answers, shows a summary, and only on the "Generate" button calls the other skills.

All button labels and phrases below are examples: say them in the person's explanation language (`explain-language`), translating on the fly.

## How to ask the steps

- **One step — one screen.** The question-choice tool (AskUserQuestion), up to 4 questions per screen, only if they are about the same thing.
- **Options, not open questions**, wherever possible. The person can always type their own answer.
- **"Skip →"** — the last option on every optional step. After a skip, say in one phrase which default was taken.
- **Back**: the person writes "back" or "step 4" — go back there, keep the other answers.
- Header of each step: `Step N of M · <name>`. M changes depending on the branch — recount it.
- After an answer — one line "Got it: …", no full recap.
- If the person is not at the screen (session with no answer) — do not wait: take the defaults and mark them in the summary.

## State

After each step — `run state.py --dir <folder> wizard step <step> --answer key=value …` (skip — `wizard skip <step>`). The script writes `prep/wizard.yaml`, writes the answers the profile needs straight into `prep/answers.yaml` too, and rebuilds the page. Everything is written to `prep/wizard.yaml` after every step, so the wizard can be interrupted and continued in another session. **After every write — `run build_page.py --dir <folder>`**: the page marks the completed step and highlights the current one. Step ids in `path` and `step`: `explain, goal, profile, resume, vacancy, company, basis, level, stack, language, weak, generate`.

```yaml
step: 6
path: [goal, profile, resume, vacancy, company, basis]   # completed steps
skipped: [company]
answers: { goal: vacancy, profile: backend, resume: uploaded, basis: [vacancy, resume] }
```

If `prep/wizard.yaml` already exists, the first screen is: "Continue from step N / Change one answer / Start over".

**Mode `edit`** (menu item "Change answers" or "English for the interview?"): ask a single step — the one in `args.question` (e.g. `english-train` → step 9), or ask with buttons which answer to change. Write it to `prep/answers.yaml` and `prep/wizard.yaml`, then act on the consequences: `english-train` became `full` → module `english`; the basis, level or stack changed → module `outline` (`mode: update`). Rebuild the page and return to the hub.

## Steps

### 0. Course languages — the first screen

Ask in the language the person wrote in. One AskUserQuestion question with **multiSelect: true**: "Which languages should the course be in? The first one you pick is the main one."

- the language the person writes in (Русский, Deutsch…) — first and with "(recommended)" if it is not English;
- "English" — first if the person writes in English;
- 1–2 more common languages;
- "Other" — free answer: the person types the language(s).

Say in one line under the question: every extra language means every lesson is written again in it — more time and tokens; one language is enough unless they really want to read in two.

`run state.py --dir <folder> wizard step explain --answer languages=<code>[,<code>…]` (ISO 639-1, main one first: `ru`, `ru,en`, `de,en`…). It also sets `explain-language` to the first code, writes both files and rebuilds the page. From this point on:

- the conversation, buttons and all wizard screens are in the main (first) language;
- materials: `content/<section>.<lang>.md` for **each chosen language and only for them**. One language — one file per section, nothing is duplicated;
- topic names in the outline: `title` in the main language, `title_<lang>` for each other chosen language (`title_en`, `title_de`…);
- the page: interface in the main language and a switch with one button per chosen language; one language — no switch;
- the page interface exists in Russian and English; for another main language: `run i18n.py --dir <folder> dump` → translate all strings, do not touch the keys → `run i18n.py --dir <folder> merge <file>`.

Change later: menu "Change answers" → this step. Adding a language means writing the missing files for it (module `build`); removing one leaves its files unused.

Person not at the screen — English only, noted in one line in the summary.

### 1. Goal

"Where do we start?"
- I have a specific job posting
- An interview is already scheduled → then a short branch: the deadline is tight, do not offer a resume or cover letter
- I'm job hunting, no posting yet → no steps 4–5, plan based on profile and resume
- Update my existing preparation → finish the wizard and return to the hub: the menu will offer what to update

### 2. Specialty

Options are non-abstract profiles (`run validate_profiles.py`, `title` from `profiles/*.yaml`). Currently: Backend developer. If nothing fits — say so plainly and offer the closest one.

### 3. Resume

Buttons:
- "I'll attach a file (recommended)" — PDF or DOCX via the paperclip → review (module `resume`, review): strengths, gaps, what to rephrase. Followed by the screen "Apply recommendations: all / I'll choose / not now".
- "I'll paste the text" — copy the resume straight into the message.
- "Create from scratch" → a series of guiding steps (module `resume`, create): roles and years, projects, personal contribution, numbers, stack. Only what the person said: embellish nothing — everything written will be asked about in the interview.
- "Skip" → I'll ask about experience along the way.

**Do not offer profile links.** LinkedIn forbids agents from reading its pages (robots.txt), and resumes on hh.ru are usually visible only to employers — the agent cannot open them. Instead of a link, explain how to get the file in 10 seconds:
- LinkedIn: your profile → "More" → "Save to PDF";
- hh.ru: your resume → «Скачать» (Download) → PDF or DOC;
- Google Docs: "File → Download → PDF", or a link with "anyone with the link" access.

If the person sends a link anyway — try to open it once. If it doesn't open → say why in one line and show the method above for that site. No workarounds (curl, caches, mirrors).

### 4. Job posting

- Paste text / link / just the company name
- Skip → plan covering the whole profile

If there is both a resume and a posting — show the comparison: what matches, what's missing, risks. This is the wizard's main screen: priorities come from it.

### 5. Company

"Create a company card in the "Interviews" section?" — Yes / Skip.
If yes: what has already happened (HR call, stages, salary range), which stages are ahead. Written to `prep/companies/<id>/company.yaml` (see module `track`).

### 6. Plan basis (multiple choice)

"What should the plan be built from?"
- For the job posting — the posting's requirements
- From my resume — review what's in my experience: that's what they'll ask about first
- The whole profile — everything usually asked for this role
- My weak spots — things I'll name myself

Default: posting + resume. The choice sets the topics' `origin` and their priority in the plan.

Right after that — the "Foundation" screen (module `outline`, step 2½): which theory to add for the stack — with buttons, the recommended one marked.

### 7. Level, timeline, stages

Position level (derived from the posting — show it and let the person correct it) and when the interview is — questions from the profile (`scope_questions`), ordered by `after`, conditions by `when`.

**Which stages there will be — not as a single question.** A question fits 4 buttons, but there are about ten stages, so a script assembles the questions:

```bash
run stage_question.py --profile <profile> --level <level> --dir <folder> [--known <stages from the posting and HR call>]   # --dir: labels in the explain-language
```

It returns 2–3 multiple-choice questions — "First stages" (screening, experience interview), "Technical" (technical, hands-on, design), "People and final" (behavioral, leadership, final). Show them on **one screen** (AskUserQuestion, `questions` as is). Stages that don't fit the level have already been removed by the script.

Answer → `stages_off` in the questionnaire, using the `map` from the script's output:
- group answered → the unchecked stages in it are turned off;
- group skipped ("Skip") → "don't know", all its stages stay;
- stages from `always` (preparation, offer) are always on.

Confirm in one line: "Preparing you for: screening, technical, live coding, system design, behavioral, final."

### 8. Stack

Specialty questions from the profile: language, frameworks, databases, brokers, infrastructure, algorithms. First infer from the resume and posting and show "here's what I understood"; ask only for what's missing.

### 9. English — always ask

If the main language is English, do not ask `english-train`: everything is already in English, there is nothing to translate the vocabulary into. Write `english-train: texts` if the interview is in English and the person wants to rehearse answers, otherwise `no`. Ask only the interview-language question.

The step is mandatory even if the interview is in the native language: English is needed for future interviews, correspondence and documentation. It cannot be skipped — only answered "No".

Screen 1 (one AskUserQuestion, two questions):
- "What language is the interview in?" — native / English / other (if clear from the posting — preselect it and say where it came from).
- "Brush up English for the interview?" (`english-train`). If English is not among the course languages, say in the option text that this adds short English versions of the lessons (needed for the vocabulary):
  - "Yes — vocabulary from my stories, plus the trainer" — first and with "(recommended)" if the interview is in English;
  - "Only my answers and stories in English" — no vocabulary;
  - "No, not needed" — first if the interview is in the native language and the posting has no English.

If "Yes" or "Only answers" — screen 2: level (`english-level`: A2 / B1 / B2 / C1) and "what to prepare" (multiple choice, preselected by the answer):
- My answers and stories in English
- Materials in two languages with a switch
- Vocabulary: every word I'll need at the interview, minus the ones I already know (only for "Yes")
- Interview phrases: asking to repeat, taking a pause, disagreeing

Explain in one line how the vocabulary will be built, so the person doesn't expect a "top-1000 words" list: "I'll count which words appear most often in your stories, topics and the job posting, and take the top of that list. On the page you'll mark what you already know — only new words go to the trainer, from most to least important: there's little time before the interview, so we learn from the top." Method — module `english`, steps 2–3.

Answers → `answers.english-train`, `answers.english-level`. `english-train` determines the "Interview language" section in the plan and the "Vocabulary"/"Trainer" tabs on the page.

### 10. Weak spots and exclusions

Two open fields, both can be skipped.

### 11. What to generate (multiple choice)

Preselected based on the answers:
- Preparation page with the plan and materials
- Materials in English (+ RU/EN switch)
- Vocabulary (only words new to you) and the trainer — if step 9 was "Yes"
- Resume tailored to the job posting
- Cover letter
- "Interviews" section on the page

### 12. Summary → Generate

A summary of all answers on one screen, skipped ones shown with their default. Options: "Generate" / "Change step…". Only after "Generate" — launch:

```
module `resume` (if selected) → module `scope` (write answers.yaml from wizard.yaml)
→ module `outline` → module `build` → module `english` (if `english-train` is not `no`) → module `track` (if a company)
```

During generation keep a task list with the stages and deliver results as they are ready: first the page with the plan, then the materials.

## YAML rules

All files in `prep/` are written in **block style**; any strings containing `,` `:` `?` `#` go in quotes. Single-line `{ ... }` only for short values without punctuation: otherwise YAML silently cuts the string. After writing — `run validate_content.py --dir .`.
