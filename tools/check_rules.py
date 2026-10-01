#!/usr/bin/env python3
"""Plugin self-check: rules, scripts and templates are consistent with each other.

    python3 tools/check_rules.py        # from the plugin root; part of tools/check_all.sh

Checks:
1. every `run X.py` and `tools/X.py` from the instructions (skills/**/*.md, docs, README) exists;
2. every tools/*.py script is mentioned in at least one instruction — so the agent knows about it
   (except the helper modules prepio, langs);
3. relative links in markdown point to existing files;
4. modules: hub table ↔ modules/*.md files ↔ module in next_steps.py;
5. interface strings: ru and en have the same keys; every L().key from the template exists in en;
6. version: top of CHANGELOG.yaml = plugin.json; top data_version = migrate.DATA_VERSION;
7. skills: name in frontmatter = folder name, description present.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HELPERS = {"prepio", "langs"}
errors: list[str] = []


def err(msg):
    errors.append(msg)


def docs():
    for pat in ("skills/**/*.md", "docs/*.md", "README.md", "CLAUDE.md"):
        yield from ROOT.glob(pat)


def main() -> int:
    tools = {p.stem for p in (ROOT / "tools").glob("*.py")}
    mentioned = set()
    for f in docs():
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r"(?:run|tools/)\s*([a-z0-9_]+)\.py", t):
            name = m.group(1)
            mentioned.add(name)
            if name not in tools:
                err(f"{f.relative_to(ROOT)}: script {name}.py is not in tools/")
        for m in re.finditer(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", t):
            target = m.group(1)
            if re.match(r"[a-z]+://|mailto:", target) or "${" in target or "<" in target:
                continue
            if not (f.parent / target).resolve().exists():
                err(f"{f.relative_to(ROOT)}: link to non-existent {target}")
    for t_ in sorted(tools - mentioned - HELPERS):
        err(f"tools/{t_}.py: not mentioned in any instruction — the agent will not know about it")

    hub = (ROOT / "skills/offerbook-start/SKILL.md").read_text(encoding="utf-8")
    table = set(re.findall(r"^\| ([a-z]+) \|", hub, re.M)) - {"module"}
    files = {p.stem for p in (ROOT / "skills/offerbook-start/modules").glob("*.md")}
    for m in sorted(table - files):
        err(f"hub: module {m} is in the table, but modules/{m}.md does not exist")
    for m in sorted(files - table):
        err(f"modules/{m}.md: not in the hub module table")
    ns = (ROOT / "tools/next_steps.py").read_text(encoding="utf-8")
    for m in sorted(set(re.findall(r'add\([^,]+,[^,]+,[^,]+,\s*"([a-z]+)"', ns)) - files):
        err(f"next_steps.py: a menu item leads to module {m}, but the file does not exist")

    ui = json.loads((ROOT / "templates/portal/i18n.json").read_text(encoding="utf-8"))
    if set(ui["ru"]) != set(ui["en"]):
        err(f"i18n.json: ru and en keys differ: {sorted(set(ui['ru']) ^ set(ui['en']))[:10]}")
    tpl = (ROOT / "templates/portal/page.js").read_text(encoding="utf-8")
    for k in sorted(set(re.findall(r"L\(\)\.([A-Za-z0-9_]+)", tpl)) - set(ui["en"])):
        err(f"page.js: string L().{k} not found in i18n.json")
    for k in sorted(set(re.findall(r"L\(\)\['([A-Za-z0-9_]+)'\]", tpl)) - set(ui["en"])):
        err(f"page.js: string L()['{k}'] not found in i18n.json")

    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
    log = yaml.safe_load((ROOT / "CHANGELOG.yaml").read_text(encoding="utf-8")) or []
    if not log or log[0]["version"] != plugin:
        err(f"CHANGELOG.yaml: top version {log[0]['version'] if log else '—'}, but plugin.json {plugin}")
    sys.path.insert(0, str(ROOT / "tools"))
    import migrate
    if log and log[0].get("data_version") != migrate.DATA_VERSION:
        err(f"CHANGELOG.yaml: data_version {log[0].get('data_version')} ≠ migrate.DATA_VERSION {migrate.DATA_VERSION}")

    for sk in (ROOT / "skills").glob("*/SKILL.md"):
        fm = re.match(r"---\n(.*?)\n---", sk.read_text(encoding="utf-8"), re.S)
        meta = yaml.safe_load(fm.group(1)) if fm else {}
        if meta.get("name") != sk.parent.name:
            err(f"{sk.relative_to(ROOT)}: name {meta.get('name')} ≠ folder {sk.parent.name}")
        if not meta.get("description"):
            err(f"{sk.relative_to(ROOT)}: no description")

    for e in errors:
        print("✗", e)
    print(f"Rules: {'no errors' if not errors else f'{len(errors)} errors'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
