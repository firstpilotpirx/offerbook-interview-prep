#!/usr/bin/env python3
"""Vocabulary candidates from the person's own materials.

Words come ONLY from what will be useful in this interview: English versions of
one's own answers and stories (the person says them), plan topics and vacancy text
(the interviewer says them). There are no generic "top-1000 words" lists.

    run rank_words.py content/ prep/companies/ --level b2 \
        --weight stories=3 --weight answers=3 --weight vacancy=2 \
        --keep prep/must-terms.txt --out prep/word-candidates.yaml

Frequency-based selection method (details: modules/english.md, step 2):
1. Lemma: provided/provides → provide. Code in `...` and ```...``` is not counted.
2. Names and products are dropped: a word that is always capitalized and rare
   in English (Kafka, Grafana, Acme). Terms one must be able to say are
   listed in --keep.
3. Basic words are cut by English frequency (wordfreq, zipf scale:
   7 — the, 5 — provide, 4 — throughput, 3 — idempotent). The threshold depends
   on level: --level a2 → 6.3, b1 → 5.8, b2 → 5.3, c1 → 4.8 (or --basic).
4. Importance = weighted number of occurrences in one's own corpus; ties go to
   the word more common in English overall (more useful).
5. Each word gets a frequency band (band 1…4) for a quick "I know these" check
   on the page: 10 words per band, knows ≥ 9 → the whole band is known.

Source weight: by substring match in the file path (stories=3 → files with
"stories" in the path weigh ×3). One's own stories and answers matter more than
technical materials: the person says them out loud.

Output: candidates with frequencies and places of use (topic ids from @@ blocks).
Translation, examples and groups are added by the skill's `english` module, then
the person marks what they know on the vocabulary check page.

Dependencies: wordfreq, simplemma, pyyaml.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import simplemma
    import yaml
    from wordfreq import zipf_frequency
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency: {e.name}. pip install -r tools/requirements.txt")

BLOCK = re.compile(r"^@@\s+([a-z][\w.-]*)\s*$", re.M)
TOKEN = re.compile(r"[A-Za-z][A-Za-z'-]*[A-Za-z]|[A-Za-z]")
CODE = re.compile(r"```.*?```|`[^`]*`", re.S)
PARTICLES = {"up", "out", "off", "down", "over", "into", "back", "through", "away", "on", "with"}


LEVEL_CUT = {"a2": 6.3, "b1": 5.8, "b2": 5.3, "c1": 4.8}


def band(z: float) -> int:
    """Frequency band: 1 is the most common (zipf ≥ 5), 4 is rare words and terms (< 3)."""
    return 1 if z >= 5 else 2 if z >= 4 else 3 if z >= 3 else 4


def files(paths: list[str]) -> list[Path]:
    out = []
    for p in map(Path, paths):
        if p.is_dir():
            # English text only: *.en.md and files without a language suffix (vacancy.md)
            out += sorted(x for x in p.rglob("*.md")
                          if (x.name.endswith(".en.md") or not re.search(r"\.[a-z]{2}\.md$", x.name))
                          and not x.name.startswith("cover."))
        elif p.exists():
            out.append(p)
        else:
            print(f"! no such file: {p}", file=sys.stderr)
    return out


def blocks(text: str, fallback: str):
    """Split a file into @@ blocks: (topic id, text)."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    parts = BLOCK.split(text)
    if len(parts) == 1:
        yield fallback, text
        return
    if parts[0].strip():
        yield fallback, parts[0]
    for i in range(1, len(parts), 2):
        yield parts[i], parts[i + 1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--weight", action="append", default=[], metavar="SUBSTR=N")
    ap.add_argument("--level", choices=sorted(LEVEL_CUT), help="English level → basic-word threshold")
    ap.add_argument("--basic", type=float, help="drop words with zipf above this (default: from --level, else 6.0)")
    ap.add_argument("--min-count", type=int, default=1)
    ap.add_argument("--keep", default="", help="file with terms to always include (one per line)")
    ap.add_argument("--out", default="-")
    args = ap.parse_args()
    if args.basic is None:
        args.basic = LEVEL_CUT.get(args.level, 6.0)

    weights = []
    for w in args.weight:
        k, _, v = w.partition("=")
        weights.append((k, float(v)))

    score: Counter = Counter()
    raw: Counter = Counter()
    where: dict[str, set] = defaultdict(set)
    surface: dict[str, Counter] = defaultdict(Counter)
    lower_seen: set = set()          # seen lowercase at least once → not a name
    src: dict[str, set] = defaultdict(set)

    for f in files(args.paths):
        wgt = next((v for k, v in weights if k in str(f)), 1.0)
        for tid, body in blocks(f.read_text(encoding="utf-8"), f.stem.split(".")[0]):
            body = CODE.sub(" ", body)
            toks = TOKEN.findall(body)
            lems = [t.lower() if "-" in t else simplemma.lemmatize(t.lower(), lang="en") for t in toks]  # leave event-driven as is
            for i, lem in enumerate(lems):
                if len(lem) < 2:
                    continue
                keys = [(lem, toks[i])]
                # phrasal verbs: keep up, keep up with, scale out
                if lem not in PARTICLES and i + 1 < len(lems) and lems[i + 1] in PARTICLES \
                        and zipf_frequency(lem, "en") > 3.5:
                    keys.append((f"{lem} {lems[i + 1]}", f"{toks[i]} {toks[i + 1]}"))
                    if i + 2 < len(lems) and lems[i + 2] in PARTICLES:
                        keys.append((f"{lem} {lems[i + 1]} {lems[i + 2]}", " ".join(toks[i:i + 3])))
                for k, seen in keys:
                    if not seen[:1].isupper():
                        lower_seen.add(k)
                    src[k].add(next((kk for kk, _ in weights if kk in str(f)), "topics"))
                    score[k] += wgt
                    raw[k] += 1
                    where[k].add(tid)
                    surface[k][seen] += 1

    keep = set()
    if args.keep:
        keep = {l.strip().lower() for l in Path(args.keep).read_text(encoding="utf-8").splitlines() if l.strip()}

    rows = []
    for k, s in score.items():
        z = zipf_frequency(k, "en")
        phrase = " " in k
        if k not in keep:
            if raw[k] < args.min_count:
                continue
            if not phrase and z >= args.basic:
                continue
            if phrase and raw[k] < 2:
                continue  # random particle combinations
            if not phrase and k not in lower_seen and z < 3.5:
                continue  # name or product: Kafka, Grafana, Acme
        rows.append({"en": k, "score": round(s, 2), "count": raw[k], "zipf": round(z, 2), "band": band(z),
                     "src": sorted(src[k]),
                     "seen_as": surface[k].most_common(1)[0][0], "used_in": sorted(where[k]),
                     **({"keep": True} if k in keep else {})})

    rows.sort(key=lambda r: (not r.get("keep", False), -r["score"], -r["zipf"], r["en"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    text = yaml.safe_dump({"candidates": rows}, allow_unicode=True, sort_keys=False, width=120)
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"candidates: {len(rows)} → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
