#!/usr/bin/env python3
"""Vocabulary method, step 6: rank cards by importance.

    run score_words.py prep/words.yaml content/ --boosts prep/word-boosts.txt

Two numbers per word:
- overall English frequency: zipf_frequency (wordfreq): 6 is very common, 3 is rare;
- frequency in one's own materials: the word's translation (field ru: translation
  into the explanation language; the field name is historical) is lemmatized and
  its occurrences in content/*.<lang>.md are counted, plus occurrences of the
  English word itself in content/*.en.md.

    score = zipf + 0.6 × log10(1 + frequency_in_materials) + boost

The logarithm keeps a word seen 400 times from swamping the rest.
Boost (--boosts, one "word +1.0" per line):
- +1.0: words and phrases specific to interviews: trade-off, outage, stakeholder,
  single point of failure, under the hood, rely on, whereas;
- +1.2…+2.2: terms without which one's topics can't be explained: idempotent +2.2,
  concurrency +2.2, scalability +2.0. By overall frequency they are rare and without
  a boost would sink to the end, even though they are needed first.

The script sorts by descending score and rewrites rank (1…N), g (groups of
--group-size, default 50), zipf and band in the file. It does not touch id:
progress is tied to it. Other card fields stay as they were.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import simplemma
    import yaml
    from wordfreq import zipf_frequency
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency: {e.name}. Run via tools/run.")

CODE = re.compile(r"```.*?```|`[^`]*`", re.S)
RU = re.compile(r"[^\W\d_]+")
SKIP_RU = set("и в на с к по о от до за для или не что как это быть свой".split())


def band(z: float) -> int:
    return 1 if z >= 5 else 2 if z >= 4 else 3 if z >= 3 else 4


def corpus(dirs, suffix):
    out = []
    for d in map(Path, dirs):
        fs = [d] if d.is_file() else sorted(d.rglob(f"*{suffix}"))
        out += [CODE.sub(" ", f.read_text(encoding="utf-8")) for f in fs if f.name.endswith(suffix)]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words", help="prep/words.yaml")
    ap.add_argument("content", nargs="+", help="folders or files with materials")
    ap.add_argument("--boosts", help="file with one \"word +1.0\" per line")
    ap.add_argument("--group-size", type=int)
    ap.add_argument("--lang", help="explanation language (default: from --dir/prep/answers.yaml)")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--dry-run", action="store_true", help="only show the top, do not touch the file")
    args = ap.parse_args()

    path = Path(args.words)
    deck = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    words = deck.get("words") or []
    size = args.group_size or deck.get("group_size") or 50

    boosts = {}
    if args.boosts and Path(args.boosts).exists():
        for line in Path(args.boosts).read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*(.+?)\s+([+-]\d+(?:\.\d+)?)\s*$", line)
            if m and not line.lstrip().startswith("#"):
                boosts[m.group(1).lower()] = float(m.group(2))

    if not args.lang:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import langs as lg
        args.lang = lg.primary(Path(args.dir))
    if args.lang == "ru":
        import pymorphy3
        morph = pymorphy3.MorphAnalyzer()
        lem = lambda w: morph.parse(w)[0].normal_form
    elif args.lang == "en":
        lem = lambda w: w   # explanation language is English: frequency only from .en.md
    else:
        lem = lambda w: simplemma.lemmatize(w, lang=args.lang).lower()
    ru_freq = Counter() if args.lang == "en" else \
        Counter(lem(w.lower()) for w in RU.findall(corpus(args.content, f".{args.lang}.md")))
    en_text = corpus(args.content, ".en.md").lower()

    for w in words:
        en = str(w["en"]).lower()
        z = zipf_frequency(en, "en")
        ru_lemmas = set() if args.lang == "en" else \
            {lem(x.lower()) for x in RU.findall(str(w.get("ru", "")).split(",")[0])} - SKIP_RU
        f_ru = max((ru_freq[x] for x in ru_lemmas), default=0)
        f_en = len(re.findall(r"\b" + re.escape(en) + r"\b", en_text))
        f = f_ru + f_en
        w["_score"] = z + 0.6 * math.log10(1 + f) + boosts.get(en, 0.0)
        w["_f"] = f
        w["zipf"] = round(z, 2)
        w["band"] = band(z)

    words.sort(key=lambda w: (-w["_score"], w["en"]))
    for i, w in enumerate(words, 1):
        w["rank"] = i
        w["g"] = (i - 1) // size + 1

    print(f"{'rank':>4}  {'score':>5}  {'zipf':>4}  {'freq':>5}  word", file=sys.stderr)
    for w in words[:25]:
        print(f"{w['rank']:>4}  {w['_score']:5.2f}  {w['zipf']:4.1f}  {w['_f']:>5}  {w['en']}", file=sys.stderr)
    for w in words:
        w.pop("_score"); w.pop("_f")

    if args.dry_run:
        return 0
    n = (len(words) + size - 1) // size
    old = {g.get("g"): g for g in deck.get("groups") or []}
    deck["groups"] = [old.get(g, {"g": g, "title": f"Слова {(g - 1) * size + 1}–{min(g * size, len(words))}",
                                   "title_en": f"Words {(g - 1) * size + 1}–{min(g * size, len(words))}"}) for g in range(1, n + 1)]
    deck["words"] = words
    path.write_text(yaml.safe_dump(deck, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    print(f"cards {len(words)}, groups {n} of {size} → {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
