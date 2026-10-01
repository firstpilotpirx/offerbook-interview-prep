---
name: offerbook-next
description: Shows the next interview-preparation step with buttons — what matters most right now and what else can be done. Use when the person returns to their preparation and says "what's next", "let's continue", "where did we stop", "where to now".
---

# /offerbook-next — what's next

A short entry into the preparation hub. All the logic is in [../offerbook-start/SKILL.md](../offerbook-start/SKILL.md); this is just the entry point.

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/offerbook-start/SKILL.md`.
2. Start right at hub step 2 (syncing with the page), then step 3 — the menu with buttons.
3. Take the preparation folder from `prep/session.yaml`. If it does not exist, this is the first run: act as `/offerbook-start` from step 1.
4. Then the usual hub loop: action → summary → menu again.

No greetings or recaps: one status line and the buttons.
