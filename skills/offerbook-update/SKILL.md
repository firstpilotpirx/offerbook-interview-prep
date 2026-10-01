---
name: offerbook-update
description: Updates the interview preparation to a new plugin version — shows what's new, makes a backup, migrates data and progress, rebuilds the page and offers new sections. Use when the person says "update", "update the page", "what's new", "the plugin was updated", "put it back as it was", "roll back", or the hub offered an update.
---

# /offerbook-update — updating without losing progress

Entry into the `upgrade` module of the preparation hub.

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/offerbook-start/SKILL.md` (common rules: running scripts via `run`, buttons, language) and `${CLAUDE_PLUGIN_ROOT}/skills/offerbook-start/modules/upgrade.md`.
2. Take the preparation folder from `prep/session.yaml` (as in hub step 1). No preparation — nothing to update: offer `/offerbook-start`.
3. Run the `upgrade` module step by step. Afterwards — the hub menu (step 3).
