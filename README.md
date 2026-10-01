# Offerbook — interview prep from resume to job offer

**Offerbook** (`offerbook-interview-prep`) is a personal interview-prep textbook for Claude. It builds a study plan from your resume and the vacancy, writes deep lessons retold from classic books (DDIA, Fowler, Evans) and system design practice with back-of-envelope estimates, trains the English vocabulary that comes from your own interview stories, tailors your resume and cover letters, and tracks your interviews per company — all on one live page with progress. The course is written in the languages you pick at the start — one or several (English by default); one language means no duplicate texts.

## Features

- **Guided start.** One command, `/offerbook-start`, walks you through a short wizard: explanation language, goal, specialty, resume, vacancy, level, deadline, interview stages, stack, weak spots. After every step it offers the next one as buttons — nothing to memorize.
- **A plan that subtracts what you already know.** Topics come from your resume, the vacancy and the specialty profile, ranked by priority. You strike out what you know or don't need; progress is counted only on what is left.
- **Deep lessons.** Each topic gets a lesson in a fixed structure (in short / how it works / where it breaks / interview Q&A / check yourself / sources), retold from classic sources such as *Designing Data-Intensive Applications*, Fowler and Evans, with depth scaled by priority.
- **Fact-checked lessons.** Every lesson and system design case is checked claim by claim against primary sources — the documentation of your versions, RFCs, book chapters — by a separate agent where possible. Sources link to the exact sections; anything that could not be confirmed is marked ⚠ on the page, and each lesson shows whether and when it was checked.
- **System design practice.** Each case is a plan for the conversation, not a worked answer: functional and non-functional requirements, what to ask the interviewer and how to lead the talk, what to watch for in the implementation — plus a fundamentals section picked for your stack.
- **Your stories and answers.** STAR stories from your own experience and ready-to-say answers ("tell me about yourself", "why are you leaving", salary expectations).
- **English trainer built from your own material.** Frequency analysis of your lessons, stories and answers; quick "check what you know" rounds by frequency band; a spaced-repetition trainer that asks every word four ways (pick the English, pick the translation, recall the English, recall the translation); the most important words come first, in decks of 50.
- **Resume and cover letters.** A one-column A4 resume in HTML, Markdown and PDF, a lint check against the vacancy, and a tailored resume and cover letter per company.
- **Interview tracker.** Companies, stage timelines, HR conversations, post-interview debriefs. Topics where you struggled go back up in the plan.
- **Study tracks with daily goals.** Theory, coding problems, system design, soft skills and words — each with a ring for today, the week, its own daily goal and a forecast; the plan shows the date you are ready by the slowest track.
- **One live page.** Plan tree with progress bars on every node, filters, table of contents, vocabulary, trainer and interviews — rebuilt as you go, with your marks kept across rebuilds and plugin updates.

## Install

### Claude app (chat / Cowork) — no terminal

