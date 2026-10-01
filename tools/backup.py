#!/usr/bin/env python3
"""Backup and restore of the preparation — before an upgrade and on request.

    run backup.py --dir . create [--reason upgrade-0.9.0]   # → prep/backups/<time>-<reason>.zip
    run backup.py --dir . list
    run backup.py --dir . verify <file>                      # does it open, what is inside
    run backup.py --dir . restore <file>                     # backs up the current state first

The backup includes everything the person did: prep/ (questionnaire, plan, page marks,
trainer and vocabulary state, companies, resumes, letters) and content/
(materials). Excluded: dist/ (rebuilt), prep/backups/, .serve.json.

Inside the zip is manifest.json with progress counters. migrate.py uses it
to verify that nothing was lost after an upgrade.
The last 20 backups are kept.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path

KEEP = 20
SKIP_NAMES = {".serve.json"}


def plugin_version() -> str:
    p = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("version", "?")
    except Exception:
        return "?"


def _json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception:
        return default


def counts(root: Path) -> dict:
    """Progress counters — what must not be lost."""
    prep = root / "prep"
    st = _json(prep / "page-state.json", {}) or {}
    tr = _json(prep / "trainer-state.json", {}) or {}
    tr_items = tr.get("items", tr) if isinstance(tr, dict) else {}
    vs = _json(prep / "vocab-state.json", {}) or {}
    vocab_ids = set()
    for rec in (vs.values() if isinstance(vs, dict) else []):
        if isinstance(rec, dict) and not rec.get("reset"):
            vocab_ids |= set(rec.get("known") or []) | set(rec.get("unknown") or [])
    blocks = 0
    for f in (root / "content").glob("*.md") if (root / "content").exists() else []:
        blocks += len(re.findall(r"^@@\s+\S+", f.read_text(encoding="utf-8"), re.M))
    words = 0
    wp = prep / "words.yaml"
    if wp.exists():
        words = len(re.findall(r"^\s*-\s+id:\s*[\"']?[wvpa]:", wp.read_text(encoding="utf-8"), re.M))
    return {
        "done": len((st.get("done") or {})), "skip": len((st.get("skip") or {})),
        "trainer": len(tr_items) if isinstance(tr_items, dict) else 0,
        "vocab_checked": len(vocab_ids), "content_blocks": blocks, "cards": words,
        "companies": len(list((prep / "companies").glob("*/company.yaml"))) if (prep / "companies").exists() else 0,
        "inbox": len(_json(prep / "inbox.json", []) or []),
    }


def files(root: Path):
    for base in ("prep", "content"):
        d = root / base
        if not d.exists():
            continue
        for f in sorted(d.rglob("*")):
            rel = f.relative_to(root)
            if f.is_file() and rel.parts[:2] != ("prep", "backups") and f.name not in SKIP_NAMES:
                yield f, rel


def create(root: Path, reason: str = "manual") -> Path:
    out_dir = root / "prep" / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = out_dir / f"{stamp}-{re.sub(r'[^0-9A-Za-z._-]+', '-', reason)}.zip"
    session = {}
    try:
        import yaml
        sp = root / "prep" / "session.yaml"
        session = (yaml.safe_load(sp.read_text(encoding="utf-8")) or {}) if sp.exists() else {}
    except Exception:
        pass
    manifest = {"created": dt.datetime.now().isoformat(timespec="seconds"), "reason": reason,
                "plugin_version": plugin_version(), "data_version": session.get("data_version"),
                "from_plugin_version": session.get("plugin_version"), "counts": counts(root), "files": 0}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        n = 0
        for f, rel in files(root):
            z.write(f, rel.as_posix()); n += 1
        manifest["files"] = n
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    # check: the zip opens and has the same number of files
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None or len(z.namelist()) != manifest["files"] + 1:
            sys.exit(f"! backup {path} is corrupted — do not continue the upgrade")
    backups = sorted(out_dir.glob("*.zip"))
    for old in backups[:-KEEP]:
        old.unlink()
    return path


def read_manifest(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read("manifest.json"))


def restore(root: Path, path: Path) -> Path:
    safety = create(root, "before-restore")
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n != "manifest.json"]
        for n in names:
            if n.startswith("/") or ".." in Path(n).parts or not n.startswith(("prep/", "content/")):
                sys.exit(f"! suspicious path in backup: {n}")
        # files that were not in the backup are not deleted — moved to prep/backups/_after-restore
        current = {rel.as_posix() for _, rel in files(root)}
        extra = current - set(names)
        if extra:
            park = root / "prep" / "backups" / f"_after-restore-{dt.datetime.now():%Y%m%d%H%M%S}"
            for n in extra:
                dst = park / n
                dst.parent.mkdir(parents=True, exist_ok=True)
                (root / n).replace(dst)
        for n in names:
            dst = root / n
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(z.read(n))
    return safety


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("--reason", default="manual")
    sub.add_parser("list")
    v = sub.add_parser("verify"); v.add_argument("file")
    r = sub.add_parser("restore"); r.add_argument("file")
    sub.add_parser("counts")
    args = ap.parse_args()
    root = Path(args.dir).expanduser()

    if args.cmd == "create":
        p = create(root, args.reason)
        m = read_manifest(p)
        print(json.dumps({"backup": str(p), **m}, ensure_ascii=False) if args.json else
              f"BACKUP {p}\n  files {m['files']}, progress: {m['counts']}")
    elif args.cmd == "list":
        rows = []
        for p in sorted((root / "prep" / "backups").glob("*.zip"), reverse=True):
            try:
                m = read_manifest(p)
            except Exception:
                m = {"broken": True}
            rows.append({"file": str(p), **m})
        if args.json:
            print(json.dumps(rows, ensure_ascii=False))
        else:
            for r_ in rows:
                print(f"{Path(r_['file']).name}  v{r_.get('plugin_version')}  {r_.get('reason')}  {r_.get('counts')}")
    elif args.cmd == "verify":
        m = read_manifest(Path(args.file))
        print(json.dumps(m, ensure_ascii=False, indent=1))
    elif args.cmd == "restore":
        safety = restore(root, Path(args.file))
        print(f"RESTORED {args.file}\n  state before restore saved to: {safety}\n  progress: {counts(root)}")
    elif args.cmd == "counts":
        print(json.dumps(counts(root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
