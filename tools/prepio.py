"""Shared I/O for preparation files — so that all scripts write the same way.

- YAML in block style only, strings with ": , # ?" are quoted (yaml.safe_dump does it),
  keys in original order. Hand-written YAML by the agent caused past errors
  (silently split strings, yes/no as booleans), so prep/ files are written by scripts.
- Writes are atomic: to a temporary file alongside, then replace.
- Schema validation (schemas/*.json) if a schema exists: on error the file is not changed.
- Command-line values: `k=v`; v is parsed as JSON if it looks like JSON
  (numbers, true/false, [lists], {objects}), otherwise a string. `k=` deletes the key.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SCHEMAS = REPO / "schemas"


class Fail(SystemExit):
    pass


def read_yaml(p: Path, default=None):
    if not p.exists():
        return default
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return default if data is None else data


def read_json(p: Path, default=None):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Fail(f"! {p}: not JSON ({e})")


def _atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, p)


def _plain(o):
    """date → str etc., so that the schema and JSON see the same as the file."""
    return json.loads(json.dumps(o, default=str, ensure_ascii=False))


def validate(data, schema_name: str | None, where: str = "") -> None:
    if not schema_name:
        return
    sp = SCHEMAS / schema_name
    if not sp.exists():
        return
    import jsonschema
    schema = json.loads(sp.read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(_plain(data)), key=lambda e: list(e.path))
    if errs:
        lines = [f"  {'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in errs[:10]]
        raise Fail(f"! {where or schema_name}: fails the schema, file not changed\n" + "\n".join(lines))


def write_yaml(p: Path, data, schema: str | None = None) -> None:
    validate(data, schema, str(p))
    _atomic(p, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120, default_flow_style=False))


def write_json(p: Path, data) -> None:
    _atomic(p, json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def parse_value(v: str):
    v = v.strip()
    if v == "":
        return None
    if re.fullmatch(r"-?\d+(\.\d+)?|true|false|null|\[.*\]|\{.*\}|\".*\"", v, re.S):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            pass
    return v


def parse_pairs(pairs: list[str]) -> dict:
    out = {}
    for p in pairs:
        if "=" not in p:
            raise Fail(f"! expected key=value: {p}")
        k, _, v = p.partition("=")
        out[k.strip()] = parse_value(v)
    return out


def apply(d: dict, pairs: dict) -> dict:
    for k, v in pairs.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    return d


def slug(s: str) -> str:
    s = s.lower().replace("ё", "е")
    tr = str.maketrans("абвгдежзийклмнопрстуфхцчшщъыьэюя",
                       "abvgdezziiklmnoprstufhccss_y_eua")
    s = s.translate(tr)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def rebuild(root: Path) -> None:
    """Rebuild the page after writing (hub rule: after every step)."""
    import subprocess
    import sys
    subprocess.run([sys.executable, str(REPO / "tools" / "build_page.py"), "--dir", str(root)],
                   check=False, stdout=subprocess.DEVNULL)