1. Open **[Customize → Plugins](https://claude.ai/customize/plugins)** → **Add** → **Add marketplace**.
2. Paste `firstpilotpirx/offerbook-interview-prep` (or the full GitHub link) and confirm.
3. Find **Offerbook** in **Discover** and install it.
4. In a new chat type `/offerbook-start`.

Updates: **Manage plugins** → the `offerbook` marketplace → **Check for updates**, or turn on **Sync automatically**. Then run `/offerbook-update` — your prep data is kept.

No GitHub access? Download `offerbook-interview-prep.zip` from the latest [release](https://github.com/firstpilotpirx/offerbook-interview-prep/releases/latest) and use **Customize → Plugins → Add → Upload plugin**.

### Claude Code — inside a session (desktop app, VS Code, JetBrains or the CLI)

Type in the chat:

```
/plugin marketplace add firstpilotpirx/offerbook-interview-prep
/plugin install offerbook-interview-prep@offerbook
```

Update later: `/plugin marketplace update offerbook`, then `/offerbook-update`.

### Claude Code — from a shell

```bash
claude plugin marketplace add firstpilotpirx/offerbook-interview-prep
claude plugin install offerbook-interview-prep@offerbook
# update later
claude plugin marketplace update offerbook
claude plugin update offerbook-interview-prep@offerbook
```

From a local clone you can also just tell Claude Code *"install the interview prep plugin from ~/path/to/offerbook-interview-prep"*: it runs `install.sh`, which registers the folder as the `offerbook` marketplace, installs the plugin, prepares the Python environment and starts the wizard.

### Share it with someone

Send them the repository link: <https://github.com/firstpilotpirx/offerbook-interview-prep>. In the Claude app they add it as a marketplace (above); in Claude Code they type the two `/plugin` lines. The plugin sets up its Python environment on first run.

### Commands

| Command | What it does |
|---|---|
| `/offerbook-start` | main entry: the wizard on first run, then the "what next" menu |
| `/offerbook-next` | straight to the menu — "where did we stop?" |
| `/offerbook-update` | move your prep to a new plugin version |

In Claude Code the commands are namespaced: `/offerbook-interview-prep:offerbook-start`, `/offerbook-interview-prep:offerbook-next`, `/offerbook-interview-prep:offerbook-update`. You can also just say "let's prepare for an interview" or "what's next with my prep".

## What this plugin runs and stores

- **Bundled scripts.** All data operations are done by the Python scripts in `tools/`, started through `bash tools/run <script>`. Claude runs them with your permission in the usual tool-approval flow.
- **Python environment.** On first run, `tools/run` creates a virtualenv at `~/.local/share/prep-interview/venv` (override with `PREP_VENV`) — with `uv` if it is installed, otherwise with `python -m venv` — and installs the pinned packages listed in [`tools/requirements.txt`](tools/requirements.txt) from PyPI: `pyyaml`, `jsonschema`, `wordfreq`, `simplemma`, `pymorphy3`, `markdown`, `jinja2`. It reinstalls only when that file changes. The environment lives outside the plugin folder and survives plugin updates.
- **Optional PDF support.** Only if you ask for a PDF resume: `tools/run --setup-pdf` installs `playwright==1.55.0` into the same virtualenv and downloads Chromium (about 150 MB) through Playwright.
- **Optional local web server.** In Claude Code, `tools/serve.py` serves your prep page and saves your marks, vocabulary checks, trainer progress and interview notes to files in your prep folder. It binds to `127.0.0.1` only and accepts requests from localhost only.
- **Where your data lives.** Everything you enter or generate — resume, wizard answers, plan, lessons, progress, vocabulary, companies — is stored locally in your prep folder (`~/interview-prep` by default; `prep/`, `content/`, `dist/`). In chat mode, without a local folder, the page is published as a private Claude artifact and progress is kept in that artifact's own storage.
- **Backups.** Before every update your prep data is copied to `prep/backups` inside the prep folder; you can roll back with one command.
- **No third parties, no telemetry.** The plugin itself sends nothing to any third-party service and collects no analytics. Web lookups (for example, reading a vacancy link or checking a fact) happen only through Claude's own tools, when you ask for them.

## Updating

Run `/offerbook-update` (or say "update the page" / "what's new"). It shows what changed since your version (from [`CHANGELOG.yaml`](CHANGELOG.yaml)), makes a backup in `prep/backups`, migrates your data to the current format without losing progress, rebuilds the page, and offers any new sections or questions. If anything doesn't match after migration, it rolls back automatically; you can also ask to restore a backup yourself.

## Repository layout

```
.claude-plugin/          plugin.json, marketplace.json
skills/
  offerbook-start/       /offerbook-start — the hub: offers the next step as buttons after every step
    SKILL.md
    modules/             wizard · resume · scope · outline · build · english · track · upgrade
    references/          page-format · material-format · trainer-format · cv-format
  offerbook-next/        /offerbook-next — short "what next?" entry, straight to the hub menu
  offerbook-update/      /offerbook-update — new version: what's new, backup, migration, rollback
profiles/                specialty profiles (base → backend), stable topic ids, renames
schemas/                 words, company and cv JSON schemas
templates/
  portal/                the page: template.html, page.css, page.js, i18n.json — built into one file
  lesson/                skeletons for lessons, cases, stories and answers per language
  cv/cv.html             one-column A4 resume
tools/
  run                    runs any script; creates the Python environment on first call
  next_steps.py          hub menu computed from your prep files
  build_page.py          builds the page from prep/ and content/
  serve.py               local page server (localhost only)
  build_cv.py, cv_lint.py            resume: HTML / PDF / Markdown, check against the vacancy
  rank_words.py, words.py            vocabulary candidates and deck
  migrate.py, backup.py, whats_new.py  updates without losing progress
  validate_profiles.py, validate_content.py, check_rules.py, check_all.sh  checks
examples/sample/         sample prep folder (also the test fixture)
docs/                    user journey, architecture, profile format
CHANGELOG.yaml           what's new per version + migration actions
```

More detail: [user journey](docs/user-journey.md), [architecture and design history](docs/architecture.md), [profile format](docs/profiles.md).

## Development

- Run `bash tools/check_all.sh` after any change to templates, schemas, profiles or scripts. It runs every check and build on `examples/sample`, plus `tools/check_rules.py` (scripts referenced in instructions exist, every script is documented, links resolve, ru/en UI strings match, CHANGELOG version matches `plugin.json`).
- Run `claude plugin validate .` to check the plugin and marketplace manifests.
- Principle: **anything a script can do is done by a script.** Skills decide what to write; page look, resume layout, word ranking, data writes and checks live in `templates/` and `tools/`.
- New specialties go in `profiles/` (start from `profiles/_template.yaml`); topic ids are stable, renames go to `profiles/_renames.yaml`. Backend is the first profile; QA, frontend and analyst come later.
- Every release adds an entry at the top of `CHANGELOG.yaml` (notes in ru and en, plus `actions` for the update flow) and, if the data format changes, a step in `tools/migrate.py`. See [CLAUDE.md](CLAUDE.md) for the full rules.

### Releasing

1. Describe the new version at the top of `CHANGELOG.yaml` (if you skip it, the script writes an entry from the commit subjects; if an unreleased entry is already on top, it tells you to release exactly that version).
2. Run `bash tools/release.sh patch` (or `minor`, `major`, or an exact `X.Y.Z`; add `--no-push` to skip the push).

The script bumps the version, runs all checks (and rolls the version back if they fail), builds `dist/offerbook-interview-prep.zip`, commits, tags `vX.Y.Z`, pushes and publishes a GitHub release with the notes and the zip. The release needs the [`gh`](https://cli.github.com/) CLI (`brew install gh && gh auth login`); `bash tools/release.sh github` republishes the release for the current version.

Commits are public: before the first push set a private author email for this repository — `git config user.email "<id>+<login>@users.noreply.github.com"` (GitHub → Settings → Emails).

## License

[MIT](LICENSE)
