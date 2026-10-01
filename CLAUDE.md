# Offerbook plugin (offerbook-interview-prep) — instructions for the agent

This is a Claude Code plugin for interview preparation. The person should not have to do anything by hand: you install and run everything.

## If the person asks to install or try the plugin

1. Run `bash install.sh` in the root of this folder. It will:
   add the `offerbook` marketplace, install the `offerbook-interview-prep@offerbook` plugin, and prepare the Python environment.
2. By exit code:
   - `0` and the line `PREP_INSTALLED root=…` — done;
   - `5` — the `claude` CLI is missing: offer, as buttons, to install it following https://code.claude.com/docs/en/setup, then retry;
   - `3` — Python is missing: offer, as buttons, to install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`, it downloads Python itself) or `brew install python@3.12`, then retry;
   - `4` — dependencies failed to install: show the tail of the error and offer to retry.
3. **Do not ask the person to restart the session.** Immediately read `skills/offerbook-start/SKILL.md` and start the hub from step 0, substituting the root from `PREP_INSTALLED root=…` for `${CLAUDE_PLUGIN_ROOT}`. In later sessions: `/offerbook-start` and `/offerbook-next` in chat (in Claude Code — `/offerbook-interview-prep:offerbook-start`, `/offerbook-interview-prep:offerbook-next`).

## If the person is editing the plugin itself

- After changes: `bash tools/check_all.sh` — all checks and builds on `examples/sample`, plus `tools/check_rules.py`: scripts referenced in instructions exist, every script is described in the instructions, links resolve, ru/en UI strings match, the version in CHANGELOG matches.
- A new operation on data means a new script subcommand and a row in the "data is written only by scripts" table (skills/offerbook-start/SKILL.md), not an instruction like "write it to the YAML".
- Page UI strings go in `templates/portal/i18n.json`, not in the template.
- `claude plugin validate .` — checks the plugin and marketplace manifests.
- Changes are picked up in sessions after `/reload-plugins` (the marketplace is local, files are read straight from here).
- Page look lives only in `templates/portal/` (`template.html` skeleton, `page.css`, `page.js`, `i18n.json`), lesson skeletons in `templates/lesson/skeletons.yaml`, the resume in `templates/cv/cv.html`. Do not copy templates for a single person.
- Every release: a new entry at the top of `CHANGELOG.yaml` with the same version as `.claude-plugin/plugin.json` (notes in ru and en, `actions` for the upgrade module); if the data format changes, bump `data_version` and add a step in `tools/migrate.py`. Topic id renames in profiles go to `profiles/_renames.yaml` — never delete entries there.
