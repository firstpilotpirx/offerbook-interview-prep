#!/usr/bin/env bash
# Installs the offerbook-interview-prep (Offerbook) plugin into Claude Code. Run by the agent; the person doesn't need to do anything.
#
#   bash install.sh
#
# Steps (safe to re-run):
#   1. registers this folder as the offerbook marketplace (or updates it);
#   2. installs the offerbook-interview-prep@offerbook plugin for the user;
#   3. prepares the Python environment with all dependencies (tools/run --check).
#
# Exit codes:
#   5 — the `claude` CLI is missing (PREP_NEEDS_CLAUDE_CLI)
#   3 / 4 — from tools/run: no Python / dependencies failed to install
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
say(){ printf '• %s\n' "$*"; }

command -v claude >/dev/null 2>&1 || { echo "PREP_NEEDS_CLAUDE_CLI: claude not found in PATH" >&2; exit 5; }

if claude plugin marketplace list 2>/dev/null | grep -q "offerbook"; then
  say "marketplace offerbook already exists — updating"
  claude plugin marketplace update offerbook >/dev/null
else
  say "adding marketplace offerbook"
  claude plugin marketplace add "$ROOT" >/dev/null
fi

# old plugin name (before 0.11 — prep@prep-local): disable and remove it; prep data is not touched
if claude plugin list 2>/dev/null | grep -q "prep@prep-local"; then
  say "removing the old version named prep — your data stays where it is"
  claude plugin uninstall prep@prep-local >/dev/null 2>&1 || claude plugin disable prep@prep-local >/dev/null 2>&1 || true
fi
# interim name in 0.11 (offerbook-interview-prep@offerbook-local)
if claude plugin marketplace list 2>/dev/null | grep -qw "offerbook-local"; then
  claude plugin marketplace remove offerbook-local >/dev/null 2>&1 || true
fi
if claude plugin marketplace list 2>/dev/null | grep -qw "prep-local"; then
  claude plugin marketplace remove prep-local >/dev/null 2>&1 || true
fi

if claude plugin list 2>/dev/null | grep -q "offerbook-interview-prep@offerbook"; then
  say "plugin offerbook-interview-prep is already installed"
  claude plugin enable offerbook-interview-prep@offerbook >/dev/null 2>&1 || true
else
  say "installing plugin offerbook-interview-prep"
  claude plugin install offerbook-interview-prep@offerbook >/dev/null
fi

say "preparing the Python environment"
bash "$ROOT/tools/run" --check >/dev/null

say "done: /offerbook-start and /offerbook-next will appear in a new session or after /reload-plugins"
echo "PREP_INSTALLED root=$ROOT"
