#!/usr/bin/env python3
"""Vocabulary method, step 1: frequency analysis of one's own materials.

What the person will talk about is written in their materials in the explanation language
(content/*.<lang>.md, stories, answers; the language is explain-language, tools/langs.py). The script counts which
words occur there most often: their English equivalents are what one needs to know.

    run word_freq.py content/ --top 600 --out prep/word-freq.yaml          # language from prep/answers.yaml
    run word_freq.py content/ --lang de --top 600 --out prep/word-freq.yaml

If the explanation language is English, there is nothing to translate: the vocabulary
is built directly from the English text (rank_words.py) and this step is skipped.

1. Cleanup: "@@ id" lines, code blocks and inline code, URLs are not counted.
2. Explanation-language words: lowercase, base form.
   Russian: pymorphy3, a stop list and only content parts of speech
   (nouns, verbs, adjectives, adverbs, participles, adverbial participles,
   numerals). Other languages: simplemma, function words are cut by
   frequency (zipf ≥ 6 in that language: der, und, ist).
3. English words in the text are counted separately: these are terms the person
   already reads (don't translate them, but they can go into --keep if they need to be said).
4. Text coverage by the top words: 100 / 200 / 300 / 500 / 1000. It shows where
   the tail stops paying off: usually the top 1000 covers ~80% of the text.

Output: top — lemmas with frequency and places of use (topic ids), en — English
words in the text, coverage — coverage table. Then the agent translates the top
lemmas into English (modules/english.md, step 2).
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
    sys.exit(f"Missing dependency: {e.name}. Run via tools/run, it installs everything itself.")

BLOCK = re.compile(r"^@@\s+([a-z][\w.-]*)\s*$", re.M)
CODE = re.compile(r"```.*?```|`[^`]*`", re.S)
URL = re.compile(r"https?://\S+|www\.\S+")
RU = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")   # words in any alphabet
EN = re.compile(r"[A-Za-z][A-Za-z'-]*[A-Za-z]")
KEEP_POS = {"NOUN", "VERB", "INFN", "ADJF", "ADJS", "COMP", "ADVB", "PRTF", "PRTS", "GRND", "NUMR"}
STOP = set("""
и в во не на с со что как а то по к ко из у о об от до за для при же ли бы но или да нет так это
этот эта эти тот та те такой такая такие весь вся все всё его её их он она они оно мы вы я ты
себя свой своя свои который которая которые которое где когда если чтобы потому поэтому тоже
также уже ещё еще только даже очень можно нужно надо есть был была были будет быть через между
под над перед после без около вместо кроме про чем чём кто чей там тут здесь вот ну ли же бы
""".split())
COVER = [100, 200, 300, 500, 1000]


def files(paths, lang):
    out = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(x for x in p.rglob(f"*.{lang}.md"))
        elif p.exists():
            out.append(p)
        else:
            print(f"! no such file: {p}", file=sys.stderr)
    return out


def blocks(text, fallback):
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
    ap.add_argument("--top", type=int, default=600, help="how many lemmas to hand over for translation")
    ap.add_argument("--lang", help="explanation language (default: from --dir/prep/answers.yaml)")
    ap.add_argument("--dir", default=".", help="prep folder to take the language from")
    ap.add_argument("--out", default="-")
    args = ap.parse_args()
    if not args.lang:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import langs as lg
        args.lang = lg.primary(Path(args.dir))
    if args.lang == "en":
        sys.exit("The explanation language is English: nothing to translate, use rank_words.py")

    if args.lang == "ru":
        import pymorphy3
        morph = pymorphy3.MorphAnalyzer()

    def analyze(w):
        if args.lang == "ru":
            p = morph.parse(w)[0]
            return p.normal_form, p.tag.POS
        lemma = simplemma.lemmatize(w, lang=args.lang)
        return lemma.lower(), ("FUNC" if zipf_frequency(lemma, args.lang) >= 6.0 else "NOUN")
    cache: dict[str, tuple] = {}
    ru, en = Counter(), Counter()
    where = defaultdict(set)
    ru_tokens = 0
    for f in files(args.paths, args.lang):
        for tid, body in blocks(f.read_text(encoding="utf-8"), f.stem.split(".")[0]):
            body = URL.sub(" ", CODE.sub(" ", body))
            for w in RU.findall(body):
                w = w.lower()
                if (args.lang == "ru" and w in STOP) or len(w) < 2 or re.fullmatch(r"[a-z'-]+", w):
                    continue   # Latin script means English terms, they are counted separately
                if w not in cache:
                    cache[w] = analyze(w)
                lemma, pos = cache[w]
                if pos not in KEEP_POS or (args.lang == "ru" and lemma in STOP):
                    continue
                ru[lemma] += 1
                ru_tokens += 1
                where[lemma].add(tid)
            for w in EN.findall(body):
                en[w.lower()] += 1

    ranked = ru.most_common()
    coverage = []
    for n in COVER:
        if n > len(ranked) and coverage:
            break
        covered = sum(c for _, c in ranked[:n])
        coverage.append({"top": n, "covers": f"{round(100 * covered / max(ru_tokens, 1))}%"})

    out = {
        "lang": args.lang,
        "summary": {"ru_words": ru_tokens, "ru_unique": len(ru), "en_words": sum(en.values()), "en_unique": len(en)},
        "coverage": coverage,
        "top": [{"ru": w, "count": c, "used_in": sorted(where[w])[:8]} for w, c in ranked[:args.top]],
        "en": [{"en": w, "count": c} for w, c in en.most_common(300)],
    }
    text = yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120)
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        s = out["summary"]
        print(f"words ({args.lang}) {s['ru_words']} (unique {s['ru_unique']}), English {s['en_words']} (unique {s['en_unique']})", file=sys.stderr)
        for c in coverage:
            print(f"  top-{c['top']:<5} covers {c['covers']} of the text", file=sys.stderr)
        print(f"→ {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
